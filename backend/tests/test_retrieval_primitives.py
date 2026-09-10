import pytest
from app.core.bm25 import BM25Index
from app.core.rrf import reciprocal_rank_fusion
from app.core.metrics import recall_at_k, reciprocal_rank, ndcg_at_k, keyword_coverage
from app.services.parsing import extract_text
from app.core.errors import AppError
from app.services.vector_index import permission_filter
from conftest import principal


def test_bm25_ranks_matching_source_before_unrelated_source():
    ranked = BM25Index(["refund manual approval threshold", "annual promotion discount"]).rank("refund approval")
    assert ranked[0][0] == 0 and ranked[0][1] > ranked[1][1]


def test_rrf_uses_both_rankings():
    scores = reciprocal_rank_fusion([["a", "b"], ["b", "c"]])
    assert scores["b"] > scores["a"] > scores["c"]


def test_document_level_metrics():
    assert recall_at_k(["wrong", "a"], {"a", "b"}, 2) == 0.5
    assert reciprocal_rank(["wrong", "a"], {"a"}) == 0.5
    assert 0 < ndcg_at_k(["wrong", "a"], {"a"}, 2) < 1
    assert keyword_coverage("Refund requires review", ("refund", "missing")) == 0.5


def test_filter_values_are_quoted_not_interpolated_as_expressions():
    p = principal('x" or tenant_id != "')
    expr = permission_filter(p, ['a"b'])
    assert '\"' in expr
    assert "chunk_id in" in expr


def test_text_parser_supports_utf8_and_rejects_bad_content():
    assert extract_text("POLICY.MD", "退款规则".encode()) == "退款规则"
    with pytest.raises(AppError):
        extract_text("rules.md", b"\xff")
    with pytest.raises(AppError):
        extract_text("rules.exe", b"not a document")


def test_unsupported_legacy_doc_is_not_silently_treated_as_docx():
    with pytest.raises(AppError):
        extract_text("legacy.doc", b"not a document")
