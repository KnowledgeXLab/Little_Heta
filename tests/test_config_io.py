from pathlib import Path

from heta.config.io import load_config, save_config
from heta.config.schema import InsertPlanningConfig, HetaConfig, LLMConfig, MinerUConfig, VectorIndexConfig


def test_save_and_load_config(tmp_path: Path) -> None:
    path = tmp_path / ".heta" / "heta.yaml"
    config = HetaConfig(
        version=1,
        llm=LLMConfig(provider="qwen", api_key="sk-test"),
        mineru=MinerUConfig.disabled(),
        vector_index=VectorIndexConfig.enabled(),
        insert_planning=InsertPlanningConfig.enabled(),
    )

    save_config(config, path)
    loaded = load_config(path)

    assert loaded == config
    assert path.exists()


def test_load_missing_config_returns_none(tmp_path: Path) -> None:
    assert load_config(tmp_path / "missing.yaml") is None


def test_config_requires_insert_planning(tmp_path: Path) -> None:
    path = tmp_path / ".heta" / "heta.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(
        """
version: 1
llm:
  provider: qwen
  api_key: sk-test
mineru:
  enable: false
  provider:
  api_key:
  endpoint:
vector_index:
  enable: true
""",
        encoding="utf-8",
    )

    try:
        load_config(path)
    except ValueError as exc:
        assert "insert_planning" in str(exc)
    else:
        raise AssertionError("missing insert_planning should fail")
