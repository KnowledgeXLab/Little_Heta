"""Filesystem and Git store for Little Heta Wiki."""

from __future__ import annotations

import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

from heta.kb import paths


def ensure_wiki_layout(base_dir: Path | None = None) -> None:
    paths.pages_dir(base_dir).mkdir(parents=True, exist_ok=True)
    index = paths.index_path(base_dir)
    log = paths.log_path(base_dir)
    if not index.exists():
        index.write_text("# Wiki Index\n\n", encoding="utf-8")
    if not log.exists():
        log.write_text("# Wiki Log\n\n", encoding="utf-8")
    ensure_wiki_repo(base_dir)


def ensure_wiki_repo(base_dir: Path | None = None) -> None:
    wiki = paths.wiki_dir(base_dir)
    wiki.mkdir(parents=True, exist_ok=True)
    if not (wiki / ".git").exists():
        _git(["init"], wiki)
    _git(["config", "user.name", "Little Heta"], wiki)
    _git(["config", "user.email", "little-heta@local"], wiki)


def save_raw_file(source: Path, base_dir: Path | None = None) -> Path:
    raw = paths.raw_dir(base_dir)
    raw.mkdir(parents=True, exist_ok=True)
    safe_name = source.name or "upload.bin"
    dated_name = f"{datetime.now():%Y-%m-%d_%H%M%S}_{safe_name}"
    target = _resolve_collision(raw, dated_name)
    shutil.copy2(source, target)
    return target


def save_raw_stream(filename: str, fileobj: BinaryIO, base_dir: Path | None = None) -> Path:
    raw = paths.raw_dir(base_dir)
    raw.mkdir(parents=True, exist_ok=True)
    safe_name = Path(filename).name or "upload.bin"
    target = _resolve_collision(raw, f"{datetime.now():%Y-%m-%d_%H%M%S}_{safe_name}")
    with target.open("wb") as file:
        while chunk := fileobj.read(1024 * 1024):
            file.write(chunk)
    return target


def append_log(message: str, root: Path) -> None:
    log = root / "log.md"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with log.open("a", encoding="utf-8") as file:
        file.write(f"- [{timestamp}] {message}\n")


def commit_wiki(message: str, base_dir: Path | None = None) -> str | None:
    wiki = paths.wiki_dir(base_dir)
    if not _is_dirty(wiki):
        return None
    _git(["add", "-A"], wiki)
    _git(["commit", "-m", message], wiki)
    return _git(["rev-parse", "--short", "HEAD"], wiki).strip()


def reset_wiki(base_dir: Path | None = None) -> None:
    wiki = paths.wiki_dir(base_dir)
    if not (wiki / ".git").exists():
        return
    _git(["reset", "--hard"], wiki)
    _git(["clean", "-fd"], wiki)


def _resolve_collision(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    for index in range(1, 1000):
        candidate = directory / f"{stem}({index}){suffix}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Too many files with the same name: {filename}")


def _is_dirty(repo_dir: Path) -> bool:
    output = _git(["status", "--porcelain"], repo_dir)
    return bool(output.strip())


def _git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git command failed")
    return result.stdout

