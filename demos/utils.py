"""
Common utilities for all GARVIS demonstration scripts.

Provides:
- MockDatabase: In-memory database that mimics asyncpg interface
- create_mock_registry: Factory for fully initialized GovernanceRegistry
- create_mock_db: Factory for mock database instances
- create_mock_validator: Factory for mock RuntimeValidator
- create_mock_enforcer: Factory for mock EnforcementEngine
- create_mock_audit: Factory for mock AuditPipeline
- create_mock_lineage: Factory for mock LineageTracker
- import_from: Direct module loader that bypasses package __init__.py
- print helpers: Headers, sections, pass/fail results with ANSI colors
- run_demo: Async runner with setup/teardown and crash handling
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

# ---------------------------------------------------------------------------
# Ensure project root is on path so imports resolve
# ---------------------------------------------------------------------------
_PROJECT_ROOT = __file__.rsplit("/demos/", 1)[0]
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ---------------------------------------------------------------------------
# Direct module loader — bypasses package __init__.py to avoid pulling in
# heavy dependencies (asyncpg) that we mock anyway.
# ---------------------------------------------------------------------------

def import_from(module_path: str, attr_name: str | None = None):
    """Import a class or function directly from a module file.

    This bypasses the package-level __init__.py, avoiding cascade imports
    of heavy dependencies like asyncpg that the demos mock anyway.

    Args:
        module_path: Dotted path to the module, e.g. "inference.prompt_mediator".
        attr_name: Name of the attribute to return, e.g. "PromptMediator".
                   If None, returns the loaded module itself.

    Returns:
        The requested attribute, or the module if attr_name is None.
    """
    # Map dotted path to filesystem path
    rel_path = module_path.replace(".", "/") + ".py"
    file_path = Path(_PROJECT_ROOT) / rel_path

    if not file_path.exists():
        raise ImportError(f"Module file not found: {file_path}")

    spec = importlib.util.spec_from_file_location(module_path, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create spec for {module_path}")

    module = importlib.util.module_from_spec(spec)
    # Ensure parent packages exist in sys.modules with __path__ set
    # so Python treats them as packages (enabling relative imports)
    parts = module_path.split(".")
    for i in range(1, len(parts)):
        parent = ".".join(parts[:i])
        if parent not in sys.modules:
            parent_mod = type(sys)(parent)
            parent_dir = Path(_PROJECT_ROOT) / "/".join(parts[:i])
            parent_mod.__path__ = [str(parent_dir)]  # type: ignore[attr-defined]
            sys.modules[parent] = parent_mod
    sys.modules[module_path] = module
    spec.loader.exec_module(module)

    if attr_name:
        return getattr(module, attr_name)
    return module


# Pre-load the models module (these have no external deps)
from models.audit import AuditEvent
from models.cognition import OperationalState, StateTransition
from models.governance import GovernanceCheckResult, GovernanceViolation
from models.inference import InferenceRequest, GovernedResponse, PromptMediationResult
from models.memory import EpisodicMemory, MemoryInfluence, ProvenanceRecord


# ---------------------------------------------------------------------------
# ANSI colour codes
# ---------------------------------------------------------------------------

_GREEN = "\033[92m"
_RED = "\033[91m"
_YELLOW = "\033[93m"
_CYAN = "\033[96m"
_BOLD = "\033[1m"
_RESET = "\033[0m"


# ===========================================================================
# MockDatabase — in-memory store that mimics the DatabaseConnection interface
# ===========================================================================

class MockDatabase:
    """Mock database for demos — no PostgreSQL required.

    Maintains named in-memory tables and responds to fetch/fetchrow/execute
    calls exactly like the real DatabaseConnection, so all production code
    (AuditPipeline, LineageTracker, etc.) works unchanged.
    """

    def __init__(self) -> None:
        self._data: dict[str, list[dict[str, Any]]] = {
            "audit_events": [],
            "state_transitions": [],
            "governance_checks": [],
            "episodic_memories": [],
            "memory_influences": [],
            "cognition_traces": [],
            "violations": [],
        }
        self._counters: dict[str, int] = {
            "execute": 0,
            "fetch": 0,
            "fetchrow": 0,
            "executemany": 0,
        }

    # -- Async interface expected by AuditPipeline / LineageTracker --------

    async def execute(self, query: str, *args: Any) -> str:
        """Store a row in the appropriate table based on query content."""
        self._counters["execute"] += 1

        # Heuristic: determine target table from the query string
        query_lower = query.lower()
        if "audit" in query_lower or "audit_insert" in query_lower:
            self._data["audit_events"].append(self._row_from_args(args))
        elif "transition" in query_lower:
            self._data["state_transitions"].append(self._row_from_args(args))
        elif "governance_check" in query_lower or "check_insert" in query_lower:
            self._data["governance_checks"].append(self._row_from_args(args))
        elif "influence" in query_lower:
            self._data["memory_influences"].append(self._row_from_args(args))
        elif "trace" in query_lower:
            self._data["cognition_traces"].append(self._row_from_args(args))
        elif "violation" in query_lower:
            self._data["violations"].append(self._row_from_args(args))

        return "INSERT 0 1"

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        """Return matching rows from the appropriate table."""
        self._counters["fetch"] += 1

        query_lower = query.lower()
        if "audit" in query_lower:
            return self._data["audit_events"]
        elif "transition" in query_lower:
            return self._data["state_transitions"]
        elif "governance_check" in query_lower:
            return self._data["governance_checks"]
        elif "influence" in query_lower:
            return self._data["memory_influences"]
        elif "trace" in query_lower:
            return self._data["cognition_traces"]
        elif "violation" in query_lower:
            return self._data["violations"]
        return []

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        """Return first matching row, or None."""
        self._counters["fetchrow"] += 1
        rows = await self.fetch(query, *args)
        return rows[0] if rows else None

    async def fetchval(self, query: str, *args: Any) -> Any:
        """Return a single scalar value."""
        return 1

    async def executemany(self, query: str, args: list[tuple]) -> None:
        """Batch insert."""
        self._counters["executemany"] += 1
        for row_args in args:
            await self.execute(query, *row_args)

    async def health_check(self) -> bool:
        return True

    @property
    def is_initialized(self) -> bool:
        return True

    # -- Internal helpers --------------------------------------------------

    def _row_from_args(self, args: tuple) -> dict[str, Any]:
        """Build a dict from positional args (best-effort column mapping)."""
        return {"args": list(args), "stored_at": datetime.now(timezone.utc)}

    def get_table(self, name: str) -> list[dict[str, Any]]:
        return list(self._data.get(name, []))

    def clear(self) -> None:
        for key in self._data:
            self._data[key] = []

    def get_counters(self) -> dict[str, int]:
        return dict(self._counters)


# ===========================================================================
# Factory functions for mock components
# ===========================================================================

def create_mock_db() -> MockDatabase:
    """Create a fresh mock database instance."""
    return MockDatabase()


def create_mock_registry() -> Any:
    """Create a fully initialized governance registry with real schemas."""
    from governance.loader import SchemaLoader
    from governance.registry import GovernanceRegistry

    loader = SchemaLoader("governance/schemas")
    registry = GovernanceRegistry(loader)
    registry.initialize()
    return registry


class AsyncRuntimeValidatorWrapper:
    """Wraps a real RuntimeValidator to make it async-compatible.

    The CognitiveStateMachine expects an async ``validate_state_transition``
    method, but RuntimeValidator provides a synchronous one. Additionally,
    the state machine calls ``has_critical_failure`` (singular) while the
    validator defines ``has_critical_failures`` (plural). This wrapper
    bridges all such gaps.
    """

    def __init__(self, real_validator: Any) -> None:
        self._validator = real_validator

    async def validate_state_transition(self, transition: Any) -> list[Any]:
        """Async wrapper around the real validator's sync method."""
        return self._validator.validate_state_transition(transition)

    def has_critical_failure(self, results: list[Any]) -> bool:
        """Delegate to has_critical_failures (plural) on the real validator."""
        return self._validator.has_critical_failures(results)

    def build_violation(self, transition: Any, result: dict[str, Any]) -> Any:
        return self._validator.build_violation(transition, result)

    # Delegate all other attributes to the real validator
    def __getattr__(self, name: str) -> Any:
        return getattr(self._validator, name)


