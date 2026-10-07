"""Offline regressions for downloader and vocabulary index correctness."""

import json
import base64
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from download_all import is_match_xd
from pep_core import PepDownloader
from vocab_ocr.pep.catalog import PepBook
from vocab_ocr.pep.parse_appendix import ParseState, parse_line
from vocab_ocr.shared.build_index import build_inverted_index, clean_zh, norm_lemma


class DownloadRegressions(unittest.TestCase):
    def test_specific_stage_does_not_select_other_stage(self):
        self.assertFalse(
            is_match_xd("小学（六三学制）", "六三学制", ["初中（六三学制）"])
        )
        self.assertFalse(
            is_match_xd("初中（六三学制）", "六三学制", ["小学（六三学制）"])
        )
        self.assertTrue(
            is_match_xd("小学（六三学制）", "六三学制", ["义务教育（六三学制）"])
        )

    def test_partial_pages_never_become_a_pdf(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            image = root / "1.jpg"
            Image.new("RGB", (20, 20), "white").save(image)
            output = root / "book.pdf"
            self.assertFalse(PepDownloader.assemble_pdf([str(image)], 2, str(output)))
            self.assertFalse(output.exists())

    def test_only_complete_and_valid_pdf_can_be_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            output = root / "book.pdf"
            output.write_bytes(b"%PDF-1.4 " + b"0" * 60000)
            self.assertFalse(PepDownloader._complete_pdf(str(output), 1))
            image = root / "1.jpg"
            Image.new("RGB", (20, 20), "white").save(image)
            self.assertTrue(PepDownloader.assemble_pdf([str(image)], 1, str(output)))
            self.assertTrue(PepDownloader._complete_pdf(str(output), 1))
            self.assertFalse(PepDownloader._complete_pdf(str(output), 2))

    def test_download_book_retains_cache_when_one_page_fails(self):
        image_bytes = io.BytesIO()
        Image.new("RGB", (20, 20), "white").save(image_bytes, "JPEG")
        page_one = "data:image/jpeg;base64," + base64.b64encode(image_bytes.getvalue()).decode()

        class FakePage:
            url = "https://book.pep.com.cn/test/"

            def goto(self, *args, **kwargs):
                pass

            def title(self):
                return "教材"

            def query_selector(self, selector):
                return None

            def evaluate(self, script, url=None):
                if url is not None:
                    return {"status": 200, "ctype": "image/jpeg", "data": page_one} if url.endswith("/1.jpg") else {"status": 500}
                if "const total" in script:
                    return {"title": "测试教材", "total": 2}
                return True

        class FakePlaywright:
            def __enter__(self):
                page = FakePage()
                context = SimpleNamespace(add_init_script=lambda *_: None, new_page=lambda: page)
                browser = SimpleNamespace(new_context=lambda **_: context, close=lambda: None)
                return SimpleNamespace(chromium=SimpleNamespace(launch=lambda **_: browser))

            def __exit__(self, *_):
                pass

        with tempfile.TemporaryDirectory() as d:
            downloader = PepDownloader(output_dir=d)
            with patch("pep_core.sync_playwright", return_value=FakePlaywright()), patch("pep_core.get_base_dir", return_value=d), patch("pep_core.time.sleep"):
                result = downloader.download_book("test", custom_title="测试教材", skip_if_exists=False, quiet=True)
            self.assertIsNone(result)
            self.assertFalse((Path(d) / "测试教材.pdf").exists())
            self.assertTrue((Path(d) / "temp_pages" / "test_mobile" / "1.jpg").exists())


class VocabRegressions(unittest.TestCase):
    def test_gloss_drops_next_english_entry(self):
        self.assertEqual(clean_zh("私人的 ; recycle v. 回收利用"), "私人的")

    def test_ocr_fragments_are_not_headwords(self):
        self.assertIsNone(norm_lemma("a ar ay p fur"))
        self.assertIsNone(norm_lemma("around the world in eighty days craven"))
        self.assertEqual(norm_lemma("au revoir"), "au revoir")

    def test_index_excludes_empty_gloss_and_unmapped_junior_az(self):
        book = {
            "book_id": "junior-test",
            "title": "测试",
            "stage": "junior",
            "unit_starts": [],
            "entries": [
                {"book_id": "junior-test", "word": "good", "unit": "1", "zh": "好", "source": "unit_list"},
                {"book_id": "junior-test", "word": "noise", "unit": "1", "zh": "", "source": "unit_list"},
                {"book_id": "junior-test", "word": "apple", "unit": "6", "page": 20, "zh": "苹果", "source": "appendix_az"},
            ],
        }
        with tempfile.TemporaryDirectory() as d:
            path = build_inverted_index([book], Path(d))
            words = json.loads(path.read_text(encoding="utf-8"))["w"]
        self.assertEqual(words, {"good": [["junior-test", "1", "好"]]})

    def test_az_section_clears_previous_unit(self):
        state = ParseState(current_unit="6", section="unit_list")
        parse_line("Vocabulary A-Z", book_id="x", book_title="x", stage="junior", state=state, pdf_page=1)
        entry = parse_line("apple 苹果 p.20", book_id="x", book_title="x", stage="junior", state=state, pdf_page=1)
        self.assertIsNotNone(entry)
        self.assertIsNone(entry.unit)

    def test_single_book_preview_does_not_replace_full_index(self):
        from vocab_ocr.pep import pipeline

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out = root / "out"
            work = root / "work"
            (out / "books").mkdir(parents=True)
            full = out / "vocab-index.min.json"
            full.write_text("full-index", encoding="utf-8")
            book = PepBook("junior-test", "测试", "junior", root / "unused.pdf")
            result = {
                "book_id": book.id,
                "title": book.title,
                "stage": book.stage,
                "entry_count": 1,
                "entry_with_unit_count": 1,
                "vocab_pdf_pages": [1, 1],
                "locate_method": "fixture",
                "entries": [{"book_id": book.id, "word": "good", "unit": "1", "zh": "好"}],
            }
            (out / "books" / "junior-test.json").write_text(json.dumps(result), encoding="utf-8")
            with patch.object(pipeline, "DEFAULT_OUT", out), patch.object(pipeline, "DEFAULT_WORK", work), patch.object(pipeline, "get_book", return_value=book), patch.object(pipeline, "process_book", return_value=result):
                path = pipeline.process_all([book.id])
            self.assertEqual(full.read_text(encoding="utf-8"), "full-index")
            self.assertTrue(path.is_relative_to(work))

    def test_cached_junior_az_uses_verified_printed_page_map(self):
        from vocab_ocr.pep.pipeline import prepare_book_for_index

        book = {
            "book_id": "junior-8a", "title": "英语八年级上册", "stage": "junior",
            "pdf_pages": 150, "unit_starts": [],
            "entries": [
                {"source": "appendix_az", "word": "apple", "page": 45, "unit": "8", "zh": "苹果"},
                {"source": "appendix_az", "word": "notes", "page": 90, "unit": "8", "zh": "笔记"},
            ],
        }
        prepared = prepare_book_for_index(book)
        self.assertEqual(prepared["entries"][0]["unit"], "5")
        self.assertIsNone(prepared["entries"][1]["unit"])
        self.assertEqual(len(prepared["unit_starts"]), 8)


if __name__ == "__main__":
    unittest.main()
