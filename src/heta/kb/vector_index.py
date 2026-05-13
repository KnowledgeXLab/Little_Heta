"""SQLite-vec index for Little Heta wiki chunks."""

from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import sqlite_vec
from openai import OpenAI

from heta.config.schema import HetaConfig
from heta.kb import paths
from heta.kb.models import FileChange

EMBEDDING_DIM = 1024
EMBEDDING_MODELS = {
    "qwen": "text-embedding-v4",
    "chatgpt": "text-embedding-3-small",
    "gemini": "text-embedding-004",
}
EMBEDDING_BATCH_SIZE = 10
EMBEDDING_BASE_URLS = {
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
}
PAGE_NAME_RE = re.compile(r"^(?P<wiki_id>\d+)-.+\.md$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


@dataclass(frozen=True)
class WikiChunk:
    wiki_id: int
    page_name: str
    chunk_id: str
    heading_path: str
    content: str
    content_hash: str


@dataclass(frozen=True)
class WikiChunkSearchResult:
    wiki_id: int
    page_name: str
    chunk_id: str
    heading_path: str
    content: str
    distance: float
    score: float


def sync_wiki_vector_index(
    *,
    changes: Iterable[FileChange],
    config: HetaConfig,
    base_dir: Path | None = None,
) -> None:
    """Synchronize changed wiki pages into sqlite-vec.

    The wiki is the source of truth. Index failures intentionally do not affect
    wiki commits; callers can warn and continue.
    """
    db_path = paths.vector_db_path(base_dir)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    try:
        _ensure_schema(conn)
        changed = list(changes)
        deleted_wiki_ids: set[int] = set()
        pages_to_embed: dict[int, Path] = {}
        for change in changed:
            wiki_id = _wiki_id_from_path(change.path)
            if wiki_id is not None:
                if wiki_id not in deleted_wiki_ids:
                    _delete_page_chunks(conn, wiki_id)
                    deleted_wiki_ids.add(wiki_id)
            if change.kind == "deleted":
                continue
            page = paths.wiki_dir(base_dir) / change.path
            if page.exists() and wiki_id is not None:
                pages_to_embed[wiki_id] = page

        chunks = [chunk for page in pages_to_embed.values() for chunk in chunk_wiki_page(page)]
        if chunks:
            embeddings = _embed_texts([chunk.content for chunk in chunks], config)
            for chunk, embedding in zip(chunks, embeddings, strict=True):
                _insert_chunk(conn, chunk, embedding)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def search_wiki_vector_index(
    *,
    query: str,
    config: HetaConfig,
    top_k: int = 5,
    base_dir: Path | None = None,
) -> list[WikiChunkSearchResult]:
    """Return semantic wiki chunk matches from sqlite-vec."""
    db_path = paths.vector_db_path(base_dir)
    if not db_path.exists():
        return []

    conn = sqlite3.connect(db_path)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    try:
        embedding = _embed_texts([query], config)[0]
        rows = conn.execute(
            """
            SELECT
              c.wiki_id,
              c.page_name,
              c.chunk_id,
              c.heading_path,
              c.content,
              v.distance
            FROM wiki_chunk_vec v
            JOIN wiki_chunks c ON c.id = v.rowid
            WHERE v.embedding MATCH ? AND k = ?
            ORDER BY v.distance
            """,
            (sqlite_vec.serialize_float32(embedding), max(1, top_k)),
        ).fetchall()
    finally:
        conn.close()

    return [
        WikiChunkSearchResult(
            wiki_id=int(row[0]),
            page_name=str(row[1]),
            chunk_id=str(row[2]),
            heading_path=str(row[3]),
            content=str(row[4]),
            distance=float(row[5]),
            score=1.0 / (1.0 + float(row[5])),
        )
        for row in rows
    ]


def chunk_wiki_page(page: Path) -> list[WikiChunk]:
    wiki_id = _wiki_id_from_path(f"pages/{page.name}")
    if wiki_id is None:
        return []

    text = page.read_text(encoding="utf-8")
    title = _frontmatter_value(text, "title") or page.stem
    summary = _section_text(text, "Summary").strip()
    content = _section_text(text, "Content").strip()
    if not content:
        return []

    chunks: list[WikiChunk] = []
    sections = _content_sections(content)
    for index, (heading_path, body) in enumerate(sections):
        chunk_text = _chunk_text(title=title, summary=summary, heading_path=heading_path, body=body)
        content_hash = _hash_text(chunk_text)
        chunk_id = f"{wiki_id}:{content_hash[:16]}"
        chunks.append(
            WikiChunk(
                wiki_id=wiki_id,
                page_name=page.name,
                chunk_id=chunk_id,
                heading_path=heading_path or "Content",
                content=chunk_text,
                content_hash=content_hash,
            )
        )
    return chunks


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wiki_chunks (
          id INTEGER PRIMARY KEY,
          wiki_id INTEGER NOT NULL,
          page_name TEXT NOT NULL,
          chunk_id TEXT NOT NULL UNIQUE,
          heading_path TEXT NOT NULL,
          content TEXT NOT NULL,
          content_hash TEXT NOT NULL,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS wiki_chunk_vec USING vec0(
          embedding FLOAT[{EMBEDDING_DIM}]
        )
        """
    )


def _delete_page_chunks(conn: sqlite3.Connection, wiki_id: int) -> None:
    rowids = [row[0] for row in conn.execute("SELECT id FROM wiki_chunks WHERE wiki_id = ?", (wiki_id,))]
    for rowid in rowids:
        conn.execute("DELETE FROM wiki_chunk_vec WHERE rowid = ?", (rowid,))
    conn.execute("DELETE FROM wiki_chunks WHERE wiki_id = ?", (wiki_id,))


def _insert_chunk(conn: sqlite3.Connection, chunk: WikiChunk, embedding: list[float]) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    cursor = conn.execute(
        """
        INSERT INTO wiki_chunks (
          wiki_id, page_name, chunk_id, heading_path, content, content_hash, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            chunk.wiki_id,
            chunk.page_name,
            chunk.chunk_id,
            chunk.heading_path,
            chunk.content,
            chunk.content_hash,
            now,
        ),
    )
    conn.execute(
        "INSERT INTO wiki_chunk_vec(rowid, embedding) VALUES (?, ?)",
        (cursor.lastrowid, sqlite_vec.serialize_float32(embedding)),
    )


def _embed_texts(texts: list[str], config: HetaConfig) -> list[list[float]]:
    client = _embedding_client(config)
    embeddings: list[list[float]] = []
    for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[start : start + EMBEDDING_BATCH_SIZE]
        response = client.embeddings.create(
            model=EMBEDDING_MODELS[config.llm.provider],
            input=batch,
            dimensions=EMBEDDING_DIM,
        )
        embeddings.extend(item.embedding for item in response.data)
    return embeddings


def _embedding_client(config: HetaConfig) -> OpenAI:
    kwargs = {"api_key": config.llm.api_key, "timeout": 120}
    base_url = EMBEDDING_BASE_URLS.get(config.llm.provider)
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def _wiki_id_from_path(path: str) -> int | None:
    name = Path(path).name
    match = PAGE_NAME_RE.match(name)
    if match is None:
        return None
    return int(match.group("wiki_id"))


def _section_text(text: str, section: str) -> str:
    match = re.search(
        rf"^## {re.escape(section)}\s*\n(?P<body>.*?)(?:\n## |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    return match.group("body") if match else ""


def _frontmatter_value(text: str, key: str) -> str | None:
    match = re.search(rf"^{re.escape(key)}:\s*(.+)$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def _content_sections(content: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    heading_stack: list[tuple[int, str]] = [(2, "Content")]
    current_heading = "Content"
    current_lines: list[str] = []
    in_code = False

    def flush() -> None:
        body = "\n".join(current_lines).strip()
        if body:
            sections.append((current_heading, body))

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            current_lines.append(line)
            continue
        if not in_code and (match := HEADING_RE.match(line)):
            level = len(match.group(1))
            title = match.group(2).strip()
            if level >= 3:
                flush()
                current_lines = []
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                heading_stack.append((level, title))
                current_heading = " > ".join(title for _, title in heading_stack)
                continue
        current_lines.append(line)
    flush()
    return sections or [("Content", content.strip())]


def _chunk_text(*, title: str, summary: str, heading_path: str, body: str) -> str:
    parts = [f"Page: {title}"]
    if summary:
        parts.append(f"Summary: {summary}")
    parts.append(f"Section: {heading_path or 'Content'}")
    parts.append("")
    parts.append(body.strip())
    return "\n".join(parts).strip()


def _hash_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


__all__ = [
    "WikiChunk",
    "WikiChunkSearchResult",
    "chunk_wiki_page",
    "search_wiki_vector_index",
    "sync_wiki_vector_index",
]
