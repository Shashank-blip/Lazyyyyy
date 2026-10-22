"""Local web app for the pardon pile."""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.pile import history, process_pile  # noqa: E402
from app.samples import SAMPLE_PILE  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"

app = FastAPI(title="Lazyyyyy")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class PileRequest(BaseModel):
    text: str = Field(default="")
    seed_memory: bool = False


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health():
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    return {
        "ok": True,
        "database": bool(os.environ.get("DATABASE_URL", "").strip()),
        "gemma_model": os.environ.get("GEMMA_MODEL", "gemma4:e4b"),
        "embed_model": os.environ.get("EMBED_MODEL", "embeddinggemma"),
        "gemma": "ollama-cloud" if "ollama.com" in host else "self-hosted",
        "embed_host_set": bool(os.environ.get("OLLAMA_EMBED_HOST", "").strip()),
    }


@app.get("/api/sample")
def sample():
    return {"text": SAMPLE_PILE.strip()}


@app.get("/api/history")
def get_history():
    try:
        return {"items": history()}
    except RuntimeError as exc:
        return {"items": [], "error": str(exc)}


@app.post("/api/pile")
def stamp_pile(body: PileRequest):
    def generate():
        for event in process_pile(body.text, body.seed_memory):
            yield json.dumps(event) + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")
