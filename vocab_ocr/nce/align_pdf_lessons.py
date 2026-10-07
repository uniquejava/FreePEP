"""Locate NCE 1/2/3 vocabulary using the printed table-of-contents pages.

The source PDFs are image-only. This tool OCRs only the table-of-contents
lesson starts or their next page, where the vocabulary section begins.
It writes review data under the ignored _work directory, never the final index.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from vocab_ocr.nce.build_book_index import load_book_rows
from vocab_ocr.nce.pilot_nce2_from_excel import norm_lemma
from vocab_ocr.shared.paths import DEFAULT_WORK

PDF_DIR = Path.home() / "Pdf/新概念课文1-4PDF"
SOURCE_DIR = Path.home() / "code/English/8.新概念英语"
WORK = DEFAULT_WORK / "nce-pdf-lessons"

# Checked against the rendered page, including two Excel/PDF headword variants:
# nce-2 content -> printed contents; the press -> printed Press.
VISUALLY_CHECKED = {
    1: {"it": 1, "trousers": 28, "lift": 46, "cake": 46,
        "biscuit": 46, "regularly": 142},
    2: {"modern": 23, "retire": 31, "content": 44, "circus": 65,
        "remote": 66, "the press": 84},
    3: {"philosopher": 27, "pot-holer": 42, "lull": 44, "safeguard": 53},
}


def printed_page(book: int, lesson: int) -> int:
    if book == 1 and 1 <= lesson <= 144:
        return 2 * lesson - 1
    if book == 2 and 1 <= lesson <= 96:
        unit = (lesson - 1) // 24
        return (12, 122, 232, 342)[unit] + 4 * ((lesson - 1) % 24)
    if book == 3 and 1 <= lesson <= 60:
        unit = (lesson - 1) // 20
        return (14, 106, 192)[unit] + 4 * ((lesson - 1) % 20)
    raise ValueError((book, lesson))


def pdf_page(book: int, lesson: int) -> int:
    if book == 1:
        return printed_page(book, lesson) + (4 if lesson <= 72 else 8)
    return printed_page(book, lesson) + {2: 3, 3: 2}[book]


def ocr_page(pdf: Path, page: int, cache: Path) -> str:
    if cache.is_file():
        return cache.read_text(encoding="utf-8")
    cache.parent.mkdir(parents=True, exist_ok=True)
    prefix = cache.with_suffix("")
    subprocess.run(
        ["pdftoppm", "-f", str(page), "-l", str(page), "-singlefile",
         "-scale-to", "1900", "-png", str(pdf), str(prefix)],
        check=True, capture_output=True,
    )
    image_path = prefix.with_suffix(".png")
    try:
        result = subprocess.run(
            ["tesseract", "stdin", "stdout", "-l", "eng", "--psm", "3"],
            input=image_path.read_bytes(), check=True, capture_output=True,
        )
    finally:
        image_path.unlink(missing_ok=True)
    text = result.stdout.decode("utf-8", errors="replace")
    cache.write_text(text, encoding="utf-8")
    return text


def vocab_block(text: str) -> tuple[str, bool]:
    start = re.search(r"News?\s+words\s+and\s+expressions", text, re.I)
    if not start:
        return "", False
    end = re.search(r"No[tf]es\s+on\s+the\s+text", text[start.end():], re.I)
    # Tesseract may read the left column, then Notes, then the right column.
    # Keep the page tail and require a printed line-reference marker below.
    return text[start.end():], bool(end)


def vocab_block_one(text: str) -> tuple[str, bool]:
    start = re.search(r"News?\s+words\s+and\s+expressions", text, re.I)
    if not start:
        return "", False
    end = re.search(r"(?:No[tf]es\s+on\s+the\s+text|Written\s+exercises?)", text[start.end():], re.I)
    return (text[start.end():start.end() + end.start()], True) if end else (text[start.end():], False)


def matches(block: str, words: list[str], book: int) -> list[str]:
    """Find known Excel headwords followed by a glossary pronunciation/reference."""
    found = []
    for word in words:
        # NCE 1 has IPA after the headword; NCE 2/3 print a line reference.
        head = r"(?<![A-Za-z])" + re.escape(word).replace(r"\ ", r"\s+")
        pattern = (head + r"\s+\S{0,8}/") if book == 1 else (
            head + r"\.?\s*\((?:title|[lI1][.\s]?\d|\d)")
        if re.search(pattern, block, re.I):
            found.append(word)
    return found


def remove_order_conflicts(results: list[dict], source_rows: list[str]) -> dict[str, list[int]]:
    """Drop extra OCR hits outside a word's position in the ordered Excel list."""
    by_word: dict[str, list[int]] = defaultdict(list)
    for item in results:
        for word in item["matches"]:
            by_word[word].append(item["lesson"])
    counts = Counter(source_rows)
    unresolved = {}
    for word, candidates in list(by_word.items()):
        if len(candidates) <= counts[word]:
            continue
        positions = [i for i, row_word in enumerate(source_rows) if row_word == word]
        allowed: set[int] = set()
        for position in positions:
            before = next((by_word[source_rows[j]][0] for j in range(position - 1, -1, -1)
                           if len(by_word[source_rows[j]]) == 1), 1)
            after = next((by_word[source_rows[j]][0] for j in range(position + 1, len(source_rows))
                          if len(by_word[source_rows[j]]) == 1), results[-1]["lesson"])
            allowed.update(lesson for lesson in candidates if before <= lesson <= after)
        if len(allowed) != counts[word]:
            unresolved[word] = candidates
            for item in results:
                if word in item["matches"]:
                    item["matches"].remove(word)
            continue
        for item in results:
            if item["lesson"] not in allowed and word in item["matches"]:
                item["matches"].remove(word)
    return unresolved


