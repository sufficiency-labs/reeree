"""Configuration for reeree."""

from dataclasses import dataclass, field
from pathlib import Path
import json
import os


def _load_api_key() -> str:
    """Load API key: env var > ~/.config/together/api_key > empty."""
    key = os.environ.get("TOGETHER_API_KEY", "")
    if key:
        return key
    key_file = Path.home() / ".config" / "together" / "api_key"
    if key_file.exists():
        return key_file.read_text().strip()
    return ""


@dataclass
class Config:
    """Runtime configuration."""

    # LLM settings
    api_base: str = "https://api.together.xyz/v1"
    model: str = "Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8"
    api_key: str = ""

    # Autonomy level: low = approve everything, medium = auto-approve reads,
    # high = auto-approve reads+writes, full = auto-approve all
    autonomy: str = "medium"

    # Project settings
    project_dir: str = "."
    plan_file: str = ".reeree/plan.md"

    # Context settings
    max_context_tokens: int = 24000  # leave room in 32K window

    # Multi-model routing (optional — falls back to single model above)
    # models: {"fast": {"model": "...", "api_base": "...", "api_key": "..."}, ...}
    models: dict = field(default_factory=dict)
    # routing: {"reasoning": "model_key", "coding": "model_key", "fast": "model_key"}
    routing: dict = field(default_factory=dict)

    def is_first_run(self) -> bool:
        """True if no config file exists or no API key configured."""
        return not self.api_key and not self.models

    def __post_init__(self):
        if not self.api_key:
            self.api_key = _load_api_key()

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
