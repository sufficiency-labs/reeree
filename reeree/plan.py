"""Plan management — the shared steering document / work queue.

Data model: Plan and Step dataclasses.
Disk format: YAML (plan.yaml). The checklist is a *view* of the data.
Display: rich unicode indicators for NORMAL mode, raw YAML for INSERT mode.
"""

import hashlib
import time as _time
from dataclasses import dataclass, field
from pathlib import Path
import re
import yaml


def _generate_step_id(description: str) -> str:
    """Generate a short stable ID from description + timestamp.

    Format: first 3 chars of first word + 4 hex chars.
    Example: "Add retry logic" -> "add-a1b2"
    """
    words = description.split()
    prefix = words[0].lower()[:3] if words else "stp"
    h = hashlib.sha1(f"{description}{_time.time()}".encode()).hexdigest()[:4]
    return f"{prefix}-{h}"


@dataclass
class Step:
    """A single step in the plan.

    Steps are work queue items with inline specs. The user edits them
    ahead of execution — adding annotations, acceptance criteria, file
    hints — while daemons are busy on earlier steps.

    Each step has a stable `id` that survives reordering, insertion, and
    deletion. Daemons reference steps by ID, not index.
    """
    description: str
    id: str = ""  # Stable identity — survives reorder/insert/delete
    status: str = "pending"  # pending, active, done, skipped, failed, blocked
    annotations: list[str] = field(default_factory=list)  # user specs, hints, acceptance criteria
    files: list[str] = field(default_factory=list)  # files this step touches
    commit_hash: str | None = None  # git commit for this step
    daemon_id: int | None = None  # which daemon is running this
    error: str | None = None  # error message if failed

    def __post_init__(self):
        if not self.id:
            self.id = _generate_step_id(self.description)

    @property
    def checkbox(self) -> str:
        markers = {
            "done": "[x]",
            "active": "[>]",
            "skipped": "[-]",
            "failed": "[!]",
            "blocked": "[~]",
        }
        return markers.get(self.status, "[ ]")

    @property
    def rich_indicator(self) -> str:
        """Unicode status indicator for rich display."""
        indicators = {
            "done": "✓",
            "active": "▶",
            "skipped": "–",
            "failed": "✗",
            "blocked": "◌",
            "decision": "?",
        }
        return indicators.get(self.status, "○")

    @property
    def done_criteria(self) -> str | None:
        """Extract acceptance criteria from annotations."""
        for a in self.annotations:
            if a.lower().startswith("done:"):
                return a[5:].strip()
        return None

    @property
    def file_hints(self) -> list[str]:
        """Extract file hints from annotations."""
        for a in self.annotations:
            if a.lower().startswith("files:"):
                return [f.strip() for f in a[6:].split(",")]
        return []

    @property
    def context_annotations(self) -> list[str]:
        """Get annotations that aren't structured (done:/files:) — free-form specs."""
        return [a for a in self.annotations
                if not a.lower().startswith(("done:", "files:"))]


