# Qwen Model Deployment - Troubleshooting Summary

---

## 📋 Issues & Resolutions Index

| #   | Issue                                                       | Root Cause                                                                                      | Resolution                                                                                             |
| --- | ----------------------------------------------------------- | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| 1   | Pod `CrashLoopBackOff` on GPU model _(OLD)_                 | GPU memory full — another model (llama-32-3b) was using it                                      | Removed the unused llama-32-3b model                                                                   |
| 2   | No external access to model endpoint                        | No route created                                                                                | `oc expose service <svc>`                                                                              |
| 3   | Route returns "Application is not available"                | HTTP route pointed at an HTTPS (vLLM) service                                                   | Recreated as a `reencrypt` TLS route                                                                   |
| 4   | Gateway route stuck, `NotAllowedByListeners`                | Namespace missing from the Gateway's allowed-namespace list                                     | Added the namespace to the Gateway's `allowedRoutes` selector                                          |
| 5   | Dashboard warning: AuthPolicy CRD not available             | Token auth enabled, but the Red Hat Connectivity Link operator isn't installed                  | Ignore (dev/test), install the operator, or redeploy without token auth                                |
| 6   | InferenceService stuck, `READY=Unknown` _(OLD)_             | `Serverless` deployment mode used, but Knative not installed                                    | Switched to `RawDeployment` mode                                                                       |
| 7   | No runtime found for PyTorch model _(OLD)_                  | Missing `ServingRuntime` for vLLM                                                               | Created and deployed the vLLM `ServingRuntime` before the model                                        |
| 8   | Nomic-embed fails to load on vLLM _(OLD)_                   | vLLM/storage-initializer can't fetch nomic-embed's custom config files                          | Moved to CPU-based or external embeddings                                                              |
| 9   | GPU can't fit both Qwen and Nomic-Embed _(OLD)_             | Both models request exclusive GPU access                                                        | Lowered Qwen's `gpu-memory-utilization` 90%→60% to free headroom (embed model still failed separately) |
| 10  | Nomic-embed still fails under vLLM embedding mode _(OLD)_   | Nomic-embed's custom architecture is unsupported by vLLM                                        | Switched to BGE-Small-EN-v1.5 (officially supported, runs on CPU)                                      |
| 11  | Postgres pod `CrashLoopBackOff` on init                     | PVC mounted directly on the data dir; a stray `lost+found` dir blocks `initdb`                  | Point `PGDATA` at a subdirectory of the mount                                                          |
| 12  | Backend pod stuck `Pending`                                 | Wrong `DATABASE_URL` hostname, and PVC requested `ReadWriteMany` (unsupported by AWS EBS)       | Fixed the hostname; changed the PVC to `ReadWriteOnce`                                                 |
| 13  | Backend pod stuck `ContainerCreating`                       | Referenced runbooks ConfigMap didn't exist                                                      | Made the mount optional, or created the ConfigMap from `runbooks/`                                     |
| 14  | Backend returns 503, SSL `CERTIFICATE_VERIFY_FAILED`        | Python `httpx` doesn't trust OpenShift's service-serving CA                                     | Disabled SSL verification in code (`httpx.Client(verify=False)`)                                       |
| 15  | `Illegal header value b'Bearer '`                           | `LLM_API_TOKEN` secret was an empty string                                                      | Set the token to a non-empty placeholder (`"not-needed"`)                                              |
| 16  | Chat returns 500, transaction aborted                       | `runbook_chunks.embedding` was `vector(768)`, but BGE returns 384-dim vectors                   | Recreated the column as `vector(384)`                                                                  |
| 17  | Runbook upload "succeeds" but 0 chunks indexed              | Indexer Job had no `command:` override, so it ran the default `uvicorn` CMD instead of indexing | Added `command: ["python3", ".../index_runbooks.py"]` to the Job                                       |
| 18  | Indexer job crashes, script file not found                  | Image built from `app/backend/` couldn't `COPY` the sibling `scripts/` directory                | Built the image from the repo root instead                                                             |
| 19  | Indexer chunks all fail with SSL `Connection error`         | Indexer script's OpenAI client was missing the same SSL fix as the backend                      | Added `httpx.Client(verify=False)` to `scripts/index_runbooks.py`                                      |
| 20  | Indexer INSERT fails: `column "chunk_index" does not exist` | Table schema was missing a column the script required                                           | `ALTER TABLE runbook_chunks ADD COLUMN chunk_index INTEGER`                                            |
| 21  | Production: `password authentication failed for user "doclocalai"` | `deploy-app.sh` regenerated the DB secret on every run; Postgres only applies `POSTGRES_PASSWORD` on first `initdb`, so it kept the old password | Synced Postgres's role password to the secret via `ALTER ROLE`; script now deletes the old secret before regenerating |
| 22  | Indexer INSERT fails: `column "content_hash" does not exist` | `openshift/application/db-init-configmap.yaml` schema had drifted from `app/db/init.sql` (missing `content_hash`/`content_tsv`/FTS); `embedding` also hardcoded `vector(768)` vs BGE's actual 384 dims | Synced the ConfigMap to the local schema with `vector(384)`; recreated the (empty) live table to match |
| 23  | Upload/search broken after fresh redeploy - embeddings fail with generic `Connection error` | `template-secrets.yaml` hardcoded `LLM_API_TOKEN: ""`; empty token → `Authorization: Bearer ` (trailing space) → httpx rejects it as an illegal header before the request is sent | Set `LLM_API_TOKEN: "not-needed"` in the template (not just the live secret); removed the dead `sed` line that targeted the old placeholder |

---

## ⚠️ IMPORTANT: Two Different Deployment Approaches

This troubleshooting guide contains issues from **TWO different deployment methods**:

### 🔴 OLD Approach (Most issues below)

**API**: `InferenceService` (v1beta1) + `ServingRuntime`

**How it worked**:

```yaml
# Step 1: Create ServingRuntime (define how to run vLLM)
kind: ServingRuntime
spec:
  containers:
    - image: quay.io/opendatahub/vllm:stable
      args:
        - --gpu-memory-utilization
        - "0.60"
        # ... manual vLLM configuration

# Step 2: Create InferenceService (reference the runtime)
kind: InferenceService
spec:
  predictor:
    model:
      runtime: vllm-runtime-shared  # Points to ServingRuntime
      storageUri: hf://...
```

**Issues**:

- ❌ Required manual ServingRuntime YAML files
- ❌ Manual vLLM parameter configuration
- ❌ UI showed "Unknown" deployment resource
- ❌ No hardware profile integration

**Status**: ⚠️ **DEPRECATED** - Archived in `archive-openshift/`

---

### 🟢 NEW Approach (Current - Nov 2026)

**API**: `LLMInferenceService` (v1alpha2) with built-in **llm-d** runtime

**How it works**:

```yaml
# Single file - NO ServingRuntime needed!
kind: LLMInferenceService
metadata:
  annotations:
    opendatahub.io/connections: "qwen"
    opendatahub.io/hardware-profile-name: "gpu-profile"
spec:
  model:
    uri: hf://Qwen/Qwen2.5-1.5B-Instruct
  # llm-d automatically configures vLLM, GPU, routing, etc.
```

**Benefits**:

- ✅ No ServingRuntime files needed
- ✅ llm-d auto-configures everything
- ✅ Full UI integration
- ✅ Hardware profile support
- ✅ Gateway-based routing

**Files**: `qwen-llm-service.yaml`, `bge-llm-service.yaml`, `deploy-llm.sh`

---

### 📌 How to Read This Guide

Issues marked with **[OLD - InferenceService]** are specific to the deprecated approach.

If you're using the **NEW LLMInferenceService** approach:

- Skip issues marked [OLD - InferenceService]
- Focus on general OpenShift/networking issues
- Refer to updated README.md for current deployment

---

## Initial Problem **[OLD - InferenceService]**

❌ **Deployment error**: "Deployment does not have minimum available"

---

## Step-by-Step Troubleshooting

### Step 1: Check Pod Status

**Command**:

```bash
oc get pods
```

**Result**:

```
qwen-15b-kserve-77bf5b4bf-x6qb7   0/1   CrashLoopBackOff   1 (19s ago)   5m15s
```

**Finding**: Pod is crashing repeatedly

---

### Step 2: Check Pod Logs

**Command**:

```bash
oc logs qwen-15b-kserve-77bf5b4bf-x6qb7
```

**Finding**:

```
ValueError: Free memory on device cuda:0 (0.07/22.03 GiB) is less than
desired GPU memory utilization (0.92, 20.27 GiB)
```

**Issue**: GPU has only 0.07GB free but needs 20GB

---

### Step 3: Find What's Using the GPU

**Command**:

```bash
oc get pods -A -o json | jq -r '.items[] | select(.spec.containers[].resources.limits."nvidia.com/gpu" != null) | "\(.metadata.namespace)/\(.metadata.name)"'
```

