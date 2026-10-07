"""Repo-relative paths for vocab OCR work products."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORK = ROOT / "data" / "vocab" / "_work"
DEFAULT_OUT = ROOT / "data" / "vocab"
DOWNLOADS = ROOT / "downloads"
