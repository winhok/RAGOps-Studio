from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.services.demo_seed import seed_demo_knowledge
from app.services.graph import build_rag_graph
from app.services.runtime import build_pipeline
from app.services.store import SQLiteDocumentStore


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        import json

        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "trace_id"):
            payload["trace_id"] = record.trace_id
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(os.getenv("LOG_LEVEL", "INFO"))


def create_app(root: Path | None = None) -> FastAPI:
    configure_logging()
    root = root or Path(__file__).resolve().parents[2]
    db_path = Path(os.getenv("RAGOPS_DB_PATH", root / "data" / "ragops.db"))

    app = FastAPI(title="RAGOps Studio API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.root = root
    app.state.store = SQLiteDocumentStore(db_path)
    if os.getenv("RAGOPS_AUTO_SEED", "1") == "1" and not app.state.store.list_documents():
        seed_demo_knowledge(app.state.store, root)
    app.state.pipeline = build_pipeline(app.state.store)
    app.state.graph = build_rag_graph(app.state.pipeline)
    app.include_router(router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "service": "ragops-studio"}

    return app


app = create_app()
