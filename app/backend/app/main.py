from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.config import settings
from app.database import Database
from app.routers import sessions_router, chat_router, runbooks_router, prompts_router, config_router
from app.middleware import setup_cors, setup_rate_limiting


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown"""
    # Startup
    Database.initialize()
    yield
    # Shutdown
    Database.close()


app = FastAPI(
    title="DocLocalAI API",
    description="OpenShift SRE Assistant with RAG capabilities",
    version="1.0.0",
    lifespan=lifespan
)

# Setup security middleware
setup_cors(app)
limiter = setup_rate_limiting(app)

# Include routers
app.include_router(sessions_router)
app.include_router(chat_router)
app.include_router(runbooks_router)
app.include_router(prompts_router)
app.include_router(config_router)


@app.get("/health")
def health():
    """Health check endpoint"""
    return {
        "status": "ok",
        "active_model": settings.llm_model_name,
        "embedding_enabled": settings.embedding_endpoint_url is not None
    }