**Result**:

```
my-first-model/llama-32-3b-instruct-predictor-d7c8f8d9-ncjzk
```

**Finding**: Another model (llama-32-3b) is using all the GPU memory

---

### Step 4: Free Up GPU Memory

**Action**: User removed the unused llama-32-3b model

**Why**: The GPU can only run one model at a time with the current memory allocation

**Result**: Pod changed from `CrashLoopBackOff` to `Running 1/1`

---

### Step 5: Create Route for Access

**Command**:

```bash
oc get route
```

**Result**: No route found

**Action**:

```bash
oc expose service qwen-15b-kserve-workload-svc
```

**Why**: Need external access to the model endpoint

---

### Step 6: Test Endpoint

**Command**:

```bash
curl https://qwen-15b-kserve-workload-svc-doclocal-ai-models.apps.ocp.adress.cluster.com/v1/chat/completions
```

**Result**: "Application is not available"

**Finding**: vLLM server uses HTTPS/TLS but route was configured for plain HTTP

---

### Step 7: Fix TLS Route Configuration

**Action**:

```bash
# Delete HTTP route
oc delete route qwen-15b-kserve-workload-svc

# Create TLS reencrypt route
oc create route reencrypt qwen-15b --service=qwen-15b-kserve-workload-svc --port=8000
```

**Why**: vLLM serves on HTTPS, so the route needs to handle TLS (reencrypt mode)

**Result**: ✅ Model endpoint now responds correctly

---

## Final Test

**Command**:

```bash
curl -X POST "https://qwen-15b-doclocal-ai-models.apps.ocp.adress.cluster.com/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen-15b", "messages": [{"role": "user", "content": "Say hello"}]}' -k
```

**Response**:

```json
{
  "choices": [
    {
      "message": {
        "content": "Hello! How can I assist you today?"
      }
    }
  ]
}
```

✅ **SUCCESS - Model is working!**

---

## Summary

| Issue                     | Root Cause                              | Solution                                 |
| ------------------------- | --------------------------------------- | ---------------------------------------- |
| Pod CrashLoopBackOff      | GPU memory full (llama model using it)  | Removed unused llama-32-3b model         |
| No external access        | No route created                        | Created route with `oc expose`           |
| Route not responding      | HTTP route for HTTPS service            | Recreated as reencrypt TLS route         |
| Gateway route not allowed | Namespace not in gateway's allowed list | Added namespace to gateway configuration |

---

---

## Issue 4: Gateway Route Not Allowed (After Redeployment)

**Symptom**: HTTPRoute stuck on "Router / scheduler" with error:

```
"NotAllowedByListeners" - namespace "doclocal-ai-models" is not allowed by the parent
```

**What Happened**: After redeploying without token auth, model uses HTTPRoute and Gateway, but namespace wasn't in gateway's allowed list.

---

### Step 1: Check HTTPRoute Status

**Command**:

```bash
oc describe httproute qwen-15b-kserve-route -n doclocal-ai-models
```

**Finding**:

```
Message: hostnames matched parent hostname "inference-gateway.apps.ocp.t97wb...",
but namespace "doclocal-ai-models" is not allowed by the parent
```

**Issue**: Gateway only allows specific namespaces (openshift-ingress, redhat-ods-applications, my-first-model)

---

### Step 2: Check Gateway Configuration

**Command**:

```bash
oc get gateway openshift-ai-inference -n openshift-ingress -o yaml | grep -A 10 "allowedRoutes"
```

**Result**:

```yaml
allowedRoutes:
  namespaces:
    from: Selector
    selector:
      matchExpressions:
        - key: kubernetes.io/metadata.name
          operator: In
          values:
            - openshift-ingress
            - redhat-ods-applications
            - my-first-model
```

**Finding**: `doclocal-ai-models` namespace is missing from allowed list

---

### Step 3: Add Namespace to Gateway

**Command**:

```bash
oc edit gateway openshift-ai-inference -n openshift-ingress
```

**Change**: Add your namespace to the values list:

```yaml
values:
  - openshift-ingress
  - redhat-ods-applications
  - my-first-model
  - doclocal-ai-models # ← ADD THIS
```

**Why**: Gateway uses a namespace selector to control which namespaces can create routes through it

**Result**: ✅ HTTPRoute becomes "Accepted" within 10-30 seconds

---

### Step 4: Verify HTTPRoute is Accepted

**Command**:

```bash
oc get httproute qwen-15b-kserve-route -n doclocal-ai-models -o jsonpath='{.status.parents[0].conditions[?(@.type=="Accepted")]}'
```

**Success**:

```json
{
  "status": "True",
  "reason": "Accepted",
  "message": "Route was valid"
}
```

---

## Alternative Solution: Use Internal Service (Recommended for Cross-Namespace)

**If your backend runs in another namespace in OpenShift**, skip the gateway and use the internal service DNS:

**Service URL**:

```
http://qwen-15b-kserve-workload-svc.doclocal-ai-models.svc.cluster.local:8000/v1
```

**Benefits**:

- ✅ No gateway configuration needed
- ✅ Faster (no extra hops)
- ✅ More secure (stays inside cluster)
- ✅ No external route needed

**Use in DocLocalAI config**:

```yaml
environment:
  LLM_ENDPOINT_URL: http://qwen-15b-kserve-workload-svc.doclocal-ai-models.svc.cluster.local:8000/v1
  LLM_MODEL_NAME: qwen-15b
```

---

## Additional Warning (Non-blocking)

### Warning: AuthPolicy CRD not available

**Message in Dashboard**:

```
AuthPolicy CRD is not available, please install Red Hat Connectivity Link: precondition not met
```

**What it means**:

- You enabled "Token authentication: Yes" during deployment
- OpenShift AI wants to enforce token auth using AuthPolicy CRD
- The Red Hat Connectivity Link operator (which provides AuthPolicy) is not installed

**Impact**:

- ⚠️ Warning shows in dashboard (cosmetic issue)
- ✅ Model works perfectly WITHOUT authentication
- ❌ Token authentication is NOT enforced (anyone can access)

**Solutions**:

| Option                        | When to Use                       | How                                                       |
| ----------------------------- | --------------------------------- | --------------------------------------------------------- |
| **Ignore it**                 | Dev/testing, internal use only    | Do nothing - model works fine                             |
| **Install Connectivity Link** | Production with token auth needed | Install operator via OperatorHub (requires cluster-admin) |
| **Redeploy without auth**     | Remove the warning completely     | Redeploy model with "Token authentication: No"            |

**Current Status**: Model is accessible without token ✅

**Test without token**:

```bash
curl -X POST "https://qwen-15b-doclocal-ai-models.apps.ocp.adress.cluster.com/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen-15b", "messages": [{"role": "user", "content": "test"}]}' -k
```

---

## Final Endpoints

### For Internal Access (Backend in OpenShift - Recommended)

**Service URL** (cross-namespace):

```
http://qwen-15b-kserve-workload-svc.doclocal-ai-models.svc.cluster.local:8000/v1
```

**Service URL** (same namespace):

```
http://qwen-15b-kserve-workload-svc:8000/v1
```

### For External Access (Testing from outside OpenShift)

**Direct Route**:

```
https://qwen-15b-doclocal-ai-models.apps.ocp.adress.cluster.com
```

**Gateway Route** (after adding namespace to gateway):

```
https://inference-gateway.apps.ocp.adress.cluster.com
```

_(Requires header: `X-Gateway-Model-Name: qwen-15b`)_

---

**API Path**: `/v1/chat/completions`  
**Model Name**: `qwen-15b`  
**Authentication**: None (open access)

---

## Issue 5: InferenceService Stuck - Serverless Mode Not Available **[OLD - InferenceService]**

**Symptom**: InferenceService shows `READY = Unknown`, no pods created

```
Warning: ServerlessModeRejected - It is not possible to use Knative deployment mode when Knative Services are not available
```

**Root Cause**: InferenceService configured with `Serverless` mode but Knative not installed on cluster

**Solution**: Change to `RawDeployment` mode

```yaml
# In qwen-inferenceservice.yaml
metadata:
  annotations:
    serving.kserve.io/deploymentMode: RawDeployment # Changed from: Serverless
```

**Fix**:

```bash
oc delete inferenceservice qwen-15b -n doclocal-ai-models
oc apply -f qwen-inferenceservice.yaml
```

---

## Issue 6: No Runtime Found for PyTorch Models **[OLD - InferenceService]**

**Symptom**: Model fails to load

```
Warning: InternalError - no runtime found to support predictor with model type: {pytorch <nil>}
Status: FailedToLoad - No runtime found to support specified framework/version
```

**Root Cause**: Missing ServingRuntime - OpenShift AI needs a runtime to know how to serve PyTorch models

