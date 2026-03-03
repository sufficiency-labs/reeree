"""Plan management — the shared steering document."""

from dataclasses import dataclass, field
from pathlib import Path
import re


@dataclass
class Step:
    """A single step in the plan."""
    description: str
    status: str = "pending"  # pending, active, done, skipped
    files: list[str] = field(default_factory=list)  # files this step touches
    commit_hash: str | None = None  # git commit for this step

    @property
    def checkbox(self) -> str:
        if self.status == "done":
            return "[x]"
        elif self.status == "active":
            return "[>]"
        elif self.status == "skipped":
            return "[-]"
        return "[ ]"


@dataclass
class Plan:
    """The plan — a list of steps with an intent."""
    intent: str
    steps: list[Step] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Render plan as markdown."""
        lines = [f"# Plan: {self.intent}", ""]
        for i, step in enumerate(self.steps, 1):
            line = f"- {step.checkbox} **Step {i}:** {step.description}"
            if step.files:
                line += f" ({', '.join(step.files)})"
            if step.commit_hash:
                line += f" `{step.commit_hash[:7]}`"
            lines.append(line)
        lines.append("")
        return "\n".join(lines)

    @classmethod
    def from_markdown(cls, text: str) -> "Plan":
        """Parse a plan from markdown."""
        lines = text.strip().split("\n")
        intent = ""
        steps = []

        for line in lines:
            # Parse header
            if line.startswith("# Plan:"):
                intent = line.replace("# Plan:", "").strip()
                continue

            # Parse step lines
            match = re.match(r"- \[(.)\] \*\*Step \d+:\*\* (.+)", line)
            if match:
                marker, desc = match.groups()
                status = {"x": "done", ">": "active", "-": "skipped"}.get(marker, "pending")

                # Extract files in parens
                files = []
                file_match = re.search(r"\(([^)]+)\)\s*(`[^`]+`)?$", desc)
                if file_match:
                    files = [f.strip() for f in file_match.group(1).split(",")]
                    desc = desc[:file_match.start()].strip()

                # Extract commit hash
                commit = None
                commit_match = re.search(r"`([a-f0-9]{7})`$", desc)
                if commit_match:
                    commit = commit_match.group(1)
                    desc = desc[:commit_match.start()].strip()

                steps.append(Step(description=desc, status=status, files=files, commit_hash=commit))

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
    def current_step(self) -> Step | None:
        """Get the next pending step."""
        for step in self.steps:
            if step.status == "pending":
                return step
        return None

    @property
    def current_step_index(self) -> int | None:
        """Get the index of the next pending step."""
        for i, step in enumerate(self.steps):
            if step.status == "pending":
                return i
        return None

    @property
    def is_complete(self) -> bool:
        return all(s.status in ("done", "skipped") for s in self.steps)
