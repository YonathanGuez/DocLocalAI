# DocLocalAI Runbooks and Recommended Structure(MD or TXT)

This directory contains runbook documentation that gets indexed into the vector database for RAG (Retrieval-Augmented Generation).

## How It Works

1. **Add runbooks** as `.md` or `.txt` files to this directory
2. **Run the indexer** to chunk and embed the content
3. **Ask questions** in the DocLocalAI UI that will use these runbooks as context

## Indexing Runbooks

```bash
# Run the indexer (requires services to be running)
python3 scripts/index_runbooks.py
```

## Runbook Format

Runbooks should be markdown or text files containing:

- **Troubleshooting guides** (symptoms, diagnosis, solutions)
- **Operational procedures** (deployment steps, maintenance tasks)
- **Configuration examples** (YAML manifests, commands)
- **Best practices** (architecture patterns, security guidelines)

### Example Structure

```markdown
# Topic Title

## Problem/Scenario

### Symptoms

- Specific observable issues

### Diagnosis Steps

\`\`\`bash

# Commands to investigate

\`\`\`

### Solutions

1. Step-by-step resolution
2. Prevention measures
```

## Current Runbooks

- `openshift-pod-troubleshooting.md` - Pod issues (CrashLoopBackOff, Pending, etc.)
- `openshift-networking.md` - Network troubleshooting (services, routes, DNS)

## Adding Your Own Runbooks

1. Create a new `.md` file in this directory
2. Write your documentation
3. Run the indexer script
4. Test queries in the UI

The system automatically:

- Chunks content into ~500 character segments
- Generates embeddings using `nomic-embed-text`
- Stores in PostgreSQL with pgvector
- Retrieves relevant chunks during chat conversations

## Recommended Structure for Optimal RAG Performance

---

# [Title] - Main Topic Name

**Last Updated:** 2026-11-23  
**Category:** Infrastructure / Networking / Troubleshooting / etc.  
**Tags:** kubernetes, openshift, pods, debugging

## Overview

Brief 2-3 sentence summary of what this runbook covers.
This helps with contextual retrieval.

## Prerequisites

- Requirement 1
- Requirement 2
- Access needed: cluster-admin, specific namespace, etc.

## Problem / Use Case

Describe when to use this runbook:

- Symptom 1
- Symptom 2
- Error messages that lead here

## Solution / Steps

### Step 1: Diagnose the Issue

```bash
# Check pod status
kubectl get pods -n production

# View pod logs
kubectl logs <pod-name> -n production --tail=50
```

**Expected Output:**

```
NAME                     READY   STATUS    RESTARTS   AGE
app-deployment-abc123    1/1     Running   0          5m
```

### Step 2: Identify Root Cause

Check for common issues:

1. **Resource Limits:** Verify CPU/memory limits aren't exceeded
2. **Network Policies:** Ensure pods can communicate
3. **Image Pull:** Verify image exists and credentials are valid

### Step 3: Apply Fix

```bash
# Restart the pod
kubectl delete pod <pod-name> -n production

# Verify new pod is running
kubectl get pods -n production -w
```

## Validation

How to verify the fix worked:

- [ ] Pod status shows "Running"
- [ ] Application responds to health check: `curl http://app/health`
- [ ] No errors in logs: `kubectl logs <pod-name> --tail=20`

## Troubleshooting

### Issue: Pod stuck in CrashLoopBackOff

**Cause:** Container exits immediately after start

**Fix:**

```bash
# Check container logs for errors
kubectl logs <pod-name> --previous

# Describe pod for events
kubectl describe pod <pod-name>
```

### Issue: ImagePullBackOff

**Cause:** Cannot pull container image

**Fix:**

```bash
# Verify image exists
kubectl describe pod <pod-name> | grep Image

# Check image pull secrets
kubectl get secrets -n production
```

## Important Notes / Warnings

⚠️ **WARNING:** Do not run `kubectl delete deployment` in production without approval

💡 **TIP:** Always backup configurations before making changes

## Related Runbooks

- [Pod Networking Issues](./pod-networking.md)
- [Resource Quota Management](./resource-quotas.md)
- [Image Registry Access](./registry-access.md)

## References

- Official Kubernetes Docs: https://kubernetes.io/docs/concepts/workloads/pods/
- Internal Wiki: https://wiki.company.com/k8s-troubleshooting
- Runbook maintained by: Platform Team

