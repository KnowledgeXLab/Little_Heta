"""MinerU provider validation."""

from __future__ import annotations

from urllib.parse import urljoin

import requests

VALIDATION_TIMEOUT_SECONDS = 10.0
MINERU_CLOUD_VALIDATION_URL = "https://mineru.net/api/v4/file-urls/batch"


def validate_mineru_cloud(api_key: str) -> bool:
    """Validate a MinerU cloud API key with a lightweight batch URL request."""
    api_key = api_key.strip()
    try:
        response = requests.post(
            MINERU_CLOUD_VALIDATION_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"files": [{"name": "heta-init-validation.pdf"}]},
            timeout=VALIDATION_TIMEOUT_SECONDS,
        )
    except requests.RequestException:
        return False
    return response.status_code == 200


def validate_mineru_local(endpoint: str) -> bool:
    """Validate a local MinerU endpoint by calling GET /health."""
    normalized_endpoint = endpoint.strip().rstrip("/") + "/"
    try:
        response = requests.get(
            urljoin(normalized_endpoint, "health"),
            timeout=VALIDATION_TIMEOUT_SECONDS,
        )
    except requests.RequestException:
        return False
    return response.status_code == 200
