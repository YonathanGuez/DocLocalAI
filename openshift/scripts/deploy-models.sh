#!/bin/bash
#
# Deploy LLMInferenceService models (NEW API with UI integration)
# This replaces the old InferenceService deployment
#

set -eo pipefail

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
if oc get namespace doclocal-ai-models &>/dev/null; then
  echo "Namespace already exists"
else
  oc create namespace doclocal-ai-models
fi
echo ""

# Check that the inference gateway authorizes routes from our namespace
GATEWAY_NAME="openshift-ai-inference"
GATEWAY_NS="openshift-ingress"
TARGET_NS="doclocal-ai-models"

echo "🔎 Checking gateway '$GATEWAY_NAME' authorizes namespace '$TARGET_NS'..."
ALLOWED_NAMESPACES=$(oc get gateway "$GATEWAY_NAME" -n "$GATEWAY_NS" \
  -o jsonpath='{.spec.listeners[0].allowedRoutes.namespaces.selector.matchExpressions[0].values}' 2>/dev/null)

if echo "$ALLOWED_NAMESPACES" | grep -q "\"$TARGET_NS\""; then
  echo "✅ Gateway already authorizes namespace '$TARGET_NS'"
else
  echo "⚠️  Namespace '$TARGET_NS' not authorized on gateway yet, patching..."
  oc patch gateway "$GATEWAY_NAME" -n "$GATEWAY_NS" --type=json -p='[
    {
      "op": "add",
      "path": "/spec/listeners/0/allowedRoutes/namespaces/selector/matchExpressions/0/values/-",
      "value": "'"$TARGET_NS"'"
    }
  ]' 2>/dev/null && echo "✅ Gateway patched to authorize '$TARGET_NS'" \
    || echo "❌ Gateway patch failed (may not exist or insufficient permissions)"
fi
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
