#!/bin/bash
#
# Master deployment script - deploys everything in order
#
set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 DocLocalAI - Complete Stack Deployment"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if logged in
if ! oc whoami &> /dev/null; then
    echo "❌ Not logged in to OpenShift"
    echo ""
    echo "Please login first:"
    echo "  oc login --token=<your-token> --server=<your-server>"
    exit 1
fi

echo "✅ Logged in as: $(oc whoami)"
echo ""

# Step 1: Deploy AI Models
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 STEP 1/2: Deploying AI Models"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -z "${HF_TOKEN}" ]; then
  echo "⚠️  HF_TOKEN not set - skipping AI models deployment"
  echo "   Set HF_TOKEN and run: ./scripts/deploy-models.sh"
  echo ""
else
  "$SCRIPT_DIR/deploy-models.sh"
  echo ""
fi

# Step 2: Deploy Application Stack
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎯 STEP 2/2: Deploying Application Stack"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

"$SCRIPT_DIR/deploy-app.sh"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ DEPLOYMENT COMPLETE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
