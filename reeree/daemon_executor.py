"""Daemon executor — multi-turn step execution.

Each dispatched daemon is a persistent LLM conversation, not a one-shot call.
The daemon calls the LLM, executes actions, feeds results back as the next
message, and loops until the LLM signals done or a turn limit is hit.

This means a daemon can: read a file → understand it → edit it → run tests →
see the failure → fix it. Like a process, not a function call.
"""

import json
from pathlib import Path
from typing import Callable

from .config import Config
from .daemon_registry import DaemonKind
from .plan import Step
from .context import gather_context
from .llm import chat_async
from .router import route_model
from .executor import run_shell, write_file, edit_file, git_commit, ExecResult


MAX_TURNS = 10  # Safety limit — daemon can't loop forever


EXECUTOR_SYSTEM = """Step execution daemon. Multi-turn action loop: respond with actions,
see results, respond again. Continue until the step is DONE.

Voice: ship's computer — direct, informational, no hedging. Report what you did and what
happened, not what you're "going to" do. No "I think", "I'll try", "Let me". Just act.

RESPOND WITH VALID YAML ONLY. No markdown, no explanation, no text outside the YAML.

Action types:
```yaml
actions:
  - type: read
    path: file.py
  - type: shell
    command: "pytest tests/ -v"
  - type: write
    path: file.py
    content: |
      full file content here
  - type: edit
    path: file.py
    old: "exact old text"
    new: "new text"
status: continue          # "continue" = I need more turns, "done" = step is complete
summary: "what I just did"
next_step_notes:          # OPTIONAL — only on final turn, pass to next step
  - "observation for whoever works on the next step"
```

WORKFLOW:
1. First turn: read the relevant files to understand the code.
2. Middle turns: make edits, write files, run commands. See results. Fix issues.
3. Final turn: verify your work (run tests if applicable), set status: done.

RULES:
- You MUST set status to "done" when the step is complete.
- If status is "continue", you WILL get another turn with the results of your actions.
- Read-only first turns are fine — you need to understand before you edit.
- But you MUST make actual changes (write/edit/shell) before setting status: done.
- Use edit (old/new) for surgical changes. Use write for new files or rewrites.
- Use YAML block scalars (|) for multi-line content.
- You may wrap YAML in ```yaml fences.
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


def _execute_actions(
    actions: list[dict],
    project_dir: Path,
    config: Config,
    log: Callable[[str], None],
) -> tuple[list[ExecResult], list[str]]:
    """Execute a list of actions. Returns (results, feedback_lines).

    feedback_lines are human-readable strings describing what happened,
    suitable for feeding back to the LLM as context for the next turn.
    """
    results = []
    feedback = []

    for action in actions:
        action_type = action.get("type", "unknown")

        if action_type == "read":
            path = project_dir / action["path"]
            if path.exists():
                content = path.read_text()
                log(f"> read {action['path']} ({len(content)} chars)")
                # Feed file content back to the LLM
                if len(content) > 8000:
                    feedback.append(f"=== {action['path']} ({len(content)} chars, truncated) ===\n{content[:8000]}\n... (truncated)")
                else:
                    feedback.append(f"=== {action['path']} ===\n{content}")
            else:
                log(f"> read {action['path']} — NOT FOUND")
                feedback.append(f"ERROR: {action['path']} does not exist")

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
            feedback.append(f"$ {action['command']}\n{'OK' if result.success else 'FAILED'}: {result.output[:2000]}")

        elif action_type == "write":
            path = project_dir / action["path"]
            content = action.get("content", "")
            log(f"> write {action['path']} ({len(content)} chars)")
            result = write_file(path, content, project_dir=project_dir)
            results.append(result)
            feedback.append(f"write {action['path']}: {'OK' if result.success else 'FAILED'} — {result.output}")

        elif action_type == "edit":
            path = project_dir / action["path"]
            log(f"> edit {action['path']}")
            result = edit_file(path, action["old"], action["new"], project_dir=project_dir)
            results.append(result)
            if not result.success:
                log(f"  FAILED: {result.output}")
            feedback.append(f"edit {action['path']}: {'OK' if result.success else 'FAILED'} — {result.output}")

        else:
            feedback.append(f"Unknown action type: {action_type}")

    return results, feedback


async def dispatch_step(
    step: Step,
    step_index: int,
    project_dir: Path,
    config: Config,
    on_log: Callable[[str], None] | None = None,
    should_continue: Callable[[], bool] | None = None,
) -> dict:
    """Execute a single step via multi-turn LLM conversation.

    The daemon loops: call LLM → execute actions → feed results back → repeat.
    Stops when LLM sets status: done, or turn limit is hit.
    Returns result dict with status, commit hash, summary, next_step_notes.
    """

    def log(msg: str) -> None:
        if on_log:
            on_log(msg)

    log(f"Executing: {step.description}")

    # Gather focused context
    context = gather_context(step, project_dir, config.max_context_tokens * 4)
    log(f"Context: {len(context)} chars")

    # Build initial prompt
    prompt_parts = [f"Project context:\n{context}"]
    prompt_parts.append(f"\nStep to execute: {step.description}")

    if step.files or step.file_hints:
        files = step.files or step.file_hints
        prompt_parts.append(f"Relevant files: {', '.join(files)}")

    if step.context_annotations:
        prompt_parts.append("Instructions:\n" + "\n".join(f"- {a}" for a in step.context_annotations))

    if step.done_criteria:
        prompt_parts.append(f"Acceptance criteria: {step.done_criteria}")

    prompt_parts.append("\nBegin executing this step. Read files first if needed, then make changes.")

    # Persistent conversation — this is the key difference from one-shot
    messages = [{"role": "user", "content": "\n\n".join(prompt_parts)}]

    all_results: list[ExecResult] = []
    has_mutations = False
    last_summary = ""
    next_step_notes = []

    # Route to best model for this task
    choice = route_model(step.description, DaemonKind.STEP, config)
    log(f"Model: {choice.model} (tier={choice.tier})")

    for turn in range(MAX_TURNS):
        # Check if daemon was killed or paused
        if should_continue and not should_continue():
            log("Daemon stopped (killed or paused)")
            return {"status": "failed", "error": "Daemon stopped by user",
                    "next_step_notes": next_step_notes}

        log(f"LLM call (turn {turn + 1}/{MAX_TURNS})...")

        try:
            response = await chat_async(
                messages, config, system=EXECUTOR_SYSTEM,
                model_override=choice.model,
                api_base_override=choice.api_base,
                api_key_override=choice.api_key,
            )
        except Exception as e:
            log(f"ERROR: {e}")
            return {"status": "failed", "error": str(e)}

        # Parse response
        data = _parse_llm_response(response)
        if data is None:
            log(f"PARSE ERROR (turn {turn + 1}) — raw response:")
            log(response[:500])
            # Give the LLM one more chance with a nudge
            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": "That was not valid YAML. Respond with YAML only. Format: actions: [...], status: continue/done, summary: '...'"})
            continue

        actions = data.get("actions", [])
        status = data.get("status", "done")  # default to done for backwards compat
        last_summary = data.get("summary", last_summary)
        turn_notes = data.get("next_step_notes", [])
        if turn_notes:
            next_step_notes = turn_notes  # last turn's notes win

        log(f"Turn {turn + 1}: {len(actions)} actions, status={status}")

        # Track mutations
        turn_has_mutations = any(
            action.get("type") in ("write", "edit", "shell")
            for action in actions
        )
        if turn_has_mutations:
            has_mutations = True

        # Execute actions and collect feedback
        results, feedback = _execute_actions(actions, project_dir, config, log)
        all_results.extend(results)

        # Check if done
        if status == "done":
            break

        # Feed results back for next turn
        messages.append({"role": "assistant", "content": response})
        feedback_text = "\n\n".join(feedback) if feedback else "No output from actions."
        messages.append({"role": "user", "content": f"Results from your actions:\n\n{feedback_text}\n\nContinue executing the step. When done, set status: done."})

    else:
        # Hit turn limit
        log(f"WARNING: hit {MAX_TURNS}-turn limit")

    # Final assessment
    if not has_mutations:
        log("WARNING: daemon made no changes across all turns")
        return {"status": "failed", "error": "Daemon made no changes (read-only)",
                "next_step_notes": next_step_notes}

    all_ok = all(r.success for r in all_results) if all_results else True

    if all_ok:
        commit_result = git_commit(f"reeree: {step.description}", project_dir)
        if commit_result.success:
            log(f"Committed: {commit_result.output}")
            commit_hash = None
            for word in commit_result.output.split():
                if len(word) == 7 and all(c in "0123456789abcdef" for c in word):
                    commit_hash = word
                    break
            log(f"Done: {last_summary}")
            if next_step_notes:
                log(f"Notes for next step: {next_step_notes}")
            return {"status": "done", "commit_hash": commit_hash, "summary": last_summary,
                    "next_step_notes": next_step_notes}
        else:
            log(f"Commit failed: {commit_result.output}")
            return {"status": "failed", "error": f"Commit failed: {commit_result.output}",
                    "summary": last_summary, "next_step_notes": next_step_notes}
    else:
        failures = [r.output for r in all_results if not r.success]
        log(f"FAILED: {'; '.join(failures)}")
        return {"status": "failed", "error": "; ".join(failures),
                "next_step_notes": next_step_notes}
