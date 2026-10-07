"""PEP end-to-end: TOC locate → OCR appendix → book JSON → inverted index."""

from __future__ import annotations

import json
from pathlib import Path

from vocab_ocr.pep.catalog import BOOKS, PepBook, get_book
from vocab_ocr.pep.locate_vocab_via_toc import locate_vocab_pages
from vocab_ocr.pep.parse_appendix import (
    UnitRange,
    apply_page_unit_mapping,
    entries_to_dicts,
    map_page_to_unit,
    parse_ocr_pages,
    parse_toc_unit_starts,
)
from vocab_ocr.shared.build_index import build_inverted_index
from vocab_ocr.shared.paths import DEFAULT_OUT, DEFAULT_WORK, ROOT
from vocab_ocr.shared.pdf_render import (
    pdf_page_count,
    pdf_page_from_render_name,
    render_pages,
    require_pdftoppm,
)
from vocab_ocr.shared.tesseract_ocr import ocr_image, require_tesseract


# Printed page starts read from the Contents of the exact local textbook
# editions. The PDF page count guards against applying them to another edition.
# End is the first page after the numbered units (Reading Plus/appendices).
KNOWN_JUNIOR_TOC: dict[str, tuple[int, list[tuple[str, int]], int]] = {
    "junior-7a": (140, [("starter-1", 1), ("starter-2", 7), ("starter-3", 13),
                         ("1", 19), ("2", 27), ("3", 35), ("4", 43),
                         ("5", 51), ("6", 59), ("7", 67)], 75),
    "junior-7b": (132, [(str(i), 1 + 8 * (i - 1)) for i in range(1, 9)], 65),
    "junior-8a": (150, [(str(i), 1 + 10 * (i - 1)) for i in range(1, 9)], 81),
    "junior-8b": (154, [(str(i), 1 + 10 * (i - 1)) for i in range(1, 9)], 81),
    "junior-9": (204, [(str(i), 1 + 8 * (i - 1)) for i in range(1, 13)], 97),
}


def unit_map_for_book(book_id: str, pdf_pages: int, toc_text: str = "") -> tuple[list[UnitRange], int | None]:
    starts = parse_toc_unit_starts(toc_text)
    if starts:
        return starts, None
    known = KNOWN_JUNIOR_TOC.get(book_id)
    if known and known[0] == pdf_pages:
        return [UnitRange(unit, page) for unit, page in known[1]], known[2]
    return [], None


def prepare_book_for_index(book: dict) -> dict:
    """Correct stale A-Z unit values in cached JSON before indexing."""
    if book.get("stage") != "junior":
        return book
    ranges = [UnitRange(str(r["unit"]), int(r["start_page"])) for r in book.get("unit_starts", [])]
    end_page = None
    if not ranges:
        ranges, end_page = unit_map_for_book(book["book_id"], book.get("pdf_pages", 0))
    prepared = {**book, "unit_starts": [
        {"unit": r.unit, "start_page": r.start_page} for r in ranges
    ]}
    entries = []
    for entry in book["entries"]:
        e = entry.copy()
        if e.get("source") == "appendix_az":
            page = e.get("page")
            e["unit"] = map_page_to_unit(page, ranges, end_page) if isinstance(page, int) else None
        entries.append(e)
    prepared["entries"] = entries
    return prepared


