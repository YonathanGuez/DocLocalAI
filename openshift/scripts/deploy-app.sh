#!/bin/bash
set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 DocLocalAI OpenShift Deployment"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
APP_DIR="$SCRIPT_DIR/../application"
NAMESPACE="${1:-doclocal-ai}"

# Check if logged in
if ! oc whoami &> /dev/null; then
    echo "❌ Not logged in to OpenShift"
    echo ""
    echo "Please login first:"
    echo "  oc login --token=<your-token> --server=<your-server>"
    exit 1
fi

echo "✅ Logged in as: $(oc whoami)"
echo "🎯 Target namespace: $NAMESPACE"
echo ""

# Check if namespace exists before creating it
if oc get namespace $NAMESPACE &>/dev/null; then
    echo "   Namespace '$NAMESPACE' already exists"
else
    echo "   Creating namespace '$NAMESPACE'..."
    oc create namespace $NAMESPACE
fi
echo ""

# Step 0: Quay.io credentials
echo "📦 Step 0: Quay.io credentials..."

# Check if secret already exists
if oc get secret yonig-robot-pull-secret -n $NAMESPACE &>/dev/null; then
    echo "   ✅ Quay robot pull secret already exists"
else
    echo ""
    read -p "Enter your Quay.io username: " QUAY_USERNAME
    read -p "Enter your Quay.io password/robot token: " -s QUAY_PASSWORD
    echo ""
    echo ""

    if [ -z "$QUAY_USERNAME" ] || [ -z "$QUAY_PASSWORD" ]; then
        echo "❌ Both username and password are required!"
        exit 1
    fi

    echo "   Creating Quay robot pull secret..."
    oc create secret docker-registry yonig-robot-pull-secret \
      --docker-server=quay.io \
      --docker-username="$QUAY_USERNAME" \
      --docker-password="$QUAY_PASSWORD" \
      -n $NAMESPACE \
      --dry-run=client -o yaml | oc apply -f -

    echo "   ✅ Quay robot pull secret created"
fi
echo ""

# Step 1: Set active project
echo "📦 Step 1: Setting active project..."
oc project $NAMESPACE

echo ""

# Step 2: Deploy secrets & config
echo "🔐 Step 2: Deploying secrets & configuration..."

# Generate secrets.yaml with random password if template exists
echo "   Generating secrets from template..."

# Remove any old secret first so a leftover one from a previous run can't
# linger, then generate a fresh DB password.
oc delete secret "${NAMESPACE}-secrets" -n "$NAMESPACE" --ignore-not-found

DB_PASSWORD=$(openssl rand -hex 16)

# Auto-discover AI model endpoints
echo "   🔍 Discovering AI model endpoints..."

AI_MODELS_NAMESPACE="doclocal-ai-models"

# Get Qwen LLM endpoint
QWEN_URL=$(oc get svc qwen-llm-kserve-workload-svc  -n doclocal-ai-models -o jsonpath='{.metadata.name}.{.metadata.namespace}.svc.cluster.local:{.spec.ports[0].port}' 2>/dev/null || echo "")
if [ -z "$QWEN_URL" ]; then
    echo "   ⚠️  Warning: Could not find qwen-llm endpoint"
    echo "      Make sure AI models are deployed in namespace: $AI_MODELS_NAMESPACE"
    QWEN_URL="<LLM_ENDPOINT_URL>"
else
    QWEN_URL="https://${QWEN_URL}/v1"
    echo "   ✅ Found Qwen: $QWEN_URL"
fi

# Get BGE Embedding endpoint
BGE_URL=$(oc get svc bge-llm-kserve-workload-svc -n $AI_MODELS_NAMESPACE -o jsonpath='{.metadata.name}.{.metadata.namespace}.svc.cluster.local:{.spec.ports[0].port}' 2>/dev/null || echo "")
if [ -z "$BGE_URL" ]; then
    echo "   ⚠️  Warning: Could not find bge-llm endpoint"
    echo "      Make sure AI models are deployed in namespace: $AI_MODELS_NAMESPACE"
    BGE_URL="<EMBEDDING_ENDPOINT_URL>"
