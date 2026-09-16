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
def test_employee_cannot_maintain_or_audit_admin_data(client, verb, path, body):
    kwargs = {"headers": auth("support")}
    if body is not None:
        kwargs["json"] = body
    assert getattr(client, verb)(path, **kwargs).status_code == 403


def test_private_sources_hidden_across_department_and_tenant(client):
    path = "/api/documents/finance-refund/versions/1/source"
    assert client.get(path, headers=auth("support")).status_code == 404
    assert client.get(path, headers=auth("finance")).status_code == 200
    assert client.get(path, headers=auth("other")).status_code == 404
    visible = client.get("/api/documents", headers=auth("support")).json()
    assert {d["id"] for d in visible} == {"company-refund", "service-review"}


def test_trace_is_private_and_revalidates_revoked_sources(client):
    result = client.post("/api/chat", headers=auth("support"), json={"query": "退款人工审核阈值是多少？"}).json()
    assert result["outcome"] == "answered"
    path = "/api/traces/" + result["trace_id"]
    assert client.get(path, headers=auth("finance")).status_code == 404
    assert client.get(path, headers=auth("other")).status_code == 404
    assert client.get(path, headers=auth("admin")).status_code == 200
    source = client.get("/api/documents/company-refund/versions/1/source", headers=auth("admin")).json()
    replacement = {k: source[k] for k in ("title", "content", "evidence_type", "effective_at")}
    replacement.update(department_id="finance", visibility="department", expected_version=1)
    assert client.put("/api/documents/company-refund", headers=auth("admin"), json=replacement).status_code == 200
    old_trace = client.get(path, headers=auth("support")).json()
    assert not old_trace["citations"]
    assert all(not s["candidates"] for s in old_trace["searches"])
    assert "3000" not in old_trace["answer"]


def test_markdown_upload_and_source_binding(client):
    response = client.post("/api/documents/upload", headers=auth(),
        data={"title": "新政策", "evidence_type": "general"},
        files={"file": ("policy.md", "# 新政策\n\n实际上传的正文。".encode(), "text/markdown")})
    assert response.status_code == 200, response.text
    document = response.json()["document"]
    source = client.get(f'/api/documents/{document["id"]}/versions/1/source', headers=auth()).json()
    assert "实际上传的正文" in source["content"]


def test_unsupported_spreadsheet_upload_rejected(client):
    response = client.post("/api/documents/upload", headers=auth(), data={"title": "Sheet"},
        files={"file": ("sheet.xlsx", b"not a spreadsheet", "application/octet-stream")})
    assert response.status_code == 400


def test_bad_dates_and_optimistic_version_validation(client):
    response = client.post("/api/documents", headers=auth(), json={"title": "Rules", "content": "Valid text", "effective_at": "2026-01-01"})
    assert response.status_code == 422
    response = client.put("/api/documents/refund-review", headers=auth(), json={"title": "Rules", "content": "Valid text"})
    assert response.status_code == 400


def test_bundled_regression_is_a_measured_run(client):
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
