# Archive - Deprecated Content

This directory contains deprecated deployment approaches and old documentation that are **no longer used** but kept for historical reference.

---

## 📂 Contents

### `inferenceservice/` - Old InferenceService API
**Deprecated**: November 2024  
**Replaced by**: LLMInferenceService (v1alpha2)

Old deployment approach using KServe's `InferenceService` v1beta1 API with manual `ServingRuntime` definitions.

**Why deprecated:**
- Required manual ServingRuntime YAML files
- Manual vLLM parameter configuration
- UI showed "Unknown" deployment resource
- No hardware profile integration

**Current approach:**
- Uses `LLMInferenceService` v1alpha2
- Built-in llm-d runtime (auto-configures vLLM)
- Full OpenShift AI UI integration
- Hardware profile support

**Files in this directory:**
```
inferenceservice/
├── bge-embedding-service.yaml      # Old BGE embedding deployment
├── qwen-generation-service.yaml    # Old Qwen LLM deployment
├── vllm-runtime-embedding.yaml     # Manual embedding runtime
├── vllm-runtime-generation.yaml    # Manual generation runtime
└── deploy-old.sh                   # Old deployment script
```

**Reference**: See `../TROUBLESHOOTING.md` Issue 5-9 for migration details.

---

### `check-gpu-usage.sh`
Helper script for checking GPU memory usage during early testing.

**Usage:**
```bash
./check-gpu-usage.sh
```

---

### `DEPLOY_QWEN.md`
Early deployment documentation for Qwen model testing.

**Superseded by**: `../README.md` (current deployment guide)

---

### `FILE_NAMING.md`
Documentation on file naming conventions explored during development.

---

## ⚠️ Important Notes

1. **Don't use these files for new deployments**
   - Use the current files in `../ai-models/` and `../application/`
   - Refer to `../README.md` for deployment instructions

2. **Why keep this?**
   - Historical reference
   - Understanding evolution of the deployment approach
   - Troubleshooting legacy issues if needed

3. **Safe to delete?**
   - Yes, if you don't need historical reference
   - Current deployment doesn't depend on anything here
   - All working approaches are documented in TROUBLESHOOTING.md

---

## 🔗 See Also

- [Current README](../README.md) - Current deployment guide
- [TROUBLESHOOTING](../TROUBLESHOOTING.md) - Issues 5-9 explain the migration
- [AI Models](../ai-models/) - Current LLMInferenceService deployments
- [Application](../application/) - Current application stack
