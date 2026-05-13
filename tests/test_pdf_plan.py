import json
from pathlib import Path

from pypdf import PdfWriter

from heta.config.schema import HetaConfig, LLMConfig, MinerUConfig, VectorIndexConfig
from heta.kb import paths
from heta.kb.pdf_plan import PDF_PAGE_THRESHOLD, SplitUnit, estimate_pdf_pages, plan_insert_files


def test_plan_insert_files_splits_large_pdf_and_keeps_original(tmp_path: Path) -> None:
    source = tmp_path / "large.pdf"
    _write_pdf(source, PDF_PAGE_THRESHOLD + 1)

    prepared, plans = plan_insert_files([source], base_dir=tmp_path)

    assert len(plans) == 1
    assert plans[0].enabled is True
    assert plans[0].page_count == PDF_PAGE_THRESHOLD + 1
    assert plans[0].parts == 3
    assert len(prepared) == 3
    assert (paths.raw_dir(tmp_path) / "originals").exists()
    assert all(item.archived_path.exists() for item in prepared)
    assert [estimate_pdf_pages(item.archived_path) for item in prepared] == [40, 40, 1]
    assert all(item.original_path is not None for item in prepared)
    assert all(item.metadata_path is not None and item.metadata_path.exists() for item in prepared)


def test_plan_insert_files_can_disable_pdf_planning(tmp_path: Path) -> None:
    source = tmp_path / "large.pdf"
    _write_pdf(source, PDF_PAGE_THRESHOLD + 1)

    prepared, plans = plan_insert_files([source], enable_pdf_planning=False, base_dir=tmp_path)

    assert len(prepared) == 1
    assert len(plans) == 1
    assert plans[0].enabled is False
    assert prepared[0].archived_path.exists()
    assert estimate_pdf_pages(prepared[0].archived_path) == PDF_PAGE_THRESHOLD + 1
    assert not (paths.raw_dir(tmp_path) / "originals").exists()


def test_plan_insert_files_uses_agent_split_plan(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "large.pdf"
    _write_pdf(source, PDF_PAGE_THRESHOLD + 1)

    monkeypatch.setattr(
        "heta.kb.pdf_plan.run_pdf_planning_agent",
        lambda profile, config: {
            "document_type": "textbook",
            "split_strategy": "chapter",
            "units": [
                {"title": "Chapter 1: Introduction", "start_page": 1, "end_page": 30},
                {"title": "Chapter 2: Methods", "start_page": 31, "end_page": 81},
            ],
        },
    )

    prepared, plans = plan_insert_files([source], config=_config(), base_dir=tmp_path)

    assert plans[0].document_type == "textbook"
    assert plans[0].split_strategy == "chapter"
    assert [item.page_start for item in prepared] == [1, 31, 71]
    assert [item.page_end for item in prepared] == [30, 70, 81]
    metadata = json.loads(prepared[0].metadata_path.read_text(encoding="utf-8"))
    assert metadata["original"].endswith("large.pdf")
    assert metadata["start_page"] == 1
    assert metadata["end_page"] == 30
    assert metadata["split_strategy"] == "chapter"


def test_plan_insert_files_falls_back_when_agent_plan_is_invalid(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "large.pdf"
    _write_pdf(source, PDF_PAGE_THRESHOLD + 1)
    monkeypatch.setattr(
        "heta.kb.pdf_plan.run_pdf_planning_agent",
        lambda profile, config: {
            "document_type": "report",
            "split_strategy": "section",
            "units": [{"title": "Invalid", "start_page": 90, "end_page": 100}],
        },
    )

    prepared, plans = plan_insert_files([source], config=_config(), base_dir=tmp_path)

    assert plans[0].split_strategy == "fixed_page_window"
    assert [estimate_pdf_pages(item.archived_path) for item in prepared] == [40, 40, 1]


def test_plan_insert_files_fills_pages_missing_from_agent_plan(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "large.pdf"
    _write_pdf(source, PDF_PAGE_THRESHOLD + 1)
    monkeypatch.setattr(
        "heta.kb.pdf_plan.run_pdf_planning_agent",
        lambda profile, config: {
            "document_type": "mixed",
            "split_strategy": "section",
            "units": [{"title": "Only Middle", "start_page": 41, "end_page": 60}],
        },
    )

    prepared, plans = plan_insert_files([source], config=_config(), base_dir=tmp_path)

    assert plans[0].split_strategy == "section"
    assert [(item.page_start, item.page_end) for item in prepared] == [(1, 40), (41, 60), (61, 81)]


def _write_pdf(path: Path, pages: int) -> None:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=72, height=72)
    with path.open("wb") as file:
        writer.write(file)


def _config() -> HetaConfig:
    return HetaConfig(
        version=1,
        llm=LLMConfig(provider="qwen", api_key="sk-test"),
        mineru=MinerUConfig.disabled(),
        vector_index=VectorIndexConfig(enable=False),
    )
