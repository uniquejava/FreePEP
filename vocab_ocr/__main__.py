"""CLI: python -m vocab_ocr pep ..."""

from __future__ import annotations

import argparse
import json
import sys


def main(argv: list[str] | None = None) -> int:
    from vocab_ocr.pep.catalog import BOOKS
    from vocab_ocr.pep import pipeline as pipe

    parser = argparse.ArgumentParser(
        description="人教 PEP 英语词表 OCR → 倒排索引（含中文释义）"
    )
    sub = parser.add_subparsers(dest="series", required=True)
    pep_p = sub.add_parser("pep", help="人教版：目录定位附录词表 → OCR → 索引")
    pep_p.add_argument(
        "--book",
        action="append",
        dest="books",
        help="Book id (repeatable). Ids: " + ", ".join(b.id for b in BOOKS),
    )
    pep_p.add_argument("--all", action="store_true", help="Process all catalog books")
    pep_p.add_argument(
        "--force", action="store_true", help="Re-OCR even if book JSON exists"
    )
    pep_p.add_argument(
        "--rebuild-index",
        action="store_true",
        help="Build a legacy OCR preview from existing books/*.json (does not publish)",
    )
    pep_p.add_argument(
        "--vision", action="store_true",
        help="Transcribe complete original PDF pages with local LM Studio",
    )
    pep_p.add_argument(
        "--vision-page", type=int, action="append",
        help="Probe one PDF page (repeatable); writes an incomplete candidate only",
    )
    pep_p.add_argument(
        "--publish-vision", action="store_true",
        help="Publish 12-book vision index only after all quality and source-review gates pass",
    )
    pep_p.add_argument(
        "--check-vision", action="store_true",
        help="Report vision quality and source-review blockers without publishing",
    )

    args = parser.parse_args(argv)
    from vocab_ocr.pep.vision_pipeline import REVIEW_SHEET, VISION_WORK

    if args.check_vision:
        if args.books or args.all or args.rebuild_index or args.vision or args.publish_vision or args.vision_page:
            parser.error("--check-vision must be used alone")
        from vocab_ocr.pep.vision_pipeline import check_vision_index

        report = check_vision_index(work_dir=VISION_WORK, review_sheet=REVIEW_SHEET)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if all(section["ok"] for section in report.values()) else 1

    if args.publish_vision:
        if args.books or args.all or args.rebuild_index or args.vision or args.vision_page:
            parser.error("--publish-vision must be used alone")
        from vocab_ocr.pep.vision_pipeline import publish_vision_index

        print(f"index -> {publish_vision_index(work_dir=VISION_WORK, review_sheet=REVIEW_SHEET)}")
        return 0

    if args.vision:
        if args.rebuild_index:
            parser.error("--vision cannot be combined with --rebuild-index")
        if not args.books and not args.all:
            parser.error("--vision needs --book ID or --all")
        if args.vision_page and (not args.books or len(args.books) != 1 or args.all):
            parser.error("--vision-page needs exactly one --book")
        from vocab_ocr.pep.vision_pipeline import process_vision_book

        selected = [next((b for b in BOOKS if b.id == book_id), None) for book_id in args.books] if args.books else list(BOOKS)
        if any(b is None for b in selected):
            parser.error("unknown --book ID")
        for book in selected:
            print(f"==> vision/{book.id}: {book.path.name}", flush=True)
            result = process_vision_book(
                book, work_dir=VISION_WORK, pages=set(args.vision_page) if args.vision_page else None,
                force=args.force,
            )
            print(f"    candidate entries={result['entry_count']} pages={result['vocab_pdf_pages']}", flush=True)
        print("candidate saved under data/vocab/_work/vision/; run --publish-vision after review")
        return 0

    if args.rebuild_index and not args.books and not args.all:
        path = pipe.rebuild_index_from_books()
        print(f"index -> {path}")
        return 0

    if not args.books and not args.all:
        parser.error("specify --book ID and/or --all (or --rebuild-index)")

    book_ids = None if args.all and not args.books else args.books
    pipe.process_all(book_ids, force=args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
