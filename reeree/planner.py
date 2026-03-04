"""Planner — decompose a user intent into a step-by-step plan."""

import json
from pathlib import Path
from .llm import chat
from .plan import Plan, Step
from .config import Config
from .context import find_relevant_files

PLANNER_SYSTEM = """Task decomposition. Given intent and project context, produce concrete atomic steps.

Rules:
- Each step should be small enough to execute in one focused LLM call
- Each step should touch at most 2-3 files
- Steps should be ordered by dependency (do reads before writes, writes before tests)
- Each step description should be specific enough that someone could execute it without additional context
- Include file paths when you know them

Respond with a JSON array of steps:
[
  {"description": "Read the current sync scripts to understand the flow", "files": ["scripts/sync.sh"]},
  {"description": "Add retry logic with exponential backoff to sync.sh", "files": ["scripts/sync.sh"]},
  {"description": "Add a test script that verifies retry behavior", "files": ["tests/test_sync.sh"]}
]

Respond ONLY with the JSON array, no other text."""


def create_plan(intent: str, project_dir: Path, config: Config) -> Plan:
    """Decompose a user intent into a plan."""
    # Gather some project context for the planner
    context_parts = []

    # Project structure (just top-level files and dirs)
    try:
        items = sorted(project_dir.iterdir())
        structure = "\n".join(
            f"  {'[dir]' if p.is_dir() else ''} {p.name}"
            for p in items
            if not p.name.startswith(".")
        )
        context_parts.append(f"Project structure:\n{structure}")
    except Exception:
        pass

    # README if it exists
    readme = project_dir / "README.md"
    if readme.exists():
        content = readme.read_text()[:2000]
        context_parts.append(f"README.md:\n{content}")

    # Files that might be relevant based on the intent
    relevant = find_relevant_files(intent, project_dir)
    if relevant:
        context_parts.append(f"Possibly relevant files: {', '.join(relevant)}")

    context = "\n\n".join(context_parts)

    messages = [
        {"role": "user", "content": f"Project context:\n{context}\n\nUser intent: {intent}"},
    ]

    response = chat(messages, config, system=PLANNER_SYSTEM)

    # Parse JSON response
    try:
        # Strip markdown code fences if present
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]
        steps_data = json.loads(text)
    except (json.JSONDecodeError, IndexError):
        # If JSON parsing fails, create a single step with the raw intent
        steps_data = [{"description": intent, "files": []}]

    steps = [
        Step(
            description=s.get("description", ""),
            files=s.get("files", []),
        )
        for s in steps_data
    ]

    return Plan(intent=intent, steps=steps)
