"""NCE2 pilot: Excel → CSV, align Lesson via public lesson vocab (no full-PDF OCR).

Usage:
  python3 -m vocab_ocr.nce.pilot_nce2_from_excel

Inputs (defaults):
  ~/code/English/8.新概念英语/新概念英语第二册（新版）.xlsx
  https://www.sohu.com/a/517761822_699921  (cached under _work)

Outputs (gitignored _work + committed index):
  data/vocab/_work/nce-2/excel.csv
  data/vocab/_work/nce-2/excel-with-lesson.csv  (includes pos for QA)
  data/vocab/_work/nce-2/lesson-vocab.csv       (includes pos for QA)
  data/vocab/nce-vocab-index.min.json   (nce-2 only; same schema as PEP, v:1; pos NOT in hits)

Index hit shape (shared with PEP, vocab_ocr.shared.build_index.INDEX_VERSION):
  [book_id, lesson, zh]
"""

from __future__ import annotations

import csv
import argparse
import json
import re
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

from vocab_ocr.shared.build_index import INDEX_VERSION
from vocab_ocr.shared.paths import DEFAULT_OUT, DEFAULT_WORK, ROOT

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
XLSX_DEFAULT = Path.home() / "code/English/8.新概念英语/新概念英语第二册（新版）.xlsx"
SOHU_URL = "https://www.sohu.com/a/517761822_699921"

ALIASES: dict[str, list[str]] = {
    "spare part": ["spare"],
    "upside down": ["upside"],
    "snake charmer": ["snake"],
    "content": ["contents"],
    "cotton wool": ["cotton"],
    "packing case": ["packing"],
    "the press": ["press"],
    "cover": ["cover", "over"],
    "pilatus porter": ["pilatusporter", "pilatus porter"],
    "fire extinguisher": ["fireextinguisher", "fire extinguisher"],
    "water ski": ["water ski"],
    "eagle eye": ["eagle eye"],
    "sea level": ["sea level"],
    "power line": ["power line"],
    "pop singer": ["pop singer"],
    "ticket office": ["ticket office"],
}

# Proper nouns / forms missing or mangled in the public list
MANUAL_LESSON: dict[str, tuple[int, str]] = {
    "wayle": (30, "威尔河"),
    "escalopia": (95, "埃斯卡罗比亚（虚构国名）"),
}

_POS_HEAD = re.compile(
    r"^(?P<word>[A-Za-z][A-Za-z\'\-]*(?:\s+[A-Za-z][A-Za-z\'\-]*)*)\s+"
    r"(?P<rest>(?:[nvap]|ad|prep|conj|modal\s+verb|prefix)\b\.?\s*.*)$",
    re.I,
)
_PLAIN = re.compile(
    r"^(?P<word>[A-Za-z][A-Za-z\'\-]*(?:\s+[A-Za-z][A-Za-z\'\-]*)*)\s*(?P<rest>.*)$"
)
_POS_TAG = re.compile(
    r"^(?P<pos>(?:[nvap]|ad|prep|conj|modal\s+verb|prefix)\.?)\s*(?P<zh>.*)$",
    re.I,
)

def col_letter_to_index(col: str) -> int:
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def cell_text(c: ET.Element) -> str:
    t = c.get("t")
    v = c.find("m:v", NS)
    is_elem = c.find("m:is", NS)
    if t == "inlineStr" and is_elem is not None:
        return "".join(
            x.text or ""
            for x in is_elem.iter(
                "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"
            )
        )
    if v is not None:
        return v.text or ""
    return ""


def read_excel(path: Path) -> list[dict[str, str]]:
    with zipfile.ZipFile(path) as z:
        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
        rows: list[list[str]] = []
        for row in sheet.findall("m:sheetData/m:row", NS):
            cells: dict[int, str] = {}
            for c in row.findall("m:c", NS):
                ref = c.get("r", "")
                m = re.match(r"([A-Z]+)", ref)
                if not m:
                    continue
                cells[col_letter_to_index(m.group(1))] = cell_text(c)
            if not cells:
                continue
            max_i = max(cells)
            vals = [cells.get(i, "") for i in range(max(max_i + 1, 4))]
            rows.append(vals[:4])
    header, *data = rows
    if "单词" not in (header[0] or ""):
        raise RuntimeError(f"unexpected excel header: {header}")
    out: list[dict[str, str]] = []
    for r in data:
        w = (r[0] or "").strip()
        if not w:
            continue
        out.append(
            {
                "word": w,
                "ipa_uk": (r[1] or "").strip(),
                "ipa_us": (r[2] or "").strip(),
                "zh": (r[3] or "").strip().replace("\n", " | "),
            }
        )
    return out


def norm_lemma(s: str) -> str:
    s = s.strip().lower().replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", s)


