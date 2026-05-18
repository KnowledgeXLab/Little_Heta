"""`heta insert-planning` commands."""

from __future__ import annotations

from dataclasses import replace

import typer
from rich.console import Console

from heta.cli.branding import HETA, MUTED, OK, WARN
from heta.config.io import CONFIG_PATH, load_config, save_config
from heta.config.schema import InsertPlanningConfig

console = Console()

app = typer.Typer(
    name="insert-planning",
    help="Manage Little Heta insert planning loops.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@app.command("on")
def insert_planning_on() -> None:
    """Enable insert planning loops such as large PDF split planning."""
    _set_insert_planning(True)


@app.command("true")
def insert_planning_true() -> None:
    """Enable insert planning loops."""
    _set_insert_planning(True)


@app.command("off")
def insert_planning_off() -> None:
    """Disable insert planning loops such as large PDF split planning."""
    _set_insert_planning(False)


@app.command("false")
def insert_planning_false() -> None:
    """Disable insert planning loops."""
    _set_insert_planning(False)


@app.command("status")
def insert_planning_status() -> None:
    """Show whether insert planning loops are enabled."""
    config = _require_config()
    state = "enabled" if config.insert_planning.enable else "disabled"
    console.print(f"[{MUTED}]insert planning:[/] [bold {HETA}]{state}[/]")


def _set_insert_planning(enable: bool) -> None:
    config = _require_config()
    updated = replace(config, insert_planning=InsertPlanningConfig(enable=enable))
    save_config(updated)
    state = "enabled" if enable else "disabled"
    console.print(f"[{OK}]✓[/] insert planning {state}")


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
