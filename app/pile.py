"""Turn a paste into stamped verdicts and store them."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.db import connect, ensure_schema, keyword_search, semantic_search
from app.judge import (
    JUDGE_SYSTEM,
    SPLIT_SYSTEM,
    VerdictError,
    brief_lines,
    build_judge_prompt,
    normalize_verdicts,
    parse_items,
)
from app.ollama_client import OllamaBadJSON, OllamaUnavailable, chat_json, embed, vector_literal
from app.samples import MEMORIES
from app.search import rrf_fusion

MAX_CHARS = 12000


def _chat_once_or_twice(system: str, user: str, num_predict: int) -> dict:
    try:
        return chat_json(system, user, num_predict)
    except OllamaBadJSON:
        return chat_json(system, user, num_predict)


def _public_item(row: dict) -> dict:
    created = row["created_at"]
    if isinstance(created, datetime):
        created = created.isoformat()
    return {
        "id": row["id"],
        "created_at": created,
        "body": row["body"],
        "verdict": row["verdict"],
        "summary": row["summary"],
        "script": row.get("script") or "",
        "origin": row.get("origin", "pile"),
        "matched_id": row.get("matched_id"),
    }


def _memory_count(conn) -> int:
    return conn.execute(
        "SELECT count(*) AS n FROM lazyyyyy.pile_items WHERE origin = 'memory'"
    ).fetchone()["n"]


def ensure_memories() -> None:
    with connect() as conn:
        ensure_schema(conn)
        if _memory_count(conn):
            return
    prepared = []
    now = datetime.now(timezone.utc)
    for memory in MEMORIES:
        prepared.append(
            (
                now - timedelta(days=memory["days_ago"]),
                memory["body"],
                vector_literal(embed(memory["body"])),
                memory["summary"],
            )
        )
    with connect() as conn:
        ensure_schema(conn)
        if _memory_count(conn):
            return
        for created_at, body, literal, summary in prepared:
            conn.execute(
                """
                INSERT INTO lazyyyyy.pile_items
                    (created_at, body, embedding, verdict, summary, origin)
                VALUES (%s, %s, %s::halfvec(768), 'pardon', %s, 'memory')
                """,
                (created_at, body, literal, summary),
            )


def history(limit: int = 12) -> list[dict]:
    with connect() as conn:
        ensure_schema(conn)
        rows = conn.execute(
            """
            SELECT id, created_at, body, verdict, summary, script, origin, matched_id
            FROM lazyyyyy.pile_items
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
    return [_public_item(row) for row in rows]


def process_pile(text: str, seed_memory: bool):
    text = text.strip()
    if not text:
        yield {"error": "The pile is empty."}
        return
    if len(text) > MAX_CHARS:
        yield {"error": "That paste is too long. Keep it under 12,000 characters."}
        return

    yield {"status": "Reading the pile"}
    try:
        items = parse_items(_chat_once_or_twice(SPLIT_SYSTEM, text, 700))
    except OllamaUnavailable as exc:
        yield {"error": str(exc)}
        return
    except (OllamaBadJSON, VerdictError):
        yield {"error": "Gemma couldn't split this pile. Try again, or paste fewer notes."}
        return

    try:
        with connect() as conn:
            ensure_schema(conn)
        if seed_memory:
            yield {"status": "Checking old pardons"}
            ensure_memories()

        yield {"status": "Searching what you've gotten away with"}
        literals = [vector_literal(embed(item)) for item in items]
        packed = []
        neighbor_lists = []
        allowed_ids: set[int] = set()
        with connect() as conn:
            for item, literal in zip(items, literals):
                keyword_rows = keyword_search(conn, item)
                semantic_rows = semantic_search(conn, literal)
                neighbors = rrf_fusion(keyword_rows, semantic_rows, limit=3)
                for neighbor in neighbors:
                    allowed_ids.add(int(neighbor["id"]))
                packed.append({"body": item, "literal": literal})
                neighbor_lists.append(neighbors)
    except (RuntimeError, OllamaUnavailable) as exc:
        yield {"error": str(exc)}
        return

    yield {"status": "Stamping verdicts"}
    try:
        payload = _chat_once_or_twice(
            JUDGE_SYSTEM,
            build_judge_prompt(items, neighbor_lists),
            1400,
        )
        verdicts = normalize_verdicts(payload, len(items), allowed_ids)
    except OllamaUnavailable as exc:
        yield {"error": str(exc)}
        return
    except (OllamaBadJSON, VerdictError):
        yield {"error": "Gemma didn't stamp every note. Try the pile again."}
        return

    line_one, line_two = brief_lines(payload, verdicts)
    index_to_id: dict[int, int] = {}
    saved = []
    try:
        with connect() as conn:
            for verdict in verdicts:
                item = packed[verdict["index"]]
                matched_id = verdict["matched_id"]
                matched_index = verdict["matched_index"]
                if matched_id is None and matched_index in index_to_id:
                    matched_id = index_to_id[matched_index]
                row = conn.execute(
                    """
                    INSERT INTO lazyyyyy.pile_items
                        (body, embedding, verdict, summary, script, matched_id, origin)
                    VALUES (%s, %s::halfvec(768), %s, %s, %s, %s, 'pile')
                    RETURNING id, created_at, body, verdict, summary, script, origin, matched_id
                    """,
                    (
                        item["body"],
                        item["literal"],
                        verdict["verdict"],
                        verdict["summary"],
                        verdict["script"] or None,
                        matched_id,
                    ),
                ).fetchone()
                index_to_id[verdict["index"]] = row["id"]
                saved.append(_public_item(row))
    except RuntimeError as exc:
        yield {"error": str(exc)}
        return

    yield {
        "done": True,
        "line_one": line_one,
        "line_two": line_two,
        "items": saved,
    }
