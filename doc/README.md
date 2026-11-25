# Documentation & Archive

This directory contains documentation, screenshots, and archived/deprecated content.

---

## 📂 Contents

### `TROUBLESHOOTING.md` ⭐
Complete troubleshooting guide for all deployment issues encountered during development and production.

**What's inside:**
- 20 documented issues with solutions
- PostgreSQL, SSL, networking, GPU issues
- Database schema problems
- Runbook indexing fixes
- Detailed error logs and diagnostic commands

**Topics covered:**
- Issues 1-9: AI Model Deployment (InferenceService → LLMInferenceService migration)
- Issues 10-15: Application Stack (Database, Backend, SSL, Vector dimensions)
- Issues 16-20: Runbook Upload & Indexing

### `screen.png`
Screenshot of the DocLocalAI application interface (UI demo).

### `tools/`
Reusable utility scripts for monitoring and managing deployments.

**Available tools:**
- `check-gpu-usage.sh` - Generic GPU monitoring for any namespace/service

See [tools/README.md](tools/README.md) for detailed usage.

### `archive-openshift/`
Archived OpenShift deployment files that are **no longer used** but kept for historical reference.

**Contains:**
- **inferenceservice/** - Old InferenceService API deployment (deprecated Nov 2024)
  - Replaced by LLMInferenceService v1alpha2
  - See main TROUBLESHOOTING.md Issues 5-9 for migration details
- **check-gpu-usage.sh** - GPU memory monitoring script
- **DEPLOY_QWEN.md** - Early deployment documentation
- **FILE_NAMING.md** - File naming conventions notes

**Why archived:**
- InferenceService v1beta1 required manual ServingRuntime configuration
- New LLMInferenceService has built-in llm-d runtime with auto-configuration
- Better UI integration in OpenShift AI Dashboard

---

## 🔗 Active Documentation

For current deployment and usage:

| Document | Location | Purpose |
|----------|----------|---------|
| **Main README** | `/README.md` | Project overview |
| **OpenShift Deployment** | `/openshift/README.md` | Current deployment guide |
| **Troubleshooting** | `/openshift/TROUBLESHOOTING.md` | Debugging & issues |
| **Scripts** | `/openshift/scripts/README.md` | Deployment automation |

---

## ⚠️ Note

**Don't use archived files for new deployments!**

All archived content is deprecated. Use the current files in:
- `/openshift/ai-models/` - AI model deployments
- `/openshift/application/` - Application stack
- `/openshift/scripts/` - Deployment scripts