**Solution**: Create vLLM ServingRuntime

**Created**: `vllm-servingruntime.yaml`

**Fix**:

```bash
# Deploy runtime FIRST
oc apply -f vllm-servingruntime.yaml

# Verify runtime exists
oc get servingruntimes -n doclocal-ai-models

# Then deploy model
oc apply -f qwen-inferenceservice.yaml
```

**Verify Success**:

```bash
# Should show READY = True
oc get inferenceservice qwen-15b -n doclocal-ai-models

# Should show 2/2 Running
oc get pods -n doclocal-ai-models

# Test endpoint
oc run test-curl --rm -i --restart=Never --image=curlimages/curl:latest \
  -n doclocal-ai-models -- \
  curl -s http://qwen-15b-predictor.doclocal-ai-models.svc.cluster.local:8080/v1/models
```

**Updated deployment order**:

1. Create namespace + secrets
2. Deploy ServingRuntime (`vllm-servingruntime.yaml`)
3. Deploy InferenceService (`qwen-inferenceservice.yaml`)

✅ The `deploy.sh` script now handles this automatically

---

## Issue 7: Embedding Models with vLLM Runtime **[OLD - InferenceService]**

**Symptom**: nomic-embed-text fails to start with vLLM runtime

```
OSError: We couldn't connect to 'https://huggingface.co' to load this file
RuntimeError: Failed to load the model config
```

**Root Cause**:

- vLLM is designed for **text generation LLMs**, not embedding models
- Nomic-embed requires custom code and additional dependencies not downloaded by storage-initializer
- Even with `--trust-remote-code`, vLLM tries to download additional files at runtime

**GPU Limitation**:

- With only 1 GPU, you can't run both Qwen (generation) and nomic-embed (embeddings) simultaneously
- Qwen needs ~20GB GPU memory, leaving no room for embedding model

**Solutions**:

### Option 1: Use CPU-based Embeddings (Recommended)

Deploy embeddings on CPU (no GPU needed) using a different approach:

- Use text-embeddings-inference runtime (Hugging Face)
- Or deploy Ollama separately for embeddings (matches your local setup)

### Option 2: Share Embeddings with Generation Model

Some modern LLMs can do both generation and embeddings:

- Use Qwen for both tasks (if it supports embeddings)
- Or switch to a multi-modal model

### Option 3: Use External Embeddings Service

Point your backend to an external embeddings API:

- OpenAI embeddings
- Cohere embeddings
- Cloud-hosted embedding service

**Current Setup**:

- ✅ Qwen 2.5 1.5B for text generation (GPU)
- ❌ Nomic-embed not supported with vLLM runtime

**For local dev**: Continue using Ollama with nomic-embed as in docker-compose.yml

---

## Issue 8: GPU Sharing Test - Qwen + Nomic-Embed **[OLD - InferenceService]**

**Goal**: Fit both Qwen (generation) and Nomic-Embed (embeddings) on the same GPU

### Test: Reduce Qwen GPU Usage

**Changes Made**:

```yaml
# vllm-runtime-generation.yaml
args:
  - --gpu-memory-utilization
  - "0.60" # Down from 0.90
  - --max-model-len
  - "3072" # Down from 4096
```

**Results**:

```
Before optimization:
├─ GPU Usage: 19.3 GB (84% of 23 GB GPU)
├─ Context: 4096 tokens
└─ Free: 3.7 GB

After optimization:
├─ GPU Usage: 12.5 GB (54% of 23 GB GPU)  ✅ -6.8 GB
├─ Context: 3072 tokens                   ✅ Still good for RAG
└─ Free: 10.5 GB                          ✅ Enough for embeddings
```

**Trade-offs**:

- ✅ 3072 tokens = 6-8 conversation exchanges (good for chat)
- ✅ Can handle 2-3 concurrent requests
- ⚠️ Fewer concurrent requests than 90% mode (3-5 users)

**Verdict**: ✅ **Qwen GPU optimization successful**

---

### Test: Deploy Nomic-Embed with Shared Runtime

**Attempt**: Deploy nomic-embed-text-v1.5 with same vLLM runtime

**Result**: ❌ **FAILED - Same vLLM incompatibility**

**Error**:

```
OSError: We couldn't connect to 'https://huggingface.co' to load this file
Could not locate the configuration_hf_nomic_bert.py inside nomic-ai/nomic-bert-2048
```

**Root Cause**: Even with GPU sharing optimization:

- vLLM is designed for **generative LLMs** only
- Embedding models need different runtime (text-embeddings-inference, Ollama, etc.)
- Storage-initializer doesn't download custom config files needed by nomic-embed

**Verdict**: ❌ **vLLM cannot serve embedding models**

---

## Solution: Separate Runtimes for Generation vs Embeddings

### Architecture for OpenShift

**Recommended Setup**:

```
┌─────────────────────────────────┐
│  Qwen 2.5 1.5B (vLLM/GPU)       │  Text generation
│  - 12.5 GB GPU                  │  - Chat completions
│  - 3072 token context           │  - RAG synthesis
│  - 2-3 concurrent users         │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│  Nomic-Embed (Ollama/CPU)       │  Embeddings
│  - 2-4 GB RAM                   │  - Vector search
│  - CPU only                     │  - Document chunking
│  - Fast batch processing        │
└─────────────────────────────────┘
```

### Deployment Options

**Option 1: Hybrid (Recommended for now)**

- ✅ Qwen on OpenShift (GPU) - for production inference
- ✅ Ollama local (CPU/GPU) - for development embeddings
- Backend connects to both endpoints

**Option 2: Both on OpenShift**

- Deploy Qwen with vLLM runtime (GPU)
- Deploy Ollama separately for embeddings (CPU)
- Both in `doclocal-ai-models` namespace

**Option 3: All-in-One Ollama**

- Deploy Ollama on OpenShift with both models
- Simpler but less optimized than vLLM for generation
- Can use same approach as local docker-compose

---

## Final Configuration Files

**Created for GPU sharing test**:

- `vllm-runtime-generation.yaml` - Runtime with 60% GPU allocation
- `qwen-generation-service.yaml` - Optimized Qwen deployment
- `nomic-embed-inferenceservice-shared.yaml` - Failed test (kept for reference)
- `GPU-OPTIMIZATION.md` - Detailed analysis and calculations

**Currently deployed**:

- ✅ Qwen 2.5 1.5B with optimized GPU usage (12.5 GB)
- ❌ Nomic-Embed removed (vLLM incompatible)

**Next steps**: Deploy Ollama for embeddings separately

---

## Issue 9: vLLM Embedding Support Discovery **[OLD - InferenceService]**

**Initial Belief**: vLLM only works for generative LLMs, not embeddings (❌ WRONG!)

**Discovery**: vLLM DOES support embedding models with `--task embed` mode ✅

### Evidence

**vLLM Help Output**:

```bash
oc exec <qwen-pod> -- python -m vllm.entrypoints.openai.api_server --help | grep task

--task {auto,generate,embedding,embed,classify,score,reward}
```

**Official Documentation**:

- vLLM Pooling Models: https://docs.vllm.ai/en/latest/models/pooling_models.html
- Supported embedding models list includes BGE, Sentence Transformers, etc.

**Key Finding**: vLLM has **TWO modes**:

1. `--task generate` (or `auto`) → Text generation (Qwen)
2. `--task embed` → Embeddings (BGE, nomic-embed, etc.)

---

### Attempt 1: Nomic-Embed with vLLM Embedding Mode

**Configuration**:

```yaml
# vllm-runtime-embedding.yaml
args:
  - --task
  - embed # ← EMBEDDING MODE
  - --gpu-memory-utilization
  - "0.3"
```

**Model**: `hf://nomic-ai/nomic-embed-text-v1.5`

**Result**: ❌ **FAILED**

**Error** (same as before):

```
OSError: Could not locate the configuration_hf_nomic_bert.py
```

**Root Cause**:

- Nomic-embed uses **custom architecture** not fully supported by vLLM
- Requires special config files not downloaded by storage-initializer
- **This is a nomic-embed compatibility issue, NOT a vLLM limitation!**

---

### Solution: Switch to BGE-Small-EN-v1.5

**Why BGE instead of Nomic?**

| Aspect       | Nomic-Embed   | BGE-Small           |
| ------------ | ------------- | ------------------- |
| vLLM Support | ⚠️ Limited    | ✅ Full             |
| Size         | 548 MB        | 133 MB (4x smaller) |
| Dimensions   | 768           | 384                 |
| RAM          | ~3-4 GB       | ~2 GB               |
| Setup        | Custom config | Works immediately   |

**Research Source**:

- vLLM supported models: https://docs.vllm.ai/en/latest/models/pooling_models.html#supported-pooling-models
- BGE listed as officially supported ✅

