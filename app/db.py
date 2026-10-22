"""Tiger Cloud connection and the lazyyyyy schema."""

from __future__ import annotations

import os
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from app.ollama_client import EMBED_DIM

_use_bm25 = False


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is missing. Copy .env.example to .env and paste a Tiger connection string."
        )
    return url


@contextmanager
def connect():
    try:
        conn = psycopg.connect(database_url(), connect_timeout=15, row_factory=dict_row)
    except psycopg.OperationalError as exc:
        raise RuntimeError(
            "Tiger didn't accept the connection. Check DATABASE_URL in .env."
        ) from exc
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def uses_bm25() -> bool:
    return _use_bm25


def _savepoint(conn, name: str, sql: str) -> bool:
    conn.execute(f"SAVEPOINT {name}")
    try:
        conn.execute(sql)
    except psycopg.Error:
        conn.execute(f"ROLLBACK TO SAVEPOINT {name}")
        return False
    conn.execute(f"RELEASE SAVEPOINT {name}")
    return True


def ensure_schema(conn) -> None:
    global _use_bm25
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    conn.execute("CREATE SCHEMA IF NOT EXISTS lazyyyyy")
    _use_bm25 = _savepoint(conn, "bm25_ext", "CREATE EXTENSION IF NOT EXISTS pg_textsearch")
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS lazyyyyy.pile_items (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            created_at timestamptz NOT NULL DEFAULT now(),
            body text NOT NULL,
            embedding halfvec({EMBED_DIM}) NOT NULL,
            verdict text NOT NULL CHECK (verdict IN ('pardon', 'two_minutes', 'merge')),
            summary text NOT NULL,
            script text,
            matched_id bigint REFERENCES lazyyyyy.pile_items (id),
            origin text NOT NULL DEFAULT 'pile' CHECK (origin IN ('pile', 'memory'))
        )
        """
    )
    if _use_bm25:
        created = _savepoint(
            conn,
            "bm25_idx",
            """
            CREATE INDEX IF NOT EXISTS pile_items_bm25
            ON lazyyyyy.pile_items USING bm25 (body) WITH (text_config = 'english')
            """,
        )
        _use_bm25 = created
    if not _use_bm25:
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS pile_items_tsv
            ON lazyyyyy.pile_items USING GIN (to_tsvector('english', body))
            """
        )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS pile_items_hnsw
        ON lazyyyyy.pile_items USING hnsw (embedding halfvec_cosine_ops)
        """
    )
    conn.commit()


def keyword_search(conn, body: str, limit: int = 20) -> list[dict]:
    if uses_bm25():
        rows = conn.execute(
            """
            SELECT id, body, verdict, summary, created_at
            FROM lazyyyyy.pile_items
            ORDER BY body <@> %s
            LIMIT %s
            """,
            (body, limit),
        ).fetchall()
        return list(rows)
    rows = conn.execute(
        """
        SELECT id, body, verdict, summary, created_at
        FROM lazyyyyy.pile_items
        WHERE to_tsvector('english', body) @@ plainto_tsquery('english', %s)
        ORDER BY ts_rank(to_tsvector('english', body), plainto_tsquery('english', %s)) DESC
        LIMIT %s
        """,
        (body, body, limit),
    ).fetchall()
    return list(rows)


def semantic_search(conn, literal: str, limit: int = 20) -> list[dict]:
    rows = conn.execute(
        f"""
        SELECT id, body, verdict, summary, created_at
        FROM lazyyyyy.pile_items
        ORDER BY embedding <=> %s::halfvec({EMBED_DIM})
        LIMIT %s
        """,
        (literal, limit),
    ).fetchall()
    return list(rows)
