"""Semantic conflict detection for L2 fact memories."""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from heta.config.schema import HetaConfig
from heta.mem.client import extra_body
from heta.mem.embedder import embed_text
from heta.mem.l2_store import search_similar_facts
from heta.mem.prompts import CONFLICT_JUDGE_PROMPT

logger = logging.getLogger(__name__)


def detect_conflicts(
    conn: Any,
    new_fact_text: str,
    llm_client: OpenAI,
    llm_model: str,
    emb_client: OpenAI,
    emb_model: str,
    config: HetaConfig,
    top_k: int = 10,
    session_id: str | None = None,
) -> list[str]:
    """Return memory_ids of existing facts that the new fact contradicts."""
    embedding = embed_text(emb_client, emb_model, new_fact_text)
    candidates = search_similar_facts(conn, embedding, top_k=top_k, exclude_session_id=session_id)

    if not candidates:
        return [], embedding

    ids_to_deprecate = _judge(llm_client, llm_model, new_fact_text, candidates, config)
    return ids_to_deprecate, embedding


def _judge(
    client: OpenAI,
    model: str,
    new_fact_text: str,
    candidates: list[dict],
    config: HetaConfig,
) -> list[str]:
    candidate_lines = "\n".join(
        f'- id: "{c["memory_id"]}"  fact: "{c["fact_text"]}"'
        for c in candidates
    )
    user_msg = f'New fact: "{new_fact_text}"\n\nExisting facts:\n{candidate_lines}'

    kwargs: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": CONFLICT_JUDGE_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.0,
    }
    body = extra_body(config)
    if body:
        kwargs["extra_body"] = body

    response = client.chat.completions.create(**kwargs)
    raw = (response.choices[0].message.content or "").strip()
    return _parse_judge_response(raw)


def _parse_judge_response(raw: str) -> list[str]:
    text = raw
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        data = json.loads(text)
        result = data.get("deprecate", [])
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, AttributeError):
        logger.warning("Failed to parse conflict judge response: %s", raw[:200])
        return []
