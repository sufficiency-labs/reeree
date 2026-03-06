"""Machine tasks — inline annotations that dispatch daemon work.

Any document can contain machine task annotations. When the user saves (:w),
the tool finds these annotations, dispatches daemons, and splices results
back into the document.

Syntax:
    [machine: description of what to do]

While running:
    [⏳ description of what to do]

When done, the annotation is replaced with the daemon's output — prose,
bullet points, whatever the task produced. The annotation disappears.
The document evolves.

This works in any markdown file. The plan/checklist is just one kind of
document with machine-addressable content. An essay, a spec, a research
brief — they all work the same way.
"""

import re
from dataclasses import dataclass, field
import time as _time


# Pattern: [machine: description]
# Captures the description text. Won't match markdown links [text](url)
# because those have () immediately after the ].
MACHINE_TASK_PATTERN = re.compile(
    r'\[machine:\s*(.+?)\](?!\()',
    re.DOTALL,
)

# Progress indicator pattern: [⏳ description]
PROGRESS_PATTERN = re.compile(
    r'\[⏳\s*(.+?)\]',
    re.DOTALL,
)


@dataclass
class MachineTask:
    """A machine task extracted from document text."""
    description: str
    start: int          # character offset in source text
    end: int            # character offset end
    task_id: str = ""   # stable ID for tracking
    daemon_id: int | None = None

    def __post_init__(self):
        if not self.task_id:
            import hashlib
            h = hashlib.sha1(f"{self.description}{_time.time()}".encode()).hexdigest()[:6]
            self.task_id = f"mt-{h}"


def find_tasks(text: str) -> list[MachineTask]:
    """Find all [machine: ...] annotations in text.

    Returns tasks in document order with character offsets.
    """
    tasks = []
    for match in MACHINE_TASK_PATTERN.finditer(text):
        tasks.append(MachineTask(
            description=match.group(1).strip(),
            start=match.start(),
            end=match.end(),
        ))
    return tasks


def mark_in_progress(text: str, tasks: list[MachineTask]) -> str:
    """Replace [machine: desc] with [⏳ desc] for all given tasks.

    Processes in reverse order to preserve character offsets.
    """
    result = text
    for task in reversed(tasks):
        before = result[:task.start]
        after = result[task.end:]
        result = f"{before}[⏳ {task.description}]{after}"
    return result


def splice_result(text: str, description: str, result: str) -> str:
    """Replace [⏳ description] with the result text.

    The progress indicator disappears. The result takes its place
    in the document — inline if short, block if multiline.
    """
    # Find the progress indicator for this task
    pattern = re.compile(
        r'\[⏳\s*' + re.escape(description) + r'\]',
        re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return text

    # Clean up the result — strip leading/trailing whitespace
    result = result.strip()

    # If the result is multiline, ensure it gets its own block
    if '\n' in result:
        # Check if the progress indicator is on its own line
        before = text[:match.start()]
        after = text[match.end():]
        # If it's inline (text before/after on same line), put result on next line
        last_newline = before.rfind('\n')
        line_before = before[last_newline + 1:] if last_newline >= 0 else before
        if line_before.strip():
            # There's text before on this line — put result on next line
            result = '\n' + result + '\n'
    return text[:match.start()] + result + text[match.end():]


def find_in_progress(text: str) -> list[str]:
    """Find all [⏳ description] markers currently in text.

    Returns the descriptions of tasks still in progress.
    """
    return [match.group(1).strip() for match in PROGRESS_PATTERN.finditer(text)]
