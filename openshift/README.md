# OpenShift Deployment for DocLocalAI

Deploy HuggingFace models: Qwen 2.5 1.5B (text generation) + BGE-Small-EN-v1.5 (embeddings) on OpenShift AI.

---

## 🖥️ Reference Environment

**This deployment was tested and optimized on:**

| Resource    | Specification     | Qwen Usage | BGE Usage | Total Used    | Available      |
| ----------- | ----------------- | ---------- | --------- | ------------- | -------------- |
| **GPU**     | NVIDIA L4 (23 GB) | ~3 GB      | ~0.5 GB   | ~3.5 GB (15%) | ~19.5 GB (85%) |
| **CPU**     | Multiple cores    | 1-4 cores  | 1-4 cores | 2-8 cores     | Varies         |
| **RAM**     | Cluster memory    | 8-12 GB    | 4-8 GB    | 12-20 GB      | Varies         |
| **Storage** | Persistent        | ~3 GB      | ~0.5 GB   | ~4 GB         | -              |

**Models deployed:**

- **Qwen 2.5 1.5B Instruct**: 2.89 GB model weights via llm-d
- **BGE-Small-EN-v1.5**: 133 MB model via llm-d

---

## 💡 Why These Configurations?

### Using llm-d (Distributed Inference)

**Choice**: Deploy via LLMInferenceService with llm-d runtime

**Reasons:**

- ✅ Full OpenShift AI UI integration
- ✅ Hardware profile support
- ✅ Gateway-based routing with load balancing
- ✅ Built-in monitoring and metrics
- ✅ Automatic scaling capabilities

**Benefits:**

- Proper deployment tracking in UI
- Connection management via OpenShift AI
- Production-ready serving stack

### Both Models on GPU

**Choice**: Both Qwen and BGE use GPU acceleration

**Reasons:**

- ✅ Faster embeddings (GPU vs CPU)
- ✅ llm-d manages GPU allocation efficiently
- ✅ Plenty of GPU memory available (L4 has 23 GB)

**Resource allocation:**

- Qwen: ~3 GB GPU memory
- BGE: ~0.5 GB GPU memory
- Free: ~19.5 GB for other workloads

### Model Size Selection

**Choice**: 1.5B parameter model (not 3B or 7B)

**Reasons:**

- ✅ Fits comfortably on L4 GPU (23 GB)
- ✅ More GPU memory available for KV cache
- ✅ Better concurrent request handling
- ✅ Fast inference (~50-100 tokens/sec)

**When to upgrade**: If you have A100 (40-80 GB), consider Qwen 7B or larger

---

## 📁 Structure

```
openshift/
├── ai-models/                      # AI inference models
│   ├── qwen-llm-service.yaml       # Qwen LLMInferenceService
│   ├── bge-llm-service.yaml        # BGE LLMInferenceService
│   ├── qwen-connection.yaml        # Qwen HuggingFace connection
│   └── bge-connection.yaml         # BGE HuggingFace connection
│
├── application/                    # DocLocalAI application stack
│   ├── database.yaml               # PostgreSQL StatefulSet
│   ├── backend.yaml                # FastAPI backend
│   ├── frontend.yaml               # Streamlit UI
│   ├── runbook-indexer-job.yaml    # Batch indexing job
│   ├── configmap.yaml              # App configuration
│   ├── db-init-configmap.yaml      # Database init SQL
│   ├── template-secrets.yaml       # Secrets template
│   └── generated-secrets.yaml      # Generated secrets (gitignored)
│
├── scripts/                        # Deployment automation
│   ├── deploy-all.sh               # Deploy complete stack
│   ├── deploy-models.sh            # Deploy AI models only
│   ├── deploy-app.sh               # Deploy application only
│   └── create-runbooks-configmap.sh # Create runbooks ConfigMap
│
└── README.md                       # This file

Related directories:
├── ../doc/                         # Documentation & tools
│   ├── TROUBLESHOOTING.md          # Complete debugging guide
│   ├── tools/                      # Utility scripts
│   │   └── check-gpu-usage.sh      # GPU monitoring tool
│   └── archive-openshift/          # Deprecated files
│       └── inferenceservice/       # Old InferenceService approach
└── ../../runbooks/                 # Sample runbook files
```

