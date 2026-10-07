"""Tesseract OCR wrapper."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def require_tesseract() -> str:
    path = shutil.which("tesseract")
    if not path:
        raise RuntimeError(
            "tesseract not found. Install with: brew install tesseract tesseract-lang"
        )
    return path


def ocr_image(
    image: Path,
    *,
    lang: str = "eng+chi_sim",
    psm: int = 6,
) -> str:
    """OCR one image; return plain text."""
    tess = require_tesseract()
    cmd = [
        tess,
        str(image),
        "stdout",
        "-l",
        lang,
        "--psm",
        str(psm),
    ]
    return subprocess.check_output(cmd, text=True, errors="replace")
