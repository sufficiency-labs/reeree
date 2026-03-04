"""Tests for reeree.daemon_executor — the core execution pipeline."""

import json
import subprocess

import pytest

from reeree.config import Config
from reeree.plan import Step
from reeree.daemon_executor import _parse_llm_json, dispatch_step


class TestParseLlmJson:
    """Test the robust JSON parser that handles malformed LLM output."""

    def test_clean_json(self):
        result = _parse_llm_json('{"actions": [], "summary": "done"}')
        assert result == {"actions": [], "summary": "done"}

    def test_json_with_markdown_fences(self):
        result = _parse_llm_json('```json\n{"actions": [], "summary": "done"}\n```')
        assert result is not None
        assert result["summary"] == "done"

    def test_json_with_leading_text(self):
        result = _parse_llm_json('Here is the result:\n{"actions": [], "summary": "done"}')
        assert result is not None
        assert result["summary"] == "done"

    def test_json_with_trailing_text(self):
        result = _parse_llm_json('{"actions": [], "summary": "done"}\n\nLet me know if you need more.')
        assert result is not None
        assert result["summary"] == "done"

    def test_truncated_json(self):
        """Parser should handle JSON that got cut off."""
        # This simulates a model that ran out of tokens
        result = _parse_llm_json('{"actions": [{"type": "read", "path": "file.py"}], "summary": "read')
        # May or may not parse — should not crash
        assert result is None or isinstance(result, dict)

    def test_empty_input(self):
        result = _parse_llm_json("")
        assert result is None

    def test_no_json_at_all(self):
        result = _parse_llm_json("This is just plain text with no JSON.")
        assert result is None

    def test_nested_json(self):
        data = {
            "actions": [
                {"type": "edit", "path": "file.py", "old": "def foo():", "new": "def bar():"}
            ],
            "summary": "renamed function",
        }
        result = _parse_llm_json(json.dumps(data))
        assert result is not None
        assert len(result["actions"]) == 1
        assert result["actions"][0]["type"] == "edit"

    def test_json_with_escaped_newlines(self):
        text = '{"actions": [{"type": "edit", "path": "f.py", "old": "line1\\nline2", "new": "line1\\nline2\\nline3"}], "summary": "added line"}'
        result = _parse_llm_json(text)
        assert result is not None
        assert "\\n" in result["actions"][0]["old"] or "\n" in result["actions"][0]["old"]


class TestDispatchStep:
    """End-to-end daemon execution tests. Require API key and git project."""

    @pytest.fixture
    def sandbox(self, tmp_project):
        """A tmp project with a file to edit."""
        (tmp_project / "app.py").write_text(
            'def greet(name):\n    print("Hello " + name)\n\ngreet("world")\n'
        )
        subprocess.run(["git", "add", "-A"], cwd=tmp_project, capture_output=True)
        subprocess.run(["git", "commit", "-m", "add app.py"], cwd=tmp_project, capture_output=True)
        return tmp_project

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not Config().api_key,
        reason="No together.ai API key available",
    )
    async def test_edit_step(self, sandbox):
        """Daemon executes an edit step and commits."""
        config = Config()
        step = Step(
            description="Add a docstring to the greet function in app.py",
            files=["app.py"],
        )
        logs = []
        result = await dispatch_step(
            step=step,
            step_index=0,
            project_dir=sandbox,
            config=config,
            on_log=lambda msg: logs.append(msg),
        )

        assert result["status"] == "done"
        assert result.get("commit_hash") is not None
        # Verify file was actually changed
        content = (sandbox / "app.py").read_text()
        assert '"""' in content or "'''" in content  # docstring added

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not Config().api_key,
        reason="No together.ai API key available",
    )
    async def test_write_step(self, sandbox):
        """Daemon executes a write step (new file) and commits."""
        config = Config()
        step = Step(
            description="Create a new file called config.py with a Config class that has host and port attributes",
            files=[],
        )
        result = await dispatch_step(
            step=step,
            step_index=0,
            project_dir=sandbox,
            config=config,
            on_log=lambda msg: None,
        )

        assert result["status"] == "done"
        assert (sandbox / "config.py").exists()

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not Config().api_key,
        reason="No together.ai API key available",
    )
    async def test_logging_callback(self, sandbox):
        """on_log callback receives execution messages."""
        config = Config()
        step = Step(description="Add a comment to app.py", files=["app.py"])
        logs = []
        await dispatch_step(
            step=step,
            step_index=0,
            project_dir=sandbox,
            config=config,
            on_log=lambda msg: logs.append(msg),
        )
        assert len(logs) > 0
        assert any("Executing" in log for log in logs)
        assert any("LLM" in log for log in logs)
