"""Locate PEP vocabulary appendix pages from the front-matter Contents."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from vocab_ocr.shared.pdf_render import (
    pdf_page_count,
    pdf_page_from_render_name,
    render_pages,
)
from vocab_ocr.shared.tesseract_ocr import ocr_image

# Contents lines that point at the word-list appendix (printed page).
TOC_VOCAB_RE = re.compile(
    r"(?:Words\s+and\s+Expressions(?:\s+in\s+Each\s+Unit)?|"
    r"Vocabulary(?:\s+in\s+Each\s+Unit)?|"
    r"词\s*汇\s*表|"
    r"本册生词)\s*[.\s]*p\.?\s*(\d{1,3})\b",
    re.I,
)

# Later appendix sections — help bound the end of the word list.
TOC_AFTER_VOCAB_RE = re.compile(
    r"(?:Irregular\s+Verbs|Proper\s+Names|Grammar|语法|"
    r"Listening\s+Scripts)\s*[.\s]*p\.?\s*(\d{1,3})\b",
    re.I,
)

VOCAB_HEADER_RE = re.compile(
    r"Vocabulary\s*A\s*[-–—]?\s*Z|"
    r"\bVocabulary\b|"
    r"Words\s+and\s+Expressions\s+in\s+Each\s+Unit|"
    r"词\s*汇\s*表|"
    r"本册生词",
    re.I,
)

ENTRY_MARKER_RE = re.compile(r"\bp\.?\s*\d{1,3}\b|\(([1-9]|1[0-9]|w)\)", re.I)
NOTES_RE = re.compile(r"^\s*Notes\b", re.I | re.M)


@dataclass
class VocabLocateResult:
    """Inclusive 1-based PDF page range for the vocabulary appendix."""

    start_pdf: int
    end_pdf: int
    printed_start: int | None
    method: str  # toc | toc+scan | densify_fallback
    toc_text: str


def ocr_front_toc(
    pdf: Path,
    work_dir: Path,
    *,
    last_page: int = 12,
    dpi: int = 150,
) -> str:
    """OCR early pages that normally hold the Contents."""
    n = pdf_page_count(pdf)
    last = min(last_page, n)
    toc_dir = work_dir / "toc"
    imgs = render_pages(pdf, toc_dir, "toc", 1, last, dpi=dpi)
    parts: list[str] = []
    for img in imgs:
        parts.append(ocr_image(img, lang="eng+chi_sim", psm=6))
    text = "\n".join(parts)
    (work_dir / "ocr_toc.txt").write_text(text, encoding="utf-8")
    return text


def parse_toc_vocab_printed_pages(toc_text: str) -> tuple[int | None, int | None]:
    """Return (vocab_printed_start, optional_printed_end_exclusive_hint)."""
    starts: list[int] = []
    after: list[int] = []
    for line in toc_text.splitlines():
        m = TOC_VOCAB_RE.search(line)
        if m:
            starts.append(int(m.group(1)))
        m2 = TOC_AFTER_VOCAB_RE.search(line)
        if m2:
            after.append(int(m2.group(1)))
    printed_start = min(starts) if starts else None
    # End hint: first "after" section page after vocab start, else None.
    end_hint = None
    if printed_start is not None and after:
        later = [p for p in after if p > printed_start]
        if later:
            end_hint = min(later)
    return printed_start, end_hint


def _page_score(text: str) -> int:
    if NOTES_RE.search(text) and len(ENTRY_MARKER_RE.findall(text)) < 8:
        return 0
    score = len(ENTRY_MARKER_RE.findall(text))
    if VOCAB_HEADER_RE.search(text):
        score += 20
    return score


def _scan_pdf_for_vocab_band(
    pdf: Path,
    work_dir: Path,
    *,
    probe_first: int,
    probe_last: int,
    dpi: int = 120,
    prefer_near_printed: int | None = None,
) -> tuple[int, int] | None:
    """OCR a PDF page window and pick a contiguous high-density vocab band."""
    probe_dir = work_dir / "locate_probe"
    ocr_dir = work_dir / "ocr_locate"
    ocr_dir.mkdir(parents=True, exist_ok=True)
    imgs = render_pages(
        pdf, probe_dir, "locate", probe_first, probe_last, dpi=dpi, clear_prefix=True
    )
    scores: dict[int, int] = {}
    for img in imgs:
        page = pdf_page_from_render_name(img)
        if page is None:
            continue
        text = ocr_image(img, lang="eng+chi_sim", psm=6)
        (ocr_dir / f"{page:03d}.txt").write_text(text, encoding="utf-8")
        scores[page] = _page_score(text)

    strong = [p for p, s in scores.items() if s >= 18]
    if not strong:
        strong = [p for p, s in scores.items() if s >= 12]
    if not strong:
        return None

    if prefer_near_printed is not None:
        # Prefer the strong page closest to printed+offset guess window start.
        start = min(strong, key=lambda p: abs(p - prefer_near_printed))
    else:
        start = min(strong)
    end = start
    page = start + 1
    while page in scores and scores[page] >= 10:
        end = page
        page += 1
        if end - start > 40:
            break
    return start, end


def locate_vocab_pages(pdf: Path, work_dir: Path) -> VocabLocateResult:
    """Primary path: Contents → printed page → scan nearby PDF pages.

    Fallback: density scan of the last ~25% of the PDF (legacy behaviour),
    only when the TOC does not name a vocabulary page.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    n = pdf_page_count(pdf)
    toc_text = ocr_front_toc(pdf, work_dir)
    printed_start, printed_end_hint = parse_toc_vocab_printed_pages(toc_text)

    if printed_start is not None:
        # Front matter usually adds some PDF pages before printed p.1.
        # Search a window starting a bit before the printed number.
        window_first = max(1, printed_start - 5)
        window_last = min(n, (printed_end_hint or printed_start) + 35)
        # Also include the true book tail in case printed→PDF offset is large.
        window_last = max(window_last, min(n, printed_start + 50))
        band = _scan_pdf_for_vocab_band(
            pdf,
            work_dir,
            probe_first=window_first,
            probe_last=window_last,
            prefer_near_printed=printed_start + 8,
        )
        if band:
            start, end = band
            if printed_end_hint:
                # Soft clamp using TOC next-section printed page + cushion.
                end = min(end, start + max(8, printed_end_hint - printed_start + 6))
            return VocabLocateResult(
                start_pdf=start,
                end_pdf=end,
                printed_start=printed_start,
                method="toc+scan",
                toc_text=toc_text,
            )

    # Fallback: last quarter only (not a blind whole-book crawl).
    probe_first = max(1, n - max(20, n // 4) + 1)
    band = _scan_pdf_for_vocab_band(
        pdf, work_dir, probe_first=probe_first, probe_last=n
    )
    if band:
        start, end = band
        return VocabLocateResult(
            start_pdf=start,
            end_pdf=end,
            printed_start=None,
            method="densify_fallback",
            toc_text=toc_text,
        )

    return VocabLocateResult(
        start_pdf=probe_first,
        end_pdf=n,
        printed_start=None,
        method="densify_fallback",
        toc_text=toc_text,
    )