def create_mock_validator(registry: Any | None = None) -> MagicMock:
    """Create a mock RuntimeValidator that always passes."""
    validator = MagicMock()
    validator.validate_state_transition = AsyncMock(return_value=[])
    validator.validate_inference_request = MagicMock(return_value=[])
    validator.validate_response = MagicMock(return_value=[])
    validator.validate_memory_operation = MagicMock(return_value=[])
    validator.has_critical_failure = MagicMock(return_value=False)
    validator.get_validation_history = MagicMock(return_value=[])
    validator.clear_history = MagicMock()
    validator.build_violation = MagicMock(
        side_effect=lambda transition, result: GovernanceViolation(
            schema_id="operational_state_model",
            policy_id="forbidden_pattern_prevention",
            severity="critical",
            description="Mock violation",
        )
    )
    return validator


def create_mock_enforcer() -> MagicMock:
    """Create a mock EnforcementEngine."""
    enforcer = MagicMock()
    enforcer.enforce_violation = AsyncMock()
    enforcer.halt_runtime = MagicMock()
    enforcer.degrade_runtime = MagicMock()
    enforcer.escalate_violation = MagicMock()
    enforcer.is_halted = False
    enforcer.is_degraded = False
    enforcer.halt_reason = None
    enforcer.degrade_reason = None
    enforcer.get_violation_counts = MagicMock(return_value={"critical": 0, "warning": 0, "info": 0})
    enforcer.reset = MagicMock()
    return enforcer


