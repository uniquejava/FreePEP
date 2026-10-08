"""Printed part-of-speech contract; no recognition or inference is performed."""

from __future__ import annotations

import json
import re
from pathlib import Path

POS_VERSION = 1
LABELS = {
    "n": "noun", "v": "verb", "vt": "transitive_verb", "vi": "intransitive_verb",
    "adj": "adjective", "a": "adjective", "adv": "adverb", "ad": "adverb",
    "pron": "pronoun", "prep": "preposition", "conj": "conjunction",
    "interj": "interjection", "int": "interjection", "art": "article",
    "num": "numeral", "aux": "auxiliary_verb", "modal": "modal_verb", "det": "determiner", "quantifier": "determiner",
}
TAGS = set(LABELS.values())
STATUSES = {"printed", "unmarked", "type", "unresolved", "inferred"}


def printed_tags(raw: str) -> list[str]:
    """Normalize literal abbreviations, rejecting unrecognized printed labels."""
    normalized = raw.lower()
    for pattern, replacement in ((r"\bmodal\s+(?:verb|v)\b\.?", "modal."),
                                 (r"\b(?:auxiliary|aux\.?)\s+(?:verb|v)\b\.?", "aux."),
                                 (r"\bpossessive\s+adjective\b", "adj."),
                                 (r"\bpredicative\s+adj\b\.?", "adj.")):
        normalized = re.sub(pattern, replacement, normalized)
    tokens = re.findall(r"[a-z]+", normalized)
    if not tokens or any(token not in LABELS for token in tokens):
        raise ValueError(f"unrecognized printed POS: {raw!r}")
    if re.sub(r"[a-z]+|[.\s&/;,、（）()]+", "", normalized):
        raise ValueError(f"unrecognized printed POS punctuation: {raw!r}")
    return list(dict.fromkeys(LABELS[token] for token in tokens))


def validate_pos(pos: dict) -> None:
    if not isinstance(pos, dict) or set(pos) - {"status", "raw", "tags", "note", "inherited_from", "senses"}:
        raise ValueError("invalid POS fields")
    status, raw, tags = pos.get("status"), pos.get("raw"), pos.get("tags")
    if (status not in STATUSES or not isinstance(raw, str) or not isinstance(tags, list)
            or any(not isinstance(tag, str) or tag not in TAGS for tag in tags)
            or len(tags) != len(set(tags))):
        raise ValueError("invalid POS status/raw/tags")
    note = pos.get("note")
    if note is not None and (not isinstance(note, str) or not note.strip()):
        raise ValueError("invalid POS note")
    if status == "printed" and (not raw.strip() or printed_tags(raw) != tags):
        raise ValueError("printed POS and normalized tags disagree")
    if status == "unmarked" and (raw or tags):
        raise ValueError("unmarked POS must have empty raw/tags")
    if status == "type" and (not raw.strip() or tags):
        raise ValueError("type description is not a grammatical POS")
    if status == "unresolved" and (tags or not note):
        raise ValueError("unresolved POS needs a note and no claimed tags")
    if status == "inferred" and (raw or not tags or not note):
        raise ValueError("inferred POS needs tags/note and no printed raw")
    if "senses" in pos:
        senses = pos["senses"]
        if status != "printed" or not isinstance(senses, list) or not senses:
            raise ValueError("printed POS senses must be a nonempty list")
        combined = []
        for sense in senses:
            if (not isinstance(sense, dict) or set(sense) != {"raw", "tags", "zh"}
                    or not isinstance(sense["zh"], str) or not sense["zh"].strip()):
                raise ValueError("invalid printed POS sense")
            validate_pos({"status": "printed", "raw": sense["raw"], "tags": sense["tags"]})
            combined.extend(tag for tag in sense["tags"] if tag not in combined)
        if combined != tags:
            raise ValueError("printed POS senses and occurrence tags disagree")
    if "inherited_from" in pos:
        inherited = pos["inherited_from"]
        if (status != "printed" or not isinstance(inherited, dict)
                or set(inherited) != {"source_pdf_page", "region_id", "entry_index"}
                or type(inherited["source_pdf_page"]) is not int or inherited["source_pdf_page"] < 1
                or type(inherited["entry_index"]) is not int or inherited["entry_index"] < 0
                or not isinstance(inherited["region_id"], str) or not inherited["region_id"]):
            raise ValueError("invalid continuation POS source")