@dataclass
class Plan:
    """The plan — a work queue with inline specs.

    The plan is a markdown file that both the user and daemons read/write.
    The user is always editing ahead of the daemons: adding steps, annotating
    future steps with specs, reordering priorities. Daemons pick up steps,
    read the annotations, execute, and mark done.

    This overlap — user planning ahead while daemons execute behind —
    is where the wasted time goes.
    """
    intent: str
    steps: list[Step] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Render plan as markdown."""
        lines = [f"# Plan: {self.intent}", ""]
        for i, step in enumerate(self.steps, 1):
            # Step line
            line = f"- {step.checkbox} Step {i}: {step.description}"
            if step.commit_hash:
                line += f" [{step.commit_hash[:7]}]"
            if step.daemon_id is not None and step.status == "active":
                line += f" (daemon {step.daemon_id})"
            if step.error:
                line += f" ERROR: {step.error}"
            lines.append(line)

            # Annotations as indented > lines
            for annotation in step.annotations:
                lines.append(f"  > {annotation}")

            # Show files if specified and not already in annotations
            if step.files and not step.file_hints:
                lines.append(f"  > files: {', '.join(step.files)}")

        lines.append("")
        return "\n".join(lines)

    def to_rich_display(self) -> str:
        """Render plan as rich-formatted display text for NORMAL mode.

        Uses Unicode indicators and cleaner formatting than raw markdown.
        Still parseable back to Plan via from_markdown (includes markers in comments).
        """
        lines = [f"  {self.intent}", ""]
        for i, step in enumerate(self.steps, 1):
            indicator = step.rich_indicator
            # Color hints via the indicator character
            desc = step.description

            # Build the display line
            suffix_parts = []
            if step.commit_hash:
                suffix_parts.append(f"[{step.commit_hash[:7]}]")
            if step.daemon_id is not None and step.status == "active":
                suffix_parts.append(f"daemon {step.daemon_id}")
            if step.error:
                suffix_parts.append(f"ERR: {step.error}")
            suffix = f"  {' '.join(suffix_parts)}" if suffix_parts else ""

            lines.append(f"  {indicator}  {i}. {desc}{suffix}")

            # Annotations as indented context
            for annotation in step.annotations:
                lines.append(f"        {annotation}")

            # Show files if specified and not in annotations
            if step.files and not step.file_hints:
                lines.append(f"        files: {', '.join(step.files)}")

        lines.append("")
        return "\n".join(lines)

    @classmethod
    def from_rich_display(cls, text: str) -> "Plan":
        """Parse plan from rich display format.

        Handles:
          intent line (first non-empty)
          ✓  1. description  [abc1234]
          ▶  2. description  daemon 1
          ○  3. description
                annotation line
        """
        import re
        lines = text.strip().split("\n")
        intent = ""
        steps = []
        current_step = None

        indicator_map = {"✓": "done", "▶": "active", "–": "skipped",
                         "✗": "failed", "◌": "blocked", "?": "decision", "○": "pending"}

        for line in lines:
            stripped = line.strip()

            # Intent: first non-empty line that isn't a step
            if not intent and stripped and not any(stripped.startswith(ind) for ind in indicator_map):
                intent = stripped.replace("# Plan:", "").strip()
                continue

            # Step line: indicator + number + description
            step_match = re.match(r'\s*([✓▶–✗◌?○])\s+(\d+)\.\s+(.+)', line)
            if step_match:
                if current_step:
                    steps.append(current_step)

                ind_char, _num, desc = step_match.groups()
                status = indicator_map.get(ind_char, "pending")

                # Extract commit hash
                commit = None
                commit_match = re.search(r'\[([a-f0-9]{7})\]', desc)
                if commit_match:
                    commit = commit_match.group(1)
                    desc = desc[:commit_match.start()].strip()

                # Extract daemon id
                daemon_id = None
                daemon_match = re.search(r'daemon (\d+)', desc)
                if daemon_match:
                    daemon_id = int(daemon_match.group(1))
                    desc = desc[:daemon_match.start()].strip()

                # Extract error
                error = None
                err_match = re.search(r'ERR: (.+)$', desc)
                if err_match:
                    error = err_match.group(1)
                    desc = desc[:err_match.start()].strip()

                current_step = Step(
                    description=desc,
                    status=status,
                    commit_hash=commit,
                    daemon_id=daemon_id,
                    error=error,
                )
                continue

            # Annotation lines (indented under a step)
            ann_match = re.match(r'\s{6,}(.+)', line)
            if ann_match and current_step:
                annotation = ann_match.group(1).strip()
                if annotation.lower().startswith("files:"):
                    current_step.files = [f.strip() for f in annotation[6:].split(",")]
                current_step.annotations.append(annotation)
                continue

            # Also handle > annotation format (from markdown)
            gt_match = re.match(r'\s+> (.+)', line)
            if gt_match and current_step:
                annotation = gt_match.group(1)
                if annotation.lower().startswith("files:"):
                    current_step.files = [f.strip() for f in annotation[6:].split(",")]
                current_step.annotations.append(annotation)

        if current_step:
            steps.append(current_step)

        return cls(intent=intent, steps=steps)

    @classmethod
    def from_markdown(cls, text: str) -> "Plan":
        """Parse a plan from markdown.

        Handles the annotation format:
            - [ ] Step 1: description
              > annotation line
              > done: criteria
              > files: a.py, b.py
        """
        lines = text.strip().split("\n")
        intent = ""
        steps = []
        current_step = None

        for line in lines:
            # Parse header
            if line.startswith("# Plan:"):
                intent = line.replace("# Plan:", "").strip()
                continue

            # Parse step lines
            step_match = re.match(r"- \[(.)\] Step \d+: (.+)", line)
            if step_match:
                # Save previous step
                if current_step:
                    steps.append(current_step)

                marker, desc = step_match.groups()
                status = {
                    "x": "done", ">": "active", "-": "skipped",
                    "!": "failed", "~": "blocked",
                }.get(marker, "pending")

                # Extract commit hash [abc1234]
                commit = None
                commit_match = re.search(r"\[([a-f0-9]{7})\]", desc)
                if commit_match:
                    commit = commit_match.group(1)
                    desc = desc[:commit_match.start()].strip()

                # Extract daemon id (daemon N)
                daemon_id = None
                daemon_match = re.search(r"\(daemon (\d+)\)", desc)
                if daemon_match:
                    daemon_id = int(daemon_match.group(1))
                    desc = desc[:daemon_match.start()].strip()

                # Extract error
                error = None
                error_match = re.search(r"ERROR: (.+)$", desc)
                if error_match:
                    error = error_match.group(1)
                    desc = desc[:error_match.start()].strip()

                current_step = Step(
                    description=desc,
                    status=status,
                    commit_hash=commit,
                    daemon_id=daemon_id,
                    error=error,
                )
                continue

            # Parse annotation lines (indented > lines)
            annotation_match = re.match(r"\s+> (.+)", line)
            if annotation_match and current_step:
                annotation = annotation_match.group(1)

                # Extract files from annotation
                if annotation.lower().startswith("files:"):
                    current_step.files = [f.strip() for f in annotation[6:].split(",")]

                current_step.annotations.append(annotation)

        # Don't forget the last step
        if current_step:
            steps.append(current_step)

        return cls(intent=intent, steps=steps)

    def step_by_id(self, step_id: str) -> Step | None:
        """Find a step by its stable ID."""
        for step in self.steps:
            if step.id == step_id:
                return step
        return None

    def step_index_by_id(self, step_id: str) -> int | None:
        """Find a step's current index by its stable ID."""
        for i, step in enumerate(self.steps):
            if step.id == step_id:
                return i
        return None

    def to_yaml(self) -> str:
        """Serialize plan as YAML — the canonical disk format."""
        data = {
            "intent": self.intent,
            "steps": [],
        }
        for step in self.steps:
            s: dict = {"id": step.id, "description": step.description, "status": step.status}
            if step.annotations:
                s["annotations"] = step.annotations
            if step.files:
                s["files"] = step.files
            if step.commit_hash:
                s["commit"] = step.commit_hash
            if step.daemon_id is not None:
                s["daemon"] = step.daemon_id
            if step.error:
                s["error"] = step.error
            data["steps"].append(s)
        return yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)

    @classmethod
    def from_yaml(cls, text: str) -> "Plan":
        """Parse plan from YAML."""
        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            return cls(intent="", steps=[])
        intent = data.get("intent", "")
        steps = []
        for s in data.get("steps", []):
            if isinstance(s, str):
                # Simple string step: "do the thing"
                steps.append(Step(description=s))
            elif isinstance(s, dict):
                steps.append(Step(
                    description=s.get("description", ""),
                    id=s.get("id", ""),  # Empty → __post_init__ generates one
                    status=s.get("status", "pending"),
                    annotations=s.get("annotations", []),
                    files=s.get("files", []),
                    commit_hash=s.get("commit"),
                    daemon_id=s.get("daemon"),
                    error=s.get("error"),
                ))
        return cls(intent=intent, steps=steps)

    def save(self, path: Path) -> None:
        """Write plan to file as YAML."""
        path.parent.mkdir(parents=True, exist_ok=True)
        # Use .yaml extension if possible, but respect whatever path is given
        path.write_text(self.to_yaml())

    @classmethod
    def load(cls, path: Path) -> "Plan":
        """Load plan from file. Detects YAML or markdown format."""
        text = path.read_text()
        # YAML files start with "intent:" or are valid YAML dicts
        # Markdown files start with "# Plan:" or "- ["
        if text.strip().startswith(("intent:", "---")):
            return cls.from_yaml(text)
        # Try YAML parse first (handles both formats)
        try:
            data = yaml.safe_load(text)
            if isinstance(data, dict) and "intent" in data:
                return cls.from_yaml(text)
        except Exception:
            pass
        # Fall back to markdown
        return cls.from_markdown(text)

    @property
    def pending_steps(self) -> list[tuple[int, Step]]:
        """Get all pending steps with their indices."""
        return [(i, s) for i, s in enumerate(self.steps) if s.status == "pending"]

    @property
    def active_steps(self) -> list[tuple[int, Step]]:
        """Get all actively executing steps."""
        return [(i, s) for i, s in enumerate(self.steps) if s.status == "active"]

    @property
    def dispatchable_steps(self) -> list[tuple[int, Step]]:
        """Get steps that are ready to dispatch (pending, not blocked)."""
        return [(i, s) for i, s in enumerate(self.steps) if s.status == "pending"]

    @property
    def is_complete(self) -> bool:
        return all(s.status in ("done", "skipped") for s in self.steps)

    @property
    def progress(self) -> tuple[int, int]:
        """Return (done_count, total_count)."""
        done = sum(1 for s in self.steps if s.status in ("done", "skipped"))
        return done, len(self.steps)


