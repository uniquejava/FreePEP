"""Copy the verified NCE vocabulary pages into small, reusable PDFs.

The checked page map is committed beside this module. The source textbooks and
the exported page PDFs stay outside Git. Pages are copied directly from the
original PDFs, so this step does not reduce scan resolution or need OCR.

Usage:
    python3 -m vocab_ocr.nce.export_vocab_pages
    python3 -m vocab_ocr.nce.export_vocab_pages --book 4
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

from pypdf import PdfReader, PdfWriter


PDF_DIR = Path.home() / "Pdf/新概念课文1-4PDF"
PAGE_MAP = Path(__file__).with_name("vocab_page_map.json")
LESSON_COUNTS = {"nce-1": 144, "nce-2": 96, "nce-3": 60, "nce-4": 48}


def load_page_map(path: Path = PAGE_MAP) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("v") != 1 or set(payload.get("books", {})) != set(LESSON_COUNTS):
        raise ValueError(f"unexpected NCE page map: {path}")
    for book, book_data in payload["books"].items():
        source_file = book_data["source_file"]
        if Path(source_file).name != source_file or not source_file.endswith(".pdf"):
            raise ValueError(f"invalid source PDF name: {book} {source_file}")
        page_count = book_data["source_page_count"]
        pages = book_data["pages"]
        if not isinstance(page_count, int) or page_count < 1 or not pages:
            raise ValueError(f"invalid source page count or empty map: {book}")
        previous_lesson = previous_page = 0
        for lesson, source_page, role in pages:
            if not (1 <= lesson <= LESSON_COUNTS[book] and
                    previous_lesson <= lesson and
                    previous_page < source_page <= page_count):
                raise ValueError(f"out-of-order or invalid page: {book} {lesson} {source_page}")
            if role == "continuation":
                if lesson != previous_lesson or source_page != previous_page + 1:
                    raise ValueError(f"orphaned continuation: {book} {lesson} {source_page}")
            elif role != "wordlist" or lesson == previous_lesson:
                raise ValueError(f"invalid wordlist role: {book} {lesson} {source_page}")
            previous_lesson, previous_page = lesson, source_page
    return payload


def printed_page(book: str, lesson: int, source_page: int) -> int:
    offset = {"nce-1": 4 if lesson <= 72 else 8,
              "nce-2": 3, "nce-3": 2, "nce-4": 29}[book]
    return source_page - offset


def export_book(book: str, book_data: dict, pdf_dir: Path, output_dir: Path) -> dict:
    source = pdf_dir / book_data["source_file"]
    if not source.is_file():
        raise FileNotFoundError(source)
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / f"{book}-词表页.pdf"
    csv_path = output_dir / f"{book}-页码清单.csv"
    pdf_temp = pdf_path.with_suffix(".tmp.pdf")
    csv_temp = csv_path.with_suffix(".tmp.csv")
    with source.open("rb") as stream:
        reader = PdfReader(stream)
        if len(reader.pages) != book_data["source_page_count"]:
            raise ValueError(f"source PDF page count changed: {source}")
        writer = PdfWriter()
        writer.add_metadata({"/Title": f"新概念英语第{book[-1]}册词表页",
                             "/Subject": f"Extracted without OCR from {source.name}"})
        csv_rows = []
        for lesson, source_page, role in book_data["pages"]:
            writer.add_page(reader.pages[source_page - 1])
            snapshot_page = len(writer.pages)
            if role == "wordlist":
                writer.add_outline_item(f"Lesson {lesson}", snapshot_page - 1)
            csv_rows.append((snapshot_page, lesson, source_page,
                             printed_page(book, lesson, source_page), role))
        with pdf_temp.open("wb") as target:
            writer.write(target)
    with csv_temp.open("w", newline="", encoding="utf-8-sig") as stream:
        csv_writer = csv.writer(stream)
        csv_writer.writerow(("snapshot_page", "lesson", "source_pdf_page",
                             "printed_page", "role"))
        csv_writer.writerows(csv_rows)
    # Validate both finished artifacts before replacing any existing export.
    if len(PdfReader(pdf_temp).pages) != len(csv_rows):
        raise ValueError(f"exported PDF page count mismatch: {pdf_temp}")
    os.replace(pdf_temp, pdf_path)
    os.replace(csv_temp, csv_path)
    return {"book": book, "source": str(source), "pdf": str(pdf_path),
            "page_map": str(csv_path), "pages": len(csv_rows),
            "lessons": len({row[1] for row in csv_rows})}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="从原书 PDF 无损保存新概念英语词表页")
    parser.add_argument("--pdf-dir", type=Path, default=PDF_DIR, help="四册原始 PDF 的目录")
    parser.add_argument("--output-dir", type=Path, help="快照输出目录，默认原始 PDF 目录下的词表页快照")
    parser.add_argument("--book", type=int, choices=(1, 2, 3, 4), help="只导出指定册")
    parser.add_argument("--page-map", type=Path, default=PAGE_MAP, help="已核对的词表页映射 JSON")
    args = parser.parse_args(argv)
    page_map = load_page_map(args.page_map)
    output_dir = args.output_dir or args.pdf_dir / "词表页快照"
    books = (f"nce-{args.book}",) if args.book else LESSON_COUNTS
    results = [export_book(book, page_map["books"][book], args.pdf_dir, output_dir)
               for book in books]
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
