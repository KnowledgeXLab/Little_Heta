from pathlib import Path

from heta.kb.text import frontmatter_page
from heta.kb.vector_index import chunk_wiki_page


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