def create_mock_audit(db: MockDatabase | None = None) -> MagicMock:
    """Create a mock AuditPipeline that stores events in memory."""
    audit = MagicMock()
    audit._events: list[AuditEvent] = []
    audit._transitions: list[StateTransition] = []

    async def _log_event(event: AuditEvent) -> None:
        audit._events.append(event)

    async def _log_state_transition(transition: StateTransition) -> None:
        audit._transitions.append(transition)

    async def _log_governance_violation(violation: GovernanceViolation, trace_id: UUID | None = None) -> None:
        event = AuditEvent(
            event_id=uuid4(),
            event_type="violation",
            severity="critical" if violation.severity == "critical" else "warning",
            component="governance_validator",
            trace_id=trace_id or uuid4(),
            details={
                "violation_id": str(violation.violation_id),
                "schema_id": violation.schema_id,
                "policy_id": violation.policy_id,
                "description": violation.description,
            },
        )
        audit._events.append(event)

    async def _log_inference(request: InferenceRequest, response: GovernedResponse, trace_id: UUID | None = None) -> None:
        event = AuditEvent(
            event_id=uuid4(),
            event_type="inference",
            severity="info" if response.passed_validation else "warning",
            component="inference_executor",
            session_id=request.session_id,
            trace_id=trace_id or uuid4(),
            details={
                "request_id": str(request.request_id),
                "response_id": str(response.response_id),
                "passed_validation": response.passed_validation,
            },
        )
        audit._events.append(event)

    async def _get_events(**kwargs: Any) -> list[AuditEvent]:
        return list(audit._events)

    async def _flush() -> None:
        pass

    async def _start() -> None:
        pass

    async def _stop() -> None:
        pass

    audit.log_event = _log_event
    audit.log_state_transition = _log_state_transition
    audit.log_governance_violation = _log_governance_violation
    audit.log_inference = _log_inference
    audit.get_events = _get_events
    audit.flush = _flush
    audit.start = _start
    audit.stop = _stop
    audit.get_violation_summary = AsyncMock(
        return_value={"by_severity": {}, "by_schema": {}, "total": 0, "period_start": None}
    )
    return audit


