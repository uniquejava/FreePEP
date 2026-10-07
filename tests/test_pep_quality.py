"""Publication gates for the image-based PEP vocabulary transcription."""

from __future__ import annotations

import copy

from vocab_ocr.pep.quality import (
    require_quality,
    validate_anchors,
    validate_book,
    validate_corpus,
    validate_review_rows,
    QualityError,
)


def _book() -> dict:
    provenance = {"pdf_sha256": "a" * 64, "prompt_sha256": "b" * 64,
                  "model": "fixture", "dpi": 200}
    entries = [
        {"word": "assessment", "zh": "评价；评定", "unit": "4", "page": None,
         "pdf_page": 120, "column": "right", "book_id": "senior-optional-1",
         "uncertainty": [], "raw": "assessment 评价；评定 (4)", "ref": "(4)"},
        {"word": "assumption", "zh": "假定；设定", "unit": "5", "page": None,
         "pdf_page": 120, "column": "right", "book_id": "senior-optional-1",
         "uncertainty": [], "raw": "assumption 假定；设定 (5)", "ref": "(5)"},
    ]
    return {
        "book_id": "senior-optional-1", "stage": "senior", "pdf_pages": 130,
        **provenance,
        "vocab_pdf_pages": [120, 121], "entry_count": len(entries),
        "entries": entries,
        "page_results": [
            {"pdf_page": 120, "kind": "vocab", "status": "ok", "entries": copy.deepcopy(entries),
             "uncertainty": [], "raw_response": "complete JSON page", **provenance},
            {"pdf_page": 121, "kind": "non_vocab", "status": "ok", "reason": "Index ends", "entries": [],
             "uncertainty": [], "raw_response": "complete JSON page", **provenance},
        ],
    }


def _anchors() -> list[dict]:
    return [
        {"word": "assessment", "pdf_page": 120, "unit": "4", "zh": "评价；评定"},
        {"word": "assumption", "pdf_page": 120, "unit": "5", "zh": "假定；设定"},
    ]


def _codes(report) -> set[str]:
    return {issue.code for issue in report.issues}


def test_complete_book_and_normalized_anchor_gloss_pass():
    book = _book()
    assert validate_book(book, min_entries=2, min_page_entries=1).ok
    assert validate_anchors(book, _anchors()).ok
    # Presentation punctuation changes do not invalidate a checked definition.
    book["entries"][0]["zh"] = "评价, 评定"
    assert validate_anchors(book, _anchors()).ok


def test_failed_or_missing_page_cannot_reach_index():
    book = _book()
    book["page_results"].pop()
    report = validate_book(book, min_entries=2, min_page_entries=1)
    assert "page_missing" in _codes(report)
    try:
        require_quality(report)
    except QualityError:
        pass
    else:
        raise AssertionError("invalid book passed publication gate")
    book = _book()
    book["page_results"][0]["status"] = "error"
    assert "page_failed" in _codes(validate_book(book, min_entries=2, min_page_entries=1))


def test_uncertainty_or_mixed_cache_provenance_blocks_publication():
    book = _book()
    book["page_results"][0]["uncertainty"] = ["bottom line may be missing"]
    book["entries"][0]["uncertainty"] = ["Unit blurry"]
    book["page_results"][1]["prompt_sha256"] = "c" * 64
    codes = _codes(validate_book(book, min_entries=2, min_page_entries=1))
    assert {"page_uncertain", "entry_uncertain", "page_provenance_mismatch"} <= codes


def test_index_cleanup_cannot_silently_truncate_gloss():
    book = _book()
    book["entries"][0]["zh"] = "评价；评定 consume v. 消耗"
    assert "gloss_rewritten" in _codes(validate_book(book, min_entries=2, min_page_entries=1))


def test_known_cross_column_head_and_thin_vocab_page_are_rejected():
    book = _book()
    book["entries"][0]["word"] = "air conditioner assessment"
    codes = _codes(validate_book(book, min_entries=2))
    assert "known_bad_head" in codes
    assert "page_entries_low" in codes


def test_assessment_unit_and_neighbor_gloss_spill_fail_source_anchors():
    book = _book()
    book["entries"][0]["unit"] = "5"
    book["entries"][0]["zh"] = "评价；评定；假定；设定"
    codes = _codes(validate_anchors(book, _anchors()))
    assert "anchor_unit_mismatch" in codes
    assert "anchor_gloss_spill" in codes


def test_corpus_requires_pdf_verified_anchor_for_every_book():
    book = _book()
    report = validate_corpus([book], expected_book_ids=[book["book_id"]],
                             min_entries_by_book={book["book_id"]: 2}, min_page_entries=1)
    assert "anchors_missing" in _codes(report)
    report = validate_corpus([book], expected_book_ids=[book["book_id"]],
                             min_entries_by_book={book["book_id"]: 2},
                             anchors_by_book={book["book_id"]: _anchors()}, min_page_entries=1)
    assert report.ok


def test_fixed_60_and_new_source_reviews_are_required():
    book = _book()
    seeds = [
        {"book_id": book["book_id"], "kind": "random", "lemma": f"old-{i}",
         "source_pdf_page": "120"} for i in range(60)
    ]
    report = validate_review_rows([book], seed_rows=seeds, review_rows=[])
    assert "fixed_review_missing" in _codes(report)
    assert "independent_review_missing" in _codes(report)

    reviews = [
        {**seed, "sample_set": "fixed", "disposition": "excluded",
         "current_word": "", "current_unit": "", "current_page": "",
         "current_zh": "", "word_ok": "na", "zh_ok": "na",
         "unit_ok": "na", "page_ok": "na", "exclusion_reason": "No source entry"}
        for seed in seeds
    ]
    indexed = {**reviews[0], "disposition": "indexed", "current_word": "assessment",
               "current_unit": "4", "current_zh": "评价；评定", "word_ok": "yes",
               "zh_ok": "yes", "unit_ok": "yes", "exclusion_reason": ""}
    reviews[0] = indexed
    reviews.append({**indexed, "sample_set": "independent", "kind": "new"})
    assert validate_review_rows([book], seed_rows=seeds, review_rows=reviews).ok
    reviews[0]["current_unit"] = "5"
    assert "review_candidate_mismatch" in _codes(
        validate_review_rows([book], seed_rows=seeds, review_rows=reviews)
    )
