"""Tests for reeree.daemon_executor — the core execution pipeline."""

import json
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from reeree.config import Config
from reeree.plan import Step
from reeree.daemon_executor import (
    _parse_llm_response,
    _execute_actions,
    dispatch_step,
    MAX_TURNS,
)


class TestParseLlmResponse:
    """Test the YAML/JSON parser that handles LLM output."""

    def test_clean_json(self):
        result = _parse_llm_response('{"actions": [], "summary": "done"}')
        assert result["actions"] == []
        assert result["summary"] == "done"

    def test_json_with_markdown_fences(self):
        result = _parse_llm_response('```json\n{"actions": [], "summary": "done"}\n```')
        assert result is not None
        assert result["summary"] == "done"

    def test_clean_yaml(self):
        result = _parse_llm_response('actions:\n  - type: read\n    path: file.py\nsummary: "read it"')
        assert result is not None
        assert len(result["actions"]) == 1
        assert result["actions"][0]["type"] == "read"

    def test_yaml_with_markdown_fences(self):
        result = _parse_llm_response('```yaml\nactions:\n  - type: shell\n    command: "ls"\nsummary: "listed"\n```')
        assert result is not None
        assert result["actions"][0]["command"] == "ls"

    def test_json_with_leading_text(self):
        result = _parse_llm_response('Here is the result:\n{"actions": [], "summary": "done"}')
        assert result is not None
        assert result["summary"] == "done"

    def test_json_with_trailing_text(self):
        result = _parse_llm_response('{"actions": [], "summary": "done"}\n\nLet me know if you need more.')
        assert result is not None
        assert result["summary"] == "done"

    def test_truncated_json(self):
        """Parser should handle JSON that got cut off."""
        result = _parse_llm_response('{"actions": [{"type": "read", "path": "file.py"}], "summary": "read')
        # May or may not parse — should not crash
        assert result is None or isinstance(result, dict)

    def test_empty_input(self):
        result = _parse_llm_response("")
        assert result is None

    def test_no_structured_data(self):
        result = _parse_llm_response("This is just plain text with no YAML or JSON.")
        assert result is None

    def test_nested_json(self):
        data = {
            "actions": [
                {"type": "edit", "path": "file.py", "old": "def foo():", "new": "def bar():"}
            ],
            "summary": "renamed function",
        }
        result = _parse_llm_response(json.dumps(data))
        assert result is not None
        assert len(result["actions"]) == 1
        assert result["actions"][0]["type"] == "edit"

    def test_yaml_multiline_content(self):
        yaml_text = 'actions:\n  - type: write\n    path: test.py\n    content: |\n      def hello():\n          print("hello")\nsummary: "wrote file"'
        result = _parse_llm_response(yaml_text)
        assert result is not None
        assert "def hello" in result["actions"][0]["content"]

    def test_next_step_notes_parsed(self):
        yaml_text = 'actions: []\nsummary: "done"\nnext_step_notes:\n  - "found config at config.yaml"\n  - "needs error handling"'
        result = _parse_llm_response(yaml_text)
        assert result is not None
        assert result["next_step_notes"] == ["found config at config.yaml", "needs error handling"]

    def test_no_next_step_notes(self):
        yaml_text = 'actions: []\nsummary: "done"'
        result = _parse_llm_response(yaml_text)
        assert result is not None
        assert result.get("next_step_notes") is None or result.get("next_step_notes") == []


