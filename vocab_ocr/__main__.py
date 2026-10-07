"""CLI: python -m vocab_ocr pep ..."""

from __future__ import annotations

import argparse
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
        help="Only rebuild inverted index from existing books/*.json",
    )

    args = parser.parse_args(argv)

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
