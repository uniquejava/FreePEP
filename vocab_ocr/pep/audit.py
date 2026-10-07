"""Generate a reproducible, source-locatable PEP index review sheet.

The CSV is a checklist, not an automatic correctness verdict. Check each row
against the source PDF; OCR text is included only to help locate the entry.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
from pathlib import Path

from vocab_ocr.pep.catalog import BOOKS
from vocab_ocr.pep.pipeline import prepare_book_for_index
from vocab_ocr.shared.build_index import clean_zh, norm_lemma
from vocab_ocr.shared.paths import DEFAULT_OUT, DEFAULT_WORK


FIELDS = [
    "book_id", "kind", "in_index", "lemma", "candidate_unit", "candidate_page", "candidate_zh",
    "pdf", "source_pdf_page", "printed_page", "source_raw",
    "word_ok", "zh_ok", "unit_ok", "page_ok", "notes",
]


def _candidates(book: dict, index: dict[str, list[list]]) -> tuple[list[dict], list[dict]]:
    included, omitted = [], []
    for entry in book["entries"]:
        lemma = norm_lemma(entry.get("word") or "")
        zh = clean_zh(entry.get("zh"))
        if not lemma or not zh or not isinstance(entry.get("pdf_page"), int):
            continue
        unit = entry.get("unit")
        page = entry.get("page")
        hit = [book["book_id"], str(unit)] if unit else None
        if hit is not None:
            if isinstance(page, int) and page > 0:
                hit.append(page)
            hit.append(zh)
        row = {
            "book_id": book["book_id"], "kind": "", "lemma": lemma,
            "in_index": "yes" if hit in index.get(lemma, []) else "no",
            "candidate_unit": str(unit) if unit else "",
            "candidate_page": page if isinstance(page, int) and page > 0 else "",
            "candidate_zh": zh, "pdf": book["pdf"],
            "source_pdf_page": entry["pdf_page"], "printed_page": page or "",
            "source_raw": entry.get("raw") or "", "word_ok": "", "zh_ok": "",
            "unit_ok": "", "page_ok": "", "notes": "",
        }
        (included if hit in index.get(lemma, []) else omitted).append(row)
    key = lambda row: (row["source_pdf_page"], row["lemma"], row["source_raw"])
    return sorted(included, key=key), sorted(omitted, key=key)


def _suspicion(row: dict) -> int:
    raw = row["source_raw"]
    # Several phonetic spans or printed unit/page markers often mean two columns
    # were read as a single line. These are review priorities, not proof of error.
    score = max(0, len(re.findall(r"/[^/\n]{1,35}/", raw)) - 1) * 3
    score += max(0, len(re.findall(r"\bp\.?\s*\d+|\(\d+\)", raw, re.I)) - 1) * 2
    score += 2 if len(row["lemma"].split()) >= 3 else 0
    score += 1 if re.search(r"[A-Za-z]{3,}", row["candidate_zh"]) else 0
    return score


def sample_rows(
    index_path: Path = DEFAULT_OUT / "vocab-index.min.json",
    books_dir: Path = DEFAULT_OUT / "books",
    *,
    seed: int = 20261008,
) -> list[dict]:
    index = json.loads(index_path.read_text(encoding="utf-8"))["w"]
    rows = []
    for catalog_book in BOOKS:
        path = books_dir / f"{catalog_book.id}.json"
        book = prepare_book_for_index(json.loads(path.read_text(encoding="utf-8")))
        included, omitted = _candidates(book, index)
        rng = random.Random(f"{seed}:{catalog_book.id}")
        chosen: set[tuple] = set()

        def take(kind: str, pool: list[dict], count: int = 1) -> None:
            available = [r for r in pool if (r["lemma"], r["source_pdf_page"]) not in chosen]
            for row in available[:count]:
                rows.append({**row, "kind": kind})
                chosen.add((row["lemma"], row["source_pdf_page"]))

        take("random", rng.sample(included, min(2, len(included))), 2)
        boundary = [r for r in included if (
            isinstance(r["printed_page"], int)
            and any(abs(r["printed_page"] - int(start["start_page"])) <= 1
                    for start in book.get("unit_starts", []))
        )]
        if boundary:
            take("unit_boundary", rng.sample(boundary, len(boundary)))
        else:
            take("unit_reference", rng.sample(included, len(included)))
        take("suspicious_ocr", sorted(included, key=lambda r: (-_suspicion(r), r["lemma"])))
        take("not_indexed_candidate", rng.sample(omitted, len(omitted)))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20261008)
    parser.add_argument("--out", type=Path, default=DEFAULT_WORK / "pep-audit-sample.csv")
    parser.add_argument("--force", action="store_true", help="replace an existing review sheet")
    args = parser.parse_args()
    if args.out.exists() and not args.force:
        parser.error(f"{args.out} already exists; use --force only if reviews may be discarded")
    rows = sample_rows(seed=args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} rows -> {args.out}")


if __name__ == "__main__":
    main()
