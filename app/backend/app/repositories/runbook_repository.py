from psycopg import Connection
from app.exceptions import DatabaseException


def reciprocal_rank_fusion(
    *ranked_id_lists: list[str],
    k: int = 60,
) -> list[tuple[str, float]]:
    """Fuse multiple ranked ID lists (best first) into one score per ID.

    Standard Reciprocal Rank Fusion: score(id) = sum(1 / (k + rank)) across
    every list the id appears in. Returns (id, fused_score) sorted best first.
    """
    fused_scores: dict[str, float] = {}

    for ranked_ids in ranked_id_lists:
        for rank, chunk_id in enumerate(ranked_ids, start=1):
            fused_scores[chunk_id] = fused_scores.get(chunk_id, 0.0) + 1.0 / (k + rank)

    return sorted(fused_scores.items(), key=lambda item: item[1], reverse=True)


class RunbookRepository:
    @staticmethod
    def search_similar_chunks(
        conn: Connection,
        query_vector: list[float],
        top_k: int = 3
    ) -> list[tuple[str, str, float]]:
        """Search for similar runbook chunks using vector similarity

        Returns:
            list of (source_doc, content, similarity_score) tuples
            similarity_score is 0.0-1.0, where 1.0 is identical
        """
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        source_doc,
                        content,
                        1 - (embedding <=> %s::vector) AS similarity
                    FROM runbook_chunks
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (query_vector, query_vector, top_k),
                )
                return cur.fetchall()
        except Exception as e:
            raise DatabaseException(f"Failed to search runbook chunks: {str(e)}")

    @staticmethod
    def get_distinct_sources(conn: Connection) -> list[tuple[str, int]]:
        """List indexed runbooks with their chunk counts, newest first.

        Returns:
            list of (source_doc, chunk_count) tuples
        """
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT source_doc, COUNT(*) AS chunk_count
                    FROM runbook_chunks
                    GROUP BY source_doc
                    ORDER BY MAX(updated_at) DESC
                    """
                )
                return cur.fetchall()
        except Exception as e:
            raise DatabaseException(f"Failed to list runbook sources: {str(e)}")

    @staticmethod
    def hybrid_search(
        conn: Connection,
        query: str,
        query_vector: list[float],
        top_k: int = 20,
    ) -> list[tuple[str, str, float]]:
        """Hybrid retrieval: BM25-style full-text search + vector search, fused with RRF.

        Catches exact matches (product codes, CLI commands, acronyms) that pure
        vector similarity can miss, while keeping semantic recall from the embedding.

        Returns:
            list of (source_doc, content, fused_score) tuples, best first
        """
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT chunk_id::text, source_doc, content
                    FROM runbook_chunks
                    WHERE content_tsv @@ plainto_tsquery('english', %s)
                    ORDER BY ts_rank(content_tsv, plainto_tsquery('english', %s)) DESC
                    LIMIT %s
                    """,
                    (query, query, top_k),
                )
                bm25_rows = cur.fetchall()

                cur.execute(
                    """
                    SELECT chunk_id::text, source_doc, content
                    FROM runbook_chunks
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (query_vector, top_k),
                )
                vector_rows = cur.fetchall()
        except Exception as e:
            raise DatabaseException(f"Failed to run hybrid search: {str(e)}")

        chunk_lookup = {row[0]: (row[1], row[2]) for row in [*bm25_rows, *vector_rows]}
        bm25_ids = [row[0] for row in bm25_rows]
        vector_ids = [row[0] for row in vector_rows]

        fused = reciprocal_rank_fusion(bm25_ids, vector_ids)

        return [
            (chunk_lookup[chunk_id][0], chunk_lookup[chunk_id][1], score)
            for chunk_id, score in fused[:top_k]
        ]

    @staticmethod
    def search_similar_chunks_by_source(
        conn: Connection,
        query_vector: list[float],
        source_filter: str,
        top_k: int = 3
    ) -> list[tuple[str, str, float]]:
        """Vector search restricted to runbooks whose filename matches source_filter."""
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        source_doc,
                        content,
                        1 - (embedding <=> %s::vector) AS similarity
                    FROM runbook_chunks
                    WHERE source_doc ILIKE %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (query_vector, f"%{source_filter}%", query_vector, top_k),
                )
                return cur.fetchall()
        except Exception as e:
            raise DatabaseException(f"Failed to search runbook chunks by source: {str(e)}")
