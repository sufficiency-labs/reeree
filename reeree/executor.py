"""Executors — apply changes to files, run shell commands, manage git."""

import subprocess
from pathlib import Path
from dataclasses import dataclass


@dataclass
class ExecResult:
    """Result of an execution."""
    success: bool
    output: str
    action: str  # what was done: "file_edit", "shell", "git_commit"


def run_shell(command: str, cwd: Path, timeout: int = 60) -> ExecResult:
    """Run a shell command and return the result."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout
        if result.stderr:
            output += f"\nSTDERR:\n{result.stderr}"
        return ExecResult(
            success=result.returncode == 0,
            output=output.strip(),
            action="shell",
        )
    except subprocess.TimeoutExpired:
        return ExecResult(success=False, output=f"Command timed out after {timeout}s", action="shell")
    except Exception as e:
        return ExecResult(success=False, output=str(e), action="shell")


def write_file(path: Path, content: str) -> ExecResult:
    """Write content to a file."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return ExecResult(success=True, output=f"Wrote {len(content)} chars to {path}", action="file_edit")
    except Exception as e:
        return ExecResult(success=False, output=str(e), action="file_edit")


def edit_file(path: Path, old: str, new: str) -> ExecResult:
    """Replace old text with new text in a file."""
    try:
        content = path.read_text()
        if old not in content:
            return ExecResult(success=False, output=f"'{old[:50]}...' not found in {path}", action="file_edit")
        updated = content.replace(old, new, 1)
        path.write_text(updated)
        return ExecResult(success=True, output=f"Replaced in {path}", action="file_edit")
    except Exception as e:
        return ExecResult(success=False, output=str(e), action="file_edit")


def git_commit(message: str, cwd: Path, files: list[str] | None = None) -> ExecResult:
    """Stage files and create a git commit."""
    try:
        if files:
            for f in files:
                subprocess.run(["git", "add", f], cwd=str(cwd), check=True)
        else:
            subprocess.run(["git", "add", "-A"], cwd=str(cwd), check=True)

        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=str(cwd),
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            # Get the commit hash
            hash_result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(cwd),
                capture_output=True,
                text=True,
            )
            commit_hash = hash_result.stdout.strip()
            return ExecResult(success=True, output=f"Committed: {commit_hash} {message}", action="git_commit")
        else:
            return ExecResult(success=False, output=result.stderr.strip(), action="git_commit")
    except Exception as e:
        return ExecResult(success=False, output=str(e), action="git_commit")


def git_revert_last(cwd: Path) -> ExecResult:
    """Revert the last commit (undo a step)."""
    return run_shell("git revert --no-edit HEAD", cwd)
