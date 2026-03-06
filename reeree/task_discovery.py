"""Queued task discovery — find and parse task starter packs.

Task files live at coordination/queued/ (vorkosigan pattern) or .reeree/tasks/.
Each is a self-contained briefing for a work session. This module discovers
them, parses their metadata, and converts them to Plan steps.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from .plan import Plan, Step


@dataclass
class TaskFile:
    """A discovered queued task file."""
    path: Path
    title: str = ""
    status: str = "PENDING"
    priority: str = "MEDIUM"
    description: str = ""  # first paragraph after title
    sections: dict = field(default_factory=dict)  # heading → content

    @property
    def is_actionable(self) -> bool:
        return self.status.upper() in ("PENDING", "OPEN", "READY")

    @property
    def filename(self) -> str:
        return self.path.name


def parse_task_file(path: Path) -> TaskFile:
    """Parse a queued task markdown file into TaskFile metadata."""
    text = path.read_text()
    lines = text.strip().split("\n")

    tf = TaskFile(path=path)

    # Title: first # heading
    for line in lines:
        if line.startswith("# "):
            tf.title = line[2:].strip()
            break

    # Parse metadata — two formats:
    # 1. Bold-label: **STATUS:** VALUE  or  **Status**: VALUE
    # 2. List-label: - **Status**: VALUE
    for line in lines:
        stripped = line.strip()
        # Format: **STATUS:** VALUE or - **Status**: VALUE
        m = re.match(r'^-?\s*\*\*(?:STATUS|Status)\*?\*?[:：]\*?\*?\s*(.+)', stripped)
        if m:
            tf.status = m.group(1).strip().rstrip("*")
            continue
        m = re.match(r'^-?\s*\*\*(?:PRIORITY|Priority)\*?\*?[:：]\*?\*?\s*(.+)', stripped)
        if m:
            tf.priority = m.group(1).strip().rstrip("*")
            continue

    # Sections: parse ## headings and their content
    current_section = None
    section_lines = []
    for line in lines:
        if line.startswith("## "):
            if current_section:
                tf.sections[current_section] = "\n".join(section_lines).strip()
            current_section = line[3:].strip()
            section_lines = []
        elif current_section is not None:
            section_lines.append(line)

    if current_section:
        tf.sections[current_section] = "\n".join(section_lines).strip()

    # Description: first non-empty paragraph after metadata block
    in_metadata = True
    desc_lines = []
    for line in lines[1:]:  # skip title
        stripped = line.strip()
        if in_metadata:
            # Skip metadata lines (bold labels, empty lines, ---)
            if (stripped.startswith("**") or stripped.startswith("- **")
                    or stripped == "---" or stripped == ""):
                continue
            in_metadata = False
        if not in_metadata:
            if stripped == "" and desc_lines:
                break  # end of first paragraph
            if stripped:
                desc_lines.append(stripped)

    tf.description = " ".join(desc_lines)[:300] if desc_lines else tf.title

    return tf


def discover_tasks(project_dir: Path, include_done: bool = False) -> list[TaskFile]:
    """Find queued task files in standard locations.

    Searches:
    1. coordination/queued/ (vorkosigan pattern)
    2. .reeree/tasks/ (local project tasks)

    Skips README.md, SUMMARY.md, and completed/ directory.
    """
    tasks = []
    search_dirs = []

    # Walk up to find coordination/queued/ (works in subrepos)
    current = project_dir.resolve()
    for _ in range(5):
        queued = current / "coordination" / "queued"
        if queued.is_dir():
            search_dirs.append(queued)
            break
        if current == current.parent:
            break
        current = current.parent

    # Local project tasks
    local_tasks = project_dir / ".reeree" / "tasks"
    if local_tasks.is_dir():
        search_dirs.append(local_tasks)

    skip_names = {"README.md", "SUMMARY.md", "INDEX.md"}

    for search_dir in search_dirs:
        for md_file in sorted(search_dir.glob("*.md")):
            if md_file.name in skip_names:
                continue
            try:
                tf = parse_task_file(md_file)
                if include_done or tf.is_actionable:
                    tasks.append(tf)
            except Exception:
                continue  # skip unparseable files

    return tasks


def task_to_steps(task: TaskFile) -> list[Step]:
    """Convert a task file into plan steps.

    Extracts actionable items from the task's sections:
    - "Implementation Order" / "Implementation" / "Steps" → numbered items
    - "Success Criteria" / "Done" → annotations on the final step
    - Falls back to a single step with the task description
    """
    steps = []

    # Look for implementation steps in known sections
    impl_sections = [
        "Implementation Order", "Implementation", "Steps",
        "Implementation Plan", "Action Items", "Tasks",
    ]

    impl_text = ""
    for section_name in impl_sections:
        if section_name in task.sections:
            impl_text = task.sections[section_name]
            break

    if impl_text:
        # Parse numbered or bulleted items
        for line in impl_text.split("\n"):
            stripped = line.strip()
            # Match: 1. item, - item, * item
            m = re.match(r'^(?:\d+\.\s+|\-\s+|\*\s+)(.+)', stripped)
            if m:
                desc = m.group(1).strip()
                # Strip markdown bold/code
                desc = re.sub(r'\*\*(.+?)\*\*', r'\1', desc)
                desc = re.sub(r'`(.+?)`', r'\1', desc)
                if desc and len(desc) > 5:
                    step = Step(description=desc)
                    step.annotations.append(f"source: {task.filename}")
                    steps.append(step)

    # If no implementation steps found, create one step from the task
    if not steps:
        step = Step(description=task.title or task.description)
        step.annotations.append(f"source: {task.filename}")
        if task.description and task.description != task.title:
            step.annotations.append(task.description[:200])
        steps.append(step)

    # Add success criteria as annotations on the last step
    for criteria_name in ["Success Criteria", "Done", "Acceptance Criteria"]:
        if criteria_name in task.sections:
            criteria = task.sections[criteria_name].strip()
            if criteria and steps:
                steps[-1].annotations.append(f"done: {criteria[:200]}")
            break

    # Add context section as annotations on the first step
    for ctx_name in ["Context", "Context (auto-generated)", "Dependencies", "Problem"]:
        if ctx_name in task.sections:
            ctx = task.sections[ctx_name].strip()
            if ctx and steps:
                steps[0].annotations.append(ctx[:200])
            break

    return steps


def task_to_plan(task: TaskFile) -> Plan:
    """Convert a task file into a full Plan."""
    intent = task.title or task.description
    steps = task_to_steps(task)
    return Plan(intent=intent, steps=steps)


def format_task_list(tasks: list[TaskFile]) -> str:
    """Format task list for TUI display."""
    if not tasks:
        return "No queued tasks found."

    lines = []
    for i, t in enumerate(tasks, 1):
        priority_marker = {"HIGH": "!", "MEDIUM": "·", "LOW": " "}.get(
            t.priority.upper(), "·"
        )
        lines.append(f"  {priority_marker} {i:2d}. {t.title or t.filename}")
        if t.description and t.description != t.title:
            lines.append(f"       {t.description[:80]}")

    lines.append(f"\n  {len(tasks)} tasks. :load-task N to load.")
    return "\n".join(lines)
