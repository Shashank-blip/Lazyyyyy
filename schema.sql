-- Lazyyyyy pile. Isolated in its own schema so it can share a Tiger service
-- with other projects. Apply with: python -m app.schema
-- The app also applies this on startup.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_textsearch;

CREATE SCHEMA IF NOT EXISTS lazyyyyy;

CREATE TABLE IF NOT EXISTS lazyyyyy.pile_items (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    created_at timestamptz NOT NULL DEFAULT now(),
    body text NOT NULL,
    embedding halfvec(768) NOT NULL,
    verdict text NOT NULL CHECK (verdict IN ('pardon', 'two_minutes', 'merge')),
    summary text NOT NULL,
    script text,
    matched_id bigint REFERENCES lazyyyyy.pile_items (id),
    origin text NOT NULL DEFAULT 'pile' CHECK (origin IN ('pile', 'memory'))
);

CREATE INDEX IF NOT EXISTS pile_items_bm25
    ON lazyyyyy.pile_items USING bm25 (body) WITH (text_config = 'english');

CREATE INDEX IF NOT EXISTS pile_items_hnsw
    ON lazyyyyy.pile_items USING hnsw (embedding halfvec_cosine_ops);
