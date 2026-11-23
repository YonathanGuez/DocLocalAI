from fastapi import APIRouter, HTTPException, status
from app.database import Database
from app.models import PromptTemplate, PromptTemplateCreate, PromptTemplateUpdate
from app.repositories import PromptRepository

router = APIRouter(prefix="/api/prompts", tags=["prompts"])


@router.get("", response_model=list[PromptTemplate])
def list_prompts():
    """Get list of all prompt templates (built-in + custom)"""
    with Database.get_connection() as conn:
        return PromptRepository.list_prompts(conn)


@router.get("/{name}", response_model=PromptTemplate)
def get_prompt(name: str):
    """Get a specific prompt template by name"""
    with Database.get_connection() as conn:
        prompt = PromptRepository.get_prompt_by_name(conn, name)
        if not prompt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prompt '{name}' not found"
            )
        return prompt


@router.post("", response_model=PromptTemplate, status_code=status.HTTP_201_CREATED)
def create_prompt(prompt: PromptTemplateCreate):
    """Create a new custom prompt template"""
    with Database.get_connection() as conn:
        # Check if name already exists
        existing = PromptRepository.get_prompt_by_name(conn, prompt.name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Prompt with name '{prompt.name}' already exists"
            )

        try:
            return PromptRepository.create_prompt(
                conn,
                prompt.name,
                prompt.description,
                prompt.prompt_text
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create prompt: {str(e)}"
            )


@router.put("/{prompt_id}", response_model=dict)
def update_prompt(prompt_id: str, prompt: PromptTemplateUpdate):
    """Update a custom prompt template (built-in prompts cannot be updated)"""
    with Database.get_connection() as conn:
        updated = PromptRepository.update_prompt(
            conn,
            prompt_id,
            prompt.name,
            prompt.description,
            prompt.prompt_text
        )

        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prompt not found or is a built-in prompt (cannot be modified)"
            )

        return {
            "success": True,
            "message": "Prompt updated successfully"
        }


@router.delete("/{prompt_id}")
def delete_prompt(prompt_id: str):
    """Delete a custom prompt template (built-in prompts cannot be deleted)"""
    with Database.get_connection() as conn:
        deleted = PromptRepository.delete_prompt(conn, prompt_id)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prompt not found or is a built-in prompt (cannot be deleted)"
            )

        return {
            "success": True,
            "message": "Prompt deleted successfully"
        }
