"""NCE index shape, book membership, and PDF lesson mapping checks."""

import json
import tempfile
import unittest
from pathlib import Path

from vocab_ocr.nce.align_pdf_lessons import matches, pdf_page, vocab_block_four
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
        self.assertEqual([pdf_page(4, n) for n in (1, 8, 9, 24, 25, 32, 33, 48)],
                         [34, 76, 82, 167, 178, 217, 224, 309])
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

    def test_fourth_book_glossary_can_start_on_either_page(self) -> None:
        block, complete, offset = vocab_block_four([
            "Lesson 1 text", "New words and expressions\nfossil man (title)\nNotes on the text",
        ])
        self.assertEqual((complete, offset), (True, 1))
        self.assertIn("fossil man (title)", block)
        block, complete, offset = vocab_block_four([
            "Lesson 48\nNew words and expression\nportfolio (title)",
            "priority (ll.14-15)\nNotes on the text\nMore text",
        ])
        self.assertEqual((complete, offset), (True, 0))
        self.assertIn("priority (ll.14-15)", block)
        self.assertEqual(matches("tipster (l.1) /'tipsta/\n"
                                 "Notes on the text\npriority (l.14)\n"
                                 "pedestrian (l.20) /pa'destrian/",
                                 ["tipster", "priority", "pedestrian"], 4),
                         ["tipster", "pedestrian"])

    def test_fourth_book_lesson_hits_keep_repeated_words(self) -> None:
        rows = {book_id: [{"word": "shared"}] for book_id, _, _ in BOOK_FILES}
        index = build_index(rows)
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            for book, count in ((2, 96), (3, 60), (4, 48)):
                path = work / f"nce-{book}" / "lesson-matches.json"
                path.parent.mkdir()
                path.write_text(json.dumps([
                    {"lesson": lesson, "matches": ["shared"] if book == 4 and lesson in (1, 48) else []}
                    for lesson in range(1, count + 1)
                ]), encoding="utf-8")
            self.assertEqual(add_pdf_lessons(index, work),
                             {"nce-2": 0, "nce-3": 0, "nce-4": 1})
        self.assertEqual(index["w"]["shared"], [
            ["nce-1", "", ""], ["nce-2", "", ""], ["nce-3", "", ""],
            ["nce-4", "1", ""], ["nce-4", "48", ""],
        ])


if __name__ == "__main__":
    unittest.main()
