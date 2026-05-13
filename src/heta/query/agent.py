"""Read-only agent loop for Little Heta wiki query."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from heta.config.schema import HetaConfig
from heta.kb.agent import AgentStats, _chat_completion, _get_client
from heta.query.models import QueryResult, QuerySource, VectorMatch
from heta.query.tools import (
    format_vector_matches,
    read_index,
    read_page,
    search_vector,
    source_from_page_path,
)

QUERY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_page",
            "description": "Read a wiki page. Valid paths: pages/*.md.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_vector",
            "description": "Search semantic wiki chunks. Returns wiki id, page path, heading path, content, and score.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer", "minimum": 1, "maximum": 10},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
]


def run_query_agent(
    *,
    question: str,
    config: HetaConfig,
    base_dir: Path | None = None,
    top_k: int = 5,
    extra_context: str | None = None,
    max_steps: int = 8,
    max_seconds: int = 180,
    temperature: float = 0.2,
) -> QueryResult:
    client, model = _get_client(config)
    stats = AgentStats(task_id="query", max_steps=max_steps, max_seconds=max_seconds)
    index_text = read_index(base_dir)
    initial_matches = search_vector(question, config, top_k=top_k, base_dir=base_dir)
    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": _initial_message(
                question=question,
                index_text=index_text,
                vector_matches=initial_matches,
                extra_context=extra_context,
            ),
        }
    ]
    read_paths: set[str] = set()
    vector_sources: dict[str, VectorMatch] = {match.path: match for match in initial_matches}
    tools = QUERY_TOOLS if config.vector_index.enable else [QUERY_TOOLS[0]]

    while stats.should_continue():
        response = _chat_completion(
            client=client,
            model=model,
            messages=[{"role": "system", "content": _system_prompt(config.vector_index.enable)}, *messages],
            tools=tools,
            temperature=temperature,
            config=config,
        )
        message = response.choices[0].message
        tool_calls = list(message.tool_calls or [])

        if not tool_calls:
            stats.record_completion(response.usage)
            return QueryResult(
                answer=message.content or "",
                sources=_build_sources(read_paths=read_paths, vector_sources=vector_sources, base_dir=base_dir),
                usage=stats.finish("completed"),
            )

        assistant_message: dict[str, Any] = {"role": "assistant"}
        if message.content:
            assistant_message["content"] = message.content
        assistant_message["tool_calls"] = [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                },
            }
            for tool_call in tool_calls
        ]
        messages.append(assistant_message)
        messages.extend(_execute_tools(tool_calls, config, base_dir, top_k, read_paths, vector_sources))
        stats.record(", ".join(tool.function.name for tool in tool_calls), response.usage)

    messages.append(
        {
            "role": "user",
            "content": "You reached the step or time limit. Do not call tools. Answer with the evidence already available.",
        }
    )
    final = _chat_completion(
        client=client,
        model=model,
        messages=[{"role": "system", "content": _system_prompt(config.vector_index.enable)}, *messages],
        tools=None,
        temperature=temperature,
        config=config,
    )
    stats.record_completion(final.usage)
    return QueryResult(
        answer=final.choices[0].message.content or "",
        sources=_build_sources(read_paths=read_paths, vector_sources=vector_sources, base_dir=base_dir),
        usage=stats.finish("stopped at limit"),
    )


def _system_prompt(vector_enabled: bool) -> str:
    vector_rule = (
        "- You may call search_vector again with a refined query if the current evidence is insufficient."
        if vector_enabled
        else "- Vector search is disabled; rely on the index and pages you read."
    )
    return f"""You are Little Heta's read-only wiki query agent.

Answer the user's question using the Little Heta wiki. You can inspect the wiki,
but you must not create, edit, delete, rename, or commit anything.

Rules:
- Treat index.md as the global map of pages, ids, paths, and summaries.
- Treat semantic matches as starting evidence, not final truth.
- If a chunk is relevant but incomplete, call read_page(path) for the full page.
- Follow useful [[Wiki Links]] by reading the linked pages when the index gives their paths.
{vector_rule}
- Stop reading when the context is enough.
- If the wiki does not contain enough evidence, say what is missing.
- Answer directly and include a short Sources section with page titles or paths you used.
"""


def _initial_message(
    *,
    question: str,
    index_text: str,
    vector_matches: list[VectorMatch],
    extra_context: str | None,
) -> str:
    parts = [
        f"Current date: {datetime.now().date().isoformat()}",
        f"Question:\n{question}",
        f"Wiki Index:\n{index_text or '(index.md is missing or empty)'}",
        f"Semantic Matches:\n{format_vector_matches(vector_matches)}",
    ]
    if extra_context:
        parts.append(f"Extra Context:\n{extra_context}")
    return "\n\n".join(parts)


def _execute_tools(
    tool_calls: list[Any],
    config: HetaConfig,
    base_dir: Path | None,
    default_top_k: int,
    read_paths: set[str],
    vector_sources: dict[str, VectorMatch],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for tool_call in tool_calls:
        name = tool_call.function.name
        try:
            arguments = json.loads(tool_call.function.arguments or "{}")
        except json.JSONDecodeError as exc:
            output = f"error: invalid tool arguments: {exc}"
        else:
            if name == "read_page":
                path = str(arguments.get("path", ""))
                output = read_page(path, base_dir)
                if not output.startswith("error:"):
                    read_paths.add(path.replace("\\", "/").strip("/"))
            elif name == "search_vector":
                query = str(arguments.get("query", ""))
                top_k = int(arguments.get("top_k") or default_top_k)
                matches = search_vector(query, config, top_k=top_k, base_dir=base_dir)
                for match in matches:
                    vector_sources.setdefault(match.path, match)
                output = format_vector_matches(matches)
            else:
                output = f"error: unknown tool {name}"
        results.append({"role": "tool", "tool_call_id": tool_call.id, "content": output})
    return results


def _build_sources(
    *,
    read_paths: set[str],
    vector_sources: dict[str, VectorMatch],
    base_dir: Path | None,
) -> list[QuerySource]:
    sources: dict[str, QuerySource] = {}
    for path, match in vector_sources.items():
        sources[path] = source_from_page_path(path, base_dir, heading_path=match.heading_path)
    for path in sorted(read_paths):
        sources[path] = source_from_page_path(path, base_dir)
    return list(sources.values())