---

### Attempt 2: BGE with vLLM Embedding Runtime

**Configuration**:

**Runtime** (`vllm-runtime-embedding.yaml`):

```yaml
apiVersion: serving.kserve.io/v1alpha1
kind: ServingRuntime
metadata:
  name: vllm-embedding
spec:
  containers:
    - name: kserve-container
      image: quay.io/opendatahub/vllm:stable
      args:
        - --model
        - /mnt/models
        - --task
        - embed # EMBEDDING MODE
        - --device
        - cpu # CPU-only (no GPU needed)
        - --trust-remote-code
```

**InferenceService** (`bge-embedding-service.yaml`):

```yaml
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: bge-vllm
spec:
  predictor:
    model:
      modelFormat:
        name: pytorch
      runtime: vllm-embedding
      storageUri: hf://BAAI/bge-small-en-v1.5
      resources:
        requests:
          cpu: "2"
          memory: 2Gi
        limits:
          cpu: "4"
          memory: 4Gi
          # No GPU - runs on CPU
```

**Deployment**:

```bash
oc apply -f vllm-runtime-embedding.yaml
oc apply -f bge-embedding-service.yaml
```

**Result**: ✅ **SUCCESS!**

---

### Verification

**Pod Status**:

```bash
oc get pods -n doclocal-ai-models
# bge-vllm-predictor-xxx   2/2   Running
```

**InferenceService**:

```bash
oc get inferenceservice bge-vllm -n doclocal-ai-models
# NAME       READY   URL
# bge-vllm   True    http://bge-vllm-predictor...
```

**Logs Confirm Embedding Mode**:

```
INFO: task='embed'
INFO: pooler_config=PoolerConfig(pooling_type='CLS', normalize=True)
INFO: Uvicorn running on http://0.0.0.0:8080
```

**Test Embedding**:

```bash
curl -X POST http://bge-vllm-predictor.doclocal-ai-models.svc.cluster.local:8080/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"input":"Hello world","model":"/mnt/models"}'

# Returns: 384-dimensional vector in OpenAI format ✅
{
  "object": "list",
  "data": [{
    "object": "embedding",
    "embedding": [0.0152, -0.0225, ...]
  }]
}
```

---

## Final Architecture **[OLD - InferenceService]**

### Deployed Models

```
┌─────────────────────────────────────┐
│  Qwen 2.5 1.5B (vLLM Generate)      │
│  Runtime: vllm-runtime-shared       │
│  - GPU: 12.5 GB (60% util)          │
│  - Context: 3072 tokens             │
│  - API: /v1/chat/completions        │
│  - OpenAI-compatible ✅             │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│  BGE-Small-EN (vLLM Embed)          │
│  Runtime: vllm-embedding            │
│  - CPU: 2-4 cores, 2-4 GB RAM       │
│  - Dims: 384                        │
│  - API: /v1/embeddings              │
│  - OpenAI-compatible ✅             │
└─────────────────────────────────────┘
```

**Key Benefits**:

- ✅ Same vLLM family for both models
- ✅ Both use OpenAI-compatible APIs
- ✅ Easier backend integration (single SDK)
- ✅ Qwen on GPU, embeddings on CPU
- ✅ Total GPU: 12.5 GB / 23 GB (54% used, 46% free)

---

## Resource Comparison

### CPU vs GPU for Embeddings

We tested both but chose **CPU**:

| Mode    | GPU Usage | Performance | Reason                               |
| ------- | --------- | ----------- | ------------------------------------ |
| **GPU** | +2-3 GB   | Faster      | ⚠️ Only 1 GPU, can't share with Qwen |
| **CPU** | 0 GB      | Good enough | ✅ Frees GPU for Qwen                |

**Why CPU?**:

- OpenShift has only 1 GPU
- Both models requesting `nvidia.com/gpu: "1"` = exclusive access
- Kubernetes doesn't share GPUs without MIG or time-slicing
- Embedding inference is fast enough on CPU

---

## Backend Integration

### Endpoints

**Qwen (Generation)**:

```
http://qwen-15b-predictor.doclocal-ai-models.svc.cluster.local:8080/v1/chat/completions
```

**BGE (Embeddings)**:

```
http://bge-vllm-predictor.doclocal-ai-models.svc.cluster.local:8080/v1/embeddings
```

### Python Example (OpenAI SDK)

```python
from openai import OpenAI

# Both use same client!
base_url_gen = "http://qwen-15b-predictor.doclocal-ai-models.svc.cluster.local:8080/v1"
base_url_embed = "http://bge-vllm-predictor.doclocal-ai-models.svc.cluster.local:8080/v1"

# Text generation
client_gen = OpenAI(base_url=base_url_gen, api_key="not-needed")
response = client_gen.chat.completions.create(
    model="/mnt/models",
    messages=[{"role": "user", "content": "Hello"}]
)

# Embeddings
client_embed = OpenAI(base_url=base_url_embed, api_key="not-needed")
response = client_embed.embeddings.create(
    model="/mnt/models",
    input="Hello world"
)
```

---

## Key Learnings

1. **vLLM DOES support embeddings** with `--task embed` ✅
   - Initial assumption was wrong!
   - Check `--help` and official docs before assuming limitations

2. **Model compatibility varies**:
   - Nomic-embed: ❌ Custom architecture, limited vLLM support
   - BGE: ✅ Officially supported, works immediately

3. **OpenAI-compatible API**: Both endpoints use `/v1/` format
   - Easier integration than mixing vLLM + TEI
   - Single SDK for all models

4. **GPU sharing requires setup**:
   - Kubernetes doesn't share GPUs by default
   - Use CPU for embeddings (fast enough)
   - Or configure MIG/time-slicing (more complex)

5. **Research matters**:
   - Check vLLM supported models list first
   - BGE found via official documentation
   - Saves time vs trial-and-error

---

## Files Summary

### Currently Deployed (Active)

| File                           | Purpose              | Model             | Resource    |
| ------------------------------ | -------------------- | ----------------- | ----------- |
| `vllm-runtime-shared.yaml`     | Generation runtime   | Qwen              | GPU (60%)   |
| `qwen-generation-service.yaml` | LLM deployment       | Qwen 2.5 1.5B     | GPU 12.5 GB |
| `vllm-runtime-embedding.yaml`  | Embedding runtime    | BGE               | CPU         |
| `bge-embedding-service.yaml`   | Embedding deployment | BGE-small-en-v1.5 | CPU 2-4 GB  |

---

---

# DocLocalAI Application Deployment Issues (Nov 2026)

This section covers issues encountered while deploying the full DocLocalAI application stack (database, backend API, frontend UI) on OpenShift.

---

## Issue 10: PostgreSQL Database Init Failed

**Symptom**: Database pod in `CrashLoopBackOff` status

**Error Logs**:

```
initdb: error: directory "/var/lib/postgresql/data" exists but is not empty
initdb: detail: It contains a lost+found directory, perhaps due to it being a mount point.
initdb: hint: Using a mount point directly as the data directory is not recommended.
Create a subdirectory under the mount point.
```

**How Found**: Checked pod logs after seeing CrashLoopBackOff status

**Root Cause**:

- PVC mounted directly to `/var/lib/postgresql/data`
- OpenShift creates a `lost+found` directory on the mount
- PostgreSQL's `initdb` refuses to initialize in a non-empty directory

**Solution**: Use a subdirectory for PostgreSQL data

```yaml
# In database.yaml
env:
  - name: PGDATA
    value: /var/lib/postgresql/data/pgdata # ← Subdirectory
volumeMounts:
  - name: db-data
    mountPath: /var/lib/postgresql/data # ← Parent directory
```

**Result**: ✅ Database initializes successfully

---

## Issue 11: Backend Pod Stuck in Pending

**Symptom**: Backend pod shows `Pending` status for several minutes

**Error from describe**:

```bash
oc describe pod doclocal-ai-api-xxx

Events:
  Warning  FailedScheduling  9m26s  default-scheduler
  running PreBind plugin "VolumeBinding": binding volumes: context deadline exceeded
```

**How Found**: `oc describe pod` showed PVC binding failure

**Root Causes**:

1. **Wrong database hostname**: Backend couldn't connect
2. **PVC access mode mismatch**: `ReadWriteMany` not supported by AWS EBS

**Findings**:

```bash
# Check DATABASE_URL
oc get secret doclocal-ai-secrets -o jsonpath='{.data.DATABASE_URL}' | base64 -d
# postgresql://user:pass@doclocalai-db:5432/db  ← WRONG (missing prefix)

# Check storage classes
oc get storageclass
# gp3-csi (default)   ebs.csi.aws.com   WaitForFirstConsumer
# ← AWS EBS only supports ReadWriteOnce (RWO)
```

**Solutions**:

1. Fix DATABASE_URL hostname:

