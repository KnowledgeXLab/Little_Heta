"""LLM client factory for the memory module."""

from __future__ import annotations

from openai import OpenAI

from heta.config.schema import HetaConfig

EXTRACTION_MODELS = {
    "qwen": "qwen-plus",
    "chatgpt": "gpt-4.1-mini",
    "gemini": "gemini-2.5-flash",
}


def build_client(config: HetaConfig) -> tuple[OpenAI, str]:
    provider = config.llm.provider
    model = EXTRACTION_MODELS[provider]
    if provider == "qwen":
        return (
            OpenAI(
                api_key=config.llm.api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                timeout=60,
            ),
            model,
        )
    if provider == "chatgpt":
        return OpenAI(api_key=config.llm.api_key, timeout=60), model
    if provider == "gemini":
        return (
            OpenAI(
                api_key=config.llm.api_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                timeout=60,
            ),
            model,
        )
    raise ValueError(f"Unsupported LLM provider: {provider}")


def extra_body(config: HetaConfig) -> dict | None:
    if config.llm.provider == "qwen":
        return {"enable_thinking": False}
    return None
