# GARVIS Memory MVP (design only)

> Design for the smallest useful persistent memory. **No database changes in this doc** —
> it specifies the schema, layers, retrieval, and storage so implementation (a separate,
> approval-gated PR) is straightforward. Builds on `GARVIS_MEMORY_ARCHITECTURE.md`.

## Scope (MVP)
Four layers only, single-user namespace, retrieval into the planner. Defer business/graph
memory to phase 2.

| Layer | Holds | Lifetime | Example |
|---|---|---|---|
| **User memory** | who Stas is, preferences, working style | long | "owner=Stas; concise; he/en/ru" |
| **Project memory** | goals/constraints not in code/git | project | "voice: ElevenLabs EN/RU; HE pending" |
| **Decision memory** | choices + rationale | long | "WDM-KS forbidden (BSOD 0x10D)" |
| **Rules memory** | hard rules always enforced | permanent | "no merges/branch-deletes without approval" |

## Storage strategy (recommended)
- **Postgres + pgvector** (already have postgres) — one `memories` table + one `rules` table.
- **Mem0** as the write/read/consolidate layer (extraction + dedup + retrieval) so we do
  not hand-roll memory logic. **Graphiti** later for decision/business graph.
- Embeddings: a local model via Ollama (no external calls) or a small sentence-transformer.

### Schema (proposed; implement later, needs approval — DB)
```
memories(
  id, namespace, layer, kind, text, embedding vector,
  metadata_json, source, confidence, created_at, updated_at, expires_at
)
rules(id, namespace, rule, severity, created_at)   -- never auto-evicted
-- pgvector index on embedding; btree on (namespace, layer)
```

## Retrieval strategy
1. **Hybrid**: pgvector semantic kNN + structured filters (layer, namespace, recency).
2. **Layer-weighted**: rules + user + decision memory always considered at plan time;
   project/task pulled by relevance.
3. **Recency + confidence decay** for non-permanent layers; **rules never decay**.
4. **Token budget**: cap injected memory; summarize/cluster overflow.
5. **Write path** (Memory Worker): extract → **redact secrets** → dedup → upsert with
   source + confidence.

## Privacy / secrets (hard rules)
- **Never store**: API keys, tokens, `.env`, `~/.git-credentials`, OAuth secrets, raw audio.
- **Redact on write** (regex + entropy) before persisting.
- **Secrets Broker**: workers request scoped, short-lived capabilities; secrets live only
  in env/vault, never in memory or logs.
- Per-namespace isolation now → enforced for multi-tenant later; support delete-by-namespace.

## Integration points
- **Planner**: `LLMPlanner.plan(run_id, goal, memory=...)` already accepts a `memory`
  dict — retrieval feeds it (hybrid, layer-weighted, budgeted).
- **Memory Worker**: writes decision/task/knowledge memory after runs (gated WRITE).
- **Rules seed**: load existing decisions (WDM-KS forbidden, no auto-merge, ElevenLabs
  Hebrew unusable) into the rules layer on first run.

## MVP implementation path (separate, approval-gated PRs)
1. `memories` + `rules` migrations (DB — needs approval).
2. Memory Worker wrapping **Mem0** behind the `Worker` contract (read/write/consolidate).
3. Secrets redaction on write (+ tests with a secret corpus).
4. Planner retrieval (hybrid, layer-weighted, token-budgeted).
5. Seed rules layer; evaluate Graphiti for decision/business graph (phase 2).

## Non-goals (MVP)
- No external hosted memory service while a single box suffices.
- No storing secrets or raw audio.
- No bespoke retrieval engine (use Mem0/Graphiti).
