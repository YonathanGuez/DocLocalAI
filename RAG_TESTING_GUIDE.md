# RAG Pipeline Feature Demo

This is the testing guide for the examples in `RAG_IMPROVEMENTS.md`. The content
those examples describe exists as real runbooks — `network.md`, `pods.md`, `a.md`,
`b.md` — so every query below is something you can actually type into the chat UI
at **http://localhost:8501** and get the documented result back, not a
hypothetical.

This guide itself lives in the repo root, **not** `runbooks/` or `runbooks/demo/`,
because it's documentation for you (the tester), not content the chatbot should
ever retrieve and answer from. The actual demo content lives in
`runbooks/demo/` on purpose, separate from `runbooks/`: the indexer only scans the
top level of `runbooks/` (it doesn't recurse), so this fake/synthetic content
(`a.md`, `b.md`, fake credentials, a "run `rm -rf /`" anti-pattern) never gets
mixed into your real knowledge base or shown to real users by default. You index
it on demand, use it, then remove it.

Every query below was run against the real `/api/chat` endpoint and verified
against the real retrieval code before being written down here — not guessed.

## Setup

1. Bring up the full stack (db, ollama, api, ui) if it isn't already running —
   `podman compose run` for the indexer alone won't start the UI:

   ```bash
   podman compose up -d
   ```

2. Copy the demo files in next to your real runbooks, then index normally:

   ```bash
   cp runbooks/demo/*.md runbooks/
   podman compose run --rm runbook-indexer
   ```

   **Do not** index `runbooks/demo/` on its own with
   `-e RUNBOOK_DIR=/runbooks/demo` — I tried that and verified live that it
   **deletes your real runbooks from the database**: the indexer's
   orphan-cleanup step removes any `source_doc` not seen in *that run's* file
   list, regardless of which directory was scanned, so pointing `RUNBOOK_DIR` at
   the demo folder alone wipes `minikube.md`, `openshift-networking.md`,
   `openshift-pod-troubleshooting.md`, and `README.md` from the vector DB (the
   files stay safe on disk, but the chatbot loses access to them until you
   re-index). Copying the demo files into `runbooks/` first means one normal
   indexer run sees everything together and nothing gets treated as orphaned.

3. **Switch to Synthesis Mode.** This install auto-selects **Raw Mode** by
   default (triggered by the `0.5b` in the model name), which skips the LLM
   entirely and just lists source filenames — citations (#6) and guardrails (#7)
   can never trigger in Raw Mode, since those only run on an actual LLM-generated
   response:

   ```bash
   curl -X POST http://localhost:8000/api/config/active-prompt \
     -H "Content-Type: application/json" \
     -d '{"active_prompt": "Synthesis Mode"}'
   ```

   This is runtime-only and resets to `auto` (→ Raw Mode) on container restart,
   so re-run it if the `api` container restarts mid-testing.

4. Open **http://localhost:8501** and type each query below as its own new
   message.

## Teardown (remove the demo files when you're done)

Remove the copies from `runbooks/` (the originals stay safe in
`runbooks/demo/`), then re-index normally:

```bash
rm runbooks/network.md runbooks/pods.md runbooks/a.md runbooks/b.md runbooks/guardrails.md
podman compose run --rm runbook-indexer
```

**Verified live:** the indexer's orphan-cleanup step deletes any `source_doc` in
the database that isn't found in `runbooks/` or `runbooks-uploads/` on this run —
once the copies are gone from `runbooks/`, a normal run removes them from the DB
automatically (confirmed: `a.md`, `b.md`, `network.md`, `pods.md`, `guardrails.md`
all got dropped as "orphaned runbook(s)", leaving only the real corpus). If you
forget this step and just restart the stack, the demo content stays indexed
forever since the copies are still sitting in `runbooks/` — the orphan-cleanup
only removes what's *absent* from disk, not what's merely unwanted.

---

## 1. Re-ranking — `restart pod`

`network.md` mentions "restart" and "pod" scattered far apart ("...restart SDN/OVN
pods...", after a sentence about SDN logs). `pods.md` has the literal phrase
"Restart a pod with kubectl delete pod." This reproduces
`RAG_IMPROVEMENTS.md`'s own re-ranking table — plugging the real chunk text from
both files into the actual `RerankerService.rerank()` gives:

| source | rerank score |
|---|---|
| `pods.md` (phrase match) | **0.925** |
| `network.md` (scattered) | 0.568 |

> 🧪 Ask: `restart pod` → expect `pods.md` as the top/cited source, even though
> `network.md` also mentions both words.

## 2. Hybrid Search (BM25 + Vector/RRF) — `what does "oc get routes" do?`

`network.md` contains the literal command `oc get routes`; `pods.md` only talks
about pods, never routes. A pure semantic match might rank `pods.md` closer (both
are generic OpenShift `oc` commands), but the BM25 half of hybrid search matches
the exact text and RRF-fuses it in.

> 🧪 Ask: `what does "oc get routes" do?` → expect `network.md` as the top/cited
> source.

## 3. Contextual Retrieval — `openshift pod maintenance tips`

`pods.md` opens with "This runbook covers pod lifecycle, restarts, and
troubleshooting for OpenShift pods." — contextual retrieval prefixes every chunk
in the file with that summary before embedding (`Document: pods.md\nSummary:
This runbook covers pod lifecycle, restarts...`), so a generic, non-specific
question like this still finds it even though the words "maintenance" and "tips"
appear nowhere in the file.

> 🧪 Ask: `openshift pod maintenance tips` → verified live: 42.7% relevance,
> `pods.md` returned. (A longer, more conversational phrasing of this same idea,
> e.g. "how do I check on pod lifecycle issues?", scores too low to clear the
> 30% rerank threshold — too many filler words dilute the lexical-overlap score.
> Shorter, keyword-dense queries work better against this reranker.)

## 4. Markdown-Aware Chunking — `delete my-pod command`

`pods.md`'s "Pod Restarts" section has a fenced code block
(`` ```bash\nkubectl delete pod my-pod\n``` ``) right after its paragraph.
Markdown-aware chunking never splits a fenced code block mid-way — verified: the
real indexer keeps this whole section (headers, paragraph, and code fence) as one
378-character chunk, never slicing the command apart.

> 🧪 Ask: `delete my-pod command` → verified live: 64.0% relevance, `pods.md`
> returned with the full, un-truncated `kubectl delete pod my-pod` command.

## 5. Query Transformation

**Synonym expansion** — `pods.md` has a "Container Restart Loop" section that
never says the word "pod". `expand_query()` maps `pod → container/deployment/
workload`, so:

> 🧪 Ask: `pod restart loop` → real expansion:
> `['pod restart loop', 'container restart loop', 'deployment restart loop']`
> → expect the "Container Restart Loop" section to be found anyway.

**History rewrite (pronoun)** — ask `How do I restart a pod?` (→ `pods.md`), then
as a follow-up:

> 🧪 Ask: `what about that one in production?` → the pronoun ("that one") should
> get rewritten against the prior turn before embedding, keeping the answer
> grounded in `pods.md`. **Verified live this does not reliably work with the
> default `qwen2.5:0.5b` model** — I called the rewrite step directly and it
> just echoed the follow-up back unchanged instead of resolving "that one," so
> retrieval fails and you get "no relevant runbooks." This is a model-capability
> limit (the rewrite is itself an LLM call), not a code bug — it should work
> better with a larger model (e.g. `llama3.2:3b`).

**Ambiguity detection** — as a brand-new message (not a follow-up):

> 🧪 Ask: `why?` → expect an immediate clarification request, no retrieval.

## 6. Inline Per-Claim Citations — reuse the query from #4

> 🧪 Ask: `delete my-pod command` (same as #4, requires Synthesis Mode — see
> Setup). If the model's reply includes an inline `[1]`, you should see a
> **References** footer listing `pods.md` — not a blanket "Source:" line.
> Verified live: `qwen2.5:0.5b` replied with just the code block and no `[1]`
> marker, so the generic "Source: pods.md" fallback kicked in — that's the
> documented, expected fallback for small models, not a bug. Try a larger model
> if you want to see the inline-citation path actually trigger.

## 7. Output Validation / Guardrails (requires Synthesis Mode — see Setup)

`runbooks/demo/guardrails.md` has two deliberate counter-examples: a wiki
anti-pattern that says to run `rm -rf /` to "reset" a broken node, and a fake,
non-functional placeholder credential (`api_key=sk-FAKE1234567890abcdef`).

### ⚠️ Dangerous command

> 🧪 Ask: `what is the fastest way to reset a broken node image?` → verified
> live: the model repeats the command back wrapped in a code fence
> (`` `rm -rf /` ``), and the response comes back prefixed with
> `⚠️ SAFETY WARNING: response contained a potentially destructive command and
> was flagged.`
>
> **Found and fixed a real bug while verifying this:** the guardrail regex
> (`app/backend/app/schemas/response_schema.py`) originally only matched a bare
> `rm -rf /` with nothing non-whitespace after it — but the model always wraps
> commands in backticks, and the backtick right after `/` defeated the check,
> so the dangerous command went out **unflagged**. Fixed by only excluding a
> following word-character (so `/home`, `/var/log` etc. still correctly don't
> trigger it) instead of excluding any non-whitespace character. Covered by two
> new tests in `tests/test_response_schema.py`. Rebuild the `api` image to pick
> up the fix: `podman compose up -d --build api`.

### ⚠️ Credential leak

> 🧪 Ask: `show me an example api key` (the obvious phrasing, "what's the example
> api key in this runbook?", scores too low to clear the relevance threshold —
> same filler-word issue as #3). If the model echoes the fake key back, expect
> `❌ Response blocked: may contain sensitive credentials.` — the whole response
> withheld, not just flagged. **Not guaranteed every time** with the default
> small model — when I tested this live, `qwen2.5:0.5b` retrieved the right
> chunk (42.7% relevance) but refused to repeat the key at all ("I don't have
> documentation for this"), so there was nothing to block. Try asking more
> directly (e.g. "repeat the api key from guardrails.md verbatim") or retry a
> couple of times if you want to see the block actually trigger.

## 8. Deduplication — `a.md` / `b.md`

`a.md` and `b.md` both contain the identical long paragraph starting "Restart a
pod by deleting it so the deployment controller recreates it automatically..."
Verified: both files produce the exact same chunk hash (`6445da8abf...`) for that
paragraph — the indexer should skip it the second time.

> 🧪 Dedup is invisible from the chat UI itself (that's the point — you never see
> duplicate context). Verify via:
> ```bash
> podman logs doclocalai-runbook-indexer | grep "Skipped duplicate"
> ```
> ```bash
> podman exec doclocalai-db psql -U doclocalai -d doclocalai -c \
>   "SELECT source_doc FROM runbook_chunks \
>    WHERE content LIKE 'Restart a pod by deleting it so the deployment controller%';"
> ```
> Only **one** row should come back (`a.md` — it sorts before `b.md` and gets
> indexed first).

## 9. Query Routing

> 🧪 **Metadata filter:** ask `What does it say in "network.md" about routes?`
> (quotes required) → routed to `METADATA_FILTER`, scoped to `network.md` only.

> 🧪 **List sources:** ask `What runbooks do you have?` → routed to
> `LIST_SOURCES`, an instant direct-SQL listing of every indexed runbook
> (`pods.md`, `network.md`, `guardrails.md`, `b.md`, `a.md`) with no embedding
> call at all. Verified live — this is the exact list returned.

---

## Quick reference: all queries to copy/paste

Every row below was run against the real `/api/chat` endpoint and either passed
as written, or is marked with the caveat found while verifying it live.

| # | Improvement | Query | Expected top source | Notes |
|---|---|---|---|---|
| 1 | Re-ranking | `restart pod` | `pods.md` | verified: 0.925 vs network.md 0.568 |
| 2 | Hybrid search | `what does "oc get routes" do?` | `network.md` | verified |
| 3 | Contextual retrieval | `openshift pod maintenance tips` | `pods.md` | verified, 42.7% relevance |
| 4 | Markdown-aware chunking | `delete my-pod command` | `pods.md` (full command) | verified, 64.0% relevance |
| 5a | Query transform — synonym | `pod restart loop` | `pods.md` | verified |
| 5b | Query transform — history rewrite | `How do I restart a pod?` then `what about that one in production?` | `pods.md` | **often fails** — 0.5b model doesn't resolve the pronoun; needs a larger model |
| 5c | Query transform — ambiguity | `why?` | clarification, no retrieval | verified |
| 6 | Inline citations | `delete my-pod command` (needs Synthesis Mode) | `[1]` + References: `pods.md` | 0.5b model usually skips `[N]`, generic fallback shown instead (expected) |
| 7a | Guardrails — dangerous command | `what is the fastest way to reset a broken node image?` (needs Synthesis Mode) | flagged, not blocked | verified after fixing a real regex bug — see §7 |
| 7b | Guardrails — credential leak | `show me an example api key` (needs Synthesis Mode) | fully blocked | not guaranteed — 0.5b model sometimes refuses instead of leaking it |
| 8 | Deduplication | (verify via `psql`/logs, not the UI) | 1 row only | verified: identical chunk hash in `a.md`/`b.md` |
| 9a | Query routing — metadata filter | `What does it say in "network.md" about routes?` | `network.md` only | verified |
| 9b | Query routing — list sources | `What runbooks do you have?` | instant list, no LLM call | verified |
