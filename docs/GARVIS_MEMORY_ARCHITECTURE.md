# GARVIS Memory Architecture

> Design doc. Layered, retrievable memory with strict secrets handling. Reuse-first:
> prefer **Mem0** or **Graphiti** over a hand-rolled memory engine; store in postgres +
> **pgvector** (already have postgres). Companion: orchestrator + worker docs.

## Goals
- Give GARVIS durable context across sessions without leaking secrets.
- Make memory **retrievable** (semantic + structured) and **governed** (what may/never be
  stored), namespaced per user/project for future multi-tenant productization.

## Layers
| Layer | Holds | Lifetime | Example |
|---|---|---|---|
| **User memory** | who Stas is, preferences, working style | long | "owner is Stas; replies short; he/en/ru" |
| **Project memory** | goals/constraints not in code or git | project | "voice MVP: cloud TTS + local STT" |
| **Decision memory** | choices + rationale | long | "WDM-KS forbidden (BSOD 0x10D)" |
| **Business memory** | product/market/strategy facts | long | "wedge = multilingual voice + workers" |
| **Task memory** | run/task state, results, artifacts | run/ttl | orchestrator run history |
| **Knowledge memory** | reference material, docs, snippets | long | curated KB (`knowledge_base/`) |
| **Safety/rules memory** | hard rules the system must always honor | permanent | "no merges/branch-deletes without approval" |

## Reuse decision
- **Mem0**: drop-in memory layer with extraction, dedup, and retrieval APIs; fastest path.
- **Graphiti**: temporal knowledge graph — better for decision/business relations over time.
- **Recommendation**: start with **Mem0** for speed (user/project/task), evaluate
  **Graphiti** for decision/business graph as a second phase. Back both with postgres+pgvector.
- Reuse the repo's existing `memory/` (episodic) + `knowledge_base/` as sources to migrate.

## Storage model (MVP)
```
memories(id, namespace, layer, kind, text, embedding vector, metadata_json,
         source, confidence, created_at, updated_at, expires_at)
-- namespace = user/project scope (multi-tenant ready)
-- pgvector index on embedding for semantic recall
rules(id, namespace, rule, severity, created_at)   -- safety/rules layer (never auto-evicted)
```

## Retrieval strategy
1. **Hybrid**: semantic (pgvector kNN) + structured filters (layer, namespace, recency).
2. **Layer-weighted**: safety/rules + user + decision memory always considered for
   planning; task/knowledge pulled on demand by relevance.
3. **Recency + confidence** decay for non-permanent layers; safety/rules never decay.
4. **Injection budget**: cap tokens injected into prompts; summarize/cluster overflow.
5. **Write path**: extract -> redact secrets -> dedup against existing -> upsert with source
   + confidence. Memory Worker owns this.

## What should NEVER be stored
- API keys, tokens, passwords, `.env` contents, `~/.git-credentials`, OAuth secrets.
- Full PII beyond what the user explicitly asks to remember.
- Raw audio of conversations (store transcripts/derived facts only if consented).
- Anything a memory's own `kind=secret` detector flags — hard-blocked on write.

## Privacy / secrets handling
- **Secrets Broker**: workers never read raw secrets; they request scoped, short-lived
  capabilities. Secrets live only in env / a vault, never in memory or logs.
- **Redaction on write**: regex + entropy checks strip key-like strings before persisting.
- **Never printed / never committed** (consistent with sprint safety rules).
- **Namespacing**: per-user isolation now (single user) → enforced for multi-tenant later.
- **Right to forget**: delete-by-namespace/kind supported for user data.

## Integration with orchestrator
- Planner pulls user/project/decision/safety memory at plan time.
- Memory Worker writes task/decision/knowledge memory after runs.
- Audit log references memory writes (traceability).

## MVP path
1. Add `memories` + `rules` tables (postgres + pgvector).
2. Wrap **Mem0** behind the Memory Worker contract (write/read/consolidate).
3. Seed safety/rules layer from existing decisions (WDM-KS forbidden, no auto-merge, etc.).
4. Wire Planner retrieval (hybrid, layer-weighted, token-budgeted).
5. Evaluate Graphiti for decision/business graph in a later phase.

## Non-goals (MVP)
- No external hosted memory service while a single box suffices.
- No storing of secrets or raw audio.
- No bespoke retrieval engine where Mem0/Graphiti fit.