def add_visual_checks(book: int, results: list[dict], source_words: list[str]) -> None:
    for word, lesson in VISUALLY_CHECKED[book].items():
        if word not in source_words:
            raise ValueError(f"visual override absent from Excel: {book} {word}")
        existing = [entry["lesson"] for entry in results if word in entry["matches"]]
        if existing and existing != [lesson]:
            raise ValueError(f"visual override conflicts with OCR: {book} {word} {existing}")
        if not existing:
            results[lesson - 1]["matches"].append(word)


def run(book: int, pdf_dir: Path, source_dir: Path, work: Path) -> dict:
    book_id = f"nce-{book}"
    rows_by_book = load_book_rows(source_dir)
    source_rows = [norm_lemma(r["word"]) for r in rows_by_book[book_id]]
    words = list(dict.fromkeys(source_rows))
    pdf = pdf_dir / f"新概念{book}.pdf"
    count = {1: 144, 2: 96, 3: 60}[book]
    results = []
    for lesson in range(1, count + 1):
        first = pdf_page(book, lesson)
        page = first + 1 if book == 1 else first
        text = ocr_page(pdf, page, work / f"nce-{book}" / f"p{page}.txt")
        block, complete = (vocab_block_one(text) if book == 1 else vocab_block(text))
        if not block and book != 1:
            page += 1
            text = ocr_page(pdf, page, work / f"nce-{book}" / f"p{page}.txt")
            block, complete = vocab_block(text)
        elif not complete and book != 1 and block:
            continuation = ocr_page(pdf, page + 1, work / f"nce-{book}" / f"p{page + 1}.txt")
            end = re.search(r"No[tf]es\s+on\s+the\s+text", continuation, re.I)
            block += "\n" + continuation
            complete = bool(end)
        hits = matches(block, words, book)
        results.append({
            "lesson": lesson, "printed_page": printed_page(book, lesson),
            "pdf_page": page, "heading_found": bool(block), "section_complete": complete,
            "matches": hits,
        })
        print(f"{book}:{lesson:02} pdf={page} heading={bool(block)} complete={complete} matches={len(hits)}", flush=True)
    unresolved = remove_order_conflicts(results, source_rows)
    add_visual_checks(book, results, words)
    output = work / f"nce-{book}" / "lesson-matches.json"
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    assignments = {}
    assignment_pages = {}
    duplicates = {}
    for item in results:
        for word in item["matches"]:
            if word in assignments:
                duplicates.setdefault(word, [assignments[word]]).append(item["lesson"])
            else:
                assignments[word] = item["lesson"]
                assignment_pages[word] = item["pdf_page"]
    review = output.with_name("review.csv")
    with review.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["word", "lesson", "status", "pdf_page"])
        for word in words:
            lesson = assignments.get(word, "")
            status = ("duplicate" if word in duplicates else
                      "visually_checked" if word in VISUALLY_CHECKED[book] else
                      "matched" if lesson else "unmatched")
            writer.writerow([word, lesson, status, assignment_pages.get(word, "")])
    return {"book": book_id, "total_words": len(words), "matched": len(assignments),
            "duplicates": duplicates, "headings_missing": [r["lesson"] for r in results if not r["heading_found"]],
            "order_conflicts": unresolved,
            "output": str(output), "review": str(review)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("book", type=int, choices=(1, 2, 3))
    parser.add_argument("--pdf-dir", type=Path, default=PDF_DIR)
    parser.add_argument("--source-dir", type=Path, default=SOURCE_DIR)
    parser.add_argument("--work", type=Path, default=WORK)
    args = parser.parse_args()
    print(json.dumps(run(args.book, args.pdf_dir, args.source_dir, args.work), ensure_ascii=False))


if __name__ == "__main__":
    main()
