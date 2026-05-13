"""CLI command: heta remember."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel

from heta.config.io import load_config
from heta.mem.pipeline import remember

console = Console()


def remember_command(
    text: str = typer.Argument(..., help="Text to remember."),
) -> None:
    """Extract and store memories from a piece of text."""
    config = load_config()
    if config is None:
        console.print("[red]Heta is not initialised. Run `heta init` first.[/red]")
        raise typer.Exit(1)

    with console.status("[cyan]Extracting memories...[/cyan]"):
        result = remember(text, config)

    console.print(
        Panel(
            f"[green]L1 episodes:[/green] {result.l1_count}\n"
            f"[green]L2 facts:[/green]    {result.l2_count}\n"
            f"[dim]session: {result.session_id}[/dim]\n"
            f"[dim]elapsed: {result.elapsed_s}s[/dim]",
            title="[bold]Memory stored[/bold]",
            border_style="green",
        )
    )