```yaml
# In generated-secrets.yaml
DATABASE_URL: postgresql://doclocalai:pass@doclocal-ai-db:5432/doclocalai
#                                           ↑ Fixed: added "doclocal-ai-" prefix
```

2. Change PVC access mode:

```yaml
# In backend.yaml
spec:
  accessModes:
    - ReadWriteOnce # ← Changed from ReadWriteMany
```

**Result**: ✅ Pod scheduled and started

---

## Issue 12: Missing Runbooks ConfigMap

**Symptom**: Backend pod stuck in `ContainerCreating`

**Error from describe**:

```bash
oc describe pod doclocal-ai-api-xxx

Events:
  Warning  FailedMount  9s (x8 over 72s)  kubelet
  MountVolume.SetUp failed for volume "runbooks":
  configmap "doclocal-ai-runbooks" not found
```

**How Found**: `oc describe pod` showed volume mount failure

**Root Cause**: Backend deployment references a ConfigMap that doesn't exist

**Solutions**:

**Option 1**: Make ConfigMap optional (quick fix)

```yaml
# In backend.yaml
volumes:
  - name: runbooks
    configMap:
      name: doclocal-ai-runbooks
      optional: true # ← Allow pod to start without it
```

**Option 2**: Create the ConfigMap automatically

```bash
# Created: openshift/application/create-runbooks-configmap.sh
#!/bin/bash
RUNBOOKS_DIR="$SCRIPT_DIR/runbooks"
oc create configmap doclocal-ai-runbooks \
  --from-file="$RUNBOOKS_DIR" \
  --namespace=doclocal-ai \
  --dry-run=client -o yaml | oc apply -f -
```

**Result**: ✅ Pod starts successfully

---

## Issue 13: AI Not Responding - SSL Certificate Verification Failed

**Symptom**:

- Backend returns `503 Service Unavailable`
- UI shows no AI response

**Error Logs**:

```
❌ Embedding error: Connection error.

Traceback (most recent call last):
  File "httpx/_transports/default.py", line 250, in handle_request
httpx.ConnectError: [SSL: CERTIFICATE_VERIFY_FAILED]
certificate verify failed: unable to get local issuer certificate (_ssl.c:1004)
...
openai.APIConnectionError: Connection error.
```

**How Found**: Backend logs showed SSL verification errors

**Testing Process**:

```bash
# 1. Test endpoint with curl from backend pod (works with -k)
oc exec deployment/doclocal-ai-api -- curl -sk \
  https://qwen-llm-kserve-workload-svc.doclocal-ai-models:8000/v1/models
# ✅ SUCCESS - endpoint is reachable

# 2. Test without -k (fails)
oc exec deployment/doclocal-ai-api -- curl -s \
  https://qwen-llm-kserve-workload-svc.doclocal-ai-models:8000/v1/models
# ❌ curl: (60) SSL certificate problem: unable to get local issuer certificate

# 3. Check certificate issuer
oc exec deployment/doclocal-ai-api -- \
  openssl s_client -connect qwen-llm-kserve-workload-svc.doclocal-ai-models:8000 \
  -showcerts 2>&1 | grep issuer
# issuer=CN=openshift-service-serving-signer@1795595960
```

**Root Cause**:

- KServe services use HTTPS with OpenShift-signed certificates
- Python `httpx` library (used by OpenAI client) verifies SSL by default
- OpenShift Service CA not in Python's trust store

**Attempted Solutions** (Failed):

1. ❌ Set environment variables: `SSL_CERT_FILE`, `REQUESTS_CA_BUNDLE`, `HTTPX_VERIFY` → httpx ignores them
2. ❌ Mount CA bundle to Python's certifi location → file is read-only
3. ❌ Use `sitecustomize.py` to monkey-patch certifi → httpx doesn't use `certifi.where()`

**Working Solution**: Modify code to disable SSL verification

```python
# File: app/backend/app/services/embedding_service.py
from openai import OpenAI
import httpx  # ← ADD THIS
from app.config import settings

class EmbeddingService:
    def __init__(self):
        self.client = None
        if settings.embedding_endpoint_url and settings.embedding_model_name:
            http_client = httpx.Client(verify=False)  # ← ADD THIS
            self.client = OpenAI(
                base_url=settings.embedding_endpoint_url,
                api_key=settings.llm_api_token,
                http_client=http_client  # ← ADD THIS
            )
```

```python
# File: app/backend/app/services/chat_service.py
from openai import OpenAI
import httpx  # ← ADD THIS

class ChatService:
    def __init__(self):
        http_client = httpx.Client(verify=False)  # ← ADD THIS
        self.llm_client = OpenAI(
            base_url=settings.llm_endpoint_url,
            api_key=settings.llm_api_token,
            http_client=http_client  # ← ADD THIS
        )
```

**Rebuild and Deploy**:

```bash
cd app/backend
docker build -t quay.io/yonig/doclocalai-api:v2 .
docker push quay.io/yonig/doclocalai-api:v2

# Update image in backend.yaml
oc apply -f openshift/application/backend.yaml
```

**Result**: ✅ SSL errors resolved

---

## Issue 14: Empty API Token Causing Illegal Header

**Symptom**: Still getting `Connection error` after SSL fix

**Error Logs**:

```
httpcore.LocalProtocolError: Illegal header value b'Bearer '
```

**How Found**: Added detailed error logging, saw HTTP protocol error

**Root Cause**:

```bash
oc get secret doclocal-ai-secrets -o jsonpath='{.data.LLM_API_TOKEN}' | base64 -d
# (empty string)
```

Empty API token causes: `Authorization: Bearer ` (invalid HTTP header)

**Solution**:

```yaml
# In generated-secrets.yaml
LLM_API_TOKEN: "not-needed" # ← Changed from: ""
```

**Result**: ✅ API token error resolved

---

## Issue 15: Vector Dimension Mismatch in Database

**Symptom**:

- Chat API returns `500 Internal Server Error`
- AI generates response but fails to save it

**Error Logs**:

```
📝 Creating/updating session
✅ Session created/updated
💬 Saving user message
✅ User message saved
🤖 Generating AI response
✅ AI response generated: ❌ **I don't have runbooks...
💾 Saving assistant reply
❌ Error: Failed to save message: current transaction is aborted,
commands ignored until end of transaction block
```

**Deep Dive**:

```bash
# Test the vector search query
oc exec deployment/doclocal-ai-api -- python3 -c "
from app.database import Database
from app.services.embedding_service import EmbeddingService

embedding_service = EmbeddingService()
query_vector = embedding_service.get_embedding('test')
print(f'Vector dimensions: {len(query_vector)}')

with Database.get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute(
            'SELECT * FROM runbook_chunks ORDER BY embedding <=> %s::vector LIMIT 1',
            (query_vector,)
        )
"

# Output:
# Vector dimensions: 384
# psycopg.errors.DataException: expected 768 dimensions, not 384
```

**How Found**: Added detailed logging to track where transaction fails, then tested vector query directly

**Root Cause**:

```bash
# Check table schema
oc exec doclocal-ai-db-0 -- psql -U doclocalai -d doclocalai -c "\d runbook_chunks"

# embedding   | vector(768)  ← Table expects 768 dimensions
```

- Database table created with `vector(768)`
- BGE embedding model returns 384-dimensional vectors
- Dimension mismatch aborts PostgreSQL transaction

**Solution**: Recreate table with correct dimensions

```bash
oc exec doclocal-ai-db-0 -- psql -U doclocalai -d doclocalai -c "
DROP TABLE IF EXISTS runbook_chunks CASCADE;
CREATE TABLE runbook_chunks (
    chunk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_doc VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    embedding vector(384),  -- ← Changed from 768 to 384
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX ON runbook_chunks USING ivfflat (embedding vector_cosine_ops);
"
```

**Verification**:

```bash
# Test chat API
curl -X POST http://doclocal-ai-api:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"...", "message":"Hello"}'

# Response:
{
  "reply": "❌ **I don't have runbooks on this subject.**...",
  "model_used": "qwen-llm"
}
```

**Result**: ✅ AI responding successfully!

---

## Final Working Configuration

### Database (StatefulSet)

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: doclocal-ai-db
spec:
  serviceName: doclocal-ai-db
  template:
    spec:
      containers:
        - name: postgres
          env:
            - name: PGDATA
              value: /var/lib/postgresql/data/pgdata # Subdirectory
          volumeMounts:
            - name: db-data
              mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:
    - metadata:
        name: db-data
      spec:
        accessModes: [ReadWriteOnce] # RWO for AWS EBS
