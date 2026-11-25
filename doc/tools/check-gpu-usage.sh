#!/bin/bash
# Quick script to check Qwen resource usage on OpenShift

NAMESPACE="doclocal-ai-models"
ISVC_NAME="qwen-15b"

echo "============================================"
echo "  Qwen 2.5 1.5B - Resource Usage Report"
echo "============================================"
echo

# Get the predictor pod name
POD=$(oc get pods -n $NAMESPACE -l serving.kserve.io/inferenceservice=$ISVC_NAME -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

if [ -z "$POD" ]; then
  echo "❌ No Qwen pod found in namespace: $NAMESPACE"
  exit 1
fi

echo "📦 Pod: $POD"
echo

# Check pod status
echo "📊 Pod Status:"
oc get pod $POD -n $NAMESPACE -o jsonpath='{.status.phase}' 2>/dev/null
echo
echo

# GPU Memory Usage
echo "🎮 GPU Memory Usage (nvidia-smi):"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
oc exec -n $NAMESPACE $POD -c kserve-container -- nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu,name --format=csv,noheader 2>/dev/null | while IFS=, read used total util name; do
  echo "GPU Model:        $name"
  echo "Memory Used:      $used"
  echo "Memory Total:     $total"
  echo "GPU Utilization:  $util"
done
echo

# vLLM Memory Allocation
echo "💾 vLLM Memory Breakdown:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
oc logs $POD -c kserve-container -n $NAMESPACE 2>/dev/null | \
  grep "model weights take\|the current vLLM instance" | tail -2
echo

# Resource Limits
echo "⚙️  Configured Resource Limits:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
oc get pod $POD -n $NAMESPACE -o json 2>/dev/null | \
  jq -r '.spec.containers[] | select(.name=="kserve-container") |
  "CPU Request:      \(.resources.requests.cpu // "not set")
CPU Limit:        \(.resources.limits.cpu // "not set")
Memory Request:   \(.resources.requests.memory // "not set")
Memory Limit:     \(.resources.limits.memory // "not set")
GPU:              \(.resources.limits."nvidia.com/gpu" // "0")"'
echo

# Model Configuration
echo "🤖 Model Configuration:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
oc logs $POD -c kserve-container -n $NAMESPACE 2>/dev/null | \
  grep -E "dtype=|max_seq_len=|gpu_memory_utilization=" | head -1 | \
  sed -E 's/.*dtype=([^,]+).*/Data Type:        \1/; s/.*max_seq_len=([0-9]+).*/Max Seq Length:   \1/; s/.*gpu_memory_utilization=([0-9.]+).*/GPU Utilization:  \1 (90%)/'
echo

# All GPU users
echo "📋 All Pods Using GPU in Cluster:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
oc get pods -A -o json 2>/dev/null | \
  jq -r '.items[] | select(.spec.containers[].resources.limits."nvidia.com/gpu" != null) |
  "\(.metadata.namespace)/\(.metadata.name)"'
echo

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Report complete!"
echo
echo "Quick commands:"
echo "  Watch GPU usage:  watch -n 2 'oc exec -n $NAMESPACE $POD -c kserve-container -- nvidia-smi'"
echo "  View logs:        oc logs -n $NAMESPACE $POD -c kserve-container --tail=50 -f"
echo "  Check status:     oc get inferenceservice $ISVC_NAME -n $NAMESPACE"
