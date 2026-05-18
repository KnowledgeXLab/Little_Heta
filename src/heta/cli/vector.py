"""`heta vector` commands."""

from __future__ import annotations

from dataclasses import replace

import typer
from rich.console import Console

from heta.cli.branding import HETA, MUTED, OK, WARN
from heta.config.io import CONFIG_PATH, load_config, save_config
from heta.config.schema import VectorIndexConfig

console = Console()

app = typer.Typer(
    name="vector",
    help="Manage Little Heta wiki vector indexing.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@app.command("on")
def vector_on() -> None:
    """Enable wiki vector indexing after insert."""
    _set_vector_index(True)


@app.command("off")
def vector_off() -> None:
    """Disable wiki vector indexing after insert."""
    _set_vector_index(False)


@app.command("status")
def vector_status() -> None:
    """Show whether wiki vector indexing is enabled."""
    config = _require_config()
    state = "enabled" if config.vector_index.enable else "disabled"
    console.print(f"[{MUTED}]vector index:[/] [bold {HETA}]{state}[/]")


def _set_vector_index(enable: bool) -> None:
    config = _require_config()
    updated = replace(config, vector_index=VectorIndexConfig(enable=enable))
    save_config(updated)
    state = "enabled" if enable else "disabled"
    console.print(f"[{OK}]✓[/] vector index {state}")


def _require_config():
    try:
        config = load_config()
    except Exception as exc:
        console.print(f"[{WARN}]?[/] Failed to read config: {exc}")
        raise typer.Exit(1) from exc
    if config is None:
        console.print(f"[{WARN}]?[/] Little Heta is not initialized.")
        console.print(f"[{MUTED}]  Missing config:[/] {CONFIG_PATH}")
        raise typer.Exit(1)
    return config


__all__ = ["app"]
