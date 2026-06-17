# GARVIS Reuse Audit — integrate, don't rebuild

> Goal: avoid rebuilding what mature OSS already does well. For each project: what it is,
> where it fits GARVIS, the verdict, and license/risk. Knowledge as of 2026-01.

## Verdict table
| Project | What it is | Fit in GARVIS | Verdict | License |
|---|---|---|---|---|
| **LangGraph** | Stateful agent graphs, checkpoints, human-in-loop | Orchestrator engine (Planner/Router/Merger as a graph) | **Integrate** (evaluate as the core; our `runtime/orchestrator` is the thin contract layer) | MIT |
| **PydanticAI** | Typed agent + tool calling on pydantic | Typed planner/worker I/O; replace manual JSON validation in `llm_planner` | **Integrate** (incremental) | MIT |
| **Aider** | Repo-aware AI coding + git | Coding Worker (scoped edits + tests + branch/PR) | **Integrate** (wrap behind Worker contract) | Apache-2.0 |
| **Browser Use** | LLM-driven browser automation | Research/Market workers (read-only fetch/extract) | **Integrate** (read-only) | MIT |
| **Mem0** | Drop-in memory layer (extract/dedup/retrieve) | Memory Worker (user/project/task) | **Integrate** (start here) | Apache-2.0 |
| **Graphiti** | Temporal knowledge graph | Decision/business memory over time | **Integrate later** (phase 2 memory) | Apache-2.0 |
| **AutoGen** | Multi-agent conversation patterns | Reference patterns; optional worker collaboration | **Borrow patterns** (don't adopt wholesale) | MIT |
| **CrewAI** | Role-based multi-agent framework | Reference for role/crew design | **Borrow patterns** | MIT |
| **OpenHands** | Autonomous software-engineering agent | Heavyweight coding autonomy | **Watch / not now** (Aider is lighter for our need) | MIT |
| **Continue** | IDE AI assistant | Dev-time aid, not a GARVIS runtime component | **Ignore for runtime** (useful as a dev tool) | Apache-2.0 |

## Recommended integrations (what to build ON, not build)
1. **Orchestration core → LangGraph.** Keep `runtime/orchestrator` models/gates/registry
   as the stable contract; let LangGraph drive state/checkpointing. Decision: write an
   ADR comparing "our thin engine" vs "LangGraph" before expanding the engine.
2. **Typed planning → PydanticAI + pydantic schemas.** Replace `llm_planner`'s manual
   JSON validation with a pydantic model; pairs with Nous Hermes for reliable tool/JSON.
3. **Coding Worker → Aider.** Wrap Aider behind the `Worker` contract (branch + draft PR,
   never main/merge; approval-gated).
4. **Research/Market Workers → Browser Use.** Read-only; behind the READ safety class.
5. **Memory → Mem0 now, Graphiti later**, both on postgres + pgvector.

## Explicitly avoid rebuilding
- A bespoke agent-graph engine (use LangGraph).
- A bespoke code-editing agent (use Aider).
- A bespoke browser automation layer (use Browser Use).
- A bespoke memory extraction/retrieval engine (use Mem0/Graphiti).
- A bespoke multi-agent protocol (borrow AutoGen/CrewAI patterns; reuse MCP tools).

## License / risk notes
- All listed are permissive (MIT/Apache-2.0) — safe for product use.
- Model weights (e.g., Nous Hermes) carry their base-model license — verify per model.
- Heaviest deps: OpenHands/torch-pulling stacks — adopt only when justified.

## Next step
Write a short ADR (`docs/adr/`) for the two highest-leverage decisions: (a) LangGraph as
orchestration core, (b) PydanticAI for typed planning — then integrate incrementally
behind the existing contracts. No rebuild.
