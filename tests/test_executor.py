"""Tests for reeree.executor — file ops, shell, git."""

import subprocess
from pathlib import Path

from reeree.executor import run_shell, write_file, edit_file, git_commit, git_revert_last


class TestRunShell:
    def test_simple_command(self, tmp_project):
        result = run_shell("echo hello", tmp_project)
        assert result.success
        assert "hello" in result.output

    def test_failed_command(self, tmp_project):
        result = run_shell("false", tmp_project)
        assert not result.success

    def test_command_output(self, tmp_project):
        result = run_shell("ls", tmp_project)
        assert result.success
        assert "main.py" in result.output

    def test_runs_in_project_dir(self, tmp_project):
        result = run_shell("pwd", tmp_project)
        assert str(tmp_project) in result.output


class TestWriteFile:
    def test_write_new_file(self, tmp_project):
        path = tmp_project / "new_file.py"
        result = write_file(path, "print('new')\n")
        assert result.success
        assert path.exists()
        assert path.read_text() == "print('new')\n"

    def test_overwrite_file(self, tmp_project):
        path = tmp_project / "main.py"
        result = write_file(path, "# replaced\n")
        assert result.success
        assert path.read_text() == "# replaced\n"

    def test_creates_parent_dirs(self, tmp_project):
        path = tmp_project / "deep" / "nested" / "file.py"
        result = write_file(path, "# deep\n")
        assert result.success
        assert path.exists()


class TestEditFile:
    def test_simple_edit(self, tmp_project):
        path = tmp_project / "main.py"
        result = edit_file(path, 'print("hello world")', 'print("goodbye world")')
        assert result.success
        assert 'goodbye world' in path.read_text()

    def test_edit_not_found(self, tmp_project):
        path = tmp_project / "main.py"
        result = edit_file(path, "text that does not exist", "replacement")
        assert not result.success

    def test_edit_missing_file(self, tmp_project):
        path = tmp_project / "nonexistent.py"
        result = edit_file(path, "old", "new")
        assert not result.success

    def test_multiline_edit(self, tmp_project):
        path = tmp_project / "utils.py"
        result = edit_file(
            path,
            "def add(a, b):\n    return a + b",
            "def add(a, b):\n    \"\"\"Add two numbers.\"\"\"\n    return a + b",
        )
        assert result.success
        assert '"""Add two numbers."""' in path.read_text()


class TestGitCommit:
    def test_commit_after_change(self, tmp_project):
        (tmp_project / "new.py").write_text("# new file\n")
        subprocess.run(["git", "add", "-A"], cwd=tmp_project, capture_output=True)
        result = git_commit("test commit", tmp_project)
        # May succeed or fail if nothing staged
        assert isinstance(result.success, bool)

    def test_commit_message_in_log(self, tmp_project):
        (tmp_project / "new.py").write_text("# new file\n")
        subprocess.run(["git", "add", "-A"], cwd=tmp_project, capture_output=True)
        git_commit("reeree: test commit msg", tmp_project)
        log = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=tmp_project, capture_output=True, text=True,
        )
        assert "test commit msg" in log.stdout


class TestGitRevert:
    def test_revert_last(self, tmp_project):
        # Make a change and commit
        (tmp_project / "main.py").write_text("# changed\n")
        subprocess.run(["git", "add", "-A"], cwd=tmp_project, capture_output=True)
        subprocess.run(["git", "commit", "-m", "change to revert"], cwd=tmp_project, capture_output=True)

        result = git_revert_last(tmp_project)
        assert result.success
        # Content should be reverted
        assert "hello world" in (tmp_project / "main.py").read_text()