else
    BGE_URL="https://${BGE_URL}/v1"
    echo "   ✅ Found BGE: $BGE_URL"
fi

# Generate secrets with discovered endpoints
cat $APP_DIR/template-secrets.yaml | \
    sed "s/<NAMESPACE>/$NAMESPACE/g" | \
    sed "s/<CHANGE_PASSWORD>/${DB_PASSWORD}/g" | \
    sed "s|<LLM_ENDPOINT_URL>|${QWEN_URL}|g" | \
    sed "s/<LLM_MODEL_NAME>/qwen-llm/g" | \
    sed "s|<EMBEDDING_ENDPOINT_URL>|${BGE_URL}|g" | \
    sed "s/<EMBEDDING_MODEL_NAME>/bge-llm/g" \
    > $APP_DIR/generated-secrets.yaml

oc apply -f $APP_DIR/generated-secrets.yaml
echo "   ✅ Generated and applied secrets"

oc apply -f $APP_DIR/configmap.yaml
oc apply -f $APP_DIR/db-init-configmap.yaml
echo "   ✅ ConfigMaps applied"

echo ""

# Step 3: Deploy database
echo "🗄️  Step 3: Deploying PostgreSQL database..."
oc apply -f $APP_DIR/database.yaml

echo ""

# Step 4: Wait for database
echo "⏳ Step 4: Waiting for database to be ready..."
echo "   This may take 1-2 minutes..."
if ! oc rollout status statefulset/doclocal-ai-db -n $NAMESPACE --timeout=500s; then
    echo "   ❌ Database did not become ready - aborting deployment"
    exit 1
fi

echo ""

# Step 5: Deploy backend
echo "⚙️  Step 5: Deploying backend API..."
oc apply -f $APP_DIR/backend.yaml

echo ""

# Step 6: Deploy frontend
echo "🎨 Step 6: Deploying frontend UI..."
oc apply -f $APP_DIR/frontend.yaml

echo ""

# Step 7: Run runbook indexer (optional)
if [ -f "$APP_DIR/runbook-indexer-job.yaml" ]; then
    echo "📚 Step 7: Running runbook indexer job..."
    oc delete job doclocal-ai-runbook-indexer -n $NAMESPACE 2>/dev/null || true
    oc apply -f $APP_DIR/runbook-indexer-job.yaml
else
    echo "📚 Step 7: Skipping runbook indexer (file not found)"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Deployment complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Get route
echo "🔍 Checking application route..."
sleep 5
ROUTE=$(oc get route doclocal-ai-ui -n $NAMESPACE -o jsonpath='{.spec.host}' 2>/dev/null || echo "")

if [ -n "$ROUTE" ]; then
    echo "🌐 Application URL: https://$ROUTE"
else
    echo "⏳ Route not ready yet. Check with:"
    echo "   oc get route doclocal-ai-ui -n $NAMESPACE"
fi

echo ""
echo "📊 Check deployment status:"
echo "   oc get pods -n $NAMESPACE"
echo ""
echo "📝 View logs:"
echo "   oc logs -f deployment/doclocal-ai-api -n $NAMESPACE"
echo "   oc logs -f deployment/doclocal-ai-ui -n $NAMESPACE"
echo ""
echo "🔗 AI Model Endpoints auto-discovered:"
if [ -n "$QWEN_URL" ] && [ "$QWEN_URL" != "<LLM_ENDPOINT_URL>" ]; then
    echo "   LLM: $QWEN_URL"
else
    echo "   LLM: Not found - check ai-models deployment"
fi
if [ -n "$BGE_URL" ] && [ "$BGE_URL" != "<EMBEDDING_ENDPOINT_URL>" ]; then
    echo "   Embeddings: $BGE_URL"
else
    echo "   Embeddings: Not found - check ai-models deployment"
fi
echo ""
