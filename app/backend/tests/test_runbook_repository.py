from app.repositories.runbook_repository import RunbookRepository, reciprocal_rank_fusion


def test_rrf_favors_ids_ranked_well_in_both_lists():
    bm25_ids = ["a", "b", "c"]
    vector_ids = ["b", "a", "c"]

    fused = reciprocal_rank_fusion(bm25_ids, vector_ids)
    fused_ids = [chunk_id for chunk_id, _ in fused]

    # "a" and "b" each appear near the top of both lists, "c" is always last
    assert fused_ids[:2] == ["a", "b"] or fused_ids[:2] == ["b", "a"]
    assert fused_ids[-1] == "c"


def test_rrf_includes_ids_present_in_only_one_list():
    fused = reciprocal_rank_fusion(["x", "y"], ["z"])
    fused_ids = {chunk_id for chunk_id, _ in fused}

    assert fused_ids == {"x", "y", "z"}


def test_rrf_empty_lists_returns_empty():
    assert reciprocal_rank_fusion([], []) == []


class _FakeCursor:
    def __init__(self, bm25_rows, vector_rows):
        self.bm25_rows = bm25_rows
        self.vector_rows = vector_rows
        self._next = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, query, params=None):
        self._next = "bm25" if "plainto_tsquery" in query else "vector"

    def fetchall(self):
        return self.bm25_rows if self._next == "bm25" else self.vector_rows


class _FakeConn:
    def __init__(self, bm25_rows, vector_rows):
        self._cursor = _FakeCursor(bm25_rows, vector_rows)

    def cursor(self):
        return self._cursor


def test_hybrid_search_fuses_bm25_and_vector_results():
    bm25_rows = [("id-1", "pods.md", "kubectl delete pod exact match")]
    vector_rows = [
        ("id-2", "network.md", "semantically similar content"),
        ("id-1", "pods.md", "kubectl delete pod exact match"),
    ]
    conn = _FakeConn(bm25_rows, vector_rows)

    results = RunbookRepository.hybrid_search(conn, "delete pod", [0.1, 0.2], top_k=10)

    sources = [r[0] for r in results]
    assert "pods.md" in sources
    assert "network.md" in sources
    # id-1 appears in both lists so it should rank first
    assert results[0][0] == "pods.md"