```

### Backend API

```yaml
env:
  - name: DATABASE_URL
    value: postgresql://user:pass@doclocal-ai-db:5432/db # Correct hostname
  - name: LLM_ENDPOINT_URL
    value: https://qwen-llm-kserve-workload-svc.doclocal-ai-models:8000/v1
  - name: LLM_API_TOKEN
    value: "not-needed" # Non-empty token
  - name: EMBEDDING_ENDPOINT_URL
    value: https://bge-llm-kserve-workload-svc.doclocal-ai-models:8000/v1
```

### Code Changes

```python
# embedding_service.py & chat_service.py
import httpx
http_client = httpx.Client(verify=False)
client = OpenAI(..., http_client=http_client)
```

### Database Schema

```sql
CREATE TABLE runbook_chunks (
    ...
    embedding vector(384)  -- Match BGE model dimensions
);
```

---

## Troubleshooting Commands Reference

### Quick Diagnostics

```bash
# Check all pod status
oc get pods -n doclocal-ai

# Check specific pod logs
oc logs -n doclocal-ai deployment/doclocal-ai-api --tail=50

# Check pod events
oc describe pod -n doclocal-ai <pod-name>

# Test backend API
oc exec -n doclocal-ai deployment/doclocal-ai-ui -- \
  curl -s http://doclocal-ai-api:8000/health

# Test AI endpoint (from backend pod)
oc exec -n doclocal-ai deployment/doclocal-ai-api -- \
  curl -sk https://qwen-llm-kserve-workload-svc.doclocal-ai-models:8000/v1/models

# Check database
oc exec -n doclocal-ai doclocal-ai-db-0 -- \
  psql -U doclocalai -d doclocalai -c "SELECT COUNT(*) FROM runbook_chunks;"
```

### Common Checks

```bash
# Check secrets
oc get secret doclocal-ai-secrets -n doclocal-ai -o jsonpath='{.data.DATABASE_URL}' | base64 -d

# Check ConfigMaps
oc get configmap -n doclocal-ai

# Check PVCs
oc get pvc -n doclocal-ai

# Check services
oc get svc -n doclocal-ai
oc get svc -n doclocal-ai-models

# Check routes
oc get route -n doclocal-ai
```

---

## Key Lessons Learned

1. **Use subdirectories for PVC mounts** - avoid `lost+found` conflicts
2. **Test with curl first** - isolate network vs SSL vs application issues
3. **Check vector dimensions early** - match embedding model output to database schema
4. **StatefulSet for databases** - more professional than Deployment
5. **Internal service URLs** - use cluster DNS for cross-namespace communication
6. **Code changes over env vars** - httpx doesn't respect all SSL env vars
7. **Non-empty API tokens** - even dummy values to avoid illegal headers

---

## Issue 16: Runbook Upload Not Working - Indexer Job Running Wrong Command

**Symptom**:

- Runbook upload returns `200 OK` status
- Files appear to be uploaded successfully
- Database has 0 indexed chunks
- No runbooks available for AI queries

**How Found**:

```bash
# Check database
oc exec statefulset/doclocal-ai-db -- psql -U doclocalai -d doclocalai \
  -c "SELECT COUNT(*) FROM runbook_chunks;"
# 0 rows

# Check indexer job
oc get job doclocal-ai-runbook-indexer -n doclocal-ai
# STATUS: Running (for 110 minutes!)

# Check job logs
oc logs -l app=runbook-indexer -n doclocal-ai --tail=50
# INFO: Uvicorn running on http://0.0.0.0:8000
# (Unexpected - should be running indexing script!)
```

**Root Cause**:

- Job YAML specified image but no **command override**
- Container ran default Docker CMD (`uvicorn`) instead of indexing script
- Job stayed Running forever instead of completing

**Initial Job Configuration** (Broken):

```yaml
# openshift/application/runbook-indexer-job.yaml
containers:
  - name: indexer
    image: quay.io/yonig/doclocalai-api:v4
    # ❌ No command specified - uses default CMD from Dockerfile
```

**Solution**: Add command override to run indexing script

```yaml
# openshift/application/runbook-indexer-job.yaml
containers:
  - name: indexer
    image: quay.io/yonig/doclocalai-api:v7
    command: ["python3", "/opt/app-root/src/scripts/index_runbooks.py"] # ← ADDED
```

**Result**: Job runs indexing script instead of web server

---

## Issue 17: Indexer Script Path Not Found in Docker Image

**Symptom**: After adding command override, job crashes immediately

**Error Logs**:

```bash
oc logs -l app=runbook-indexer -n doclocal-ai
# python3: can't open file '/scripts/index_runbooks.py':
# [Errno 2] No such file or directory
```

**How Found**: Job pod in `CrashLoopBackOff`, logs show file not found

**Root Cause**:

- Dockerfile built from `app/backend/` context
- Could not `COPY ../scripts/` (parent directory access denied in Docker)
- Script exists in repo at `scripts/index_runbooks.py` but not in image

**Investigation**:

```bash
# Check what's in the image
docker run --rm quay.io/yonig/doclocalai-api:v6 \
  find /opt/app-root/src -name "index_runbooks.py"
# (empty - file not found)

# Check repo structure
find . -name "index_runbooks.py"
# ./app/backend/scripts/index_runbooks.py
```

**Solution**: Build image from repo root with updated Dockerfile

```dockerfile
# app/backend/Dockerfile (BEFORE - broken)
FROM registry.access.redhat.com/ubi9/python-311:latest
WORKDIR /opt/app-root/src
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
# ❌ Can't do: COPY ../scripts/ /scripts/

# app/backend/Dockerfile (AFTER - working)
FROM registry.access.redhat.com/ubi9/python-311:latest
WORKDIR /opt/app-root/src
COPY app/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/backend/app/ ./app/
COPY scripts/ ./scripts/  # ← Build from repo root
```

**Build from repo root**:

```bash
cd ./DocLocalAI
docker build -f app/backend/Dockerfile -t quay.io/yonig/doclocalai-api:v6 .
docker push quay.io/yonig/doclocalai-api:v6
```

**Update job path**:

```yaml
command: ["python3", "/opt/app-root/src/scripts/index_runbooks.py"]
#                     ↑ Full path in image
```

**Result**: ✅ Script found in image at correct path

---

## Issue 18: Indexer Job Fails with SSL Certificate Error

**Symptom**: Job runs but all chunks fail to index

**Error Logs**:

```bash
oc logs -l app=runbook-indexer -n doclocal-ai
# 📄 Processing: README.md
#    Created 19 chunks
#    ✗ Failed chunk 0: Connection error.
#    ✗ Failed chunk 1: Connection error.
#    ...
# 📊 Indexing complete!
#    Total chunks: 0
#    Unique documents: 0
```

**How Found**: Job completes successfully but database still has 0 chunks

**Root Cause**:

- Indexer script creates OpenAI client for embeddings
- Same SSL issue as backend services (Issue 13)
- Script missing `httpx.Client(verify=False)` fix

**Code Comparison**:

```python
# Backend service (working) - chat_service.py
import httpx
http_client = httpx.Client(verify=False)
self.llm_client = OpenAI(..., http_client=http_client)

# Indexer script (broken) - scripts/index_runbooks.py
embed_client = OpenAI(base_url=EMBED_URL, api_key="not-needed")
# ❌ No SSL fix!
```

**Solution**: Add SSL fix to indexer script

```python
# File: app/backend/scripts/index_runbooks.py
import os
import sys
import psycopg
import httpx  # ← ADD THIS
from pathlib import Path
from openai import OpenAI
from pgvector.psycopg import register_vector

def main():
    try:
        http_client = httpx.Client(verify=False)  # ← ADD THIS
        embed_client = OpenAI(
            base_url=EMBED_URL,
            api_key="not-needed",
            http_client=http_client  # ← ADD THIS
        )
        conn = psycopg.connect(DB_DSN)
        # ... rest of code
```

**Rebuild and Deploy**:

```bash
docker build -f app/backend/Dockerfile -t quay.io/yonig/doclocalai-api:v7 .
docker push quay.io/yonig/doclocalai-api:v7

# Update image version
# In backend.yaml and runbook-indexer-job.yaml
image: quay.io/yonig/doclocalai-api:v7

# Restart job
oc delete job doclocal-ai-runbook-indexer -n doclocal-ai
oc apply -f openshift/application/runbook-indexer-job.yaml
```

**Result**: SSL errors resolved, embeddings generated successfully

---

## Issue 19: Database Schema Missing chunk_index Column

**Symptom**: Indexer job runs but fails to insert chunks

**Error Logs**:

```bash
oc logs -l app=runbook-indexer -n doclocal-ai
# 📄 Processing: README.md
#    Created 19 chunks
#    ✗ Failed chunk 0: column "chunk_index" of relation "runbook_chunks" does not exist
# LINE 2: INSERT INTO runbook_chunks (source_doc, chunk_index, content...
#                                                  ^
#    ✗ Failed chunk 1: current transaction is aborted, commands ignored...
```

**How Found**: Job logs show SQL error on INSERT

**Root Cause**:

- Indexer script expects `chunk_index` column
- Database table schema missing this column
- Schema mismatch between code and database

**Investigation**:

```bash
# Check actual table schema
oc exec statefulset/doclocal-ai-db -n doclocal-ai -- \
  psql -U doclocalai -d doclocalai -c "\d runbook_chunks"