def semantics(pos: dict) -> dict:
    result = {key: pos[key] for key in ("status", "raw", "tags")}
    if pos["status"] in {"unresolved", "inferred"}:
        result["note"] = pos["note"]
    if "senses" in pos:
        result["senses"] = pos["senses"]
    return result


def identity(pos: dict | None) -> str:
    return json.dumps(semantics(pos), sort_keys=True, ensure_ascii=False) if pos else ""


def valid_digest(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def review_regions(record: dict, book: dict, book_id: str, crops: Path, digest) -> dict:
    review = record.get("pos_review")
    required = {e["region_id"] for e in record["entries"]}
    if (not isinstance(review, dict) or review.get("reviewed_by") != "codex-direct-vision"
            or not isinstance(review.get("regions"), dict) or not required <= review["regions"].keys()):
        raise ValueError("POS review must cover every entry region")
    result = {}
    for region_id, evidence in review["regions"].items():
        region = next((r for r in record["regions"] if r["id"] == region_id), None)
        if not region or not isinstance(evidence, dict) or not all(
                valid_digest(evidence.get(k)) for k in ("metadata_sha256", "image_sha256")):
            raise ValueError("invalid POS region evidence")
        # Snapshot page names are independent of original source page numbers.
        candidates = []
        for path in (crops / book_id).glob(f"*-{region_id}.json"):
            metadata = json.loads(path.read_text())
            if (metadata.get("source_pdf_page") == record["source_pdf_page"]
                    and metadata.get("region_id") == region_id):
                candidates.append((path, metadata))
        if len(candidates) != 1:
            raise ValueError("missing/ambiguous POS crop provenance")
        path, metadata = candidates[0]
        if (digest(path) != evidence["metadata_sha256"] or digest(path.with_suffix(".png")) != evidence["image_sha256"]
                or metadata.get("source_sha256") != book["source_sha256"]
                or metadata.get("book") != book_id or metadata.get("region_id") != region_id
                or metadata.get("bbox") != region["bbox"]
                or metadata.get("coordinate_system") != "visible-page-top-left-normalized"
                or not all(valid_digest(metadata.get(k)) for k in ("pdf_sha256", "map_sha256"))):
            raise ValueError("POS crop source/image identity mismatch")
        result[region_id] = dict(evidence)
    return result


def resolve_source(record: dict, entry: dict, records: list[dict]) -> tuple[dict, dict]:
    """A continuation may inherit only from the same printed word/gloss/unit."""
    current_record, current_entry, seen = record, entry, set()
    while inherited := current_entry["pos"].get("inherited_from"):
        marker = (inherited["source_pdf_page"], inherited["entry_index"])
        if marker in seen:
            raise ValueError("cyclic continuation POS source")
        seen.add(marker)
        target = next((r for r in records if r["source_pdf_page"] == marker[0]), None)
        if target is None or not 0 <= marker[1] < len(target["entries"]):
            raise ValueError("missing continuation POS source")
        target_entry = target["entries"][marker[1]]
        if (target_entry["region_id"] != inherited["region_id"]
                or any(target_entry.get(k) != entry.get(k) for k in ("word", "unit", "zh", "page"))
                or identity(target_entry.get("pos")) != identity(entry["pos"])):
            raise ValueError("continuation POS source disagrees with entry")
        current_record, current_entry = target, target_entry
    return current_record, current_entry
