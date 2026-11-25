#!/bin/bash
# Automatically create or update the runbooks ConfigMap from the runbooks directory

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
NAMESPACE="doclocal-ai"
CONFIGMAP_NAME="doclocal-ai-runbooks"
# Sample runbooks are at repo root
RUNBOOKS_DIR="$SCRIPT_DIR/../../runbooks"

echo "Creating ConfigMap '$CONFIGMAP_NAME' in namespace '$NAMESPACE'..."

# Check if runbooks directory exists
if [ ! -d "$RUNBOOKS_DIR" ]; then
    echo "Error: Runbooks directory not found at $RUNBOOKS_DIR"
    exit 1
fi

# Check if directory has any files
if [ -z "$(ls -A $RUNBOOKS_DIR)" ]; then
    echo "Warning: Runbooks directory is empty"
    exit 1
fi

# Create or replace the ConfigMap
oc create configmap "$CONFIGMAP_NAME" \
    --from-file="$RUNBOOKS_DIR" \
    --namespace="$NAMESPACE" \
    --dry-run=client -o yaml | oc apply -f -

echo "✓ ConfigMap created/updated successfully!"
echo "  Namespace: $NAMESPACE"
echo "  ConfigMap: $CONFIGMAP_NAME"
echo "  Source: $RUNBOOKS_DIR"
echo "  Files:"
ls -1 "$RUNBOOKS_DIR" | sed 's/^/    - /'
