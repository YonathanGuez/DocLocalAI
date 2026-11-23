from fastapi import APIRouter
from app.database import Database
from app.models import ChatRequest, ChatResponse
from app.services import ChatService
from app.routers.sessions import validate_uuid

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Process a chat message and return AI response"""
    validate_uuid(req.session_id)

    chat_service = ChatService()

    with Database.get_connection() as conn:
        assistant_reply, model_used = chat_service.process_chat(
            conn,
            req.session_id,
            req.message
        )

    return ChatResponse(reply=assistant_reply, model_used=model_used)
