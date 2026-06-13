# GARVIS — Governance-Aware Reflective Virtual Intelligence System

## Phase 1 Runtime — Persistent Governed Reflective Cognition Runtime

---

## WHAT GARVIS IS

GARVIS is **constitutional cognition infrastructure** — not an AI assistant, not an autonomous agent, not a chatbot wrapper. It is a governed runtime that hosts LLM inference under strict, declarative, enforceable governance constraints.

Every cognition operation — every inference, every memory retrieval, every state transition — passes through governance validation. Any breach halts execution. Nothing operates outside declared boundaries. Nothing evolves without operator authorization. Every decision is traceable, auditable, and observable.

## WHAT GARVIS IS NOT

- Not an AI assistant
- Not AutoGPT or an autonomous agent
- Not a chatbot wrapper
- Not a generic orchestration framework
- Not self-modifying
- Not silently evolving
- Not capable of self-authorized expansion

---

## CORE PRINCIPLES

| Principle | Meaning |
|-----------|---------|
| **Governance FIRST** | All cognition passes through governance validation before execution |
| **Capabilities SECOND** | No capability exists without governance binding |
| **Fail-Closed** | Any validation breach halts execution; no silent failures |
| **No Hidden Autonomy** | Every decision is traceable, auditable, observable |
| **Bounded Cognition** | All reasoning operates within declared boundaries |
| **Traceable Memory** | Every memory influence on reasoning is visible |

---

## ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────┐
│                    GOVERNANCE LAYER                          │
│  Schema Registry │ Policy Validator │ Boundary Enforcer      │
├─────────────────────────────────────────────────────────────┤
│                   COGNITION LAYER                            │
│  State Machine │ Inference Wrapper │ Session Manager         │
├─────────────────────────────────────────────────────────────┤
│                   MEMORY LAYER                               │
│  Episodic Store │ Retrieval Engine │ Influence Mapper         │
├─────────────────────────────────────────────────────────────┤
│                  TRACEABILITY LAYER                          │
│  Lineage Tracker │ Audit Pipeline │ Governance Influence Log   │
├─────────────────────────────────────────────────────────────┤
│                   RUNTIME LAYER                              │
│  Ollama Client │ PostgreSQL │ Event Bus │ Health Monitor      │
└─────────────────────────────────────────────────────────────┘
```

### Governance Layer (governance/)

**The foundation. Nothing runs without it.**

| Component | Purpose |
|-----------|---------|
| `SchemaLoader` | Loads 28 YAML governance schemas into validated Pydantic models |
| `GovernanceRegistry` | Manages active schemas, enforces cross-schema consistency |
| `RuntimeValidator` | Core fail-closed validation engine — checks every operation |
| `GovernanceMiddleware` | Async firewall — every cognition pathway passes through here |
| `EnforcementEngine` | Executes enforcement: halt, degrade, or escalate on violation |

**28 Governance Schemas** across 5 categories:
- **Epistemic** (6): uncertainty_management, truthfulness_governance, evidence_coherence, cognitive_consistency, provenance_awareness, cognitive_humility
- **Operational** (6): operational_state_model, escalation_awareness, integrity_verification, planning_cognition, priority_resolution, workload_awareness
- **Boundary** (7): decision_boundaries, runtime_boundary, runtime_mediation, interception_manifest, boundary_preservation, boundary_conflicts
- **Reflective** (7): cognitive_traceability, degradation_awareness, resilience_awareness, adaptation_pressure, equilibrium_awareness, self_limitation_awareness, recovery_awareness
- **Session** (2): session_continuity, retrieval_scoring, dependency_awareness

### Cognition Layer (cognition/)

**The operational brain. 13 governed states. Forbidden patterns detected automatically.**

| Component | Purpose |
|-----------|---------|
| `CognitiveStateMachine` | 13-state machine with validated transitions and forbidden-pattern detection |
| `TransitionValidator` | Validates transitions against governance rules |
| `ForbiddenPatternDetector` | Detects 4 forbidden patterns → auto-FAIL_CLOSED |
| `SessionManager` | Manages cognition sessions with active governance schemas |

**Operational States:**
`UNINITIALIZED → INITIALIZING → STANDBY → GOVERNANCE_CHECK → COGNITION_ACTIVE → INFERENCE_EXECUTING → ... → FAIL_CLOSED/SHUTDOWN`

**Forbidden Patterns (auto-detected):**
- Recursive inference (two consecutive INFERENCE_EXECUTING)
- Illegal recovery (FAIL_CLOSED → COGNITION_ACTIVE direct)
- Degraded inference (DEGRADED → INFERENCE_EXECUTING)
- Uninitialized active (UNINITIALIZED → COGNITION_ACTIVE)

### Memory Layer (memory/)

**Every memory has provenance. Every retrieval is governed. Every influence is traceable.**

| Component | Purpose |
|-----------|---------|
| `EpisodicMemoryStore` | Stores cognitive episodes with full provenance |
| `RetrievalEngine` | Provenance-aware, temporally-scoped, relevance-scored retrieval |
| `InfluenceMapper` | Maps how memories influence reasoning — all visible |
| `MemoryPersistence` | PostgreSQL persistence with soft-delete only |

### Traceability Layer (traceability/)

**Complete lineage. Immutable audit trail. Every step recorded.**

| Component | Purpose |
|-----------|---------|
| `LineageTracker` | Records reasoning lineage across all cognition |
| `AuditPipeline` | Buffered, durable, append-only event logging |
| `TraceGraphBuilder` | Constructs trace graphs with critical path analysis |

### Inference Layer (inference/)

**The ONLY path to LLM inference. No inference bypasses governance.**

| Component | Purpose |
|-----------|---------|
| `OllamaClient` | Async HTTP client for Ollama local inference |
| `PromptMediator` | Injects governance constraints into every prompt |
| `ResponseValidator` | Validates every response before release |
| `GovernedInferenceExecutor` | 9-step governed inference pipeline |

**Inference Pipeline (9 steps):**
1. Validate request through governance
2. Transition to INFERENCE_EXECUTING
3. Mediate prompt (inject governance constraints)
4. Retrieve episodic memories
5. Execute via Ollama (with retry)
6. Validate response
7. Record lineage and audit
8. Store as episodic memory
9. Release validated response

### Runtime Layer (runtime/)

**Governance-first initialization. Strict ordering. Any failure = no start.**

| Component | Purpose |
|-----------|---------|
| `RuntimeBootstrap` | 15-step initialization (governance must succeed first) |
| `RuntimeConfig` | 12-factor configuration from environment |
| `HealthMonitor` | Periodic health checks on all dependencies |
| `EventBus` | Async pub/sub for internal communication |
| `RuntimeLifecycle` | start/pause/resume/stop/emergency_stop |

---

## FAIL-CLOSED BEHAVIOR

GARVIS enters `FAIL_CLOSED` state when:

| Trigger | Response |
|---------|----------|
| Governance schema load failure | Runtime does not start |
| Cross-schema inconsistency | Runtime does not start |
| Critical governance violation | All cognition halts |
| Forbidden state transition | Transition blocked, audit logged |
| Forbidden state pattern detected | Auto-transition to FAIL_CLOSED |
| Database connection loss | Read-only mode, halt new cognition |
| Integrity verification failure | Runtime halts |

In `FAIL_CLOSED`:
- All inference stops immediately
- No new sessions
- Active sessions terminated with full audit trail
- Memory preserved (read-only)
- Audit continues (read-only queries)
- Only `RECOVERING` or `SHUTDOWN` transitions allowed
- **Operator intervention required to exit**

---

## QUICK START

### Prerequisites
- Docker + Docker Compose
- Git

### 1. Clone and Configure
```bash
git clone <repository>
cd garvis
cp .env.example .env
# Edit .env if needed
```

### 2. Start Services
```bash
docker compose up -d
```

This starts:
- PostgreSQL 16 (persistent storage)
- Ollama (local LLM inference)
- GARVIS runtime (governance-first initialization)

### 3. Verify Health
```bash
docker compose logs -f garvis
```

### 4. Pull a Model (first time)
```bash
docker compose exec ollama ollama pull llama3.1
```

---

## PROJECT STATISTICS

| Metric | Count |
|--------|-------|
| Python files | 42 |
| Python LOC | ~10,328 |
| YAML governance schemas | 28 |
| YAML LOC | 1,332 |
| SQL migration files | 2 |
| SQL LOC | 412 |
| Test files | 11 |
| Test LOC | 4,734 |
| Tests | 249 (239 passing) |
| Total LOC | ~16,806 |

---

## GOVERNANCE VALIDATION FLOW

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Operator   │────▶│   Request    │────▶│  Governance  │
│              │     │   Enters     │     │  Middleware  │
└──────────────┘     │   Runtime    │     │  Validates   │
                     └──────────────┘     └──────┬───────┘
                                                  │
                       ┌──────────────────────────┼──────────────────────────┐
                       │                          │                          │
                       ▼                          ▼                          ▼
                 ┌──────────┐             ┌──────────┐               ┌──────────┐
                 │  PASS    │             │  WARN    │               │  FAIL    │
                 │ Continue │             │ Degrade  │               │  Halt    │
                 └──────────┘             └──────────┘               └──────────┘
```

---

## EXPANSION-SAFE ARCHITECTURE

- **No Silent Evolution**: Schemas never auto-reload
- **No Self-Modification**: No runtime capability expansion
- **All Changes Audited**: Every modification logged
- **Operator Authorization Required**: All changes need explicit approval
- **Bounded Growth**: New capabilities only via explicit schema + deployment

---

## TESTING

```bash
# Run all tests
pytest tests/ -v

# Run specific module
pytest tests/test_state_machine.py -v

# Run with coverage
pytest tests/ --cov=. --cov-report=term-missing
```

---

## DOCUMENTATION

- `SPEC.md` — Full technical specification (architecture, models, interfaces, data flow)
- `governance/schemas/*.yml` — 28 governance schemas (human-readable policy documents)
- `database/migrations/` — PostgreSQL schema definitions
- This README — Architecture overview and quick start

---

## LICENSE

[License to be determined by project owner]

---

## PROJECT STATUS

**Phase 1 Complete**: Runtime implementation with governance-first architecture, 28 schemas, fail-closed enforcement, traceable memory, and governed inference pipeline.

**Next Phases** (not in scope):
- Phase 2: Operator dashboard, governance schema editor, trace visualization
- Phase 3: Multi-model support, advanced retrieval, distributed operation
- Phase 4: Formal verification, compliance reporting, external audit integration
