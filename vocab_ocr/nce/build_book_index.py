"""Build New Concept English index from Excel, optionally adding PDF lessons.

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


def add_pdf_lessons(index: dict, work: Path) -> dict[str, int]:
    """Add only headwords directly matched in the PDF vocabulary blocks."""
    counts = {}
    for book in (1, 2, 3):
        book_id = f"nce-{book}"
        path = work / book_id / "lesson-matches.json"
        if book == 1 and not path.exists():
            continue
        entries = json.loads(path.read_text(encoding="utf-8"))
        expected = {1: 144, 2: 96, 3: 60}[book]
        if [entry["lesson"] for entry in entries] != list(range(1, expected + 1)):
            raise ValueError(f"incomplete or unordered lesson matches: {path}")
        lessons_by_word: dict[str, set[int]] = defaultdict(set)
        for entry in entries:
            lesson = entry["lesson"]
            for word in entry["matches"]:
                if word not in index["w"] or not any(hit[0] == book_id for hit in index["w"][word]):
                    raise ValueError(f"PDF match absent from source Excel: {book_id} {word}")
                lessons_by_word[word].add(lesson)
        for word, lessons in lessons_by_word.items():
            hits = index["w"][word]
            index["w"][word] = [hit for hit in hits if hit[0] != book_id] + [
                [book_id, str(lesson), ""] for lesson in sorted(lessons)
            ]
            index["w"][word].sort(key=lambda hit: hit[0])
        counts[book_id] = len(lessons_by_word)
    return counts


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
    parser = argparse.ArgumentParser(description="从四册 Excel 生成新概念词源索引，可选 PDF 课次证据")
    parser.add_argument("--source-dir", type=Path, default=SOURCE_DIR, help="四份新版 Excel 所在目录")
    parser.add_argument("--output", type=Path, default=OUTPUT, help="输出的紧凑 JSON 文件")
    parser.add_argument("--pdf-lessons-work", type=Path, help="已核对的 PDF 课次匹配目录；缺证据的词保留册级命中")
    args = parser.parse_args(argv)
    rows_by_book = load_book_rows(args.source_dir)
    index = build_index(rows_by_book)
    lesson_counts = add_pdf_lessons(index, args.pdf_lessons_work) if args.pdf_lessons_work else {}
    output = write_index(index, args.output)
    print(json.dumps({
        "output": str(output),
        "source_rows": {book_id: len(rows) for book_id, rows in rows_by_book.items()},
        "lemmas": len(index["w"]),
        "pdf_lesson_lemmas": lesson_counts,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
