# DocLocalAI - Complete Use Case Walkthrough

## 🎯 Goal

Demonstrate that DocLocalAI's RAG system works end-to-end:

1. ✅ Runbooks are indexed in the database
2. ✅ User asks a question via UI
3. ✅ System retrieves relevant runbook chunks
4. ✅ AI uses runbook context to answer
5. ✅ Answer includes specific troubleshooting steps from runbooks

---

## Step 1: Verify Services Are Running

```bash
podman ps --format "table {{.Names}}\t{{.Status}}"
```

**Expected Output:**

```
NAMES           STATUS
DocLocalAI-db      Up X minutes (healthy)
DocLocalAI-ollama  Up X minutes (healthy)
DocLocalAI-api     Up X minutes
DocLocalAI-ui      Up X minutes
```

✅ **All 4 services should be running**

---

## Step 2: Verify Runbooks Are Indexed in Database

Check how many runbook chunks are stored:

```bash
podman exec DocLocalAI-db psql -U DocLocalAI -d DocLocalAI -c \
  "SELECT COUNT(*) as total_chunks FROM runbook_chunks;"
```

**Expected Output:**

```
 total_chunks
--------------
           25
```

See which runbooks are indexed:

```bash
podman exec DocLocalAI-db psql -U DocLocalAI -d DocLocalAI -c \
  "SELECT source_doc, COUNT(*) as chunks FROM runbook_chunks GROUP BY source_doc ORDER BY source_doc;"
```

**Expected Output:**

```
            source_doc            | chunks
----------------------------------+--------
 openshift-networking.md          |     11
 openshift-pod-troubleshooting.md |     10
 README.md                        |      4
```

✅ **Should show 25 total chunks from 3 runbooks**

---

## Step 3: Preview Runbook Content in Database

Let's see what kind of content is indexed:

```bash
podman exec DocLocalAI-db psql -U DocLocalAI -d DocLocalAI -c \
  "SELECT source_doc, substring(content, 1, 150) as preview FROM runbook_chunks WHERE source_doc = 'openshift-pod-troubleshooting.md' LIMIT 3;"
```

**Expected Output:**

```
            source_doc            |                                     preview
----------------------------------+-----------------------------------------------------------------------------------
 openshift-pod-troubleshooting.md | # OpenShift Pod Troubleshooting Guide
                                  |
                                  | ## Pod CrashLoopBackOff
                                  |
                                  | ### Symptoms
                                  | - Pod status shows CrashLoopBackOff
 openshift-pod-troubleshooting.md | Container repeatedly restarts
                                  | - Application logs show errors during startup
                                  |
                                  | ### Common Causes
                                  | 1. **Application Error**: The...
 openshift-pod-troubleshooting.md | \`\`\`bash
                                  | # Check pod status and events
                                  | oc describe pod <pod-name>
                                  |
                                  | # View container logs
                                  | oc logs <pod-name> --previous...
```

✅ **You should see troubleshooting content with commands and solutions**

---

## Step 4: Test Vector Search (Simulating What Happens During Chat)

Let's manually test if the vector search retrieves relevant content.

First, check if embeddings exist:

```bash
podman exec DocLocalAI-db psql -U DocLocalAI -d DocLocalAI -c \
  "SELECT source_doc, chunk_index, (embedding IS NOT NULL) as has_embedding FROM runbook_chunks LIMIT 5;"
```

**Expected Output:**

```
            source_doc            | chunk_index | has_embedding
----------------------------------+-------------+---------------
 README.md                        |           0 | t
 README.md                        |           1 | t
 README.md                        |           2 | t
 README.md                        |           3 | t
 openshift-networking.md          |           0 | t
```

✅ **All rows should have `has_embedding = t` (true)**

---

## Step 5: Open the UI

Open your browser and navigate to:

```
http://localhost:8501
```

You should see:

- **Title**: "DocLocalAI — OpenShift Incident & Runbook Assistant"
- **Sidebar**: Shows "Discussions" and "Saved Sessions"
- **Chat Input**: "Ask an OpenShift question..."

✅ **UI should load successfully**

---

## Step 6: Ask a Question That Matches Runbook Content

Type this question in the chat input:

```
My pod is in CrashLoopBackOff state. How do I troubleshoot it?
```

---

## Step 7: Observe the RAG System in Action

**What happens behind the scenes:**

1. **UI sends question** to API: `POST /api/chat`
2. **API generates embedding** of your question using `nomic-embed-text`
3. **Vector search** finds the 3 most relevant chunks from `runbook_chunks` table
4. **API builds context** from those chunks
5. **LLM receives** both your question AND the runbook context
6. **AI generates answer** using the runbook knowledge
7. **Response displayed** in UI

---

## Step 8: Verify Answer Quality

**Expected Answer Characteristics:**

The AI should respond with specific details from the runbook, such as:

✅ **Mentions CrashLoopBackOff symptoms**

- Pod status shows CrashLoopBackOff
- Container repeatedly restarts

