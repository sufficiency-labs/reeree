"""reeree CLI — terminal-native LLM coding tool with tmux-style TUI."""

import click
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.text import Text

from .config import Config
from .plan import Plan
from .planner import create_plan
from .executor import run_shell, write_file, edit_file, git_commit, git_revert_last
from .context import gather_context
from .llm import chat, chat_stream

console = Console()

STEP_SYSTEM = """You are a coding assistant executing ONE step of a plan. You have access to the project files shown in the context.

Your job is to execute the step described, and respond with the actions to take. Respond in this JSON format:

{
  "actions": [
    {"type": "shell", "command": "ls -la src/"},
    {"type": "write", "path": "src/foo.py", "content": "...file content..."},
    {"type": "edit", "path": "src/foo.py", "old": "old text", "new": "new text"},
    {"type": "shell", "command": "python -m pytest tests/"}
  ],
  "summary": "Brief description of what was done"
}

Action types:
- "shell": run a shell command
- "write": write/create a file (full content)
- "edit": replace text in an existing file
- "read": read a file (use to gather more info before acting)

Keep actions minimal. Do exactly what the step says, nothing more.
Respond ONLY with JSON, no other text."""


def show_plan(plan: Plan) -> None:
    """Display the plan in a panel."""
    console.print(Panel(
        Markdown(plan.to_markdown()),
        title="[bold cyan]Plan[/bold cyan]",
        border_style="cyan",
    ))


def show_step(step_num: int, total: int, description: str) -> None:
    """Display the current step."""
    console.print(f"\n[bold yellow]Step {step_num}/{total}:[/bold yellow] {description}")


def execute_step_actions(actions: list[dict], project_dir: Path, config: Config, autonomy: str) -> list:
    """Execute a list of actions with appropriate approval gates."""
    import json
    results = []

    for action in actions:
        action_type = action.get("type", "unknown")

        # Determine if we need approval
        needs_approval = True
        if autonomy == "high" and action_type in ("read", "shell"):
            needs_approval = False
        elif autonomy == "full":
            needs_approval = False
        elif autonomy == "medium" and action_type == "read":
            needs_approval = False

        # Show what we're about to do
        if action_type == "shell":
            console.print(f"  [dim]$[/dim] [green]{action['command']}[/green]")
        elif action_type == "write":
            content = action.get("content", "")
            console.print(f"  [dim]write[/dim] [blue]{action['path']}[/blue] ({len(content)} chars)")
        elif action_type == "edit":
            console.print(f"  [dim]edit[/dim] [blue]{action['path']}[/blue]")
            console.print(f"    [red]- {action.get('old', '')[:80]}[/red]")
            console.print(f"    [green]+ {action.get('new', '')[:80]}[/green]")

        # Gate on approval if needed
        if needs_approval:
            if not Confirm.ask("    Execute?", default=True):
                console.print("    [yellow]Skipped[/yellow]")
                continue

        # Execute
        if action_type == "shell":
            result = run_shell(action["command"], project_dir)
            if result.output:
                console.print(f"    [dim]{result.output[:500]}[/dim]")
            results.append(result)
        elif action_type == "write":
            path = project_dir / action["path"]
            result = write_file(path, action["content"])
            results.append(result)
        elif action_type == "edit":
            path = project_dir / action["path"]
            result = edit_file(path, action["old"], action["new"])
            results.append(result)

        if results and not results[-1].success:
            console.print(f"    [red]Failed: {results[-1].output}[/red]")

    return results


@click.command()
@click.argument("intent", nargs=-1, required=False)
@click.option("--plan", "plan_file", type=click.Path(), help="Resume from existing plan file")
@click.option("--model", help="Model to use (e.g. ollama/deepseek-v3, gpt-4o)")
@click.option("--api-base", help="API base URL")
@click.option("--api-key", help="API key")
@click.option("--autonomy", type=click.Choice(["low", "medium", "high", "full"]), default="medium",
              help="Approval level: low=approve all, medium=auto-read, high=auto-read+shell, full=auto-all")