def process_book(
    book: PepBook,
    *,
    work_dir: Path = DEFAULT_WORK,
    out_dir: Path = DEFAULT_OUT,
    final_dpi: int = 220,
    force: bool = False,
) -> dict:
    require_pdftoppm()
    require_tesseract()
    if not book.path.is_file():
        raise FileNotFoundError(book.path)

    book_work = work_dir / book.id
    book_work.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "books" / f"{book.id}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists() and not force:
        return json.loads(out_path.read_text(encoding="utf-8"))

    n_pages = pdf_page_count(book.path)
    located = locate_vocab_pages(book.path, book_work)
    start, end = located.start_pdf, located.end_pdf

    final_dir = book_work / "final"
    ocr_final_dir = book_work / "ocr_final"
    ocr_final_dir.mkdir(parents=True, exist_ok=True)

    pages: list[tuple[int, str]] = []
    # Reuse locate-probe OCR when present; only re-render missing / higher DPI gaps.
    locate_ocr = {
        int(p.stem): p.read_text(encoding="utf-8", errors="replace")
        for p in (book_work / "ocr_locate").glob("*.txt")
        if p.stem.isdigit()
    }
    missing = [p for p in range(start, end + 1) if p not in locate_ocr]
    if missing:
        imgs = render_pages(
            book.path,
            final_dir,
            "final",
            min(missing),
            max(missing),
            dpi=final_dpi,
        )
        for img in imgs:
            pdf_page = pdf_page_from_render_name(img)
            if pdf_page is None or pdf_page < start or pdf_page > end:
                continue
            if pdf_page not in missing:
                continue
            text = ocr_image(img, lang="eng+chi_sim", psm=6)
            (ocr_final_dir / f"{pdf_page:03d}.txt").write_text(text, encoding="utf-8")
            locate_ocr[pdf_page] = text

    for pdf_page in range(start, end + 1):
        text = locate_ocr.get(pdf_page)
        if not text:
            continue
        (ocr_final_dir / f"{pdf_page:03d}.txt").write_text(text, encoding="utf-8")
        pages.append((pdf_page, text))

    entries = parse_ocr_pages(
        pages,
        book_id=book.id,
        book_title=book.title,
        stage=book.stage,
    )

    toc_text = located.toc_text or ""
    toc_path = book_work / "ocr_toc.txt"
    if toc_path.exists() and not toc_text:
        toc_text = toc_path.read_text(encoding="utf-8", errors="replace")
    unit_starts, unit_end = unit_map_for_book(book.id, n_pages, toc_text)
    entries = apply_page_unit_mapping(entries, unit_starts, unit_end)

    with_unit = sum(1 for e in entries if e.unit)
    result = {
        "book_id": book.id,
        "title": book.title,
        "stage": book.stage,
        "series": "pep",
        "pdf": str(book.path.relative_to(ROOT))
        if book.path.is_relative_to(ROOT)
        else str(book.path),
        "pdf_pages": n_pages,
        "vocab_pdf_pages": [start, end],
        "locate_method": located.method,
        "toc_printed_start": located.printed_start,
        "unit_starts": [
            {"unit": u.unit, "start_page": u.start_page} for u in unit_starts
        ],
        "entry_count": len(entries),
        "entry_with_unit_count": with_unit,
        "entries": entries_to_dicts(entries),
    }
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def rebuild_index_from_books(out_dir: Path = DEFAULT_OUT) -> Path:
    books_dir = out_dir / "books"
    results = []
    for b in BOOKS:
        p = books_dir / f"{b.id}.json"
        if p.exists():
            results.append(prepare_book_for_index(json.loads(p.read_text(encoding="utf-8"))))
    if not results:
        raise FileNotFoundError(f"no PEP book JSON under {books_dir}")
    return build_inverted_index(results, out_dir, basename="vocab-index")


def process_all(
    book_ids: list[str] | None = None,
    *,
    force: bool = False,
) -> Path:
    selected = [get_book(i) for i in book_ids] if book_ids else list(BOOKS)
    for book in selected:
        print(f"==> pep/{book.id}: {book.path.name}")
        result = process_book(book, force=force)
        print(
            f"    entries={result['entry_count']} "
            f"with_unit={result['entry_with_unit_count']} "
            f"pages={result['vocab_pdf_pages']} "
            f"via={result['locate_method']}"
        )

    books_dir = DEFAULT_OUT / "books"
    # --book subset: index only those books (preview). --all: every catalog book on disk.
    to_index = selected if book_ids else list(BOOKS)
    merged = []
    for b in to_index:
        p = books_dir / f"{b.id}.json"
        if p.exists():
            merged.append(prepare_book_for_index(json.loads(p.read_text(encoding="utf-8"))))
    # A single-book run is a preview. Keep the checked-in full index intact.
    target_dir = DEFAULT_WORK / "preview" if book_ids else DEFAULT_OUT
    path = build_inverted_index(merged, target_dir, basename="vocab-index")
    print(f"index -> {path}")
    return path
