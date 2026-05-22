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


def test_parse_document_uses_local_mineru_zip_artifacts(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "paper.pdf"
    archived = tmp_path / "2026-05-15_paper.pdf"
    source.write_bytes(b"%PDF")
    archived.write_bytes(b"%PDF")
    zip_bytes = _mineru_zip(
        "# Paper\n\n![](images/figure.jpg)\n",
        content_list=[
            {
                "type": "image",
                "img_path": "images/figure.jpg",
                "bbox": [1, 2, 3, 4],
                "page_idx": 2,
            }
        ],
        images={"images/figure.jpg": b"jpg"},
    )
    config = HetaConfig(
        version=1,
        llm=LLMConfig(provider="qwen", api_key="sk-test"),
        mineru=MinerUConfig(enable=True, provider="local", api_key=None, endpoint="http://127.0.0.1:8000"),
        vector_index=VectorIndexConfig(enable=False),
        insert_planning=InsertPlanningConfig.enabled(),
    )

    def post(url, **kwargs):
        assert url == "http://127.0.0.1:8000/file_parse"
        assert "files" in kwargs["files"]
        assert kwargs["data"]["response_format_zip"] == "true"
        assert kwargs["data"]["return_content_list"] == "true"
        return _Response(content=zip_bytes, headers={"content-type": "application/zip"})

    monkeypatch.setattr("heta.kb.parser.requests.post", post)

    document = parse_document(
        source,
        archived,
        config,
        original_name="paper.pdf",
        page_offset=20,
        base_dir=tmp_path,
    )

    assert "../../raw/parsed/2026-05-15_paper/images/figure.jpg" in document.markdown_content
    assert "Source: paper.pdf, page 23, bbox [1, 2, 3, 4]" in document.markdown_content
    parsed = tmp_path / "workspace" / "kb" / "raw" / "parsed" / "2026-05-15_paper"
    assert (parsed / "full.md").exists()
    assert (parsed / "content_list.json").exists()
    assert (parsed / "images" / "figure.jpg").read_bytes() == b"jpg"


def _mineru_zip(
    markdown: str,
    *,
    content_list: list[dict] | None = None,
    images: dict[str, bytes] | None = None,
) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("full.md", markdown)
        if content_list is not None:
            import json

            archive.writestr("demo_content_list.json", json.dumps(content_list))
        for path, data in (images or {}).items():
            archive.writestr(path, data)
    return buffer.getvalue()
