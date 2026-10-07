"""Safety checks for resumable PEP visual extraction and publication."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vocab_ocr.pep.catalog import PepBook
from vocab_ocr.pep import vision_pipeline


class VisionPipelineTests(unittest.TestCase):
    def test_whole_page_candidate_keeps_printed_reference_and_reuses_matching_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf = root / "book.pdf"
            pdf.write_bytes(b"fixture")
            book = PepBook("junior-8a", "英语八年级上册", "junior", pdf)
            image = root / "page.jpg"
            image.write_bytes(b"image")
            response = {
                "source_pdf_page": 126, "kind": "vocab", "reason": None,
                "printed_page": "42", "uncertainty": [], "raw_response": "{}",
                "entries": [{"word": "disappointed", "zh": "失望的；沮丧的", "ref": "p.36",
                             "raw": "disappointed 失望的；沮丧的 p.36", "uncertainty": [],
                             "column": "left", "source_pdf_page": 126}],
            }
            source = {"pdf_pages": 150, "vocab_pdf_pages": [126, 126]}
            with patch.object(vision_pipeline, "_source_book", return_value=source), \
                 patch.object(vision_pipeline, "render_pages", return_value=[image]), \
                 patch.object(vision_pipeline, "transcribe_page", return_value=response) as transcribe:
                first = vision_pipeline.process_vision_book(book, work_dir=root / "work")
                second = vision_pipeline.process_vision_book(book, work_dir=root / "work")
            self.assertEqual(transcribe.call_count, 1)
            self.assertEqual(first["entries"], second["entries"])
            self.assertEqual(first["entries"][0]["unit"], "4")
            self.assertEqual(first["entries"][0]["page"], 36)
            self.assertEqual(first["entries"][0]["pdf_page"], 126)

    def test_missing_corpus_does_not_replace_formal_index(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            out = root / "out"
            out.mkdir()
            formal = out / "vocab-index.min.json"
            formal.write_text("existing index", encoding="utf-8")
            book = PepBook("junior-8a", "英语八年级上册", "junior", root / "book.pdf")
            with patch.object(vision_pipeline, "DEFAULT_OUT", out), \
                 patch.object(vision_pipeline, "BOOKS", [book]):
                with self.assertRaises(FileNotFoundError):
                    vision_pipeline.publish_vision_index(work_dir=root / "vision")
            self.assertEqual(formal.read_text(encoding="utf-8"), "existing index")


if __name__ == "__main__":
    unittest.main()
