"""NCE index shape, book membership, and PDF lesson mapping checks."""

import json
import tempfile
import unittest
from pathlib import Path

from vocab_ocr.nce.align_pdf_lessons import pdf_page
from vocab_ocr.nce.build_book_index import BOOK_FILES, add_pdf_lessons, build_index


class NceBookIndexTests(unittest.TestCase):
    def test_deduplicates_within_book_and_keeps_cross_book_membership(self) -> None:
        rows = {book_id: [{"word": f"only {book_id}"}] for book_id, _, _ in BOOK_FILES}
        rows["nce-1"] += [{"word": "Private"}, {"word": "private"}]
        rows["nce-2"] += [{"word": "PRIVATE"}]

        index = build_index(rows)

        self.assertEqual(index["v"], 1)
        self.assertEqual(set(index["books"]), {"nce-1", "nce-2", "nce-3", "nce-4"})
        self.assertEqual(index["w"]["private"], [["nce-1", "", ""], ["nce-2", "", ""]])

    def test_missing_book_cannot_build_partial_index(self) -> None:
        rows = {book_id: [{"word": "sample"}] for book_id, _, _ in BOOK_FILES[:3]}
        with self.assertRaisesRegex(ValueError, "exactly four books"):
            build_index(rows)

    def test_pdf_lesson_boundaries_and_partial_enrichment(self) -> None:
        self.assertEqual([pdf_page(1, n) for n in (1, 72, 73, 144)], [5, 147, 153, 295])
        self.assertEqual([pdf_page(2, n) for n in (1, 24, 25, 48, 49, 72, 73, 96)],
                         [15, 107, 125, 217, 235, 327, 345, 437])
        self.assertEqual([pdf_page(3, n) for n in (1, 20, 21, 40, 41, 60)],
                         [16, 92, 108, 184, 194, 270])
        rows = {book_id: [{"word": "shared"}, {"word": "unknown"}]
                for book_id, _, _ in BOOK_FILES}
        index = build_index(rows)
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            for book, count in ((2, 96), (3, 60)):
                path = work / f"nce-{book}" / "lesson-matches.json"
                path.parent.mkdir()
                path.write_text(json.dumps([
                    {"lesson": lesson, "matches": ["shared"] if lesson in (1, 2) else []}
                    for lesson in range(1, count + 1)
                ]), encoding="utf-8")
            self.assertEqual(add_pdf_lessons(index, work), {"nce-2": 1, "nce-3": 1})
        self.assertEqual(index["w"]["shared"], [
            ["nce-1", "", ""], ["nce-2", "1", ""], ["nce-2", "2", ""],
            ["nce-3", "1", ""], ["nce-3", "2", ""], ["nce-4", "", ""],
        ])
        self.assertEqual(index["w"]["unknown"], [
            ["nce-1", "", ""], ["nce-2", "", ""],
            ["nce-3", "", ""], ["nce-4", "", ""],
        ])


if __name__ == "__main__":
    unittest.main()