class TestExecuteActions:
    """Test action execution and feedback generation."""

    def test_read_existing_file(self, tmp_path):
        (tmp_path / "hello.py").write_text("print('hello')")
        config = Config()
        logs = []
        actions = [{"type": "read", "path": "hello.py"}]
        results, feedback = _execute_actions(actions, tmp_path, config, logs.append)
        assert len(results) == 0  # reads don't produce ExecResults
        assert len(feedback) == 1
        assert "print('hello')" in feedback[0]

    def test_read_missing_file(self, tmp_path):
        config = Config()
        actions = [{"type": "read", "path": "nope.py"}]
        results, feedback = _execute_actions(actions, tmp_path, config, lambda m: None)
        assert "does not exist" in feedback[0]

    def test_write_file(self, tmp_path):
        config = Config()
        actions = [{"type": "write", "path": "new.py", "content": "x = 1\n"}]
        results, feedback = _execute_actions(actions, tmp_path, config, lambda m: None)
        assert len(results) == 1
        assert results[0].success
        assert (tmp_path / "new.py").read_text() == "x = 1\n"
        assert "OK" in feedback[0]

    def test_edit_file(self, tmp_path):
        (tmp_path / "app.py").write_text("def foo():\n    pass\n")
        config = Config()
        actions = [{"type": "edit", "path": "app.py", "old": "pass", "new": "return 42"}]
        results, feedback = _execute_actions(actions, tmp_path, config, lambda m: None)
        assert results[0].success
        assert "return 42" in (tmp_path / "app.py").read_text()

    def test_edit_file_old_not_found(self, tmp_path):
        (tmp_path / "app.py").write_text("def foo():\n    pass\n")
        config = Config()
        actions = [{"type": "edit", "path": "app.py", "old": "NOPE", "new": "yes"}]
        results, feedback = _execute_actions(actions, tmp_path, config, lambda m: None)
        assert not results[0].success
        assert "FAILED" in feedback[0]

    def test_shell_safe_command(self, tmp_path):
        config = Config()
        actions = [{"type": "shell", "command": "echo hello"}]
        results, feedback = _execute_actions(actions, tmp_path, config, lambda m: None)
        assert results[0].success
        assert "hello" in feedback[0]

    def test_mixed_actions(self, tmp_path):
        (tmp_path / "f.py").write_text("old\n")
        config = Config()
        actions = [
            {"type": "read", "path": "f.py"},
            {"type": "edit", "path": "f.py", "old": "old", "new": "new"},
            {"type": "shell", "command": "echo done"},
        ]
        results, feedback = _execute_actions(actions, tmp_path, config, lambda m: None)
        assert len(results) == 2  # edit + shell (reads don't produce results)
        assert len(feedback) == 3
        assert "new" in (tmp_path / "f.py").read_text()


