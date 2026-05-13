"""CLI command: heta recall."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from heta.config.io import load_config
from heta.mem.recall import recall

console = Console()

_LAYER_LABELS = {
    "raw": "L0 Raw",
    "episode": "L1 Episode",
    "atomic_fact": "L2 Atomic Fact",
}


def recall_command(
    query: str = typer.Argument(..., help="What to recall."),
    top_k: int = typer.Option(10, "--top-k", "-k", help="Results per layer."),
) -> None:
    """Retrieve and rank memories relevant to a query."""
    config = load_config()
    if config is None:
        console.print("[red]Heta is not initialised. Run `heta init` first.[/red]")
        raise typer.Exit(1)

    with console.status("[cyan]Searching memories...[/cyan]"):
        result = recall(query, config, top_k=top_k)

    ranking_str = " > ".join(_LAYER_LABELS.get(r, r) for r in result.ranking)

    lines = Text()
    lines.append("Layer ranking: ", style="dim")
    lines.append(ranking_str + "\n", style="bold cyan")
    lines.append("Reason: ", style="dim")
    lines.append(result.reason + "\n\n", style="italic")
    lines.append(result.answer, style="white")

    console.print(Panel(lines, title=f'[bold]Recall: "{result.query}"[/bold]', border_style="cyan"))

    console.print()
    for layer_ev in result.evidence:
        if not layer_ev.items:
            continue
        label = _LAYER_LABELS.get(layer_ev.layer, layer_ev.layer)
        console.print(f"[bold]{label}[/bold]")
        for item in layer_ev.items:
            score = item.get("score", 0)
            if layer_ev.layer == "raw":
                text = item["text_content"]
            elif layer_ev.layer == "episode":
                text = item["summary"]
            else:
                text = item["fact_text"]
            console.print(f"  [dim][score={score:.3f}][/dim] {text}")
        console.print()
