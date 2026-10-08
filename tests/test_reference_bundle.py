"""Portable references must survive relocation and reject mismatched evidence."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject

from vocab_ocr.reference import (
    build_bundle, export_regions, install_bundle, junior_unit, lemma, publish_indexes, read_corpus, record_page,
    sha256, validate_bundle, write_json,
)


class ReferenceBundleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.work, self.output = self.root / "work", self.root / "bundle"
        books = {}
        for series, book_id in [("pep", "senior-fixture"), ("nce", "nce-fixture")]:
            source = self.root / f"{book_id}.pdf"
            writer = PdfWriter()
            for width in (101, 200, 303, 404):
                page = writer.add_blank_page(width=width, height=400)
                if width == 200:
                    content = DecodedStreamObject()
                    content.set_data(b"1 0 0 rg 0 0 100 400 re f 0 0 1 rg 100 0 100 400 re f")
                    page[NameObject("/Contents")] = writer._add_object(content)
                    page.rotate(90)
            writer.write(source)
            books[book_id] = {
                "title": book_id, "series": series, "stage": "senior" if series == "pep" else "nce",
                "source": str(source), "source_sha256": sha256(source), "source_page_count": 4,
                "pages": [{"source_pdf_page": p, "unit": "27"} for p in (2, 3, 4)],
            }
        write_json(self.work / "sources.json", {"v": 1, "reader": "codex-direct-vision", "books": books})
        for book_id in books:
            for p in (2, 3):
                record_page(book_id, p, p - 1, "nuclear|27|原子能的；核能的|top", work=self.work,
                            regions=[{"id": "top", "bbox": [0, 0, 1, .5]}])
            record_page(book_id, 4, None, "", regions=[], kind="non_vocab", reason="封底", work=self.work)

    def rehash_manifest(self):
        manifest = json.loads((self.output / "manifest.json").read_text())
        manifest["files"] = {name: sha256(self.output / name) for name in manifest["files"]}
        write_json(self.output / "manifest.json", manifest)

    def test_whole_pages_order_continuation_and_relocation(self):
        result = build_bundle(self.work, self.output)
        self.assertEqual(result["pages"], 4)
        index = json.loads((self.output / "pep-vocab-index.min.json").read_text())
        hit = index["w"]["nuclear"][0]
        self.assertEqual(hit["pdf_pages"], [1, 2])
        self.assertEqual(hit["references"], [{"pdf_page": 1, "region_id": "top"}, {"pdf_page": 2, "region_id": "top"}])
        pdf = PdfReader(self.output / index["pdfs"]["senior-fixture"]["file"])
        self.assertEqual([int(p.mediabox.width) for p in pdf.pages], [200, 303])
        self.assertEqual(pdf.pages[0].rotation, 90)
        moved = self.root / "relocated"
        shutil.move(self.output, moved)
        for p in self.root.glob("*-fixture.pdf"):
            p.unlink()
        validate_bundle(moved)

    def test_incomplete_review_cannot_replace_published_output(self):
        self.output.mkdir()
        (self.output / "keep").write_text("previous good bundle")
        (self.work / "books/nce-fixture/pages/003.json").unlink()
        with self.assertRaisesRegex(ValueError, "publication blocked"):
            build_bundle(self.work, self.output)
        self.assertEqual((self.output / "keep").read_text(), "previous good bundle")

    def test_source_change_invalidates_review(self):
        source = self.root / "senior-fixture.pdf"
        with source.open("ab") as stream:
            stream.write(b"\n% changed source\n")
        _, _, blockers = read_corpus(self.work)
        self.assertIn("senior-fixture: source PDF changed", blockers)

    def test_wrong_nce_lesson_cannot_publish_a_consistent_but_false_page_map(self):
        path = self.work / "books/nce-fixture/pages/002.json"
        record = json.loads(path.read_text())
        record["entries"][0]["unit"] = "60"
        write_json(path, record)
        with self.assertRaisesRegex(ValueError, "word Lesson disagrees"):
            build_bundle(self.work, self.output)

    def test_grade_nine_includes_the_two_final_units_from_the_actual_contents(self):
        self.assertEqual(junior_unit("junior-9", 204, 96), "12")
        self.assertEqual(junior_unit("junior-9", 204, 97), "13")
        self.assertEqual(junior_unit("junior-9", 204, 105), "14")
        self.assertEqual(junior_unit("junior-9", 204, 112), "14")
        with self.assertRaises(ValueError):
            junior_unit("junior-9", 204, 113)

    def test_application_install_is_complete_and_small_publication_excludes_pdfs(self):
        build_bundle(self.work, self.output)
        installed = self.root / "App/Resources/TextbookReferences"
        install_bundle(self.output, installed)
        shutil.rmtree(self.output)
        validate_bundle(installed)
        small = self.root / "data/vocab"
        publish_indexes(installed, small)
        self.assertEqual({p.name for p in small.iterdir()}, {
            "vocab-index.min.json", "nce-vocab-index.min.json", "vocab-page-map.json"})
        self.assertEqual(json.loads((small / "vocab-index.min.json").read_text())["v"], 2)
        # An invalid new input cannot replace the previously installed package.
        corrupt = self.root / "corrupt"
        shutil.copytree(installed, corrupt)
        (corrupt / "pdf/nce-fixture-vocab.pdf").unlink()
        with self.assertRaises(ValueError):
            install_bundle(corrupt, installed)
        validate_bundle(installed)

    def test_pdf_content_and_metadata_are_both_checked(self):
        build_bundle(self.work, self.output)
        index_path = self.output / "pep-vocab-index.min.json"
        index = json.loads(index_path.read_text())
        index["pdfs"]["senior-fixture"]["page_count"] = 30
        write_json(index_path, index)
        self.rehash_manifest()
        with self.assertRaisesRegex(ValueError, "PDF metadata mismatch"):
            validate_bundle(self.output)

    def test_region_reference_is_checked_even_with_valid_digests(self):
        build_bundle(self.work, self.output)
        index_path = self.output / "nce-vocab-index.min.json"
        index = json.loads(index_path.read_text())
        index["w"]["nuclear"][0]["references"][0]["region_id"] = "missing"
        write_json(index_path, index)
        self.rehash_manifest()
        with self.assertRaisesRegex(ValueError, "bad region or unit"):
            validate_bundle(self.output)

    def test_manifest_rejects_missing_pdf_or_traversal(self):
        build_bundle(self.work, self.output)
        manifest_path = self.output / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"]["../outside.pdf"] = "0" * 64
        write_json(manifest_path, manifest)
        with self.assertRaisesRegex(ValueError, "manifest"):
            validate_bundle(self.output)

    def test_crops_follow_visible_rotation_and_keep_provenance(self):
        build_bundle(self.work, self.output)
        crops = self.root / "crops"
        export_regions(self.output, crops, dpi=72)
        with Image.open(crops / "senior-fixture/001-top.png") as crop:
            red, green, blue = crop.convert("RGB").getpixel((200, 50))
            self.assertGreater(red, 240)
            self.assertLess(blue, 15)
        provenance = json.loads((crops / "senior-fixture/001-top.json").read_text())
        self.assertEqual(provenance["source_pdf_page"], 2)
        self.assertEqual(provenance["pdf_page"], 1)
        self.assertEqual(provenance["map_sha256"], sha256(self.output / "vocab-page-map.json"))

    def test_printed_alias_and_keyboard_apostrophe_find_same_source(self):
        path = self.work / "books/senior-fixture/pages/002.json"
        record = json.loads(path.read_text())
        record["entries"][0].update(word="one’s", lemma=lemma("one’s"), aliases=["printed alternative"])
        write_json(path, record)
        build_bundle(self.work, self.output)
        index = json.loads((self.output / "pep-vocab-index.min.json").read_text())
        self.assertEqual(index["w"]["one's"], index["w"]["printed alternative"])


if __name__ == "__main__":
    unittest.main()
