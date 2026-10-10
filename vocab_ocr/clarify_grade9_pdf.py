"""Overlay visually verified Chinese on a separate textbook vocabulary PDF.

Coordinates come from human-reviewed page renders, not OCR. This utility does
not write indexes or source PDFs. Uncertain patches are rejected by default.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
from pathlib import Path

from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.generic import RectangleObject
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(source: Path, annotation_paths: list[Path], output: Path,
          font_path: Path, font_index: int, expected_pages: list[int]) -> None:
    if source.resolve() == output.resolve():
        raise ValueError("Source PDF must never be overwritten")
    before = digest(source)
    pages = {}
    for path in annotation_paths:
        annotations = json.loads(path.read_text(encoding="utf-8"))
        if annotations.get("source_sha256") != before:
            raise ValueError(f"Annotation source mismatch: {path}")
        for page in annotations["pages"]:
            number = page["pdf_page"]
            if number in pages:
                raise ValueError(f"Duplicate annotation page {number}")
            pages[number] = page
    if sorted(pages) != expected_pages:
        raise ValueError(f"Page coverage {sorted(pages)} != {expected_pages}")
    pdfmetrics.registerFont(TTFont("ClearChinese", str(font_path),
                                  subfontIndex=font_index))
    reader = PdfReader(source)
    writer = PdfWriter()
    for number in expected_pages:
        annotation = pages[number]
        # Copy the page dictionary, keeping its immutable source streams.
        # Deepcopy follows indirect references into the entire reader graph.
        page = copy.copy(reader.pages[number - 1])
        if page.rotation:
            raise ValueError("Rotated source page needs explicit coordinate review")
        left, bottom, right, top = map(float, page.cropbox)
        width, height = right - left, top - bottom
        sx, sy = width / annotation["width"], height / annotation["height"]
        page.add_transformation(Transformation().translate(-left, -bottom))
        page.mediabox = RectangleObject([0, 0, width, height])
        page.cropbox = RectangleObject([0, 0, width, height])
        buffer = io.BytesIO()
        layer = canvas.Canvas(buffer, pagesize=(width, height))
        for patch in annotation["patches"]:
            if patch.get("confidence") != "verified" or not patch.get("evidence"):
                raise ValueError(f"Unverified patch on source page {number}: {patch}")
            x0, y0, x1, y1 = patch["box"]
            if not (0 <= x0 < x1 <= annotation["width"] and
                    0 <= y0 < y1 <= annotation["height"]):
                raise ValueError(f"Invalid patch bounds on page {number}")
            size = patch["font_size"] * sy
            leading = patch.get("line_height", patch["font_size"] * 1.1) * sy
            baseline = height - patch["text_y"] * sy
            text_x = patch.get("text_x", x0) * sx
            if text_x < x0 * sx or size <= 0 or leading <= 0:
                raise ValueError(f"Invalid text position or size on page {number}")
            lines = patch["text"].split("\n")
            for index, line in enumerate(lines):
                text_width = pdfmetrics.stringWidth(line, "ClearChinese", size)
                if text_x + text_width > x1 * sx + 0.5:
                    raise ValueError(f"Text overflows patch on page {number}: {line}")
                if baseline - index * leading < height - y1 * sy:
                    raise ValueError(f"Text falls below patch on page {number}: {line}")
            layer.setFillColorRGB(1, 1, 1)
            layer.rect(x0 * sx, height - y1 * sy,
                       (x1 - x0) * sx, (y1 - y0) * sy, fill=1, stroke=0)
            layer.setFillColorRGB(0, 0, 0)
            layer.setFont("ClearChinese", size)
            for index, line in enumerate(lines):
                layer.drawString(text_x, baseline - index * leading, line)
        layer.setFillColorRGB(0.4, 0.4, 0.4)
        layer.setFont("ClearChinese", 5.5)
        layer.drawRightString(width - 12, 7, "中文清晰阅读衍生文件 / 非出版社原页")
        layer.save()
        page.merge_page(PdfReader(buffer).pages[0])
        writer.add_page(page)
    writer.add_metadata({"/Title": "九年级下册词表 - 中文清晰阅读衍生文件",
                         "/Subject": "中文含注明来源的阅读替补；英文、音标、词性和页码保留原图",
                         "/SourceSHA256": before})
    provenance = {"source_sha256": before, "kind": "Chinese reading derivative",
                  "pages": [pages[number] for number in expected_pages]}
    writer.add_attachment("chinese-repair-provenance.json",
                          json.dumps(provenance, ensure_ascii=False,
                                     indent=2).encode("utf-8"))
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = output.with_suffix(".staging.pdf")
    try:
        with staging.open("wb") as stream:
            writer.write(stream)
        if len(PdfReader(staging).pages) != len(expected_pages):
            raise ValueError("Output page count mismatch")
        if digest(source) != before:
            raise ValueError("Source changed during rendering")
        staging.replace(output)
    finally:
        staging.unlink(missing_ok=True)
    print(json.dumps({"output": str(output), "pages": len(expected_pages),
                      "patches": sum(len(p["patches"]) for p in pages.values()),
                      "source_sha256": before}, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("annotations", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pages", default="94-104")
    parser.add_argument("--font", type=Path,
                        default=Path("/System/Library/Fonts/Supplemental/Songti.ttc"))
    parser.add_argument("--font-index", type=int, default=6)
    args = parser.parse_args()
    start, end = map(int, args.pages.split("-"))
    build(args.source, args.annotations, args.output, args.font, args.font_index,
          list(range(start, end + 1)))


if __name__ == "__main__":
    main()
