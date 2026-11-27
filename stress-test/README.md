# Stress Testing DocLocalAI

Load-tests the running podman stack (`api`, `ollama`, `db`) to find concurrent-user
limits, throughput, and failure points. Runs entirely in containers via
[k6](https://k6.io) — nothing is installed on the host, and traffic goes
container-to-container (`api:8000`, `ollama:11434`) on the `doclocalai_default`
network instead of through the host port mapping.

## Prerequisites

The app must already be running (`podman ps` should show `api`, `ollama`, `db`
as `Up`). Internet access is needed once, to pull `grafana/k6`.

## Run everything

```bash
cd stress-test
./run.sh
```

This runs four tests in sequence, each ramping concurrency up in stages, with
a cooldown pause between each (`COOLDOWN_SECONDS`, default 20s, so CPU/fans
get a breather), and saves the full k6 text summary of each under
`stress-test/results/<timestamp>/*.log`:

| #   | Script                | What it isolates                                                                                                              | Default peak concurrency |
| --- | --------------------- | ----------------------------------------------------------------------------------------------------------------------------- | ------------------------ |
| 1   | `health_baseline.js`  | Bare FastAPI/uvicorn overhead — no DB, no RAG, no LLM.                                                                        | 40                       |
| 2   | `ollama_raw_bench.js` | Pure LLM generation ceiling (hits Ollama directly).                                                                           | 6                        |
| 3   | `embedding_bench.js`  | Pure embedding-model ceiling (every chat call embeds the query at least once).                                                | 10                       |
| 4   | `chat_load_test.js`   | **The real number**: full `/api/chat` path — retrieval, hybrid search, reranker, Postgres, and (conditionally) LLM synthesis. | 15                       |

These defaults are intentionally conservative (a local laptop running an LLM
is not a server — it gets hot fast). Override `STAGES` per script, or
`COOLDOWN_SECONDS`, if your machine can take more or you want to push to an
actual breaking point; see below.

Each simulated "user" in test 4 keeps one persistent session (its own UUID)
and asks a random question drawn from the sample runbooks, with 1-3s think
time between messages, so the server sees realistic session/history load
too (not just raw request spam).

## Run a single test / customize

```bash
podman run --rm --network doclocalai_default \
  -v "$PWD/k6:/scripts:Z" -w /scripts \
  -e BASE_URL=http://api:8000 \
  -e STAGES='[{"duration":"30s","target":50}]' \
  ghcr.io/grafana/k6:latest run chat_load_test.js
```

`STAGES` (JSON array of `{duration, target}`) overrides the ramp profile for
any of the four scripts if you want to push further or test a specific
concurrency level directly.

## How to read the results

- **`chat_errors` rate** (test 4): fraction of requests that got a non-200
  response or an unparseable body. This is your practical "breaking point" —
  note the VU stage where this starts climbing above ~5%.
- **`chat_duration_ms` p95/p90** (test 4): response time users actually feel.
  Compare it against `llm_gen_duration_ms` (test 2) and `embedding_duration_ms`
  (test 3) to see how much of the latency is the app/retrieval vs. the model
  itself.
- **`http_req_failed`** (test 1): if the bare `/health` baseline degrades
  before the RAG path does, something in uvicorn/networking is the limit, not
  the LLM.
- **`chat_timeouts` / `chat_rate_limited_429` / `chat_server_errors_5xx`**:
  counters that tell you _how_ requests failed (timeout vs. 429 vs. crash),
  not just that they did.
- `results/<ts>/podman_stats_after.txt`: CPU/memory per container right
  after the run, useful to confirm which container (usually `ollama`) was
  pegged at the breaking point.

## Known architectural limits to expect (read before you panic at the numbers)

These come from reading the app's code, not from running it — the actual
numbers from `run.sh` will confirm or refute them:

- **Single Ollama instance does both embedding and generation, CPU-only
  by default.** It's one process serving both models — this is almost
  always the first bottleneck, not FastAPI.
- **DB pool is capped at 10 connections**
  (`db_pool_max_size` in `app/backend/app/config.py`). Each `/api/chat` call
  holds one connection for the whole retrieval+LLM+save sequence. Expect
  queuing/timeouts once concurrent in-flight chats exceed ~10, independent of
  Ollama's own limits.
- **Single uvicorn worker, no `--workers` flag** (see
  `app/backend/Dockerfile`). Sync route handlers run in Starlette's default
  thread pool (40 threads), so very high concurrency queues at the app layer
  too, before it reaches the DB or Ollama.
- **Rate limiting is configured but not wired up**: `slowapi`/`Limiter` is
  set up in `app/backend/app/middleware/security.py` with
  `rate_limit_per_minute: 60`, but no route actually has a `@limiter.limit(...)`
  decorator, so today nothing throttles `/api/chat`. The limits you'll observe
  are purely resource-exhaustion limits (CPU/DB pool), not an intentional
  rate limiter kicking in.
- **With the current config (`RAG_STRATEGY=auto` + `qwen2.5:0.5b`), most
  chat turns skip LLM generation entirely.** `auto` picks "Raw Mode" for
  models matching `0.5b/1b/1.5b/tiny/small`, which returns only the matched
  source filenames — no LLM completion call
  (see `generate_response` in `app/backend/app/services/chat_service.py`).
  The LLM _is_ still called for ambiguous-query rewriting when history needs
  resolving. So test 4's numbers mostly stress **retrieval + reranking +
  Postgres**, not LLM generation — that's what tests 2 and 3 are for. To
  also load-test the full LLM-synthesis path, restart `api` with
  `RAG_STRATEGY=synthesis` (or point `LLM_MODEL_NAME` at a bigger model) and
  rerun test 4.

## Cleaning up

Results are gitignored (`stress-test/results/`). The k6 image persists in
local podman storage; remove it with `podman rmi ghcr.io/grafana/k6:latest`
if you don't want it kept around.

# Sumup Stress Test:

## LLM Generation Bench (direct to Ollama, qwen2.5:0.5b)

- Ramped 1 → 6 concurrent generation requests, 55 completions, 0 errors

- Latency: avg 4.64s, median 3.8s, p90 10.2s, p95 11.3s, max 11.7s

- Clear degradation curve: latency climbs sharply with concurrency since Ollama serves this CPU-bound
  model mostly serially. At 1 VU it was ~0.5-1s per response; by 5-6 concurrent it's 10+ seconds.

## Embedding Bench (nomic-embed-text, direct to Ollama)

- Ramped 2 → 10 concurrent, 6,199 completions, 0 errors, ~88.5 req/s sustained

- Latency: avg 50ms, median 43ms, p90 94ms, p95 101ms, max 293ms

- Very cheap and stable even at 10 concurrent — embeddings are not your bottleneck.

## Conclusion on capacity

- Embedding throughput is not a limiting factor — handles 10 concurrent easily at ~100ms p95, likely
  scales well beyond that.

- LLM generation is the real ceiling. With this tiny 0.5b model on your CPU, each generation already costs
  multiple seconds, and it degrades fast past ~3-4 concurrent requests (p95 jumping to 10+ seconds).
  Practically: comfortable concurrent LLM users ≈ 2-3 before responses start feeling slow (>5s), and ~6
  concurrent is the point where it becomes painful (10+s responses) but still didn't error out.

- Since your current app config (RAG_STRATEGY=auto + 0.5b model) uses "Raw Mode" and skips LLM generation
  for most chat replies, real-world /api/chat throughput will be far higher than this LLM number — it's
  dominated by the cheap embedding+retrieval path instead. The LLM ceiling above only matters for
  query-rewrite calls and if you switch to RAG_STRATEGY=synthesis or a bigger model.
