#!/bin/bash
# Deployment script for Qwen 2.5 1.5B + BGE Embeddings on OpenShift AI
# Usage: HF_TOKEN="hf_xxx" ./deploy.sh

set -e

NAMESPACE="doclocal-ai-models"

echo "============================================"
echo "  DocLocalAI - OpenShift Deployment"
echo "============================================"
echo

# Verify HF_TOKEN is configured
if [ -z "${HF_TOKEN}" ]; then
  echo "❌ ERROR: HF_TOKEN is not configured!"
  echo ""
  echo "Please set your HuggingFace token before running this script:"
  echo "  export HF_TOKEN='hf_your_token_here'"
  echo ""
  echo "Or run with:"
  echo "  HF_TOKEN='hf_your_token_here' ./deploy.sh"
  echo ""
  echo "Get your token at: https://huggingface.co/settings/tokens"
  exit 1
fi

echo "✅ HF_TOKEN is configured"
echo ""

# Create namespace
echo "📦 Creating namespace: $NAMESPACE"
oc create namespace $NAMESPACE 2>/dev/null || echo "Namespace already exists"

# Create HuggingFace secret
echo "🔑 Creating HuggingFace token secret..."
oc create secret generic huggingface-token \
  --from-literal=HF_TOKEN="${HF_TOKEN}" \
  -n $NAMESPACE \
  --dry-run=client -o yaml | oc apply -f -

# Add namespace to gateway (optional, may fail)
echo ""
echo "🌐 Adding namespace to gateway (optional)..."
oc patch gateway openshift-ai-inference -n openshift-ingress --type=json -p='[
  {
    "op": "add",
    "path": "/spec/listeners/0/allowedRoutes/namespaces/selector/matchExpressions/0/values/-",
    "value": "'"$NAMESPACE"'"
  }
]' 2>/dev/null || echo "⚠️  Gateway patch failed (may already exist or gateway not available)"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Deploying Runtimes"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Deploy vLLM runtime (for Qwen - text generation)
echo ""
echo "🔧 Deploying vLLM runtime (GPU, 60% utilization)..."
oc apply -f vllm-runtime-generation.yaml

# Deploy Text-Embeddings-Inference runtime (for BGE - embeddings)
echo ""
echo "🔧 Deploying Text-Embeddings-Inference runtime (CPU)..."
oc apply -f vllm-runtime-embedding.yaml

echo ""
echo "⏳ Waiting 5 seconds for runtimes to register..."
sleep 5

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Deploying Models"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Deploy Qwen (text generation)
echo ""
echo "🤖 Deploying Qwen 2.5 1.5B (text generation)..."
oc apply -f qwen-generation-service.yaml

# Deploy BGE embeddings
echo ""
echo "📝 Deploying BGE-Small-EN-v1.5 (embeddings)..."
oc apply -f bge-embedding-service.yaml

echo ""
echo "✅ Deployment initiated!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⏳ Models will take 2-5 minutes to download and start"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
