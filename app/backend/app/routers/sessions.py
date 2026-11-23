from fastapi import APIRouter, status
from app.database import Database
from app.models import ChatSession, ChatMessage, DeleteResponse
from app.repositories import SessionRepository, MessageRepository
from app.exceptions import SessionNotFoundException, InvalidSessionIdException
import uuid

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def validate_uuid(session_id: str) -> None:
    """Validate that session_id is a valid UUID"""
    try:
        uuid.UUID(session_id)
    except ValueError:
        raise InvalidSessionIdException()


@router.get("", response_model=list[ChatSession])
def list_sessions():
    """Get list of all chat sessions"""
    with Database.get_connection() as conn:
        return SessionRepository.list_sessions(conn)


@router.get("/{session_id}", response_model=list[ChatMessage])
def get_session_messages(session_id: str):
    """Get all messages for a specific session"""
    validate_uuid(session_id)

    with Database.get_connection() as conn:
        messages = MessageRepository.get_session_messages(conn, session_id)
        if not messages:
            # Check if session exists
            sessions = SessionRepository.list_sessions(conn, limit=1000)
            if not any(s.session_id == session_id for s in sessions):
                raise SessionNotFoundException(session_id)
        return messages


@router.delete("/{session_id}", response_model=DeleteResponse, status_code=status.HTTP_200_OK)
def delete_session(session_id: str):
    """Delete a chat session and all its messages"""
    validate_uuid(session_id)

    with Database.get_connection() as conn:
        deleted = SessionRepository.delete_session(conn, session_id)

        if not deleted:
            raise SessionNotFoundException(session_id)

        return DeleteResponse(
            success=True,
            session_id=session_id,
            message="Session deleted successfully"
        )


@router.delete("", status_code=status.HTTP_200_OK)
def delete_all_sessions():
    """Delete ALL chat sessions and their messages"""
    with Database.get_connection() as conn:
        count = SessionRepository.delete_all_sessions(conn)

        return {
            "success": True,
            "count": count,
            "message": f"Successfully deleted {count} session(s)"
        }
