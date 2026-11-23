from psycopg import Connection
from app.models import ChatSession
from app.exceptions import DatabaseException


class SessionRepository:
    @staticmethod
    def create_or_update(conn: Connection, session_id: str, title: str) -> None:
        """Create a new session or update existing one"""
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO chat_sessions (session_id, title)
                    VALUES (%s::uuid, %s)
                    ON CONFLICT (session_id) DO NOTHING
                    """,
                    (session_id, title),
                )
                conn.commit()
        except Exception as e:
            conn.rollback()
            raise DatabaseException(f"Failed to create/update session: {str(e)}")

    @staticmethod
    def list_sessions(conn: Connection, limit: int = 25) -> list[ChatSession]:
        """Get list of recent sessions"""
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT session_id::text, title, updated_at
                    FROM chat_sessions
                    ORDER BY updated_at DESC
                    LIMIT %s
                    """,
                    (limit,)
                )
                return [
                    ChatSession(
                        session_id=r[0],
                        title=r[1],
                        updated_at=r[2]
                    )
                    for r in cur.fetchall()
                ]
        except Exception as e:
            raise DatabaseException(f"Failed to list sessions: {str(e)}")

    @staticmethod
    def delete_session(conn: Connection, session_id: str) -> bool:
        """Delete a session and all its messages"""
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM chat_sessions
                    WHERE session_id = %s::uuid
                    RETURNING session_id::text
                    """,
                    (session_id,),
                )
                deleted = cur.fetchone()
                conn.commit()
                return deleted is not None
        except Exception as e:
            conn.rollback()
            raise DatabaseException(f"Failed to delete session: {str(e)}")

    @staticmethod
    def touch_session(conn: Connection, session_id: str) -> None:
        """Update session's updated_at timestamp"""
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE chat_sessions SET updated_at = NOW() WHERE session_id = %s::uuid",
                    (session_id,),
                )
                conn.commit()
        except Exception as e:
            conn.rollback()
            raise DatabaseException(f"Failed to update session timestamp: {str(e)}")

    @staticmethod
    def delete_all_sessions(conn: Connection) -> int:
        """Delete all sessions and their messages

        Returns:
            Number of sessions deleted
        """
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM chat_sessions")
                count = cur.fetchone()[0]

                cur.execute("DELETE FROM chat_sessions")
                conn.commit()
                return count
        except Exception as e:
            conn.rollback()
            raise DatabaseException(f"Failed to delete all sessions: {str(e)}")
