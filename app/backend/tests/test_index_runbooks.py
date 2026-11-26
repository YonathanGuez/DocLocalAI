import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from index_runbooks import (
    chunk_markdown,
    chunk_with_context,
    index_runbook,
    split_markdown_blocks,
)


def test_split_markdown_blocks_keeps_code_fence_intact():
    text = "# Title\n\nSome intro text.\n\n```bash\nkubectl get pods\nkubectl delete pod x\n```\n\nMore text."
    blocks = split_markdown_blocks(text)

    fence_blocks = [b for b in blocks if b.startswith("```")]
    assert len(fence_blocks) == 1
    assert "kubectl get pods" in fence_blocks[0]
    assert "kubectl delete pod x" in fence_blocks[0]


def test_split_markdown_blocks_separates_headers():
    text = "# Header One\nParagraph one.\n\n## Header Two\nParagraph two."
    blocks = split_markdown_blocks(text)

    assert "# Header One" in blocks
    assert "## Header Two" in blocks


def test_chunk_markdown_keeps_code_fence_intact_when_it_fits():
    fence = "```bash\n" + "\n".join(f"echo line{i}" for i in range(10)) + "\n```"
    text = f"# Runbook\n\nIntro paragraph.\n\n{fence}\n\nOutro paragraph."

    chunks = chunk_markdown(text, chunk_size=500, overlap=10)

    fence_chunks = [c for c in chunks if "echo line0" in c]
    assert len(fence_chunks) == 1
    assert "echo line9" in fence_chunks[0]


def test_chunk_markdown_falls_back_to_slicing_oversized_block():
    fence = "```bash\n" + "\n".join(f"echo line{i}" for i in range(40)) + "\n```"
    text = f"# Runbook\n\nIntro paragraph.\n\n{fence}\n\nOutro paragraph."

    # Fence alone exceeds chunk_size, so it must be sliced rather than
    # produced as one oversized chunk.
    chunks = chunk_markdown(text, chunk_size=80, overlap=10)

    assert all(len(c) <= 80 for c in chunks)
    assert any("echo line0" in c for c in chunks)
    assert any("echo line39" in c for c in chunks)


def test_chunk_markdown_respects_chunk_size_for_normal_text():
    text = "\n\n".join(f"Paragraph number {i} with some filler words." for i in range(20))
    chunks = chunk_markdown(text, chunk_size=100, overlap=10)

    assert len(chunks) > 1
    for c in chunks:
        assert len(c) <= 200  # generous bound; no runaway chunk


def test_chunk_with_context_prefixes_document_summary():
    text = "# Pod Restarts\n\nTo restart a pod, delete it and let the deployment recreate it."
    chunks = chunk_with_context(text, "pods.md", chunk_size=500)

    assert len(chunks) >= 1
    first = chunks[0]
    assert first["enriched"].startswith("Document: pods.md")
    assert "Summary:" in first["enriched"]
    assert first["raw"] in first["enriched"]
    assert first["metadata"]["source"] == "pods.md"


def test_chunk_with_context_produces_stable_content_hash():
    text = "# Topic\n\nIdentical content for hashing."
    c1 = chunk_with_context(text, "a.md", chunk_size=500)
    c2 = chunk_with_context(text, "b.md", chunk_size=500)

    # Same raw content -> same hash even if source document differs
    assert c1[0]["content_hash"] == c2[0]["content_hash"]
    # Enriched text differs because doc context differs
    assert c1[0]["enriched"] != c2[0]["enriched"]


class _FakeCursor:
    def __init__(self, store):
        self.store = store

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, query, params=None):
        if query.strip().startswith("DELETE"):
            source = params[0]
            self.store[:] = [r for r in self.store if r["source_doc"] != source]
        elif query.strip().startswith("INSERT"):
            source_doc, chunk_index, content, embedding, content_hash = params
            self.store.append({
                "source_doc": source_doc,
                "chunk_index": chunk_index,
                "content": content,
                "embedding": embedding,
                "content_hash": content_hash,
            })


class _FakeConn:
    def __init__(self):
        self.store = []
        self.committed = False

    def cursor(self):
        return _FakeCursor(self.store)

    def commit(self):
        self.committed = True


class _FakeEmbedClient:
    class _Embeddings:
        def create(self, model, input):
            class _Resp:
                data = [type("D", (), {"embedding": [0.1, 0.2, 0.3]})]
            return _Resp()

    def __init__(self):
        self.embeddings = self._Embeddings()


def test_index_runbook_skips_duplicate_chunks_across_files(tmp_path):
    file_a = tmp_path / "a.md"
    file_a.write_text("# Shared\n\nThis exact paragraph appears in both files.")
    file_b = tmp_path / "b.md"
    file_b.write_text("# Shared\n\nThis exact paragraph appears in both files.")

    conn = _FakeConn()
    embed_client = _FakeEmbedClient()
    seen_hashes: set[str] = set()

    inserted_a = index_runbook(conn, embed_client, file_a, seen_hashes)
    inserted_b = index_runbook(conn, embed_client, file_b, seen_hashes)

    assert inserted_a == 1
    assert inserted_b == 0  # duplicate content skipped
    assert len(conn.store) == 1
