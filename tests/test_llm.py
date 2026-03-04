"""Tests for reeree.llm — LLM API interface."""

import json
import pytest

from reeree.config import Config
from reeree.llm import chat


class TestChat:
    @pytest.mark.skipif(
        not Config().api_key,
        reason="No together.ai API key available",
    )
    def test_basic_response(self):
        """LLM returns a non-empty response."""
        c = Config()
        resp = chat(
            [{"role": "user", "content": "Reply with exactly: ok"}],
            c,
            system="Reply with one word only.",
        )
        assert len(resp) > 0

    @pytest.mark.skipif(
        not Config().api_key,
        reason="No together.ai API key available",
    )
    def test_json_response(self):
        """LLM can produce valid JSON when asked."""
        c = Config()
        resp = chat(
            [{"role": "user", "content": 'Reply with exactly: {"status": "ok"}'}],
            c,
            system="Reply with valid JSON only. No markdown, no explanation.",
        )
        data = json.loads(resp)
        assert data["status"] == "ok"

    @pytest.mark.skipif(
        not Config().api_key,
        reason="No together.ai API key available",
    )
    def test_system_prompt_included(self):
        """System prompt influences the response."""
        c = Config()
        resp = chat(
            [{"role": "user", "content": "What are you?"}],
            c,
            system="You are a calculator. You only respond with numbers.",
        )
        # Should be short/numeric-ish, not a long essay
        assert len(resp) < 500