def create_mock_lineage() -> MagicMock:
    """Create a mock LineageTracker that records in memory."""
    lineage = MagicMock()
    lineage._traces: list[dict[str, Any]] = []
    lineage._inferences: list[dict[str, Any]] = []
    lineage._governance_influences: list[Any] = []
    lineage._memory_influences: list[MemoryInfluence] = []

    async def _start_trace(session_id: UUID) -> UUID:
        trace_id = uuid4()
        lineage._traces.append({
            "trace_id": trace_id,
            "session_id": session_id,
            "start_time": datetime.now(timezone.utc),
        })
        return trace_id

    async def _record_inference(trace_id: UUID, request: InferenceRequest, response: GovernedResponse, state: OperationalState) -> None:
        lineage._inferences.append({
            "trace_id": trace_id,
            "request_id": request.request_id,
            "response_id": response.response_id,
            "state": state,
        })

    async def _record_governance_influence(trace_id: UUID, check_results: list[GovernanceCheckResult]) -> None:
        lineage._governance_influences.extend(check_results)

    async def _record_memory_influence(trace_id: UUID, influences: list[MemoryInfluence]) -> None:
        lineage._memory_influences.extend(influences)

    async def _get_trace(trace_id: UUID) -> Any:
        return None

    async def _get_lineage_graph(trace_id: UUID) -> dict[str, Any]:
        return {
            "trace_id": str(trace_id),
            "node_count": 0,
            "edge_count": 0,
            "nodes": {},
            "edges": [],
        }

    lineage.start_trace = _start_trace
    lineage.record_inference = _record_inference
    lineage.record_governance_influence = _record_governance_influence
    lineage.record_memory_influence = _record_memory_influence
    lineage.get_trace = _get_trace
    lineage.get_lineage_graph = _get_lineage_graph
    return lineage


def create_mock_ollama_client(response_text: str | None = None) -> MagicMock:
    """Create a mock OllamaClient."""
    client = MagicMock()
    client.base_url = "http://localhost:11434"
    client.default_model = "llama3.1"
    default_response = (
        response_text
        or "Autonomous weapons raise significant ethical concerns. "
           "The development and deployment of lethal autonomous systems "
           "challenges existing frameworks of international humanitarian law. "
           "Key concerns include: accountability gaps when machines make "
           "life-or-death decisions, the potential for algorithmic bias in "
           "target selection, and the erosion of human dignity when lethal "
           "force is automated. Many experts argue that meaningful human "
           "control must be maintained over all weapons systems. "
           "Confidence: 0.82"
    )
    client.generate = AsyncMock(return_value=default_response)
    client.list_models = AsyncMock(return_value=["llama3.1", "mistral"])
    client.health_check = AsyncMock(return_value=True)
    client.close = AsyncMock()
    return client


# ===========================================================================
# Print helpers
# ===========================================================================

def print_demo_header(title: str, subtitle: str = "") -> None:
    """Print a formatted demo header with clear visual separation."""
    print()
    print(f"{_BOLD}{'=' * 70}{_RESET}")
    print(f"{_BOLD}{_CYAN}  DEMO: {title}{_RESET}")
    if subtitle:
        print(f"{_CYAN}  {subtitle}{_RESET}")
    print(f"{_BOLD}{'=' * 70}{_RESET}")
    print()


def print_section(title: str) -> None:
    """Print a section header."""
    print()
    print(f"{_BOLD}{'─' * 50}{_RESET}")
    print(f"  {_BOLD}{title}{_RESET}")
    print(f"{_BOLD}{'─' * 50}{_RESET}")


def print_subsection(title: str) -> None:
    """Print a subsection header."""
    print(f"\n  {_YELLOW}▸ {title}{_RESET}")


def print_result(name: str, passed: bool, detail: str = "") -> None:
    """Print a pass/fail result with optional detail."""
    status = f"{_GREEN}PASS{_RESET}" if passed else f"{_RED}FAIL{_RESET}"
    marker = f"{_GREEN}✓{_RESET}" if passed else f"{_RED}✗{_RESET}"
    print(f"  {marker} [{status}] {name}")
    if detail:
        print(f"         {detail}")


def print_kv(key: str, value: Any, indent: int = 2) -> None:
    """Print a key-value pair with consistent formatting."""
    prefix = " " * indent
    if isinstance(value, list):
        print(f"{prefix}{_BOLD}{key}:{_RESET}")
        for item in value:
            print(f"{prefix}    • {item}")
    elif isinstance(value, dict):
        print(f"{prefix}{_BOLD}{key}:{_RESET}")
        for k, v in value.items():
            print(f"{prefix}    {k}: {v}")
    elif isinstance(value, bool):
        colored = f"{_GREEN}{value}{_RESET}" if value else f"{_RED}{value}{_RESET}"
        print(f"{prefix}{_BOLD}{key}:{_RESET} {colored}")
    else:
        print(f"{prefix}{_BOLD}{key}:{_RESET} {value}")