class TestMultiTurnDispatch:
    """Test multi-turn executor loop with mocked LLM."""

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
    async def test_two_turn_read_then_edit(self, sandbox):
        """Daemon reads on turn 1, edits on turn 2."""
        turn1 = (
            'actions:\n'
            '  - type: read\n'
            '    path: app.py\n'
            'status: continue\n'
            'summary: "read the file"\n'
        )
        turn2 = (
            'actions:\n'
            '  - type: edit\n'
            '    path: app.py\n'
            '    old: "def greet(name):"\n'
            '    new: "def greet(name):\\n    \\"\\"\\"Greet someone.\\"\\"\\""\n'
            'status: done\n'
            'summary: "added docstring"\n'
        )
        responses = iter([turn1, turn2])

        async def mock_chat(*args, **kwargs):
            return next(responses)

        config = Config()
        step = Step(description="Add a docstring to greet", files=["app.py"])
        logs = []

        with patch("reeree.daemon_executor.chat_async", side_effect=mock_chat):
            result = await dispatch_step(
                step=step, step_index=0, project_dir=sandbox,
                config=config, on_log=logs.append,
            )

        assert result["status"] == "done"
        assert result.get("commit_hash") is not None
        # Should have called LLM twice
        assert any("turn 1" in log for log in logs)
        assert any("turn 2" in log for log in logs)

    @pytest.mark.asyncio
    async def test_single_turn_done(self, sandbox):
        """Daemon can finish in one turn if it does everything at once."""
        response = (
            'actions:\n'
            '  - type: edit\n'
            '    path: app.py\n'
            '    old: "def greet(name):"\n'
            '    new: "def greet(name):\\n    \\"\\"\\"Greet.\\"\\"\\""\n'
            'status: done\n'
            'summary: "added docstring in one shot"\n'
        )

        async def mock_chat(*args, **kwargs):
            return response

        config = Config()
        step = Step(description="Add a docstring", files=["app.py"])

        with patch("reeree.daemon_executor.chat_async", side_effect=mock_chat):
            result = await dispatch_step(
                step=step, step_index=0, project_dir=sandbox,
                config=config, on_log=lambda m: None,
            )

        assert result["status"] == "done"

    @pytest.mark.asyncio
    async def test_read_only_succeeds(self, sandbox):
        """Read-only steps are valid work (understanding codebase, etc.)."""
        response = (
            'actions:\n'
            '  - type: read\n'
            '    path: app.py\n'
            'status: done\n'
            'summary: "just read it"\n'
        )

        async def mock_chat(*args, **kwargs):
            return response

        config = Config()
        step = Step(description="Do something", files=["app.py"])

        with patch("reeree.daemon_executor.chat_async", side_effect=mock_chat):
            result = await dispatch_step(
                step=step, step_index=0, project_dir=sandbox,
                config=config, on_log=lambda m: None,
            )

        assert result["status"] == "done"
        assert result["summary"] == "just read it"

    @pytest.mark.asyncio
    async def test_turn_limit(self, sandbox):
        """Daemon stops at MAX_TURNS even if LLM keeps saying continue."""
        response = (
            'actions:\n'
            '  - type: read\n'
            '    path: app.py\n'
            'status: continue\n'
            'summary: "still reading"\n'
        )

        async def mock_chat(*args, **kwargs):
            return response

        config = Config()
        step = Step(description="Infinite loop daemon", files=["app.py"])
        logs = []

        with patch("reeree.daemon_executor.chat_async", side_effect=mock_chat):
            result = await dispatch_step(
                step=step, step_index=0, project_dir=sandbox,
                config=config, on_log=logs.append,
            )

        # Hits turn limit, but only did reads — still counts as done (read-only)
        assert result["status"] == "done"
        assert any(f"{MAX_TURNS}-turn limit" in log for log in logs)

    @pytest.mark.asyncio
    async def test_parse_error_recovery(self, sandbox):
        """Daemon recovers from a parse error by nudging the LLM."""
        bad_response = "I'm not sure what to do here, let me think..."
        good_response = (
            'actions:\n'
            '  - type: write\n'
            '    path: notes.txt\n'
            '    content: "hello"\n'
            'status: done\n'
            'summary: "wrote notes"\n'
        )
        responses = iter([bad_response, good_response])

        async def mock_chat(*args, **kwargs):
            return next(responses)

        config = Config()
        step = Step(description="Write notes", files=[])

        with patch("reeree.daemon_executor.chat_async", side_effect=mock_chat):
            result = await dispatch_step(
                step=step, step_index=0, project_dir=sandbox,
                config=config, on_log=lambda m: None,
            )

        assert result["status"] == "done"

    @pytest.mark.asyncio
    async def test_feedback_contains_file_content(self, sandbox):
        """Read actions feed file content back to LLM."""
        messages_seen = []

        turn1 = (
            'actions:\n'
            '  - type: read\n'
            '    path: app.py\n'
            'status: continue\n'
            'summary: "reading"\n'
        )
        turn2 = (
            'actions:\n'
            '  - type: write\n'
            '    path: notes.txt\n'
            '    content: "done"\n'
            'status: done\n'
            'summary: "done"\n'
        )
        responses = iter([turn1, turn2])

        async def mock_chat(messages, *args, **kwargs):
            messages_seen.append(messages)
            return next(responses)

        config = Config()
        step = Step(description="Read and note", files=["app.py"])

        with patch("reeree.daemon_executor.chat_async", side_effect=mock_chat):
            await dispatch_step(
                step=step, step_index=0, project_dir=sandbox,
                config=config, on_log=lambda m: None,
            )

        # Second call should have file content in messages
        assert len(messages_seen) == 2
        last_messages = messages_seen[1]
        # Should contain the file content as feedback
        feedback_msg = [m for m in last_messages if m["role"] == "user" and "Results" in m.get("content", "")]
        assert len(feedback_msg) == 1
        assert "def greet" in feedback_msg[0]["content"]

    @pytest.mark.asyncio
    async def test_next_step_notes_from_final_turn(self, sandbox):
        """next_step_notes from the final turn are returned."""
        response = (
            'actions:\n'
            '  - type: write\n'
            '    path: x.py\n'
            '    content: "x=1"\n'
            'status: done\n'
            'summary: "created x"\n'
            'next_step_notes:\n'
            '  - "x.py uses global state"\n'
        )

        async def mock_chat(*args, **kwargs):
            return response

        config = Config()
        step = Step(description="Create x", files=[])

        with patch("reeree.daemon_executor.chat_async", side_effect=mock_chat):
            result = await dispatch_step(
                step=step, step_index=0, project_dir=sandbox,
                config=config, on_log=lambda m: None,
            )

        assert result["next_step_notes"] == ["x.py uses global state"]


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
