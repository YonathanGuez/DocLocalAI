from fastapi import APIRouter
from pydantic import BaseModel
from app.config import settings

router = APIRouter(prefix="/api/config", tags=["config"])


class ActivePromptConfig(BaseModel):
    active_prompt: str | None


@router.get("/active-prompt")
def get_active_prompt():
    """Get the currently active prompt template name"""
    return {
        "active_prompt": settings.active_prompt,
        "rag_strategy": settings.rag_strategy
    }


@router.post("/active-prompt")
def set_active_prompt(config: ActivePromptConfig):
    """Set the active prompt template (runtime only, not persisted)"""
    settings.active_prompt = config.active_prompt
    return {
        "success": True,
        "active_prompt": settings.active_prompt,
        "message": f"Active prompt set to: {config.active_prompt or 'auto (strategy-based)'}"
    }
