"""Ollama calls for Gemma generation and EmbeddingGemma vectors."""

from __future__ import annotations

import os

import httpx

from app.judge import parse_json_object

EMBED_DIM = 768


class OllamaUnavailable(RuntimeError):
    """The local Ollama server did not answer."""


class OllamaBadJSON(RuntimeError):
    """Gemma answered, but the answer was not usable JSON."""


def _host() -> str:
    return os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")


def _embed_host() -> str:
    return os.environ.get("OLLAMA_EMBED_HOST", _host()).rstrip("/")


def _headers() -> dict[str, str]:
    key = os.environ.get("OLLAMA_API_KEY", "").strip()
    if not key:
        return {}
    return {"Authorization": f"Bearer {key}"}


def _timeout() -> float:
    raw = os.environ.get("OLLAMA_TIMEOUT", "120")
    try:
        return float(raw)
    except ValueError:
        return 120.0


def explain_ollama_error(detail: str, status: int | None, *, embed: bool) -> str:
    text = detail.lower()
    if status == 401 or "unauthorized" in text or "invalid api key" in text:
        return "Ollama rejected the key. Set OLLAMA_API_KEY from https://ollama.com/settings/keys."
    if "allocate" in text or "out of memory" in text:
        return (
            "Gemma 4 E4B needs about 6 GB free to load, and there isn't that much free right now. "
            "Close other apps, or set GEMMA_MODEL=gemma4 and OLLAMA_HOST=https://ollama.com."
        )
    if embed:
        return "EmbeddingGemma didn't answer. Point OLLAMA_EMBED_HOST at an Ollama server with embeddinggemma pulled."
    return "Gemma didn't answer. Check OLLAMA_HOST, GEMMA_MODEL, and OLLAMA_API_KEY."


def chat_json(system: str, user: str, num_predict: int) -> dict:
    model = os.environ.get("GEMMA_MODEL", "gemma4:e4b")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.2, "num_predict": num_predict, "num_ctx": 4096},
    }
    try:
        response = httpx.post(
            f"{_host()}/api/chat",
            json=payload,
            headers=_headers(),
            timeout=_timeout(),
        )
        response.raise_for_status()
        content = response.json().get("message", {}).get("content", "")
    except httpx.HTTPError as exc:
        detail = ""
        status = None
        failed = getattr(exc, "response", None)
        if failed is not None:
            detail = failed.text
            status = failed.status_code
        raise OllamaUnavailable(explain_ollama_error(detail, status, embed=False)) from exc
    try:
        return parse_json_object(content)
    except Exception as exc:
        raise OllamaBadJSON("Gemma didn't return JSON.") from exc


def embed(text: str) -> list[float]:
    host = _embed_host()
    if "ollama.com" in host:
        raise OllamaUnavailable(
            "EmbeddingGemma does not run on ollama.com. Set OLLAMA_EMBED_HOST to an Ollama server, or run docker compose."
        )
    model = os.environ.get("EMBED_MODEL", "embeddinggemma")
    payload = {"model": model, "input": text}
    try:
        response = httpx.post(
            f"{host}/api/embed",
            json=payload,
            headers=_headers(),
            timeout=60,
        )
        response.raise_for_status()
        vectors = response.json().get("embeddings") or []
        vector = vectors[0]
    except (httpx.HTTPError, IndexError, KeyError, TypeError) as exc:
        detail = ""
        status = None
        failed = getattr(exc, "response", None)
        if failed is not None:
            detail = failed.text
            status = failed.status_code
        raise OllamaUnavailable(explain_ollama_error(detail, status, embed=True)) from exc
    if len(vector) != EMBED_DIM:
        raise OllamaUnavailable(
            f"EmbeddingGemma returned {len(vector)} dimensions, and the pile expects {EMBED_DIM}."
        )
    return [float(value) for value in vector]


def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.7f}" for value in values) + "]"