# Table "public.runbook_chunks"
#    Column   |           Type
# ------------+--------------------------
#  chunk_id   | uuid
#  source_doc | character varying(255)
#  content    | text
#  embedding  | vector(384)
#  created_at | timestamp with time zone
# ❌ Missing: chunk_index column
```

**Code Requirement**:

```python
# scripts/index_runbooks.py
cur.execute(
    """
    INSERT INTO runbook_chunks (source_doc, chunk_index, content, embedding)
    VALUES (%s, %s, %s, %s)
    """,
    (source_name, idx, chunk, embedding)  # ← Requires chunk_index
)
```

**Solution**: Add missing column to table

```bash
oc exec statefulset/doclocal-ai-db -n doclocal-ai -- \
  psql -U doclocalai -d doclocalai -c \
  "ALTER TABLE runbook_chunks ADD COLUMN chunk_index INTEGER NOT NULL DEFAULT 0;"
```

**Verification**:

```bash
# Check updated schema
oc exec statefulset/doclocal-ai-db -- psql -U doclocalai -d doclocalai -c "\d runbook_chunks"
# chunk_index | integer | not null | 0  ✅
```

**Result**: ✅ INSERT statements succeed

---

## Issue 20: Runbook Indexing Success

**Final Result**: After fixing all issues, runbook indexing works end-to-end

**Successful Job Logs**:

```bash
oc logs -l app=runbook-indexer -n doclocal-ai
# 📘 Found 4 sample runbooks in /runbooks
# 📗 Found 0 uploaded runbooks in /runbooks-uploads
# 🔍 Total: 4 runbook files to index
# 📊 Connecting to database...
# ✅ Connected
#
# 📄 Processing: README.md
#    Created 19 chunks
#    ✓ Chunk 1/19
#    ✓ Chunk 2/19
#    ...
#    ✓ Chunk 19/19
#    ✅ Indexed README.md
#
# 📄 Processing: minikube.md
#    Created 14 chunks
#    ✓ Chunk 1/14
#    ...
#    ✅ Indexed minikube.md
#
# 📄 Processing: openshift-networking.md
#    Created 11 chunks
#    ✅ Indexed openshift-networking.md
#
# 📄 Processing: openshift-pod-troubleshooting.md
#    Created 10 chunks
#    ✅ Indexed openshift-pod-troubleshooting.md
#
# 🧹 Cleaning up orphaned chunks...
#    ✓ No orphaned chunks found
#
# 📊 Indexing complete!
#    Total chunks: 54
#    Unique documents: 4
```

**Job Status**:

```bash
oc get job doclocal-ai-runbook-indexer -n doclocal-ai
# NAME                          STATUS     COMPLETIONS   DURATION
# doclocal-ai-runbook-indexer   Complete   1/1           7s
```

**Database Verification**:

```bash
oc exec statefulset/doclocal-ai-db -- psql -U doclocalai -d doclocalai -c \
  "SELECT source_doc, COUNT(*) as chunks FROM runbook_chunks GROUP BY source_doc;"

# source_doc                       | chunks
# ---------------------------------+--------
#  minikube.md                     |     14
#  openshift-networking.md         |     11
#  openshift-pod-troubleshooting.md|     10
#  README.md                       |     19
# (4 rows)
```

**AI Query Test**:

```bash
# Ask question via UI: "How do I troubleshoot a pod in OpenShift?"
# Response: AI returns relevant content from indexed runbooks ✅
```

---

## Runbook Upload/Indexing - Summary of Fixes

| Issue                    | Root Cause                       | Solution                                      | Image Version |
| ------------------------ | -------------------------------- | --------------------------------------------- | ------------- |
| Job runs forever         | No command override in Job YAML  | Add `command:` to run indexing script         | v5            |
| Script file not found    | Dockerfile can't copy from `../` | Build from repo root, copy scripts/ directory | v6            |
| SSL certificate error    | Indexer missing httpx SSL fix    | Add `httpx.Client(verify=False)` to script    | v7            |
| chunk_index column error | Database schema missing column   | `ALTER TABLE ADD COLUMN chunk_index INTEGER`  | v7            |
| **SUCCESS**              | All issues fixed                 | 54 chunks indexed from 4 runbooks ✅          | v7            |

**Working Configuration**:

```yaml
# openshift/application/runbook-indexer-job.yaml
spec:
  template:
    spec:
      containers:
        - name: indexer
          image: quay.io/yonig/doclocalai-api:v7
          command: ["python3", "/opt/app-root/src/scripts/index_runbooks.py"]
          envFrom:
            - configMapRef:
                name: doclocal-ai-config
            - secretRef:
                name: doclocal-ai-secrets
          volumeMounts:
            - name: runbooks
              mountPath: /runbooks
            - name: runbooks-uploads
              mountPath: /runbooks-uploads
```

```python
# app/backend/scripts/index_runbooks.py
import httpx
from openai import OpenAI

