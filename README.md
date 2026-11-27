# DocLocalAI — Knowledge Assistant

> Local RAG-powered assistant with PostgreSQL + pgvector, Ollama (LLM + embeddings), FastAPI backend, and Streamlit UI.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

![screenshot](./doc/screen.png)

## 🆕 Recent Updates

✨ **Advanced Retrieval Pipeline** — see **[RAG_GUIDE.md](./RAG_GUIDE.md)** for the full write-up with before/after examples and Mermaid diagrams for every change

- **Hybrid search**: BM25 full-text + vector search, fused with Reciprocal Rank Fusion (catches exact commands/codes that pure vector search misses)
- **Two-stage re-ranking**: broad recall (top-20) narrowed to top-k with lexical re-ranking
- **Contextual retrieval**: chunks embedded with document context prefixed (Anthropic's Contextual Retrieval pattern)
- **Markdown-aware chunking**: headers, paragraphs, and code fences are never split mid-block
- **Query transformation**: ambiguous queries trigger a clarification prompt; follow-ups are rewritten standalone using chat history; synonym expansion broadens recall
- **Query routing**: "what runbooks do you have?" and "...in the 'x.md' runbook..." are answered directly/scoped instead of going through a generic vector search
- **Inline per-claim citations**: responses cite `[1]`, `[2]` per claim, validated against the retrieved chunks
- **Output guardrails**: responses are scanned for leaked credentials (blocked) and destructive commands (flagged)
- **Content deduplication**: identical chunk content across runbooks is only embedded/stored once

✨ **Intelligent Relevance Detection**

- Similarity threshold (40%) detects when no relevant docs exist
- Shows "No documentation found" with helpful suggestions
- Displays relevance percentage on every response (e.g., "Relevance: 85.3%")

✨ **Improved RAG Strategies**

- **RAW mode**: Shows ONLY source references (zero hallucination for small models)
- **SYNTHESIS mode**: LLM explains and summarizes (better for 3B+ models)
- Different system prompts optimized for each mode
- Generic & customizable - works for any domain (not just OpenShift)

✨ **Enhanced UX**

- **Clear All Sessions**: Bulk delete with confirmation
- **Auto-refresh**: Source buttons appear immediately without page reload
- **File uploader reset**: Clears automatically after successful upload
- **Unique button keys**: Ask same question multiple times without errors

✨ **Auto-Indexing**

- Upload/delete triggers background re-indexing (10-15 seconds)
- No manual restart needed
- Orphaned chunks automatically cleaned from database

---

## 🚀 Quick Start

```bash
# Clone the repository
git clone <your-repo-url>
cd DocLocalAI

# Start all services
podman-compose up -d
# OR
docker-compose up -d

# Wait for models to download (first run only, ~2-3 minutes)
podman-compose logs -f ollama-init
```

**When you see:** `✅ Local models ready.` → Open http://localhost:8501

| Service        | URL                        |
| -------------- | -------------------------- |
| **UI**         | http://localhost:8501      |
| **API**        | http://localhost:8000      |
| **API Docs**   | http://localhost:8000/docs |
| **Ollama**     | http://localhost:11434     |
| **PostgreSQL** | localhost:5432             |

---

## ✨ Features

### 🤖 **Intelligent RAG System**

- **Adaptive Strategy**: Auto-detects model size and chooses optimal approach
  - Small models (0.5b-1.5b): Shows only source references (zero hallucination)
  - Large models (3b+): LLM synthesizes conversational answers
  - Manual override: Set `RAG_STRATEGY` to "raw" or "synthesis"
- **Relevance Detection**: Similarity threshold (40%) filters irrelevant results
  - Shows "No documentation found" when relevance is too low
  - Displays relevance percentage on every response
  - Suggests rephrasing or uploading relevant content
- **Hybrid Search**: pgvector cosine similarity + Postgres full-text search (BM25-style), fused with Reciprocal Rank Fusion
- **Re-ranking**: broad recall (top-20) re-ranked by lexical overlap before truncating to the final top-k, counters "Lost in the Middle"
- **Query Routing & Transformation**: list/browse and scoped-by-filename queries are answered directly; ambiguous queries ask for clarification; follow-ups are rewritten using chat history
- **Inline Citations**: responses cite `[1]`, `[2]` per claim when the model supports it, validated against retrieved chunks
- **Output Guardrails**: responses are scanned for leaked credentials (blocked) and destructive commands (flagged)
- **Source Citations**: Every answer shows which runbook it came from
- **Generic & Customizable**: Works for any domain (not just OpenShift)
- Full details: **[RAG_GUIDE.md](./RAG_GUIDE.md)**

### 💬 **Chat Interface**

- **Multi-Session**: Create and manage multiple conversations
- **Delete Sessions**: Remove individual conversations with confirmation dialog
- **Clear All Sessions**: Bulk delete all conversations with safety confirmation
- **Auto-Refresh**: Source buttons appear immediately without page reload
- **Persistent**: All chats saved to PostgreSQL
- **History**: Maintains conversation context (configurable window size)

### 🔒 **Secure Architecture**

- **Connection Pooling**: Efficient database connections
- **Input Validation**: UUID and length constraints
- **SQL Injection Protection**: Parameterized queries
- **Rate Limiting**: Configurable per-IP limits (60 req/min default)
- **CORS Protection**: Whitelist-based origin control

### 📚 **Runbook Management**

- **UI Upload**: Upload runbooks via web interface (max 2MB, .md/.txt)
  - **Auto-Reset**: File uploader clears after successful upload
  - **Validation**: Client & server-side 2MB limit enforcement
- **Auto-Indexing**: Uploads/deletes trigger automatic re-indexing (10-15 seconds)
  - **Background Processing**: No manual restart needed
  - **Orphan Cleanup**: Deleted files automatically removed from vector database
- **Dual Storage**: Sample runbooks (read-only) + user uploads (persistent volume)
- **Easy Indexing**: Drop markdown files in `runbooks/` directory
- **Markdown-Aware Chunking**: Splits docs into ~500-char chunks without breaking headers, paragraphs, or code fences mid-block
- **Contextual Retrieval**: each chunk is embedded with a document-context prefix for better recall (raw text is still what's stored/shown)
- **Deduplication**: identical chunk content across runbooks is embedded/stored only once (content-hash based)
- **Vector Embeddings**: nomic-embed-text model (768 dimensions)
- **Similarity Search**: Sub-second retrieval with cosine distance + hybrid full-text search
- **Runbook Viewer**: Click source citations to view full runbook content inlineS

---

## 🏗️ Architecture

```mermaid
graph TB
    Browser[🌐 Browser]

    subgraph UI["Streamlit UI :8501"]
        Chat[💬 Chat Interface]
        Sessions[📋 Session Management]
        Upload[📤 Upload Runbooks]
        ViewDocs[📖 View Documentation]
    end

    subgraph Backend["FastAPI Backend :8000"]
        subgraph Routers
            SessionRouter[sessions.py]
            ChatRouter[chat.py]
            RunbookRouter[runbooks.py]
            PromptRouter[prompts.py]
            ConfigRouter[config.py]
        end

        subgraph Services
            ChatService[chat_service]
            EmbeddingService[embedding]
            QueryRouter[query_router]
            QueryTransform[query_transform]
            Reranker[reranker_service]
            Citations[citations]
        end

        subgraph Repositories
            SessionRepo[session_repo]
            MessageRepo[message_repo]
            RunbookRepo["runbook_repo<br/>(hybrid search + RRF)"]
            PromptRepo[prompt_repo]
        end
    end

    subgraph Database["PostgreSQL + pgvector :5432"]
        Sessions_DB[(Sessions)]
        Messages_DB[(Messages)]
        Runbooks_DB[(Runbooks)]
    end

    subgraph LLM["Ollama :11434"]
        Model[🤖 qwen2.5:0.5b]
        Embeddings[🔤 nomic-embed-text]
    end

    Indexer[🔄 Auto-Indexer<br/>- On upload<br/>- On delete<br/>- Cleanup orphans]

    Browser --> UI
    UI --> Routers
    Routers --> Services
    Services --> Repositories
    Repositories --> Database
    Services --> LLM
    RunbookRouter -.->|triggers| Indexer
    Indexer --> Database
    Indexer --> LLM

    style Browser fill:#bdbdbd,stroke:#616161,stroke-width:2px,color:#000
    style UI fill:#ffb74d,stroke:#f57c00,stroke-width:2px,color:#000
    style Backend fill:#64b5f6,stroke:#1976d2,stroke-width:2px,color:#000
    style Database fill:#81c784,stroke:#388e3c,stroke-width:2px,color:#000
    style LLM fill:#f06292,stroke:#c2185b,stroke-width:2px,color:#000
    style Indexer fill:#fff176,stroke:#f9a825,stroke-width:2px,color:#000
```

**Stack:**

- **Frontend**: Streamlit (Python)
- **Backend**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 16 + pgvector
- **LLM**: Ollama (OpenAI-compatible API)
- **Embeddings**: nomic-embed-text (768 dimensions)
- **Models**: qwen2.5:0.5b (default, 400MB)

---

## ☁️ Deployment on OpenShift & OpenShift AI

In addition to running locally with Podman/Docker Compose + Ollama, DocLocalAI can be deployed on **OpenShift** with model serving on **OpenShift AI**:

- **Qwen 2.5 1.5B Instruct** — text generation, served via llm-d / vLLM (OpenAI-compatible `/v1/chat/completions`)
- **BGE-Small-EN-v1.5** — embeddings, served via llm-d / vLLM (OpenAI-compatible `/v1/embeddings`, 384 dimensions)

This setup replaces the local Ollama service with HuggingFace models deployed as `LLMInferenceService` resources on OpenShift AI, while the rest of the stack (FastAPI backend, Streamlit UI, PostgreSQL + pgvector) runs as standard OpenShift workloads.

See **[openshift/README.md](./openshift/README.md)** for full deployment instructions, resource sizing, and dashboard/CLI steps.

---

## 🎯 Usage

### Ask Questions

```
"My pod is in CrashLoopBackOff, how do I debug it?"
"How to troubleshoot OpenShift networking issues?"
"What causes ImagePullBackOff errors?"
"How do I check if a service is reachable?"
```

### RAG Strategy Modes

The system adapts based on your model and configuration:

#### **Raw Mode** (Small Models: 0.5b, 1b, 1.5b)

_Shows ONLY source references - prevents hallucination_

```
✅ I found relevant information in this runbook:

📄 openshift-pod-troubleshooting.md

💡 Click the source button below to view the full runbook content.

*Relevance: 85.3%*

---
📚 Source: openshift-pod-troubleshooting.md
```

#### **Synthesis Mode** (Large Models: 3b, 7b+)

_LLM summarizes and explains the documentation_

```
To troubleshoot OOM kill:

1. Check pod events:
   oc describe pod <pod-name>

2. Increase memory limits:
   oc edit deployment my-deployment

3. Update resources.limits.memory value

4. Monitor with:
   oc get pods -w

*Relevance: 78.4%*

---
📚 Source: openshift-pod-troubleshooting.md
```

#### **No Relevant Content**

_When similarity is below threshold (40%)_

```
❌ I don't have runbooks on this subject.

The closest match I found had a similarity of 25.4%,
which is below the relevance threshold of 40.0%.

💡 Suggestions:
- Try rephrasing your question
- Upload relevant runbooks via the sidebar
- Ask about topics covered in your knowledge base
```

**Configure via environment:**

```yaml
RAG_STRATEGY: "auto"      # Smart detection (default)
RAG_STRATEGY: "raw"       # Always show only source references
RAG_STRATEGY: "synthesis" # Always use LLM to synthesize answers
SIMILARITY_THRESHOLD: "0.4"  # 0.0-1.0, minimum relevance (40% default)
```

---

## ⚙️ Configuration

### Environment Variables

Edit `docker-compose.yml`. The `api` service and the `ui` service each read their own env vars — `APP_TITLE` is set independently on both (backend uses it to name itself in prompts, frontend uses it as the page heading), so the two can differ.

**`api` service:**

```yaml
environment:
  # Database
  DATABASE_URL: postgresql://doclocalai:password@db:5432/doclocalai
  DB_POOL_MIN_SIZE: 2
  DB_POOL_MAX_SIZE: 10

  # LLM
  LLM_ENDPOINT_URL: http://ollama:11434/v1
  LLM_MODEL_NAME: qwen2.5:0.5b
  LLM_API_TOKEN: not-needed

  # Embeddings
  EMBEDDING_ENDPOINT_URL: http://ollama:11434/v1
  EMBEDDING_MODEL_NAME: nomic-embed-text

  # RAG Settings
  HISTORY_WINDOW_SIZE: "12"       # Conversation context
  MAX_TOKENS: "400"                # Response length limit (lower prevents repetition)
  TEMPERATURE: "0.1"               # Lower = less creative/hallucination
  TOP_K_CONTEXT: "3"               # Runbook chunks to retrieve (final, after re-ranking)
  RAG_STRATEGY: "auto"             # auto|raw|synthesis
  SIMILARITY_THRESHOLD: "0.4"      # 0.0-1.0, minimum relevance to show results

  # Retrieval pipeline (see RAG_GUIDE.md)
  ENABLE_HYBRID_SEARCH: "true"     # BM25 + vector fused with RRF (falls back to vector-only on error)
  ENABLE_RERANKER: "true"          # Lexical re-ranking of the broad recall set
  INITIAL_RETRIEVAL_K: "20"        # Broad recall size before re-ranking
  RERANK_THRESHOLD: "0.3"          # Min blended rerank score (different scale than cosine similarity)

  # Application name used inside prompts
  APP_TITLE: "DocLocalAI — OpenShift Incident & Runbook Assistant"

  # Security
  CORS_ORIGINS: ["http://localhost:3000","http://localhost:5173"]
  RATE_LIMIT_PER_MINUTE: 60
```

**`ui` service:**

```yaml
environment:
  DOCLOCALAI_API_URL: http://api:8000
  APP_TITLE: "DocLocalAI — OpenShift Incident & Runbook Assistant"  # Page heading
  APP_PAGE_TITLE: "DocLocalAI Assistant"                             # Browser tab title
```

### Upgrade Models

```bash
# Install 3B model (better quality, 2GB)
podman exec doclocalai-ollama ollama pull qwen2.5:3b

# Update docker-compose.yml
LLM_MODEL_NAME: qwen2.5:3b

# Restart
podman-compose up -d doclocalai-api
```

**Available models:**
| Model | Size | RAM | Mode | Quality |
|-------|------|-----|------|---------|
| qwen2.5:0.5b | 400MB | ~1GB | Raw | ⭐⭐ |
| qwen2.5:3b | 2GB | ~4GB | Synthesis | ⭐⭐⭐⭐ |
| qwen2.5:7b | 4GB | ~8GB | Synthesis | ⭐⭐⭐⭐⭐ |

### Similarity Threshold Tuning

The system uses a **similarity threshold (default: 0.4 or 40%)** to determine if retrieved content is relevant:

**Adjust in `docker-compose.yml`:**

```yaml
SIMILARITY_THRESHOLD: "0.4" # 0.0-1.0
```

**Guidelines:**

- **0.3-0.4** (Recommended): Balanced - catches most relevant content
- **0.5-0.6** (Strict): Only very relevant matches, may miss some content
- **0.2-0.3** (Lenient): More results, but may include less relevant content

**Example responses by threshold:**

| Threshold | Similarity | Result                                  |
| --------- | ---------- | --------------------------------------- |
| 0.4       | 85%        | ✅ Shows content + "Relevance: 85%"     |
| 0.4       | 35%        | ❌ "No documentation found (35% < 40%)" |
| 0.3       | 35%        | ✅ Shows content + "Relevance: 35%"     |

**When to adjust:**

- **Too many "No documentation found"** → Lower threshold (0.3)
- **Getting irrelevant results** → Raise threshold (0.5)

---

## 📚 Adding Runbooks

### Method 1: Upload via UI (Recommended) ✨

1. **Open Streamlit UI** at http://localhost:8501
2. **Click "📚 Manage Runbooks"** in the sidebar
3. **Drag & drop** your `.md` or `.txt` file (max 2MB)
4. **Click "💾 Upload"**
5. **Wait 10-15 seconds** - Auto-indexing happens in background!

✅ **Fully Automatic:**

- ✅ Upload → Auto-indexed into vector database
- ✅ Delete → Auto-removed from vector database
- ✅ No manual commands needed!

**Features:**

- 📗 Uploaded files stored in persistent volume (`/runbooks-uploads`)
- 🗑️ Delete button for uploaded runbooks (samples are protected)
- 📄 View full runbook content by clicking source citations
- 🔒 2MB file size limit enforced (client & server)
- ✅ UTF-8 validation ensures text-only content

### Method 2: Manual File Drop

1. **Create runbook** in `runbooks/` directory:

   ````bash
   cat > runbooks/my-troubleshooting.md << 'EOF'
   # My Troubleshooting Guide

   ## Problem Description

   ### Symptoms
   - Issue observable by users

   ### Diagnosis
   ```bash
   # Commands to investigate
   ```

   ### Solution

   Step-by-step resolution
   EOF
   ````

2. **Re-index**:

```bash
podman-compose restart runbook-indexer
podman logs doclocalai-runbook-indexer
```

3. **Verify indexing**:

```bash
podman exec doclocalai-db psql -U doclocalai -d doclocalai -c \
  "SELECT source_doc, COUNT(*) FROM runbook_chunks GROUP BY source_doc;"
```

### Storage Architecture

| Directory           | Type            | Purpose         | Deletable via UI |
| ------------------- | --------------- | --------------- | ---------------- |
| `/runbooks`         | Read-only mount | Sample runbooks | ❌ Protected     |
| `/runbooks-uploads` | Named volume    | User uploads    | ✅ Yes           |

**OpenShift Ready:**

- Sample runbooks → ConfigMap
- User uploads → PersistentVolumeClaim (PVC)

---

## 🧪 Testing

Run the complete test walkthrough:

```bash
# See USE_CASE.md for step-by-step testing guide
```

---

**Quick validation:**

1. ✅ UI loads at http://localhost:8501
2. ✅ Ask: "How do I troubleshoot pod crashes?"
3. ✅ Response includes source citation and relevance percentage
4. ✅ Click **📄 source button** to view full runbook (appears automatically)
5. ✅ Ask unrelated question: "How to cook pasta?" → See "No documentation found"
6. ✅ Session appears in sidebar
7. ✅ Delete single session with confirmation
8. ✅ **Clear All** sessions with safety confirmation
9. ✅ Upload runbook via "📚 Manage Runbooks" → auto-indexed in 10-15 seconds
10. ✅ Delete uploaded runbook → auto-removed from database
11. ✅ File uploader resets after successful upload
12. ✅ Test RAW mode (only sources) vs SYNTHESIS mode (explained answers)

---

## 🔒 Security Features

✅ **Connection Pooling** - Prevents connection exhaustion
✅ **Input Validation** - UUID format, length constraints
✅ **SQL Injection Protection** - Parameterized queries
✅ **Rate Limiting** - 60 req/min per IP
✅ **CORS Protection** - Whitelist origins
✅ **Error Handling** - Proper exceptions with rollback
✅ **Environment Secrets** - No hardcoded credentials

---

## 🎁 What's Included

- ✅ Full-stack RAG application with intelligent relevance detection
- ✅ **Adaptive hallucination prevention** (RAG strategy auto-switching)
- ✅ **Similarity threshold** - detects when no relevant docs exist
- ✅ **Relevance scoring** - shows % match on every response
- ✅ Multi-session chat with persistence
- ✅ **Delete single or all sessions** with confirmation dialogs
- ✅ **Auto-refresh UI** - buttons appear without page reload
- ✅ Source citations on every answer
- ✅ Inline runbook viewer (click citations)
- ✅ **UI-based runbook upload** with auto-indexing (10-15 seconds)
- ✅ **Auto-reset uploader** - clears after successful upload
- ✅ **Automatic cleanup** - deleted files removed from vector DB
- ✅ **Generic & customizable** - works for any domain (configurable title)
- ✅ Secure backend with connection pooling
- ✅ Sample OpenShift runbooks included
- ✅ Vector search with pgvector (cosine similarity)
- ✅ Local LLM with Ollama (privacy-first)
- ✅ Persistent storage (named volumes)
- ✅ Containerized with Podman/Docker Compose
- ✅ Comprehensive documentation
- ✅ OpenShift deployment ready, with OpenShift AI model serving (Qwen 2.5 1.5B + BGE-Small-EN-v1.5)

---

## 📝 Credentials (Local Development)

- **PostgreSQL**: `doclocalai` / `localdevpassword` / DB `doclocalai`
- **Ollama**: No authentication required (local only)

---

## 🚀 Next Steps

1. **Try it out** - Ask OpenShift questions
2. **Add runbooks** - Drop `.md` files in `runbooks/`
3. **Upgrade model** - Install 3B for better synthesis
4. **Customize** - Adjust RAG strategy, temperature, etc.
5. **Read docs** - See ARCHITECTURE.md and [RAG_GUIDE.md](./RAG_GUIDE.md) for the retrieval pipeline deep-dive

---

## 📄 License

MIT License - See LICENSE file for details

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

---

## ⭐ Star History

If you find this project useful, please consider giving it a star!
