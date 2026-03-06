"""Tests for reeree.claude_backend — Claude Code subprocess backend."""

import json
import shutil
from unittest.mock import patch, AsyncMock, MagicMock
from pathlib import Path

import pytest

from reeree.claude_backend import (
    _claude_available,
    _build_step_prompt,
    dispatch_step_claude,
    chat_claude,
)
from reeree.config import Config
from reeree.plan import Step


class TestClaudeAvailable:
    def test_returns_bool(self):
        """_claude_available returns True or False depending on PATH."""
        result = _claude_available()
        assert isinstance(result, bool)

    def test_reflects_which(self):
        """Matches shutil.which behavior."""
        assert _claude_available() == (shutil.which("claude") is not None)


class TestBuildStepPrompt:
    def test_basic_step(self, tmp_path):
        """Prompt includes step description."""
        step = Step(description="Fix the bug in auth.py")
        prompt = _build_step_prompt(step, tmp_path)
        assert "Fix the bug in auth.py" in prompt

    def test_includes_files(self, tmp_path):
        """Prompt includes file hints."""
        step = Step(description="Update tests", files=["tests/test_auth.py"])
        prompt = _build_step_prompt(step, tmp_path)
        assert "test_auth.py" in prompt

    def test_includes_annotations(self, tmp_path):
        """Prompt includes annotations as instructions."""
        step = Step(description="Add retry", annotations=["max 3 retries", "exponential backoff"])
        prompt = _build_step_prompt(step, tmp_path)
        assert "max 3 retries" in prompt
        assert "exponential backoff" in prompt


class TestDispatchStepClaude:
    @pytest.mark.asyncio
    async def test_fails_without_claude(self, tmp_path):
        """Returns failure if claude CLI not found."""
        step = Step(description="test")
        config = Config(backend="claude-code")
        logs = []

        with patch("reeree.claude_backend._claude_available", return_value=False):
            result = await dispatch_step_claude(
                step=step, step_index=0, project_dir=tmp_path,
                config=config, on_log=logs.append,
            )

        assert result["status"] == "failed"
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_parses_json_output(self, tmp_path):
        """Parses JSON output from claude subprocess."""
        step = Step(description="test step")
        config = Config(backend="claude-code")

        mock_output = json.dumps({
            "session_id": "test-session-123",
            "result": "Step completed successfully",
            "cost": 0.005,
            "usage": {"input_tokens": 100, "output_tokens": 50},
        })

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(mock_output.encode(), b""))
        mock_proc.stderr = AsyncMock()
        mock_proc.stderr.readline = AsyncMock(return_value=b"")

        with patch("reeree.claude_backend._claude_available", return_value=True), \
             patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await dispatch_step_claude(
                step=step, step_index=0, project_dir=tmp_path,
                config=config,
            )

        assert result["status"] == "done"
        assert result["session_id"] == "test-session-123"
        assert result["cost"] == 0.005

    @pytest.mark.asyncio
    async def test_passes_session_id_for_resume(self, tmp_path):
        """Passes --resume when session_id is provided."""
        step = Step(description="continue work")
        config = Config(backend="claude-code")

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(
            json.dumps({"session_id": "s2", "result": "ok"}).encode(), b""
        ))
        mock_proc.stderr = AsyncMock()
        mock_proc.stderr.readline = AsyncMock(return_value=b"")

        captured_cmd = []

        async def capture_exec(*args, **kwargs):
            captured_cmd.extend(args)
            return mock_proc

        with patch("reeree.claude_backend._claude_available", return_value=True), \
             patch("asyncio.create_subprocess_exec", side_effect=capture_exec):
            await dispatch_step_claude(
                step=step, step_index=0, project_dir=tmp_path,
                config=config, session_id="existing-session",
            )

        assert "--resume" in captured_cmd
        assert "existing-session" in captured_cmd


class TestChatClaude:
    @pytest.mark.asyncio
    async def test_fails_without_claude(self, tmp_path):
        """Returns error if claude CLI not found."""
        config = Config(backend="claude-code")

        with patch("reeree.claude_backend._claude_available", return_value=False):
            result = await chat_claude(
                user_msg="hello", project_dir=tmp_path, config=config,
            )

        assert "not found" in result["result"]

    @pytest.mark.asyncio
    async def test_returns_session_id(self, tmp_path):
        """Chat returns session_id for persistence."""
        config = Config(backend="claude-code")

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(
            json.dumps({"session_id": "chat-123", "result": "hello back"}).encode(), b""
        ))
        mock_proc.stderr = AsyncMock()
        mock_proc.stderr.readline = AsyncMock(return_value=b"")

        with patch("reeree.claude_backend._claude_available", return_value=True), \
             patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await chat_claude(
                user_msg="hello", project_dir=tmp_path, config=config,
            )

        assert result["session_id"] == "chat-123"
        assert result["result"] == "hello back"


class TestConfigBackend:
    def test_default_backend(self):
        """Default backend is together."""
        c = Config()
        assert c.backend == "together"

    def test_claude_code_backend(self):
        """Backend can be set to claude-code."""
        c = Config(backend="claude-code")
        assert c.backend == "claude-code"

    def test_claude_model_default(self):
        """Default claude model is sonnet."""
        c = Config()
        assert c.claude_model == "sonnet"

    def test_save_load_backend(self, tmp_path):
        """Backend setting survives save/load."""
        config_file = tmp_path / "config.json"
        c = Config(backend="claude-code", claude_model="opus")
        c.save(config_file)

        loaded = Config.load(config_file)
        assert loaded.backend == "claude-code"
        assert loaded.claude_model == "opus"
