"""Book-level NCE index shape and membership checks."""

import unittest

from vocab_ocr.nce.build_book_index import BOOK_FILES, build_index


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


if __name__ == "__main__":
    unittest.main()
