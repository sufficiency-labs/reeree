"""Daemon executor — dispatches and runs a step."""

import json
from pathlib import Path
from typing import Callable

from .config import Config
from .plan import Step
from .context import gather_context
from .llm import chat, chat_async
from .executor import run_shell, write_file, edit_file, git_commit


EXECUTOR_SYSTEM = """You are a daemon that EXECUTES one step of a coding plan.

You MUST actually make changes — write files, edit code, run commands.
DO NOT just read files and call it done. Reading is preparation, not execution.
If the step says "add X to file.py", you MUST include a write or edit action that adds X.

RESPOND WITH VALID YAML ONLY. No markdown, no explanation, no text outside the YAML.

Action types:
```yaml
actions:
  - type: read          # Read a file (for understanding before editing)
    path: file.py
  - type: shell         # Run a shell command
    command: "pytest tests/ -v"
  - type: write         # Write/create a file (full content)
    path: file.py
    content: |
      full file content here
  - type: edit          # Edit part of a file (search and replace)
    path: file.py
    old: "exact old text"
    new: "new text"
summary: "one sentence describing what was done"
next_step_notes:       # OPTIONAL — pass observations to the next step
  - "e.g. 'found config uses YAML not JSON'"
```

RULES:
- You MUST include at least one write, edit, or shell action. Read-only responses are WRONG.
- A typical step: read the relevant file(s), then edit or write the changes.
- Use edit (old/new) for surgical changes to existing files.
- Use write (full content) for new files or full rewrites.
- Use shell for running tests, installing packages, etc.
- Use YAML block scalars (|) for multi-line content in write actions.
- You may wrap the YAML in ```yaml fences if you prefer.
- Output ONLY the YAML, nothing else."""


def _parse_llm_response(text: str) -> dict | None:
    """Parse YAML or JSON from LLM output. Tries YAML first, falls back to JSON."""
    import yaml

    text = text.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if "```" in text:
            text = text.rsplit("```", 1)[0]
    text = text.strip()

    # Try YAML first (YAML is a superset of JSON, so this handles both)
    try:
        result = yaml.safe_load(text)
        if isinstance(result, dict) and ("actions" in result or "summary" in result):
            return result
    except Exception:
        pass

    # Try to find YAML/JSON in the text if there's surrounding prose
    # Look for 'actions:' line (YAML) or '{' (JSON)
    for marker in ["actions:", "{"]:
        idx = text.find(marker)
        if idx != -1:
            substr = text[idx:]
            try:
                result = yaml.safe_load(substr)
                if isinstance(result, dict):
                    return result
            except Exception:
                pass

    # Legacy JSON fallback with brace matching
    brace_start = text.find("{")
    if brace_start != -1:
        substr = text[brace_start:]
        try:
            return json.loads(substr)
        except json.JSONDecodeError:
            pass
        # Try to find matching closing brace
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

    prompt_parts.append("\nExecute this step NOW. Respond with YAML actions including at least one write, edit, or shell action.")

    messages = [{"role": "user", "content": "\n\n".join(prompt_parts)}]

    # LLM call
    log("LLM call...")
    try:
        response = await chat_async(messages, config, system=EXECUTOR_SYSTEM)
    except Exception as e:
        log(f"ERROR: {e}")
        return {"status": "failed", "error": str(e)}

    # Parse response — robust handling for small model output
    data = _parse_llm_response(response)
    if data is None:
        log(f"PARSE ERROR — raw response:")
        log(response[:500])
        return {"status": "failed", "error": "Failed to parse LLM response as JSON"}
    actions = data.get("actions", [])
    summary = data.get("summary", "")
    next_step_notes = data.get("next_step_notes", [])

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
            from .executor import classify_command
            classification = classify_command(action["command"])
            log(f"> $ {action['command']}  [{classification}]")
            result = run_shell(action["command"], project_dir, autonomy=config.autonomy)
            if result.output:
                log(f"  {result.output[:200]}")
            if not result.success and "BLOCKED" in result.output:
                log(f"  BLOCKED by safety guardrails")
            results.append(result)

        elif action_type == "write":
            path = project_dir / action["path"]
            content = action.get("content", "")
            log(f"> write {action['path']} ({len(content)} chars)")
            result = write_file(path, content, project_dir=project_dir)
            results.append(result)

        elif action_type == "edit":
            path = project_dir / action["path"]
            log(f"> edit {action['path']}")
            result = edit_file(path, action["old"], action["new"], project_dir=project_dir)
            results.append(result)
            if not result.success:
                log(f"  FAILED: {result.output}")

    # Check if any actual changes were made (not just reads)
    has_mutations = any(
        action.get("type") in ("write", "edit", "shell")
        for action in actions
    )
    if not has_mutations:
        log("WARNING: daemon only read files, made no changes")

    # Results
    all_ok = all(r.success for r in results) if results else True

    if not has_mutations:
        # Read-only response — report as incomplete, don't create empty commit
        return {"status": "failed", "error": "Daemon only read files, made no changes",
                "next_step_notes": next_step_notes}

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
            if next_step_notes:
                log(f"Notes for next step: {next_step_notes}")
            return {"status": "done", "commit_hash": commit_hash, "summary": summary,
                    "next_step_notes": next_step_notes}
        else:
            log(f"Commit failed: {commit_result.output}")
            return {"status": "done", "commit_hash": None, "summary": summary,
                    "next_step_notes": next_step_notes}
    else:
        failures = [r.output for r in results if not r.success]
        log(f"FAILED: {'; '.join(failures)}")
        return {"status": "failed", "error": "; ".join(failures),
                "next_step_notes": next_step_notes}