http_client = httpx.Client(verify=False)
embed_client = OpenAI(
    base_url=EMBED_URL,
    api_key="not-needed",
    http_client=http_client
)
```

```sql
-- Database schema
CREATE TABLE runbook_chunks (
    chunk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_doc VARCHAR(255) NOT NULL,
    chunk_index INTEGER NOT NULL DEFAULT 0,  -- ← Added
    content TEXT NOT NULL,
    embedding vector(384),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

## Issue 21: Production - DB Password Desync After Redeploy

**Symptom**: Backend continuously fails to reach the database. Postgres logs show, repeatedly:

```
FATAL:  password authentication failed for user "doclocalai"
DETAIL:  Connection matched file "/var/lib/postgresql/data/pgdata/pg_hba.conf" line 128: "host all all all scram-sha-256"
```

Backend logs show a healthy `/health` (200 OK, doesn't touch the DB) alongside a connection pool failing from the very first request:

```
error connecting in 'pool-1': connection failed: connection to server at "10.128.1.28", port 5432 failed: FATAL:  password authentication failed for user "doclocalai"
psycopg_pool.PoolTimeout: couldn't get a connection after 30.00 sec
```

**How Found**:

```bash
# Current secret's password
PW=$(oc get secret doclocal-ai-secrets -n doclocal-ai -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d)

# ⚠️ This "succeeds" but is a FALSE POSITIVE - loopback is `trust`-authed, no
# password is actually checked:
oc exec -n doclocal-ai doclocal-ai-db-0 -- bash -c "PGPASSWORD='$PW' psql -h 127.0.0.1 -U doclocalai -d doclocalai -c 'select 1;'"

# The REAL test - over the service/pod IP, which hits the password-checked rule:
oc exec -n doclocal-ai doclocal-ai-db-0 -- bash -c "PGPASSWORD='$PW' psql -h doclocal-ai-db -U doclocalai -d doclocalai -c 'select 1;'"
# FATAL: password authentication failed for user "doclocalai"  ← confirms real mismatch

# Confirmed via pg_hba.conf:
oc exec -n doclocal-ai doclocal-ai-db-0 -- cat /var/lib/postgresql/data/pgdata/pg_hba.conf
#   local   all   all                    trust       ← loopback bypasses password check
#   host    all   all   127.0.0.1/32     trust
#   host    all   all   all              scram-sha-256   ← real traffic hits this one
```

**Root Cause**: `deploy-app.sh` ran `DB_PASSWORD=$(openssl rand -hex 16)` unconditionally and re-applied the `<namespace>-secrets` Secret on **every** invocation, even against an already-initialized database. Postgres only applies `POSTGRES_PASSWORD` the first time it runs `initdb` on an empty PVC — on every later start it keeps whatever password is already in its role catalog. Running the deploy script a second time (without wiping the DB) regenerated the Secret with a brand-new password that the backend picked up immediately, while Postgres kept the original one — a silent split between "what the Secret says" and "what Postgres actually has."

**Solution (live fix, zero downtime, no data loss)**: Push the password from the current Secret into Postgres directly, using the pod's trusted local socket (bypasses the mismatch since local connections don't check a password):

```bash
NS=doclocal-ai
PW=$(oc get secret doclocal-ai-secrets -n $NS -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d)
oc exec -n $NS doclocal-ai-db-0 -- psql -U doclocalai -d doclocalai -v ON_ERROR_STOP=1 \
  -c "ALTER ROLE doclocalai WITH PASSWORD '${PW}';"
```

The backend's existing connection pool recovers on its own within seconds — no pod restart needed.

**Script Fix**: `deploy-app.sh` now deletes any existing `<namespace>-secrets` Secret before generating a new one, so a stale secret from a prior run can't linger:

```bash
oc delete secret "${NAMESPACE}-secrets" -n "$NAMESPACE" --ignore-not-found
DB_PASSWORD=$(openssl rand -hex 16)
```

**⚠️ Caveat**: This prevents a stale Secret object from lingering, but it does **not** by itself keep Postgres's actual stored password in sync — regenerating the password and redeploying against an **already-initialized** database (non-empty PVC) will reproduce this exact issue again. If that happens, re-run the `ALTER ROLE` sync above. For a true clean reset, wipe the database's PVC so `initdb` re-runs with the new password.

**Result**: ✅ Backend reconnects immediately; root cause documented so it's recognized instantly next time instead of re-diagnosed from scratch.

---

## Issue 22: `content_hash` Column Missing + Wrong Vector Dimension (OpenShift Schema Drift)

**Symptom**: Runbook indexing fails on every chunk:

```
ERROR: column "content_hash" of relation "runbook_chunks" does not exist at character 95
STATEMENT:
INSERT INTO runbook_chunks (source_doc, chunk_index, content, embedding, content_hash)
VALUES ($1, $2, $3, $4, $5)
ERROR: current transaction is aborted, commands ignored until end of transaction block
```

**How Found**: Compared the live table against the local docker-compose schema:

```bash
oc exec -n doclocal-ai doclocal-ai-db-0 -- psql -U doclocalai -d doclocalai -c '\d runbook_chunks'
# Only had: chunk_id, source_doc, chunk_index, content, embedding vector(768), updated_at
# Missing: content_hash, content_tsv (and its FTS trigger/index)
```

**Root Cause**: `openshift/application/db-init-configmap.yaml` is a separate, hand-maintained copy of the schema in `app/db/init.sql` (used by docker-compose) — and it had drifted. `content_hash` (dedup) and `content_tsv` + its trigger/GIN index (hybrid full-text search) were added to the local schema but never ported to the OpenShift ConfigMap, so `scripts/index_runbooks.py`'s 5-column insert (including `content_hash`) failed immediately against an OpenShift-provisioned database.

Separately — **not actually caused by "using a different model than docker-compose," but adjacent to it** — both schema files hardcoded `embedding vector(768)` (matching local Ollama's `nomic-embed-text`), while this OpenShift deployment serves embeddings via **BGE-Small-EN-v1.5, confirmed live to return 384-dim vectors**:

```bash
oc run test-bge-dim --rm -i --restart=Never --image=curlimages/curl:latest -n doclocal-ai-models -- \
  curl -sk -X POST https://bge-llm-kserve-workload-svc.doclocal-ai-models.svc.cluster.local:8000/v1/embeddings \
  -H "Content-Type: application/json" -d '{"model":"bge-llm","input":"Hello world"}'
# → embedding array length: 384
```
This would have surfaced as a second failure (`expected 768 dimensions, not 384`) right after fixing the missing column.

**Solution**:

1. Updated `openshift/application/db-init-configmap.yaml` to match `app/db/init.sql` (adds `content_hash`, `content_tsv` + trigger + GIN index), using `embedding vector(384)` instead of `vector(768)` to match BGE's real output.
2. Applied the equivalent DDL live (table had 0 rows, so a straight recreate was safe):

```bash
oc exec -i -n doclocal-ai doclocal-ai-db-0 -- psql -U doclocalai -d doclocalai -v ON_ERROR_STOP=1 <<'EOF'
DROP TABLE IF EXISTS runbook_chunks CASCADE;

CREATE TABLE runbook_chunks (
    chunk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_doc VARCHAR(255) NOT NULL,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(384),
    content_hash VARCHAR(64),
    content_tsv tsvector,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_runbook_embedding ON runbook_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_runbook_content_hash ON runbook_chunks(content_hash);
CREATE INDEX idx_runbook_content_fts ON runbook_chunks USING gin(content_tsv);

CREATE OR REPLACE FUNCTION runbook_chunks_tsv_trigger() RETURNS trigger AS $$
BEGIN
    NEW.content_tsv := to_tsvector('english', COALESCE(NEW.content, ''));
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

CREATE TRIGGER tsvector_update BEFORE INSERT OR UPDATE OF content
ON runbook_chunks FOR EACH ROW EXECUTE FUNCTION runbook_chunks_tsv_trigger();
EOF
```

**Gotcha**: `oc exec` needs `-i` to forward a heredoc's stdin into `psql` — without it, the commands are silently never sent (no error, nothing happens).

**Verification**:

```bash
oc delete job doclocal-ai-runbook-indexer -n doclocal-ai --ignore-not-found
oc apply -f openshift/application/runbook-indexer-job.yaml
# ...
# ✅ Indexed COE Process Client.md (18 chunks)
# 📊 Indexing complete! Total chunks: 18
```

**⚠️ Caveat**: Like `db-init-configmap.yaml`'s other init SQL, this only applies automatically to a fresh/empty PVC. The local (`app/db/init.sql`) and OpenShift (`db-init-configmap.yaml`) schemas are two independently maintained copies with no shared migration mechanism — any future schema change must be ported to both by hand, and manually re-applied (via `ALTER TABLE`/recreate) to any database that's already running.

**Result**: ✅ Runbook indexing works end-to-end on OpenShift, including dedup (`content_hash`) and hybrid full-text search (`content_tsv`).

---

## Issue 23: Upload/Search Broken After Fresh Redeploy - `LLM_API_TOKEN` Regression

**Symptom**: After a full teardown + redeploy, runbook upload and chat search both silently fail. Backend logs show embedding calls failing with a generic connection error:

```
httpx.LocalProtocolError: Illegal header value b'Bearer '

openai.APIConnectionError: Connection error.
  File "/opt/app-root/src/app/services/embedding_service.py", line 24, in get_embedding
    response = self.client.embeddings.create(
```

**How Found**:

```bash
# Confirmed the token itself was empty in the running pod:
oc exec -n doclocal-ai <api-pod> -- printenv LLM_API_TOKEN
# (empty)

# Direct embedding test reproduced it immediately:
oc exec -n doclocal-ai <api-pod> -- python3 -c "
from app.services.embedding_service import EmbeddingService
EmbeddingService().get_embedding('test')
"
```

**Root Cause**: This is a **regression of Issue 14** (`Illegal header value b'Bearer '`). That issue was originally fixed by changing the value directly in the generated/live Secret, but the actual source of truth, `openshift/application/template-secrets.yaml`, still hardcoded:

```yaml
LLM_API_TOKEN: ""
```

`deploy-app.sh` also still had `sed "s/<LLM_API_TOKEN>//g"` left over from an older version of the template that used a `<LLM_API_TOKEN>` placeholder — by the time of this issue the template no longer had that placeholder at all, so the `sed` was dead code substituting nothing into nothing. Nothing in the deploy path ever set a non-empty token. The fix "stuck" only as long as nobody tore down and redeployed from scratch; a fresh `teardown-app.sh` + `deploy-app.sh` regenerated the secret from the still-broken template and brought the bug straight back.

`EmbeddingService` (and `ChatService`) both use `settings.llm_api_token` as the `api_key` for their `OpenAI(...)` client, so an empty token breaks embeddings (upload indexing + query-time search) the same way it breaks chat.

**Solution**:

1. Fixed the actual source of truth in `openshift/application/template-secrets.yaml`:
   ```yaml
   LLM_API_TOKEN: "not-needed"
   ```
2. Removed the dead `sed "s/<LLM_API_TOKEN>//g"` line from `deploy-app.sh` - the template now has a literal value, not a placeholder.
3. Fixed the already-running cluster without a redeploy:
   ```bash
   oc patch secret doclocal-ai-secrets -n doclocal-ai --type=merge -p '{"stringData":{"LLM_API_TOKEN":"not-needed"}}'
   oc rollout restart deployment/doclocal-ai-api -n doclocal-ai
   ```

**Verification**:

```bash
oc exec -n doclocal-ai <api-pod> -- python3 -c "
from app.services.embedding_service import EmbeddingService
print(len(EmbeddingService().get_embedding('test query')))
"
# 384

curl -X POST .../api/chat -d '{"session_id":"...","message":"what runbooks do you have?"}'
# {"reply":"📚 Here are the runbooks I have access to: ...", "model_used":"qwen-llm"}
```

**⚠️ Lesson**: A fix applied only to a live Secret/ConfigMap (not to the template/script that generates it) is not actually fixed — it's postponed until the next clean redeploy. Issues 14, 21, and 22 in this document are all instances of the same pattern: always confirm the fix lives in the file under version control, not just in `oc patch`/`oc edit` against the running cluster.

**Result**: ✅ Upload and search both work again; the fix now survives a full teardown + redeploy.

---
