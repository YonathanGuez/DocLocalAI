#!/usr/bin/env python3
"""
Runbook Indexer for DocLocalAI
Chunks and embeds markdown/text runbooks into PostgreSQL + pgvector
"""

import hashlib
import os
import re
import sys
import psycopg
import httpx
from pathlib import Path
from openai import OpenAI
from pgvector.psycopg import register_vector

# Configuration
DB_DSN = os.getenv("DATABASE_URL", "postgresql://doclocalai:localdevpassword@localhost:5432/doclocalai")
EMBED_URL = os.getenv("EMBEDDING_ENDPOINT_URL", "http://localhost:11434/v1")
EMBED_MODEL = os.getenv("EMBEDDING_MODEL_NAME", "nomic-embed-text")
RUNBOOK_DIR = os.getenv("RUNBOOK_DIR", "../runbooks")
RUNBOOK_UPLOAD_DIR = os.getenv("RUNBOOK_UPLOAD_DIR", "/runbooks-uploads")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))  # characters per chunk


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks (legacy, character-based)"""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap
    return chunks


def split_markdown_blocks(text: str) -> list[str]:
    """Split markdown text into structural blocks without breaking them apart.

    Keeps fenced code blocks, headers and list items intact as single units
    so chunking never slices a table row, code fence or bullet in half.
    """
    lines = text.split("\n")
    blocks: list[str] = []
    buffer: list[str] = []
    in_fence = False

    def flush():
        if buffer:
            block = "\n".join(buffer).strip("\n")
            if block.strip():
                blocks.append(block)
            buffer.clear()

    for line in lines:
        fence_match = re.match(r"^\s*(```|~~~)", line)
        if fence_match:
            if in_fence:
                buffer.append(line)
                flush()
                in_fence = False
            else:
                flush()
                buffer.append(line)
                in_fence = True
            continue

        if in_fence:
            buffer.append(line)
            continue

        is_header = bool(re.match(r"^#{1,6}\s", line))
        is_blank = line.strip() == ""

        if is_header:
            flush()
            buffer.append(line)
            flush()
        elif is_blank:
            flush()
        else:
            buffer.append(line)

    flush()
    return blocks


def chunk_markdown(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Chunk text on markdown-aware boundaries (headers/paragraphs/code fences).

    Falls back to character slicing only for a single block that alone
    exceeds chunk_size (e.g. a very long code fence).
    """
    blocks = split_markdown_blocks(text)
    if not blocks:
        return []

    chunks: list[str] = []
    current = ""

    for block in blocks:
        if len(block) > chunk_size:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(chunk_text(block, chunk_size, overlap))
            continue

        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) > chunk_size and current:
            chunks.append(current.strip())
            current = block
        else:
            current = candidate

    if current:
        chunks.append(current.strip())

    return [c for c in chunks if c]


def chunk_with_context(text: str, source_name: str, chunk_size: int = 500) -> list[dict]:
    """Chunk markdown respecting structure and prepend document context
    before embedding (Anthropic's Contextual Retrieval pattern).

    Returns a list of dicts with:
      - raw: the original chunk text (stored in DB / shown to users)
      - enriched: raw text prefixed with document context (used for embedding)
      - metadata: dict with source + chunk type info
    """
    raw_chunks = chunk_markdown(text, chunk_size)
    if not raw_chunks:
        return []

    summary = " ".join(text.strip().split())[:200]
    doc_context = f"Document: {source_name}\nSummary: {summary}..."

    results = []
    for idx, raw in enumerate(raw_chunks):
        enriched = f"{doc_context}\n\n{raw}"
        content_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        results.append({
            "raw": raw,
            "enriched": enriched,
            "content_hash": content_hash,
            "metadata": {"source": source_name, "chunk_index": idx},
        })
    return results


