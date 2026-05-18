"""`heta mem-clean` command — wipe all memory data."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.prompt import Confirm

from heta.cli.branding import MUTED, OK
from heta.mem.clean import clean_memory
from heta.mem.db import get_connection, init_db
from heta.mem.paths import db_path, ensure_mem_dir

console = Console()


def mem_clean_command(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation."),
) -> None:
    """Erase everything Little Heta has remembered."""
    if not yes and not Confirm.ask(
        "Delete all memory data? This cannot be undone.",
        default=False,
    ):
        console.print(f"[{MUTED}]Cancelled.[/]")
        raise typer.Exit(0)

    ensure_mem_dir()
    conn = get_connection(db_path(), with_vec=True)
    init_db(conn)
    result = clean_memory(conn)
    conn.close()

    console.print(f"[{OK}]✓[/] Memory cleared.")
    console.print(f"  [{MUTED}]sessions:[/] {result.deleted_sessions}")
    console.print(f"  [{MUTED}]L0 turns:[/] {result.deleted_l0_turns}")
    console.print(f"  [{MUTED}]L1 episodes:[/] {result.deleted_l1_episodes}")
    console.print(f"  [{MUTED}]L2 facts:[/] {result.deleted_l2_facts}")
    console.print(f"  [{MUTED}]KB insights:[/] {result.deleted_kb_insights}")
    console.print(f"  [{MUTED}]memory_meta rows:[/] {result.deleted_meta}")
