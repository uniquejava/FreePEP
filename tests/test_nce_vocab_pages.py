"""The vocabulary-page export keeps source page order and page mapping."""

import csv
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from vocab_ocr.nce.export_vocab_pages import export_book, load_page_map


class NceVocabPagesTests(unittest.TestCase):
    def test_checked_page_map_keeps_cross_page_glossaries(self) -> None:
        books = load_page_map()["books"]
        self.assertEqual({book: len(data["pages"]) for book, data in books.items()},
                         {"nce-1": 115, "nce-2": 96, "nce-3": 67, "nce-4": 52})
        self.assertIn([43, 203, "continuation"], books["nce-3"]["pages"])
        self.assertIn([27, 190, "continuation"], books["nce-4"]["pages"])
        self.assertEqual(books["nce-4"]["source_file"], "新概念4-完整.pdf")

    def test_export_copies_selected_pages_and_writes_usable_csv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.pdf"
            writer = PdfWriter()
            for width in range(101, 107):
                writer.add_blank_page(width=width, height=200)
            with source.open("wb") as stream:
                writer.write(stream)
            result = export_book("nce-2", {
                "source_file": source.name, "source_page_count": 6,
                "pages": [[1, 4, "wordlist"], [1, 5, "continuation"],
                          [2, 6, "wordlist"]],
            }, root, root / "export")
            exported = PdfReader(result["pdf"])
            self.assertEqual([int(page.mediabox.width) for page in exported.pages],
                             [104, 105, 106])
            self.assertEqual(len(exported.outline), 2)
            with Path(result["page_map"]).open(encoding="utf-8-sig") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual([(r["snapshot_page"], r["lesson"],
                               r["source_pdf_page"], r["printed_page"], r["role"])
                              for r in rows], [
                                  ("1", "1", "4", "1", "wordlist"),
                                  ("2", "1", "5", "2", "continuation"),
                                  ("3", "2", "6", "3", "wordlist"),
                              ])


if __name__ == "__main__":
    unittest.main()
