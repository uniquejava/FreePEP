"""Portable references must survive relocation and reject mismatched evidence."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject

from vocab_ocr.reference import (
    build_bundle, build_selected_draft, export_regions, install_bundle, junior_unit, lemma, prepare,
    prepare_grade9_replacement, publish_indexes, read_corpus, record_page,
    pos_status, sha256, validate_bundle, write_json,
)
from vocab_ocr.pos import printed_tags, resolve_source, validate_pos
from vocab_ocr.pep.catalog import PepBook


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

    def add_pos_review(self):
        # These test-only images stand in for directly reviewed crop evidence.
        build_bundle(self.work, self.output)
        crops = self.work.parent / "vocab-page-regions"
        export_regions(self.output, crops, dpi=72)
        for path in self.work.glob("books/*/pages/*.json"):
            record = json.loads(path.read_text())
            if record["kind"] != "vocab":
                continue
            crop = crops / path.parents[1].name / f"{record['source_pdf_page'] - 1:03d}-top.json"
            record["pos_review"] = {"reviewed_by": "codex-direct-vision", "regions": {
                "top": {"metadata_sha256": sha256(crop), "image_sha256": sha256(crop.with_suffix('.png'))}}}
            for entry in record["entries"]:
                entry["pos"] = {"status": "printed", "raw": "adj.", "tags": ["adjective"]}
            write_json(path, record)

    def test_pos_conflicts_split_occurrences_and_aliases_keep_evidence(self):
        self.add_pos_review()
        path = self.work / "books/senior-fixture/pages/003.json"
        record = json.loads(path.read_text())
        record["entries"][0].update(pos={"status": "printed", "raw": "n.", "tags": ["noun"]}, aliases=["atomic"])
        write_json(path, record)
        self.assertEqual(pos_status(read_corpus(self.work)[1])["senior-fixture"]["conflicts"], 1)
        build_bundle(self.work, self.output)
        index = json.loads((self.output / "pep-vocab-index.min.json").read_text())
        self.assertEqual(index["pos_version"], 1)
        hits = index["w"]["nuclear"]
        self.assertEqual([h["pos"]["tags"] for h in hits], [["adjective"], ["noun"]])
        self.assertEqual([h["pdf_pages"] for h in hits], [[1], [2]])
        self.assertEqual(index["w"]["atomic"], [hits[1]])
        self.assertEqual(hits[1]["pos_evidence"][0]["source_pdf_page"], 3)

    def test_pos_continuation_uses_the_actual_printed_source(self):
        self.add_pos_review()
        path = self.work / "books/senior-fixture/pages/003.json"
        record = json.loads(path.read_text())
        record["entries"][0]["pos"]["inherited_from"] = {
            "source_pdf_page": 2, "region_id": "top", "entry_index": 0}
        write_json(path, record)
        build_bundle(self.work, self.output)
        hit = json.loads((self.output / "pep-vocab-index.min.json").read_text())["w"]["nuclear"][0]
        self.assertEqual(hit["pdf_pages"], [1, 2])
        self.assertEqual([e["source_pdf_page"] for e in hit["pos_evidence"]], [2])
        record["entries"][0]["pos"]["inherited_from"]["source_pdf_page"] = 3
        write_json(path, record)
        with self.assertRaisesRegex(ValueError, "cyclic continuation"):
            build_bundle(self.work, self.output)

    def test_unmarked_continuation_uses_the_headword_region_and_rejects_different_entries(self):
        self.add_pos_review()
        for page in (2, 3):
            path = self.work / f"books/senior-fixture/pages/{page:03d}.json"
            record = json.loads(path.read_text())
            record["entries"][0].update(word="combine ... with ...", lemma="combine ... with ...",
                                        zh="把……与……结合起来",
                                        pos={"status": "unmarked", "raw": "", "tags": []})
            if page == 3:
                record["entries"][0]["pos"]["inherited_from"] = {
                    "source_pdf_page": 2, "region_id": "top", "entry_index": 0}
            write_json(path, record)
        build_bundle(self.work, self.output)
        hit = json.loads((self.output / "pep-vocab-index.min.json").read_text())["w"]["combine ... with ..."][0]
        self.assertEqual(hit["pos"], {"status": "unmarked", "raw": "", "tags": []})
        self.assertEqual(hit["pdf_pages"], [1, 2])
        self.assertEqual([e["source_pdf_page"] for e in hit["pos_evidence"]], [2])

        # Exact Grade 9 lower-book continuation: PDF101 has only the Chinese
        # tail; the headword and absence of a printed label are on PDF100.
        source_entry = {"word": "combine ... with ...", "unit": "3", "page": 22,
                        "zh": "把……与……结合起来", "region_id": "right",
                        "pos": {"status": "unmarked", "raw": "", "tags": []}}
        source = {"source_pdf_page": 100, "entries": [dict(source_entry, word="other") for _ in range(39)] + [source_entry]}
        continuation_entry = json.loads(json.dumps(source_entry))
        continuation_entry["region_id"] = "left"
        continuation_entry["pos"]["inherited_from"] = {
            "source_pdf_page": 100, "region_id": "right", "entry_index": 39}
        continuation = {"source_pdf_page": 101, "entries": [continuation_entry]}
        validate_pos(continuation_entry["pos"])
        self.assertEqual(resolve_source(continuation, continuation_entry, [source, continuation]),
                         (source, source_entry))
        for change in ({"word": "combine"}, {"zh": "不同词义"}, {"unit": "4"}, {"page": 23},
                       {"region_id": "left"}, {"pos": {"status": "printed", "raw": "v.", "tags": ["verb"]}}):
            bad_source = json.loads(json.dumps(source))
            bad_source["entries"][39].update(change)
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "source disagrees"):
                resolve_source(continuation, continuation_entry, [bad_source, continuation])
        wrong_target = json.loads(json.dumps(continuation_entry))
        wrong_target["pos"]["inherited_from"]["entry_index"] = 38
        with self.assertRaisesRegex(ValueError, "source disagrees"):
            resolve_source(continuation, wrong_target, [source, continuation])
        for pos in ({"status": "type", "raw": "phrase", "tags": []},
                    {"status": "inferred", "raw": "", "tags": ["verb"], "note": "guess"},
                    {"status": "unresolved", "raw": "", "tags": [], "note": "unknown"}):
            pos["inherited_from"] = continuation_entry["pos"]["inherited_from"]
            with self.subTest(status=pos["status"]), self.assertRaisesRegex(ValueError, "invalid continuation"):
                validate_pos(pos)

    def test_partial_or_stale_pos_review_cannot_publish(self):
        self.add_pos_review()
        path = self.work / "books/senior-fixture/pages/003.json"
        original = json.loads(path.read_text())
        record = json.loads(path.read_text())
        del record["entries"][0]["pos"]
        write_json(path, record)
        with self.assertRaisesRegex(ValueError, "POS review missing"):
            build_bundle(self.work, self.output)
        write_json(path, original)
        crop = self.work.parent / "vocab-page-regions/senior-fixture/002-top.png"
        crop.write_bytes(crop.read_bytes() + b"changed")
        with self.assertRaisesRegex(ValueError, "POS crop source/image identity"):
            build_bundle(self.work, self.output)

    def test_pos_corruption_is_rejected_even_after_rehash(self):
        self.add_pos_review()
        build_bundle(self.work, self.output)
        path = self.output / "pep-vocab-index.min.json"
        original = json.loads(path.read_text())
        for mutate in (lambda h: h["pos"].update(tags=["verb"]),
                       lambda h: h["pos_evidence"][0].update(source_pdf_page=4),
                       lambda h: h["pos_evidence"][0].update(image_sha256="0" * 64),
                       lambda h: h.update(pos_evidence=[None]),
                       lambda h: h["pos"].update(senses=[{"raw": "n.", "tags": ["noun"], "zh": "核"}]),
                       lambda h: h.pop("pos")):
            index = json.loads(json.dumps(original))
            mutate(index["w"]["nuclear"][0])
            write_json(path, index)
            self.rehash_manifest()
            with self.assertRaisesRegex(ValueError, "POS"):
                validate_bundle(self.output)

    def test_printed_labels_preserve_verb_granularity(self):
        self.assertEqual(printed_tags("vt. & vi."), ["transitive_verb", "intransitive_verb"])
        self.assertEqual(printed_tags("modal v."), ["modal_verb"])
        self.assertEqual(printed_tags("possessive adjective"), ["adjective"])
        self.assertEqual(printed_tags("predicative adj."), ["adjective"])
        self.assertEqual(printed_tags("quantifier"), ["determiner"])

    def test_evidence_without_pos_extension_cannot_install(self):
        build_bundle(self.work, self.output)
        path = self.output / "pep-vocab-index.min.json"
        index = json.loads(path.read_text())
        index["w"]["nuclear"][0]["pos_evidence"] = [None]
        write_json(path, index)
        self.rehash_manifest()
        with self.assertRaisesRegex(ValueError, "POS occurrence requires"):
            validate_bundle(self.output)

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

    def grade9_replacement(self, *, pos=True):
        """Small baseline plus real new-edition page counts, no textbook assets."""
        baseline = json.loads((self.work / "sources.json").read_text())
        old = dict(baseline["books"]["senior-fixture"], id="junior-9", title="英语九年级全一册")
        baseline["books"]["junior-9"] = old
        write_json(self.work / "sources.json", baseline)
        for p in (2, 3):
            record_page("junior-9", p, p - 1, "obsolete|27|旧版词项|top", work=self.work,
                        regions=[{"id": "top", "bbox": [0, 0, 1, .5]}])
        record_page("junior-9", 4, None, "", work=self.work, regions=[], kind="non_vocab", reason="封底")
        with patch("vocab_ocr.reference.BOOKS", [PepBook("junior-9", old["title"], "junior", Path(old["source"]))]):
            if pos:
                self.add_pos_review()
            build_bundle(self.work, self.output)
        replacement = self.root / "replacement"
        catalog = []
        books = {}
        for book_id, count, first, title in (("junior-9a", 142, 117, "英语九年级上册"),
                                             ("junior-9b", 108, 94, "英语九年级下册")):
            source = self.root / f"{book_id}.pdf"
            writer = PdfWriter()
            for n in range(count):
                writer.add_blank_page(width=100 + n, height=400)
            writer.write(source)
            catalog.append(PepBook(book_id, title, "junior", source))
            books[book_id] = {"id": book_id, "title": title, "series": "pep", "stage": "junior",
                              "source": str(source), "source_sha256": sha256(source), "source_page_count": count,
                              "pages": [{"source_pdf_page": n, "unit": ""} for n in range(first, count + 1)]}
        # The plan and one reviewed page may exist before preparation.
        write_json(replacement / "sources.json", {"v": 1, "reader": "codex-direct-vision", "books": books})
        for book_id, book in books.items():
            for i, row in enumerate(book["pages"]):
                page = row["source_pdf_page"]
                if i < 2:
                    record_page(book_id, page, i + 1, f"nuclear|p.{1 + 10 * i}|新版释义|top",
                                work=replacement, regions=[{"id": "top", "bbox": [0, 0, 1, .5]}])
                    path = replacement / "books" / book_id / "pages" / f"{page:03d}.json"
                    data = json.loads(path.read_text())
                    data["entries"][0]["pos"] = {"status": "printed", "raw": "n.", "tags": ["noun"]}
                    write_json(path, data)
                else:
                    record_page(book_id, page, None, "", work=replacement, regions=[],
                                kind="non_vocab", reason="测试中的非词表候选页")
        return replacement, catalog

    def review_grade9_draft(self, work, draft):
        crops = work.parent / "vocab-page-regions"
        export_regions(draft, crops, dpi=72, books=["junior-9a", "junior-9b"])
        for book_id in ("junior-9a", "junior-9b"):
            paths = sorted((work / "books" / book_id / "pages").glob("*.json"))
            for snapshot, path in enumerate(paths[:2], 1):
                row = json.loads(path.read_text())
                crop = crops / book_id / f"{snapshot:03d}-top.json"
                row["pos_review"] = {"reviewed_by": "codex-direct-vision", "regions": {"top": {
                    "metadata_sha256": sha256(crop), "image_sha256": sha256(crop.with_suffix('.png'))}}}
                write_json(path, row)

    def test_grade9_prepare_upgrades_only_identical_pair_and_preserves_records(self):
        work, catalog = self.grade9_replacement()
        before = {p: p.read_bytes() for p in work.glob("books/*/pages/*.json")}
        frozen = (self.work / "sources.json").read_bytes()
        with patch("vocab_ocr.reference.BOOKS", catalog):
            plan = prepare_grade9_replacement(self.work, work, self.output)
            self.assertEqual(set(plan["books"]), {"senior-fixture", "nce-fixture", "junior-9a", "junior-9b"})
            self.assertEqual(prepare_grade9_replacement(self.work, work, self.output), plan)
            with self.assertRaisesRegex(ValueError, "source plan changed"):
                prepare(self.work, nce_dir=self.root)
        self.assertEqual((self.work / "sources.json").read_bytes(), frozen)
        self.assertTrue(all(p.read_bytes() == content for p, content in before.items()))
        plan["books"]["junior-9a"]["source_sha256"] = "0" * 64
        write_json(work / "sources.json", plan)
        with patch("vocab_ocr.reference.BOOKS", catalog), self.assertRaisesRegex(ValueError, "plan changed"):
            prepare_grade9_replacement(self.work, work, self.output)

    def test_retired_grade9_cannot_overwrite_current_resources_but_remains_a_valid_baseline(self):
        work, catalog = self.grade9_replacement()
        validate_bundle(self.output)
        frozen = {p.relative_to(self.output): p.read_bytes() for p in self.output.rglob("*") if p.is_file()}
        installed, small = self.root / "installed", self.root / "published"
        for path in (installed, small):
            path.mkdir()
            (path / "current").write_text("keep current resources")
        for action in (lambda: build_bundle(self.work, self.output),
                       lambda: publish_indexes(self.output, small),
                       lambda: install_bundle(self.output, installed)):
            with self.assertRaisesRegex(ValueError, "retired book junior-9"):
                action()
        self.assertTrue(all((self.output / p).read_bytes() == data for p, data in frozen.items()))
        for path in (installed, small):
            self.assertEqual([p.name for p in path.iterdir()], ["current"])
            self.assertEqual((path / "current").read_text(), "keep current resources")
        # Validation and incremental reuse intentionally accept the historical
        # bundle, even though current publication must reject its retired ID.
        with patch("vocab_ocr.reference.BOOKS", catalog):
            prepare_grade9_replacement(self.work, work, self.output)
            draft, output = self.root / "draft", self.root / "replacement-bundle"
            build_selected_draft(work, draft)
            self.review_grade9_draft(work, draft)
            build_bundle(work, output, base_bundle=self.output)
            publish_indexes(output, small)
            install_bundle(output, installed)
        self.assertNotIn("junior-9", json.loads((small / "vocab-index.min.json").read_text())["books"])
        # A test catalogue explicitly containing the old ID can still construct
        # historical fixtures; unrelated small fixture books are not restricted.
        old = json.loads((self.work / "sources.json").read_text())["books"]["junior-9"]
        with patch("vocab_ocr.reference.BOOKS", [PepBook("junior-9", old["title"], "junior", Path(old["source"]))]):
            build_bundle(self.work, self.output)
            publish_indexes(self.output, self.root / "historical-indexes")
            install_bundle(self.output, self.root / "historical-install")

    def test_selected_draft_is_unpublishable_and_regions_are_scoped(self):
        work, catalog = self.grade9_replacement()
        original = {p: p.read_bytes() for p in work.glob("books/*/pages/*.json")}
        draft = self.root / "draft"
        with patch("vocab_ocr.reference.BOOKS", catalog):
            prepare_grade9_replacement(self.work, work, self.output)
            build_selected_draft(work, draft, books=["junior-9a"])
        validate_bundle(draft, allow_draft=True)
        for action in (lambda: validate_bundle(draft), lambda: publish_indexes(draft, self.root / "small"),
                       lambda: install_bundle(draft, self.root / "installed")):
            with self.assertRaisesRegex(ValueError, "draft"):
                action()
        self.assertTrue(all(p.read_bytes() == content for p, content in original.items()))
        index = json.loads((draft / "pep-vocab-index.min.json").read_text())
        self.assertNotIn("pos_version", index)
        self.assertNotIn("pos", index["w"]["nuclear"][0])
        crops = self.root / "crops"
        sentinel = crops / "nce-fixture/frozen.png"
        sentinel.parent.mkdir(parents=True)
        sentinel.write_bytes(b"frozen evidence")
        result = export_regions(draft, crops, dpi=72, books=["junior-9a"])
        self.assertEqual(result["regions"], 2)
        self.assertEqual(sentinel.read_bytes(), b"frozen evidence")
        with self.assertRaisesRegex(ValueError, "outside bundle catalogue"):
            export_regions(draft, crops, books=["junior-9b"])

    def test_incremental_grade9_preserves_baseline_and_draft_pdf_bytes(self):
        work, catalog = self.grade9_replacement()
        baseline_map = json.loads((self.output / "vocab-page-map.json").read_text())
        baseline_pep = json.loads((self.output / "pep-vocab-index.min.json").read_text())
        baseline_files = {p.relative_to(self.output): p.read_bytes() for p in self.output.rglob("*") if p.is_file()}
        draft, output = self.root / "draft", self.root / "new-bundle"
        with patch("vocab_ocr.reference.BOOKS", catalog):
            prepare_grade9_replacement(self.work, work, self.output)
            build_selected_draft(work, draft)
            self.review_grade9_draft(work, draft)
            # No unchanged source PDF is needed for the incremental build.
            (self.root / "senior-fixture.pdf").unlink()
            (self.root / "nce-fixture.pdf").unlink()
            build_bundle(work, output, base_bundle=self.output)
        validate_bundle(output)
        self.assertTrue(all((self.output / name).read_bytes() == data for name, data in baseline_files.items()))
        self.assertEqual((output / "nce-vocab-index.min.json").read_bytes(), baseline_files[Path("nce-vocab-index.min.json")])
        mapped = json.loads((output / "vocab-page-map.json").read_text())
        self.assertNotIn("junior-9", mapped["books"])
        for book_id in ("senior-fixture", "nce-fixture"):
            self.assertEqual(mapped["books"][book_id], baseline_map["books"][book_id])
            relative = mapped["books"][book_id]["file"]
            self.assertEqual((output / relative).read_bytes(), baseline_files[Path(relative)])
        for book_id in ("junior-9a", "junior-9b"):
            relative = mapped["books"][book_id]["file"]
            self.assertEqual((output / relative).read_bytes(), (draft / relative).read_bytes())
        pep = json.loads((output / "pep-vocab-index.min.json").read_text())
        keep = lambda index: {key: hits for key, rows in index["w"].items()
                             if (hits := [h for h in rows if h["book"] == "senior-fixture"])}
        self.assertEqual(keep(pep), keep(baseline_pep))
        self.assertNotIn("obsolete", pep["w"])
        self.assertEqual(pep["pos_version"], 1)

    def test_replacement_rejects_incomplete_wrong_catalogue_or_wrong_baseline(self):
        work, catalog = self.grade9_replacement()
        output = self.root / "new-bundle"
        output.mkdir()
        (output / "keep").write_text("previous package")
        with patch("vocab_ocr.reference.BOOKS", catalog):
            plan = prepare_grade9_replacement(self.work, work, self.output)
            with self.assertRaisesRegex(ValueError, "requires the frozen"):
                build_bundle(work, output)
            with self.assertRaisesRegex(ValueError, "publication blocked"):
                build_bundle(work, output, base_bundle=self.output)
            changed = json.loads(json.dumps(plan))
            changed["books"]["senior-fixture"]["title"] = "wrong catalogue"
            write_json(work / "sources.json", changed)
            with self.assertRaisesRegex(ValueError, "baseline book mismatch"):
                build_bundle(work, output, base_bundle=self.output)
            write_json(work / "sources.json", plan)
            wrong = self.root / "wrong-baseline"
            shutil.copytree(self.output, wrong)
            with (wrong / "manifest.json").open("a") as stream:
                stream.write(" \n")
            with self.assertRaisesRegex(ValueError, "baseline identity mismatch"):
                build_bundle(work, output, base_bundle=wrong)
            (work / "books/junior-9b/pages/094.json").unlink()
            with self.assertRaisesRegex(ValueError, "draft blocked"):
                build_selected_draft(work, self.root / "draft")
        self.assertEqual((output / "keep").read_text(), "previous package")

    def test_new_grade9_unit_boundaries_are_exact_edition_checked(self):
        self.assertEqual(junior_unit("junior-9a", 142, 71), "8")
        self.assertEqual(junior_unit("junior-9b", 108, 41), "5")
        for book_id, count, end in (("junior-9a", 142, 81), ("junior-9b", 108, 51)):
            with self.assertRaises(ValueError):
                junior_unit(book_id, count, end)
            with self.assertRaisesRegex(ValueError, "TOC edition mismatch"):
                junior_unit(book_id, count - 1, 1)

    def test_gloss_provenance_splits_hits_and_rejects_invalid_extensions(self):
        for page in (2, 3):
            path = self.work / f"books/senior-fixture/pages/{page:03d}.json"
            row = json.loads(path.read_text())
            row["entries"][0]["gloss_source"] = {
                "status": "cross-reference", "note": "同书释义恢复",
                "sources": [{"kind": "same-book", "label": "同书对照", "source_pdf_pages": [page]}]}
            if page == 3:
                row["entries"][0]["aliases"] = ["atomic"]
            write_json(path, row)
        build_bundle(self.work, self.output)
        index_path = self.output / "pep-vocab-index.min.json"
        original = json.loads(index_path.read_text())
        self.assertEqual(original["gloss_version"], 1)
        self.assertEqual(len(original["w"]["nuclear"]), 2)
        self.assertEqual(original["w"]["atomic"], [original["w"]["nuclear"][1]])
        for mutate in (lambda d: d.pop("gloss_version"), lambda d: d.update(gloss_version=99),
                       lambda d: d["w"]["nuclear"][0]["gloss_source"]["sources"][0].update(source_pdf_pages=[5])):
            data = json.loads(json.dumps(original))
            mutate(data)
            write_json(index_path, data)
            self.rehash_manifest()
            with self.assertRaisesRegex(ValueError, "gloss"):
                validate_bundle(self.output)
        plan = json.loads((self.work / "sources.json").read_text())
        plan["gloss_version"] = 99
        write_json(self.work / "sources.json", plan)
        with self.assertRaisesRegex(ValueError, "unsupported gloss"):
            build_bundle(self.work, self.output)

    def test_out_of_body_reference_needs_a_confirming_cross_table_occurrence(self):
        work, catalog = self.grade9_replacement()
        path = work / "books/junior-9b/pages/094.json"
        row = json.loads(path.read_text())
        entry = row["entries"][0]
        entry.update(page=55, unit="2", unit_source_pdf_page=95, reference_note="原印p55，另表p11确认Unit 2")
        # The printed Chinese may differ between the two tables.
        entry["zh"] = "原表释义"
        write_json(path, row)
        draft = self.root / "draft"
        build_selected_draft(work, draft, books=["junior-9b"])
        validate_bundle(draft, allow_draft=True)
        index = json.loads((draft / "pep-vocab-index.min.json").read_text())
        hit = next(h for h in index["w"]["nuclear"] if h.get("page") == 55)
        self.assertEqual(hit["unit_source_pdf_page"], 95)
        mapped = json.loads((draft / "vocab-page-map.json").read_text())["books"]["junior-9b"]
        self.assertEqual(mapped["pages"][0]["reference_notes"][0]["body_page"], 55)
        for update in ({"reference_note": ""}, {"unit_source_pdf_page": 108}, {"unit": "3"}):
            bad = json.loads(json.dumps(row))
            bad["entries"][0].update(update)
            write_json(path, bad)
            with self.assertRaisesRegex(ValueError, "draft blocked"):
                build_selected_draft(work, self.root / "bad-draft", books=["junior-9b"])
        bad = json.loads(json.dumps(row))
        del bad["entries"][0]["unit_source_pdf_page"]
        del bad["entries"][0]["reference_note"]
        write_json(path, bad)
        with self.assertRaisesRegex(ValueError, "draft blocked"):
            build_selected_draft(work, self.root / "bad-draft", books=["junior-9b"])

    def reading_pdf_fixture(self, source, pages, destination):
        writer = PdfWriter()
        reader = PdfReader(source)
        for page_number in pages:
            page = writer.add_page(reader.pages[page_number - 1])
            content = DecodedStreamObject()
            content.set_data(b"0 1 0 rg 0 0 20 20 re f")
            page[NameObject("/Contents")] = writer._add_object(content)
        writer.write(destination)

    def test_prepare_reading_binding_is_explicit_repeatable_and_cannot_switch_silently(self):
        work, catalog = self.grade9_replacement()
        reading = self.root / "reading.pdf"
        source = next(b.path for b in catalog if b.id == "junior-9b")
        self.reading_pdf_fixture(source, [94, 95], reading)
        before = (work / "sources.json").read_bytes()
        with patch("vocab_ocr.reference.BOOKS", catalog):
            with self.assertRaisesRegex(ValueError, "reading derivative page count"):
                prepare_grade9_replacement(self.work, work, self.output, reading_pdf=reading)
            self.assertEqual((work / "sources.json").read_bytes(), before)
            self.reading_pdf_fixture(source, list(range(94, 105)), reading)
            plan = prepare_grade9_replacement(self.work, work, self.output, reading_pdf=reading)
            bound = plan["books"]["junior-9b"]["reading_derivative"]
            self.assertEqual(bound["source_pdf_pages"], list(range(94, 105)))
            self.assertEqual(bound["sha256"], sha256(reading))
            self.assertEqual(bound["source_sha256"], sha256(source))
            self.assertEqual(prepare_grade9_replacement(self.work, work, self.output), plan)
            self.assertEqual(prepare_grade9_replacement(self.work, work, self.output, reading_pdf=reading), plan)
            alternate = self.root / "other-reading.pdf"
            shutil.copyfile(reading, alternate)
            with self.assertRaisesRegex(ValueError, "binding changed"):
                prepare_grade9_replacement(self.work, work, self.output, reading_pdf=alternate)

    def test_reading_derivative_is_used_and_wrong_digest_pages_count_are_rejected(self):
        work, catalog = self.grade9_replacement()
        with patch("vocab_ocr.reference.BOOKS", catalog):
            plan = prepare_grade9_replacement(self.work, work, self.output)
            reading = self.root / "reading.pdf"
            source = next(b.path for b in catalog if b.id == "junior-9b")
            self.reading_pdf_fixture(source, [94, 95], reading)
            binding = {"path": str(reading.resolve()), "sha256": sha256(reading), "source_sha256": sha256(source),
                       "source_pdf_pages": [94, 95], "note": "测试阅读衍生文件说明"}
            plan["books"]["junior-9b"]["reading_derivative"] = binding
            write_json(work / "sources.json", plan)
            draft, output = self.root / "draft", self.root / "new-bundle"
            build_selected_draft(work, draft)
            self.review_grade9_draft(work, draft)
            build_bundle(work, output, base_bundle=self.output)
        pdfs = json.loads((output / "pep-vocab-index.min.json").read_text())["pdfs"]
        mapped = json.loads((output / "vocab-page-map.json").read_text())["books"]["junior-9b"]
        self.assertEqual(pdfs["junior-9b"]["pdf_note"], binding["note"])
        self.assertEqual(mapped["pdf_note"], binding["note"])
        self.assertNotIn("path", mapped["reading_derivative"])
        self.assertEqual(mapped["source_sha256"], sha256(source))
        relative = pdfs["junior-9b"]["file"]
        self.assertEqual((output / relative).read_bytes(), (draft / relative).read_bytes())
        self.assertEqual(PdfReader(output / relative).pages[0].get_contents().get_data(),
                         PdfReader(reading).pages[0].get_contents().get_data())
        for change, message in (({"sha256": "0" * 64}, "file digest"),
                                ({"source_sha256": "0" * 64}, "source/page binding"),
                                ({"source_pdf_pages": [95, 94]}, "source/page binding"),
                                ({"source_pdf_pages": [94, 96]}, "source/page binding")):
            bad = json.loads(json.dumps(plan))
            bad["books"]["junior-9b"]["reading_derivative"].update(change)
            write_json(work / "sources.json", bad)
            with self.assertRaisesRegex(ValueError, message):
                build_selected_draft(work, self.root / "bad-draft")
        self.reading_pdf_fixture(source, [94, 95, 96], reading)
        plan["books"]["junior-9b"]["reading_derivative"]["sha256"] = sha256(reading)
        write_json(work / "sources.json", plan)
        with self.assertRaisesRegex(ValueError, "page count"):
            build_selected_draft(work, self.root / "bad-draft")

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
