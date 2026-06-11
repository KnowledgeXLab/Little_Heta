"""`heta mem-show` commands — inspect stored memories."""

from __future__ import annotations

import sqlite3
from datetime import datetime

import typer
from rich.console import Console
from rich.table import Table

from heta.cli.branding import HETA, MUTED, WARN
from heta.mem.db import get_connection, init_db
from heta.mem.paths import db_path

console = Console()

app = typer.Typer(
    name="mem-show",
    help="Browse the memories Little Heta has stored.",
    no_args_is_help=False,
    rich_markup_mode="rich",
)


@app.callback(invoke_without_command=True)
def mem_show_command(
    ctx: typer.Context,
    limit: int = typer.Option(50, "--limit", "-n", help="Max rows to show per memory layer."),
    full: bool = typer.Option(False, "--full", "-f", help="Show full text (no truncation)."),
) -> None:
    """List all stored memories, grouped by memory layer."""
    if ctx.invoked_subcommand is not None:
        return

    if not db_path().exists():
        console.print(f"[{WARN}]?[/] Memory DB does not exist yet.")
        console.print(f"[{MUTED}]  Run `heta remember` or `heta ask` at least once to populate it.[/]")
        raise typer.Exit(0)

    conn = get_connection(db_path(), with_vec=True)
    init_db(conn)
    try:
        memories = _fetch_all_memories(conn, limit=limit)
        totals = _count_all_memories(conn)
    finally:
        conn.close()

    if not any(memories.values()):
        console.print(f"[{MUTED}]No memories stored yet.[/]")
        return

    _print_all_memories(memories, totals=totals, full=full)


@app.command("insights")
def insights_command(
    source: str | None = typer.Option(None, "--source", "-s", help="Filter by source_path substring (e.g. 'pages/1-foo.md')."),
    question: str | None = typer.Option(None, "--question", "-q", help="Filter by question substring."),
    limit: int = typer.Option(50, "--limit", "-n", help="Max rows to show."),
    full: bool = typer.Option(False, "--full", "-f", help="Show full insight text (no truncation)."),
) -> None:
    """List stored kb_insight memories, newest first."""
    if not db_path().exists():
        console.print(f"[{WARN}]?[/] Memory DB does not exist yet.")
        console.print(f"[{MUTED}]  Run `heta ask` at least once to populate it.[/]")
        raise typer.Exit(0)

    conn = get_connection(db_path(), with_vec=True)
    init_db(conn)
    try:
        rows = _fetch_insights(conn, source=source, question=question, limit=limit)
        total = _count_total(conn, source=source, question=question)
    finally:
        conn.close()

    if not rows:
        console.print(f"[{MUTED}]No insights matched.[/]")
        return

    table = Table(
        title=f"kb_insights ({len(rows)} of {total} shown)",
        show_lines=not full,
        border_style=HETA,
    )
    table.add_column("#", style="dim", justify="right", no_wrap=True)
    table.add_column("created", style=MUTED, no_wrap=True)
    table.add_column("sources", style=MUTED)
    table.add_column("question", style=MUTED)
    table.add_column("insight")

    for i, row in enumerate(rows, 1):
        insight_text = row["insight"] if full else _truncate(row["insight"], 140)
        question_text = row["question"] or ""
        if not full:
            question_text = _truncate(question_text, 50)
        sources_text = "\n".join(row["source_paths"]) if full else _truncate(
            ", ".join(row["source_paths"]), 40
        )
        table.add_row(
            str(i),
            _format_ts(row["created_at"]),
            sources_text,
            question_text,
            insight_text,
        )
    console.print(table)


def _print_all_memories(memories: dict[str, list[dict]], *, totals: dict[str, int], full: bool) -> None:
    _print_l0(memories["l0"], total=totals["l0"], full=full)
    _print_l1(memories["l1"], total=totals["l1"], full=full)
    _print_l2(memories["l2"], total=totals["l2"], full=full)
    _print_kb_insights(memories["kb_insight"], total=totals["kb_insight"], full=full)


