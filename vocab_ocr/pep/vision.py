"""Transcribe a complete PEP vocabulary page with an already running LM Studio.

This module produces reviewable candidates, not verified index entries. In
particular, a plausible Unit number in a model response is not evidence that
the printed number was read correctly.
"""

from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from vocab_ocr.shared.paths import ROOT


GEMMA_MODEL = "gemma-4-26b-a4b-it-claude-opus-heretic-ara"
ENV_FILE = ROOT / ".env"
BASE_URL_KEY = "LM_STUDIO_BASE_URL"

_ENTRY_SCHEMA = {
    "type": "object",
    "properties": {
        "word": {"type": "string"},
        "zh": {"type": ["string", "null"]},
        "ref": {"type": ["string", "null"]},
        "raw": {"type": "string"},
        "uncertainty": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["word", "zh", "ref", "raw", "uncertainty"],
}

_PAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["vocab", "non_vocab"]},
        "reason": {"type": ["string", "null"]},
        "printed_page": {"type": ["string", "null"]},
        "columns": {
            "type": "object",
            "properties": {
                "left": {"type": "array", "items": _ENTRY_SCHEMA},
                "right": {"type": "array", "items": _ENTRY_SCHEMA},
            },
            "required": ["left", "right"],
        },
        "uncertainty": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["kind", "reason", "printed_page", "columns", "uncertainty"],
}


class VisionTranscriptionError(RuntimeError):
    """A page cannot be safely used as a complete transcription candidate."""


def _load_base_url(env_file: Path = ENV_FILE) -> str:
    """Read the local LM Studio address from the ignored project .env file."""
    if not env_file.is_file():
        raise VisionTranscriptionError(f"missing {env_file}; copy .env.sample to .env")
    values = []
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if separator and key.strip() == BASE_URL_KEY:
            values.append(value.strip().strip("\"'"))
    if len(values) != 1 or not values[0]:
        raise VisionTranscriptionError(f"{env_file} must define {BASE_URL_KEY} exactly once")
    url = values[0]
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise VisionTranscriptionError(f"{BASE_URL_KEY} must be an HTTP(S) URL")
    return url


_INSTRUCTIONS = """你在转录人教版英语教材附录中的词汇表。只依据所给的完整原页图片逐字读取，不猜读、补全或改写。
版式：页面有左、右两栏。先逐行读完左栏，再逐行读完右栏；同一水平线上的左右词条互不相连。
页面右下角单独的数字是词汇表本身的印刷页码，只填 printed_page，绝不是词条的正文页码或 Unit。
初中词条后面的 p. 数字是该词在教材正文中的页码，逐条原样保留在 ref；它不是词汇表页码，也不是 Unit。
高中词条后括号中的数字是该词所属 Unit，逐条原样保留在 ref；它不是词汇表页码。括号内容为 w 时也原样保留。
一个词条的中文释义不能混入下一词，也不能混入另一栏。完整保留每条可见中文释义及标点。词头保留图片上的拼写；不要根据语义或相邻词条修正 Unit 或页码。
zh 字段只写中文释义，不含 n.、v.、adj. 等词性；词性与音标仍可保留在 raw。Unit 标题、字母分段标题和无英文词头的上一页续行不是新词条，不要加入两栏词条数组。普通换行只需归并，不算 uncertainty；只有真实无法判清的内容才列为疑点。
只返回一个完整 JSON 对象，不要 Markdown。形状：
{"kind":"vocab 或 non_vocab","reason":"非词汇页的具体依据，词汇页填 null","printed_page":"页脚数字或 null","columns":{"left":[{"word":"英文词头","zh":"完整中文释义或 null","ref":"原样的 p. 数字或 (Unit)，看不清则 null","raw":"该词条在图片上可读的整条原文","uncertainty":["无法辨识或可能跨行的具体问题"]}],"right":[同样结构]},"uncertainty":["整页遗漏、版式或页脚疑点"]}
只有页面实际没有词汇表，才输出 kind=non_vocab、非空 reason 和两栏空数组。词汇页必须输出全部可读词条。
即使其中一栏没有词条也返回空数组。遇到模糊文字，用 null 和 uncertainty 说明；绝不编造。输出必须覆盖页面所有可读词条。"""


