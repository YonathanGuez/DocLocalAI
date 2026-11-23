import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str
    db_pool_min_size: int = 2
    db_pool_max_size: int = 10

    # LLM
    llm_endpoint_url: str
    llm_model_name: str
    llm_api_token: str = "not-needed"

    # Embedding
    embedding_endpoint_url: str | None = None
    embedding_model_name: str | None = None

    # App settings
    app_title: str = "AI Assistant"  # Customizable application name
    history_window_size: int = 12
    max_tokens: int = 400  # Lower limit to prevent repetition
    temperature: float = 0.1  # Lower temperature to reduce hallucination
    top_k_context: int = 3
    similarity_threshold: float = 0.4  # Minimum similarity score (0.0-1.0) to consider a chunk relevant

    # RAG strategy: "auto", "raw", "synthesis", or custom prompt name
    # - auto: Use raw for small models (<3B), synthesis for larger
    # - raw: Use "Raw Mode" prompt template
    # - synthesis: Use "Synthesis Mode" prompt template
    # - <custom-name>: Use custom prompt template by name
    rag_strategy: str = "auto"
    active_prompt: str | None = None  # Override with specific prompt name

    @property
    def use_raw_retrieval(self) -> bool:
        """Determine if we should use raw retrieval based on model size"""
        if self.rag_strategy == "raw":
            return True
        elif self.rag_strategy == "synthesis":
            return False
        else:  # auto
            # Detect small models by name pattern
            model_lower = self.llm_model_name.lower()
            small_model_patterns = ["0.5b", "1b", "1.5b", "tiny", "small"]
            return any(pattern in model_lower for pattern in small_model_patterns)

    # Security
    api_key: str | None = None
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    rate_limit_per_minute: int = 60

    class Config:
        env_file = ".env"
        case_sensitive = False
        # Map environment variables to settings
        fields = {
            'database_url': {'env': 'DATABASE_URL'},
            'llm_endpoint_url': {'env': 'LLM_ENDPOINT_URL'},
            'llm_model_name': {'env': 'LLM_MODEL_NAME'},
            'llm_api_token': {'env': 'LLM_API_TOKEN'},
            'embedding_endpoint_url': {'env': 'EMBEDDING_ENDPOINT_URL'},
            'embedding_model_name': {'env': 'EMBEDDING_MODEL_NAME'},
            'history_window_size': {'env': 'HISTORY_WINDOW_SIZE'},
        }


settings = Settings()
