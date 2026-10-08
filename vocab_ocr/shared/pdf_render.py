"""Render PDF pages to JPEG via pdftoppm."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def require_pdftoppm() -> str:
    path = shutil.which("pdftoppm")
    if not path:
        raise RuntimeError("pdftoppm not found (install poppler via brew)")
    return path


def pdf_page_count(pdf: Path) -> int:
    info = shutil.which("pdfinfo")
    if not info:
        raise RuntimeError("pdfinfo not found (install poppler via brew)")
    out = subprocess.check_output([info, str(pdf)], text=True, errors="replace")
    for line in out.splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":", 1)[1].strip())
    raise RuntimeError(f"cannot read page count: {pdf}")


def render_pages(
    pdf: Path,
    out_dir: Path,
    prefix: str,
    first: int,
    last: int,
    dpi: int = 200,
    *,
    clear_prefix: bool = True,
    crop_box: bool = False,
) -> list[Path]:
    """Render 1-based inclusive page range. Returns sorted JPEG paths."""
    require_pdftoppm()
    out_dir.mkdir(parents=True, exist_ok=True)
    if clear_prefix:
        for old in out_dir.glob(f"{prefix}-*.jpg"):
            old.unlink(missing_ok=True)

    stem = out_dir / prefix
    cmd = [
        "pdftoppm",
        "-jpeg",
        "-r",
        str(dpi),
        "-f",
        str(first),
        "-l",
        str(last),
        str(pdf),
        str(stem),
    ]
    if crop_box:
        cmd.insert(1, "-cropbox")
    subprocess.check_call(cmd)
    pages = sorted(out_dir.glob(f"{prefix}-*.jpg"))
    if not pages:
        raise RuntimeError(f"no pages rendered for {pdf} [{first}-{last}]")
    return pages


def pdf_page_from_render_name(path: Path) -> int | None:
    """Extract 1-based PDF page from pdftoppm name like prefix-052.jpg."""
    import re

    m = re.search(r"-(\d+)\.jpe?g$", path.name, re.I)
    return int(m.group(1)) if m else None
