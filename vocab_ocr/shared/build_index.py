"""Build inverted word→hits index (with per-occurrence Chinese gloss)."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

_WORD_OK = re.compile(r"^[a-z][a-z'’\-\s]{0,40}$")
PHONETIC_STRIP = re.compile(r"/[^/\n]{0,40}/")
_KEEP_SHORT = {
    "a",
    "i",
    "an",
    "to",
    "of",
    "in",
    "on",
    "up",
    "at",
    "or",
    "no",
    "my",
    "me",
    "we",
    "be",
    "do",
    "is",
    "am",
    "as",
    "by",
    "if",
    "it",
    "so",
    "us",
}
_TRAILING_POS = {"a", "n", "v", "vt", "vi", "adj", "adv", "prep", "conj", "pron"}

# Shared schema for PEP + NCE. Hits always end with zh (string). Keep at 1 until a
# breaking change ships; do not invent parallel version numbers per corpus.
INDEX_VERSION = 1


def clean_zh(zh: str | None) -> str:
    """Normalize OCR Chinese gloss for the index."""
    if not zh:
        return ""
    s = str(zh).strip()
    s = PHONETIC_STRIP.sub(" ", s)
    s = re.sub(r"\[[^\]]{0,40}\]", " ", s)
    # Cut when next English entry / POS leaked into the gloss.
    s = re.split(
        r"\b(?:adj|adv|n|v|vt|vi|prep|pron|conj|art|num|phr)\s*\.?\s+[A-Za-z]",
        s,
        maxsplit=1,
    )[0]
    s = re.split(r"\s+p\.?\s*[A-Za-z0-9]+\b", s, maxsplit=1, flags=re.I)[0]
    s = re.split(r"(?<=[\u4e00-\u9fff])\s+(?=[A-Za-z]{3,}\b)", s, maxsplit=1)[0]
    # Drop leading non-CJK junk (OCR debris).
    s = re.sub(r"^[^\u4e00-\u9fffA-Za-z0-9（(]+", "", s)
    # Collapse spaces between CJK characters.
    s = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", s)
    s = re.sub(r"\s+", " ", s).strip(" ;,，、.|·:：")
    # Keep only if we still have some CJK (otherwise empty rather than English noise).
    if not re.search(r"[\u4e00-\u9fff]", s):
        return ""
    return s


def _collapse_hits(hits: list[list]) -> list[list]:
    """One hit per (book, unit); prefer the one with page and/or richer zh."""
    best: dict[tuple[str, str], list] = {}
    for hit in hits:
        if len(hit) < 3:
            continue
        key = (str(hit[0]), str(hit[1]))
        prev = best.get(key)
        if prev is None:
            best[key] = hit
            continue
        # Prefer longer hit (has page) then longer zh.
        prev_zh = str(prev[-1] or "")
        hit_zh = str(hit[-1] or "")
        if len(hit) > len(prev):
            best[key] = hit
        elif len(hit) == len(prev) and len(hit_zh) > len(prev_zh):
            best[key] = hit
    return list(best.values())


def norm_lemma(word: str) -> str | None:
    s = (word or "").strip().lower()
    s = PHONETIC_STRIP.sub(" ", s)
    s = re.split(r"[\u4e00-\u9fff]", s, maxsplit=1)[0]
    s = re.sub(r"[^a-z'’\-\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" -–—·.,;:'’")
    if not s or not _WORD_OK.match(s):
        return None
    tokens = s.split()
    while len(tokens) > 1 and tokens[-1] in _TRAILING_POS:
        tokens.pop()
    while len(tokens) > 1 and len(tokens[-1]) <= 2 and tokens[-1] not in _KEEP_SHORT:
        tokens.pop()
    key = " ".join(tokens)
    if key in {"a", "i", "unit", "vocabulary", "appendices", "section", "lesson"}:
        return None
    return key


def build_inverted_index(
    book_results: list[dict],
    out_dir: Path,
    *,
    basename: str = "vocab-index",
) -> Path:
    """Write ``{basename}.json`` + ``{basename}.min.json``.

    Hit shape (v=1, shared by PEP and NCE):
      ``[book_id, unit_or_lesson, zh]``
      ``[book_id, unit_or_lesson, page, zh]`` when page is known

    The **last** element is always the Chinese gloss (string, may be \"\").
    The same lemma in two units/lessons yields **two** hits (each with its own zh).
    POS / 词性 is not part of the index.
    """
    index: dict[str, list[list]] = defaultdict(list)
    books_meta: dict[str, str] = {}
    for book in book_results:
        books_meta[book["book_id"]] = book["title"]
        for e in book["entries"]:
            key = norm_lemma(e.get("word") or "")
            if not key:
                continue
            unit = e.get("unit")
            if unit is None or unit == "":
                continue
            unit_s = str(unit)
            zh = clean_zh(e.get("zh"))
            page = e.get("page")
            hit: list = [e["book_id"], unit_s]
            if isinstance(page, int) and page > 0:
                hit.append(page)
            hit.append(zh)
            if hit not in index[key]:
                index[key].append(hit)

    for key in index:
        index[key] = _collapse_hits(index[key])

        def sort_key(x: list) -> tuple:
            page = x[2] if len(x) == 4 and isinstance(x[2], int) else 0
            return (str(x[0]), str(x[1]), page)

        index[key].sort(key=sort_key)

    payload = {
        "v": INDEX_VERSION,
        "books": dict(sorted(books_meta.items())),
        "w": dict(sorted(index.items())),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{basename}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    compact = out_dir / f"{basename}.min.json"
    compact.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return path
