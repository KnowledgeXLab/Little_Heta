"""Embedding calls for the memory module."""

from __future__ import annotations

from openai import OpenAI

from heta.mem.client import EMBEDDING_DIM


def embed_text(client: OpenAI, model: str, text: str) -> list[float]:
    response = client.embeddings.create(
        model=model,
        input=[text],
        dimensions=EMBEDDING_DIM,
    )
    return response.data[0].embedding


def fact_text(subject: str, predicate: str, object_: str) -> str:
    """Convert a triple to a natural language string for embedding."""
    return f"{subject} {predicate.replace('_', ' ')} {object_}"
