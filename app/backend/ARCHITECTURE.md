# DocLocalAI Backend Architecture

## Overview

This backend is a layered FastAPI service implementing a RAG (Retrieval-Augmented Generation) assistant over user-uploaded runbooks, with hybrid search, re-ranking, query routing, and citation tracking on top of a local/self-hosted LLM and embedding model.

## Project Structure

```
app/
├── main.py                      # Application entry point, FastAPI app setup
├── config.py                    # Centralized configuration management
├── database.py                  # Database connection pooling and management
├── models.py                    # Pydantic models for request/response validation
├── exceptions.py                # Custom exception classes
├── middleware/                  # Security and cross-cutting concerns
│   ├── __init__.py
│   └── security.py             # CORS and rate limiting setup
├── repositories/                # Database access layer (data persistence)
│   ├── __init__.py
│   ├── session_repository.py   # Session CRUD operations
│   ├── message_repository.py   # Message CRUD operations
│   ├── runbook_repository.py   # Runbook vector/hybrid search
│   └── prompt_repository.py    # Prompt template CRUD operations
├── services/                    # Business logic layer
│   ├── __init__.py
│   ├── chat_service.py         # Chat orchestration, retrieval pipeline, LLM integration
│   ├── embedding_service.py    # Embedding generation
│   ├── reranker_service.py     # Lexical re-ranking of retrieved chunks
│   ├── query_router.py         # Classifies queries (vector search / list / metadata filter)
│   ├── query_transform.py      # Ambiguity detection, synonym expansion, history rewriting
│   └── citations.py            # Inline [N] citation building and extraction
├── schemas/                     # Structured output schema and response safety checks
│   ├── __init__.py
│   └── response_schema.py      # Structured LLM output schema + BusinessRuleValidator
└── routers/                     # API endpoints (presentation layer)
    ├── __init__.py
    ├── sessions.py              # Session management endpoints
    ├── chat.py                  # Chat endpoint
    ├── runbooks.py              # Runbook upload/list/delete/reindex endpoints
    ├── prompts.py                # Prompt template CRUD endpoints
    └── config.py                # Runtime config (active prompt) endpoints

scripts/
└── index_runbooks.py            # Standalone runbook indexing job (embeds + stores chunks)

tests/                            # pytest suite (unit tests per service/repository)
```

## Architectural Layers

### 1. **Routers** (Presentation Layer)

- Handle HTTP requests/responses
- Input validation via Pydantic models
- Coordinate between services/repositories
- Return appropriate status codes

### 2. **Services** (Business Logic Layer)

- Implement core business logic and the RAG retrieval pipeline
- Orchestrate between multiple repositories
- Handle LLM and embedding operations
- No direct HTTP concerns

### 3. **Repositories** (Data Access Layer)

- Direct database operations
- SQL query execution
- Data transformation to/from models
- Transaction management

### 4. **Models / Schemas** (Data Transfer Objects)

- `models.py`: request/response schemas, input validation rules, type safety
- `schemas/response_schema.py`: structured LLM output schema (for optional JSON-mode generation) and `BusinessRuleValidator`, which screens every LLM response for leaked credentials and destructive shell commands

### 5. **Middleware** (Cross-cutting Concerns)

- Security (CORS, rate limiting)
- Authentication (ready for future implementation — an `api_key` setting exists but is not yet enforced)
- Logging and monitoring (ready for expansion)

## Retrieval Pipeline (RAG)

`ChatService.retrieve_context` drives the following pipeline for each incoming message:

1. **Query routing** (`query_router.py`) — classifies the query as a vector search, a "list available runbooks" request, or a metadata-filtered search (e.g. `in "filename"`).
2. **Query transformation** (`query_transform.py`) — detects queries too ambiguous to retrieve against (asks the user to clarify), rewrites pronoun-referencing follow-ups into standalone queries using recent history, and expands the query with domain synonyms before embedding.
3. **Hybrid retrieval** (`runbook_repository.py`) — combines BM25 keyword search and vector similarity search via Reciprocal Rank Fusion when `enable_hybrid_search` is on, falling back to vector-only search on error.
4. **Re-ranking** (`reranker_service.py`) — when `enable_reranker` is on, narrows the broad recall set (`initial_retrieval_k`) down to `top_k_context` using lexical overlap scoring; reranked results are filtered against `rerank_threshold` instead of `similarity_threshold`, since the two scores are on different scales.
5. **Citation building** (`citations.py`) — tags retrieved chunks with `[N]` markers and builds a `chunk_id -> (source, content)` map so the LLM's response can be matched back to its sources.
6. **RAG strategy selection** — based on `rag_strategy` (`auto`, `raw`, or `synthesis`) and `active_prompt`, the response is either returned as a list of source references only (**Raw Mode**, used for small models by default) or synthesized by the LLM using a prompt template loaded from the database (**Synthesis Mode**).
7. **Response safety checks** (`BusinessRuleValidator`) — LLM responses are screened for credential leaks (blocked outright) and destructive commands (flagged with a warning) before being returned.

## Security Improvements

### 1. **Connection Pooling**

