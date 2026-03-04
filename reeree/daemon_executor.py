"""Daemon executor — dispatches and runs a step."""

import json
from pathlib import Path
from typing import Callable

from .config import Config
from .plan import Step
from .context import gather_context
from .llm import chat, chat_async
from .executor import run_shell, write_file, edit_file, git_commit


EXECUTOR_SYSTEM = """You execute ONE step of a coding plan.

RESPOND WITH VALID JSON ONLY. No markdown, no explanation, no text outside the JSON.

Format:
{"actions": [<action>, ...], "summary": "one sentence"}

Action types:
{"type": "read", "path": "file.py"}
{"type": "shell", "command": "ls -la"}
{"type": "write", "path": "file.py", "content": "full file content here"}
{"type": "edit", "path": "file.py", "old": "exact old text", "new": "new text"}

IMPORTANT:
- old/new strings must be valid JSON strings (escape newlines as \\n, quotes as \\")
- Do EXACTLY what the step says, nothing more
- ONLY output the JSON object, nothing else"""


def _parse_llm_json(text: str) -> dict | None:
    """Parse JSON from LLM output, handling common malformations."""
    text = text.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if "```" in text:
            text = text.rsplit("```", 1)[0]

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find the first { and try to parse from there
    brace_start = text.find("{")
    if brace_start == -1:
        return None

    # Try progressively shorter substrings (truncated JSON)
    substr = text[brace_start:]
    try:
        return json.loads(substr)
    except json.JSONDecodeError:
        pass

    # Try to find matching closing brace by counting
    depth = 0
    for i, c in enumerate(substr):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(substr[:i + 1])
                except json.JSONDecodeError:
                    pass
                break

    # Last resort: try to fix truncated JSON by closing brackets
    for suffix in ["]}}", "]}", "}", '"}]}', '"]}']:
        try:
            return json.loads(substr + suffix)
        except json.JSONDecodeError:
            pass

    return None


async def dispatch_step(
    step: Step,
    step_index: int,
    project_dir: Path,
    config: Config,
    on_log: Callable[[str], None] | None = None,
) -> dict:
    """Execute a single step. Returns result dict with status and commit hash."""

    def log(msg: str) -> None:
        if on_log:
            on_log(msg)

    log(f"Executing: {step.description}")

    # Gather focused context
    context = gather_context(step, project_dir, config.max_context_tokens * 4)
    log(f"Context: {len(context)} chars")

    # Build prompt
    prompt_parts = [f"Project context:\n{context}"]
    prompt_parts.append(f"\nStep: {step.description}")

    if step.files or step.file_hints:
        files = step.files or step.file_hints
        prompt_parts.append(f"Files: {', '.join(files)}")

    if step.context_annotations:
        prompt_parts.append("Instructions:\n" + "\n".join(f"- {a}" for a in step.context_annotations))

    if step.done_criteria:
        prompt_parts.append(f"Acceptance criteria: {step.done_criteria}")

    prompt_parts.append("\nExecute. Respond with JSON actions.")

    messages = [{"role": "user", "content": "\n\n".join(prompt_parts)}]

    # LLM call
    log("LLM call...")
    try:
        response = await chat_async(messages, config, system=EXECUTOR_SYSTEM)
    except Exception as e:
        log(f"ERROR: {e}")
        return {"status": "failed", "error": str(e)}

    # Parse response — robust handling for small model output
    data = _parse_llm_json(response)
    if data is None:
        log(f"PARSE ERROR — raw response:")
        log(response[:500])
        return {"status": "failed", "error": "Failed to parse LLM response as JSON"}
    actions = data.get("actions", [])
    summary = data.get("summary", "")

    # Execute actions
    log(f"Actions: {len(actions)}")
    results = []
    for action in actions:
        action_type = action.get("type", "unknown")

        if action_type == "read":
            path = project_dir / action["path"]
            if path.exists():
                log(f"> read {action['path']} ({len(path.read_text())} chars)")
            else:
                log(f"> read {action['path']} — NOT FOUND")

        elif action_type == "shell":
            log(f"> $ {action['command']}")
            result = run_shell(action["command"], project_dir)
            if result.output:
                log(f"  {result.output[:200]}")
            results.append(result)

        elif action_type == "write":
            path = project_dir / action["path"]
            content = action.get("content", "")
            log(f"> write {action['path']} ({len(content)} chars)")
            result = write_file(path, content)
            results.append(result)

        elif action_type == "edit":
            path = project_dir / action["path"]
            log(f"> edit {action['path']}")
            result = edit_file(path, action["old"], action["new"])
            results.append(result)
            if not result.success:
                log(f"  FAILED: {result.output}")

    # Results
    all_ok = all(r.success for r in results) if results else True

    if all_ok:
        commit_result = git_commit(f"reeree: {step.description}", project_dir)
        if commit_result.success:
            log(f"Committed: {commit_result.output}")
            commit_hash = None
            for word in commit_result.output.split():
                if len(word) == 7 and all(c in "0123456789abcdef" for c in word):
                    commit_hash = word
                    break
            log(f"Done: {summary}")
            return {"status": "done", "commit_hash": commit_hash, "summary": summary}
        else:
            log(f"Commit failed: {commit_result.output}")
            return {"status": "done", "commit_hash": None, "summary": summary}
    else:
        failures = [r.output for r in results if not r.success]
        log(f"FAILED: {'; '.join(failures)}")
        return {"status": "failed", "error": "; ".join(failures)}