---

## 🚀 Quick Start

### Option 1: Deploy Everything (Recommended)

```bash
cd openshift

# Set your HuggingFace token (for AI models)
export HF_TOKEN="hf_your_token_here"

# Deploy complete stack (AI models + application)
./scripts/deploy-all.sh
```

### Option 2: Deploy AI Models Only

```bash
cd openshift

# Set your HuggingFace token
export HF_TOKEN="hf_your_token_here"

# Deploy both models with llm-d
./scripts/deploy-models.sh
```

### Option 3: Deploy Application Only

```bash
cd openshift

# Deploy application stack (assumes AI models already deployed)
./scripts/deploy-app.sh
```

### Monitor Deployment

```bash
# Check status
oc get llminferenceservice -n doclocal-ai-models

# Watch pods
oc get pods -n doclocal-ai-models -w

# Check in UI
# OpenShift AI Dashboard → Project → doclocal-ai-models → Deployments
```

---

## 📊 What Gets Deployed

### 1. Qwen 2.5 1.5B (Text Generation)

- **Runtime**: llm-d (Distributed inference)
- **API Type**: LLMInferenceService (v1alpha2)
- **GPU Memory**: ~3 GB
- **Resources**: 2-4 CPU, 8-12 GB RAM, 1 GPU
- **API**: `/v1/chat/completions` (OpenAI-compatible)
- **Gateway URL**: `https://inference-gateway.apps.../doclocal-ai-models/qwen-llm`
- **Hardware Profile**: gpu-profile

### 2. BGE-Small-EN-v1.5 (Embeddings)

- **Runtime**: llm-d (Distributed inference)
- **API Type**: LLMInferenceService (v1alpha2)
- **GPU Memory**: ~0.5 GB
- **Resources**: 2-4 CPU, 4-8 GB RAM, 1 GPU
- **Dimensions**: 384
- **API**: `/v1/embeddings` (OpenAI-compatible)
- **Gateway URL**: `https://inference-gateway.apps.../doclocal-ai-models/bge-llm`
- **Hardware Profile**: gpu-profile

---

## 🔧 Backend Configuration

Point your DocLocalAI backend to these endpoints:

**Direct service URLs (Recommended for backend):**

```yaml
LLM_ENDPOINT_URL: https://qwen-llm-kserve-workload-svc.doclocal-ai-models.svc.cluster.local:8000/v1
LLM_MODEL_NAME: qwen-llm

EMBEDDING_ENDPOINT_URL: https://bge-llm-kserve-workload-svc.doclocal-ai-models.svc.cluster.local:8000/v1
EMBEDDING_MODEL_NAME: bge-llm
```

**How to discover these URLs:**

```bash
# Get Qwen LLM endpoint
oc get svc qwen-llm-kserve-workload-svc -n doclocal-ai-models \
  -o jsonpath='https://{.metadata.name}.{.metadata.namespace}.svc.cluster.local:{.spec.ports[0].port}/v1'

# Get BGE embedding endpoint
oc get svc bge-llm-kserve-workload-svc -n doclocal-ai-models \
  -o jsonpath='https://{.metadata.name}.{.metadata.namespace}.svc.cluster.local:{.spec.ports[0].port}/v1'
```

**Note:** These use **OpenAI-compatible APIs** - you can use the OpenAI Python SDK!

**SSL Certificate:** Services use self-signed OpenShift certificates. In your backend code, disable SSL verification:
```python
import httpx
http_client = httpx.Client(verify=False)
client = OpenAI(..., http_client=http_client)
```

---

## 📚 Documentation

- **[TROUBLESHOOTING.md](../doc/TROUBLESHOOTING.md)** - Complete troubleshooting guide
- **[ai-models/](ai-models/)** - AI model deployment files

---

## ✅ Verification

### Test from within OpenShift cluster:

