"""Executors — apply changes to files, run shell commands, manage git.

Guardrails modeled on Claude Code's execution safety:
- Path containment: all file ops must stay within project_dir
- Command classification: safe/moderate/dangerous
- Blocked patterns: destructive commands that should never run unattended
- Autonomy levels: low/medium/high/full control what's allowed
- Timeouts on all shell commands
- Log everything before executing
"""

import re
import subprocess
from pathlib import Path
from dataclasses import dataclass


@dataclass
class ExecResult:
    """Result of an execution."""
    success: bool
    output: str
    action: str  # what was done: "file_edit", "shell", "git_commit"


# ── Command safety classification ──────────────────────────────────────

# Never run these regardless of autonomy level
BLOCKED_PATTERNS = [
    r"rm\s+(-[rf]+\s+)?/",          # rm -rf / or rm /
    r"rm\s+-[rf]*\s+~",              # rm -rf ~
    r"rm\s+-[rf]*\s+\.\.",           # rm -rf ..
    r"mkfs\.",                        # format filesystems
    r"dd\s+.*of=/dev/",              # dd to raw devices
    r":\(\)\s*\{\s*:\|:\s*&\s*\}",   # fork bomb
    r"curl.*\|\s*(ba)?sh",           # curl | sh
    r"wget.*\|\s*(ba)?sh",           # wget | sh
    r"eval\s+.*\$\(",               # eval with command substitution
    r"git\s+push\s+.*--force",       # force push
    r"git\s+push\s+.*-f\b",         # force push short flag
    r"git\s+reset\s+--hard",        # hard reset
    r"git\s+clean\s+-[dfx]+",       # git clean
    r"DROP\s+TABLE",                 # SQL drop
    r"DROP\s+DATABASE",              # SQL drop
    r"TRUNCATE\s+",                  # SQL truncate
    r">\s*/dev/sd",                  # write to raw disk
    r"chmod\s+777",                  # world-writable
    r"chmod\s+-R\s+777",            # recursive world-writable
    r"sudo\s+",                      # no sudo
    r"systemctl\s+(stop|disable|mask|reset-failed)",  # don't stop services
    r"kill\s+-9",                    # don't kill -9
    r"pkill\s+",                     # don't pkill
    r"ssh\s+.*rm\s+",               # remote deletion
]

# Commands that need "high" or "full" autonomy
DANGEROUS_PATTERNS = [
    r"git\s+push",                   # any push
    r"git\s+rebase",                 # rebase
    r"git\s+checkout\s+\.",          # discard changes
    r"git\s+restore\s+\.",           # discard changes
    r"rm\s+-[rf]",                   # recursive/force delete (within project)
    r"pip\s+install",                # install packages
    r"npm\s+install",               # install packages
    r"curl\s+",                      # network requests
    r"wget\s+",                      # network requests
    r"docker\s+",                    # container ops
    r"gh\s+pr\s+create",            # create PRs
    r"gh\s+issue",                  # GitHub issues
]

# Commands that need at least "medium" autonomy
MODERATE_PATTERNS = [
    r"git\s+add",                    # staging
    r"git\s+commit",                 # committing
    r"mv\s+",                        # move files
    r"cp\s+",                        # copy files
    r"mkdir\s+",                     # create dirs
    r"touch\s+",                     # create files
    r"python\s+",                    # run python
    r"pytest\s+",                    # run tests
    r"make\s+",                      # run make
]


def classify_command(command: str) -> str:
    """Classify a shell command: 'blocked', 'dangerous', 'moderate', or 'safe'.

    blocked = never run
    dangerous = needs high/full autonomy
    moderate = needs medium+ autonomy
    safe = always allowed (read-only: ls, cat, grep, git status, etc.)
    """
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return "blocked"
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return "dangerous"
    for pattern in MODERATE_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return "moderate"
    return "safe"


def check_autonomy(command: str, autonomy: str) -> tuple[bool, str]:
    """Check if a command is allowed under the current autonomy level.

    Returns (allowed, reason).
    """
    level = classify_command(command)

    if level == "blocked":
        return False, f"BLOCKED: '{command[:80]}' matches a blocked pattern (destructive/dangerous)"

    autonomy_rank = {"low": 0, "medium": 1, "high": 2, "full": 3}
    required = {"safe": 0, "moderate": 1, "dangerous": 2}
    current = autonomy_rank.get(autonomy, 1)
    needed = required.get(level, 1)

    if current < needed:
        return False, f"DENIED: '{command[:80]}' requires autonomy={list(autonomy_rank.keys())[needed]} (current: {autonomy})"

    return True, "ok"


# ── Path containment ───────────────────────────────────────────────────

def check_path_containment(path: Path, project_dir: Path) -> tuple[bool, str]:
    """Verify a file path is within the project directory.

    Prevents path traversal (../../etc/passwd) and writes outside the project.
    """
    try:
        resolved = path.resolve()
        project_resolved = project_dir.resolve()
        if not str(resolved).startswith(str(project_resolved)):
            return False, f"PATH ESCAPE: {path} resolves to {resolved}, outside project {project_resolved}"
        return True, "ok"
    except Exception as e:
        return False, f"PATH ERROR: {e}"


# ── Executors ──────────────────────────────────────────────────────────

def run_shell(command: str, cwd: Path, timeout: int = 60, autonomy: str = "medium") -> ExecResult:
    """Run a shell command with safety checks."""
    # Check autonomy
    allowed, reason = check_autonomy(command, autonomy)
    if not allowed:
        return ExecResult(success=False, output=reason, action="shell")

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


def write_file(path: Path, content: str, project_dir: Path | None = None) -> ExecResult:
    """Write content to a file with path containment check."""
    if project_dir:
        ok, reason = check_path_containment(path, project_dir)
        if not ok:
            return ExecResult(success=False, output=reason, action="file_edit")

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return ExecResult(success=True, output=f"Wrote {len(content)} chars to {path}", action="file_edit")
    except Exception as e:
        return ExecResult(success=False, output=str(e), action="file_edit")


def edit_file(path: Path, old: str, new: str, project_dir: Path | None = None) -> ExecResult:
    """Replace old text with new text in a file, with path containment."""
    if project_dir:
        ok, reason = check_path_containment(path, project_dir)
        if not ok:
            return ExecResult(success=False, output=reason, action="file_edit")

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