- Uses `psycopg-pool` for efficient connection management
- Configurable min/max pool size
- Automatic connection recycling
- Prevents connection exhaustion

### 2. **Input Validation**

- UUID format validation on session IDs
- Message length constraints (1-5000 chars)
- Runbook upload validation (extension, size limit, UTF-8 content, path traversal checks)
- Pydantic model validation on all inputs

### 3. **SQL Injection Prevention**

- All queries use parameterized statements
- No string concatenation in SQL
- Type-safe UUID casting

### 4. **Error Handling**

- Custom exception hierarchy
- Proper HTTP status codes
- Transaction rollback on errors
- No sensitive data in error messages

### 5. **Rate Limiting**

- Configurable per-IP rate limits
- Protection against abuse
- Default: 60 requests/minute

### 6. **CORS Configuration**

- Whitelist-based origin control
- Configurable allowed origins
- Prevents unauthorized cross-origin requests

### 7. **Environment-based Configuration**

- All secrets in environment variables
- No hardcoded credentials
- Validation of required settings

### 8. **Response Safety Checks**

- Post-generation screening for leaked credentials (blocks the response)
- Post-generation screening for destructive shell commands (flags with a warning)

## API Endpoints

### Health Check

- `GET /health` - Service health and active model info

### Sessions

- `GET /api/sessions` - List recent sessions
- `GET /api/sessions/{session_id}` - Get session messages
- `DELETE /api/sessions/{session_id}` - Delete a session
- `DELETE /api/sessions` - Delete all sessions

### Chat

- `POST /api/chat` - Send message and get response

### Runbooks

- `GET /api/runbooks` - List sample and uploaded runbooks
- `GET /api/runbooks/{filename}/content` - Get the content of a runbook
- `POST /api/runbooks/upload` - Upload a runbook (.md/.txt, max 2MB) and trigger re-indexing
- `DELETE /api/runbooks/{filename}` - Delete an uploaded runbook (samples are not deletable) and trigger re-indexing
- `POST /api/runbooks/reindex` - Manually trigger re-indexing

### Prompt Templates

- `GET /api/prompts` - List built-in and custom prompt templates
- `GET /api/prompts/{name}` - Get a prompt template by name
- `POST /api/prompts` - Create a custom prompt template
- `PUT /api/prompts/{prompt_id}` - Update a custom prompt template (built-ins are immutable)
- `DELETE /api/prompts/{prompt_id}` - Delete a custom prompt template (built-ins are immutable)

### Runtime Config

- `GET /api/config/active-prompt` - Get the active prompt name and RAG strategy
- `POST /api/config/active-prompt` - Set the active prompt template (runtime only, not persisted)

## Configuration

Create a `.env` file or set environment variables:

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost/DocLocalAI
DB_POOL_MIN_SIZE=2
DB_POOL_MAX_SIZE=10

# LLM
LLM_ENDPOINT_URL=http://localhost:8080/v1
LLM_MODEL_NAME=mistral
LLM_API_TOKEN=not-needed

# Embedding (optional)
EMBEDDING_ENDPOINT_URL=http://localhost:8080/v1
EMBEDDING_MODEL_NAME=nomic-embed-text

# App settings
APP_TITLE="AI Assistant"
HISTORY_WINDOW_SIZE=12
MAX_TOKENS=400
TEMPERATURE=0.1
TOP_K_CONTEXT=3
SIMILARITY_THRESHOLD=0.4

# Retrieval pipeline (hybrid search + re-ranking)
ENABLE_HYBRID_SEARCH=true
ENABLE_RERANKER=true
INITIAL_RETRIEVAL_K=20
RERANK_THRESHOLD=0.3

# RAG strategy: auto | raw | synthesis | <custom prompt name>
RAG_STRATEGY=auto
ACTIVE_PROMPT=

# Security
API_KEY=
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]
RATE_LIMIT_PER_MINUTE=60
```

## Running the Application

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Set environment variables or create `.env` file

3. Run the server:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Database Management

The application uses connection pooling with:

- Automatic initialization on startup
- Graceful shutdown on application close
- Context managers for safe connection handling
- Transaction management with automatic rollback

## Testing

The `tests/` directory contains a pytest suite covering the retrieval pipeline and data layer, including:

- `test_chat_service.py`, `test_query_router.py`, `test_query_transform.py`, `test_reranker_service.py`, `test_citations.py`
- `test_response_schema.py` (structured output + business rule validation)
- `test_runbook_repository.py`, `test_index_runbooks.py`

The layered structure (routers / services / repositories) keeps these independently testable via mocking at each boundary.

## Future Enhancements

- [ ] User authentication (JWT tokens)
- [ ] API key authentication (settings field exists, not yet enforced)
- [ ] Request/response logging middleware
- [ ] Metrics and monitoring (Prometheus)
- [ ] Distributed tracing (OpenTelemetry)
- [ ] Caching layer (Redis)
- [ ] Async database operations
- [ ] Background task processing via a real task queue (currently uses ad hoc `subprocess.Popen` for re-indexing)
- [ ] Wire up structured JSON-mode output (`schemas/response_schema.py` is scaffolded but not yet used by `generate_response`)
