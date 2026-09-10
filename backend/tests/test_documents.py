from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone

import pytest
from app.api.schemas import SaveDocumentRequest
from app.core.chunking import chunk_document, markdown_sections
from app.core.errors import AppError, Conflict, Forbidden, NotFound
from app.services.store import SQLiteDocumentStore, valid_dates
from conftest import principal


def test_normalized_duplicate_skips_embedding(runtime, admin, publish, monkeypatch):
    first = publish(content="# Rules\r\n\r\n退款超过 2000 元需要审核。\r\n")
    def no_embedding(_):
        pytest.fail("Identical active content and metadata must not be re-embedded")
    monkeypatch.setattr(runtime.embeddings, "embed_many", no_embedding)
    second = publish(content="# Rules\n\n退款超过 2000 元需要审核。")
    assert first["document"]["version"] == 1
    assert second["status"] == "skipped"
    assert second["duplicate"] is True


def test_metadata_change_is_not_skipped(runtime, admin, publish):
    publish(visibility="company")
    second = publish(visibility="department", department_id="finance", expected_version=1)
    assert second["document"]["version"] == 2
    assert runtime.store.snapshot(principal(role="employee", department="customer-service")) == []
    assert len(runtime.store.versions(admin, "policy")) == 2


def test_version_replacement_and_historical_source(runtime, admin, publish):
    publish(content="退款超过 2000 元需要人工审核。")
    changed = publish(content="退款超过 5000 元需要人工审核。", expected_version=1)
    active = runtime.store.snapshot(admin)
    assert changed["document"]["version"] == 2
    assert {chunk.version for chunk in active} == {2}
    assert all("2000" not in chunk.text for chunk in active)
    assert "2000" in runtime.store.source(admin, "policy", 1).content
    employee = principal(role="employee", department="customer-service")
    with pytest.raises(NotFound):
        runtime.store.source(employee, "policy", 1)


def test_reverting_to_old_content_creates_new_revision(runtime, admin, publish):
    publish(content="Policy A")
    publish(content="Policy B", expected_version=1)
    result = publish(content="Policy A", expected_version=2)
    assert result["document"]["version"] == 3
    assert result["status"] == "updated"


def test_failed_vector_stage_keeps_old_revision_active(runtime, admin, publish, monkeypatch):
    publish(content="Refund threshold 2000")
    def fail(_):
        raise RuntimeError("index unavailable")
    monkeypatch.setattr(runtime.index, "stage", fail)
    with pytest.raises(RuntimeError):
        publish(content="Refund threshold 5000", expected_version=1)
    assert runtime.store.list_documents(admin)[0].version == 1
    assert len(runtime.store.versions(admin, "policy")) == 1
    assert "2000" in runtime.store.snapshot(admin)[0].text


def test_optimistic_lock_conflict_and_no_state_corruption(runtime, admin, publish):
    publish()
    with pytest.raises(Conflict):
        publish(content="New rule", expected_version=0)
    assert runtime.store.list_documents(admin)[0].version == 1


def test_concurrent_same_version_has_exactly_one_winner(runtime, admin, publish):
    publish()
    def update(number):
        try:
            publish(content=f"Rule {number}", expected_version=1)
            return "published"
        except Conflict:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(update, [1, 2]))
    assert sorted(outcomes) == ["conflict", "published"]
    assert runtime.store.list_documents(admin)[0].version == 2


def test_soft_delete_removes_all_retrieval_paths(runtime, admin, publish):
    publish()
    assert runtime.store.delete(admin, "policy", 1)["status"] == "deleted"
    assert runtime.store.snapshot(admin) == []
    assert runtime.store.list_documents(admin) == []
    assert len(runtime.store.versions(admin, "policy")) == 1
    assert runtime.store.delete(admin, "policy", 1)["status"] == "skipped"


def test_seed_does_not_reactivate_deleted_or_overwrite_updated(populated, admin):
    from bootstrap import seed
    populated.store.delete(admin, "refund-review", 1)
    assert seed(populated) == 0
    assert all(c.document_id != "refund-review" for c in populated.store.snapshot(admin))


def test_department_and_tenant_scope_are_checked_before_retrieval(populated):
    support = principal("bluewhale-kb", "employee", "customer-service", "support")
    finance = principal("bluewhale-kb", "employee", "finance", "finance")
    assert {c.document_id for c in populated.store.snapshot(support)} == {"company-refund", "service-review"}
    assert {c.document_id for c in populated.store.snapshot(finance)} == {"company-refund", "finance-refund"}
    admin = principal("bluewhale-kb")
    assert {c.tenant_id for c in populated.store.snapshot(admin)} == {"bluewhale-kb"}


def test_heading_paths_and_bounded_chunk_overlap(runtime, admin, publish):
    body = "0123456789" * 180
    publish(content="# Refunds\n\nOverview.\n\n## Materials\n\n" + body + "\n\n```python\nprint('receipt')\n```")
    doc = runtime.store.source(admin, "policy", 1)
    chunks = chunk_document(doc)
    assert all(len(c.text) <= 700 for c in chunks)
    material = [c.text for c in chunks if c.text.startswith("Refunds / Materials")]
    assert len(material) >= 3
    assert material[0][-80:] == material[1].split("\n\n", 1)[1][:80]
    assert any("print('receipt')" in c.text for c in chunks)
    assert [c.id for c in chunks] == [c.id for c in chunk_document(doc)]
    assert chunks[0].id != chunk_document(replace(doc, version=2))[0].id


def test_heading_only_document_is_not_published(runtime, admin, publish):
    with pytest.raises(AppError):
        publish(content="# Only a heading")
    assert not runtime.store.list_documents(admin)


@pytest.mark.parametrize("effective,expires", [
    ("2026-01-01T00:00:00", None),
    ("2099-01-01T00:00:00Z", None),
    ("2020-01-01T00:00:00Z", "2020-02-01T00:00:00Z"),
    ("invalid", None),
])
def test_invalid_or_inactive_dates_fail_closed(effective, expires):
    assert not valid_dates(effective, expires, datetime(2026, 9, 11, tzinfo=timezone.utc))


def test_index_configuration_change_is_explicit(runtime):
    with pytest.raises(Conflict):
        runtime.store.bind_index_configuration({"dimensions": 64})


def test_cross_tenant_source_and_history_not_found(populated):
    with pytest.raises(NotFound):
        populated.store.source(principal("starlight"), "refund-review", 1)
    with pytest.raises(NotFound):
        populated.store.versions(principal("starlight"), "refund-review")
