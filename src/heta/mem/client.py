"""LLM and embedding client factories for the memory module."""

from __future__ import annotations

from openai import OpenAI

from heta.config.schema import HetaConfig

EXTRACTION_MODELS = {
    "qwen": "qwen-plus",
    "chatgpt": "gpt-4.1-mini",
    "gemini": "gemini-2.5-flash",
}

EMBEDDING_MODELS = {
    "qwen": "text-embedding-v4",
    "chatgpt": "text-embedding-3-small",
    "gemini": "text-embedding-004",
}

EMBEDDING_DIM = 1024

_BASE_URLS = {
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
}


def _make_client(config: HetaConfig, timeout: int) -> OpenAI:
    kwargs: dict = {"api_key": config.llm.api_key, "timeout": timeout}
    if config.llm.provider in _BASE_URLS:
        kwargs["base_url"] = _BASE_URLS[config.llm.provider]
    return OpenAI(**kwargs)


def build_client(config: HetaConfig) -> tuple[OpenAI, str]:
    """Return (client, model) for text generation."""
    if config.llm.provider not in EXTRACTION_MODELS:
        raise ValueError(f"Unsupported LLM provider: {config.llm.provider}")
    return _make_client(config, timeout=60), EXTRACTION_MODELS[config.llm.provider]


def build_embedding_client(config: HetaConfig) -> tuple[OpenAI, str]:
    """Return (client, model) for embedding generation."""
    if config.llm.provider not in EMBEDDING_MODELS:
        raise ValueError(f"Unsupported embedding provider: {config.llm.provider}")
    return _make_client(config, timeout=120), EMBEDDING_MODELS[config.llm.provider]


def extra_body(config: HetaConfig) -> dict | None:
    if config.llm.provider == "qwen":
        return {"enable_thinking": False}
    return None
