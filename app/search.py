"""Reciprocal rank fusion for keyword and vector hits."""

from __future__ import annotations


def rrf_fusion(
    keyword_rows: list[dict],
    semantic_rows: list[dict],
    k: int = 60,
    limit: int = 3,
    keyword_weight: float = 1.0,
    semantic_weight: float = 1.0,
) -> list[dict]:
    scores: dict[int, float] = {}
    rows: dict[int, dict] = {}
    for rank, row in enumerate(keyword_rows, start=1):
        row_id = int(row["id"])
        scores[row_id] = scores.get(row_id, 0.0) + keyword_weight / (k + rank)
        rows[row_id] = row
    for rank, row in enumerate(semantic_rows, start=1):
        row_id = int(row["id"])
        scores[row_id] = scores.get(row_id, 0.0) + semantic_weight / (k + rank)
        rows[row_id] = row
    ranked = sorted(scores, key=lambda row_id: scores[row_id], reverse=True)[:limit]
    return [{**rows[row_id], "score": scores[row_id]} for row_id in ranked]
