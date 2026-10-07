"""Resumable, source-locatable PEP visual extraction and gated publication."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from vocab_ocr.pep.catalog import BOOKS, PepBook
from vocab_ocr.pep.pipeline import unit_map_for_book
from vocab_ocr.pep.parse_appendix import map_page_to_unit
from vocab_ocr.pep.vision import GEMMA_MODEL, VisionTranscriptionError, transcribe_page
from vocab_ocr.shared.build_index import build_inverted_index
from vocab_ocr.shared.paths import DEFAULT_OUT, DEFAULT_WORK, ROOT
from vocab_ocr.shared.pdf_render import pdf_page_count, render_pages


VISION_WORK = DEFAULT_WORK / "vision"
REVIEW_SHEET = DEFAULT_WORK / "pep-05-review.csv"
FIXED_SAMPLE = DEFAULT_WORK / "pep-audit-sample.csv"
_JUNIOR_REF = re.compile(r"^p[.．]?\s*(\d{1,3})$", re.I)
_SENIOR_REF = re.compile(r"^[（(]\s*(\d{1,2}|w)\s*[）)]$", re.I)


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        temp_path = Path(stream.name)
    os.replace(temp_path, path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_book(book: PepBook) -> dict:
    """Use the prior PDF band's location, never its OCR words or verdicts."""
    path = DEFAULT_OUT / "books" / f"{book.id}.json"
    if not path.exists():
        raise FileNotFoundError(f"no reviewed page range for {book.id}: {path}")
    old = json.loads(path.read_text(encoding="utf-8"))
    total = pdf_page_count(book.path)
    if old.get("book_id") != book.id or old.get("pdf_pages") != total:
        raise ValueError(f"PDF or page range changed for {book.id}; re-locate and review the range")
    source_pdf = Path(str(old.get("pdf") or ""))
    if not source_pdf.is_absolute():
        source_pdf = ROOT / source_pdf
    if source_pdf.resolve() != book.path.resolve():
        raise ValueError(f"cached page range belongs to a different PDF: {book.id}")
    start, end = old["vocab_pdf_pages"]
    if not (isinstance(start, int) and isinstance(end, int) and 1 <= start <= end <= total):
        raise ValueError(f"invalid vocabulary PDF page range for {book.id}")
    return old


def _entry_from_vision(entry: dict, *, book: PepBook, unit_starts: list, unit_end: int | None) -> dict:
    ref = (entry.get("ref") or "").strip()
    page = None
    unit = None
    problems = list(entry.get("uncertainty") or [])
    if book.stage == "junior":
        match = _JUNIOR_REF.fullmatch(ref)
        if match:
            page = int(match.group(1))
            unit = map_page_to_unit(page, unit_starts, unit_end)
        else:
            problems.append(f"unparsed printed p. reference: {ref!r}")
        if unit is None:
            problems.append(f"no verified unit for printed page {page!r}")
    else:
        match = _SENIOR_REF.fullmatch(ref)
        if match:
            unit = match.group(1).lower().lstrip("0") or "0"
        else:
            problems.append(f"unparsed printed Unit reference: {ref!r}")
    return {
        "word": entry.get("word"),
        "book_id": book.id,
        "book_title": book.title,
        "stage": book.stage,
        "unit": unit,
        "page": page,
        "zh": entry.get("zh"),
        "source": "vision",
        "pdf_page": entry["source_pdf_page"],
        "column": entry["column"],
        "ref": entry.get("ref"),
        "raw": entry.get("raw"),
        "uncertainty": problems,
    }


