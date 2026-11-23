from psycopg import Connection
from app.models import ChatMessage
from app.exceptions import DatabaseException


class MessageRepository:
    @staticmethod
    def save_message(
        conn: Connection,
        session_id: str,
        role: str,
        content: str,
        model_version: str | None = None
    ) -> None:
        """Save a message to the database"""
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO chat_messages (session_id, role, content, model_version)
                    VALUES (%s::uuid, %s, %s, %s)
                    """,
                    (session_id, role, content, model_version),
                )
                conn.commit()
        except Exception as e:
            conn.rollback()
            raise DatabaseException(f"Failed to save message: {str(e)}")

    @staticmethod
    def get_session_messages(conn: Connection, session_id: str) -> list[ChatMessage]:
        """Get all messages for a session"""
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT role, content, model_version
                    FROM chat_messages
                    WHERE session_id = %s::uuid
                    ORDER BY created_at ASC
                    """,
                    (session_id,),
                )
                return [
                    ChatMessage(role=r[0], content=r[1], model=r[2])
                    for r in cur.fetchall()
                ]
        except Exception as e:
            raise DatabaseException(f"Failed to get session messages: {str(e)}")

    @staticmethod
    def get_conversation_history(
        conn: Connection,
        session_id: str,
        limit: int
    ) -> list[dict[str, str]]:
        """Get recent conversation history for context"""
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT role, content FROM (
                        SELECT role, content, created_at
                        FROM chat_messages
                        WHERE session_id = %s::uuid
                        ORDER BY created_at DESC
                        LIMIT %s
                    ) sub ORDER BY created_at ASC
                    """,
                    (session_id, limit),
                )
                return [{"role": r[0], "content": r[1]} for r in cur.fetchall()]
        except Exception as e:
            raise DatabaseException(f"Failed to get conversation history: {str(e)}")
