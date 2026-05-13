"""Typed configuration schema for Little Heta."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

LLMProvider = Literal["qwen", "chatgpt", "gemini"]
MinerUProvider = Literal["cloud", "local"]


@dataclass(frozen=True)
class LLMConfig:
    provider: LLMProvider
    api_key: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LLMConfig":
        provider = data.get("provider")
        api_key = data.get("api_key")
        if provider not in {"qwen", "chatgpt", "gemini"}:
            raise ValueError("Invalid LLM provider in config.")
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("Invalid LLM api_key in config.")
        return cls(provider=provider, api_key=api_key)


@dataclass(frozen=True)
class MinerUConfig:
    enable: bool
    provider: MinerUProvider | None
    api_key: str | None
    endpoint: str | None

    @classmethod
    def disabled(cls) -> "MinerUConfig":
        return cls(enable=False, provider=None, api_key=None, endpoint=None)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MinerUConfig":
        enable = data.get("enable")
        provider = data.get("provider")
        api_key = data.get("api_key")
        endpoint = data.get("endpoint")

        if not isinstance(enable, bool):
            raise ValueError("Invalid MinerU enable flag in config.")
        if not enable:
            return cls.disabled()
        if provider not in {"cloud", "local"}:
            raise ValueError("Invalid MinerU provider in config.")
        if provider == "cloud" and (not isinstance(api_key, str) or not api_key.strip()):
            raise ValueError("MinerU cloud config requires api_key.")
        if provider == "local" and (not isinstance(endpoint, str) or not endpoint.strip()):
            raise ValueError("MinerU local config requires endpoint.")

        return cls(enable=True, provider=provider, api_key=api_key, endpoint=endpoint)


@dataclass(frozen=True)
class VectorIndexConfig:
    enable: bool

    @classmethod
    def enabled(cls) -> "VectorIndexConfig":
        return cls(enable=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VectorIndexConfig":
        enable = data.get("enable")
        if not isinstance(enable, bool):
            raise ValueError("Invalid vector_index enable flag in config.")
        return cls(enable=enable)


@dataclass(frozen=True)
class HetaConfig:
    version: int
    llm: LLMConfig
    mineru: MinerUConfig
    vector_index: VectorIndexConfig

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HetaConfig":
        version = data.get("version")
        if version != 1:
            raise ValueError("Unsupported config version.")
        llm = data.get("llm")
        mineru = data.get("mineru")
        vector_index = data.get("vector_index")
        if not isinstance(llm, dict):
            raise ValueError("Missing LLM config.")
        if not isinstance(mineru, dict):
            raise ValueError("Missing MinerU config.")
        if not isinstance(vector_index, dict):
            raise ValueError("Missing vector_index config.")
        return cls(
            version=1,
            llm=LLMConfig.from_dict(llm),
            mineru=MinerUConfig.from_dict(mineru),
            vector_index=VectorIndexConfig.from_dict(vector_index),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
