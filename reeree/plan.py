"""Plan management — the shared steering document / work queue."""

from dataclasses import dataclass, field
from pathlib import Path
import re


@dataclass
class Step:
    """A single step in the plan.

    Steps are work queue items with inline specs. The user edits them
    ahead of execution — adding annotations, acceptance criteria, file
    hints — while daemons are busy on earlier steps.

    Format on disk:
        - [ ] Add retry logic to sync.sh
          > max 3 retries, exponential backoff
          > files: scripts/sync.sh, scripts/retry.sh
          > done: retry_test.sh passes

    The `> ` lines are annotations the daemon reads as context.
    """
    description: str
    status: str = "pending"  # pending, active, done, skipped, failed, blocked
    annotations: list[str] = field(default_factory=list)  # user specs, hints, acceptance criteria
    files: list[str] = field(default_factory=list)  # files this step touches
    commit_hash: str | None = None  # git commit for this step
    daemon_id: int | None = None  # which daemon is running this
    error: str | None = None  # error message if failed

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

    def save(self, path: Path) -> None:
        """Write plan to file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_markdown())

    @classmethod
    def load(cls, path: Path) -> "Plan":
        """Load plan from file."""
        return cls.from_markdown(path.read_text())

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
