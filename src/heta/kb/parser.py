"""File parsing for Little Heta KB."""

from __future__ import annotations

import mimetypes
import time
import zipfile
from io import BytesIO
from pathlib import Path

import requests

from heta.config.schema import HetaConfig
from heta.kb.audio_parser import AUDIO_EXTENSIONS, parse_audio_markdown
from heta.kb.code_parser import CODE_EXTENSIONS, parse_code_markdown
from heta.kb.discovery import MINERU_EXTENSIONS
from heta.kb.html_parser import HTML_EXTENSIONS, parse_html_markdown
from heta.kb.image_parser import IMAGE_EXTENSIONS, parse_image_markdown
from heta.kb.models import ParsedDocument
from heta.kb.text import extract_title


def parse_document(source_path: Path, archived_path: Path, config: HetaConfig) -> ParsedDocument:
    suffix = source_path.suffix.lower()
    if suffix in {".md", ".markdown", ".txt"}:
        markdown = source_path.read_text(encoding="utf-8")
    elif suffix in MINERU_EXTENSIONS:
        markdown = _parse_with_mineru(archived_path, config)
    elif suffix in IMAGE_EXTENSIONS:
        markdown = parse_image_markdown(source_path, archived_path, config)
    elif suffix in AUDIO_EXTENSIONS:
        markdown = parse_audio_markdown(source_path, archived_path, config)
    elif suffix in HTML_EXTENSIONS:
        markdown = parse_html_markdown(source_path, archived_path)
    elif suffix in CODE_EXTENSIONS:
        markdown = parse_code_markdown(source_path, archived_path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")

    title = extract_title(markdown, source_path.stem.replace("_", " ").replace("-", " ").title())
    return ParsedDocument(
        source_path=source_path,
        archived_path=archived_path,
        title=title,
        markdown_content=markdown,
        source_name=archived_path.name,
        metadata={"extension": suffix},
    )


def _parse_with_mineru(path: Path, config: HetaConfig) -> str:
    if not config.mineru.enable:
        raise ValueError(f"Document parsing requires MinerU: {path.name}")
    if config.mineru.provider == "local":
        return _parse_with_local_mineru(path, config.mineru.endpoint or "")
    if config.mineru.provider == "cloud":
        return _parse_with_cloud_mineru(path, config.mineru.api_key or "")
    raise ValueError("Invalid MinerU configuration.")


def _parse_with_local_mineru(path: Path, endpoint: str) -> str:
    url = endpoint.rstrip("/") + "/file_parse"
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    with path.open("rb") as file:
        response = requests.post(url, files={"file": (path.name, file, content_type)}, timeout=300)
    if response.status_code != 200:
        raise RuntimeError(f"MinerU local parse failed: HTTP {response.status_code}")

    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = response.json()
        for key in ("markdown", "content", "text", "md"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
        data = payload.get("data")
        if isinstance(data, dict):
            for key in ("markdown", "content", "text", "md"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    return value
        raise RuntimeError("MinerU local response did not include markdown content.")

    return response.text


def _parse_with_cloud_mineru(path: Path, api_key: str) -> str:
    if not api_key.strip():
        raise ValueError("MinerU cloud parsing requires api_key.")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "*/*",
    }
    create_response = requests.post(
        "https://mineru.net/api/v4/file-urls/batch",
        headers=headers,
        json={
            "files": [{"name": path.name, "data_id": path.stem}],
            "language": "ch",
            "enable_table": True,
            "enable_formula": True,
            "model_version": "vlm",
        },
        timeout=30,
    )
    if create_response.status_code != 200:
        raise RuntimeError(f"MinerU cloud task creation failed: HTTP {create_response.status_code}")

    payload = create_response.json()
    if payload.get("code") != 0:
        raise RuntimeError(f"MinerU cloud task creation failed: {payload.get('msg')}")
    batch_id = payload.get("data", {}).get("batch_id")
    file_urls = payload.get("data", {}).get("file_urls")
    if not batch_id or not isinstance(file_urls, list) or not file_urls:
        raise RuntimeError("MinerU cloud did not return batch_id and file_urls.")

    with path.open("rb") as file:
        upload_response = requests.put(file_urls[0], data=file, timeout=120)
    if upload_response.status_code not in {200, 201, 204}:
        raise RuntimeError(f"MinerU cloud upload failed: HTTP {upload_response.status_code}")

    zip_url = _poll_mineru_zip_url(batch_id, headers=headers, file_name=path.name)
    zip_response = requests.get(zip_url, timeout=120)
    if zip_response.status_code != 200:
        raise RuntimeError(f"MinerU zip download failed: HTTP {zip_response.status_code}")
    markdown = _extract_mineru_markdown(zip_response.content).strip()
    if not markdown:
        raise RuntimeError("MinerU cloud returned empty markdown.")
    return markdown


def _poll_mineru_zip_url(
    batch_id: str,
    *,
    headers: dict[str, str],
    file_name: str,
    timeout_seconds: int = 300,
) -> str:
    deadline = time.time() + timeout_seconds
    url = f"https://mineru.net/api/v4/extract-results/batch/{batch_id}"
    while time.time() < deadline:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            raise RuntimeError(f"MinerU cloud polling failed: HTTP {response.status_code}")
        payload = response.json()
        if payload.get("code") != 0:
            raise RuntimeError(f"MinerU cloud polling failed: {payload.get('msg')}")
        result = _mineru_batch_result(payload, file_name=file_name)
        state = result.get("state")
        if state == "done":
            zip_url = result.get("full_zip_url")
            if not zip_url:
                raise RuntimeError("MinerU cloud result did not include full_zip_url.")
            return zip_url
        if state == "failed":
            raise RuntimeError(f"MinerU cloud parsing failed: {result.get('err_msg') or result.get('err_code')}")
        time.sleep(2)
    raise TimeoutError(f"MinerU cloud parsing timed out after {timeout_seconds}s: {batch_id}")


def _mineru_batch_result(payload: dict, *, file_name: str) -> dict:
    results = payload.get("data", {}).get("extract_result")
    if isinstance(results, list):
        for result in results:
            if isinstance(result, dict) and result.get("file_name") == file_name:
                return result
        if results and isinstance(results[0], dict):
            return results[0]
    return {}


def _extract_mineru_markdown(zip_content: bytes) -> str:
    with zipfile.ZipFile(BytesIO(zip_content)) as archive:
        names = archive.namelist()
        for name in names:
            if name.endswith("full.md"):
                return archive.read(name).decode("utf-8")
        for name in names:
            if name.endswith(".md"):
                return archive.read(name).decode("utf-8")
    raise RuntimeError("MinerU zip did not include markdown output.")
