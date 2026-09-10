from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from app.api.schemas import SaveDocumentRequest
from app.core.config import Settings
from app.core.models import Principal
from app.services.runtime import Runtime
from bootstrap import seed


def principal(tenant="bluewhale", role="admin", department="platform", user="admin"):
    return Principal(user_id=user, name=user, tenant_id=tenant, department_id=department, role=role)


@pytest.fixture
def settings(tmp_path):
    return Settings(root=ROOT, state_dir=tmp_path / "state", principals_file=tmp_path / "principals.json")


@pytest.fixture
def runtime(settings):
    rt = Runtime(settings)
    yield rt
    rt.close()


@pytest.fixture
def populated(runtime):
    seed(runtime)
    return runtime


@pytest.fixture
def admin():
    return principal()


@pytest.fixture
def publish(runtime, admin):
    def create(content="退款金额超过 2000 元时必须人工审核。", *, id="policy", p=None, **kwargs):
        data = dict(title="退款人工审核规则", content=content, evidence_type="review_rule", effective_at="2026-01-01T00:00:00+00:00")
        data.update(kwargs)
        return runtime.store.publish(p or admin, SaveDocumentRequest(**data), runtime.embeddings, runtime.index, id)
    return create


@pytest.fixture
def client(populated, settings):
    from app.main import create_app
    identities = {
        "agentic": principal(),
        "admin": principal("bluewhale-kb"),
        "support": principal("bluewhale-kb", "employee", "customer-service", "support"),
        "finance": principal("bluewhale-kb", "employee", "finance", "finance"),
        "other": principal("starlight"),
    }
    rows = [dict(token_sha256=hashlib.sha256(("test-" + token).encode()).hexdigest(), principal=p.model_dump()) for token, p in identities.items()]
    settings.principals_file.write_text(json.dumps(rows), encoding="utf-8")
    with TestClient(create_app(settings, populated)) as connection:
        yield connection


def auth(name="agentic"):
    return {"Authorization": "Bearer test-" + name}