@click.option("--project", type=click.Path(exists=True), default=".", help="Project directory")
def main(intent, plan_file, model, api_base, api_key, autonomy, project):
    """reeree — high-bandwidth, tight-steering LLM coding tool.

    Express your intent and steer the execution.

    Examples:
        reeree make the sync more resilient
        reeree "add retry logic to the upload script"
        reeree --plan .reeree/plan.md  (resume)
        reeree --model gpt-4o --autonomy low "refactor auth"
    """
    project_dir = Path(project).resolve()

    # Load or create config
    config = Config.load(project_dir / ".reeree" / "config.json")
    if model:
        config.model = model
    if api_base:
        config.api_base = api_base
    if api_key:
        config.api_key = api_key
    config.autonomy = autonomy

    console.print(Panel(
        f"[bold]reeree[/bold] v0.1.0\n"
        f"Model: [cyan]{config.model}[/cyan]\n"
        f"API: [dim]{config.api_base}[/dim]\n"
        f"Autonomy: [yellow]{config.autonomy}[/yellow]\n"
        f"Project: [blue]{project_dir}[/blue]",
        title="[bold green]reeree[/bold green]",
        border_style="green",
    ))

    # Load or create plan
    plan_path = project_dir / ".reeree" / "plan.md"

    if plan_file:
        plan = Plan.load(Path(plan_file))
        console.print("[dim]Loaded existing plan[/dim]")
    elif plan_path.exists() and not intent:
        plan = Plan.load(plan_path)
        console.print("[dim]Resuming existing plan[/dim]")
    elif intent:
        intent_str = " ".join(intent)
        console.print(f"\n[bold]Intent:[/bold] {intent_str}")
        console.print("[dim]Planning...[/dim]")
        try:
            plan = create_plan(intent_str, project_dir, config)
        except Exception as e:
            console.print(f"[red]Failed to create plan: {e}[/red]")
            sys.exit(1)
    else:
        console.print("[yellow]Usage: reeree <your intent>[/yellow]")
        console.print("[dim]Example: reeree add error handling to the upload script[/dim]")
        sys.exit(0)

    # Show the plan
    show_plan(plan)
    plan.save(plan_path)
    console.print(f"[dim]Plan saved to {plan_path}[/dim]")

    # Let user review/edit plan
    console.print("\n[bold]Commands:[/bold] [green]go[/green] (execute), [yellow]edit[/yellow] (modify plan), [red]quit[/red]")
    action = Prompt.ask("", choices=["go", "edit", "quit", "g", "e", "q"], default="go")

    if action in ("quit", "q"):
        console.print("[dim]Plan saved. Resume later with: reeree[/dim]")
        return

    if action in ("edit", "e"):
        console.print(f"[dim]Edit the plan file at: {plan_path}[/dim]")
        console.print("[dim]Then run 'reeree' to resume.[/dim]")
        return

    # Execute steps
    import json

    while not plan.is_complete:
        step = plan.current_step
        step_idx = plan.current_step_index
        if step is None:
            break

        step.status = "active"
        plan.save(plan_path)

        show_step(step_idx + 1, len(plan.steps), step.description)

        # Gather focused context for this step
        context = gather_context(step, project_dir, config.max_context_tokens * 4)

        # Ask LLM to execute this step
        messages = [
            {"role": "user", "content": (
                f"Project context:\n{context}\n\n"
                f"Current step: {step.description}\n"
                f"Files to work with: {', '.join(step.files) if step.files else 'determine from context'}\n\n"
                f"Execute this step. Respond with JSON actions."
            )},
        ]

        try:
            response = chat(messages, config, system=STEP_SYSTEM)
        except Exception as e:
            console.print(f"[red]LLM error: {e}[/red]")
            step.status = "pending"
            plan.save(plan_path)
            break

        # Parse actions
        try:
            text = response.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                text = text.rsplit("```", 1)[0]
            data = json.loads(text)
            actions = data.get("actions", [])
            summary = data.get("summary", "")
        except (json.JSONDecodeError, KeyError):
            console.print(f"[red]Failed to parse LLM response[/red]")
            console.print(f"[dim]{response[:500]}[/dim]")
            step.status = "pending"
            plan.save(plan_path)
            break

        # Execute actions
        results = execute_step_actions(actions, project_dir, config, config.autonomy)

        # Commit this step
        all_ok = all(r.success for r in results) if results else True
        if all_ok:
            commit_result = git_commit(
                f"reeree: {step.description}",
                project_dir,
            )
            if commit_result.success:
                step.commit_hash = commit_result.output.split(":")[0].split()[-1] if ":" in commit_result.output else None
                console.print(f"  [green]{commit_result.output}[/green]")
            step.status = "done"
        else:
            step.status = "pending"  # Keep pending so user can retry
            console.print("[yellow]Step had failures. Fix and re-run, or skip.[/yellow]")

        plan.save(plan_path)

        # Between steps: let user steer
        if not plan.is_complete:
            console.print(f"\n[dim]({len([s for s in plan.steps if s.status == 'done'])}/{len(plan.steps)} steps done)[/dim]")
            next_action = Prompt.ask(
                "[green]next[/green] / [yellow]edit[/yellow] / [blue]undo[/blue] / [red]quit[/red]",
                choices=["next", "edit", "undo", "skip", "quit", "n", "e", "u", "s", "q"],
                default="next",
            )

            if next_action in ("quit", "q"):
                console.print("[dim]Plan saved. Resume with: reeree[/dim]")
                return
            elif next_action in ("edit", "e"):
                console.print(f"[dim]Edit: {plan_path}[/dim]")
                return
            elif next_action in ("undo", "u"):
                result = git_revert_last(project_dir)
                if result.success:
                    step.status = "pending"
                    step.commit_hash = None
                    plan.save(plan_path)
                    console.print("[green]Reverted last step[/green]")
                else:
                    console.print(f"[red]Revert failed: {result.output}[/red]")
            elif next_action in ("skip", "s"):
                next_step = plan.current_step
                if next_step:
                    next_step.status = "skipped"
                    plan.save(plan_path)

    if plan.is_complete:
        console.print(Panel(
            "[bold green]All steps complete![/bold green]\n\n" + plan.to_markdown(),
            title="Done",
            border_style="green",
        ))


if __name__ == "__main__":
    main()