def process_vision_book(
    book: PepBook,
    *,
    work_dir: Path = VISION_WORK,
    pages: set[int] | None = None,
    force: bool = False,
    dpi: int = 200,
) -> dict:
    """Transcribe every PDF page in the located range; retain failures for review.

    A page cache is only reused with the same PDF digest, model, prompt version,
    and rendering DPI. Neither old OCR words nor failed pages are reused.
    """
    if not book.path.is_file():
        raise FileNotFoundError(book.path)
    model = GEMMA_MODEL
    source = _source_book(book)
    pdf_digest = _sha256(book.path)
    from vocab_ocr.pep import vision

    prompt_digest = hashlib.sha256(vision._prompt(book.stage).encode("utf-8")).hexdigest()
    start, end = source["vocab_pdf_pages"]
    book_dir = work_dir / book.id
    cache_dir = book_dir / "pages"
    image_dir = book_dir / "images"
    cache_dir.mkdir(parents=True, exist_ok=True)
    unit_starts, unit_end = unit_map_for_book(
        book.id, source["pdf_pages"], source.get("toc_text", "")
    )
    # Existing book JSON may carry TOC starts that were confirmed against this PDF.
    if book.stage == "junior" and not unit_starts and source.get("unit_starts"):
        from vocab_ocr.pep.parse_appendix import UnitRange

        unit_starts = [UnitRange(str(item["unit"]), int(item["start_page"])) for item in source["unit_starts"]]

    selected_pages = sorted(pages) if pages is not None else list(range(start, end + 1))
    if not selected_pages or any(page < start or page > end for page in selected_pages):
        raise ValueError(f"selected pages must be within {book.id} PDF span {start}–{end}")

    def process_page(page: int) -> dict:
        cache_path = cache_dir / f"{page:03d}.json"
        cached = None
        if cache_path.exists() and not force:
            old = json.loads(cache_path.read_text(encoding="utf-8"))
            if (old.get("pdf_sha256"), old.get("model"), old.get("prompt_sha256"), old.get("dpi")) == (
                pdf_digest, model, prompt_digest, dpi
            ) and old.get("status") == "ok":
                cached = old
        if cached is None:
            images = render_pages(book.path, image_dir / f"{page:03d}", "page", page, page, dpi=dpi)
            if len(images) != 1:
                raise RuntimeError(f"expected one rendered image for {book.id} PDF page {page}")
            try:
                transcript = transcribe_page(images[0], stage=book.stage, pdf_page=page, model=model)
                cached = {
                    "pdf_page": page, "status": "ok", "kind": transcript["kind"],
                    "reason": transcript["reason"], "printed_page": transcript["printed_page"],
                    "entries": [
                        _entry_from_vision(e, book=book, unit_starts=unit_starts, unit_end=unit_end)
                        for e in transcript["entries"]
                    ],
                    "uncertainty": transcript["uncertainty"],
                    "raw_response": transcript["raw_response"],
                    "pdf_sha256": pdf_digest, "model": model,
                    "prompt_sha256": prompt_digest, "dpi": dpi,
                }
            except VisionTranscriptionError as exc:
                cached = {
                    "pdf_page": page, "status": "error", "kind": "unknown",
                    "reason": None, "entries": [], "error": str(exc),
                    "pdf_sha256": pdf_digest, "model": model,
                    "prompt_sha256": prompt_digest, "dpi": dpi,
                }
            finally:
                images[0].unlink(missing_ok=True)
            _write_json(cache_path, cached)
        print(f"    PDF p.{page}: {cached['status']} {cached.get('kind')} entries={len(cached['entries'])}", flush=True)
        return cached

    page_results = [process_page(page) for page in selected_pages]
    entries = [entry for result in page_results for entry in result["entries"]]

    result = {
        "book_id": book.id, "title": book.title, "stage": book.stage,
        "series": "pep", "extraction_engine": "vision-lmstudio",
        "model": model, "pdf_sha256": pdf_digest,
        "prompt_sha256": prompt_digest, "dpi": dpi,
        "pdf": str(book.path.relative_to(ROOT)) if book.path.is_relative_to(ROOT) else str(book.path),
        "pdf_pages": source["pdf_pages"], "vocab_pdf_pages": [start, end],
        "unit_starts": [{"unit": u.unit, "start_page": u.start_page} for u in unit_starts],
        "entry_count": len(entries),
        "entry_with_unit_count": sum(bool(e["unit"]) for e in entries),
        "page_results": page_results,
        "entries": entries,
    }
    _write_json(book_dir / "book.json", result)
    return result


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def validate_vision_books(books: list[dict], *, review_sheet: Path = REVIEW_SHEET):
    from vocab_ocr.pep.quality import validate_corpus, validate_review_rows

    anchors_path = Path(__file__).with_name("source_anchors.json")
    anchors = json.loads(anchors_path.read_text(encoding="utf-8"))
    report = validate_corpus(
        books, expected_book_ids=[b.id for b in BOOKS], anchors_by_book=anchors,
    )
    review = validate_review_rows(
        books,
        seed_rows=_read_csv(FIXED_SAMPLE),
        review_rows=_read_csv(review_sheet),
    )
    return report, review


def check_vision_index(*, work_dir: Path = VISION_WORK, review_sheet: Path = REVIEW_SHEET) -> dict:
    """Report every current quality blocker without touching the formal index."""
    books = []
    for catalog_book in BOOKS:
        path = work_dir / catalog_book.id / "book.json"
        if path.exists():
            books.append(json.loads(path.read_text(encoding="utf-8")))
    structural, reviewed = validate_vision_books(books, review_sheet=review_sheet)
    return {"structural": structural.to_dict(), "source_review": reviewed.to_dict()}


def publish_vision_index(*, work_dir: Path = VISION_WORK, review_sheet: Path = REVIEW_SHEET) -> Path:
    """Publish only a complete, source-reviewed 12-book corpus."""
    from vocab_ocr.pep.quality import require_quality

    books = []
    for catalog_book in BOOKS:
        path = work_dir / catalog_book.id / "book.json"
        if not path.exists():
            raise FileNotFoundError(f"vision candidate missing for {catalog_book.id}: {path}")
        candidate = json.loads(path.read_text(encoding="utf-8"))
        if candidate.get("pdf_sha256") != _sha256(catalog_book.path):
            raise ValueError(f"source PDF changed after transcription: {catalog_book.id}")
        books.append(candidate)
    structural, reviewed = validate_vision_books(books, review_sheet=review_sheet)
    require_quality(structural)
    require_quality(reviewed)
    staged = work_dir / "index"
    built = build_inverted_index(books, staged, basename="vocab-index")
    compact = built.with_name("vocab-index.min.json")
    payload = json.loads(compact.read_text(encoding="utf-8"))
    if payload.get("v") != 1 or set(payload.get("books", {})) != {b.id for b in BOOKS}:
        raise ValueError("staged index is incomplete or has unexpected schema")
    destination = DEFAULT_OUT / "vocab-index.min.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_destination = destination.with_suffix(".min.json.tmp")
    temp_destination.write_bytes(compact.read_bytes())
    os.replace(temp_destination, destination)
    return destination
