import unittest

from vocab_ocr.gloss import validate_gloss_source


class GlossProvenanceTests(unittest.TestCase):
    def test_supplement_requires_explicit_origin_and_usable_source(self):
        valid = {"status": "supplemented", "note": "中文首义以同版资料补充",
                 "sources": [{"kind": "same-edition", "label": "Unit 4讲义",
                              "url": "https://example.com/unit4"}]}
        validate_gloss_source(valid, 108)
        for url in ("file:///tmp/a", "https://user:password@example.com/a", "relative/path"):
            candidate = {**valid, "sources": [{**valid["sources"][0], "url": url}]}
            with self.assertRaises(ValueError):
                validate_gloss_source(candidate, 108)
        with self.assertRaises(ValueError):
            validate_gloss_source({**valid, "sources": []})

    def test_cross_reference_must_point_inside_the_same_source_book(self):
        valid = {"status": "cross-reference", "note": "同书A–Z对照恢复",
                 "sources": [{"kind": "same-book", "label": "A–Z",
                              "source_pdf_pages": [100]}]}
        validate_gloss_source(valid, 108)
        for pages in ([109], [100, 100], [True]):
            with self.assertRaises(ValueError):
                validate_gloss_source({**valid, "sources": [{**valid["sources"][0], "source_pdf_pages": pages}]}, 108)
        with self.assertRaises(ValueError):
            validate_gloss_source({**valid, "sources": [{"kind": "conventional-name", "label": "规范译名"}]})


if __name__ == "__main__":
    unittest.main()
