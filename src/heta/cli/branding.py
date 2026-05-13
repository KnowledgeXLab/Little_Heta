"""Shared Little Heta CLI branding."""

from __future__ import annotations

from heta import __version__

HETA = "rgb(52,144,220)"
CYAN = "rgb(88,196,220)"
OK = "rgb(76,196,142)"
MUTED = "rgb(126,146,158)"

APP_TITLE = "Little Heta"
APP_TAGLINE = "Personal knowledge, memory, and document intelligence CLI"
APP_TEAM = "KnowledgeXLab"


def brand_line() -> str:
    return (
        f"[bold {HETA}]>_ {APP_TITLE}[/] "
        f"[bold {CYAN}]✦[/][bold {OK}]✧[/] "
        f"[{MUTED}]v{__version__}[/]"
    )


__all__ = ["APP_TAGLINE", "APP_TEAM", "APP_TITLE", "brand_line"]
