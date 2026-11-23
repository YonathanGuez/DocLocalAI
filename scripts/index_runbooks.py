#!/usr/bin/env python3
"""
Runbook Indexer for DocLocalAI
Chunks and embeds markdown/text runbooks into PostgreSQL + pgvector
"""

import os
import sys
import psycopg
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
    """Split text into overlapping chunks"""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap
    return chunks


def index_runbook(conn, embed_client, file_path: Path):
    """Index a single runbook file"""
    print(f"📄 Processing: {file_path.name}")

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split into chunks
    chunks = chunk_text(content, CHUNK_SIZE)
    print(f"   Created {len(chunks)} chunks")

    # Generate embeddings and insert
    source_name = file_path.name

    with conn.cursor() as cur:
        # Clear existing chunks from this document
        cur.execute("DELETE FROM runbook_chunks WHERE source_doc = %s", (source_name,))

        for idx, chunk in enumerate(chunks):
            try:
                # Generate embedding
                emb_resp = embed_client.embeddings.create(
                    model=EMBED_MODEL,
                    input=chunk
                )
                embedding = emb_resp.data[0].embedding

                # Insert into database
                cur.execute(
                    """
                    INSERT INTO runbook_chunks (source_doc, chunk_index, content, embedding)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (source_name, idx, chunk, embedding)
                )
                print(f"   ✓ Chunk {idx + 1}/{len(chunks)}")

            except Exception as e:
                print(f"   ✗ Failed chunk {idx}: {e}")
                continue

        conn.commit()

    print(f"   ✅ Indexed {source_name}\n")


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
        embed_client = OpenAI(base_url=EMBED_URL, api_key="not-needed")
        conn = psycopg.connect(DB_DSN)
        register_vector(conn)

        print(f"✅ Connected\n")

        # Index each runbook
        for runbook_file in sorted(runbook_files):
            index_runbook(conn, embed_client, runbook_file)

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