@dataclass
class StepStatusUpdate:
    """A daemon's status update for a step, keyed by step ID."""
    step_id: str
    status: str
    commit_hash: str | None = None
    error: str | None = None
    timestamp: float = field(default_factory=_time.time)

    def apply(self, step: Step) -> None:
        """Apply this update to a step's status fields."""
        step.status = self.status
        if self.commit_hash:
            step.commit_hash = self.commit_hash
        if self.error:
            step.error = self.error


class StatusOverlay:
    """Buffers daemon status updates, decoupled from the TextArea.

    Daemons post updates here. In NORMAL mode, updates apply to the Plan
    and re-render immediately. In INSERT mode, updates apply to the Plan
    (in-memory) but the TextArea is untouched — updates queue here and
    merge when the user exits INSERT mode.
    """

    def __init__(self):
        self._pending: dict[str, StepStatusUpdate] = {}

    def post(self, update: StepStatusUpdate) -> None:
        """Daemon posts a status update."""
        self._pending[update.step_id] = update

    def drain(self) -> list[StepStatusUpdate]:
        """Consume all pending updates. Called on INSERT→NORMAL."""
        updates = list(self._pending.values())
        self._pending.clear()
        return updates

    def peek(self) -> dict[str, StepStatusUpdate]:
        """Read pending updates without consuming."""
        return dict(self._pending)

    @property
    def has_pending(self) -> bool:
        return bool(self._pending)

    @property
    def pending_count(self) -> int:
        return len(self._pending)
