#!/bin/bash
#
# Remove the DocLocalAI application stack from OpenShift (database, backend,
# frontend, secrets, configmaps, PVCs). Does NOT touch the AI models namespace
# (doclocal-ai-models) - run that teardown separately if you need it too.
#
set -eo pipefail

NAMESPACE="${1:-doclocal-ai}"
FORCE="${FORCE:-false}"
DELETE_NAMESPACE="${DELETE_NAMESPACE:-false}"

for arg in "$@"; do
    case "$arg" in
        --yes|-y) FORCE="true" ;;
        --delete-namespace) DELETE_NAMESPACE="true" ;;
    esac
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🗑️  DocLocalAI OpenShift Teardown"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if ! oc whoami &> /dev/null; then
    echo "❌ Not logged in to OpenShift"
    exit 1
fi

echo "✅ Logged in as: $(oc whoami)"
echo "🎯 Target namespace: $NAMESPACE"
echo ""

echo "📚 Step 1: Deleting indexer job..."
oc delete job doclocal-ai-runbook-indexer -n "$NAMESPACE" --ignore-not-found

echo "🎨 Step 2: Deleting frontend (Deployment, Service, Route)..."
oc delete deployment doclocal-ai-ui -n "$NAMESPACE" --ignore-not-found
oc delete service doclocal-ai-ui -n "$NAMESPACE" --ignore-not-found
oc delete route doclocal-ai-ui -n "$NAMESPACE" --ignore-not-found
echo ""

echo "⚙️  Step 3: Deleting backend (Deployment, Service)..."
oc delete deployment doclocal-ai-api -n "$NAMESPACE" --ignore-not-found
oc delete service doclocal-ai-api -n "$NAMESPACE" --ignore-not-found
echo ""

echo "🗄️  Step 4: Deleting database (StatefulSet, Service)..."
oc delete statefulset doclocal-ai-db -n "$NAMESPACE" --ignore-not-found
oc delete service doclocal-ai-db -n "$NAMESPACE" --ignore-not-found
echo ""

echo "🔐 Step 5: Deleting secrets & configmaps..."
oc delete secret doclocal-ai-secrets -n "$NAMESPACE" --ignore-not-found
oc delete secret yonig-robot-pull-secret -n "$NAMESPACE" --ignore-not-found
oc delete secret quay-pull-secret -n "$NAMESPACE" --ignore-not-found
oc delete configmap doclocal-ai-config -n "$NAMESPACE" --ignore-not-found
oc delete configmap doclocal-ai-db-init -n "$NAMESPACE" --ignore-not-found
oc delete configmap doclocal-ai-runbooks -n "$NAMESPACE" --ignore-not-found
echo ""

echo "💾 Step 6: Deleting PVCs (database data + uploaded runbooks)..."
oc delete pvc -n "$NAMESPACE" -l app=doclocal-ai-db --ignore-not-found
oc delete pvc db-data-doclocal-ai-db-0 -n "$NAMESPACE" --ignore-not-found
oc delete pvc doclocal-ai-runbooks-pvc -n "$NAMESPACE" --ignore-not-found
echo ""

if [ "$DELETE_NAMESPACE" = "true" ]; then
    echo "🏷️  Step 7: Deleting namespace '$NAMESPACE'..."
    oc delete namespace "$NAMESPACE" --ignore-not-found
    echo ""
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Teardown complete"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Remaining resources in '$NAMESPACE' (should be empty unless --delete-namespace was skipped):"
oc get all,pvc,secret,configmap -n "$NAMESPACE" 2>&1 || true
echo ""
echo "Note: the AI models namespace (doclocal-ai-models) was NOT touched."
echo "Redeploy with: ./scripts/deploy-app.sh $NAMESPACE"
