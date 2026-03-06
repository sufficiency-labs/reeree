"""Claude Code subprocess backend — persistent daemons via claude -p.

Each daemon is a Claude Code session. Sessions persist via --resume <session_id>,
so daemons retain full conversation context across turns. Claude Code handles
file operations (read/write/edit), shell commands, and search natively — no
need for our executor.py action parsing.

This is one backend option. The Together.ai/OpenAI-compatible API backend
in llm.py + daemon_executor.py is the other.
"""

import asyncio
import json
import shutil
from pathlib import Path
from typing import Callable

from .config import Config
from .plan import Step
from .voice import VOICE


def _claude_available() -> bool:
    """Check if claude CLI is on PATH."""
    return shutil.which("claude") is not None


def _build_step_prompt(step: Step, project_dir: Path) -> str:
    """Build the prompt for a step execution."""
    parts = [f"Execute this task: {step.description}"]

    if step.files or getattr(step, "file_hints", None):
        files = step.files or step.file_hints
        parts.append(f"Relevant files: {', '.join(files)}")

    if step.annotations:
        parts.append("Instructions:")
        for a in step.annotations:
            parts.append(f"- {a}")

    if getattr(step, "done_criteria", None):
        parts.append(f"Acceptance criteria: {step.done_criteria}")

    if getattr(step, "context_annotations", None):
        parts.append("Context:")
        for a in step.context_annotations:
            parts.append(f"- {a}")

    parts.append("\nWork in the current directory. Read files first if needed, "
                 "then make changes. Commit when done.")

    return "\n".join(parts)


async def dispatch_step_claude(
    step: Step,
    step_index: int,
    project_dir: Path,
    config: Config,
    on_log: Callable[[str], None] | None = None,
    should_continue: Callable[[], bool] | None = None,
    session_id: str = "",
) -> dict:
    """Execute a step using Claude Code subprocess.

    Returns dict with: status, summary, session_id, cost, commit_hash.
    """
    def log(msg: str) -> None:
        if on_log:
            on_log(msg)

    if not _claude_available():
        log("ERROR: claude CLI not found on PATH")
        return {"status": "failed", "error": "claude CLI not found"}

    prompt = _build_step_prompt(step, project_dir)
    log(f"Executing: {step.description}")
    log(f"Backend: claude-code ({config.claude_model})")

    cmd = [
        "claude", "-p", prompt,
        "--output-format", "json",
        "--model", config.claude_model,
        "--max-turns", "25",
        "--dangerously-skip-permissions",
        "--append-system-prompt", VOICE,
    ]

    if session_id:
        cmd.extend(["--resume", session_id])
        log(f"Resuming session: {session_id[:12]}...")

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(project_dir),
        )

        # Stream stderr for live logging
        async def read_stderr():
            while proc.stderr:
                line = await proc.stderr.readline()
                if not line:
                    break
                text = line.decode().rstrip()
                if text:
                    log(text)

        stderr_task = asyncio.create_task(read_stderr())

        # Wait for completion
        stdout_bytes, _ = await proc.communicate()
        await stderr_task

        stdout = stdout_bytes.decode().strip()

        if proc.returncode != 0 and not stdout:
            log(f"claude exited with code {proc.returncode}")
            # Detect auth errors
            if proc.returncode == 1:
                log("hint: run 'claude' interactively to authenticate")
            return {"status": "failed", "error": f"claude exit code {proc.returncode}"}

        # Parse JSON output
        try:
            output = json.loads(stdout)
        except json.JSONDecodeError:
            # Might be plain text output
            log(f"Non-JSON output: {stdout[:200]}")
            return {
                "status": "done" if proc.returncode == 0 else "failed",
                "summary": stdout[:500],
            }

        new_session_id = output.get("session_id", session_id)
        result_text = output.get("result", "")
        cost = output.get("cost", 0)
        usage = output.get("usage", {})

        tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        log(f"Done ({tokens} tokens, ${cost:.4f})")
        if result_text:
            # Show last ~200 chars of result as summary
            summary = result_text[-200:] if len(result_text) > 200 else result_text
            log(f"Result: {summary}")

        return {
            "status": "done" if proc.returncode == 0 else "failed",
            "summary": result_text[:500] if result_text else "",
            "session_id": new_session_id,
            "cost": cost,
            "usage": usage,
        }

    except Exception as e:
        log(f"ERROR: {e}")
        return {"status": "failed", "error": str(e)}


async def chat_claude(
    user_msg: str,
    project_dir: Path,
    config: Config,
    on_log: Callable[[str], None] | None = None,
    session_id: str = "",
    plan_context: str = "",
) -> dict:
    """Chat with Claude Code — persistent conversation via --resume.

    Returns dict with: result, session_id, cost, usage.
    """
    def log(msg: str) -> None:
        if on_log:
            on_log(msg)

    if not _claude_available():
        return {"result": "Error: claude CLI not found on PATH", "session_id": ""}

    # Build system context
    system_parts = [VOICE]
    if plan_context:
        system_parts.append(f"\nCurrent plan:\n{plan_context}")
    system_parts.append(
        "\nYou are an executor daemon. The user is working on a project. "
        "Help them by reading files, making edits, running commands. "
        "Be concise. Report what you did, not what you're going to do."
    )

    cmd = [
        "claude", "-p", user_msg,
        "--output-format", "json",
        "--model", config.claude_model,
        "--max-turns", "10",
        "--dangerously-skip-permissions",
        "--append-system-prompt", "\n".join(system_parts),
    ]

    if session_id:
        cmd.extend(["--resume", session_id])

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(project_dir),
        )

        async def read_stderr():
            while proc.stderr:
                line = await proc.stderr.readline()
                if not line:
                    break
                text = line.decode().rstrip()
                if text:
                    log(text)

        stderr_task = asyncio.create_task(read_stderr())
        stdout_bytes, _ = await proc.communicate()
        await stderr_task

        stdout = stdout_bytes.decode().strip()

        if proc.returncode != 0 and not stdout:
            hint = " — run 'claude' to authenticate" if proc.returncode == 1 else ""
            return {"result": f"claude exited with code {proc.returncode}{hint}", "session_id": session_id}

        try:
            output = json.loads(stdout)
        except json.JSONDecodeError:
            return {"result": stdout[:1000], "session_id": session_id}

        return {
            "result": output.get("result", ""),
            "session_id": output.get("session_id", session_id),
            "cost": output.get("cost", 0),
            "usage": output.get("usage", {}),
        }

    except Exception as e:
        return {"result": f"Error: {e}", "session_id": session_id}
