from pathlib import Path

from heta.kb.text import frontmatter_page
import sqlite3

import sqlite_vec

from heta.config.schema import InsertPlanningConfig, HetaConfig, LLMConfig, MinerUConfig, VectorIndexConfig
from heta.kb import paths
from heta.kb.models import FileChange
from heta.kb.vector_index import (
    _ensure_schema,
    _insert_chunk,
    chunk_wiki_page,
    search_wiki_vector_index,
    sync_wiki_vector_index,
)


def test_chunk_wiki_page_uses_heading_path_and_page_context(tmp_path: Path) -> None:
    page = tmp_path / "12-hetagen.md"
    page.write_text(
        frontmatter_page(
            "HetaGen",
            "source.md",
            "Structured content generation.",
            """
### Capabilities

HetaGen supports table synthesis and Text-to-SQL.

### Table Synthesis

#### Submit a task

Submit a question and poll by task id.
""",
        ),
        encoding="utf-8",
    )

    chunks = chunk_wiki_page(page)

    assert [chunk.heading_path for chunk in chunks] == [
        "Content > Capabilities",
        "Content > Table Synthesis > Submit a task",
    ]
    assert chunks[0].wiki_id == 12
    assert chunks[0].page_name == "12-hetagen.md"
    assert chunks[0].content.startswith("Page: HetaGen\nSummary: Structured content generation.")


def test_chunk_wiki_page_returns_empty_for_unnumbered_page(tmp_path: Path) -> None:
    page = tmp_path / "hetagen.md"
    page.write_text(frontmatter_page("HetaGen", "source.md", "Summary.", "Body."), encoding="utf-8")

    assert chunk_wiki_page(page) == []


def test_search_wiki_vector_index_returns_ranked_chunks(monkeypatch, tmp_path: Path) -> None:
    db_path = paths.vector_db_path(tmp_path)
    db_path.parent.mkdir(parents=True)
    conn = sqlite3.connect(db_path)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    _ensure_schema(conn)
    chunk = chunk_wiki_page(
        _write_page(
            tmp_path,
            "1-hetagen.md",
            "HetaGen",
            "Structured content generation.",
            "HetaGen supports table synthesis.",
        )
    )[0]
    _insert_chunk(conn, chunk, [1.0] + [0.0] * 1023)
    conn.commit()
    conn.close()

    monkeypatch.setattr("heta.kb.vector_index._embed_texts", lambda texts, config: [[1.0] + [0.0] * 1023])
    config = HetaConfig(
        version=1,
        llm=LLMConfig(provider="qwen", api_key="sk-test"),
        mineru=MinerUConfig.disabled(),
        vector_index=VectorIndexConfig.enabled(),
        insert_planning=InsertPlanningConfig.enabled(),
    )

    results = search_wiki_vector_index(query="table synthesis", config=config, top_k=3, base_dir=tmp_path)

    assert len(results) == 1
    assert results[0].wiki_id == 1
    assert results[0].page_name == "1-hetagen.md"
    assert results[0].heading_path == "Content"
    assert results[0].score == 1.0


def test_sync_wiki_vector_index_deduplicates_repeated_page_changes(monkeypatch, tmp_path: Path) -> None:
    _write_page(
        tmp_path,
        "1-hetagen.md",
        "HetaGen",
        "Structured content generation.",
        """
### Capabilities

HetaGen supports table synthesis.

### Query

HetaGen can answer structured questions.
""",
    )
    monkeypatch.setattr("heta.kb.vector_index._embed_texts", lambda texts, config: [[1.0] + [0.0] * 1023 for _ in texts])
    config = HetaConfig(
        version=1,
        llm=LLMConfig(provider="qwen", api_key="sk-test"),
        mineru=MinerUConfig.disabled(),
        vector_index=VectorIndexConfig.enabled(),
        insert_planning=InsertPlanningConfig.enabled(),
    )

    sync_wiki_vector_index(
        changes=[
            FileChange("added", "HetaGen", "pages/1-hetagen.md"),
            FileChange("updated", "HetaGen", "pages/1-hetagen.md"),
        ],
        config=config,
        base_dir=tmp_path,
    )

    conn = sqlite3.connect(paths.vector_db_path(tmp_path))
    try:
        assert conn.execute("SELECT count(*) FROM wiki_chunks").fetchone()[0] == 2
    finally:
        conn.close()


def _write_page(tmp_path: Path, name: str, title: str, summary: str, content: str) -> Path:
    page = paths.pages_dir(tmp_path) / name
    page.parent.mkdir(parents=True)
    page.write_text(frontmatter_page(title, "source.md", summary, content), encoding="utf-8")
    return page
