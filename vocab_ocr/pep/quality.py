"""Fail-closed quality checks for the PEP visual vocabulary index.

These checks catch structural omissions and suspicious transcription. They cannot
prove that a visual model read a page correctly; publication also requires a
separate, source-PDF-verified review of the fixed and independent samples.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from vocab_ocr.pep.catalog import BOOKS
from vocab_ocr.shared.build_index import clean_zh, norm_lemma


# Deliberately conservative lower bounds from the earlier 12-book extraction.
# They detect catastrophic loss only; the old OCR is not a correctness oracle.
MIN_BOOK_ENTRIES = {
    "junior-7a": 400, "junior-7b": 400, "junior-8a": 450,
    "junior-8b": 450, "junior-9": 500,
    "senior-compulsory-1": 140, "senior-compulsory-2": 140,
    "senior-compulsory-3": 150, "senior-optional-1": 140,
    "senior-optional-2": 140, "senior-optional-3": 120,
    "senior-optional-4": 120,
}
EXPECTED_BOOK_IDS = tuple(b.id for b in BOOKS)
_CJK = re.compile(r"[\u3400-\u9fff]")
_REFERENCE_IN_GLOSS = re.compile(r"(?:\bp\s*[.．]?\s*\d{1,3}\b|[（(]\s*\d{1,2}\s*[)）])", re.I)
_POS_IN_GLOSS = re.compile(r"\b(?:n|v|vt|vi|adj|adv|prep|pron|conj|art|num)\s*\.\s+[A-Za-z]", re.I)
_ALLOWED_STATUS = {"ok", "error"}
_ALLOWED_COLUMNS = {"left", "right"}
_VALID_REVIEW = {"yes", "na"}
_KNOWN_BAD_HEADS = {
    "bicycle bike welcome", "disappointed role", "hide hid hidden interviewer",
    "ring rang rung berlin", "eighbourhood us eighborhood piano",
    "ba' ju'mn", "air conditioner assessment", "picasso rely i",
    "barbecue abbr bbq chiang mai",
}


@dataclass(frozen=True)
class QualityIssue:
    code: str
    detail: str
    book_id: str = ""
    pdf_page: int | None = None
    word: str = ""


@dataclass
class QualityReport:
    issues: list[QualityIssue]
    checked_books: int = 0
    checked_pages: int = 0
    checked_entries: int = 0
    checked_reviews: int = 0

    @property
    def ok(self) -> bool:
        return not self.issues

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "checked_books": self.checked_books,
            "checked_pages": self.checked_pages,
            "checked_entries": self.checked_entries,
            "checked_reviews": self.checked_reviews,
            "issues": [asdict(issue) for issue in self.issues],
        }


class QualityError(ValueError):
    """A candidate index failed its publication gate."""


def require_quality(report: QualityReport) -> None:
    if not report.ok:
        first = report.issues[0]
        raise QualityError(
            f"PEP index quality gate failed ({len(report.issues)} issues): "
            f"{first.book_id} {first.pdf_page or ''} {first.code}: {first.detail}"
        )


def _issue(issues: list[QualityIssue], code: str, detail: str,
           book_id: str = "", pdf_page: int | None = None,
           word: str = "") -> None:
    issues.append(QualityIssue(code, detail, book_id, pdf_page, word))


def _entry_identity(entry: dict) -> tuple:
    """Identity of a page transcription, excluding optional model diagnostics."""
    return (
        entry.get("word"), entry.get("zh"), entry.get("unit"),
        entry.get("page"), entry.get("pdf_page"), entry.get("column"),
    )


def _valid_units(book: dict) -> set[str]:
    stage = book.get("stage")
    if stage == "senior":
        return {"w", "1", "2", "3", "4", "5"}
    starts = book.get("unit_starts") or []
    return {str(item.get("unit")) for item in starts if isinstance(item, dict)}


def _normalized_gloss(value: str) -> str:
    """Ignore presentation punctuation/spacing, retaining all meaning-bearing text."""
    value = unicodedata.normalize("NFKC", value).casefold()
    return "".join(c for c in value if c.isalnum())


def validate_anchors(book: dict, anchors: Sequence[dict]) -> QualityReport:
    """Match PDF-verified source anchors against visual entries.

    A candidate gloss may contain the complete normalized anchor gloss, but may
    not also contain another anchor's gloss from the same PDF page. This catches
    the known assessment/assumption spill while allowing punctuation variants.
    """
    issues: list[QualityIssue] = []
    book_id = str(book.get("book_id") or "")
    entries = book.get("entries") or []
    for anchor in anchors:
        word = str(anchor.get("word") or "")
        pdf_page = anchor.get("pdf_page")
        unit = str(anchor.get("unit") or "")
        expected_zh = _normalized_gloss(str(anchor.get("zh") or ""))
        if not word or not isinstance(pdf_page, int) or not unit or not expected_zh:
            _issue(issues, "anchor_invalid", "source anchor needs word, PDF page, Unit and gloss", book_id, pdf_page, word)
            continue
        matches = [e for e in entries if isinstance(e, dict) and
                   str(e.get("word") or "").casefold() == word.casefold() and
                   e.get("pdf_page") == pdf_page]
        if len(matches) != 1:
            _issue(issues, "anchor_word_mismatch", f"expected one match; found {len(matches)}", book_id, pdf_page, word)
            continue
        entry = matches[0]
        if str(entry.get("unit") or "") != unit:
            _issue(issues, "anchor_unit_mismatch", f"source Unit {unit}, candidate {entry.get('unit')!r}", book_id, pdf_page, word)
        if entry.get("page") != anchor.get("page"):
            _issue(issues, "anchor_page_mismatch", f"source p. {anchor.get('page')}, candidate {entry.get('page')!r}", book_id, pdf_page, word)
        actual_zh = _normalized_gloss(str(entry.get("zh") or ""))
        if expected_zh not in actual_zh:
            _issue(issues, "anchor_gloss_mismatch", f"source gloss {anchor.get('zh')!r} missing", book_id, pdf_page, word)
        for other in anchors:
            if other is anchor or other.get("pdf_page") != pdf_page:
                continue
            other_zh = _normalized_gloss(str(other.get("zh") or ""))
            if len(other_zh) >= 2 and other_zh in actual_zh and other_zh not in expected_zh:
                _issue(issues, "anchor_gloss_spill", f"gloss also contains {other.get('word')}'s gloss", book_id, pdf_page, word)
    return QualityReport(issues, checked_reviews=len(anchors))


def _unit_for_printed_page(book: dict, page: int) -> str | None:
    starts = book.get("unit_starts") or []
    ordered = sorted(
        ((int(item["start_page"]), str(item["unit"])) for item in starts
         if isinstance(item, dict) and str(item.get("start_page", "")).isdigit()),
    )
    unit = None
    for first, name in ordered:
        if page < first:
            break
        unit = name
    return unit


def validate_book(
    book: dict,
    *,
    min_entries: int | None = None,
    min_page_entries: int = 8,
) -> QualityReport:
    """Check one complete visual transcription before it can be indexed.

    ``page_results`` must cover every PDF page in ``vocab_pdf_pages``. An empty
    page needs an explicit ``kind='non_vocab'`` and explanation. Book ``entries``
    must exactly mirror page results, preserving all entries rather than silently
    filtering bad ones before validation.
    """
    issues: list[QualityIssue] = []
    book_id = str(book.get("book_id") or "")
    stage = book.get("stage")
    if not book_id:
        _issue(issues, "book_id_missing", "book_id is required")
    if stage not in {"junior", "senior"}:
        _issue(issues, "stage_invalid", f"unknown stage {stage!r}", book_id)
    pdf_pages = book.get("pdf_pages")
    span = book.get("vocab_pdf_pages")
    if not isinstance(pdf_pages, int) or pdf_pages < 1:
        _issue(issues, "pdf_pages_invalid", "positive PDF page count required", book_id)
    if (not isinstance(span, list) or len(span) != 2 or
            any(not isinstance(n, int) for n in span) or
            span[0] < 1 or span[0] > span[1] or
            (isinstance(pdf_pages, int) and span[1] > pdf_pages)):
        _issue(issues, "vocab_span_invalid", "valid inclusive PDF page range required", book_id)
        expected_pages: set[int] = set()
    else:
        expected_pages = set(range(span[0], span[1] + 1))

    entries = book.get("entries")
    if not isinstance(entries, list):
        _issue(issues, "entries_missing", "entries must be a list", book_id)
        entries = []
    floor = min_entries if min_entries is not None else MIN_BOOK_ENTRIES.get(book_id)
    if floor is None:
        _issue(issues, "entry_floor_missing", "set a reviewed minimum entry count", book_id)
    elif len(entries) < floor:
        _issue(issues, "entry_count_low", f"{len(entries)} entries below floor {floor}", book_id)
    if book.get("entry_count") != len(entries):
        _issue(issues, "entry_count_mismatch", "entry_count differs from entries length", book_id)
    provenance = {key: book.get(key) for key in
                  ("pdf_sha256", "model", "prompt_sha256", "dpi")}
    if (not isinstance(provenance["pdf_sha256"], str) or
            not re.fullmatch(r"[0-9a-f]{64}", provenance["pdf_sha256"])):
        _issue(issues, "pdf_digest_missing", "book needs a SHA-256 PDF digest", book_id)
    if not isinstance(provenance["model"], str) or not provenance["model"]:
        _issue(issues, "model_missing", "book needs model identity", book_id)
    if (not isinstance(provenance["prompt_sha256"], str) or
            not re.fullmatch(r"[0-9a-f]{64}", provenance["prompt_sha256"])):
        _issue(issues, "prompt_digest_missing", "book needs a SHA-256 prompt digest", book_id)
    if not isinstance(provenance["dpi"], int) or provenance["dpi"] < 100:
        _issue(issues, "dpi_invalid", "book needs rendering DPI >= 100", book_id)

    page_results = book.get("page_results")
    if not isinstance(page_results, list):
        _issue(issues, "page_results_missing", "every PDF page needs a result", book_id)
        page_results = []
    page_numbers = [r.get("pdf_page") for r in page_results if isinstance(r, dict)]
    count = Counter(page_numbers)
    for page in sorted(expected_pages - set(page_numbers)):
        _issue(issues, "page_missing", "no page result", book_id, page)
    for page, copies in count.items():
        if copies > 1:
            _issue(issues, "page_duplicate", f"{copies} page results", book_id, page)
        if page not in expected_pages:
            _issue(issues, "page_outside_span", "page result outside vocabulary span", book_id, page)
    flattened: list[dict] = []
    for result in page_results:
        if not isinstance(result, dict):
            _issue(issues, "page_result_invalid", "page result must be an object", book_id)
            continue
        page = result.get("pdf_page")
        status = result.get("status")
        kind = result.get("kind")
        page_entries = result.get("entries")
        for key, expected in provenance.items():
            if result.get(key) != expected or expected is None:
                _issue(issues, "page_provenance_mismatch", f"{key} differs from book metadata", book_id, page)
        if result.get("uncertainty"):
            _issue(issues, "page_uncertain", "resolve all page uncertainty against the PDF", book_id, page)
        if not isinstance(result.get("uncertainty"), list):
            _issue(issues, "page_uncertainty_missing", "page must record uncertainty list", book_id, page)
        if status == "ok" and not str(result.get("raw_response") or "").strip():
            _issue(issues, "page_response_missing", "keep the model's complete page response", book_id, page)
        if status not in _ALLOWED_STATUS or status != "ok":
            _issue(issues, "page_failed", f"status={status!r}: {result.get('error', '')}", book_id, page)
        if not isinstance(page_entries, list):
            _issue(issues, "page_entries_missing", "page entries must be a list", book_id, page)
            continue
        flattened.extend(e for e in page_entries if isinstance(e, dict))
        if kind == "vocab":
            if len(page_entries) < min_page_entries:
                _issue(issues, "page_entries_low", f"{len(page_entries)} entries", book_id, page)
        elif kind == "non_vocab":
            if page_entries or not str(result.get("reason") or "").strip():
                _issue(issues, "non_vocab_unjustified", "empty page needs reason; non-vocab page cannot have entries", book_id, page)
        else:
            _issue(issues, "page_kind_invalid", "kind must be vocab or non_vocab", book_id, page)
        for entry in page_entries:
            if not isinstance(entry, dict) or entry.get("pdf_page") != page:
                _issue(issues, "entry_page_mismatch", "entry must carry its source PDF page", book_id, page)
    if Counter(map(_entry_identity, (e for e in entries if isinstance(e, dict)))) != Counter(map(_entry_identity, flattened)):
        _issue(issues, "flatten_mismatch", "book entries differ from per-page transcription", book_id)

    valid_units = _valid_units(book)
    if stage == "junior" and not valid_units:
        _issue(issues, "unit_map_missing", "junior printed-page unit map required", book_id)
    seen: set[tuple] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            _issue(issues, "entry_invalid", "entry must be an object", book_id)
            continue
        word = str(entry.get("word") or "").strip()
        page = entry.get("pdf_page")
        unit = str(entry.get("unit") or "")
        printed = entry.get("page")
        gloss = str(entry.get("zh") or "").strip()
        if entry.get("book_id") not in {None, book_id}:
            _issue(issues, "entry_book_mismatch", "entry belongs to another book", book_id, page, word)
        if page not in expected_pages:
            _issue(issues, "entry_page_invalid", "entry PDF page outside range", book_id, page, word)
        if entry.get("column") not in _ALLOWED_COLUMNS:
            _issue(issues, "column_missing", "left/right source column required", book_id, page, word)
        lemma = norm_lemma(word)
        if lemma is None or lemma != re.sub(r"\s+", " ", word.lower().strip()):
            _issue(issues, "word_suspicious", "word would be discarded or changed by index normalization", book_id, page, word)
        if re.sub(r"\s+", " ", word.casefold()) in _KNOWN_BAD_HEADS:
            _issue(issues, "known_bad_head", "#04 crossed-column OCR head survived", book_id, page, word)
        if not gloss or not _CJK.search(gloss) or not clean_zh(gloss):
            _issue(issues, "gloss_empty", "Chinese gloss required", book_id, page, word)
        elif _REFERENCE_IN_GLOSS.search(gloss) or _POS_IN_GLOSS.search(gloss):
            _issue(issues, "gloss_polluted", "another entry's reference/POS may be in the gloss", book_id, page, word)
        elif _normalized_gloss(clean_zh(gloss)) != _normalized_gloss(gloss):
            _issue(issues, "gloss_rewritten", "index cleanup would silently drop gloss content", book_id, page, word)
        if entry.get("uncertainty"):
            _issue(issues, "entry_uncertain", "resolve entry uncertainty against the PDF", book_id, page, word)
        if not isinstance(entry.get("uncertainty"), list):
            _issue(issues, "entry_uncertainty_missing", "entry must record uncertainty list", book_id, page, word)
        if not str(entry.get("raw") or "").strip() or not str(entry.get("ref") or "").strip():
            _issue(issues, "entry_source_missing", "entry needs raw source line and printed reference", book_id, page, word)
        if not valid_units or unit not in valid_units:
            _issue(issues, "unit_invalid", f"unit {unit!r} not in this book", book_id, page, word)
        if stage == "junior":
            if not isinstance(printed, int) or printed < 1 or (isinstance(pdf_pages, int) and printed > pdf_pages):
                _issue(issues, "printed_page_invalid", "junior p. reference must be a plausible positive page", book_id, page, word)
            elif valid_units and _unit_for_printed_page(book, printed) != unit:
                _issue(issues, "unit_page_conflict", "Unit disagrees with the printed-page map", book_id, page, word)
        elif printed is not None:
            _issue(issues, "senior_page_invalid", "senior parentheses denote Unit, not a page", book_id, page, word)
        key = (lemma, page, unit, printed)
        if key in seen:
            _issue(issues, "entry_duplicate", "same word/reference repeated on one PDF page", book_id, page, word)
        seen.add(key)

    return QualityReport(issues, checked_books=1, checked_pages=len(page_results), checked_entries=len(entries))


def validate_corpus(
    books: Sequence[dict],
    *,
    expected_book_ids: Sequence[str] = EXPECTED_BOOK_IDS,
    min_entries_by_book: Mapping[str, int] | None = None,
    anchors_by_book: Mapping[str, Sequence[dict]] | None = None,
    min_anchors_per_book: int = 1,
    min_page_entries: int = 8,
) -> QualityReport:
    issues: list[QualityIssue] = []
    actual = [str(book.get("book_id") or "") for book in books]
    for book_id in sorted(set(expected_book_ids) - set(actual)):
        _issue(issues, "book_missing", "catalog book missing", book_id)
    for book_id in sorted(set(actual) - set(expected_book_ids)):
        _issue(issues, "book_unexpected", "book outside publication corpus", book_id)
    for book_id, copies in Counter(actual).items():
        if copies > 1:
            _issue(issues, "book_duplicate", f"{copies} book results", book_id)
    report = QualityReport(issues)
    for book in books:
        one = validate_book(
            book, min_entries=(min_entries_by_book or {}).get(book.get("book_id")),
            min_page_entries=min_page_entries,
        )
        report.issues.extend(one.issues)
        report.checked_books += one.checked_books
        report.checked_pages += one.checked_pages
        report.checked_entries += one.checked_entries
        anchors = (anchors_by_book or {}).get(str(book.get("book_id") or ""), ())
        if len(anchors) < min_anchors_per_book:
            _issue(report.issues, "anchors_missing", f"need {min_anchors_per_book} PDF-verified source anchors", str(book.get("book_id") or ""))
        checked = validate_anchors(book, anchors)
        report.issues.extend(checked.issues)
        report.checked_reviews += checked.checked_reviews
    return report


def read_review_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def _review_key(row: Mapping[str, str]) -> tuple[str, str, str, str]:
    return tuple(str(row.get(key) or "").strip() for key in
                 ("book_id", "kind", "lemma", "source_pdf_page"))


def validate_review_rows(
    books: Sequence[dict],
    *,
    seed_rows: Sequence[Mapping[str, str]],
    review_rows: Sequence[Mapping[str, str]],
    min_independent_per_book: int = 1,
) -> QualityReport:
    """Gate publication on PDF-verified fixed and new independent samples.

    The fixed rows retain their #04 CSV key (book_id, kind, original lemma,
    source_pdf_page). Review rows add sample_set=fixed|independent,
    current_word/unit/page/zh, disposition=indexed|excluded, and four *_ok
    judgements. An excluded source fragment requires a written reason.
    """
    issues: list[QualityIssue] = []
    seed_keys = Counter(_review_key(row) for row in seed_rows)
    if len(seed_rows) != 60 or any(copies != 1 for copies in seed_keys.values()):
        _issue(issues, "seed_set_invalid", "#04 fixed sample must contain 60 unique rows")
    fixed = [r for r in review_rows if r.get("sample_set") == "fixed"]
    independent = [r for r in review_rows if r.get("sample_set") == "independent"]
    fixed_keys = Counter(_review_key(row) for row in fixed)
    for key in seed_keys.keys() - fixed_keys.keys():
        _issue(issues, "fixed_review_missing", f"unreviewed #04 row {key}", key[0])
    for key in fixed_keys.keys() - seed_keys.keys():
        _issue(issues, "fixed_review_unexpected", f"row not in #04 seed {key}", key[0])
    for key, copies in fixed_keys.items():
        if copies > 1:
            _issue(issues, "review_duplicate", f"{copies} reviews for {key}", key[0])
    indexed_positions = Counter(
        (str(r.get("book_id") or ""), str(r.get("source_pdf_page") or ""),
         str(r.get("current_word") or "").casefold())
        for r in fixed if r.get("disposition") == "indexed"
    )
    for (book_id, pdf_page, word), copies in indexed_positions.items():
        if copies > 1:
            _issue(issues, "review_candidate_duplicate", f"{copies} fixed samples map to one current entry", book_id,
                   int(pdf_page) if pdf_page.isdigit() else None, word)
    books_by_id = {str(b.get("book_id")): b for b in books}
    independent_count = Counter(str(r.get("book_id")) for r in independent)
    for book_id in books_by_id:
        if independent_count[book_id] < min_independent_per_book:
            _issue(issues, "independent_review_missing", f"need {min_independent_per_book} new samples", book_id)
    for row in review_rows:
        book_id = str(row.get("book_id") or "")
        source_page_raw = str(row.get("source_pdf_page") or "")
        source_page = int(source_page_raw) if source_page_raw.isdigit() else None
        if row.get("sample_set") not in {"fixed", "independent"}:
            _issue(issues, "review_set_invalid", "sample_set must be fixed or independent", book_id, source_page)
        if source_page is None:
            _issue(issues, "review_source_missing", "source PDF page required", book_id)
        book = books_by_id.get(book_id)
        if book is None:
            _issue(issues, "review_book_missing", "review book not in corpus", book_id, source_page)
            continue
        judgement = {field: str(row.get(field) or "").strip().lower() for field in
                     ("word_ok", "zh_ok", "unit_ok", "page_ok")}
        if any(value not in _VALID_REVIEW for value in judgement.values()):
            _issue(issues, "review_incomplete", f"four judgements need yes/na: {judgement}", book_id, source_page)
        disposition = row.get("disposition")
        candidates = [e for e in book.get("entries", []) if isinstance(e, dict) and
                      e.get("pdf_page") == source_page and
                      e.get("word") == row.get("current_word")]
        if disposition == "indexed":
            if judgement["word_ok"] != "yes" or judgement["zh_ok"] != "yes" or judgement["unit_ok"] != "yes":
                _issue(issues, "review_rejected", "indexed word/gloss/Unit require yes", book_id, source_page)
            expected_page_ok = "yes" if book.get("stage") == "junior" else "na"
            if judgement["page_ok"] != expected_page_ok:
                _issue(issues, "review_page_invalid", f"page_ok must be {expected_page_ok}", book_id, source_page)
            if len(candidates) != 1 or any(
                str(candidates[0].get(field) if candidates else "") != str(row.get(review_field) or "")
                for field, review_field in (("unit", "current_unit"), ("zh", "current_zh"))
            ) or (candidates and str(candidates[0].get("page") or "") != str(row.get("current_page") or "")):
                _issue(issues, "review_candidate_mismatch", "review does not match exactly one current visual entry", book_id, source_page)
        elif disposition == "excluded":
            if not str(row.get("exclusion_reason") or "").strip() or any(v != "na" for v in judgement.values()):
                _issue(issues, "exclusion_unjustified", "excluded fragment needs reason and four na", book_id, source_page)
            old_lemma = norm_lemma(str(row.get("lemma") or ""))
            source_matches = [e for e in book.get("entries", []) if isinstance(e, dict) and
                              e.get("pdf_page") == source_page and
                              old_lemma and norm_lemma(str(e.get("word") or "")) == old_lemma]
            if candidates or source_matches:
                _issue(issues, "excluded_still_indexed", "excluded fragment is still in current entries", book_id, source_page)
        else:
            _issue(issues, "disposition_missing", "indexed/excluded disposition required", book_id, source_page)
    return QualityReport(issues, checked_reviews=len(review_rows))
