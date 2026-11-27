#!/usr/bin/env bash
# Runs the k6 load tests inside a container (grafana/k6), attached to the
# same podman network as the app, so nothing is installed on the host and
# traffic goes service-to-service (api:8000, ollama:11434) instead of via
# the host port mapping.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NETWORK="${NETWORK:-doclocalai_default}"
K6_IMAGE="${K6_IMAGE:-ghcr.io/grafana/k6:latest}"
COOLDOWN_SECONDS="${COOLDOWN_SECONDS:-20}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
RESULTS_DIR="$SCRIPT_DIR/results/$TIMESTAMP"
mkdir -p "$RESULTS_DIR"

echo "==> Verifying app containers are up..."
for c in api ollama db; do
  if ! podman ps --format '{{.Names}}' | grep -qx "$c"; then
    echo "Container '$c' is not running. Start the app first (podman-compose up / compose up)." >&2
    exit 1
  fi
done

echo "==> Pulling $K6_IMAGE (skips if already present)..."
podman pull -q "$K6_IMAGE" >/dev/null

run_k6() {
  local name="$1" script="$2"; shift 2
  local env_args=("$@")
  echo ""
  echo "=== $name ==="
  podman run --rm \
    --network "$NETWORK" \
    -v "$SCRIPT_DIR/k6:/scripts:ro,Z" \
    -w /scripts \
    "${env_args[@]}" \
    "$K6_IMAGE" run \
      "$script" \
    2>&1 | tee "$RESULTS_DIR/${name}.log"
  echo "--- cooling down ${COOLDOWN_SECONDS}s before next test ---"
  sleep "$COOLDOWN_SECONDS"
}

# 1) Baseline: web server overhead only, no DB/RAG/LLM.
run_k6 "01_health_baseline" "health_baseline.js" \
  -e "BASE_URL=http://api:8000"

# 2) Pure LLM generation ceiling (bypasses the app entirely).
run_k6 "02_ollama_llm_bench" "ollama_raw_bench.js" \
  -e "OLLAMA_URL=http://ollama:11434" \
  -e "MODEL=${LLM_MODEL_NAME:-qwen2.5:0.5b}"

# 3) Pure embedding model ceiling (bypasses the app entirely).
run_k6 "03_ollama_embedding_bench" "embedding_bench.js" \
  -e "OLLAMA_URL=http://ollama:11434" \
  -e "EMBED_MODEL=${EMBEDDING_MODEL_NAME:-nomic-embed-text}"

# 4) Full end-to-end RAG+LLM chat load test (the real-world number).
run_k6 "04_chat_load_test" "chat_load_test.js" \
  -e "BASE_URL=http://api:8000"

echo ""
echo "==> All runs complete. Results in: $RESULTS_DIR"
echo "==> Capturing container resource usage snapshot..."
podman stats --no-stream > "$RESULTS_DIR/podman_stats_after.txt" || true

echo ""
echo "Done. Review $RESULTS_DIR/*.log for the full k6 summary of each test."
