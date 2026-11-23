# DocLocalAI RAG Strategy

DocLocalAI automatically adapts its behavior based on the LLM model size to prevent hallucinations.

## 🧠 Automatic Strategy Selection

The system chooses one of two strategies:

### **Raw Retrieval Mode** (Small Models)

Used for: `0.5b`, `1b`, `1.5b`, `tiny`, `small` models

**What it does:**

- Shows raw runbook sections directly to the user
- **Zero LLM synthesis** - no risk of hallucination
- Fast and accurate

**Example response:**

````
I found these relevant sections from the runbooks:

📄 openshift-pod-troubleshooting.md

## Pod CrashLoopBackOff
### Diagnosis Steps
```bash
oc describe pod <pod-name>
oc logs <pod-name> --previous
````

📚 Source: openshift-pod-troubleshooting.md

```

### **Synthesis Mode** (Large Models)
Used for: `3b`, `7b`, `13b`, `70b` and larger models

**What it does:**
- LLM reads runbooks and synthesizes a conversational answer
- More natural, contextualized responses
- Requires larger model to avoid hallucination

**Example response:**
```

To troubleshoot a CrashLoopBackOff issue, follow these steps:

1. Check pod status: `oc describe pod <pod-name>`
2. View previous logs: `oc logs <pod-name> --previous`
3. Check for resource limits or health check failures

📚 Source: openshift-pod-troubleshooting.md

````

## ⚙️ Configuration

Set `RAG_STRATEGY` environment variable:

```bash
# Auto-detect based on model name (default)
RAG_STRATEGY=auto

# Always use raw retrieval (safest)
RAG_STRATEGY=raw

# Always use LLM synthesis (requires 3B+ model)
RAG_STRATEGY=synthesis
````

## 🔄 Switching Models

### Current Setup (Small Model)

```yaml
LLM_MODEL_NAME: qwen2.5:0.5b # 500MB, fast, raw mode
```

**Behavior:** Shows raw runbook chunks (no hallucination)

### Upgrade to Medium Model

```bash
docker exec DocLocalAI-ollama ollama pull qwen2.5:3b
```

```yaml
LLM_MODEL_NAME: qwen2.5:3b # 2GB, synthesis mode
```

**Behavior:** LLM synthesizes conversational answers

### Upgrade to Large Model

```bash
docker exec DocLocalAI-ollama ollama pull qwen2.5:7b
```

```yaml
LLM_MODEL_NAME: qwen2.5:7b # 4GB, best synthesis
```

**Behavior:** Best quality conversational answers

## 📊 Model Comparison

| Model        | Size  | RAM  | Mode      | Quality    | Speed  |
| ------------ | ----- | ---- | --------- | ---------- | ------ |
| qwen2.5:0.5b | 400MB | ~1GB | Raw       | ⭐⭐       | ⚡⚡⚡ |
| qwen2.5:3b   | 2GB   | ~4GB | Synthesis | ⭐⭐⭐⭐   | ⚡⚡   |
| qwen2.5:7b   | 4GB   | ~8GB | Synthesis | ⭐⭐⭐⭐⭐ | ⚡     |

## 🎯 Recommendations

- **Dev/Testing:** Keep `0.5b` with raw mode (fast, accurate)
- **Production:** Use `3b` or `7b` for better UX (if you have RAM)
- **Low RAM systems:** Stick with `0.5b` raw mode

## 🔍 How Detection Works

The system checks the model name for patterns:

- Contains `0.5b`, `1b`, `1.5b`, `tiny`, `small` → **Raw mode**
- Otherwise → **Synthesis mode**

## Strategy :

### Option 1: Auto (Current - Recommended)

RAG_STRATEGY: "auto"

- ✅ Smart detection based on model size
- ✅ 0.5b, 1b, 1.5b → Raw mode (no hallucination)
- ✅ 3b, 7b+ → Synthesis mode (conversational)

### Option 2: Always Raw (Safest)

RAG_STRATEGY: "raw"

- ✅ Always shows raw runbook chunks
- ✅ Zero hallucination guaranteed
- ✅ Works with any model size

### Option 3: Always Synthesis

RAG_STRATEGY: "synthesis"

- ⚠️ Requires 3B+ model to avoid hallucinations
- ✅ Conversational responses
- ✅ LLM explains and synthesizes
