"""LLM-based episodic memory extraction."""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from heta.config.schema import HetaConfig
from heta.mem.client import extra_body
from heta.mem.prompts import EPISODE_EXTRACTION_PROMPT

logger = logging.getLogger(__name__)


def extract_episodes(
    client: OpenAI,
    model: str,
    text: str,
    config: HetaConfig,
) -> list[dict[str, Any]]:
    """Call the LLM and return a list of raw episode dicts."""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": EPISODE_EXTRACTION_PROMPT},
            {"role": "user", "content": text},
        ],
        temperature=0.2,
        **({"extra_body": extra_body(config)} if extra_body(config) else {}),
    )
    raw = response.choices[0].message.content or ""
    return _parse_episodes(raw)


def _parse_episodes(raw: str) -> list[dict[str, Any]]:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        data = json.loads(text)
        episodes = data.get("episodes", [])
        if not isinstance(episodes, list):
            return []
        return [e for e in episodes if isinstance(e, dict) and "what" in e]
    except (json.JSONDecodeError, AttributeError):
        logger.warning("Failed to parse episode extraction response: %s", raw[:200])
        return []