```bash
# Test Qwen LLM (text generation)
oc run test-gen --rm -i --restart=Never --image=curlimages/curl:latest \
  -n doclocal-ai-models -- \
  curl -sk https://qwen-llm-kserve-workload-svc.doclocal-ai-models.svc.cluster.local:8000/v1/models

# Expected output: {"object":"list","data":[{"id":"qwen-llm",...}]}

# Test BGE embeddings
oc run test-embed --rm -i --restart=Never --image=curlimages/curl:latest \
  -n doclocal-ai-models -- \
  curl -sk https://bge-llm-kserve-workload-svc.doclocal-ai-models.svc.cluster.local:8000/v1/models

# Expected output: {"object":"list","data":[{"id":"bge-llm",...}]}
```

### Test actual inference:

```bash
# Test chat completion
oc run test-chat --rm -i --restart=Never --image=curlimages/curl:latest \
  -n doclocal-ai-models -- \
  curl -sk -X POST https://qwen-llm-kserve-workload-svc.doclocal-ai-models.svc.cluster.local:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"qwen-llm","messages":[{"role":"user","content":"Hello"}]}'

# Test embeddings
oc run test-embedding --rm -i --restart=Never --image=curlimages/curl:latest \
  -n doclocal-ai-models -- \
  curl -sk -X POST https://bge-llm-kserve-workload-svc.doclocal-ai-models.svc.cluster.local:8000/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"model":"bge-llm","input":"Hello world"}'
```

**Note:** Use `-k` flag with curl to skip SSL certificate verification (self-signed certs).

---

## 📦 Resource Usage

| Component | GPU              | CPU       | RAM     |
| --------- | ---------------- | --------- | ------- |
| **Qwen**  | 12.5 GB          | 2-4 cores | 6-12 GB |
| **BGE**   | -                | 2-4 cores | 2-4 GB  |
| **Total** | 12.5/23 GB (54%) | 4-8 cores | 8-16 GB |

**GPU Free**: 10.5 GB (46% available)

---

## 🖥️ Manual Deployment via OpenShift AI Dashboard

If you prefer using the OpenShift AI Dashboard UI instead of the CLI script:

### Prerequisites

