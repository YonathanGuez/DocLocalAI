#!/bin/bash
#
# Wait for LLMInferenceServices to become Ready before deploying the app
#
set -e

MODEL_NS="doclocal-ai-models"
TIMEOUT="${MODEL_READY_TIMEOUT:-600s}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⏳ Waiting for AI Models to become Ready"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if ! oc get llminferenceservice -n "$MODEL_NS" &>/dev/null; then
  echo "❌ ERROR: no LLMInferenceServices found in namespace '$MODEL_NS'"
  echo "   Did deploy-models.sh run successfully?"
  exit 1
fi

echo "Waiting up to $TIMEOUT for all LLMInferenceServices in '$MODEL_NS' to be Ready..."
echo ""

if oc wait --for=condition=Ready llminferenceservice --all -n "$MODEL_NS" --timeout="$TIMEOUT"; then
  echo ""
  echo "✅ All models are Ready"
  oc get llminferenceservice -n "$MODEL_NS"
else
  echo ""
  echo "❌ Timed out waiting for models to become Ready"
  echo ""
  oc get llminferenceservice -n "$MODEL_NS"
  exit 1
fi
echo ""
