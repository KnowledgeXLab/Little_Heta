"""Filesystem paths for the memory module."""

from __future__ import annotations

from pathlib import Path


def mem_dir() -> Path:
    return Path.home() / ".heta" / "workspace" / "mem"


def db_path() -> Path:
    return mem_dir() / "mem.sqlite3"


def ensure_mem_dir() -> Path:
    path = mem_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path