def keys_of(word: str) -> list[str]:
    w = norm_lemma(word)
    ks = [w]
    if w in ALIASES:
        for a in ALIASES[w]:
            if a not in ks:
                ks.append(a)
    w2 = re.sub(r"\([^)]*\)", "", w).strip()
    if w2 and w2 not in ks:
        ks.append(w2)
    if "-" in w2:
        for alt in (w2.replace("-", " "), w2.replace("-", "")):
            if alt not in ks:
                ks.append(alt)
    if " " in w2:
        joined = w2.replace(" ", "")
        if joined not in ks:
            ks.append(joined)
    return ks


def html_to_text(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</(?:p|div|li|h\d)>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    return text


def fetch_sohu(cache: Path) -> str:
    if cache.exists() and cache.stat().st_size > 1000:
        return cache.read_text(encoding="utf-8")
    req = urllib.request.Request(SOHU_URL, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    text = html_to_text(html)
    cache.write_text(text, encoding="utf-8")
    return text


def split_pos_zh(rest: str) -> tuple[str, str]:
    """Split leading POS tag from gloss. POS is for _work CSV only."""
    rest = (rest or "").strip()
    m = _POS_TAG.match(rest)
    if not m:
        return "", rest
    pos = m.group("pos").strip().lower().rstrip(".")
    # normalize a few textbook abbreviations
    if pos == "a":
        pos = "adj"
    elif pos == "ad":
        pos = "adv"
    elif pos == "p":
        pos = "prep"
    elif pos == "modal verb":
        pos = "modal"
    return pos, (m.group("zh") or "").strip()


def parse_entry_line(line: str) -> tuple[str, str, str] | None:
    """Parse one sohu vocab line → (word, pos, zh)."""
    line = re.sub(r"^(\d+)([A-Za-z])", r"\1 \2", line.strip())
    line = re.sub(r"^(\d+)\s*", "", line)
    line = re.sub(r"^a\s+ccidentally", "accidentally", line, flags=re.I)
    line = re.sub(r"\bKivun\.", "Kivu ", line)
    line = re.sub(r"\[[^\]]*\]", " ", line)
    line = re.sub(r"\s+", " ", line).strip()
    if not line or not re.match(r"^[A-Za-z]", line):
        return None
    m = _POS_HEAD.match(line) or _PLAIN.match(line)
    if not m:
        return None
    word = m.group("word").strip()
    pos, zh = split_pos_zh(m.group("rest"))
    return word, pos, zh


def parse_lesson_vocab(text: str) -> list[dict]:
    ordered: list[dict] = []
    cur: int | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = re.match(r"^Lesson\s+(\d+)\s*$", line, re.I)
        if m:
            cur = int(m.group(1))
            continue
        if cur is None:
            continue
        if line.startswith("新概念") or "返回搜狐" in line:
            break
        parsed = parse_entry_line(line)
        if not parsed:
            continue
        word, pos, zh = parsed
        ordered.append({"lesson": cur, "word": word, "pos": pos, "zh": zh})
    return ordered


def sequential_align(excel_rows: list[dict], sohu_rows: list[dict]) -> list[dict | None]:
    results: list[dict | None] = [None] * len(excel_rows)
    j = 0
    for i, row in enumerate(excel_rows):
        eks = set(keys_of(row["word"]))
        found = None
        for k in range(j, min(j + 15, len(sohu_rows))):
            if eks & set(keys_of(sohu_rows[k]["word"])):
                found = k
                break
        if found is None:
            for k in range(j, len(sohu_rows)):
                if eks & set(keys_of(sohu_rows[k]["word"])):
                    found = k
                    break
        if found is not None:
            results[i] = sohu_rows[found]
            j = found + 1
    return results


def short_zh(lesson_zh: str, excel_zh: str) -> str:
    """Gloss for index hits only — never embed POS into zh."""
    zh = lesson_zh or excel_zh.split("|")[0].strip()
    _, zh = split_pos_zh(zh)
    if "|" in zh:
        zh = zh.split("|")[0].strip()
    if len(zh) > 40:
        zh = re.split(r"[；。]", zh)[0].strip()
        _, zh = split_pos_zh(zh)
    return zh


def build_index(rows: list[dict]) -> dict:
    """Build inverted index. POS is intentionally omitted from hits (v:1)."""
    index: dict = {
        "v": INDEX_VERSION,
        "books": {"nce-2": "新概念英语第二册"},
        "w": {},
    }
    for r in rows:
        if not r.get("lesson"):
            continue
        lemma = norm_lemma(r["word"])
        # hit: [book_id, lesson, zh] — no pos, no page in this pilot
        hit = ["nce-2", r["lesson"], short_zh(r.get("lesson_zh", ""), r["zh"])]
        index["w"].setdefault(lemma, []).append(hit)
    for lem, hits in list(index["w"].items()):
        seen: set[tuple] = set()
        uniq = []
        for h in hits:
            t = tuple(h)
            if t not in seen:
                seen.add(t)
                uniq.append(h)
        index["w"][lem] = uniq
    return index


def run(xlsx: Path = XLSX_DEFAULT, lesson_vocab: Path | None = None) -> dict:
    work = DEFAULT_WORK / "nce-2"
    work.mkdir(parents=True, exist_ok=True)

    excel = read_excel(xlsx)
    excel_csv = work / "excel.csv"
    with excel_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["word", "ipa_uk", "ipa_us", "zh"])
        w.writeheader()
        w.writerows(excel)

    sohu_text = (
        lesson_vocab.read_text(encoding="utf-8")
        if lesson_vocab is not None
        else fetch_sohu(work / "sohu-lesson-vocab.txt")
    )
    sohu_ordered = parse_lesson_vocab(sohu_text)
    if len({it["lesson"] for it in sohu_ordered}) < 90:
        raise RuntimeError(
            f"sohu parse too thin: {len(sohu_ordered)} entries / "
            f"{len({it['lesson'] for it in sohu_ordered})} lessons"
        )

    with (work / "lesson-vocab.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["lesson", "word", "pos", "zh"])
        w.writeheader()
        w.writerows(sohu_ordered)

    lemma_map: dict[str, list[dict]] = defaultdict(list)
    for it in sohu_ordered:
        for k in keys_of(it["word"]):
            lemma_map[k].append(it)

    seq = sequential_align(excel, sohu_ordered)
    consumed: set[tuple[int, str]] = set()
    rows_out: list[dict] = []
    stats: Counter[str] = Counter()

    for i, row in enumerate(excel):
        hit = seq[i]
        method = "seq" if hit else None
        if hit is None:
            for k in keys_of(row["word"]):
                for it in lemma_map.get(k, []):
                    key = (it["lesson"], norm_lemma(it["word"]))
                    if key in consumed:
                        continue
                    hit = it
                    method = "lookup"
                    consumed.add(key)
                    break
                if hit:
                    break
        else:
            consumed.add((hit["lesson"], norm_lemma(hit["word"])))

        if hit is None:
            manual = MANUAL_LESSON.get(norm_lemma(row["word"]))
            if manual:
                lesson, zh = manual
                stats["manual"] += 1
                rows_out.append(
                    {
                        **row,
                        "lesson": str(lesson),
                        "pos": "",
                        "lesson_zh": zh,
                        "match": "manual",
                        "sohu_word": row["word"],
                    }
                )
            else:
                stats["unmatched"] += 1
                rows_out.append(
                    {
                        **row,
                        "lesson": "",
                        "pos": "",
                        "lesson_zh": "",
                        "match": "unmatched",
                        "sohu_word": "",
                    }
                )
        else:
            stats[method or "ok"] += 1
            rows_out.append(
                {
                    **row,
                    "lesson": str(hit["lesson"]),
                    "pos": hit.get("pos", ""),
                    "lesson_zh": hit["zh"],
                    "match": method or "ok",
                    "sohu_word": hit["word"],
                }
            )

    enriched = work / "excel-with-lesson.csv"
    with enriched.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "lesson",
                "word",
                "pos",
                "ipa_uk",
                "ipa_us",
                "zh",
                "lesson_zh",
                "match",
                "sohu_word",
            ],
        )
        w.writeheader()
        for r in rows_out:
            w.writerow({k: r.get(k, "") for k in w.fieldnames})

    index = build_index(rows_out)
    min_path = DEFAULT_OUT / "nce-vocab-index.min.json"
    min_path.write_text(
        json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    (work / "nce-vocab-index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    matched = len(excel) - stats["unmatched"]
    with_pos = sum(1 for r in rows_out if r.get("pos"))
    report = {
        "index_version": INDEX_VERSION,
        "excel_rows": len(excel),
        "sohu_entries": len(sohu_ordered),
        "lessons": len({it["lesson"] for it in sohu_ordered}),
        "matched": matched,
        "match_rate": round(matched / len(excel), 4),
        "stats": dict(stats),
        "rows_with_pos_in_csv": with_pos,
        "unmatched": [r["word"] for r in rows_out if r["match"] == "unmatched"],
        "index_lemmas": len(index["w"]),
        "outputs": {
            "excel_csv": str(excel_csv.relative_to(ROOT)),
            "enriched_csv": str(enriched.relative_to(ROOT)),
            "index": str(min_path.relative_to(ROOT)),
        },
    }
    (work / "pilot-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="新概念英语二册 Excel/课次词表索引试点")
    parser.add_argument("--xlsx", type=Path, default=XLSX_DEFAULT, help="四列词表 Excel 路径")
    parser.add_argument("--lesson-vocab", type=Path, help="已保存的 Lesson 词表纯文本；省略时读取缓存或搜狐页面")
    args = parser.parse_args(argv)
    report = run(args.xlsx, args.lesson_vocab)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
