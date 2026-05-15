from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path

from heta.config.schema import HetaConfig, InsertPlanningConfig, LLMConfig, MinerUConfig, VectorIndexConfig
from heta.kb.parser import parse_document


class _Response:
    def __init__(
        self,
        *,
        status_code: int = 200,
        payload: dict | None = None,
        content: bytes = b"",
        text: str = "",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.content = content
        self.text = text
        self.headers = headers or {}

    def json(self) -> dict:
        return self._payload


def _config() -> HetaConfig:
    return HetaConfig(
        version=1,
        llm=LLMConfig(provider="qwen", api_key="sk-test"),
        mineru=MinerUConfig(enable=True, provider="cloud", api_key="mineru-token", endpoint=None),
        vector_index=VectorIndexConfig(enable=False),
        insert_planning=InsertPlanningConfig.enabled(),
    )


def test_parse_document_accepts_office_via_mineru_cloud(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "slides.pptx"
    archived = tmp_path / "2026-05-15_slides.pptx"
    source.write_bytes(b"pptx")
    archived.write_bytes(b"pptx")
    zip_bytes = _mineru_zip("# Slides\n\nParsed by MinerU.")
    requests_seen: list[tuple[str, str]] = []

    def post(url, **kwargs):
        requests_seen.append(("POST", url))
        assert kwargs["headers"]["Authorization"] == "Bearer mineru-token"
        assert kwargs["json"]["files"] == [{"name": "2026-05-15_slides.pptx", "data_id": "2026-05-15_slides"}]
        assert kwargs["json"]["model_version"] == "vlm"
        return _Response(payload={"code": 0, "data": {"batch_id": "batch-1", "file_urls": ["https://upload"]}})

    def put(url, **kwargs):
        requests_seen.append(("PUT", url))
        assert url == "https://upload"
        return _Response(status_code=200)

    def get(url, **kwargs):
        requests_seen.append(("GET", url))
        if url.endswith("/batch-1"):
            assert kwargs["headers"]["Authorization"] == "Bearer mineru-token"
            return _Response(
                payload={
                    "code": 0,
                    "data": {
                        "extract_result": [
                            {
                                "file_name": "2026-05-15_slides.pptx",
                                "state": "done",
                                "full_zip_url": "https://result.zip",
                            }
                        ]
                    },
                }
            )
        assert url == "https://result.zip"
        return _Response(content=zip_bytes)

    monkeypatch.setattr("heta.kb.parser.requests.post", post)
    monkeypatch.setattr("heta.kb.parser.requests.put", put)
    monkeypatch.setattr("heta.kb.parser.requests.get", get)

    document = parse_document(source, archived, _config())

    assert document.title == "Slides"
    assert document.metadata["extension"] == ".pptx"
    assert document.markdown_content == "# Slides\n\nParsed by MinerU."
    assert [method for method, _ in requests_seen] == ["POST", "PUT", "GET", "GET"]


def _mineru_zip(markdown: str) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("full.md", markdown)
    return buffer.getvalue()
