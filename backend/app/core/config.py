from __future__ import annotations
import os
from pathlib import Path
from typing import Literal
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, model_validator

class Settings(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True)
    root: Path
    state_dir: Path
    principals_file: Path
    graph_engine: Literal['python', 'langgraph'] = 'python'
    model_provider: Literal['local', 'zhipu', 'deepseek', 'openai'] = 'local'
    embedding_provider: Literal['hash', 'zhipu', 'openai'] = 'hash'
    rerank_provider: Literal['lexical', 'zhipu'] = 'lexical'
    vector_backend: Literal['local', 'milvus', 'qdrant'] = 'local'
    dimensions: int = Field(default=512, ge=64, le=8192)
    max_searches: int = Field(default=3, ge=1, le=8)
    max_upload_bytes: int = Field(default=2000000, ge=1024, le=10000000)
    max_active_chunks: int = Field(default=5000, ge=1, le=10000)
    timeout_seconds: float = Field(default=45, gt=0, le=120)
    http_attempts: int = Field(default=3, ge=1, le=4)
    zhipu_api_key: str = Field(default='', repr=False)
    deepseek_api_key: str = Field(default='', repr=False)
    openai_api_key: str = Field(default='', repr=False)
    zhipu_base_url: str = 'https://open.bigmodel.cn/api/paas/v4'
    deepseek_base_url: str = 'https://api.deepseek.com'
    openai_base_url: str = 'https://api.openai.com/v1'
    chat_model: str = ''
    embedding_model: str = ''
    rerank_model: str = 'rerank'
    milvus_uri: str = 'http://127.0.0.1:19530'
    milvus_token: str = Field(default='', repr=False)
    collection: str = 'ragops_chunks_v2'
    qdrant_url: str = 'http://127.0.0.1:6333'
    qdrant_api_key: str = Field(default='', repr=False)
    cors_origins: list[str] = Field(default_factory=lambda: ['http://localhost:5173', 'http://127.0.0.1:5173'])

    @model_validator(mode='after')
    def check_providers(self):
        needs_zhipu = 'zhipu' in (self.model_provider, self.embedding_provider, self.rerank_provider)
        if needs_zhipu and (not self.zhipu_api_key):
            raise ValueError('ZHIPU_API_KEY is required by the selected provider')
        if self.model_provider == 'deepseek' and (not self.deepseek_api_key):
            raise ValueError('DEEPSEEK_API_KEY is required')
        if 'openai' in (self.model_provider, self.embedding_provider) and (not self.openai_api_key):
            raise ValueError('OPENAI_API_KEY is required')
        if self.model_provider != 'local' and (not self.chat_model):
            raise ValueError('CHAT_MODEL must be set explicitly for the configured account')
        if self.embedding_provider != 'hash' and (not self.embedding_model):
            raise ValueError('EMBEDDING_MODEL must be set explicitly')
        if self.embedding_provider == 'zhipu' and self.dimensions not in {256, 512, 1024, 2048}:
            raise ValueError('Zhipu embedding dimensions must be 256, 512, 1024 or 2048')
        return self

    @classmethod
    def from_env(cls, root: Path | None=None):
        root = root or Path(__file__).resolve().parents[3]
        load_dotenv(root / '.env', override=False)
        state_dir = Path(os.getenv('RAGOPS_STATE_DIR', str(root / '.state')))
        kwargs = dict(root=root, state_dir=state_dir, principals_file=Path(os.getenv('RAGOPS_PRINCIPALS_FILE', str(root / '.secrets/principals.json'))))
        mapping = {'graph_engine': 'RAGOPS_GRAPH_ENGINE', 'model_provider': 'RAGOPS_MODEL_PROVIDER', 'embedding_provider': 'RAGOPS_EMBEDDING_PROVIDER', 'rerank_provider': 'RAGOPS_RERANK_PROVIDER', 'vector_backend': 'RAGOPS_VECTOR_BACKEND', 'dimensions': 'EMBEDDING_DIMENSIONS', 'max_searches': 'RAGOPS_MAX_SEARCHES', 'max_active_chunks': 'RAGOPS_MAX_ACTIVE_CHUNKS', 'max_upload_bytes': 'RAGOPS_MAX_UPLOAD_BYTES', 'http_attempts': 'PROVIDER_HTTP_ATTEMPTS', 'timeout_seconds': 'PROVIDER_TIMEOUT_SECONDS', 'zhipu_api_key': 'ZHIPU_API_KEY', 'deepseek_api_key': 'DEEPSEEK_API_KEY', 'openai_api_key': 'OPENAI_API_KEY', 'chat_model': 'CHAT_MODEL', 'embedding_model': 'EMBEDDING_MODEL', 'rerank_model': 'RERANK_MODEL', 'milvus_uri': 'MILVUS_URI', 'milvus_token': 'MILVUS_TOKEN', 'collection': 'VECTOR_COLLECTION', 'qdrant_url': 'QDRANT_URL', 'qdrant_api_key': 'QDRANT_API_KEY', 'openai_base_url': 'OPENAI_BASE_URL'}
        for key, env in mapping.items():
            if (value := os.getenv(env)):
                kwargs[key] = value
        if (value := os.getenv('CORS_ORIGINS')):
            kwargs['cors_origins'] = value.split(',')
        return cls(**kwargs)

    def public_runtime(self) -> dict:
        return {'graph_engine': self.graph_engine, 'model_provider': self.model_provider, 'embedding_provider': self.embedding_provider, 'rerank_provider': self.rerank_provider, 'vector_backend': self.vector_backend, 'dimensions': self.dimensions, 'max_searches': self.max_searches, 'chat_model': self.chat_model or 'local-extractive', 'embedding_model': self.embedding_model or 'signed-hash-v1'}
