"""`heta query` command."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from heta.config.io import CONFIG_PATH, load_config
from heta.query import QueryResult, run_wiki_query

console = Console()

HETA = "rgb(52,144,220)"
MUTED = "rgb(126,146,158)"
WARN = "rgb(238,183,74)"


def query_command(
    question: str = typer.Argument(..., help="Question to answer from the Little Heta wiki."),
    top_k: int = typer.Option(5, "--top-k", min=1, max=10, help="Initial vector matches to include."),
) -> None:
    """Ask a read-only question against the Little Heta wiki."""
    config = load_config()
    if config is None:
        console.print(f"[{WARN}]?[/] Little Heta is not initialized.")
        console.print(f"[{MUTED}]  Missing config:[/] {CONFIG_PATH}")
        console.print(f"[{MUTED}]  Next:[/] [bold {HETA}]heta init[/]")
        raise typer.Exit(1)

    try:
        with console.status("Querying Little Heta wiki", spinner="dots"):
            result = run_wiki_query(question, config, top_k=top_k)
    except Exception as exc:
        console.print(f"[{WARN}]?[/] Query failed.")
        console.print(f"[{MUTED}]  Reason:[/] {exc}")
        raise typer.Exit(1) from exc

    _show_result(result)


def _show_result(result: QueryResult) -> None:
    console.print(
        Panel(
            result.answer.strip() or "No answer returned.",
            title="answer",
            border_style=HETA,
            padding=(1, 2),
        )
    )

    if not result.sources:
        return

    table = Table.grid(padding=(0, 2))
    table.add_column(style=f"bold {HETA}")
    table.add_column()
    for source in result.sources:
        label = f"[{source.wiki_id}]" if source.wiki_id is not None else "[?]"
        detail = source.title
        if source.heading_path:
            detail += f" — {source.heading_path}"
        detail += f" ({source.path})"
        table.add_row(label, detail)

    console.print()
    console.print(Panel(table, title="sources", border_style=HETA, padding=(1, 2)))

