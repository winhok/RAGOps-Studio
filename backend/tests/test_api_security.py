import json
import re
import pytest
from conftest import auth


def test_health_and_missing_credentials(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/api/documents").status_code == 401
    assert client.get("/api/session", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_principal_resolved_by_server_not_body(client):
    session = client.get("/api/session", headers=auth("support")).json()
    assert session["principal"]["role"] == "employee"
    forged = client.post("/api/chat", headers=auth("support"), json={"query": "refund", "role": "admin", "tenant_id": "starlight"})
    assert forged.status_code == 422


def test_config_does_not_expose_secrets(client):
    data = client.get("/api/session", headers=auth()).json()
    assert "api_key" not in json.dumps(data)
    assert data["runtime"]["model_provider"] == "local"


@pytest.mark.parametrize("verb,path,body", [
    ("post", "/api/documents", {"title": "Title", "content": "secret"}),
    ("put", "/api/documents/company-refund", {"title": "Title", "content": "secret", "expected_version": 1}),
    ("delete", "/api/documents/company-refund?expected_version=1", None),
    ("post", "/api/evaluate", {"k": 5}),
    ("get", "/api/documents/company-refund/versions", None),
])
def test_missing_credentials_on_protected_routes(client, verb, path, body):
    response = getattr(client, verb)(path, json=body) if body is not None else getattr(client, verb)(path)
    assert response.status_code == 401


def test_employee_cannot_write_documents(client):
    response = client.post("/api/documents", headers=auth("support"), json={"title": "nope", "content": "nope"})
    assert response.status_code == 403


def test_department_and_tenant_scope(client):
    support = client.get("/api/documents", headers=auth("support"))
    assert support.status_code == 200
    titles = {row["title"] for row in support.json()}
    assert "客服退款操作手册" in titles
    assert "财务退款对账要求" not in titles
    assert "星光商城促销规则" not in titles

    finance = client.get("/api/documents", headers=auth("finance"))
    assert finance.status_code == 200
    titles = {row["title"] for row in finance.json()}
    assert "财务退款对账要求" in titles
    assert "客服退款审核流程" not in titles


def test_hidden_source_returns_not_found(client):
    response = client.get("/api/documents/finance-refund/versions/1/source", headers=auth("support"))
    assert response.status_code == 404


def test_trace_scope_follows_owner(client):
    chat = client.post("/api/chat", headers=auth("support"), json={"query": "退款金额超过多少元需要人工审核？"})
    assert chat.status_code == 200
    trace_id = chat.json()["trace_id"]
    assert client.get(f"/api/traces/{trace_id}", headers=auth("support")).status_code == 200
    assert client.get(f"/api/traces/{trace_id}", headers=auth("finance")).status_code == 404


def test_stale_document_update_returns_conflict(client):
    current = client.get("/api/documents/company-refund/versions/1/source", headers=auth()).json()
    payload = {
        "title": current["title"], "content": current["content"], "department_id": current["department_id"],
        "visibility": current["visibility"], "evidence_type": current["evidence_type"],
        "additional_evidence_types": current["additional_evidence_types"], "effective_at": current["effective_at"],
        "expires_at": current["expires_at"], "expected_version": 0,
    }
    response = client.put("/api/documents/company-refund", headers=auth(), json=payload)
    assert response.status_code == 409


def test_evaluation_requires_admin(client):
    assert client.post("/api/evaluate", headers=auth("support"), json={"k": 5}).status_code == 403
    result = client.post("/api/evaluate", headers=auth(), json={"k": 5})
    assert result.status_code == 200, result.text
    data = result.json()
    assert data["summary"]["cases"] == 4
    assert data["runtime"]["embedding_provider"] == "hash"
    assert "synthetic" in data["metric_scope"]
    assert all(row["trace_id"].startswith("tr_") for row in data["cases"])


def test_upload_body_limit(client):
    response = client.post("/api/documents/upload", headers={**auth(), "Content-Length": "99999999"}, content=b"x")
    assert response.status_code == 413


def test_response_security_headers(client):
    response = client.get("/api/documents", headers=auth())
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_compiled_client_is_served_by_the_same_app(client):
    response = client.get("/")
    if response.status_code == 404:
        pytest.skip("frontend production build is not present")
    assert response.status_code == 200
    assert "RAGOps Studio" in response.text
    assets = re.findall(r'(?:src|href)="(/assets/[^"]+\.(?:js|css))"', response.text)
    assert any(asset.endswith(".js") for asset in assets)
    assert any(asset.endswith(".css") for asset in assets)
    for asset in assets:
        assert client.get(asset).status_code == 200
    assert client.get("/.secrets/access-credentials.txt").status_code == 404
