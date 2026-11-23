from psycopg import Connection
from app.models import PromptTemplate
from app.exceptions import DatabaseException


class PromptRepository:
    @staticmethod
    def list_prompts(conn: Connection) -> list[PromptTemplate]:
        """Get list of all prompt templates"""
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT prompt_id::text, name, description, prompt_text, is_builtin, created_at, updated_at
                    FROM prompt_templates
                    ORDER BY is_builtin DESC, name ASC
                    """
                )
                return [
                    PromptTemplate(
                        prompt_id=r[0],
                        name=r[1],
                        description=r[2],
                        prompt_text=r[3],
                        is_builtin=r[4],
                        created_at=r[5],
                        updated_at=r[6]
                    )
                    for r in cur.fetchall()
                ]
        except Exception as e:
            raise DatabaseException(f"Failed to list prompts: {str(e)}")

    @staticmethod
    def get_prompt_by_name(conn: Connection, name: str) -> PromptTemplate | None:
        """Get a prompt template by name"""
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT prompt_id::text, name, description, prompt_text, is_builtin, created_at, updated_at
                    FROM prompt_templates
                    WHERE name = %s
                    """,
                    (name,)
                )
                row = cur.fetchone()
                if row:
                    return PromptTemplate(
                        prompt_id=row[0],
                        name=row[1],
                        description=row[2],
                        prompt_text=row[3],
                        is_builtin=row[4],
                        created_at=row[5],
                        updated_at=row[6]
                    )
                return None
        except Exception as e:
            raise DatabaseException(f"Failed to get prompt: {str(e)}")

    @staticmethod
    def create_prompt(conn: Connection, name: str, description: str | None, prompt_text: str) -> PromptTemplate:
        """Create a new custom prompt template"""
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO prompt_templates (name, description, prompt_text, is_builtin)
                    VALUES (%s, %s, %s, FALSE)
                    RETURNING prompt_id::text, name, description, prompt_text, is_builtin, created_at, updated_at
                    """,
                    (name, description, prompt_text)
                )
                row = cur.fetchone()
                conn.commit()

                return PromptTemplate(
                    prompt_id=row[0],
                    name=row[1],
                    description=row[2],
                    prompt_text=row[3],
                    is_builtin=row[4],
                    created_at=row[5],
                    updated_at=row[6]
                )
        except Exception as e:
            conn.rollback()
            raise DatabaseException(f"Failed to create prompt: {str(e)}")

    @staticmethod
    def update_prompt(conn: Connection, prompt_id: str, name: str | None, description: str | None, prompt_text: str | None) -> bool:
        """Update a custom prompt template (built-in prompts cannot be updated)"""
        try:
            updates = []
            params = []

            if name is not None:
                updates.append("name = %s")
                params.append(name)
            if description is not None:
                updates.append("description = %s")
                params.append(description)
            if prompt_text is not None:
                updates.append("prompt_text = %s")
                params.append(prompt_text)

            if not updates:
                return False

            updates.append("updated_at = NOW()")
            params.append(prompt_id)

            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE prompt_templates
                    SET {', '.join(updates)}
                    WHERE prompt_id = %s::uuid AND is_builtin = FALSE
                    RETURNING prompt_id
                    """,
                    params
                )
                updated = cur.fetchone()
                conn.commit()
                return updated is not None
        except Exception as e:
            conn.rollback()
            raise DatabaseException(f"Failed to update prompt: {str(e)}")

    @staticmethod
    def delete_prompt(conn: Connection, prompt_id: str) -> bool:
        """Delete a custom prompt template (built-in prompts cannot be deleted)"""
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM prompt_templates
                    WHERE prompt_id = %s::uuid AND is_builtin = FALSE
                    RETURNING prompt_id
                    """,
                    (prompt_id,)
                )
                deleted = cur.fetchone()
                conn.commit()
                return deleted is not None
        except Exception as e:
            conn.rollback()
            raise DatabaseException(f"Failed to delete prompt: {str(e)}")
