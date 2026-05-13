"""Orchestrator for the heta recall pipeline."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from heta.config.schema import HetaConfig
from heta.mem.client import build_client, build_embedding_client, extra_body
from heta.mem.db import get_connection, init_db
from heta.mem.embedder import embed_text
from heta.mem.l0_search import search_turns
from heta.mem.l1_search import search_episodes
from heta.mem.l2_store import search_similar_facts
from heta.mem.paths import db_path, ensure_mem_dir
from heta.mem.prompts import RECALL_RANKER_PROMPT

logger = logging.getLogger(__name__)


@dataclass
class LayerEvidence:
    layer: str          # raw / episode / atomic_fact
    items: list[dict] = field(default_factory=list)


@dataclass
class RecallResult:
    query: str
    ranking: list[str]
    answer: str
    reason: str
    evidence: list[LayerEvidence]


def recall(query: str, config: HetaConfig, top_k: int = 10) -> RecallResult:
    ensure_mem_dir()
    conn = get_connection(db_path(), with_vec=True)
    init_db(conn)

    llm_client, llm_model = build_client(config)
    emb_client, emb_model = build_embedding_client(config)

    query_embedding = embed_text(emb_client, emb_model, query)

    l0_hits = search_turns(conn, query, top_k=top_k)
    l1_hits = search_episodes(conn, query_embedding, top_k=top_k)
    l2_hits = search_similar_facts(conn, query_embedding, top_k=top_k)

    conn.close()

    evidence = [
        LayerEvidence(layer="raw", items=l0_hits),
        LayerEvidence(layer="episode", items=l1_hits),
        LayerEvidence(layer="atomic_fact", items=l2_hits),
    ]

    ranking, answer, reason = _rank(
        query=query,
        evidence=evidence,
        client=llm_client,
        model=llm_model,
        config=config,
    )

    return RecallResult(
        query=query,
        ranking=ranking,
        answer=answer,
        reason=reason,
        evidence=evidence,
    )


def _rank(
    query: str,
    evidence: list[LayerEvidence],
    client,
    model: str,
    config: HetaConfig,
) -> tuple[list[str], str, str]:
    evidence_text = _format_evidence(evidence)
    user_msg = f"Question:\n{query}\n\nRetrieved evidence from each memory layer:\n{evidence_text}"

    kwargs: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": RECALL_RANKER_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.2,
    }
    body = extra_body(config)
    if body:
        kwargs["extra_body"] = body

    response = client.chat.completions.create(**kwargs)
    raw = (response.choices[0].message.content or "").strip()
    return _parse_rank_response(raw)


def _format_evidence(evidence: list[LayerEvidence]) -> str:
    parts = []
    for layer_ev in evidence:
        parts.append(f"## {layer_ev.layer}")
        if not layer_ev.items:
            parts.append("(no results)")
        else:
            for i, item in enumerate(layer_ev.items, 1):
                score = item.get("score", 0)
                if layer_ev.layer == "raw":
                    parts.append(f"[{i}; score={score:.4f}] {item['text_content']}")
                elif layer_ev.layer == "episode":
                    parts.append(f"[{i}; score={score:.4f}] {item['summary']}")
                else:
                    parts.append(f"[{i}; score={score:.4f}] {item['fact_text']}")
    return "\n".join(parts)


def _parse_rank_response(raw: str) -> tuple[list[str], str, str]:
    text = raw
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        data = json.loads(text)
        ranking = data.get("ranking", [])
        answer = data.get("answer", "")
        reason = data.get("reason", "")
        return ranking, answer, reason
    except (json.JSONDecodeError, AttributeError):
        logger.warning("Failed to parse ranker response: %s", raw[:200])
        return [], raw, ""
