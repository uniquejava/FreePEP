"""Parse OCR text from PEP English vocabulary appendix pages."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

UNIT_HEADER_RE = re.compile(
    r"^\s*(?:Unit|UNIT)\s*(\d+)\b|"
    r"^\s*(?:Welcome\s+Unit|预备单元)\b|"
    r"^\s*(?:Words\s+and\s+Expressions\s+in\s+Each\s+Unit)\b",
    re.I,
)

SECTION_AZ_RE = re.compile(
    r"Vocabulary\s*A\s*[-–—]?\s*Z|"
    r"Appendices|"
    r"词\s*汇\s*表|"
    r"Words\s+and\s+Expressions",
    re.I,
)

JUNIOR_PAGE_RE = re.compile(
    r"^(?P<head>.+?)\s+p[.．]?\s*(?P<page>[SsGgOoZz]?\d{1,3})\s*$",
    re.I,
)

SENIOR_UNIT_RE = re.compile(
    r"^(?P<head>.+?)\s*[(\uff08〈]\s*(?P<unit>\d{1,2}|w+)\s*[)\uff09〉]\s*$",
    re.I,
)

PHONETIC_RE = re.compile(r"/[^/\n]{1,40}/")
LETTER_ONLY_RE = re.compile(r"^[A-Za-z]$")
POS_RE = re.compile(
    r"\b(?:n|v|vt|vi|adj|adv|pron|prep|conj|interj|art|num|aux|modal|phr)\.?",
    re.I,
)


@dataclass
class VocabEntry:
    word: str
    book_id: str
    book_title: str
    stage: str
    unit: str | None = None
    page: int | None = None
    zh: str | None = None
    phonetic: str | None = None
    source: str = "appendix"
    pdf_page: int | None = None
    raw: str = ""


@dataclass
class ParseState:
    current_unit: str | None = None
    section: str | None = None
    entries: list[VocabEntry] = field(default_factory=list)


def _ocr_int(raw: str) -> int:
    table = str.maketrans(
        {"S": "5", "s": "5", "G": "6", "g": "6", "O": "0", "o": "0", "Z": "2", "z": "2"}
    )
    digits = re.sub(r"\D", "", raw.translate(table))
    return int(digits) if digits else 0


def normalize_word(head: str) -> tuple[str, str | None, str | None]:
    phonetic = None
    m = PHONETIC_RE.search(head)
    if m:
        phonetic = m.group(0)
        head = (head[: m.start()] + " " + head[m.end() :]).strip()

    zh = None
    cjk = re.search(r"[\u4e00-\u9fff]", head)
    if cjk:
        zh = head[cjk.start() :].strip()
        head = head[: cjk.start()].strip()

    head = POS_RE.sub(" ", head)
    head = re.sub(r"\s+", " ", head).strip(" -–—·.,;:()[]")
    head = re.sub(r"^[^A-Za-z]+", "", head)
    head = re.sub(r"[^A-Za-z0-9'’\-\s()/.=]+$", "", head).strip()
    return head, phonetic, zh


def looks_like_vocab_line(line: str) -> bool:
    s = line.strip()
    if len(s) < 3 or LETTER_ONLY_RE.match(s):
        return False
    if not re.search(r"[A-Za-z]", s):
        return False
    if JUNIOR_PAGE_RE.search(s) or SENIOR_UNIT_RE.search(s):
        return True
    if PHONETIC_RE.search(s) and re.search(r"[\u4e00-\u9fff]", s):
        return True
    return False


def parse_line(
    line: str,
    *,
    book_id: str,
    book_title: str,
    stage: str,
    state: ParseState,
    pdf_page: int | None,
) -> VocabEntry | None:
    s = line.strip()
    if not s:
        return None

    uh = UNIT_HEADER_RE.match(s)
    if uh:
        if uh.group(1):
            state.current_unit = uh.group(1)
        elif re.search(r"Welcome|预备", s, re.I):
            state.current_unit = "welcome"
        else:
            state.section = "unit_list"
        return None

    if SECTION_AZ_RE.search(s) and "Each Unit" not in s:
        state.section = "az"
        return None

    if not looks_like_vocab_line(s):
        return None

    unit = state.current_unit
    page = None
    source = "unit_list" if state.section == "unit_list" or state.current_unit else "appendix_az"

    m_j = JUNIOR_PAGE_RE.match(s)
    m_s = SENIOR_UNIT_RE.match(s)
    if m_j:
        head = m_j.group("head")
        page = _ocr_int(m_j.group("page"))
        source = "appendix_az"
    elif m_s:
        head = m_s.group("head")
        u = m_s.group("unit").lower()
        unit = "w" if u.startswith("w") else u.lstrip("0") or u
        source = "appendix_az"
    else:
        m_tail = re.search(
            r"[(\uff08〈]\s*(\d{1,2}|w+)\s*[)\uff09〉]\s*$", s, re.I
        )
        m_page_tail = re.search(r"p[.．]?\s*([SsGgOoZz]?\d{1,3})\s*$", s, re.I)
        if m_tail and stage == "senior":
            head = s[: m_tail.start()]
            u = m_tail.group(1).lower()
            unit = "w" if u.startswith("w") else u.lstrip("0") or u
            source = "appendix_az"
        elif m_page_tail and stage == "junior":
            head = s[: m_page_tail.start()]
            page = _ocr_int(m_page_tail.group(1))
            source = "appendix_az"
        else:
            head = s

    word, phonetic, zh = normalize_word(head)
    if len(word) < 1 or not re.search(r"[A-Za-z]", word):
        return None
    if word.lower() in {
        "vocabulary",
        "appendices",
        "unit",
        "words and expressions",
        "people's education press",
    }:
        return None

    return VocabEntry(
        word=word,
        book_id=book_id,
        book_title=book_title,
        stage=stage,
        unit=unit,
        page=page,
        zh=zh,
        phonetic=phonetic,
        source=source,
        pdf_page=pdf_page,
        raw=s,
    )


def _split_merged_entries(line: str) -> list[str]:
    s = line.strip()
    if not s:
        return []
    parts = re.split(r"(?<=\d)\s+(?=[A-Za-z].+?\s+p\.?\s*\d+\s*$)", s)
    if len(parts) > 1:
        return [p.strip() for p in parts if p.strip()]
    hits = list(re.finditer(r"\((\d+|w)\)", s, re.I))
    if len(hits) >= 2:
        out = []
        start = 0
        for h in hits:
            out.append(s[start : h.end()].strip())
            start = h.end()
        rest = s[start:].strip()
        if rest:
            out.append(rest)
        return [x for x in out if x]
    return [s]


def _dedupe(entries: list[VocabEntry]) -> list[VocabEntry]:
    seen: set[tuple] = set()
    out: list[VocabEntry] = []
    for e in entries:
        key = (e.word.lower(), e.book_id, e.unit, e.page)
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


def parse_ocr_pages(
    pages: list[tuple[int, str]],
    *,
    book_id: str,
    book_title: str,
    stage: str,
) -> list[VocabEntry]:
    state = ParseState()
    for pdf_page, text in pages:
        for raw_line in text.splitlines():
            for chunk in _split_merged_entries(raw_line):
                entry = parse_line(
                    chunk,
                    book_id=book_id,
                    book_title=book_title,
                    stage=stage,
                    state=state,
                    pdf_page=pdf_page,
                )
                if entry:
                    state.entries.append(entry)
    return _dedupe(state.entries)


def entries_to_dicts(entries: list[VocabEntry]) -> list[dict]:
    return [asdict(e) for e in entries]


@dataclass
class UnitRange:
    unit: str
    start_page: int


def parse_toc_unit_starts(ocr_text: str) -> list[UnitRange]:
    ranges: list[UnitRange] = []
    for line in ocr_text.splitlines():
        s = line.strip()
        m = re.search(r"(?:Unit|UNIT)\s*(\d+)\b.*?(\d{1,3})\s*$", s, re.I)
        if m:
            ranges.append(UnitRange(unit=m.group(1), start_page=int(m.group(2))))
            continue
        m2 = re.search(r"(Welcome\s+Unit|预备单元).*?(\d{1,3})\s*$", s, re.I)
        if m2:
            ranges.append(UnitRange(unit="welcome", start_page=int(m2.group(2))))
    by_unit: dict[str, int] = {}
    for r in sorted(ranges, key=lambda x: x.start_page):
        by_unit.setdefault(r.unit, r.start_page)
    return [UnitRange(u, p) for u, p in sorted(by_unit.items(), key=lambda kv: kv[1])]


def map_page_to_unit(page: int, unit_starts: list[UnitRange]) -> str | None:
    if not unit_starts:
        return None
    current = None
    for ur in unit_starts:
        if page >= ur.start_page:
            current = ur.unit
        else:
            break
    return current


def apply_page_unit_mapping(
    entries: list[VocabEntry], unit_starts: list[UnitRange]
) -> list[VocabEntry]:
    for e in entries:
        if e.unit is None and e.page is not None:
            e.unit = map_page_to_unit(e.page, unit_starts)
    return entries
