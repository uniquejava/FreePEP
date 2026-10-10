"""Provenance for restored or supplemented textbook Chinese glosses."""

from __future__ import annotations

import json
from urllib.parse import urlsplit

GLOSS_VERSION = 1


def validate_gloss_source(value: dict, source_page_count: int | None = None) -> None:
    if (not isinstance(value, dict) or set(value) != {"status", "note", "sources"}
            or value["status"] not in {"cross-reference", "supplemented"}
            or not isinstance(value["note"], str) or not value["note"].strip()
            or not isinstance(value["sources"], list) or not value["sources"]):
        raise ValueError("invalid gloss provenance")
    for source in value["sources"]:
        if not isinstance(source, dict) or not isinstance(source.get("label"), str) or not source["label"].strip():
            raise ValueError("gloss source needs a label")
        kind = source.get("kind")
        if kind == "same-book":
            if set(source) != {"kind", "label", "source_pdf_pages"}:
                raise ValueError("invalid same-book gloss source fields")
            pages = source["source_pdf_pages"]
            if (not isinstance(pages, list) or not pages
                    or any(type(n) is not int or n < 1 or
                           (source_page_count is not None and n > source_page_count) for n in pages)
                    or len(pages) != len(set(pages))):
                raise ValueError("invalid same-book gloss source pages")
        elif kind == "same-edition":
            if set(source) != {"kind", "label", "url"} or not isinstance(source["url"], str):
                raise ValueError("invalid same-edition gloss source fields")
            url = urlsplit(source["url"])
            if url.scheme not in {"http", "https"} or not url.netloc or url.username or url.password:
                raise ValueError("invalid gloss source URL")
        elif kind == "conventional-name":
            if set(source) != {"kind", "label"} or value["status"] != "supplemented":
                raise ValueError("a conventional name must be a labeled supplement")
        else:
            raise ValueError("unknown gloss source kind")
    if value["status"] == "cross-reference" and any(s["kind"] != "same-book" for s in value["sources"]):
        raise ValueError("cross-reference gloss must come from the same book")


def identity(value: dict | None) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True) if value is not None else ""
