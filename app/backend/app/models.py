from pydantic import BaseModel, Field, UUID4
from datetime import datetime


class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=36, max_length=36, description="UUID of the session")
    message: str = Field(..., min_length=1, max_length=5000, description="User message")


class ChatMessage(BaseModel):
    role: str
    content: str
    model: str | None = None


class ChatSession(BaseModel):
    session_id: str
    title: str
    updated_at: datetime


class ChatResponse(BaseModel):
    reply: str
    model_used: str


class DeleteResponse(BaseModel):
    success: bool
    session_id: str | None = None
    message: str


class PromptTemplate(BaseModel):
    """Prompt template model"""
    prompt_id: str
    name: str
    description: str | None = None
    prompt_text: str
    is_builtin: bool
    created_at: datetime
    updated_at: datetime


class PromptTemplateCreate(BaseModel):
    """Create new prompt template"""
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    prompt_text: str = Field(..., min_length=10)


class PromptTemplateUpdate(BaseModel):
    """Update existing prompt template"""
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    prompt_text: str | None = Field(None, min_length=10)
