import pytest

from app.services.reranker_service import RerankerService


@pytest.fixture
def reranker():
    return RerankerService()


def test_rerank_prefers_lexical_overlap_over_raw_score(reranker):
    chunks = [
        ("network.md", "Check routes with oc get routes.", 0.95),
        ("pods.md", "Restart a pod with kubectl delete pod.", 0.5),
    ]

    results = reranker.rerank("restart pod kubectl", chunks, top_k=2)

    assert results[0][0] == "pods.md"


def test_rerank_returns_top_k_only(reranker):
    chunks = [(f"doc{i}.md", f"content about pod {i}", 0.5) for i in range(5)]

    results = reranker.rerank("pod", chunks, top_k=2)

    assert len(results) == 2


def test_rerank_empty_chunks_returns_empty(reranker):
    assert reranker.rerank("anything", [], top_k=3) == []


def test_rerank_no_query_terms_falls_back_to_original_order(reranker):
    chunks = [("a.md", "content", 0.5), ("b.md", "content", 0.9)]

    results = reranker.rerank("???", chunks, top_k=2)

    assert results == chunks