def _prompt(stage: Literal["junior", "senior"]) -> str:
    if stage == "junior":
        stage_note = "这是一册初中英语：每条 p. 后面的数字必须保留，Unit 不在本页直接印在词条后。"
    else:
        stage_note = "这是一册高中英语：每条词头后的括号数字/字母必须保留，它是 Unit，不要从页脚推断。"
    return _INSTRUCTIONS + "\n" + stage_note


def _json_text(content: str) -> dict:
    text = content.strip()
    if text.startswith("```json") and text.endswith("```"):
        text = text[7:-3].strip()
    elif text.startswith("```") and text.endswith("```"):
        text = text[3:-3].strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        raise VisionTranscriptionError(f"model did not return complete JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise VisionTranscriptionError("model JSON root must be an object")
    return obj


def _uncertainty(value: object, location: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise VisionTranscriptionError(f"{location}.uncertainty must be a string array")
    return value


def parse_vision_response(response: dict, *, stage: Literal["junior", "senior"], pdf_page: int) -> dict:
    """Validate LM Studio's response and preserve a trace for page review.

    The returned ``entries`` are in left-column then right-column order. A
    missing value becomes an explicit uncertainty; it is never inferred here.
    """
    if stage not in ("junior", "senior") or pdf_page < 1:
        raise ValueError("stage must be junior/senior and pdf_page must be positive")
    try:
        choice = response["choices"][0]
        finish_reason = choice["finish_reason"]
        raw_response = choice["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise VisionTranscriptionError("LM Studio response has no complete chat choice") from exc
    if finish_reason != "stop":
        raise VisionTranscriptionError(f"model stopped without finishing page: {finish_reason!r}")
    if not isinstance(raw_response, str) or not raw_response.strip():
        raise VisionTranscriptionError("model returned empty or non-text content")

    obj = _json_text(raw_response)
    if any(key not in obj for key in ("kind", "reason", "printed_page", "columns", "uncertainty")):
        raise VisionTranscriptionError("page JSON must include kind, reason, printed_page, columns, uncertainty")
    kind = obj["kind"]
    reason = obj["reason"]
    if kind not in ("vocab", "non_vocab"):
        raise VisionTranscriptionError("kind must be vocab or non_vocab")
    if kind == "non_vocab" and (not isinstance(reason, str) or not reason.strip()):
        raise VisionTranscriptionError("non_vocab page needs a reason")
    if kind == "vocab" and reason is not None:
        raise VisionTranscriptionError("vocab page reason must be null")
    printed_page = obj["printed_page"]
    if printed_page is not None and not isinstance(printed_page, (str, int)):
        raise VisionTranscriptionError("printed_page must be a string, integer, or null")
    if isinstance(printed_page, int):
        printed_page = str(printed_page)
    columns = obj["columns"]
    if not isinstance(columns, dict) or any(side not in columns for side in ("left", "right")):
        raise VisionTranscriptionError("page JSON must contain left and right columns")

    issues = _uncertainty(obj["uncertainty"], "page")
    if kind == "vocab" and printed_page is None:
        issues.append("printed_page is unreadable")
    cleaned: dict[str, list[dict]] = {}
    for side in ("left", "right"):
        source = columns[side]
        if not isinstance(source, list):
            raise VisionTranscriptionError(f"{side} column must be an array")
        cleaned[side] = []
        for position, item in enumerate(source, 1):
            location = f"{side}[{position}]"
            if not isinstance(item, dict) or any(k not in item for k in ("word", "zh", "ref", "raw", "uncertainty")):
                raise VisionTranscriptionError(f"{location} lacks required fields")
            for key in ("word", "zh", "ref", "raw"):
                value = item[key]
                if value is not None and not isinstance(value, str):
                    raise VisionTranscriptionError(f"{location}.{key} must be text or null")
            word = item["word"]
            raw = item["raw"]
            if not isinstance(word, str) or not word.strip() or not isinstance(raw, str) or not raw.strip():
                raise VisionTranscriptionError(f"{location} needs nonempty word and raw")
            entry_issues = _uncertainty(item["uncertainty"], location)
            if item["zh"] is None or not item["zh"].strip():
                entry_issues.append("Chinese definition is unreadable")
            if item["ref"] is None or not item["ref"].strip():
                entry_issues.append("printed reference is unreadable")
            else:
                ref = item["ref"].strip()
                if stage == "junior" and not ref.lower().startswith("p."):
                    entry_issues.append("junior reference is not a printed p. page")
                if stage == "senior" and not (ref.startswith("(") and ref.endswith(")")):
                    entry_issues.append("senior reference is not a parenthesized Unit")
            cleaned[side].append({
                "word": word,
                "zh": item["zh"],
                "ref": item["ref"],
                "raw": raw,
                "uncertainty": entry_issues,
                "column": side,
                "source_pdf_page": pdf_page,
            })
            issues.extend(f"{location}: {issue}" for issue in entry_issues)

    if kind == "vocab" and not (cleaned["left"] or cleaned["right"]):
        raise VisionTranscriptionError("vocab page has no entries")
    if kind == "non_vocab" and (cleaned["left"] or cleaned["right"]):
        raise VisionTranscriptionError("non_vocab page contains entries")

    return {
        "source_pdf_page": pdf_page,
        "kind": kind,
        "reason": reason,
        "printed_page": printed_page,
        "columns": cleaned,
        "entries": cleaned["left"] + cleaned["right"],
        "uncertainty": issues,
        "raw_response": raw_response,
        "model": response.get("model"),
    }


def transcribe_page(
    image_path: Path,
    *,
    stage: Literal["junior", "senior"],
    pdf_page: int,
    model: str = GEMMA_MODEL,
    base_url: str | None = None,
    timeout: float = 180,
    max_tokens: int = 6144,
) -> dict:
    """Send an unmodified complete page image to LM Studio's chat API.

    LM Studio must already be running. This does not crop the page, retry a
    truncated response, or write output; callers must gate publication on
    independent comparison with the source PDF.
    """
    if stage not in ("junior", "senior") or pdf_page < 1:
        raise ValueError("stage must be junior/senior and pdf_page must be positive")
    image_path = Path(image_path)
    if not image_path.is_file():
        raise FileNotFoundError(image_path)
    mime = mimetypes.guess_type(image_path.name)[0]
    if mime not in ("image/jpeg", "image/png", "image/webp"):
        raise ValueError("image must be JPEG, PNG, or WebP")
    image_data = base64.b64encode(image_path.read_bytes()).decode("ascii")
    body = {
        "model": model,
        "temperature": 0,
        "max_tokens": max_tokens,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "pep_vocabulary_page", "schema": _PAGE_SCHEMA},
        },
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": _prompt(stage)},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_data}"}},
            ],
        }],
    }
    url = (base_url or _load_base_url()).rstrip("/") + "/v1/chat/completions"
    request = Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as stream:
            response = json.load(stream)
    except HTTPError as exc:
        detail = exc.read(500).decode("utf-8", errors="replace")
        raise VisionTranscriptionError(f"LM Studio HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise VisionTranscriptionError(f"cannot connect to LM Studio at {url}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise VisionTranscriptionError(f"LM Studio returned invalid API JSON: {exc}") from exc
    if not isinstance(response, dict):
        raise VisionTranscriptionError("LM Studio API response must be an object")
    return parse_vision_response(response, stage=stage, pdf_page=pdf_page)
