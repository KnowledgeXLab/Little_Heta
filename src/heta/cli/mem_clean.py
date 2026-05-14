"""`heta mem-clean` command — wipe all memory data."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.prompt import Confirm

from heta.mem.clean import clean_memory
from heta.mem.db import get_connection, init_db
from heta.mem.paths import db_path, ensure_mem_dir

console = Console()


def mem_clean_command(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation."),
) -> None:
    """Wipe all memory (personal + KB cache). Schema is preserved."""
    if not yes and not Confirm.ask(
        "Delete all memory data? This cannot be undone.",
        default=False,
    ):
        console.print("[dim]Cancelled.[/dim]")
        raise typer.Exit(0)

    ensure_mem_dir()
    conn = get_connection(db_path(), with_vec=True)
    init_db(conn)
    result = clean_memory(conn)
    conn.close()

    console.print("[green]✓[/green] Memory cleared.")
    console.print(f"  [dim]sessions:[/dim] {result.deleted_sessions}")
    console.print(f"  [dim]L0 turns:[/dim] {result.deleted_l0_turns}")
    console.print(f"  [dim]L1 episodes:[/dim] {result.deleted_l1_episodes}")
    console.print(f"  [dim]L2 facts:[/dim] {result.deleted_l2_facts}")
    console.print(f"  [dim]KB insights:[/dim] {result.deleted_kb_insights}")
    console.print(f"  [dim]memory_meta rows:[/dim] {result.deleted_meta}")