- ✅ OpenShift AI 3.3+ installed
- ✅ HuggingFace token ([get here](https://huggingface.co/settings/tokens))
- ✅ Access to OpenShift AI Dashboard

### Steps

#### 1. Get HuggingFace Token

- Go to https://huggingface.co/settings/tokens
- Click **New token**
- Name: `openshift-model-download`
- Type: **Read** (not Write)
- Click **Generate token**
- Copy the token (starts with `hf_...`)

#### 2. Create Token Secret

Via OpenShift Console:

- Go to **Workloads** → **Secrets**
- Select your namespace/project (`doclocal-ai-models`)
- Click **Create** → **Key/value secret**
  - Name: `huggingface-token`
  - Key: `HF_TOKEN`
  - Value: `hf_your_token_here` (paste your token)
- Click **Create**

Or via CLI:

```bash
oc create secret generic huggingface-token \
  --from-literal=HF_TOKEN="hf_your_actual_token_here" \
  -n doclocal-ai-models
```

#### 3. Deploy Model via Dashboard

**For Text Generation (Qwen):**

1. Open **OpenShift AI Dashboard**
2. Go to **Project** section
3. Go to **Deployments** section
4. Click **Deploy Model** (Single-model serving platform)
5. Configure:
   - **Model location**:
     - Connection type: URI
     - Connection name: `qwen-connection`
     - URI: `hf://Qwen/Qwen2.5-1.5B-Instruct`
   - **Model type**: Generative AI model (LLM)
   - **Model deployment name**: `qwen-15b`
   - **Serving runtime**: vLLM ServingRuntime for KServe
   - **Hardware profile**: Custom
   - **Customize resource requests and limits**:
     - **Minimum** (CPU inference):
       - CPU: 2 cores (request), 4 cores (limit)
       - Memory: 8 Gi (request), 16 Gi (limit)
     - **Recommended** (GPU inference):
       - CPU: 2 cores (request), 4 cores (limit)
       - Memory: 6 Gi (request), 12 Gi (limit)
       - GPU: 1 (nvidia.com/gpu)
   - **Model server replicas**: `1`
   - **Token authentication**: Disable (for internal use)
   - **Environment variables**:
     - Click **Add custom runtime environment variables**
     - Key: `HF_TOKEN`
     - Secret: `huggingface-token`
6. Click **Deploy**

**For Embeddings (BGE):**

Repeat the same steps with these changes:

- **URI**: `hf://BAAI/bge-small-en-v1.5`
- **Model deployment name**: `bge-embedding`
- **Resource settings** (CPU only):
  - CPU: 2 cores (request), 4 cores (limit)
  - Memory: 2 Gi (request), 4 Gi (limit)
  - GPU: None
- **Environment variables**: Same `HF_TOKEN`

#### 4. Wait for Deployment

- Status: `Pending` → `Downloading` → `Loading` → `Ready`
- First download takes 2-5 minutes
- Monitor in Dashboard or via CLI:
  ```bash
  oc get inferenceservice -n doclocal-ai-models -w
  ```

#### 5. Get Endpoints

Once status is **Ready**:

- Copy the **Inference endpoint** URL from Dashboard
- Or via CLI:
  ```bash
  oc get inferenceservice -n doclocal-ai-models
  ```

### Configuration Values Quick Reference

| Field                      | Qwen Value                        | BGE Value                     |
| -------------------------- | --------------------------------- | ----------------------------- |
| **Model URI**              | `hf://Qwen/Qwen2.5-1.5B-Instruct` | `hf://BAAI/bge-small-en-v1.5` |
| **Deployment name**        | `qwen-15b`                        | `bge-embedding`               |
| **Runtime**                | vLLM ServingRuntime               | vLLM ServingRuntime           |
| **Secret name**            | `huggingface-token`               | `huggingface-token`           |
| **Secret key**             | `HF_TOKEN`                        | `HF_TOKEN`                    |
| **CPU (request/limit)**    | 2/4 cores                         | 2/4 cores                     |
| **Memory (request/limit)** | 6-8/12-16 Gi                      | 2/4 Gi                        |
| **GPU**                    | 1 (recommended)                   | None                          |
| **Disk space**             | ~10 Gi                            | ~5 Gi                         |

### Resource Requirements Detail

**For Qwen (Text Generation):**

| Configuration         | CPU       | Memory  | GPU          | Disk  | Use Case                  |
| --------------------- | --------- | ------- | ------------ | ----- | ------------------------- |
| **Minimum** (CPU)     | 2/4 cores | 8/16 Gi | 0            | 10 Gi | Testing, low load         |
| **Recommended** (GPU) | 2/4 cores | 6/12 Gi | 1 (T4/L4)    | 10 Gi | Production (60% GPU util) |
| **High Performance**  | 4/8 cores | 8/16 Gi | 1 (A10/A100) | 20 Gi | High load, 90% GPU util   |

**For BGE (Embeddings):**

| Configuration   | CPU       | Memory | GPU | Disk | Use Case                   |
| --------------- | --------- | ------ | --- | ---- | -------------------------- |
| **Recommended** | 2/4 cores | 2/4 Gi | 0   | 5 Gi | CPU inference (sufficient) |

**Notes:**

- Request/Limit format: `request/limit` (e.g., 2/4 cores = 2 cores requested, 4 cores limit)
- First deployment requires downloading models from HuggingFace
- Qwen model: ~3 GB download
- BGE model: ~133 MB download

### Testing the Deployment

```bash
# Get endpoint URL
QWEN_URL=$(oc get inferenceservice qwen-15b -n doclocal-ai-models -o jsonpath='{.status.url}')

# Test with curl
curl -X POST "${QWEN_URL}/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "/mnt/models",
    "messages": [{"role": "user", "content": "Hello!"}],
    "max_tokens": 50
  }'
```

---

## 🔄 Next Steps

1. ✅ Deploy AI models (done with `ai-models/deploy.sh`)
2. ⏳ Deploy DocLocalAI application (future - in `application/`)
3. ⏳ Connect backend to AI model endpoints

---

**OpenShift AI Version**: 3.3  
**Last Updated**: 2026-11-25
