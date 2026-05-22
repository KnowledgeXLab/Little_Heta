"""File parsing for Little Heta KB."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import time
import zipfile
from io import BytesIO
from pathlib import Path

import requests

from heta.config.schema import HetaConfig
from heta.kb import paths
from heta.kb.audio_parser import AUDIO_EXTENSIONS, parse_audio_markdown
from heta.kb.code_parser import CODE_EXTENSIONS, parse_code_markdown
from heta.kb.discovery import MINERU_EXTENSIONS
from heta.kb.html_parser import HTML_EXTENSIONS, parse_html_markdown
from heta.kb.image_parser import IMAGE_EXTENSIONS, parse_image_markdown
from heta.kb.models import ParsedDocument
from heta.kb.text import extract_title


def parse_document(
    source_path: Path,
    archived_path: Path,
    config: HetaConfig,
    *,
    original_name: str | None = None,
    page_offset: int = 0,
    base_dir: Path | None = None,
) -> ParsedDocument:
    suffix = source_path.suffix.lower()
    if suffix in {".md", ".markdown", ".txt"}:
        markdown = source_path.read_text(encoding="utf-8")
    elif suffix in MINERU_EXTENSIONS:
        markdown = _parse_with_mineru(
            archived_path,
            config,
            original_name=original_name or source_path.name,
            page_offset=page_offset,
            base_dir=base_dir,
        )
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


def _parse_with_mineru(
    path: Path,
    config: HetaConfig,
    *,
    original_name: str | None = None,
    page_offset: int = 0,
    base_dir: Path | None = None,
) -> str:
    if not config.mineru.enable:
        raise ValueError(f"Document parsing requires MinerU: {path.name}")
    if config.mineru.provider == "local":
        return _parse_with_local_mineru(
            path,
            config.mineru.endpoint or "",
            original_name=original_name or path.name,
            page_offset=page_offset,
            base_dir=base_dir,
        )
    if config.mineru.provider == "cloud":
        return _parse_with_cloud_mineru(
            path,
            config.mineru.api_key or "",
            original_name=original_name or path.name,
            page_offset=page_offset,
            base_dir=base_dir,
        )
    raise ValueError("Invalid MinerU configuration.")


def _parse_with_local_mineru(
    path: Path,
    endpoint: str,
    *,
    original_name: str,
    page_offset: int,
    base_dir: Path | None,
) -> str:
    url = endpoint.rstrip("/") + "/file_parse"
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    with path.open("rb") as file:
        response = _resilient_request(
            "POST",
            url,
            files={"files": (path.name, file, content_type)},
            data={
                "lang_list": "ch",
                "backend": "hybrid-auto-engine",
                "parse_method": "auto",
                "formula_enable": "true",
                "table_enable": "true",
                "return_md": "true",
                "return_middle_json": "true",
                "return_model_output": "true",
                "return_content_list": "true",
                "return_images": "true",
                "return_original_file": "true",
                "response_format_zip": "true",
            },
            timeout=300,
        )
    if response.status_code != 200:
        raise RuntimeError(f"MinerU local parse failed: HTTP {response.status_code}")

    if _looks_like_zip_response(response):
        return _finalize_mineru_artifacts(
            zip_content=response.content,
            empty_error="MinerU local returned empty markdown.",
            path=path,
            original_name=original_name,
            page_offset=page_offset,
            base_dir=base_dir,
        )

    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        return _local_markdown_from_json(response.json())

    return response.text


def _parse_with_cloud_mineru(
    path: Path,
    api_key: str,
    *,
    original_name: str,
    page_offset: int,
    base_dir: Path | None,
) -> str:
    if not api_key.strip():
        raise ValueError("MinerU cloud parsing requires api_key.")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "*/*",
    }
    create_response = _resilient_request(
        "POST",
        "https://mineru.net/api/v4/file-urls/batch",
        headers=headers,
        json={
            "files": [{"name": path.name, "data_id": _safe_mineru_data_id(path.stem)}],
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

    upload_payload = path.read_bytes()  # buffer once so retries reuse the same bytes
    upload_response = _resilient_request("PUT", file_urls[0], data=upload_payload, timeout=120)
    if upload_response.status_code not in {200, 201, 204}:
        raise RuntimeError(f"MinerU cloud upload failed: HTTP {upload_response.status_code}")

    zip_url = _poll_mineru_zip_url(batch_id, headers=headers, file_name=path.name)
    zip_response = _resilient_request("GET", zip_url, timeout=120)
    if zip_response.status_code != 200:
        raise RuntimeError(f"MinerU zip download failed: HTTP {zip_response.status_code}")

    return _finalize_mineru_artifacts(
        zip_content=zip_response.content,
        empty_error="MinerU cloud returned empty markdown.",
        path=path,
        original_name=original_name,
        page_offset=page_offset,
        base_dir=base_dir,
    )


def _finalize_mineru_artifacts(
    *,
    zip_content: bytes,
    empty_error: str,
    path: Path,
    original_name: str,
    page_offset: int,
    base_dir: Path | None,
) -> str:
    artifacts = _extract_mineru_artifacts(zip_content)
    markdown = artifacts["markdown"].strip()
    if not markdown:
        raise RuntimeError(empty_error)

    if artifacts["content_list"] or artifacts["images"]:
        parsed_dir = paths.raw_dir(base_dir) / "parsed" / path.stem
        _persist_mineru_artifacts(parsed_dir, markdown, artifacts["content_list"], artifacts["images"])

    annotated = _annotate_mineru_markdown(
        markdown=markdown,
        content_list=artifacts["content_list"],
        original_name=original_name,
        page_offset=page_offset,
        part_stem=path.stem,
    )
    return annotated.strip()


def _looks_like_zip_response(response) -> bool:
    content_type = response.headers.get("content-type", "").lower()
    return "zip" in content_type or response.content.startswith(b"PK\x03\x04")


def _local_markdown_from_json(payload: dict) -> str:
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
        try:
            response = requests.get(url, headers=headers, timeout=30)
        except requests.exceptions.RequestException:
            time.sleep(5)
            continue
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


_MINERU_RETRY_BACKOFFS = (3, 5, 10, 20)


def _resilient_request(method: str, url: str, **kwargs):
    """HTTP request with retry on transient network/SSL/DNS/proxy errors.

    Retries on any `requests.RequestException`. Backoff series is
    `_MINERU_RETRY_BACKOFFS` (4 intervals → 5 attempts total).
    """
    funcs = {"GET": requests.get, "POST": requests.post, "PUT": requests.put}
    func = funcs[method.upper()]
    last_exc: Exception | None = None
    backoffs = (*_MINERU_RETRY_BACKOFFS, None)
    for backoff in backoffs:
        try:
            return func(url, **kwargs)
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            if backoff is None:
                raise
            time.sleep(backoff)
    assert last_exc is not None  # for type checker; loop always raises or returns
    raise last_exc


def _safe_mineru_data_id(stem: str, *, max_bytes: int = 120) -> str:
    """Keep MinerU's data_id under its 128-byte cap.

    CJK chars are 3 bytes in UTF-8, so a long part stem with Chinese section
    titles easily blows past the cap. Truncate the byte form and append a
    short content hash so two parts with the same prefix still get distinct ids.
    """
    encoded = stem.encode("utf-8")
    if len(encoded) <= max_bytes:
        return stem
    digest = hashlib.sha1(encoded).hexdigest()[:12]
    head = encoded[: max_bytes - len(digest) - 1].decode("utf-8", errors="ignore")
    return f"{head}_{digest}"


def _extract_mineru_artifacts(zip_content: bytes) -> dict:
    """Pull markdown, content_list.json, and image bytes out of MinerU's zip.

    The cloud zip layout (per inspected sample):
        full.md
        <uuid>_content_list.json        ← flat per-block list with bbox/page_idx
        <uuid>_content_list_v2.json     ← richer schema, not used
        images/<hash>.jpg               ← all images
        ...other debug files...
    """
    markdown = ""
    content_list: list[dict] = []
    images: dict[str, bytes] = {}

    with zipfile.ZipFile(BytesIO(zip_content)) as archive:
        names = archive.namelist()

        # Markdown: prefer full.md, fall back to any .md
        md_name = next((n for n in names if n.endswith("full.md")), None)
        if md_name is None:
            md_name = next((n for n in names if n.endswith(".md")), None)
        if md_name is None:
            raise RuntimeError("MinerU zip did not include markdown output.")
        markdown = archive.read(md_name).decode("utf-8")

        # Content list (v1, flat): the file ending in `_content_list.json` (not _v2)
        cl_name = next(
            (n for n in names if n.endswith("_content_list.json") and not n.endswith("_v2.json")),
            None,
        )
        if cl_name is not None:
            try:
                data = json.loads(archive.read(cl_name).decode("utf-8"))
                if isinstance(data, list):
                    content_list = [item for item in data if isinstance(item, dict)]
            except (json.JSONDecodeError, UnicodeDecodeError):
                content_list = []

        # Images
        for name in names:
            # Match "images/<hash>.ext" anywhere in the archive path.
            idx = name.find("images/")
            if idx == -1:
                continue
            rel = name[idx:]  # "images/<hash>.ext"
            if rel == "images/" or rel.endswith("/"):
                continue
            images[rel] = archive.read(name)

    return {"markdown": markdown, "content_list": content_list, "images": images}


def _persist_mineru_artifacts(
    parsed_dir: Path,
    markdown: str,
    content_list: list[dict],
    images: dict[str, bytes],
) -> None:
    """Write MinerU outputs to disk so external agents can read them later."""
    parsed_dir.mkdir(parents=True, exist_ok=True)
    (parsed_dir / "full.md").write_text(markdown, encoding="utf-8")
    (parsed_dir / "content_list.json").write_text(
        json.dumps(content_list, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if images:
        (parsed_dir / "images").mkdir(parents=True, exist_ok=True)
    for rel_path, data in images.items():
        # rel_path is like "images/<hash>.jpg"
        target = parsed_dir / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


# Image markdown line: ![alt](images/<filename>)
_MINERU_IMG_RE = re.compile(r"^!\[[^\]]*\]\(images/([^)]+)\)\s*$")
# Table block markers in MinerU markdown.
_MINERU_TABLE_OPEN_RE = re.compile(r"<table[\s>]", re.IGNORECASE)
_MINERU_TABLE_CLOSE_RE = re.compile(r"</table>", re.IGNORECASE)


def _annotate_mineru_markdown(
    *,
    markdown: str,
    content_list: list[dict],
    original_name: str,
    page_offset: int,
    part_stem: str,
) -> str:
    """Inject `Source:` lines after each image and table, and rewrite image paths.

    Image paths in MinerU markdown are `images/<hash>.jpg`, relative to the parser's
    own `full.md`. We rewrite them so they resolve from a wiki page at
    `<workspace>/wiki/pages/<id>-<slug>.md` to the persisted artifact at
    `<workspace>/raw/parsed/<part_stem>/images/<hash>.jpg`.
    """
    image_path_prefix = f"../../raw/parsed/{part_stem}/images/"

    # Queue figure/table provenance in document order. content_list emits items
    # in document order; we keep image and table queues separate so positional
    # matching is robust to missing items on either side.
    image_provenance = [
        (item.get("bbox"), item.get("page_idx"))
        for item in content_list
        if isinstance(item, dict) and item.get("type") == "image"
    ]
    table_provenance = [
        (item.get("bbox"), item.get("page_idx"))
        for item in content_list
        if isinstance(item, dict) and item.get("type") == "table"
    ]
    img_cursor = 0
    tbl_cursor = 0

    out_lines: list[str] = []
    in_table = False
    lines = markdown.splitlines()

    for line in lines:
        # Inside a table block: just pass lines through; check for close marker.
        if in_table:
            out_lines.append(line)
            if _MINERU_TABLE_CLOSE_RE.search(line):
                in_table = False
                src = _source_line_at(table_provenance, tbl_cursor, original_name, page_offset)
                if src is not None:
                    out_lines.append("")
                    out_lines.append(src)
                tbl_cursor += 1
            continue

        # Image line
        img_match = _MINERU_IMG_RE.match(line.strip())
        if img_match is not None:
            out_lines.append(f"![]({image_path_prefix}{img_match.group(1)})")
            src = _source_line_at(image_provenance, img_cursor, original_name, page_offset)
            if src is not None:
                out_lines.append("")
                out_lines.append(src)
            img_cursor += 1
            continue

        # Table start
        if _MINERU_TABLE_OPEN_RE.search(line):
            out_lines.append(line)
            if _MINERU_TABLE_CLOSE_RE.search(line):
                # Single-line table block — close immediately.
                src = _source_line_at(table_provenance, tbl_cursor, original_name, page_offset)
                if src is not None:
                    out_lines.append("")
                    out_lines.append(src)
                tbl_cursor += 1
            else:
                in_table = True
            continue

        out_lines.append(line)

    return "\n".join(out_lines)


def _source_line_at(
    provenance: list[tuple],
    cursor: int,
    original_name: str,
    page_offset: int,
) -> str | None:
    if cursor >= len(provenance):
        return None
    bbox, page_idx = provenance[cursor]
    if not isinstance(bbox, list) or len(bbox) != 4 or not isinstance(page_idx, int):
        return None
    page = page_offset + page_idx + 1
    bbox_str = f"[{bbox[0]}, {bbox[1]}, {bbox[2]}, {bbox[3]}]"
    return f"Source: {original_name}, page {page}, bbox {bbox_str}"
