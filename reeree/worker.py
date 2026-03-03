"""Worker — a roomba that executes one step."""

import json
from pathlib import Path
from typing import Callable

from .config import Config
from .plan import Step
from .context import gather_context
from .llm import chat
from .executor import run_shell, write_file, edit_file, git_commit


WORKER_SYSTEM = """You are a worker executing ONE step of a plan. You receive focused context (only the files relevant to this step).

Execute the step. Respond with JSON:

{
  "actions": [
    {"type": "read", "path": "src/foo.py"},
    {"type": "shell", "command": "ls -la src/"},
    {"type": "write", "path": "src/foo.py", "content": "...full file..."},
    {"type": "edit", "path": "src/foo.py", "old": "text to find", "new": "replacement text"},
    {"type": "shell", "command": "python -m pytest tests/test_foo.py"}
  ],
  "summary": "What was done in one sentence"
}

Action types:
- "read": read a file to gather info before acting
- "shell": run a shell command
- "write": write/create a file (provide full content)
- "edit": replace text in an existing file (old must match exactly)

Rules:
- Do EXACTLY what the step says. Nothing more.
- If the step has acceptance criteria (done: ...), verify them.
- If annotations reference other docs, they've been included in your context. Use them.
- Respond ONLY with JSON."""


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

    log(f"Starting: {step.description}")

    # Gather focused context
    context = gather_context(step, project_dir, config.max_context_tokens * 4)
    log(f"Context loaded: {len(context)} chars")

    # Build the prompt with annotations
    prompt_parts = [f"Project context:\n{context}"]
    prompt_parts.append(f"\nStep to execute: {step.description}")

    if step.files or step.file_hints:
        files = step.files or step.file_hints
        prompt_parts.append(f"Files: {', '.join(files)}")

    if step.context_annotations:
        prompt_parts.append(f"Additional instructions:\n" + "\n".join(f"- {a}" for a in step.context_annotations))

    if step.done_criteria:
        prompt_parts.append(f"Acceptance criteria: {step.done_criteria}")

    prompt_parts.append("\nExecute this step. Respond with JSON actions.")

    messages = [{"role": "user", "content": "\n\n".join(prompt_parts)}]

    # Call LLM
    log("Calling LLM...")
    try:
        response = chat(messages, config, system=WORKER_SYSTEM)
    except Exception as e:
        log(f"LLM ERROR: {e}")
        return {"status": "failed", "error": str(e)}

    # Parse response
    try:
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]
        data = json.loads(text)
        actions = data.get("actions", [])
        summary = data.get("summary", "")
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        log(f"PARSE ERROR: {e}")
        log(f"Raw response: {response[:500]}")
        return {"status": "failed", "error": f"Failed to parse LLM response: {e}"}

    # Execute actions
    log(f"Executing {len(actions)} actions...")
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
                log(f"  EDIT FAILED: {result.output}")

    # Check results
    all_ok = all(r.success for r in results) if results else True

    if all_ok:
        # Git commit
        commit_result = git_commit(f"reeree: {step.description}", project_dir)
        if commit_result.success:
            log(f"Committed: {commit_result.output}")
            commit_hash = None
            # Extract hash from output
            for word in commit_result.output.split():
                if len(word) == 7 and all(c in "0123456789abcdef" for c in word):
                    commit_hash = word
                    break
            log(f"DONE: {summary}")
            return {"status": "done", "commit_hash": commit_hash, "summary": summary}
        else:
            log(f"Commit failed: {commit_result.output}")
            return {"status": "done", "commit_hash": None, "summary": summary}
    else:
        failures = [r.output for r in results if not r.success]
        log(f"FAILED: {'; '.join(failures)}")
        return {"status": "failed", "error": "; ".join(failures)}
