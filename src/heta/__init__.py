"""Little Heta."""

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import re


def _version_from_pyproject() -> str | None:
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    if not pyproject.exists():
        return None
    text = pyproject.read_text(encoding="utf-8")
    if 'name = "little-heta"' not in text:
        return None
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return match.group(1) if match else None


try:
    __version__ = _version_from_pyproject() or version("little-heta")
except PackageNotFoundError:
    __version__ = "0.0.0"
