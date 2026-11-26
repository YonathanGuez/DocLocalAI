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

## Setup

1. Bring up the full stack (db, ollama, api, ui) if it isn't already running —
   `podman compose run` for the indexer alone won't start the UI:

   ```bash
   podman compose up -d
   ```

2. Index the demo files on top of whatever's already running:

   ```bash
   podman compose run --rm -e RUNBOOK_DIR=/runbooks/demo runbook-indexer
   ```

   This adds `network.md`, `pods.md`, `a.md`, and `b.md` to the vector DB **in
   addition to** whatever's already indexed from `runbooks/` — it does not touch
   or remove your real runbooks.

3. Open **http://localhost:8501** and type each query below as its own new
   message.

## Teardown (remove the demo files when you're done)

```bash
podman exec doclocalai-db psql -U doclocalai -d doclocalai -c \
  "DELETE FROM runbook_chunks WHERE source_doc IN \
   ('network.md', 'pods.md', 'a.md', 'b.md');"
```

The indexer doesn't delete rows for files it wasn't given, so this manual cleanup
step is how you get your real corpus back to exactly what's in `runbooks/`.

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

## 3. Contextual Retrieval — `how do I check on pod lifecycle issues?`

`pods.md` opens with "This runbook covers pod lifecycle, restarts, and
troubleshooting for OpenShift pods." — contextual retrieval prefixes every chunk
in the file with that summary before embedding (`Document: pods.md\nSummary:
This runbook covers pod lifecycle, restarts...`), so a generic, non-specific
question like this still finds it.

> 🧪 Ask: `how do I check on pod lifecycle issues?` → expect a `pods.md` answer,
> even though no single chunk in the file literally contains the phrase
> "lifecycle issues".

## 4. Markdown-Aware Chunking — `give me the exact command to delete my-pod`

`pods.md`'s "Pod Restarts" section has a fenced code block
(`` ```bash\nkubectl delete pod my-pod\n``` ``) right after its paragraph.
Markdown-aware chunking never splits a fenced code block mid-way — verified: the
real indexer keeps this whole section (headers, paragraph, and code fence) as one
378-character chunk, never slicing the command apart.

> 🧪 Ask: `give me the exact command to delete my-pod` → expect the full,
> un-truncated `kubectl delete pod my-pod` command in the answer.

## 5. Query Transformation

**Synonym expansion** — `pods.md` has a "Container Restart Loop" section that
never says the word "pod". `expand_query()` maps `pod → container/deployment/
workload`, so:

> 🧪 Ask: `pod restart loop` → real expansion:
> `['pod restart loop', 'container restart loop', 'deployment restart loop']`
> → expect the "Container Restart Loop" section to be found anyway.

**History rewrite (pronoun)** — ask `How do I restart a pod?` (→ `pods.md`), then
as a follow-up:

> 🧪 Ask: `what about that one in production?` → the pronoun ("that one") gets
> rewritten against the prior turn before embedding, and the answer should still
> be grounded in `pods.md`.

**Ambiguity detection** — as a brand-new message (not a follow-up):

> 🧪 Ask: `why?` → expect an immediate clarification request, no retrieval.

## 6. Inline Per-Claim Citations — reuse the query from #4

> 🧪 Ask: `give me the exact command to delete my-pod` (same as #4). If the model's
> reply includes an inline `[1]`, you should see a **References** footer listing
> `pods.md` — not a blanket "Source:" line. (The default small local model doesn't
> always add `[N]` markers; if it doesn't, the generic "Source:" fallback is
> expected, not a bug.)

## 7. Output Validation / Guardrails

### ⚠️ Anti-Pattern: Do Not Run This

This is a *counter-example* kept here on purpose: some outdated internal wikis
still tell people to run `rm -rf /` to "reset" a broken node image. **Do not do
this.**

> 🧪 Ask: `what's the fastest way to reset a broken node image?` → if the model
> repeats the command, expect it prefixed with `⚠️ SAFETY WARNING: ...` rather
> than shown silently.

### ⚠️ Anti-Pattern: Example Credential

This is a *fake, non-functional* placeholder kept here on purpose, to test the
credential-leak guardrail — it is not a real secret:
`api_key=sk-FAKE1234567890abcdef`.

> 🧪 Ask: `what's the example api key in this runbook?` → if the model echoes it,
> expect `❌ Response blocked: may contain sensitive credentials.` — the whole
> response withheld, not just flagged.

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
> (including `network.md`, `pods.md`, `a.md`, `b.md`) with no embedding call at
> all.

---

## Quick reference: all queries to copy/paste

| # | Improvement | Query | Expected top source |
|---|---|---|---|
| 1 | Re-ranking | `restart pod` | `pods.md` |
| 2 | Hybrid search | `what does "oc get routes" do?` | `network.md` |
| 3 | Contextual retrieval | `how do I check on pod lifecycle issues?` | `pods.md` |
| 4 | Markdown-aware chunking | `give me the exact command to delete my-pod` | `pods.md` (full command) |
| 5a | Query transform — synonym | `pod restart loop` | `pods.md` |
| 5b | Query transform — history rewrite | `How do I restart a pod?` then `what about that one in production?` | `pods.md` |
| 5c | Query transform — ambiguity | `why?` | clarification, no retrieval |
| 6 | Inline citations | `give me the exact command to delete my-pod` | `[1]` + References: `pods.md` |
| 7a | Guardrails — dangerous command | `what's the fastest way to reset a broken node image?` | flagged, not blocked |
| 7b | Guardrails — credential leak | `what's the example api key in this runbook?` | fully blocked |
| 8 | Deduplication | (verify via `psql`/logs, not the UI) | 1 row only |
| 9a | Query routing — metadata filter | `What does it say in "network.md" about routes?` | `network.md` only |
| 9b | Query routing — list sources | `What runbooks do you have?` | instant list, no LLM call |
