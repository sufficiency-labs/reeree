"""Setup screen — first-run "character creation" for reeree.

When no config exists, this screen helps assemble the ideal tool configuration:
API providers, model assignments per tier, autonomy level, context budget.
"""

import httpx
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static, Input, Button, Select, RadioSet, RadioButton

from ..config import Config


# Well-known API providers to probe
_PROVIDERS = [
    ("together.ai", "https://api.together.xyz/v1", "TOGETHER_API_KEY"),
    ("openai", "https://api.openai.com/v1", "OPENAI_API_KEY"),
    ("gemini", "https://generativelanguage.googleapis.com/v1beta", "GEMINI_API_KEY"),
    ("ollama (local)", "http://localhost:11434/v1", None),
]

# Recommended models per tier (Together.ai)
_RECOMMENDED_MODELS = {
    "coding": "Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8",
    "reasoning": "Qwen/Qwen3-235B-A22B-Thinking-2507",
    "fast": "Qwen/Qwen3-Coder-30B-A3B-Instruct",
}

# Available execution backends to detect
_BACKENDS = [
    ("claude", "claude"),
    ("aider", "aider"),
    ("codex", "codex"),
]


def _probe_provider(api_base: str, api_key: str = "") -> bool:
    """Quick check if an API endpoint is reachable."""
    try:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        resp = httpx.get(f"{api_base}/models", headers=headers, timeout=5.0)
        return resp.status_code == 200
    except Exception:
        return False


class SetupScreen(ModalScreen[Config]):
    """First-run setup wizard. Returns a Config when dismissed."""

    DEFAULT_CSS = """
    SetupScreen {
        align: center middle;
    }
    #setup-container {
        width: 70;
        height: auto;
        max-height: 80%;
        border: solid $primary;
        background: $surface;
        padding: 1 2;
    }
    .setup-section {
        margin-bottom: 1;
    }
    .setup-label {
        color: $text;
        text-style: bold;
    }
    #setup-status {
        color: $text-muted;
        margin-bottom: 1;
    }
    Button {
        margin-top: 1;
    }
    """

    def __init__(self, existing_config: Config | None = None, **kwargs):
        super().__init__(**kwargs)
        self._config = existing_config or Config()
        self._detected: dict[str, bool] = {}

    def compose(self) -> ComposeResult:
        with Vertical(id="setup-container"):
            yield Static("[bold]reeree setup[/bold] — assemble your tools", classes="setup-label")
            yield Static("", id="setup-status")

            yield Static("[bold]API Key[/bold] (together.ai, openai, or custom)", classes="setup-label")
            yield Input(
                value=self._config.api_key,
                placeholder="paste API key here",
                password=True,
                id="api-key-input",
            )

            yield Static("[bold]API Base URL[/bold]", classes="setup-label")
            yield Input(
                value=self._config.api_base,
                placeholder="https://api.together.xyz/v1",
                id="api-base-input",
            )

            yield Static("[bold]Model (coding tier)[/bold]", classes="setup-label")
            yield Input(
                value=self._config.model,
                placeholder=_RECOMMENDED_MODELS["coding"],
                id="model-input",
            )

            yield Static("[bold]Reasoning model[/bold] (coherence, planning)", classes="setup-label")
            yield Input(
                value=self._config.models.get("reasoning", {}).get("model", _RECOMMENDED_MODELS["reasoning"]),
                placeholder=_RECOMMENDED_MODELS["reasoning"],
                id="reasoning-model-input",
            )

            yield Static("[bold]Fast model[/bold] (reads, checks, status)", classes="setup-label")
            yield Input(
                value=self._config.models.get("fast", {}).get("model", _RECOMMENDED_MODELS["fast"]),
                placeholder=_RECOMMENDED_MODELS["fast"],
                id="fast-model-input",
            )

            yield Static("[bold]Autonomy[/bold]", classes="setup-label")
            with RadioSet(id="autonomy-radio"):
                yield RadioButton("low — approve everything", value=self._config.autonomy == "low")
                yield RadioButton("medium — auto-approve reads", value=self._config.autonomy == "medium" or self._config.autonomy not in ("low", "high", "full"))
                yield RadioButton("high — auto-approve reads+writes", value=self._config.autonomy == "high")
                yield RadioButton("full — auto-approve all", value=self._config.autonomy == "full")

            yield Static("[bold]Context Budget[/bold]", classes="setup-label")
            with RadioSet(id="context-radio"):
                yield RadioButton("8K tokens", value=self._config.max_context_tokens <= 8000)
                yield RadioButton("16K tokens", value=8000 < self._config.max_context_tokens <= 16000)
                yield RadioButton("24K tokens (default)", value=16000 < self._config.max_context_tokens <= 24000 or self._config.max_context_tokens not in (8000, 16000, 32000))
                yield RadioButton("32K tokens", value=self._config.max_context_tokens >= 32000)

            yield Button("Save & Start", variant="primary", id="save-btn")

    def on_mount(self) -> None:
        self._probe_apis()

    def _probe_apis(self) -> None:
        """Probe known API providers and execution backends."""
        import os
        import shutil
        status_lines = ["[bold]API providers:[/bold]"]
        for name, base, env_var in _PROVIDERS:
            key = os.environ.get(env_var, "") if env_var else ""
            available = _probe_provider(base, key)
            self._detected[name] = available
            icon = "[green]OK[/green]" if available else "[dim]--[/dim]"
            status_lines.append(f"  {icon} {name}")

        status_lines.append("\n[bold]Execution backends:[/bold]")
        for name, binary in _BACKENDS:
            found = shutil.which(binary) is not None
            self._detected[f"backend:{name}"] = found
            icon = "[green]OK[/green]" if found else "[dim]--[/dim]"
            status_lines.append(f"  {icon} {name}")

        status = self.query_one("#setup-status", Static)
        status.update("\n".join(status_lines))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-btn":
            self._save_and_dismiss()

    def _save_and_dismiss(self) -> None:
        api_key = self.query_one("#api-key-input", Input).value.strip()
        api_base = self.query_one("#api-base-input", Input).value.strip()
        model = self.query_one("#model-input", Input).value.strip()
        reasoning_model = self.query_one("#reasoning-model-input", Input).value.strip()
        fast_model = self.query_one("#fast-model-input", Input).value.strip()

        # Autonomy
        autonomy_map = {0: "low", 1: "medium", 2: "high", 3: "full"}
        autonomy_radio = self.query_one("#autonomy-radio", RadioSet)
        autonomy = autonomy_map.get(autonomy_radio.pressed_index, "medium")

        # Context budget
        context_map = {0: 8000, 1: 16000, 2: 24000, 3: 32000}
        context_radio = self.query_one("#context-radio", RadioSet)
        max_context = context_map.get(context_radio.pressed_index, 24000)

        effective_base = api_base or self._config.api_base
        effective_key = api_key or self._config.api_key

        # Build multi-model routing
        models = {}
        routing = {}
        if reasoning_model:
            models["reasoning"] = {"model": reasoning_model, "api_base": effective_base, "api_key": effective_key}
            routing["reasoning"] = "reasoning"
        if model:
            models["coding"] = {"model": model, "api_base": effective_base, "api_key": effective_key}
            routing["coding"] = "coding"
        if fast_model:
            models["fast"] = {"model": fast_model, "api_base": effective_base, "api_key": effective_key}
            routing["fast"] = "fast"

        config = Config(
            api_key=effective_key,
            api_base=effective_base,
            model=model or self._config.model,
            autonomy=autonomy,
            max_context_tokens=max_context,
            models=models,
            routing=routing,
        )

        self.dismiss(config)
