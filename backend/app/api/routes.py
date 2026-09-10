from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from app.api.schemas import ChatRequest, EvaluateRequest, IngestTextRequest
from app.core.models import BenchmarkCase
from app.services.evaluation import Evaluator
from app.services.parsing import extract_text

router = APIRouter(prefix="/api")


def _load_benchmark(root: Path) -> list[BenchmarkCase]:
    import json

    path = root / "data" / "benchmark.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        BenchmarkCase(
            query=row["query"],
            relevant_source_ids=tuple(row["relevant_source_ids"]),
            expected_keywords=tuple(row.get("expected_keywords", [])),
            role=row.get("role", "public"),
        )
        for row in payload
    ]


@router.post("/documents/ingest-text")
def ingest_text(request: Request, payload: IngestTextRequest) -> dict:
    document, duplicate = request.app.state.store.ingest(
        source_id=payload.source_id,
        title=payload.title,
        content=payload.content,
        allowed_roles=tuple(payload.allowed_roles),
        metadata=payload.metadata,
    )
    return {"document": asdict(document), "duplicate": duplicate}


@router.post("/documents/upload")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    source_id: str = Form(...),
    allowed_roles: str = Form("public"),
) -> dict:
    raw = await file.read()
    try:
        content = extract_text(file.filename or "upload.txt", raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if len(content.strip()) < 20:
        raise HTTPException(status_code=400, detail="No usable text extracted from file")
    roles = tuple(role.strip() for role in allowed_roles.split(",") if role.strip()) or ("public",)
    document, duplicate = request.app.state.store.ingest(
        source_id=source_id,
        title=file.filename or source_id,
        content=content,
        allowed_roles=roles,
        metadata={"source_type": "upload", "filename": file.filename},
    )
    return {"document": asdict(document), "duplicate": duplicate}


@router.get("/documents")
def list_documents(request: Request, include_inactive: bool = False) -> list[dict]:
    return [asdict(doc) for doc in request.app.state.store.list_documents(include_inactive=include_inactive)]


@router.post("/chat")
def chat(request: Request, payload: ChatRequest) -> dict:
    state = request.app.state.graph.invoke({"query": payload.query, "role": payload.role, "top_k": payload.top_k})
    return state["result"]


@router.get("/traces/{trace_id}")
def trace(request: Request, trace_id: str) -> dict:
    payload = request.app.state.store.get_trace(trace_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Trace not found")
    return payload


@router.post("/evaluate")
def evaluate(request: Request, payload: EvaluateRequest) -> dict:
    evaluator = Evaluator(request.app.state.pipeline)
    return evaluator.evaluate(_load_benchmark(request.app.state.root), k=payload.k)