# ===========================================================================
# Demo runner
# ===========================================================================

async def run_demo(demo_func, title: str) -> bool:
    """Run a demo function with proper setup, teardown, and crash handling.

    Args:
        demo_func: Async callable that returns list[tuple[str, bool]].
        title: Human-readable title for the demo.

    Returns:
        True if all steps passed, False otherwise.
    """
    print_demo_header(title)
    try:
        results = await demo_func()
        passed_count = sum(1 for _, p in results if p)
        total_count = len(results)

        print()
        print(f"  {('─' * 50)}")
        print(f"  Results: {passed_count}/{total_count} steps passed")

        if passed_count == total_count:
            print(f"\n  {_GREEN}{_BOLD}═══════════════════════════════════════════{_RESET}")
            print(f"  {_GREEN}{_BOLD}  DEMO PASSED — All steps completed successfully{_RESET}")
            print(f"  {_GREEN}{_BOLD}═══════════════════════════════════════════{_RESET}\n")
            return True
        else:
            print(f"\n  {_RED}{_BOLD}═══════════════════════════════════════════{_RESET}")
            print(f"  {_RED}{_BOLD}  DEMO FAILED — {total_count - passed_count} step(s) failed{_RESET}")
            print(f"  {_RED}{_BOLD}═══════════════════════════════════════════{_RESET}\n")
            return False

    except Exception as e:
        print(f"\n  {_RED}{_BOLD}DEMO CRASHED: {e}{_RESET}")
        import traceback
        traceback.print_exc()
        return False


# ===========================================================================
# Sample data factories
# ===========================================================================

def create_sample_inference_request(
    prompt: str | None = None,
    model: str = "llama3.1",
    governance_context: list[str] | None = None,
) -> InferenceRequest:
    """Create a sample InferenceRequest for demos."""
    return InferenceRequest(
        session_id=uuid4(),
        prompt=prompt or "What are the ethical implications of autonomous weapons systems?",
        model=model,
        governance_context=governance_context or [
            "uncertainty_management",
            "truthfulness_governance",
            "cognitive_humility",
            "boundary_preservation",
            "provenance_awareness",
        ],
        parameters={"temperature": 0.7, "max_tokens": 512},
    )


def create_sample_episodic_memories() -> list[EpisodicMemory]:
    """Create three sample episodic memories with different provenance."""
    session_id = uuid4()
    return [
        EpisodicMemory(
            session_id=session_id,
            episode_type="inference",
            content="Paris is the capital of France",
            provenance=ProvenanceRecord(
                source_schema="uncertainty_management",
                creator_component="test_data_factory",
            ),
            governance_influences=["uncertainty_management"],
            confidence=0.95,
        ),
        EpisodicMemory(
            session_id=session_id,
            episode_type="inference",
            content="The speed of light is 299,792,458 m/s",
            provenance=ProvenanceRecord(
                source_schema="truthfulness_governance",
                creator_component="test_data_factory",
            ),
            governance_influences=["truthfulness_governance"],
            confidence=0.99,
        ),
        EpisodicMemory(
            session_id=session_id,
            episode_type="inference",
            content="Climate change is caused by human activity",
            provenance=ProvenanceRecord(
                source_schema="evidence_coherence",
                creator_component="test_data_factory",
            ),
            governance_influences=["evidence_coherence"],
            confidence=0.88,
        ),
    ]


def create_mock_governed_response(
    request_id: UUID,
    raw_response: str = "",
    passed_validation: bool = True,
) -> GovernedResponse:
    """Create a sample GovernedResponse."""
    return GovernedResponse(
        request_id=request_id,
        raw_response=raw_response or "This is a test response. Confidence: 0.85",
        validated_response=raw_response or "This is a test response. Confidence: 0.85",
        passed_validation=passed_validation,
        validation_failures=[],
        memory_influences=[],
    )
