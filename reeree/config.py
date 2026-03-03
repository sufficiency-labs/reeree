"""Configuration for reeree."""

from dataclasses import dataclass, field
from pathlib import Path
import json


@dataclass
class Config:
    """Runtime configuration."""

    # LLM settings
    api_base: str = "http://localhost:11434/v1"  # ollama default
    model: str = "deepseek-coder-v2:latest"
    api_key: str = "ollama"  # ollama doesn't need a real key

    # Autonomy level: low = approve everything, medium = auto-approve reads,
    # high = auto-approve reads+writes, full = auto-approve all
    autonomy: str = "medium"

    # Project settings
    project_dir: str = "."
    plan_file: str = ".reeree/plan.md"

    # Context settings
    max_context_tokens: int = 24000  # leave room in 32K window

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        """Load config from .reeree/config.json or defaults."""
        if path is None:
            path = Path(".reeree/config.json")
        if path.exists():
            data = json.loads(path.read_text())
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        return cls()

    def save(self, path: Path | None = None) -> None:
        """Save config to file."""
        if path is None:
            path = Path(".reeree/config.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        from dataclasses import asdict
        path.write_text(json.dumps(asdict(self), indent=2) + "\n")
