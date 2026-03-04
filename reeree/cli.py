"""reeree CLI — entry point for the living document interface."""

import click
import sys
from pathlib import Path

from .config import Config
from .plan import Plan
from .planner import create_plan


@click.group(invoke_without_command=True)
@click.argument("intent", nargs=-1, required=False)
@click.option("--model", help="Model to use (e.g. deepseek-coder-v2:latest)")
@click.option("--api-base", help="API base URL")
@click.option("--api-key", help="API key")
@click.option("--autonomy", type=click.Choice(["low", "medium", "high", "full"]), default="medium")
@click.option("--project", type=click.Path(exists=True), default=".", help="Project directory")
@click.option("--setup", is_flag=True, help="Launch setup wizard")
@click.pass_context
def main(ctx, intent, model, api_base, api_key, autonomy, project, setup):
    """reeree — edit a markdown document. daemons respond to what you write.

    Examples:
        reeree                                  # open TUI (resume plan or blank)
        reeree "add error handling to scraper"  # open TUI with generated plan
        reeree ls                               # list sessions
        reeree kill                             # kill daemon
    """
    if ctx.invoked_subcommand is not None:
        return

    project_dir = Path(project).resolve()

    # Load config
    config = Config.load(project_dir / ".reeree" / "config.json")
    if model:
        config.model = model
    if api_base:
        config.api_base = api_base
    if api_key:
        config.api_key = api_key
    config.autonomy = autonomy

    # Load or create plan
    plan_path = project_dir / ".reeree" / "plan.md"
    plan = None

    if intent:
        intent_str = " ".join(intent)
        click.echo(f"Planning: {intent_str}")
        try:
            plan = create_plan(intent_str, project_dir, config)
            plan.save(plan_path)
            click.echo(f"Plan: {plan_path} ({len(plan.steps)} steps)")
        except Exception as e:
            click.echo(f"Failed to create plan: {e}", err=True)
            sys.exit(1)
    elif plan_path.exists():
        plan = Plan.load(plan_path)
        done, total = plan.progress
        click.echo(f"Resuming: {plan_path} ({done}/{total} done)")
    else:
        click.echo(f"No plan. Edit {plan_path} or pass an intent.")

    if plan is None:
        plan = Plan(intent="", steps=[])

    # Force first-run setup if --setup flag
    if setup:
        config.api_key = ""
        config.models = {}

    # Launch TUI
    from .tui.app import ReereeApp
    app = ReereeApp(project_dir=project_dir, config=config, plan=plan)
    app.run()


@main.command()
def ls():
    """List active sessions."""
    # TODO: read from daemon socket
    click.echo("Sessions: (daemon not yet implemented)")


@main.command()
def kill():
    """Kill the daemon."""
    # TODO: send kill to daemon
    click.echo("Kill: (daemon not yet implemented)")


if __name__ == "__main__":
    main()
