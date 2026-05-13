"""LLM-based semantic fact extraction."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from openai import OpenAI

from heta.config.schema import HetaConfig
from heta.mem.client import extra_body
from heta.mem.prompts import FACT_EXTRACTION_PROMPT

logger = logging.getLogger(__name__)


def extract_facts(
    client: OpenAI,
    model: str,
    text: str,
    config: HetaConfig,
    session_ts: int | None = None,
) -> list[dict[str, Any]]:
    """Call the LLM and return a list of raw fact dicts."""
    anchor_date = _fmt_date(session_ts)
    user_content = f"Anchor date: {anchor_date}\n\nText:\n{text}"

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": FACT_EXTRACTION_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.2,
        **({"extra_body": extra_body(config)} if extra_body(config) else {}),
    )
    raw = response.choices[0].message.content or ""
    return _parse_facts(raw)


def _fmt_date(ts: int | None) -> str:
    if ts is None:
        return datetime.now().strftime("%Y-%m-%d")
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


def _parse_facts(raw: str) -> list[dict[str, Any]]:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        data = json.loads(text)
        facts = data.get("facts", [])
        if not isinstance(facts, list):
            return []
        return [
            f for f in facts
            if isinstance(f, dict) and all(k in f for k in ("subject", "predicate", "object"))
        ]
    except (json.JSONDecodeError, AttributeError):
        logger.warning("Failed to parse fact extraction response: %s", raw[:200])
        return []
