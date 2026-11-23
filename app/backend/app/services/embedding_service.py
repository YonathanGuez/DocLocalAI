from openai import OpenAI
from app.config import settings
from app.exceptions import LLMException


class EmbeddingService:
    def __init__(self):
        self.client = None
        if settings.embedding_endpoint_url and settings.embedding_model_name:
            self.client = OpenAI(
                base_url=settings.embedding_endpoint_url,
                api_key=settings.llm_api_token
            )

    def get_embedding(self, text: str) -> list[float] | None:
        """Get embedding vector for text"""
        if not self.client or not settings.embedding_model_name:
            return None

        try:
            response = self.client.embeddings.create(
                model=settings.embedding_model_name,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            raise LLMException(f"Embedding generation failed: {str(e)}")
