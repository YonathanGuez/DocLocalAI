from psycopg import Connection
from app.exceptions import DatabaseException


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