def _print_l0(rows: list[dict], *, total: int, full: bool) -> None:
    if not rows:
        return
    table = Table(title=f"L0 turns ({len(rows)} of {total} shown)", show_lines=not full, border_style=HETA)
    table.add_column("#", style="dim", justify="right", no_wrap=True)
    table.add_column("created", style=MUTED, no_wrap=True)
    table.add_column("role", style=MUTED, no_wrap=True)
    table.add_column("session", style=MUTED)
    table.add_column("text")
    for i, row in enumerate(rows, 1):
        text = row["text_content"] if full else _truncate(row["text_content"], 160)
        table.add_row(str(i), _format_ts(row["created_at"]), row["role"], _truncate(row["session_id"], 12), text)
    console.print(table)


def _print_l1(rows: list[dict], *, total: int, full: bool) -> None:
    if not rows:
        return
    table = Table(title=f"L1 episodes ({len(rows)} of {total} shown)", show_lines=not full, border_style=HETA)
    table.add_column("#", style="dim", justify="right", no_wrap=True)
    table.add_column("created", style=MUTED, no_wrap=True)
    table.add_column("when", style=MUTED)
    table.add_column("who", style=MUTED)
    table.add_column("summary")
    for i, row in enumerate(rows, 1):
        summary = row["summary"] if full else _truncate(row["summary"], 160)
        when = row["when_resolved"] or row["when_text"] or ""
        table.add_row(str(i), _format_ts(row["created_at"]), when, _truncate(row["who"], 40), summary)
    console.print(table)


def _print_l2(rows: list[dict], *, total: int, full: bool) -> None:
    if not rows:
        return
    table = Table(title=f"L2 facts ({len(rows)} of {total} shown)", show_lines=not full, border_style=HETA)
    table.add_column("#", style="dim", justify="right", no_wrap=True)
    table.add_column("created", style=MUTED, no_wrap=True)
    table.add_column("subject", style=MUTED)
    table.add_column("predicate", style=MUTED)
    table.add_column("fact")
    for i, row in enumerate(rows, 1):
        fact = row["fact_text"] or f'{row["subject"]} {row["predicate"]} {row["object"]}'
        if not full:
            fact = _truncate(fact, 160)
        table.add_row(str(i), _format_ts(row["created_at"]), row["subject"], row["predicate"], fact)
    console.print(table)


def _print_kb_insights(rows: list[dict], *, total: int, full: bool) -> None:
    if not rows:
        return
    table = Table(title=f"KB insights ({len(rows)} of {total} shown)", show_lines=not full, border_style=HETA)
    table.add_column("#", style="dim", justify="right", no_wrap=True)
    table.add_column("created", style=MUTED, no_wrap=True)
    table.add_column("sources", style=MUTED)
    table.add_column("insight")
    for i, row in enumerate(rows, 1):
        insight = row["insight"] if full else _truncate(row["insight"], 160)
        sources = "\n".join(row["source_paths"]) if full else _truncate(", ".join(row["source_paths"]), 60)
        table.add_row(str(i), _format_ts(row["created_at"]), sources, insight)
    console.print(table)


def _fetch_all_memories(conn: sqlite3.Connection, *, limit: int) -> dict[str, list[dict]]:
    limit = max(1, limit)
    return {
        "l0": _fetch_l0_turns(conn, limit=limit),
        "l1": _fetch_l1_episodes(conn, limit=limit),
        "l2": _fetch_l2_facts(conn, limit=limit),
        "kb_insight": _fetch_insights(conn, source=None, question=None, limit=limit),
    }


def _count_all_memories(conn: sqlite3.Connection) -> dict[str, int]:
    return {
        "l0": _count_rows(conn, "l0_turn"),
        "l1": _count_active_rows(conn, "l1_episodic", "e"),
        "l2": _count_active_rows(conn, "l2_semantic", "s", extra="AND s.t_valid_end IS NULL"),
        "kb_insight": _count_total(conn, source=None, question=None),
    }


