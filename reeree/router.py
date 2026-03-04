"""Model routing — pick the right model for the task.

Classifies tasks into tiers (reasoning/coding/fast) and routes to the
best available model for that tier. Enables cost-efficient multi-model usage.
"""

from dataclasses import dataclass
from .config import Config
from .daemon_registry import DaemonKind


# Keywords that suggest each tier
_REASONING_KEYWORDS = {"architect", "design", "refactor", "plan", "analyze", "review",
                       "coherence", "strategy", "decide", "evaluate", "compare"}
_FAST_KEYWORDS = {"read", "check", "list", "grep", "find", "search", "count",
                  "status", "show", "cat", "ls", "diff"}


@dataclass
class ModelChoice:
    """The selected model for a task."""
    model: str
    api_base: str
    api_key: str
    tier: str  # "reasoning" | "coding" | "fast"


def classify_task(description: str, daemon_kind: DaemonKind) -> str:
    """Classify a task into a tier: reasoning, coding, or fast.

    Uses daemon kind + description keywords.
    """
    # Daemon kind overrides
    if daemon_kind in (DaemonKind.COHERENCE, DaemonKind.STATE):
        return "reasoning"
    if daemon_kind == DaemonKind.WATCHER:
        return "fast"

    # Keyword analysis on description
    words = set(description.lower().split())
    if words & _REASONING_KEYWORDS:
        return "reasoning"
    if words & _FAST_KEYWORDS:
        return "fast"

    # Default: coding
    return "coding"


def route_model(description: str, daemon_kind: DaemonKind, config: Config) -> ModelChoice:
    """Pick the best model for a task based on tier and available models.

    Falls back to config.model if no multi-model routing is configured.
    """
    tier = classify_task(description, daemon_kind)

    # Check if multi-model routing is configured
    models = getattr(config, "models", None) or {}
    routing = getattr(config, "routing", None) or {}

    if models and routing:
        model_key = routing.get(tier)
        if model_key and model_key in models:
            model_cfg = models[model_key]
            return ModelChoice(
                model=model_cfg.get("model", config.model),
                api_base=model_cfg.get("api_base", config.api_base),
                api_key=model_cfg.get("api_key", config.api_key),
                tier=tier,
            )

    # Fallback: use single configured model for everything
    return ModelChoice(
        model=config.model,
        api_base=config.api_base,
        api_key=config.api_key,
        tier=tier,
    )
