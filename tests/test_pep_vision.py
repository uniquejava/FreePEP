"""Boundary checks for complete-page vision transcription responses."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from vocab_ocr.pep.vision import VisionTranscriptionError, _load_base_url, parse_vision_response


def reply(page: dict, finish_reason: str = "stop") -> dict:
    return {
        "model": "test-model",
        "choices": [{"finish_reason": finish_reason, "message": {"content": json.dumps(page)}}],
    }


class VisionResponseTests(unittest.TestCase):
    def test_base_url_comes_from_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("LM_STUDIO_BASE_URL=http://localhost:4321\n", encoding="utf-8")
            self.assertEqual(_load_base_url(env_file), "http://localhost:4321")

    def test_missing_env_file_fails_with_setup_instruction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(VisionTranscriptionError, "copy .env.sample to .env"):
                _load_base_url(Path(directory) / ".env")

    def test_preserves_left_then_right_with_original_references(self) -> None:
        page = {
            "kind": "vocab", "reason": None, "printed_page": "112",
            "columns": {
                "left": [{"word": "assessment", "zh": "评价；评定", "ref": "(4)",
                          "raw": "assessment n. 评价；评定 (4)", "uncertainty": []}],
                "right": [{"word": "assumption", "zh": "假定；假设", "ref": "(4)",
                           "raw": "assumption n. 假定；假设 (4)", "uncertainty": []}],
            },
            "uncertainty": [],
        }
        parsed = parse_vision_response(reply(page), stage="senior", pdf_page=120)
        self.assertEqual([e["word"] for e in parsed["entries"]], ["assessment", "assumption"])
        self.assertEqual(parsed["entries"][0]["ref"], "(4)")
        self.assertEqual(parsed["entries"][0]["source_pdf_page"], 120)
        self.assertEqual(parsed["printed_page"], "112")

    def test_truncated_response_is_never_accepted(self) -> None:
        page = {"kind": "non_vocab", "reason": "table of contents", "printed_page": None,
                "columns": {"left": [], "right": []}, "uncertainty": []}
        with self.assertRaisesRegex(VisionTranscriptionError, "without finishing"):
            parse_vision_response(reply(page, "length"), stage="junior", pdf_page=5)

    def test_empty_vocab_page_is_failure(self) -> None:
        page = {"kind": "vocab", "reason": None, "printed_page": "90",
                "columns": {"left": [], "right": []}, "uncertainty": []}
        with self.assertRaisesRegex(VisionTranscriptionError, "no entries"):
            parse_vision_response(reply(page), stage="junior", pdf_page=100)

    def test_unreadable_reference_becomes_review_issue(self) -> None:
        page = {
            "kind": "vocab", "reason": None, "printed_page": "90",
            "columns": {"left": [{"word": "role", "zh": "角色", "ref": None,
                                  "raw": "role n. 角色 p. ?", "uncertainty": ["page digit is blurred"]}],
                        "right": []},
            "uncertainty": [],
        }
        parsed = parse_vision_response(reply(page), stage="junior", pdf_page=126)
        self.assertTrue(any("reference is unreadable" in x for x in parsed["uncertainty"]))


if __name__ == "__main__":
    unittest.main()