def _fetch_l0_turns(conn: sqlite3.Connection, *, limit: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT session_id, turn_index, role, modality, text_content, created_at
        FROM l0_turn
        ORDER BY created_at DESC, turn_index DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def _fetch_l1_episodes(conn: sqlite3.Connection, *, limit: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT e.memory_id, e.who, e.what, e.where_loc, e.when_text, e.when_resolved,
               e.when_precision, e.why, e.summary, m.created_at, m.session_id
        FROM l1_episodic e
        JOIN memory_meta m ON m.memory_id = e.memory_id
        WHERE m.status = 'active'
        ORDER BY m.created_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def _fetch_l2_facts(conn: sqlite3.Connection, *, limit: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT s.memory_id, s.subject, s.predicate, s.object, s.object_type, s.fact_text,
               s.when_text, s.when_resolved, s.when_precision, m.created_at, m.session_id
        FROM l2_semantic s
        JOIN memory_meta m ON m.memory_id = s.memory_id
        WHERE m.status = 'active'
          AND s.t_valid_end IS NULL
        ORDER BY m.created_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def _count_rows(conn: sqlite3.Connection, table_name: str) -> int:
    row = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
    return int(row[0])


def _count_active_rows(conn: sqlite3.Connection, table_name: str, alias: str, *, extra: str = "") -> int:
    row = conn.execute(
        f"""
        SELECT COUNT(*)
        FROM {table_name} {alias}
        JOIN memory_meta m ON m.memory_id = {alias}.memory_id
        WHERE m.status = 'active'
        {extra}
        """
    ).fetchone()
    return int(row[0])


def _fetch_insights(
    conn: sqlite3.Connection,
    *,
    source: str | None,
    question: str | None,
    limit: int,
) -> list[dict]:
    """Fetch insights and their full source_paths list."""
    base_sql = """
        SELECT i.memory_id, i.insight, i.question, i.created_at
        FROM kb_insight i
        JOIN memory_meta m ON m.memory_id = i.memory_id
        WHERE m.status = 'active'
    """
    clauses, params = _build_filters(source=source, question=question)
    sql = f"{base_sql} {clauses} ORDER BY i.created_at DESC LIMIT ?"
    params.append(max(1, limit))
    rows = conn.execute(sql, params).fetchall()

    results = []
    for r in rows:
        paths = [
            row[0]
            for row in conn.execute(
                "SELECT source_path FROM kb_insight_source WHERE memory_id = ? ORDER BY source_path",
                (r["memory_id"],),
            ).fetchall()
        ]
        results.append({
            "insight": r["insight"],
            "question": r["question"],
            "source_paths": paths,
            "created_at": r["created_at"],
        })
    return results


def _count_total(
    conn: sqlite3.Connection,
    *,
    source: str | None,
    question: str | None,
) -> int:
    base_sql = """
        SELECT COUNT(*) FROM kb_insight i
        JOIN memory_meta m ON m.memory_id = i.memory_id
        WHERE m.status = 'active'
    """
    clauses, params = _build_filters(source=source, question=question)
    row = conn.execute(f"{base_sql} {clauses}", params).fetchone()
    return int(row[0])


def _build_filters(*, source: str | None, question: str | None) -> tuple[str, list]:
    clauses: list[str] = []
    params: list = []
    if source:
        clauses.append(
            "AND i.memory_id IN (SELECT memory_id FROM kb_insight_source WHERE source_path LIKE ?)"
        )
        params.append(f"%{source}%")
    if question:
        clauses.append("AND i.question LIKE ?")
        params.append(f"%{question}%")
    return " ".join(clauses), params


def _truncate(text: str, max_len: int) -> str:
    if text is None:
        return ""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _format_ts(ts: int | None) -> str:
    if not ts:
        return ""
    return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M")


__all__ = ["app"]
