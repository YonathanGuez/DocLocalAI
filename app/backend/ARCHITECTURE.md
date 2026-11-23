# DocLocalAI Backend Architecture

## Overview

This backend has been restructured following best practices for security, maintainability, and scalability.

## Project Structure

```
app/
├── main.py                    # Application entry point, FastAPI app setup
├── config.py                  # Centralized configuration management
├── database.py                # Database connection pooling and management
├── models.py                  # Pydantic models for request/response validation
├── exceptions.py              # Custom exception classes
├── middleware/                # Security and cross-cutting concerns
│   ├── __init__.py
│   └── security.py           # CORS and rate limiting setup
├── repositories/              # Database access layer (data persistence)
│   ├── __init__.py
│   ├── session_repository.py # Session CRUD operations
│   ├── message_repository.py # Message CRUD operations
│   └── runbook_repository.py # Runbook vector search
├── services/                  # Business logic layer
│   ├── __init__.py
│   ├── chat_service.py       # Chat orchestration and LLM integration
│   └── embedding_service.py  # Embedding generation
└── routers/                   # API endpoints (presentation layer)
    ├── __init__.py
    ├── sessions.py           # Session management endpoints
    └── chat.py               # Chat endpoints
```

## Architectural Layers

### 1. **Routers** (Presentation Layer)

- Handle HTTP requests/responses
- Input validation via Pydantic models
- Coordinate between services
- Return appropriate status codes

### 2. **Services** (Business Logic Layer)

- Implement core business logic
- Orchestrate between multiple repositories
- Handle LLM and embedding operations
- No direct HTTP concerns

### 3. **Repositories** (Data Access Layer)

- Direct database operations
- SQL query execution
- Data transformation to/from models
- Transaction management

### 4. **Models** (Data Transfer Objects)

- Request/response schemas
- Input validation rules
- Type safety

### 5. **Middleware** (Cross-cutting Concerns)

- Security (CORS, rate limiting)
- Authentication (ready for future implementation)
- Logging and monitoring (ready for expansion)

## Security Improvements

### 1. **Connection Pooling**

- Uses `psycopg-pool` for efficient connection management
- Configurable min/max pool size
- Automatic connection recycling
- Prevents connection exhaustion

### 2. **Input Validation**

- UUID format validation on session IDs
- Message length constraints (1-5000 chars)
- Pydantic model validation on all inputs
- Protection against invalid data

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

## API Endpoints

### Health Check

- `GET /health` - Service health and model info

### Sessions

- `GET /api/sessions` - List recent sessions
- `GET /api/sessions/{session_id}` - Get session messages
- `DELETE /api/sessions/{session_id}` - Delete session

### Chat

- `POST /api/chat` - Send message and get response

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

# App Settings
HISTORY_WINDOW_SIZE=12
MAX_TOKENS=800
TEMPERATURE=0.3
TOP_K_CONTEXT=3

# Security
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

## Future Enhancements

Ready for easy addition:

- [ ] User authentication (JWT tokens)
- [ ] API key authentication
- [ ] Request/response logging middleware
- [ ] Metrics and monitoring (Prometheus)
- [ ] Distributed tracing (OpenTelemetry)
- [ ] Caching layer (Redis)
- [ ] Async database operations
- [ ] Background task processing (Celery)

## Testing

Structure enables easy unit testing:

- Mock repositories for service tests
- Mock services for router tests
- Integration tests with test database
- FastAPI TestClient for API tests

## Migration from Old Code

The old monolithic `main.py` has been refactored into this layered architecture while maintaining the same functionality and API contracts.
