"""Catalog of PEP English textbooks to index."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from vocab_ocr.shared.paths import DOWNLOADS


@dataclass(frozen=True)
class PepBook:
    id: str
    title: str
    stage: str  # junior | senior
    path: Path


BOOKS: list[PepBook] = [
    PepBook("junior-7a", "英语七年级上册", "junior", DOWNLOADS / "789txt-main" / "英语七年级上册.pdf"),
    PepBook("junior-7b", "英语七年级下册", "junior", DOWNLOADS / "789txt-main" / "英语七年级下册.pdf"),
    PepBook("junior-8a", "英语八年级上册", "junior", DOWNLOADS / "789txt-main" / "英语八年级上册.pdf"),
    PepBook("junior-8b", "英语八年级下册", "junior", DOWNLOADS / "789txt-main" / "英语八年级下册.pdf"),
    PepBook("junior-9a", "英语九年级上册", "junior", DOWNLOADS / "789txt-main" / "英语九年级上册.pdf"),
    PepBook("junior-9b", "英语九年级下册", "junior", DOWNLOADS / "初中（六三学制）" / "九年级" / "2027春人教版九年级英语下册电子课本（彩色版）.pdf"),
    PepBook(
        "senior-compulsory-1",
        "英语必修第一册",
        "senior",
        DOWNLOADS / "高中" / "英语" / "英语必修第一册.pdf",
    ),
    PepBook(
        "senior-compulsory-2",
        "英语必修第二册",
        "senior",
        DOWNLOADS / "高中" / "英语" / "英语必修第二册.pdf",
    ),
    PepBook(
        "senior-compulsory-3",
        "英语必修第三册",
        "senior",
        DOWNLOADS / "高中" / "英语" / "英语必修第三册.pdf",
    ),
    PepBook(
        "senior-optional-1",
        "英语选择性必修第一册",
        "senior",
        DOWNLOADS / "高中" / "英语" / "英语选择性必修第一册.pdf",
    ),
    PepBook(
        "senior-optional-2",
        "英语选择性必修第二册",
        "senior",
        DOWNLOADS / "高中" / "英语" / "英语选择性必修第二册.pdf",
    ),
    PepBook(
        "senior-optional-3",
        "英语选择性必修第三册",
        "senior",
        DOWNLOADS / "高中" / "英语" / "英语选择性必修第三册.pdf",
    ),
    PepBook(
        "senior-optional-4",
        "英语选择性必修第四册",
        "senior",
        DOWNLOADS / "高中" / "英语" / "英语选择性必修第四册.pdf",
    ),
]


def get_book(book_id: str) -> PepBook:
    for b in BOOKS:
        if b.id == book_id:
            return b
    raise KeyError(f"unknown PEP book id: {book_id}")
