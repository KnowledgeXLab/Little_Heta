"""Wiki merge helpers for Little Heta KB."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from heta.kb.models import FileChange, ParsedDocument
from heta.kb.store import append_log
from heta.kb.text import frontmatter_page, slugify, summarize


@dataclass(frozen=True)
class MergeResult:
    added: list[FileChange]
    updated: list[FileChange]
    deleted: list[FileChange]


@dataclass(frozen=True)
class NormalizeResult:
    path_map: dict[str, str]


WIKI_PAGE_NAME_RE = re.compile(r"^(?P<id>\d+)-(?P<slug>.+)\.md$")


def merge_documents_into_wiki(documents: list[ParsedDocument], wiki_root: Path) -> MergeResult:
    pages = wiki_root / "pages"
    pages.mkdir(parents=True, exist_ok=True)
    _ensure_layout(wiki_root)

    added: list[FileChange] = []
    updated: list[FileChange] = []

    for document in documents:
        slug = slugify(document.title)
        page_path = pages / f"{slug}.md"
        page_rel = f"pages/{page_path.name}"
        summary = summarize(document.markdown_content)
        page = frontmatter_page(
            title=document.title,
            source_name=document.source_name,
            summary=summary,
            content=document.markdown_content,
        )

        if page_path.exists():
            _merge_existing_page(page_path, document)
            updated.append(FileChange("updated", document.title, page_rel))
            append_log(f"Merged content into page: {document.title} from {document.source_name}", wiki_root)
        else:
            page_path.write_text(page, encoding="utf-8")
            added.append(FileChange("added", document.title, page_rel))
            append_log(f"Created page: {document.title} from {document.source_name}", wiki_root)

        _upsert_index_entry(wiki_root / "index.md", document.title, page_rel, summary)

    return MergeResult(added=added, updated=updated, deleted=[])


def validate_wiki(wiki_root: Path) -> None:
    index = wiki_root / "index.md"
    log = wiki_root / "log.md"
    pages = wiki_root / "pages"

    if not index.exists():
        raise ValueError("working copy is missing index.md")
    if not log.exists():
        raise ValueError("working copy is missing log.md")
    if not pages.exists():
        raise ValueError("working copy is missing pages/")

    page_titles = set()
    for page in pages.glob("*.md"):
        text = page.read_text(encoding="utf-8").strip()
        if not text:
            raise ValueError(f"page is empty: {page.name}")
        title = _frontmatter_value(text, "title")
        sources = _frontmatter_value(text, "sources")
        updated = _frontmatter_value(text, "updated")
        if not title or not sources or not updated:
            raise ValueError(f"page frontmatter is incomplete: {page.name}")
        for heading in ("## Summary", "## Content", "## Related Pages", "## Source"):
            if heading not in text:
                raise ValueError(f"page is missing {heading}: {page.name}")
        page_titles.add(title.lower())
        page_titles.add(page.stem.lower())

    index_text = index.read_text(encoding="utf-8")
    for page in pages.glob("*.md"):
        text = page.read_text(encoding="utf-8")
        title = _frontmatter_value(text, "title") or page.stem
        rel_path = f"pages/{page.name}"
        if f"[[{title}]]" not in index_text or rel_path not in index_text:
            raise ValueError(f"index.md is missing page entry or path for: {page.name}")

    for page in pages.glob("*.md"):
        text = page.read_text(encoding="utf-8")
        for link in re.findall(r"\[\[([^\]]+)\]\]", text):
            if link.strip().lower() not in page_titles:
                raise ValueError(f"broken wiki link in {page.name}: {link}")


def repair_broken_wiki_links(wiki_root: Path) -> None:
    """Downgrade broken wiki links to plain text before validation."""
    pages = wiki_root / "pages"
    if not pages.exists():
        return

    page_titles = set()
    for page in pages.glob("*.md"):
        text = page.read_text(encoding="utf-8")
        title = _frontmatter_value(text, "title") or page.stem
        page_titles.add(title.strip().lower())
        page_titles.add(page.stem.strip().lower())

    for page in pages.glob("*.md"):
        text = page.read_text(encoding="utf-8")

        def replace(match: re.Match[str]) -> str:
            link = match.group(1).strip()
            if link.lower() in page_titles:
                return match.group(0)
            return link

        repaired = re.sub(r"\[\[([^\]]+)\]\]", replace, text)
        if repaired != text:
            page.write_text(repaired, encoding="utf-8")


def normalize_wiki_pages(wiki_root: Path) -> NormalizeResult:
    """Assign numeric page filename prefixes and rewrite index paths.

    This is intentionally a best-effort normalization layer, not validation.
    Agent-created pages can use semantic names; this function gives new pages
    stable numeric identities such as ``pages/12-hetagen.md``.
    """
    pages = wiki_root / "pages"
    pages.mkdir(parents=True, exist_ok=True)

    path_map: dict[str, str] = {}
    next_id = _next_wiki_id(pages)

    for page in sorted(pages.glob("*.md")):
        if _wiki_id_from_name(page.name) is not None:
            continue

        text = page.read_text(encoding="utf-8")
        title = _frontmatter_value(text, "title") or page.stem
        target_name = _available_numbered_name(pages, next_id, slugify(title))
        next_id += 1

        target = pages / target_name
        page.rename(target)
        path_map[f"pages/{page.name}"] = f"pages/{target.name}"

    _rewrite_index(wiki_root)
    return NormalizeResult(path_map=path_map)


def detect_wiki_changes(wiki_root: Path, before: dict[str, str]) -> MergeResult:
    pages = wiki_root / "pages"
    after = {
        f"pages/{page.name}": page.read_text(encoding="utf-8")
        for page in sorted(pages.glob("*.md"))
    } if pages.exists() else {}

    added: list[FileChange] = []
    updated: list[FileChange] = []
    deleted: list[FileChange] = []

    for path, content in after.items():
        title = _frontmatter_value(content, "title") or Path(path).stem
        if path not in before:
            added.append(FileChange("added", title, path))
        elif before[path] != content:
            updated.append(FileChange("updated", title, path))

    for path, content in before.items():
        if path not in after:
            title = _frontmatter_value(content, "title") or Path(path).stem
            deleted.append(FileChange("deleted", title, path))

    return MergeResult(added=added, updated=updated, deleted=deleted)


def apply_path_map(changes: list[FileChange], path_map: dict[str, str]) -> list[FileChange]:
    return [
        FileChange(change.kind, change.title, path_map.get(change.path, change.path))
        for change in changes
    ]


def _ensure_layout(wiki_root: Path) -> None:
    (wiki_root / "pages").mkdir(parents=True, exist_ok=True)
    index = wiki_root / "index.md"
    log = wiki_root / "log.md"
    if not index.exists():
        index.write_text("# Wiki Index\n\n", encoding="utf-8")
    if not log.exists():
        log.write_text("# Wiki Log\n\n", encoding="utf-8")


def _merge_existing_page(page_path: Path, document: ParsedDocument) -> None:
    existing = page_path.read_text(encoding="utf-8").rstrip()
    source_line = f"- {document.source_name}"
    addition = (
        "\n\n"
        "## Imported Update\n\n"
        f"Source: {document.source_name}\n\n"
        f"{document.markdown_content.strip()}\n"
    )
    updated = existing + addition
    if "## Source" in updated and source_line not in updated:
        updated += f"\n{source_line}\n"
    page_path.write_text(updated.rstrip() + "\n", encoding="utf-8")


def _upsert_index_entry(index_path: Path, title: str, page_path: str, summary: str) -> None:
    index = index_path.read_text(encoding="utf-8") if index_path.exists() else "# Wiki Index\n\n"
    entry = f"- [[{title}]] ({page_path})\n  - {summary}"
    pattern = re.compile(rf"- \[\[{re.escape(title)}\]\] \([^)]+\)\n  - .*(?:\n|$)")
    if pattern.search(index):
        index = pattern.sub(entry + "\n", index)
    else:
        if "## Imported Knowledge" not in index:
            index = index.rstrip() + "\n\n## Imported Knowledge\n\n"
        index = index.rstrip() + "\n\n" + entry + "\n"
    index_path.write_text(index.rstrip() + "\n", encoding="utf-8")


def _next_wiki_id(pages: Path) -> int:
    ids = [
        wiki_id
        for page in pages.glob("*.md")
        if (wiki_id := _wiki_id_from_name(page.name)) is not None
    ]
    return max(ids, default=0) + 1


def _wiki_id_from_name(filename: str) -> int | None:
    match = WIKI_PAGE_NAME_RE.match(filename)
    if match is None:
        return None
    return int(match.group("id"))


def _available_numbered_name(pages: Path, wiki_id: int, slug: str) -> str:
    base = f"{wiki_id}-{slug or 'untitled'}"
    candidate = f"{base}.md"
    if not (pages / candidate).exists():
        return candidate
    for suffix in range(1, 1000):
        candidate = f"{base}-{suffix}.md"
        if not (pages / candidate).exists():
            return candidate
    raise RuntimeError(f"Too many wiki pages with id {wiki_id}")


def _rewrite_index(wiki_root: Path) -> None:
    pages = wiki_root / "pages"
    entries: list[tuple[int, str]] = []
    for page in sorted(pages.glob("*.md"), key=_page_sort_key):
        wiki_id = _wiki_id_from_name(page.name)
        if wiki_id is None:
            continue
        text = page.read_text(encoding="utf-8")
        title = _frontmatter_value(text, "title") or page.stem
        summary = _summary_value(text) or "Imported knowledge page."
        entries.append((wiki_id, f"- [{wiki_id}] [[{title}]] (pages/{page.name}) — {summary}"))

    index_text = "# Wiki Index\n"
    if entries:
        index_text += "\n" + "\n".join(entry for _, entry in entries) + "\n"
    (wiki_root / "index.md").write_text(index_text, encoding="utf-8")


def _page_sort_key(page: Path) -> tuple[int, str]:
    wiki_id = _wiki_id_from_name(page.name)
    return (wiki_id if wiki_id is not None else 10**12, page.name)


def _summary_value(text: str) -> str | None:
    match = re.search(
        r"^## Summary\s*\n(?P<summary>.*?)(?:\n## |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    if match is None:
        return None
    for line in match.group("summary").splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _frontmatter_value(text: str, key: str) -> str | None:
    match = re.search(rf"^{re.escape(key)}:\s*(.+)$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else None
