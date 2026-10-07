"""Prepare a PDF-grounded review sheet for a rebuilt PEP visual index.

The fixed #04 sample is kept intact. This writes a *new* sheet with its 60
source locations and an independent, reproducible sample from rebuilt books.
Automated matching is only a locator, never a correctness verdict.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path

from vocab_ocr.pep.catalog import BOOKS
from vocab_ocr.shared.build_index import norm_lemma
from vocab_ocr.shared.paths import DEFAULT_OUT, DEFAULT_WORK


FIELDS = [
    "sample_set", "book_id", "kind", "lemma", "source_pdf_page", "pdf",
    "current_word", "current_unit", "current_page", "current_zh",
    "page_candidate_words", "word_ok", "zh_ok", "unit_ok", "page_ok",
    "disposition", "exclusion_reason", "notes",
    "old_in_index", "old_candidate_unit", "old_candidate_page", "old_candidate_zh",
    "old_word_ok", "old_zh_ok", "old_unit_ok", "old_page_ok", "old_notes",
]


def _page(entry: dict) -> int | None:
    try:
        value = int(entry.get("pdf_page"))
    except (ValueError, TypeError):
        return None
    return value if value > 0 else None


def _current(row: dict, entry: dict) -> None:
    row["current_word"] = entry.get("word") or ""
    row["current_unit"] = entry.get("unit") or ""
    row["current_page"] = entry.get("page") or ""
    row["current_zh"] = entry.get("zh") or ""


def make_rows(
    fixed_csv: Path,
    books_dir: Path,
    *,
    seed: int = 20261009,
    independent_per_book: int = 2,
) -> list[dict]:
    with fixed_csv.open(encoding="utf-8-sig", newline="") as stream:
        fixed = list(csv.DictReader(stream))
    if len(fixed) != 60:
        raise ValueError(f"expected #04's 60 fixed rows, got {len(fixed)}")

    by_book: dict[str, list[dict]] = {}
    by_page: dict[str, dict[int, list[dict]]] = {}
    for book in BOOKS:
        path = books_dir / f"{book.id}.json"
        if not path.exists():
            path = books_dir / book.id / "book.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = [e for e in data.get("entries", []) if _page(e) and e.get("word")]
        by_book[book.id] = entries
        pages: dict[int, list[dict]] = defaultdict(list)
        for entry in entries:
            pages[_page(entry)].append(entry)
        by_page[book.id] = pages

    result: list[dict] = []
    fixed_pages: dict[str, set[int]] = defaultdict(set)
    for old in fixed:
        book_id = old["book_id"]
        page = int(old["source_pdf_page"])
        fixed_pages[book_id].add(page)
        row = {field: "" for field in FIELDS}
        row.update(sample_set="fixed", book_id=book_id, kind=old["kind"],
                   lemma=old["lemma"], source_pdf_page=page, pdf=old["pdf"])
        candidates = by_page[book_id].get(page, [])
        row["page_candidate_words"] = " | ".join(str(e["word"]) for e in candidates)
        exact = [e for e in candidates if norm_lemma(e["word"]) == norm_lemma(old["lemma"])]
        if len(exact) == 1:
            _current(row, exact[0])
        else:
            row["notes"] = ("No unique exact visual candidate on source page; "
                            "inspect page_candidate_words and PDF before marking disposition.")
        for key in ("in_index", "candidate_unit", "candidate_page", "candidate_zh",
                    "word_ok", "zh_ok", "unit_ok", "page_ok", "notes"):
            row[f"old_{key}"] = old.get(key, "")
        result.append(row)

    for book in BOOKS:
        book_id = book.id
        eligible = [e for e in by_book[book_id]
                    if _page(e) not in fixed_pages[book_id]
                    and e.get("zh") and norm_lemma(e["word"])]
        # Dedupe exact source positions before sampling. A stable sort keeps the
        # sample independent of the visual model's output order.
        unique = {(norm_lemma(e["word"]), _page(e), str(e.get("unit"))): e for e in eligible}
        pool = [unique[key] for key in sorted(unique)]
        if len(pool) < independent_per_book:
            raise ValueError(f"{book_id}: only {len(pool)} independent candidates")
        rng = random.Random(f"{seed}:{book_id}")
        for entry in rng.sample(pool, independent_per_book):
            page = _page(entry)
            row = {field: "" for field in FIELDS}
            row.update(sample_set="independent", book_id=book_id,
                       kind="random_independent", lemma=entry["word"],
                       source_pdf_page=page, pdf=str(book.path))
            _current(row, entry)
            row["page_candidate_words"] = " | ".join(
                str(e["word"]) for e in by_page[book_id][page])
            result.append(row)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixed-csv", type=Path, default=DEFAULT_WORK / "pep-audit-sample.csv")
    parser.add_argument("--books-dir", type=Path, default=DEFAULT_OUT / "books")
    parser.add_argument("--out", type=Path, default=DEFAULT_WORK / "pep-05-review.csv")
    parser.add_argument("--seed", type=int, default=20261009)
    parser.add_argument("--independent-per-book", type=int, default=2)
    args = parser.parse_args()
    if args.out.exists():
        parser.error(f"{args.out} already exists; choose a new --out to preserve reviews")
    rows = make_rows(args.fixed_csv, args.books_dir, seed=args.seed,
                     independent_per_book=args.independent_per_book)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} review rows -> {args.out}")


if __name__ == "__main__":
    main()
