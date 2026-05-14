from pathlib import Path

from heta.config.schema import HetaConfig, InsertPlanningConfig, LLMConfig, MinerUConfig, VectorIndexConfig
from heta.kb.audio_parser import build_audio_markdown
from heta.kb.parser import parse_document
from heta.kb.text import extract_title


def _config() -> HetaConfig:
    return HetaConfig(
        version=1,
        llm=LLMConfig(provider="qwen", api_key="sk-test"),
        mineru=MinerUConfig.disabled(),
        vector_index=VectorIndexConfig(enable=False),
        insert_planning=InsertPlanningConfig.enabled(),
    )


def test_build_audio_markdown_uses_compact_retrieval_sections() -> None:
    markdown = build_audio_markdown(
        title="Audio - Meeting",
        source_name="meeting.mp3",
        media_path="../../raw/meeting.mp3",
        media_kind="Audio",
        summary="A meeting recording.",
        transcript="Speaker 1: Let's ship the feature.",
        key_points_metadata="Decision: ship the feature. Language: English.",
        interpretation_keywords="Meeting notes. keywords: feature, release.",
    )

    assert extract_title(markdown, "fallback") == "Audio - Meeting"
    assert "[Audio file](<../../raw/meeting.mp3>)" in markdown
    assert "### Transcript" in markdown
    assert "### Key Points and Metadata" in markdown
    assert "### Interpretation and Keywords" in markdown
    assert "## Related Pages" in markdown
    assert "## Source" in markdown


def test_build_audio_markdown_supports_video_link_label() -> None:
    markdown = build_audio_markdown(
        title="Video - Demo",
        source_name="demo.mp4",
        media_path="../../raw/demo.mp4",
        media_kind="Video",
        summary="A product demo.",
        transcript="Narrator: This is the dashboard.",
        key_points_metadata="Media type: video.",
        interpretation_keywords="Product demo, dashboard.",
    )

    assert "[Video file](<../../raw/demo.mp4>)" in markdown


def test_parse_document_accepts_audio_branch(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "meeting.mp3"
    archived = tmp_path / "raw_meeting.mp3"
    source.write_bytes(b"mp3")
    archived.write_bytes(b"mp3")

    monkeypatch.setattr(
        "heta.kb.parser.parse_audio_markdown",
        lambda source_path, archived_path, config: build_audio_markdown(
            title="Audio - Meeting",
            source_name=archived_path.name,
            media_path="../../raw/raw_meeting.mp3",
            media_kind="Audio",
            summary="A meeting.",
            transcript="Speaker 1: hello.",
            key_points_metadata="Language: English.",
            interpretation_keywords="meeting, test",
        ),
    )

    document = parse_document(source, archived, _config())

    assert document.title == "Audio - Meeting"
    assert document.source_name == "raw_meeting.mp3"
    assert document.metadata["extension"] == ".mp3"
    assert "### Transcript" in document.markdown_content