def index_runbook(conn, embed_client, file_path: Path, seen_hashes: set[str] | None = None) -> int:
    """Index a single runbook file.

    Returns the number of chunks actually inserted (duplicates skipped).
    """
    print(f"📄 Processing: {file_path.name}")

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split into context-enriched, markdown-aware chunks
    chunks = chunk_with_context(content, file_path.name, CHUNK_SIZE)
    print(f"   Created {len(chunks)} chunks")

    source_name = file_path.name
    seen_hashes = seen_hashes if seen_hashes is not None else set()
    inserted = 0

    with conn.cursor() as cur:
        # Clear existing chunks from this document
        cur.execute("DELETE FROM runbook_chunks WHERE source_doc = %s", (source_name,))

        for idx, chunk in enumerate(chunks):
            content_hash = chunk["content_hash"]
            if content_hash in seen_hashes:
                print(f"   ⤼ Skipped duplicate chunk {idx}")
                continue

            try:
                # Generate embedding from the context-enriched text
                emb_resp = embed_client.embeddings.create(
                    model=EMBED_MODEL,
                    input=chunk["enriched"]
                )
                embedding = emb_resp.data[0].embedding

                # Insert raw content (not enriched) so users see clean text
                cur.execute(
                    """
                    INSERT INTO runbook_chunks (source_doc, chunk_index, content, embedding, content_hash)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (source_name, idx, chunk["raw"], embedding, content_hash)
                )
                seen_hashes.add(content_hash)
                inserted += 1
                print(f"   ✓ Chunk {idx + 1}/{len(chunks)}")

            except Exception as e:
                print(f"   ✗ Failed chunk {idx}: {e}")
                continue

        conn.commit()

    print(f"   ✅ Indexed {source_name} ({inserted} chunks)\n")
    return inserted


def main():
    """Index all runbooks from both sample and upload directories"""
    runbook_path = Path(__file__).parent / RUNBOOK_DIR
    upload_path = Path(RUNBOOK_UPLOAD_DIR)

    # Collect files from both directories
    runbook_files = []

    # Sample runbooks
    if runbook_path.exists():
        sample_files = list(runbook_path.glob("*.md")) + list(runbook_path.glob("*.txt"))
        runbook_files.extend(sample_files)
        print(f"📘 Found {len(sample_files)} sample runbooks in {runbook_path}")
    else:
        print(f"⚠️  Sample runbook directory not found: {runbook_path}")

    # Uploaded runbooks
    if upload_path.exists():
        upload_files = list(upload_path.glob("*.md")) + list(upload_path.glob("*.txt"))
        runbook_files.extend(upload_files)
        print(f"📗 Found {len(upload_files)} uploaded runbooks in {upload_path}")
    else:
        print(f"⚠️  Upload directory not found: {upload_path}")
        upload_path.mkdir(parents=True, exist_ok=True)
        print(f"   Created: {upload_path}")

    if not runbook_files:
        print(f"⚠️  No runbook files found")
        print("Add .md or .txt files and run again.")
        return

    print(f"🔍 Total: {len(runbook_files)} runbook files to index")
    print(f"📊 Connecting to database...")

    # Connect to database and embedding service
    try:
        http_client = httpx.Client(verify=False)
        embed_client = OpenAI(
            base_url=EMBED_URL,
            api_key="not-needed",
            http_client=http_client
        )
        conn = psycopg.connect(DB_DSN)
        register_vector(conn)

        print(f"✅ Connected\n")

        # Index each runbook, deduplicating identical chunk content across files
        seen_hashes: set[str] = set()
        for runbook_file in sorted(runbook_files):
            index_runbook(conn, embed_client, runbook_file, seen_hashes)

        # Clean up: Remove chunks from files that no longer exist
        print(f"\n🧹 Cleaning up orphaned chunks...")
        indexed_files = {f.name for f in runbook_files}

        with conn.cursor() as cur:
            # Get all source docs in database
            cur.execute("SELECT DISTINCT source_doc FROM runbook_chunks")
            db_sources = [row[0] for row in cur.fetchall()]

            # Find orphaned sources (in DB but not in filesystem)
            orphaned = [src for src in db_sources if src not in indexed_files]

            if orphaned:
                print(f"   Found {len(orphaned)} orphaned runbook(s)")
                for src in orphaned:
                    cur.execute("DELETE FROM runbook_chunks WHERE source_doc = %s", (src,))
                    print(f"   ✗ Removed: {src}")
                conn.commit()
            else:
                print(f"   ✓ No orphaned chunks found")

        # Show summary
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) as total_chunks,
                    COUNT(DISTINCT source_doc) as unique_docs
                FROM runbook_chunks
            """)
            total, docs = cur.fetchone()
            print(f"\n📊 Indexing complete!")
            print(f"   Total chunks: {total}")
            print(f"   Unique documents: {docs}")

        conn.close()

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
