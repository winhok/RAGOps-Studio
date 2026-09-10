from __future__ import annotations
import json
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from app.api.routes import router
from app.core.auth import CredentialRegistry
from app.core.config import Settings
from app.core.errors import AppError
from app.services.runtime import Runtime

class JsonFormatter(logging.Formatter):

    def format(self, record):
        payload = {'level': record.levelname, 'logger': record.name, 'message': record.getMessage()}
        for key in ('trace_id', 'outcome', 'latency_ms', 'error_code'):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, ensure_ascii=False)

def create_app(settings: Settings | None=None, runtime=None):
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app):
        app.state.runtime = runtime or Runtime(settings)
        app.state.credentials = CredentialRegistry(settings.principals_file)
        yield
        if runtime is None:
            app.state.runtime.close()
    app = FastAPI(title='RAGOps Studio', version='0.2.0', lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False, allow_methods=['GET', 'POST', 'PUT', 'DELETE'], allow_headers=['Authorization', 'Content-Type'])

    @app.middleware('http')
    async def headers(request: Request, call_next):
        # Reject oversized requests before multipart parsing. Proxies must also impose a body limit.
        length = request.headers.get('content-length')
        if length and (not length.isdigit() or int(length) > settings.max_upload_bytes + 100000):
            return JSONResponse({'error': {'code': 'payload_too_large', 'message': 'Request body exceeds size limit'}}, status_code=413)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Frame-Options'] = 'DENY'
        if request.url.path.startswith('/api'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.exception_handler(AppError)
    async def application_error(request, exc):
        return JSONResponse({'error': {'code': exc.code, 'message': str(exc), 'trace_id': exc.trace_id}}, status_code=exc.status_code)

    @app.get('/health')
    def health():
        return {'status': 'ok', 'service': 'ragops-studio', 'version': '0.2.0'}
    app.include_router(router)
    public = settings.root / 'frontend/dist'
    if public.exists():
        app.mount('/', StaticFiles(directory=public, html=True), name='web')
    return app
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logging.getLogger('app').handlers = [handler]
logging.getLogger('app').setLevel(logging.INFO)
app = create_app()
