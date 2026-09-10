from __future__ import annotations
import json
from dataclasses import asdict
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, Query
from pydantic import ValidationError
from app.api.schemas import ChatRequest, EvaluateRequest, SaveDocumentRequest
from app.core.auth import current_principal, require_admin
from app.core.errors import AppError
from app.core.models import BenchmarkCase, Principal
from app.services.evaluation import Evaluator
from app.services.parsing import extract_text
from app.services.store import document_summary
router = APIRouter(prefix='/api')

@router.get('/session')
def session(request: Request, principal: Principal=Depends(current_principal)):
    return {'principal': principal.model_dump(), 'runtime': request.app.state.runtime.settings.public_runtime()}

@router.post('/chat')
def chat(request: Request, payload: ChatRequest, principal: Principal=Depends(current_principal)):
    return asdict(request.app.state.runtime.pipeline.run(payload.query, principal, payload.top_k))

@router.get('/traces/{trace_id}')
def trace(request: Request, trace_id: str, principal: Principal=Depends(current_principal)):
    return request.app.state.runtime.store.get_trace(principal, trace_id)

@router.get('/documents')
def documents(request: Request, principal: Principal=Depends(current_principal)):
    return [document_summary(doc) for doc in request.app.state.runtime.store.list_documents(principal)]

@router.post('/documents', status_code=201)
def create_document(request: Request, payload: SaveDocumentRequest, principal: Principal=Depends(require_admin)):
    rt = request.app.state.runtime
    return rt.store.publish(principal, payload, rt.embeddings, rt.index)

@router.put('/documents/{document_id}')
def update_document(request: Request, document_id: str, payload: SaveDocumentRequest, principal: Principal=Depends(require_admin)):
    if payload.expected_version is None:
        raise AppError('expected_version is required when publishing a replacement')
    rt = request.app.state.runtime
    return rt.store.publish(principal, payload, rt.embeddings, rt.index, document_id, must_exist=True)

@router.post('/documents/upload')
def upload_document(request: Request, file: UploadFile=File(...), title: str=Form(...), department_id: str=Form('customer-service'), visibility: str=Form('company'), evidence_type: str=Form('general'), additional_evidence_types: str=Form(''), effective_at: str=Form(''), expires_at: str=Form(''), document_id: str=Form(''), expected_version: int | None=Form(None), principal: Principal=Depends(require_admin)):
    rt = request.app.state.runtime
    raw = file.file.read(rt.settings.max_upload_bytes + 1)
    if len(raw) > rt.settings.max_upload_bytes:
        raise AppError('File exceeds upload size limit')
    text = extract_text(file.filename or '', raw)
    try:
        payload = SaveDocumentRequest(title=title, content=text, department_id=department_id, visibility=visibility, evidence_type=evidence_type, additional_evidence_types=[x.strip() for x in additional_evidence_types.split(',') if x.strip()], effective_at=effective_at or datetime.now(timezone.utc), expires_at=expires_at or None, expected_version=expected_version)
    except ValidationError as exc:
        raise AppError('Invalid document metadata or dates') from exc
    if document_id and expected_version is None:
        raise AppError('expected_version is required for file replacement')
    return rt.store.publish(principal, payload, rt.embeddings, rt.index, document_id or None, must_exist=bool(document_id))

@router.get('/documents/{document_id}/versions')
def versions(request: Request, document_id: str, principal: Principal=Depends(require_admin)):
    return [document_summary(doc) for doc in request.app.state.runtime.store.versions(principal, document_id)]

@router.get('/documents/{document_id}/versions/{version}/source')
def source(request: Request, document_id: str, version: int, principal: Principal=Depends(current_principal)):
    return asdict(request.app.state.runtime.store.source(principal, document_id, version))

@router.delete('/documents/{document_id}')
def delete_document(request: Request, document_id: str, expected_version: int=Query(ge=1), principal: Principal=Depends(require_admin)):
    return request.app.state.runtime.store.delete(principal, document_id, expected_version)

@router.post('/evaluate')
def evaluate(request: Request, payload: EvaluateRequest, principal: Principal=Depends(require_admin)):
    dataset = json.loads((request.app.state.runtime.settings.root / 'data/benchmark.json').read_text(encoding='utf-8'))
    cases = [BenchmarkCase(row['query'], tuple(row['relevant_source_ids']), tuple(row.get('expected_keywords', []))) for row in dataset if row['tenant_id'] == principal.tenant_id]
    if not cases:
        raise AppError('No bundled regression dataset exists for this tenant')
    return Evaluator(request.app.state.runtime.pipeline).evaluate(cases, principal, payload.k)