---

# STRUCTURE GUIDELINES

## ✅ GOOD PRACTICES (for RAG optimization)

### 1. Use Clear Headers (H1, H2, H3)

```markdown
# Main Title (H1) - One per document

## Major Sections (H2) - Problem, Solution, Troubleshooting

### Subsections (H3) - Specific steps or scenarios
```

### 2. Code Blocks with Language Tags

`````markdown
````bash
kubectl get pods
\`\`\`

```yaml
apiVersion: v1
kind: Pod
\`\`\`
````
`````

`````

### 3. Lists for Steps or Prerequisites

```markdown
1. First step
2. Second step
   - Sub-item with detail
   - Another detail
3. Third step
```

### 4. Tables for Comparisons

```markdown
| Issue     | Cause          | Fix             |
| --------- | -------------- | --------------- |
| CrashLoop | Config error   | Check env vars  |
| ImagePull | Missing secret | Add pull secret |
```

### 5. Metadata at Top

```markdown
**Category:** Troubleshooting
**Tags:** kubernetes, pods, errors
**Last Updated:** 2026-11-23
```

### 6. Callouts for Important Info

```markdown
⚠️ **WARNING:** Dangerous operation ahead
💡 **TIP:** Helpful shortcut
✅ **SUCCESS:** Expected result
❌ **ERROR:** Common mistake
```

## ❌ AVOID (harder for RAG to parse)

### 1. No Structure

```markdown
Just write everything in one paragraph with no headers or breaks
and mix commands with explanations and have no clear sections...
```

### 2. No Code Formatting

```markdown
Run this command kubectl get pods and then do kubectl logs podname
to see the output and check if there are errors.
```

### 3. Ambiguous References

```markdown
"Use the command from above" (instead of repeating it)
"See the other runbook" (instead of naming it)
"As mentioned earlier" (instead of being explicit)
```

### 4. Inconsistent Formatting

```markdown
Some commands in `backticks`
Some commands in "quotes"
Some commands with no formatting at all
```

---

# EXAMPLE: MINIMAL RUNBOOK

If you want to keep it simple, this minimal structure works:

````markdown
# How to Restart a Pod

## Problem

Pod is stuck or not responding

## Solution

````bash
kubectl delete pod <pod-name> -n <namespace>
kubectl get pods -n <namespace>
\`\`\`

## Verify
Check pod status shows "Running" and app is accessible

---

# EXAMPLE: COMPREHENSIVE RUNBOOK

For complex procedures:

```markdown
# OpenShift Router Configuration

**Category:** Networking
**Last Updated:** 2026-11-23
**Tags:** openshift, router, haproxy, routes

## Overview
How to configure and troubleshoot OpenShift routers for external traffic.

## Prerequisites
- cluster-admin role
- Access to router namespace
- HAProxy knowledge helpful

## Architecture
[Diagram or description of router setup]

## Configuration Steps
[Detailed steps with commands]

## Troubleshooting Matrix

| Symptom | Check | Fix |
|---------|-------|-----|
| 503 errors | Backend pods | Scale deployment |
| SSL issues | Certificate | Renew cert |
| Timeout | Route config | Adjust timeout |

## Monitoring
Grafana dashboard: https://grafana.company.com/d/router-metrics

## References
- Internal docs: wiki.company.com/openshift-routers
- Maintained by: Platform Team (platform@company.com)
`````

````

---

# FILE NAMING CONVENTIONS

Good names for searchability:

```
✅ pod-restart-procedure.md
✅ troubleshooting-network-policies.md
✅ openshift-router-configuration.md
✅ database-backup-restore.md

❌ doc1.md
❌ notes.txt
❌ stuff.md
❌ TEMP_v2_final.md
```

---

# SUMMARY

## Minimum Required (works with current system):

- Plain text or Markdown format
- .md or .txt extension
- Clear command examples

## Recommended (works best with improvements):

- Structured headers (H1, H2, H3)
- Code blocks with language tags
- Metadata at top (category, tags, date)
- Lists for steps
- Tables for comparisons
- Clear section breaks

## Optimal (maximum RAG performance):

- All recommended items above, PLUS:
- Contextual retrieval metadata (auto-added by improvement)
- Cross-references to related runbooks
- Validation/verification steps
- Troubleshooting decision tree
- Version tracking in filename or header
````