✅ **Provides diagnostic commands**

```bash
oc describe pod <pod-name>
oc logs <pod-name> --previous
oc get events --field-selector involvedObject.name=<pod-name>
```

✅ **Lists common causes**

- Application Error
- Missing Dependencies
- Resource Limits (OOMKilled)
- Failed Health Checks

✅ **Suggests solutions**

- Review application logs
- Check environment variables
- Verify ConfigMaps and Secrets
- Increase memory/CPU limits
- Adjust health check timing

**At the bottom of the response, you'll see:**

```
Served by: qwen2.5:0.5b
```

---

## Step 9: Verify RAG Context Was Used

To confirm the system actually used the runbooks, ask a question about content NOT in the runbooks:

```
What is the capital of France?
```

The AI should give a generic answer WITHOUT specific troubleshooting commands, because there's no relevant runbook context.

Then ask another question that IS in the runbooks:

```
How do I fix ImagePullBackOff errors?
```

The AI should again provide specific troubleshooting steps from the runbook, including:

- Checking image name and pull policy
- Creating image pull secrets
- Verifying registry connectivity

✅ **Answers should be more detailed for runbook-covered topics**

---

## Step 10: Check Chat Session Was Saved

Your conversation should be persisted in PostgreSQL:

```bash
podman exec DocLocalAI-db psql -U DocLocalAI -d DocLocalAI -c \
  "SELECT title, created_at FROM chat_sessions ORDER BY created_at DESC LIMIT 5;"
```

**Expected Output:**

```
                           title                            |          created_at
------------------------------------------------------------+-------------------------------
 My pod is in CrashLoopBackOff state. How do I troublesh... | 2026-11-18 16:30:15.123+00
```

Check the messages:

```bash
podman exec DocLocalAI-db psql -U DocLocalAI -d DocLocalAI -c \
  "SELECT role, substring(content, 1, 80) as message_preview FROM chat_messages ORDER BY created_at DESC LIMIT 5;"
```

**Expected Output:**

```
   role    |                              message_preview
-----------+----------------------------------------------------------------------------
 assistant | To troubleshoot a pod in CrashLoopBackOff state, follow these steps:...
 user      | My pod is in CrashLoopBackOff state. How do I troubleshoot it?
```

✅ **Your conversation should be saved**

---

## Step 11: Test Session Continuity

In the UI sidebar, you should see your saved session. Click on it.

The conversation should reload, proving that:

- Sessions are persisted
- Message history is retrieved
- UI state management works

✅ **Previous conversation should reload**

---

## Step 12: Verify API Endpoint Directly (Optional)

Test the API directly with curl:

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-session-001",
    "message": "What causes pod pending state?"
  }' | jq .
```

**Expected Output:**

```json
{
  "reply": "A pod remains in Pending state when it cannot be scheduled...",
  "model_used": "qwen2.5:0.5b"
}
```

The reply should include specific causes from the runbook:

- Insufficient Resources
- Node Selector Mismatch
- Taints and Tolerations
- PVC Issues

✅ **API should return structured JSON with AI-generated answer**

---

## 🎉 Success Criteria

If all steps pass, you have confirmed:

✅ **Database Integration**

- 25 runbook chunks stored in PostgreSQL
- Embeddings generated for all chunks
- Vector search capability via pgvector

✅ **RAG System**

- Questions trigger vector search
- Relevant runbook chunks retrieved
- Context included in LLM prompt

✅ **AI Quality**

- Answers include specific runbook content
- Commands and solutions from indexed docs
- Better answers for covered topics

✅ **Persistence**

- Chat sessions saved
- Messages stored
- Session retrieval works

✅ **End-to-End Flow**

- UI → API → Vector DB → LLM → Response
- All components communicating correctly

---

## 📊 Expected Behavior Summary

| Question Type           | Expected Behavior                                         |
| ----------------------- | --------------------------------------------------------- |
| **Covered in runbooks** | Detailed answer with specific commands, causes, solutions |
| **Not in runbooks**     | Generic answer without specific troubleshooting steps     |
| **Follow-up question**  | Uses conversation history + runbook context               |

---

## 🐛 If Something Doesn't Work

### No runbook chunks in database?

```bash
podman compose restart runbook-indexer
podman logs DocLocalAI-runbook-indexer
```

### Generic answers only?

```bash
# Check if embeddings exist
podman exec DocLocalAI-db psql -U DocLocalAI -d DocLocalAI -c \
  "SELECT COUNT(*) FROM runbook_chunks WHERE embedding IS NOT NULL;"
```

### UI shows "Waiting for API"?

```bash
curl http://localhost:8000/health
podman logs DocLocalAI-api
```

---

## 💡 Next Steps

1. **Add your own runbooks** to `runbooks/` directory
2. **Re-index**: `podman compose restart runbook-indexer`
3. **Ask questions** about your custom content
4. **Verify** the system uses your new runbooks

This proves your DocLocalAI RAG system is fully operational! 🚀
