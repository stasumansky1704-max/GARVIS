# GARVIS Worker System

> Design doc. Workers are permissioned, single-responsibility agents behind a uniform
> contract, dispatched by the Orchestrator (`GARVIS_ORCHESTRATOR_ARCHITECTURE.md`).
> Reuse-first: every worker maps to a mature OSS tool where one exists.

## Worker contract (uniform)
Every worker implements the same envelope so the Router/Merger stay generic:
```
class Worker:
    name: str
    capabilities: list[str]
    input_schema / output_schema     # pydantic models
    tool_permissions: list[str]      # least-privilege allowlist
    safety_class: read | write | external | dangerous
    cost_class: cheap | moderate | expensive

    def run(task) -> Envelope          # {task_id,status,result,artifacts,cost,logs}
```
Rules: deterministic I/O schemas; no direct secret access (Secrets Broker only); every
external/irreversible action routes through the Approval + Safety gates; emits audit logs.

## Reuse-first stance (do not rebuild)
| Need | Reuse (recommended) | Notes |
|---|---|---|
| Orchestration graph | **LangGraph** | Mature, stateful graphs, checkpoints, human-in-loop; fits Planner/Router/Merger. Strong adoption. |
| Multi-agent patterns | **AutoGen** / **CrewAI** | Reference patterns; consider over rolling our own role/conversation logic. |
| Typed agent/tool calls | **PydanticAI** + **Nous Hermes** model | Strong typed tool-calling; pairs with our pydantic envelopes. |
| Coding worker | **Aider** | Best-in-class repo-aware code edits + git; wrap it rather than build a code agent. |
| Browser/research | **Browser Use** / Playwright | Robust web automation for the Research/Market workers. |
| General code execution | **Open Interpreter** | Sandboxed code/run for ad-hoc tasks (guarded). |
| Tool ecosystem | **MCP servers** | Reuse existing MCP tools (GitHub, filesystem, web) instead of bespoke integrations. |

Decision rule: pick the most mature, highest-adoption option; wrap it behind the Worker
contract so it's swappable.

## First workers

### 1. Research Worker (safety: read)
- Capability: web search + fetch + summarize with citations.
- Reuse: Browser Use / Playwright + an MCP web tool; LLM summarization via Ollama.
- Tools: `web:read` only. No writes. Time-boxed.

### 2. GitHub Worker (safety: write/external)
- Capability: read repo/PRs/issues; create branches, commits, **draft PRs** (default).
- Reuse: `gh`/GitHub API or GitHub MCP server. Already proven in this repo's workflow.
- Guardrails: **draft-PR only by default**; no merges, no branch deletes (Approval Gate).

### 3. Coding Worker (safety: write)
- Capability: scoped, test-backed code edits.
- Reuse: **Aider** (repo-aware) wrapped behind the contract; run tests after edits.
- Guardrails: edits land on a branch + draft PR; never on main; approval for anything
  beyond the declared scope.

### 4. Docs Worker (safety: write)
- Capability: generate/update repo docs (like this sprint).
- Reuse: LLM + repo file tools; output via branch + draft PR.
- Lowest-risk worker — ideal first end-to-end pipeline test.

### 5. Memory Worker (safety: write, internal)
- Capability: write/read/consolidate memory per `GARVIS_MEMORY_ARCHITECTURE.md`.
- Reuse: **Mem0** or **Graphiti** for the memory layer (don't hand-roll retrieval);
  postgres + pgvector as the store.
- Guardrails: enforces "never store secrets"; redaction on write.

### 6. Voice Worker (safety: read/external)
- Capability: STT -> LLM -> TTS as an orchestrator-callable worker.
- Reuse: faster-whisper (local STT) + **ElevenLabs** (TTS) with Piper/pyttsx3 fallback;
  safe WASAPI capture only (**never WDM-KS**).
- Guardrails: no endless loops; bounded turns; wake-word gating (OpenWakeWord) later.

### 7. Market Worker (safety: read/external)
- Capability: read-only market/news/data pulls + summarize.
- Reuse: provider APIs/MCP; same shape as Research Worker.
- Guardrails: read-only; rate-limited; no trading/orders ever.

### Future connectors
- **Calendar Worker / Gmail Worker**: read-first via Google APIs/MCP; any send/modify
  behind Approval Gate. Defer until core workers are solid; treat as external/dangerous.

## Worker lifecycle
register -> Planner plans with capability -> Router dispatches -> Safety Gate (pre-call)
-> [Approval Gate if write/external] -> run -> Envelope -> Merger -> audit.

## MVP path
1. Implement the `Worker` base + registry in `runtime/orchestrator/`.
2. Ship **Docs Worker** + **Research Worker** first (read/low-risk) to prove the pipeline.
3. Add **GitHub Worker** (draft-PR only), then **Memory Worker** (Mem0/Graphiti + pgvector).
4. Add **Coding Worker** (Aider) behind approval, then **Voice Worker**.
5. Market + connectors last.

## Non-goals (MVP)
- No worker with unrestricted tool access.
- No auto-merge / branch-delete / prod actions from any worker.
- No bespoke reimplementation where Aider / Browser Use / Mem0 / LangGraph already fit.
