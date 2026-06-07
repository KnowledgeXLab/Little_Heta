from pathlib import Path

from heta.cli.status import build_status_summary
from heta.config.schema import InsertPlanningConfig, HetaConfig, LLMConfig, MinerUConfig, VectorIndexConfig


def test_status_summary_counts_kb_and_wiki_pages(tmp_path: Path) -> None:
    raw = tmp_path / "workspace" / "kb" / "raw"
    pages = tmp_path / "workspace" / "kb" / "wiki" / "pages"
    raw.mkdir(parents=True)
    pages.mkdir(parents=True)
    (raw / "note.md").write_text("raw", encoding="utf-8")
    (raw / "paper.pdf").write_bytes(b"pdf")
    (pages / "alpha.md").write_text("# Alpha", encoding="utf-8")
    (pages / "ignore.txt").write_text("no", encoding="utf-8")

    config = HetaConfig(
        version=1,
        llm=LLMConfig(provider="qwen", api_key="sk-test"),
        mineru=MinerUConfig(enable=True, provider="local", api_key=None, endpoint="http://127.0.0.1:8000"),
        vector_index=VectorIndexConfig.enabled(),
        insert_planning=InsertPlanningConfig.enabled(),
    )

    summary = build_status_summary(config, tmp_path)

    assert summary.llm_provider == "qwen"
    assert summary.mineru == "local (http://127.0.0.1:8000)"
    assert summary.insert_planning == "enabled"
    assert summary.dynamic_insert == "disabled"
    assert summary.kb_files == 2
    assert summary.wiki_pages == 1
    assert summary.heta_space == tmp_path
    assert summary.heta_used_bytes >= len("raw") + len(b"pdf") + len("# Alpha") + len("no")
    assert summary.disk_free_bytes > 0


def test_status_summary_handles_missing_config_and_workspace(tmp_path: Path) -> None:
    summary = build_status_summary(None, tmp_path)

    assert summary.llm_provider == "not configured"
    assert summary.mineru == "not configured"
    assert summary.insert_planning == "not configured"
    assert summary.dynamic_insert == "not configured"
    assert summary.kb_files == 0
    assert summary.wiki_pages == 0
    assert summary.heta_used_bytes == 0


def test_default_heta_space_is_config_home() -> None:
    summary = build_status_summary(None)

    assert str(summary.heta_space).endswith(".heta")
