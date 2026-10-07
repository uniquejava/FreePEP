"""Build a book-only New Concept English index from four structured Excel lists.

The v:1 hit keeps its existing three fields: [book_id, lesson, zh]. Empty
lesson and zh mean this source only establishes book-level membership.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from pathlib import Path

from vocab_ocr.nce.pilot_nce2_from_excel import norm_lemma, read_excel
from vocab_ocr.shared.build_index import INDEX_VERSION
from vocab_ocr.shared.paths import DEFAULT_OUT


SOURCE_DIR = Path.home() / "code/English/8.新概念英语"
OUTPUT = DEFAULT_OUT / "nce-vocab-index.min.json"
BOOK_FILES = (
    ("nce-1", "新概念英语第一册", "新概念英语第一册（新版）.xlsx"),
    ("nce-2", "新概念英语第二册", "新概念英语第二册（新版）.xlsx"),
    ("nce-3", "新概念英语第三册", "新概念英语第三册（新版）.xlsx"),
    ("nce-4", "新概念英语第四册", "新概念英语第四册（新版）.xlsx"),
)


def load_book_rows(source_dir: Path) -> dict[str, list[dict[str, str]]]:
    """Read every source before replacing the existing complete index."""
    rows_by_book = {}
    for book_id, _, filename in BOOK_FILES:
        path = source_dir / filename
        if not path.is_file():
            raise FileNotFoundError(path)
        rows = read_excel(path)
        if not rows:
            raise ValueError(f"empty Excel vocabulary list: {path}")
        rows_by_book[book_id] = rows
    return rows_by_book


def build_index(rows_by_book: dict[str, list[dict[str, str]]]) -> dict:
    """Deduplicate within a book while preserving hits across books."""
    expected = {book_id for book_id, _, _ in BOOK_FILES}
    if set(rows_by_book) != expected:
        raise ValueError(f"expected exactly four books: {sorted(expected)}")
    words: dict[str, list[list[str]]] = defaultdict(list)
    for book_id, _, _ in BOOK_FILES:
        seen = set()
        rows = rows_by_book[book_id]
        if not rows:
            raise ValueError(f"empty vocabulary list: {book_id}")
        for row in rows:
            lemma = norm_lemma(row.get("word", ""))
            if not lemma or lemma in seen:
                continue
            seen.add(lemma)
            words[lemma].append([book_id, "", ""])
        if not seen:
            raise ValueError(f"no usable words: {book_id}")
    return {
        "v": INDEX_VERSION,
        "books": {book_id: title for book_id, title, _ in BOOK_FILES},
        "w": dict(sorted(words.items())),
    }


def write_index(index: dict, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    temporary.write_text(
        json.dumps(index, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    os.replace(temporary, output)
    return output


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="从四册 Excel 生成新概念英语册级词源索引")
    parser.add_argument("--source-dir", type=Path, default=SOURCE_DIR, help="四份新版 Excel 所在目录")
    parser.add_argument("--output", type=Path, default=OUTPUT, help="输出的紧凑 JSON 文件")
    args = parser.parse_args(argv)
    rows_by_book = load_book_rows(args.source_dir)
    index = build_index(rows_by_book)
    output = write_index(index, args.output)
    print(json.dumps({
        "output": str(output),
        "source_rows": {book_id: len(rows) for book_id, rows in rows_by_book.items()},
        "lemmas": len(index["w"]),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
