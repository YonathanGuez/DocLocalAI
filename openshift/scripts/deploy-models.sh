#!/bin/bash
#
# Deploy LLMInferenceService models (NEW API with UI integration)
# This replaces the old InferenceService deployment
#

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
MODELS_DIR="$SCRIPT_DIR/../ai-models"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 DEPLOYING LLMINFERENCESERVICE MODELS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check HF_TOKEN is configured
if [ -z "${HF_TOKEN}" ]; then
  echo "❌ ERROR: HF_TOKEN is not configured!"
  echo ""
  echo "Please set your HuggingFace token:"
  echo "  export HF_TOKEN=hf_your_token_here"
  echo ""
  echo "Get a token from: https://huggingface.co/settings/tokens"
  exit 1
fi

echo "✅ HF_TOKEN is configured"
echo ""

# Create namespace if it doesn't exist
echo "📦 Ensuring namespace exists..."
oc create namespace doclocal-ai-models 2>/dev/null || echo "Namespace already exists"
echo ""

# Create HuggingFace token secret
echo "🔐 Creating HuggingFace token secret..."
oc create secret generic huggingface-token \
  --from-literal=HF_TOKEN="${HF_TOKEN}" \
  --namespace=doclocal-ai-models \
  --dry-run=client -o yaml | oc apply -f -
echo ""

# Create connections (URI type)
echo "🔗 Creating model connections..."
oc apply -f $MODELS_DIR/qwen-connection.yaml
oc apply -f $MODELS_DIR/bge-connection.yaml
echo ""

# Deploy LLMInferenceServices
echo "🤖 Deploying Qwen LLM (text generation)..."
oc apply -f $MODELS_DIR/qwen-llm-service.yaml
echo ""

echo "📊 Deploying BGE LLM (embeddings)..."
oc apply -f $MODELS_DIR/bge-llm-service.yaml
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ DEPLOYMENT STARTED"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Check status with:"
echo "  oc get llminferenceservice -n doclocal-ai-models"
echo ""
echo "Watch pods:"
echo "  oc get pods -n doclocal-ai-models -w"
echo ""
echo "View in UI:"
echo "  OpenShift AI Dashboard → Project → doclocal-ai-models → Deployments"
echo ""
