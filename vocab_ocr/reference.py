"""Build a portable textbook reference bundle from source-page transcriptions.

No model or OCR service is called here. Codex reads rendered original pages and
writes reviewed page records. Publication requires every planned source page to
have a record bound to the current source PDF digest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import tempfile
import unicodedata
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from vocab_ocr.pep.catalog import BOOKS
from vocab_ocr.pep.parse_appendix import UnitRange, map_page_to_unit
from vocab_ocr.shared.paths import DEFAULT_WORK, DOWNLOADS

WORK = DEFAULT_WORK / "reference-rebuild"
OUTPUT = DOWNLOADS / "vocab-reference"
VERSION = 2

# Exact editions checked against their rendered contents pages. The legacy OCR
# fallback had only twelve Units for the fourteen-Unit Grade 9 textbook.
REVIEWED_JUNIOR_TOC: dict[str, tuple[int, list[tuple[str, int]], int]] = {
    "junior-7a": (140, [("starter-1", 1), ("starter-2", 7), ("starter-3", 13),
                       ("1", 19), ("2", 27), ("3", 35), ("4", 43),
                       ("5", 51), ("6", 59), ("7", 67)], 75),
    "junior-7b": (132, [(str(i), 1 + 8 * (i - 1)) for i in range(1, 9)], 65),
    "junior-8a": (150, [(str(i), 1 + 10 * (i - 1)) for i in range(1, 9)], 81),
    "junior-8b": (154, [(str(i), 1 + 10 * (i - 1)) for i in range(1, 9)], 81),
    "junior-9": (204, [(str(i), 1 + 8 * (i - 1)) for i in range(1, 15)], 113),
}


def junior_unit(book_id: str, source_page_count: int, body_page: int) -> str:
    count, starts, end = REVIEWED_JUNIOR_TOC[book_id]
    if count != source_page_count:
        raise ValueError("TOC edition mismatch")
    unit = map_page_to_unit(body_page, [UnitRange(u, n) for u, n in starts], end)
    if unit is None:
        raise ValueError(f"body page has no checked Unit: {book_id}/{body_page}")
    return unit


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def lemma(word: str) -> str:
    # Keep the printed headword separately; normal keyboard apostrophes must find
    # book phrases printed with curly quotes. Accents and names remain intact.
    normalized = unicodedata.normalize("NFC", word).translate(str.maketrans({"’": "'", "‘": "'"}))
    result = " ".join(normalized.strip().lower().split())
    if not result or "|" in result or any(ord(c) < 32 for c in result):
        raise ValueError(f"invalid source word: {word!r}")
    return result


def validate_regions(regions: list[dict]) -> None:
    if not isinstance(regions, list):
        raise ValueError("regions must be a list")
    ids = []
    for region in regions:
        name, box = region.get("id"), region.get("bbox")
        if not isinstance(name, str) or not name or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for c in name):
            raise ValueError(f"invalid region id: {name!r}")
        ids.append(name)
        if (not isinstance(box, list) or len(box) != 4 or
                any(type(n) not in (int, float) or not math.isfinite(n) for n in box) or
                not 0 <= box[0] < box[2] <= 1 or not 0 <= box[1] < box[3] <= 1):
            raise ValueError(f"invalid normalized region: {region}")
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate region id")


def validate_record(record: dict, book: dict, page: int) -> None:
    if (record.get("source_sha256") != book["source_sha256"] or
            record.get("source_pdf_page") != page or record.get("reviewed_by") != "codex-direct-vision"):
        raise ValueError("source or review identity mismatch")
    printed = record.get("printed_page")
    if printed is not None and (type(printed) is not int or printed < 1):
        raise ValueError("invalid printed page")
    validate_regions(record["regions"])
    entries = record["entries"]
    if not isinstance(entries, list):
        raise ValueError("entries must be a list")
    if record.get("kind") == "non_vocab":
        if entries or record["regions"] or not record.get("reason"):
            raise ValueError("non-vocabulary page needs a reason and no entries/regions")
        return
    if record.get("kind") != "vocab" or not entries:
        raise ValueError("invalid or empty vocabulary page")
    ids = {r["id"] for r in record["regions"]}
    lesson = next((p["unit"] for p in book["pages"] if p["source_pdf_page"] == page), None)
    for entry in entries:
        if (entry.get("lemma") != lemma(entry["word"]) or not entry.get("unit") or
                not entry.get("zh") or entry.get("region_id") not in ids):
            raise ValueError(f"invalid source entry: {entry}")
        if book["stage"] == "nce" and entry["unit"] != lesson:
            raise ValueError("word Lesson disagrees with the reviewed source-page plan")
        aliases = entry.get("aliases", [])
        if not isinstance(aliases, list) or any(not isinstance(a, str) for a in aliases):
            raise ValueError("aliases must be printed alternative headwords")
        for alias in aliases:
            lemma(alias)
        body_page = entry.get("page")
        if body_page is not None and (type(body_page) is not int or body_page < 1):
            raise ValueError("invalid body page")
        if book["stage"] == "junior" and body_page is not None:
            # Detect stale records after a corrected contents-page mapping.
            book_id = book.get("id")
            if book_id is None or entry["unit"] != junior_unit(book_id, book["source_page_count"], body_page):
                raise ValueError("body page and checked Unit disagree")


def prepare(work: Path = WORK, nce_dir: Path | None = None) -> dict:
    """Freeze source identities and candidate pages; no old words are reused."""
    from vocab_ocr.nce.export_vocab_pages import load_page_map

    nce_dir = nce_dir or Path.home() / "Pdf/新概念课文1-4PDF"
    books = {}
    # Include the whole appendix area. Each page is classified by direct review,
    # so older OCR ranges cannot silently omit words or include acknowledgements.
    junior_starts = {"junior-7a": 116, "junior-7b": 107, "junior-8a": 121,
                     "junior-8b": 123, "junior-9": 172}
    for book in BOOKS:
        count = len(PdfReader(book.path).pages)
        first = junior_starts.get(book.id, max(1, count - 35))
        books[book.id] = {
            "id": book.id,
            "title": book.title, "series": "pep", "stage": book.stage,
            "source": str(book.path), "source_sha256": sha256(book.path),
            "source_page_count": count,
            "pages": [{"source_pdf_page": n, "unit": ""} for n in range(first, count + 1)],
        }
    for book_id, data in load_page_map()["books"].items():
        source = nce_dir / data["source_file"]
        if len(PdfReader(source).pages) != data["source_page_count"]:
            raise ValueError(f"source edition changed: {book_id}")
        books[book_id] = {
            "id": book_id,
            "title": f"新概念英语第{'一二三四'[int(book_id[-1]) - 1]}册",
            "series": "nce", "stage": "nce", "source": str(source),
            "source_sha256": sha256(source), "source_page_count": data["source_page_count"],
            "pages": [{"source_pdf_page": page, "unit": str(unit), "role": role}
                      for unit, page, role in data["pages"]],
        }
    plan = {"v": 1, "reader": "codex-direct-vision", "books": books}
    destination = work / "sources.json"
    if destination.exists() and json.loads(destination.read_text()) != plan:
        raise ValueError("source plan changed; preserve/review existing transcripts before preparing another run")
    write_json(destination, plan)
    return plan


def record_page(book_id: str, page: int, printed_page: int | None,
                rows: str, *, regions: list[dict], kind: str = "vocab",
                reason: str | None = None, work: Path = WORK) -> dict:
    """Save directly transcribed rows: word|unit-or-p.N|Chinese gloss|region id.

    For NCE the page's checked Lesson is used when the second field is empty.
    PEP junior p.N references are mapped using the exact-edition TOC. Words from
    primary-school lists may have no body reference and an explicit Unit instead.
    """
    book = json.loads((work / "sources.json").read_text())["books"][book_id]
    planned = next((p for p in book["pages"] if p["source_pdf_page"] == page), None)
    if planned is None:
        raise ValueError(f"page outside source plan: {book_id}/{page}")
    region_ids = {r["id"] for r in regions}
    entries = []
    for line in rows.strip().splitlines():
        if not line.strip():
            continue
        fields = line.split("|")
        if len(fields) != 4:
            raise ValueError(f"four fields required: {line!r}")
        word, ref, zh, region = (f.strip() for f in fields)
        unit, body_page = ref or planned["unit"], None
        if book["stage"] == "junior" and ref.startswith("p."):
            body_page = int(ref[2:])
            unit = junior_unit(book_id, book["source_page_count"], body_page)
        if not unit or region not in region_ids:
            raise ValueError(f"missing Unit/Lesson or region: {line}")
        if not zh:
            raise ValueError(f"empty textbook gloss: {line}")
        entries.append({"word": word, "lemma": lemma(word), "unit": unit,
                        "page": body_page, "zh": zh, "region_id": region})
    if kind == "vocab" and not entries:
        raise ValueError("a vocabulary page needs complete transcribed entries")
    if kind == "non_vocab" and (entries or not reason):
        raise ValueError("non-vocabulary page needs a reason and no entries")
    result = {"source_pdf_page": page, "source_sha256": book["source_sha256"],
              "printed_page": printed_page, "kind": kind, "reason": reason,
              "reviewed_by": "codex-direct-vision", "regions": regions, "entries": entries}
    validate_record(result, book, page)
    write_json(work / "books" / book_id / "pages" / f"{page:03d}.json", result)
    return result


def read_corpus(work: Path = WORK) -> tuple[dict, dict, list[str]]:
    plan = json.loads((work / "sources.json").read_text())
    records, blockers = {}, []
    for book_id, book in plan["books"].items():
        if sha256(Path(book["source"])) != book["source_sha256"]:
            blockers.append(f"{book_id}: source PDF changed")
        records[book_id] = []
        for p in book["pages"]:
            page = p["source_pdf_page"]
            path = work / "books" / book_id / "pages" / f"{page:03d}.json"
            if not path.exists():
                blockers.append(f"{book_id}/{page}: not transcribed")
                continue
            try:
                row = json.loads(path.read_text())
                validate_record(row, book, page)
            except (ValueError, KeyError, TypeError) as error:
                blockers.append(f"{book_id}/{page}: {error}")
                continue
            records[book_id].append(row)
    return plan, records, blockers


def build_bundle(work: Path = WORK, output: Path = OUTPUT) -> dict:
    plan, records, blockers = read_corpus(work)
    if blockers:
        raise ValueError(f"publication blocked: {len(blockers)} issues; first: {blockers[0]}")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".vocab-reference-", dir=output.parent))
    try:
        payloads = {series: {"v": VERSION, "books": {}, "pdfs": {}, "w": {}}
                    for series in ("pep", "nce")}
        page_map = {"v": 1, "coordinate_system": "visible-page-top-left-normalized", "books": {}}
        for book_id, book in plan["books"].items():
            source = PdfReader(book["source"])
            writer, maps = PdfWriter(), []
            index = payloads[book["series"]]
            index["books"][book_id] = book["title"]
            for record in records[book_id]:
                if record["kind"] != "vocab":
                    continue
                original = source.pages[record["source_pdf_page"] - 1]
                writer.add_page(original)
                snapshot_page = len(writer.pages)
                planned_page = next(p for p in book["pages"] if p["source_pdf_page"] == record["source_pdf_page"])
                maps.append({"snapshot_page": snapshot_page, "source_pdf_page": record["source_pdf_page"],
                             "printed_page": record["printed_page"], "regions": record["regions"],
                             "role": planned_page.get("role", "vocab"),
                             "units": sorted({e["unit"] for e in record["entries"]}),
                             "width": float(original.cropbox.width), "height": float(original.cropbox.height),
                             "rotation": original.rotation})
                writer.add_outline_item(f"原书第 {record['printed_page'] or record['source_pdf_page']} 页", snapshot_page - 1)
                for entry in record["entries"]:
                    identity = (book_id, entry["unit"], entry["page"], entry["zh"], entry["word"])
                    for key in {lemma(w) for w in [entry["word"], *entry.get("aliases", [])]}:
                        hits = index["w"].setdefault(key, [])
                        hit = next((h for h in hits if (h["book"], h["unit"], h.get("page"), h["zh"], h["headword"]) == identity), None)
                        if hit is None:
                            hit = {"book": book_id, "unit": entry["unit"], "zh": entry["zh"],
                                   "headword": entry["word"], "pdf_pages": [], "references": []}
                            if entry["page"] is not None:
                                hit["page"] = entry["page"]
                            hits.append(hit)
                        if snapshot_page not in hit["pdf_pages"]:
                            hit["pdf_pages"].append(snapshot_page)
                        reference = {"pdf_page": snapshot_page, "region_id": entry["region_id"]}
                        if reference not in hit["references"]:
                            hit["references"].append(reference)
            if not writer.pages:
                raise ValueError(f"no reviewed vocabulary pages: {book_id}")
            relative = f"pdf/{book_id}-vocab.pdf"
            destination = staging / relative
            destination.parent.mkdir(exist_ok=True)
            with destination.open("wb") as stream:
                writer.write(stream)
            if len(PdfReader(destination).pages) != len(maps):
                raise ValueError(f"snapshot count mismatch: {book_id}")
            pdf = {"file": relative, "sha256": sha256(destination), "page_count": len(maps)}
            index["pdfs"][book_id] = pdf
            page_map["books"][book_id] = {**pdf, "source_sha256": book["source_sha256"],
                                          "source_page_count": book["source_page_count"], "pages": maps}
            if book["stage"] == "junior":
                _, starts, end = REVIEWED_JUNIOR_TOC[book_id]
                page_map["books"][book_id].update(
                    unit_starts=[{"unit": u, "printed_page": n} for u, n in starts],
                    body_end_page_exclusive=end,
                )
        for series, index in payloads.items():
            index["w"] = dict(sorted(index["w"].items()))
            write_json(staging / f"{series}-vocab-index.min.json", index)
        write_json(staging / "vocab-page-map.json", page_map)
        manifest = {"v": 1, "index_version": VERSION, "files": {
            str(path.relative_to(staging)): sha256(path) for path in sorted(staging.rglob("*")) if path.is_file()}}
        write_json(staging / "manifest.json", manifest)
        # Validate every reference before publishing a directory as one unit.
        validate_bundle(staging)
        backup = output.with_name(output.name + ".previous")
        if backup.exists():
            raise ValueError(f"preserve or remove previous backup before another publication: {backup}")
        if output.exists():
            os.replace(output, backup)
        try:
            os.replace(staging, output)
        except BaseException:
            if backup.exists():
                os.replace(backup, output)
            raise
        if backup.exists():
            shutil.rmtree(backup)
        return {"output": str(output.resolve()), "books": len(page_map["books"]),
                "pages": sum(p["page_count"] for p in page_map["books"].values()),
                "words": {s: len(i["w"]) for s, i in payloads.items()}}
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def validate_bundle(path: Path) -> None:
    manifest = json.loads((path / "manifest.json").read_text())
    if manifest.get("v") != 1 or manifest.get("index_version") != VERSION:
        raise ValueError("unsupported reference bundle version")
    files = manifest["files"]
    actual = {str(p.relative_to(path)) for p in path.rglob("*") if p.is_file() and p != path / "manifest.json"}
    if set(files) != actual:
        raise ValueError("manifest does not cover the complete bundle")
    for relative, digest in files.items():
        target = path / relative
        if (Path(relative).is_absolute() or ".." in Path(relative).parts or
                target.is_symlink() or not target.resolve().is_relative_to(path.resolve()) or
                sha256(target) != digest):
            raise ValueError(f"bundle file mismatch: {relative}")
    page_map = json.loads((path / "vocab-page-map.json").read_text())
    if page_map.get("v") != 1 or page_map.get("coordinate_system") != "visible-page-top-left-normalized":
        raise ValueError("unsupported page map")
    mapped_books = page_map["books"]
    used_books, required_files = set(), {"pep-vocab-index.min.json", "nce-vocab-index.min.json", "vocab-page-map.json"}
    for series in ("pep", "nce"):
        index = json.loads((path / f"{series}-vocab-index.min.json").read_text())
        if index.get("v") != VERSION:
            raise ValueError("index version mismatch")
        if set(index["books"]) != set(index["pdfs"]) or used_books.intersection(index["books"]):
            raise ValueError("book catalogue and PDFs disagree")
        used_books.update(index["books"])
        for book_id, pdf in index["pdfs"].items():
            mapped = mapped_books.get(book_id)
            relative, count = pdf["file"], pdf["page_count"]
            if (not mapped or any(mapped.get(k) != pdf[k] for k in ("file", "page_count", "sha256")) or
                    relative not in files or files[relative] != pdf["sha256"] or
                    type(count) is not int or count < 1 or len(PdfReader(path / relative).pages) != count):
                raise ValueError(f"PDF metadata mismatch: {book_id}")
            required_files.add(relative)
            pages = mapped["pages"]
            if len(pages) != count or [p["snapshot_page"] for p in pages] != list(range(1, count + 1)):
                raise ValueError(f"snapshot page map mismatch: {book_id}")
            previous = 0
            for p in pages:
                source_page = p["source_pdf_page"]
                if type(source_page) is not int or not previous < source_page <= mapped["source_page_count"]:
                    raise ValueError(f"invalid original page ordering: {book_id}")
                previous = source_page
                validate_regions(p["regions"])
        for word, hits in index["w"].items():
            if lemma(word) != word or not hits:
                raise ValueError(f"invalid lookup key: {word}")
            for hit in hits:
                pdf = index["pdfs"].get(hit["book"])
                destinations = hit["pdf_pages"]
                if (not pdf or not hit.get("unit") or not hit.get("zh") or not hit.get("headword") or
                        not destinations or any(type(n) is not int or not 1 <= n <= pdf["page_count"] for n in destinations) or
                        len(destinations) != len(set(destinations))):
                    raise ValueError(f"bad PDF destination: {word} {hit}")
                references = hit["references"]
                if {r["pdf_page"] for r in references} != set(destinations):
                    raise ValueError(f"region references disagree with pages: {word}")
                for ref in references:
                    mapped_page = mapped_books[hit["book"]]["pages"][ref["pdf_page"] - 1]
                    if ref["region_id"] not in {r["id"] for r in mapped_page["regions"]} or hit["unit"] not in mapped_page["units"]:
                        raise ValueError(f"bad region or unit reference: {word}")
    if used_books != set(mapped_books) or required_files != set(files):
        raise ValueError("bundle contains missing or unreferenced books/files")


def install_bundle(bundle: Path, destination: Path) -> dict:
    """Install the complete resource directory, validating before replacement."""
    validate_bundle(bundle)
    if bundle.resolve() == destination.resolve():
        raise ValueError("source bundle and destination must differ")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".textbook-resources-", dir=destination.parent))
    backup = destination.with_name(destination.name + ".previous")
    try:
        shutil.copytree(bundle, staging, dirs_exist_ok=True)
        validate_bundle(staging)
        if backup.exists():
            raise ValueError(f"preserve previous backup before installation: {backup}")
        if destination.exists():
            os.replace(destination, backup)
        try:
            os.replace(staging, destination)
        except BaseException:
            if backup.exists():
                os.replace(backup, destination)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return {"installed": str(destination.resolve())}


def publish_indexes(bundle: Path, destination: Path) -> dict:
    """Export the small versioned indexes/map for source control, without PDFs."""
    validate_bundle(bundle)
    files = {"pep-vocab-index.min.json": "vocab-index.min.json",
             "nce-vocab-index.min.json": "nce-vocab-index.min.json",
             "vocab-page-map.json": "vocab-page-map.json"}
    for source, target in files.items():
        write_json(destination / target, json.loads((bundle / source).read_text()))
    return {"published": str(destination.resolve()), "files": list(files.values())}


def export_regions(bundle: Path = OUTPUT, output: Path = DEFAULT_WORK / "vocab-page-regions", dpi: int = 200) -> dict:
    """Rebuild derived crops from the portable full-page PDFs and their map.

    Poppler renders the visible page, including its PDF rotation; stored boxes
    therefore use the same top-left coordinate system as the reviewed images.
    These crops never replace the reader PDFs or enter the application bundle.
    """
    from PIL import Image
    from vocab_ocr.shared.pdf_render import render_pages

    validate_bundle(bundle)
    page_map = json.loads((bundle / "vocab-page-map.json").read_text())
    output.mkdir(parents=True, exist_ok=True)
    count = 0
    for book_id, book in page_map["books"].items():
        destination = output / book_id
        destination.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="vocab-regions-") as temporary:
            rendered = render_pages(bundle / book["file"], Path(temporary), "page", 1, book["page_count"], dpi, crop_box=True)
            for row, image_path in zip(book["pages"], rendered, strict=True):
                with Image.open(image_path) as page:
                    width, height = page.size
                    for region in row["regions"]:
                        x1, y1, x2, y2 = region["bbox"]
                        box = (math.floor(x1 * width), math.floor(y1 * height), math.ceil(x2 * width), math.ceil(y2 * height))
                        name = f"{row['snapshot_page']:03d}-{region['id']}"
                        page.crop(box).save(destination / f"{name}.png")
                        write_json(destination / f"{name}.json", {
                            "v": 1, "book": book_id, "region_id": region["id"], "bbox": region["bbox"],
                            "coordinate_system": page_map["coordinate_system"], "dpi": dpi,
                            "source_sha256": book["source_sha256"], "pdf_sha256": book["sha256"],
                            "source_pdf_page": row["source_pdf_page"], "pdf_page": row["snapshot_page"],
                            "map_sha256": sha256(bundle / "vocab-page-map.json"),
                        })
                        count += 1
    return {"regions": count, "output": str(output.resolve())}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "status", "build", "validate", "regions", "install", "publish"))
    parser.add_argument("--work", type=Path, default=WORK)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--regions-output", type=Path, default=DEFAULT_WORK / "vocab-page-regions")
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument("--destination", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        plan = prepare(args.work)
        result = {"books": len(plan["books"]), "pages": sum(len(b["pages"]) for b in plan["books"].values())}
    elif args.command == "status":
        plan, records, blockers = read_corpus(args.work)
        result = {"books": len(plan["books"]), "reviewed_pages": sum(len(r) for r in records.values()),
                  "remaining_pages": len(blockers), "next": blockers[:5]}
    elif args.command == "build":
        result = build_bundle(args.work, args.output)
    elif args.command == "regions":
        result = export_regions(args.output, args.regions_output, args.dpi)
    elif args.command == "install":
        if args.destination is None:
            parser.error("install requires --destination (the application resource folder)")
        result = install_bundle(args.output, args.destination)
    elif args.command == "publish":
        result = publish_indexes(args.output, args.destination or Path("data/vocab"))
    else:
        validate_bundle(args.output)
        result = {"ok": True}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
