#!/usr/bin/env python3
"""GARVIS — Governed Cognition Observation Interface

The live operational CLI for GARVIS (Governance-Aware Reflective Virtual
Intelligence System). This is NOT a chatbot. This is a governed cognition
observation interface. The operator is an OBSERVER and GOVERNOR of the
cognition process.

Every prompt submission shows the full governance pipeline:
  mediation → inference → validation → governance checks → memory influence → trace → audit

Usage:
    python garvis_cli.py cognize --prompt "Your question here" [--model llama3.1]
    python garvis_cli.py schemas [--category epistemic]
    python garvis_cli.py trace --session-id <uuid>
    python garvis_cli.py audit --session-id <uuid> [--severity critical]
    python garvis_cli.py status
    python garvis_cli.py init
    python garvis_cli.py shutdown

Exit codes:
    0  — Success
    1  — General error
    2  — Governance blocked
    3  — Inference degraded
    4  — Fail-closed
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

# Ensure the project root is importable
PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Stub heavy dependencies that may not be installed.
# These modules are imported transitively but not needed for CLI operation.
# We inject lightweight stubs into sys.modules BEFORE loading GARVIS code.
# ---------------------------------------------------------------------------

def _inject_stubs() -> None:
    """Inject stub modules for heavy dependencies not needed by the CLI."""
    import types

    # Stub asyncpg
    if "asyncpg" not in sys.modules:
        asyncpg_stub = types.ModuleType("asyncpg")
        asyncpg_stub.connect = lambda *a, **k: None
        asyncpg_stub.create_pool = lambda *a, **k: None
        asyncpg_stub.Pool = type("Pool", (), {"acquire": lambda s: None, "close": lambda s: None})
        asyncpg_stub.Record = dict
        sys.modules["asyncpg"] = asyncpg_stub

    # Stub aiohttp (used by OllamaClient)
    if "aiohttp" not in sys.modules:
        aiohttp_stub = types.ModuleType("aiohttp")
        aiohttp_stub.ClientSession = lambda *a, **k: None
        aiohttp_stub.ClientTimeout = lambda *a, **k: None
        aiohttp_stub.ClientConnectionError = Exception
        sys.modules["aiohttp"] = aiohttp_stub

    # Stub database.connection
    if "database.connection" not in sys.modules:
        db_conn_stub = types.ModuleType("database.connection")
        db_conn_stub.DatabaseConnection = type(
            "DatabaseConnection", (), {
                "__init__": lambda s, *a, **k: None,
                "initialize_pool": lambda s, *a, **k: None,
                "execute": lambda s, *a, **k: None,
                "fetch": lambda s, *a, **k: [],
                "fetchrow": lambda s, *a, **k: None,
                "executemany": lambda s, *a, **k: None,
                "close": lambda s, *a, **k: None,
            },
        )
        db_conn_stub.close_pool = lambda: None
        db_conn_stub.initialize_pool = lambda *a, **k: None
        sys.modules["database.connection"] = db_conn_stub
        if "database" not in sys.modules:
            sys.modules["database"] = types.ModuleType("database")

    # Stub database.queries
    if "database.queries" not in sys.modules:
        queries_stub = types.ModuleType("database.queries")
        for qname in ["TRACE_INSERT", "CHECK_INSERT", "INFLUENCE_INSERT",
                      "AUDIT_INSERT", "AUDIT_INSERT_MANY", "TRANSITION_INSERT",
                      "VIOLATION_INSERT", "MEMORY_INSERT", "MEMORY_SEARCH_TEXT",
                      "MEMORY_GET_BY_ID", "MEMORY_GET_BY_SESSION", "MEMORY_UPDATE_ACCESS",
                      "TRACE_GET_BY_ID", "TRANSITION_GET_BY_TRACE", "AUDIT_GET_BY_TRACE",
                      "AUDIT_GET_FILTERED", "INFLUENCE_GET_BY_SESSION",
                      "CHECK_GET_BY_TRACE", "VIOLATION_SUMMARY", "Queries"]:
            setattr(queries_stub, qname, "")
        sys.modules["database.queries"] = queries_stub

    # Stub governance submodules with sentinel classes
    _validator_stub = types.ModuleType("governance.validator")
    _validator_stub.RuntimeValidator = type(
        "RuntimeValidator", (), {
            "__init__": lambda s, *a, **k: None,
            "validate_inference_request": lambda s, *a, **k: [],
            "validate_response": lambda s, *a, **k: [],
            "validate_memory_operation": lambda s, *a, **k: [],
            "validate_state_transition": lambda s, *a, **k: [],
            "has_critical_failure": lambda s, *a, **k: False,
            "build_violation": lambda s, *a, **k: None,
        },
    )
    sys.modules["governance.validator"] = _validator_stub

    _enforcer_stub = types.ModuleType("governance.enforcer")
    _enforcer_stub.EnforcementEngine = type(
        "EnforcementEngine", (), {
            "__init__": lambda s, *a, **k: None,
            "enforce_violation": lambda s, *a, **k: None,
            "halt_runtime": lambda s, *a, **k: None,
        },
    )
    sys.modules["governance.enforcer"] = _enforcer_stub

    _middleware_stub = types.ModuleType("governance.middleware")
    _middleware_stub.GovernanceMiddleware = type(
        "GovernanceMiddleware", (), {
            "__init__": lambda s, *a, **k: None,
            "activate": lambda s: None,
            "deactivate": lambda s: None,
            "is_active": False,
            "process_inference_request": lambda s, *a, **k: None,
            "process_inference_response": lambda s, *a, **k: None,
            "process_memory_store": lambda s, *a, **k: None,
            "process_memory_retrieval": lambda s, *a, **k: None,
            "process_state_transition": lambda s, *a, **k: None,
        },
    )
    sys.modules["governance.middleware"] = _middleware_stub

    # Stub memory components
    for mod_name in ["memory.store", "memory.retrieval", "memory.influence"]:
        if mod_name not in sys.modules:
            sys.modules[mod_name] = types.ModuleType(mod_name)

    # Stub traceability components
    for mod_name in ["traceability.audit", "traceability.lineage"]:
        if mod_name not in sys.modules:
            stub = types.ModuleType(mod_name)
            stub.AuditPipeline = type("AuditPipeline", (), {
                "__init__": lambda s, *a, **k: None,
                "log_event": lambda s, *a, **k: None,
                "log_state_transition": lambda s, *a, **k: None,
                "log_inference": lambda s, *a, **k: None,
                "flush": lambda s: None,
                "get_events": lambda s, *a, **k: [],
            })
            stub.LineageTracker = type("LineageTracker", (), {
                "__init__": lambda s, *a, **k: None,
                "start_trace": lambda s, *a, **k: __import__("uuid").uuid4(),
                "record_inference": lambda s, *a, **k: None,
                "get_trace": lambda s, *a, **k: None,
                "get_lineage_graph": lambda s, *a, **k: {"nodes": {}, "edges": []},
            })
            sys.modules[mod_name] = stub

    # Ensure all package namespaces exist
    for pkg in ["traceability", "memory", "database"]:
        if pkg not in sys.modules:
            sys.modules[pkg] = types.ModuleType(pkg)

    # ---- inference package (heavy __init__.py) ----
    _inf_stub = types.ModuleType("inference")
    sys.modules["inference"] = _inf_stub

    # ---- cognition package (lightweight __init__.py, should be OK) ----
    if "cognition" not in sys.modules:
        sys.modules["cognition"] = types.ModuleType("cognition")

    # ---- runtime package (heavy __init__.py) ----
    _rt_stub = types.ModuleType("runtime")
    sys.modules["runtime"] = _rt_stub


_inject_stubs()

# ---------------------------------------------------------------------------
# Direct module loading — bypasses package __init__.py to avoid pulling
# in heavy dependencies (asyncpg, etc.) that may not be installed.
# ---------------------------------------------------------------------------

def _load_module(module_name: str, file_path: Path):
    """Load a module directly from its file path."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {module_name} from {file_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


# Pre-load inference submodules before session_controller loads them
_inf_stub = sys.modules["inference"]
for _inf_sub in ["prompt_mediator", "response_validator", "ollama_client"]:
    _mod_path = PROJECT_ROOT / "inference" / f"{_inf_sub}.py"
    if _mod_path.exists() and f"inference.{_inf_sub}" not in sys.modules:
        _mod = _load_module(f"inference.{_inf_sub}", _mod_path)
        setattr(_inf_stub, _inf_sub, _mod)

# Pre-load cognition submodules before session_controller loads them
_cog_stub = sys.modules.get("cognition")
if _cog_stub is not None:
    for _cog_sub in ["state_machine", "session"]:
        _mod_path = PROJECT_ROOT / "cognition" / f"{_cog_sub}.py"
        if _mod_path.exists() and f"cognition.{_cog_sub}" not in sys.modules:
            _mod = _load_module(f"cognition.{_cog_sub}", _mod_path)
            setattr(_cog_stub, _cog_sub, _mod)

# Load runtime modules directly
_runtime_config_mod = _load_module(
    "runtime.config", PROJECT_ROOT / "runtime" / "config.py"
)
RuntimeConfig = _runtime_config_mod.RuntimeConfig

_session_controller_mod = _load_module(
    "runtime.session_controller", PROJECT_ROOT / "runtime" / "session_controller.py"
)
SessionController = _session_controller_mod.SessionController

_operator_interface_mod = _load_module(
    "runtime.operator_interface", PROJECT_ROOT / "runtime" / "operator_interface.py"
)
print_header = _operator_interface_mod.print_header
print_subheader = _operator_interface_mod.print_subheader
print_separator = _operator_interface_mod.print_separator
print_label_value = _operator_interface_mod.print_label_value
status_pass = _operator_interface_mod.status_pass
status_fail = _operator_interface_mod.status_fail
status_warn = _operator_interface_mod.status_warn
status_blocked = _operator_interface_mod.status_blocked
status_degraded = _operator_interface_mod.status_degraded
status_completed = _operator_interface_mod.status_completed
status_fail_closed = _operator_interface_mod.status_fail_closed
format_governance_checks = _operator_interface_mod.format_governance_checks
format_state_transitions = _operator_interface_mod.format_state_transitions
format_memory_influences = _operator_interface_mod.format_memory_influences
format_schema_table = _operator_interface_mod.format_schema_table
format_audit_events = _operator_interface_mod.format_audit_events
format_trace_graph_text = _operator_interface_mod.format_trace_graph_text
format_prompt = _operator_interface_mod.format_prompt
format_response = _operator_interface_mod.format_response
export_mermaid = _operator_interface_mod.export_mermaid
export_dot = _operator_interface_mod.export_dot
format_runtime_status = _operator_interface_mod.format_runtime_status
format_audit_event = _operator_interface_mod.format_audit_event
format_memory_influence = _operator_interface_mod.format_memory_influence
format_state_transition = _operator_interface_mod.format_state_transition

# Load governance registry directly
_governance_registry_mod = _load_module(
    "governance.registry", PROJECT_ROOT / "governance" / "registry.py"
)
GovernanceRegistry = _governance_registry_mod.GovernanceRegistry

# Load governance loader
_governance_loader_mod = _load_module(
    "governance.loader", PROJECT_ROOT / "governance" / "loader.py"
)
SchemaLoader = _governance_loader_mod.SchemaLoader

# Now set up the governance package stub to prevent __init__.py from running.
# We must create a proper NamespaceLoader package so 'from governance.X import Y' works.
import types as _types
from importlib.machinery import ModuleSpec, NamespaceLoader

_gov_loader = NamespaceLoader(str(PROJECT_ROOT / "governance"))
_gov_spec = ModuleSpec(
    "governance",
    _gov_loader,
    origin=str(PROJECT_ROOT / "governance"),
    is_package=True,
)
_gov_spec.submodule_search_locations = [str(PROJECT_ROOT / "governance")]
_gov_stub = _types.ModuleType("governance")
_gov_stub.__spec__ = _gov_spec
_gov_stub.__path__ = [str(PROJECT_ROOT / "governance")]
_gov_stub.__package__ = "governance"
_gov_stub.__loader__ = _gov_loader

# Expose key classes so 'from governance import X' works
_gov_stub.SchemaLoader = SchemaLoader
_gov_stub.GovernanceLoadError = Exception
_gov_stub.GovernanceRegistry = GovernanceRegistry

# Also wire submodule references so attribute access works
_gov_stub.registry = sys.modules["governance.registry"]
_gov_stub.validator = sys.modules["governance.validator"]
_gov_stub.enforcer = sys.modules["governance.enforcer"]
_gov_stub.middleware = sys.modules["governance.middleware"]
sys.modules["governance"] = _gov_stub

logger = logging.getLogger("garvis.cli")

# ---------------------------------------------------------------------------
# Global runtime state (singleton per process)
# ---------------------------------------------------------------------------

_runtime_state: dict[str, Any] = {
    "initialized": False,
    "registry": None,
    "config": None,
    "controller": None,
    "bootstrap": None,
    "started_at": None,
}


def _configure_logging(level: str = "WARNING") -> None:
    """Configure minimal logging for CLI use."""
    log_level = getattr(logging, level.upper(), logging.WARNING)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=sys.stderr,
    )


# ---------------------------------------------------------------------------
# Runtime initialization helpers
# ---------------------------------------------------------------------------

def _init_standalone() -> tuple[GovernanceRegistry, RuntimeConfig]:
    """Initialize governance in standalone mode (no database required).

    Loads the governance registry directly from the schema loader.
    This is sufficient for CLI operation without the full runtime.

    Returns:
        Tuple of (registry, config).
    """
    config = RuntimeConfig.from_env()

    # Initialize governance registry (SchemaLoader loaded at module level)
    loader = SchemaLoader(config.governance_schemas_path)
    registry = GovernanceRegistry(loader)
    registry.initialize()

    return registry, config


async def _init_full_runtime() -> dict[str, Any]:
    """Initialize the full GARVIS runtime via bootstrap.

    Returns:
        Dict of initialized components.

    Raises:
        Exception: If bootstrap fails.
    """
    from runtime.bootstrap import RuntimeBootstrap

    bootstrap = RuntimeBootstrap()
    components = await bootstrap.bootstrap()
    return {"bootstrap": bootstrap, "components": components}


def _ensure_initialized() -> tuple[GovernanceRegistry, RuntimeConfig, SessionController | None]:
    """Ensure governance is initialized.

    Returns:
        Tuple of (registry, config, controller). Controller is None if
        not yet created.
    """
    if not _runtime_state["initialized"]:
        print("Initializing GARVIS governance (standalone mode)...", file=sys.stderr)
        registry, config = _init_standalone()
        _runtime_state["registry"] = registry
        _runtime_state["config"] = config
        _runtime_state["initialized"] = True
        _runtime_state["started_at"] = datetime.now(timezone.utc)

    registry = _runtime_state["registry"]
    config = _runtime_state["config"]
    controller = _runtime_state["controller"]

    return registry, config, controller


# ---------------------------------------------------------------------------
# CLI subcommands
# ---------------------------------------------------------------------------


def cmd_cognize(args: argparse.Namespace) -> int:
    """Execute the 'cognize' command — submit a prompt through governed cognition.

    This is the primary operator-facing command. It shows the full
    governance pipeline: mediation, inference, validation, governance
    checks, memory influence, trace, and audit trail.
    """
    return asyncio.run(_cmd_cognize_async(args))


async def _cmd_cognize_async(args: argparse.Namespace) -> int:
    """Async implementation of the cognize command."""
    registry, config, _ = _ensure_initialized()

    # Create a fresh controller for this cognition cycle
    controller = SessionController(registry, config)
    _runtime_state["controller"] = controller

    prompt: str = args.prompt
    model: str | None = args.model

    # ------------------------------------------------------------------
    # Execute the governed cognition pipeline
    # ------------------------------------------------------------------

    result = await controller.submit(prompt, model)

    status = result["status"]

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    if args.json:
        # JSON output
        output = {
            "status": status,
            "trace_id": str(result["trace_id"]),
            "session_id": str(result["session_id"]),
            "elapsed_seconds": result["elapsed_seconds"],
            "request": {
                "request_id": str(result["request"].request_id),
                "model": result["request"].model,
                "prompt": result["request"].prompt,
            },
            "mediation": {
                "applied_schemas": result["mediation"].applied_schemas,
                "injected_constraints": result["mediation"].injected_constraints,
                "original_length": len(result["mediation"].original_prompt),
                "mediated_length": len(result["mediation"].mediated_prompt),
            },
            "response": None,
            "governance_checks": [
                {
                    "schema_id": c.schema_id,
                    "policy_id": c.policy_id,
                    "passed": c.passed,
                    "violation": (
                        c.violation.model_dump(mode="json") if c.violation else None
                    ),
                }
                for c in result["governance_checks"]
            ],
            "state_transitions": [
                {
                    "from_state": t.from_state.value,
                    "to_state": t.to_state.value,
                    "trigger": t.trigger,
                    "governance_check": t.governance_check,
                }
                for t in result["state_transitions"]
            ],
            "memory_influences": [
                {
                    "memory_id": str(m.memory_id),
                    "influence_type": m.influence_type,
                    "strength": m.strength,
                }
                for m in result["memory_influences"]
            ],
            "audit_event_count": len(result["audit_events"]),
        }

        response = result["response"]
        if response is not None:
            output["response"] = {
                "response_id": str(response.response_id),
                "passed_validation": response.passed_validation,
                "validation_failures": response.validation_failures,
                "raw_response_preview": response.raw_response[:500] if response.raw_response else None,
                "validated_response_preview": (
                    response.validated_response[:500] if response.validated_response else None
                ),
            }

        print(json.dumps(output, indent=2, default=str))
        return _exit_code_for_status(status)

    # ------------------------------------------------------------------
    # Human-readable output
    # ------------------------------------------------------------------

    # Banner
    print_header("GARVIS GOVERNED COGNITION")
    print(f"\n  {_configure_ansi('bold', 'white')}Trace:{_configure_ansi('reset')}  {_configure_ansi('cyan')}{result['trace_id']}{_configure_ansi('reset')}")
    print(f"  {_configure_ansi('bold', 'white')}Session:{_configure_ansi('reset')} {_configure_ansi('cyan')}{result['session_id']}{_configure_ansi('reset')}")
    print(f"  {_configure_ansi('bold', 'white')}Status:{_configure_ansi('reset')}  {_status_indicator(status)}")
    print(f"  {_configure_ansi('bold', 'white')}Model:{_configure_ansi('reset')}   {result['request'].model}")
    print(f"  {_configure_ansi('bold', 'white')}Elapsed:{_configure_ansi('reset')} {result['elapsed_seconds']:.3f}s")

    # MEDIATION section
    if args.show_mediation or not args.show_trace:
        print_header("MEDIATION")
        mediation = result["mediation"]
        print(f"\n  {_configure_ansi('bold', 'blue')}Applied Schemas:{_configure_ansi('reset')} {mediation.applied_schemas}")
        print(f"  {_configure_ansi('bold', 'blue')}Injected Constraints:{_configure_ansi('reset')} {len(mediation.injected_constraints)}")
        for constraint in mediation.injected_constraints:
            print(f"    {_configure_ansi('magenta')}•{_configure_ansi('reset')} {constraint}")

        if args.show_mediation:
            print(format_prompt(mediation.mediated_prompt, "MEDIATED PROMPT"))

    # INFERENCE section
    print_header("INFERENCE")
    print(format_prompt(result["request"].prompt, "ORIGINAL PROMPT"))
    response = result["response"]
    if response is not None and response.validated_response:
        print(format_response(response.validated_response, "VALIDATED RESPONSE"))
    elif response is not None:
        print(format_response(response.raw_response, "RAW RESPONSE"))
    else:
        print(format_response(None))

    # VALIDATION section
    print_header("VALIDATION")
    if response is not None:
        if response.passed_validation:
            print(f"\n  {status_pass('PASSED')}  All governance checks passed")
        else:
            print(f"\n  {status_fail('FAILED')}  Critical governance checks failed")
            if response.validation_failures:
                print(f"\n  {_configure_ansi('bold', 'red')}Failures:{_configure_ansi('reset')}")
                for failure in response.validation_failures:
                    print(f"    {_configure_ansi('red')}•{_configure_ansi('reset')} {failure}")
    else:
        print(f"\n  {status_blocked()}  No response — inference was blocked or failed")

    # GOVERNANCE section
    if args.show_governance or not args.show_trace:
        print_header("GOVERNANCE")
        print(format_governance_checks(result["governance_checks"]))

    # MEMORY INFLUENCE section
    if args.show_memory or not args.show_trace:
        print_header("MEMORY INFLUENCE")
        print(format_memory_influences(result["memory_influences"]))

    # TRACE section
    if args.show_trace:
        print_header("TRACE")
        trace_data = {
            "trace_id": result["trace_id"],
            "session_id": result["session_id"],
            "status": status,
            "state_transitions": result["state_transitions"],
            "governance_checks": result["governance_checks"],
            "response": response,
        }
        print(format_trace_graph_text(trace_data))

    # AUDIT section
    if args.show_audit or not args.show_trace:
        print_header("AUDIT TRAIL")
        print(format_audit_events(result["audit_events"]))

    # Footer
    print_separator()
    print(f"\n  {_configure_ansi('dim')}Cognition cycle complete — status: {status}{_configure_ansi('reset')}\n")

    return _exit_code_for_status(status)


def _configure_ansi(*codes: str) -> str:
    """Helper to get ANSI codes."""
    ansi_codes = {
        "reset": "\033[0m",
        "bold": "\033[1m",
        "dim": "\033[2m",
        "green": "\033[32m",
        "red": "\033[31m",
        "yellow": "\033[33m",
        "blue": "\033[34m",
        "magenta": "\033[35m",
        "cyan": "\033[36m",
        "white": "\033[37m",
        "bright_green": "\033[92m",
        "bright_red": "\033[91m",
        "bright_yellow": "\033[93m",
        "bright_blue": "\033[94m",
        "bright_magenta": "\033[95m",
        "bright_cyan": "\033[96m",
    }
    if not sys.stdout.isatty():
        return ""
    return "".join(ansi_codes.get(c, "") for c in codes)


def _status_indicator(status: str) -> str:
    """Get a visual status indicator."""
    if status == "completed":
        return status_completed()
    elif status == "blocked":
        return status_blocked()
    elif status == "degraded":
        return status_degraded()
    elif status == "fail_closed":
        return status_fail_closed()
    else:
        return status_warn(status.upper())


def _exit_code_for_status(status: str) -> int:
    """Map status to exit code."""
    return {
        "completed": 0,
        "blocked": 2,
        "degraded": 3,
        "fail_closed": 4,
    }.get(status, 1)


def cmd_schemas(args: argparse.Namespace) -> int:
    """Execute the 'schemas' command — list active governance schemas."""
    registry, _, _ = _ensure_initialized()

    category_filter: str | None = args.category

    schemas = registry.get_all_schemas()
    if category_filter:
        schemas = [s for s in schemas if s.category == category_filter]

    if args.json:
        output = [
            {
                "schema_id": s.schema_id,
                "name": s.name,
                "version": s.version,
                "category": s.category,
                "policies": len(s.policies),
                "constraints": len(s.constraints),
                "fail_closed": s.fail_closed,
            }
            for s in schemas
        ]
        print(json.dumps(output, indent=2))
        return 0

    # Header
    print_header("GOVERNANCE SCHEMAS")

    if category_filter:
        print(f"\n  Filtered by category: {_configure_ansi('blue', 'bold')}{category_filter}{_configure_ansi('reset')}")

    active_ids = set(registry.get_active_schema_ids())
    schemas_display = []
    for s in schemas:
        # Annotate with active status
        class _SchemaDisplay:
            pass
        sd = _SchemaDisplay()
        sd.schema_id = s.schema_id
        sd.name = s.name
        sd.version = s.version
        sd.category = s.category
        sd.policies = s.policies
        sd.constraints = s.constraints
        sd.is_active = s.schema_id in active_ids
        schemas_display.append(sd)

    # Simple display
    if not schemas_display:
        print(f"\n  {_configure_ansi('dim')}(no schemas found){_configure_ansi('reset')}")
        return 0

    print(f"\n  {_configure_ansi('bold', 'white')}Total:{_configure_ansi('reset')} {len(schemas_display)} schema(s)")
    print(f"  {_configure_ansi('bold', 'white')}Active:{_configure_ansi('reset')} {len([s for s in schemas_display if s.is_active])}")
    print("")

    # Column header
    id_w = max(max(len(s.schema_id) for s in schemas_display), 20)
    name_w = max(max(len(s.name) for s in schemas_display), 18)

    header = (
        f"  {_configure_ansi('bold')}{'Active':<8} {'Schema ID':<{id_w}} {'Name':<{name_w}} "
        f"{'Version':<8} {'Category':<14} {'Policies':>8} {'Constraints':>11}{_configure_ansi('reset')}"
    )
    sep = (
        f"  {'─' * 8} {'─' * id_w} {'─' * name_w} "
        f"{'─' * 8} {'─' * 14} {'─' * 8} {'─' * 11}"
    )
    print(header)
    print(sep)

    for s in schemas_display:
        active_marker = f"{_configure_ansi('green')}● ACTIVE{_configure_ansi('reset')}" if s.is_active else f"{_configure_ansi('dim')}  —{_configure_ansi('reset')}"
        sid_fmt = f"{_configure_ansi('magenta')}{s.schema_id}{_configure_ansi('reset')}"
        cat_color = "blue" if s.category == "epistemic" else "green" if s.category == "operational" else "yellow"
        cat_fmt = f"{_configure_ansi(cat_color)}{s.category}{_configure_ansi('reset')}"

        # We need to account for ANSI codes in width — simplified approach
        line = (
            f"  {active_marker:<{18 if s.is_active else 10}}"
        )
        print(line + f" {_configure_ansi('magenta')}{s.schema_id:<{id_w}}{_configure_ansi('reset')} "
              f"{s.name:<{name_w}} "
              f"{_configure_ansi('dim')}{s.version:<8}{_configure_ansi('reset')} "
              f"{cat_fmt:<{22}} "
              f"{_configure_ansi('white')}{len(s.policies):>8}{_configure_ansi('reset')} "
              f"{_configure_ansi('white')}{len(s.constraints):>11}{_configure_ansi('reset')}")

    print("")
    return 0


def cmd_trace(args: argparse.Namespace) -> int:
    """Execute the 'trace' command — display cognition trace for a session."""
    registry, config, controller = _ensure_initialized()

    session_id_str: str = args.session_id
    output_format: str = args.format

    try:
        session_id = UUID(session_id_str)
    except ValueError:
        print(f"{_configure_ansi('red')}Error: Invalid UUID: {session_id_str}{_configure_ansi('reset')}", file=sys.stderr)
        return 1

    # Get or create controller
    if controller is None:
        controller = SessionController(registry, config)
        _runtime_state["controller"] = controller

    # Get session
    session = controller.get_session(session_id)
    if session is None:
        # Show a message — session may have ended
        print(f"{_configure_ansi('yellow')}Note: Session {session_id} not found or has ended.{_configure_ansi('reset')}")
        print(f"  Sessions are ephemeral — traces are only available for active sessions.")
        return 0

    # Build trace from session data
    trace_data = {
        "trace_id": session.trace_id,
        "session_id": session.session_id,
        "status": "unknown",
        "state_transitions": [],
        "governance_checks": [],
        "response": None,
    }

    # Get audit events from controller
    audit_events = controller.get_session_audit_trail(session_id)

    if output_format == "json":
        output = {
            "session_id": str(session.session_id),
            "trace_id": str(session.trace_id),
            "created_at": session.created_at.isoformat(),
            "current_state": session.current_state.value,
            "is_active": session.is_active,
            "active_schemas": session.active_schemas,
            "audit_event_count": len(audit_events),
        }
        print(json.dumps(output, indent=2, default=str))
        return 0

    if output_format == "mermaid":
        graph = {
            "trace_id": str(session.trace_id),
            "nodes": {
                f"trace:{session.trace_id}": {
                    "type": "trace",
                    "label": f"Trace {str(session.trace_id)[:8]}",
                    "session_id": str(session.session_id),
                },
                f"session:{session.session_id}": {
                    "type": "session",
                    "label": f"Session {str(session.session_id)[:8]}",
                },
            },
            "edges": [
                {"from": f"trace:{session.trace_id}", "to": f"session:{session.session_id}", "type": "belongs_to"},
            ],
        }
        print(export_mermaid(graph))
        return 0

    if output_format == "dot":
        graph = {
            "trace_id": str(session.trace_id),
            "nodes": {
                f"trace:{session.trace_id}": {
                    "type": "trace",
                    "label": f"Trace {str(session.trace_id)[:8]}",
                },
                f"session:{session.session_id}": {
                    "type": "session",
                    "label": f"Session {str(session.session_id)[:8]}",
                },
            },
            "edges": [
                {"from": f"trace:{session.trace_id}", "to": f"session:{session.session_id}", "type": "belongs_to"},
            ],
        }
        print(export_dot(graph))
        return 0

    # Default text format
    print_header("COGNITION TRACE")
    print(f"\n  {_configure_ansi('bold')}Session:{_configure_ansi('reset')}     {_configure_ansi('cyan')}{session.session_id}{_configure_ansi('reset')}")
    print(f"  {_configure_ansi('bold')}Trace:{_configure_ansi('reset')}       {_configure_ansi('cyan')}{session.trace_id}{_configure_ansi('reset')}")
    print(f"  {_configure_ansi('bold')}State:{_configure_ansi('reset')}       {_configure_ansi('blue')}{session.current_state.value}{_configure_ansi('reset')}")
    print(f"  {_configure_ansi('bold')}Active:{_configure_ansi('reset')}      {session.is_active}")
    print(f"  {_configure_ansi('bold')}Created:{_configure_ansi('reset')}     {session.created_at.isoformat()}")
    print(f"  {_configure_ansi('bold')}Schemas:{_configure_ansi('reset')}     {session.active_schemas}")

    if audit_events:
        print(f"\n  {_configure_ansi('bold')}Audit Events:{_configure_ansi('reset')} {len(audit_events)}")
        for event in audit_events[:20]:  # Show first 20
            print(format_audit_event(event))
    else:
        print(f"\n  {_configure_ansi('dim')}(no audit events recorded){_configure_ansi('reset')}")

    print("")
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    """Execute the 'audit' command — display audit events for a session."""
    registry, config, controller = _ensure_initialized()

    session_id_str: str = args.session_id
    event_type_filter: str | None = args.event_type
    severity_filter: str | None = args.severity
    limit: int = args.limit

    try:
        session_id = UUID(session_id_str)
    except ValueError:
        print(f"{_configure_ansi('red')}Error: Invalid UUID: {session_id_str}{_configure_ansi('reset')}", file=sys.stderr)
        return 1

    # Get or create controller
    if controller is None:
        controller = SessionController(registry, config)
        _runtime_state["controller"] = controller

    # Get all audit events and filter
    all_events = controller.get_session_audit_trail(session_id)

    filtered = all_events
    if event_type_filter:
        filtered = [e for e in filtered if e.event_type == event_type_filter]
    if severity_filter:
        filtered = [e for e in filtered if e.severity == severity_filter]

    filtered = filtered[:limit]

    if args.json:
        output = [
            {
                "event_id": str(e.event_id),
                "event_type": e.event_type,
                "severity": e.severity,
                "component": e.component,
                "timestamp": e.timestamp.isoformat(),
                "details": e.details,
            }
            for e in filtered
        ]
        print(json.dumps(output, indent=2, default=str))
        return 0

    # Human-readable
    print_header("AUDIT TRAIL")
    print(f"\n  {_configure_ansi('bold')}Session:{_configure_ansi('reset')} {_configure_ansi('cyan')}{session_id}{_configure_ansi('reset')}")
    print(f"  {_configure_ansi('bold')}Total Events:{_configure_ansi('reset')} {len(all_events)}")
    if event_type_filter:
        print(f"  {_configure_ansi('bold')}Type Filter:{_configure_ansi('reset')} {event_type_filter}")
    if severity_filter:
        print(f"  {_configure_ansi('bold')}Severity Filter:{_configure_ansi('reset')} {severity_filter}")
    print(f"  {_configure_ansi('bold')}Showing:{_configure_ansi('reset')} {len(filtered)} (limit: {limit})")
    print("")
    print(format_audit_events(filtered))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Execute the 'status' command — show runtime status."""
    registry, config, controller = _ensure_initialized()

    # Compute uptime
    uptime: float | None = None
    if _runtime_state["started_at"] is not None:
        uptime = (datetime.now(timezone.utc) - _runtime_state["started_at"]).total_seconds()

    # Component health
    component_health: dict[str, bool] = {
        "governance_registry": True,
        "session_controller": controller is not None,
    }

    # Try to check Ollama health
    try:
        _ollama_mod = _load_module(
            "inference.ollama_client", PROJECT_ROOT / "inference" / "ollama_client.py"
        )
        OllamaClient = _ollama_mod.OllamaClient
        ollama = OllamaClient(config.ollama_host, config.default_model)
        # Fire-and-forget health check
        loop = asyncio.new_event_loop()
        try:
            healthy = loop.run_until_complete(
                asyncio.wait_for(ollama.health_check(), timeout=2.0)
            )
            component_health["ollama"] = healthy
        except Exception:
            component_health["ollama"] = False
        finally:
            loop.run_until_complete(ollama.close())
            loop.close()
    except Exception:
        component_health["ollama"] = False

    active_schemas = registry.get_active_schema_ids()
    session_count = len(controller.list_sessions()) if controller else 0

    if args.json:
        output = {
            "initialized": _runtime_state["initialized"],
            "operational_state": "standby",  # CLI always in standby
            "uptime_seconds": uptime,
            "active_schemas": active_schemas,
            "active_sessions": session_count,
            "component_health": component_health,
        }
        print(json.dumps(output, indent=2, default=str))
        return 0

    # Human-readable
    format_runtime_status(
        state="standby",
        active_schemas=active_schemas,
        uptime=uptime,
        component_health=component_health,
        session_count=session_count,
    )
    print("")  # trailing newline
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    """Execute the 'init' command — initialize the runtime."""
    print_header("INITIALIZING GARVIS RUNTIME")
    print("")

    try:
        registry, config = _init_standalone()
        _runtime_state["registry"] = registry
        _runtime_state["config"] = config
        _runtime_state["initialized"] = True
        _runtime_state["started_at"] = datetime.now(timezone.utc)

        active_schemas = registry.get_active_schema_ids()
        schemas = registry.get_all_schemas()

        print(f"  {status_pass('OK')}  Governance registry initialized")
        print(f"  {status_info('INFO')}  Loaded {len(schemas)} schema(s), {len(active_schemas)} active")
        print(f"")

        for sid in active_schemas:
            schema = registry.get_schema(sid)
            if schema:
                print(f"    {_configure_ansi('green')}●{_configure_ansi('reset')} {_configure_ansi('magenta')}{sid}{_configure_ansi('reset')} — {schema.name} (v{schema.version})")

        print(f"\n  {_configure_ansi('green', 'bold')}Runtime initialized — state: STANDBY{_configure_ansi('reset')}")
        print(f"  {_configure_ansi('dim')}Ready for governed cognition operations.{_configure_ansi('reset')}")
        print("")
        return 0

    except Exception as exc:
        print(f"\n  {status_fail('FAIL')}  Initialization failed: {exc}", file=sys.stderr)
        return 1


def cmd_shutdown(args: argparse.Namespace) -> int:
    """Execute the 'shutdown' command — graceful shutdown."""
    print_header("SHUTTING DOWN GARVIS")
    print("")

    if not _runtime_state["initialized"]:
        print(f"  {status_warn('WARN')}  Runtime was not initialized — nothing to shut down")
        print("")
        return 0

    # Note: In standalone mode there's no background runtime to stop.
    # In full-runtime mode, we would call bootstrap.shutdown().
    if _runtime_state["bootstrap"] is not None:
        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(_runtime_state["bootstrap"].shutdown())
            loop.close()
            print(f"  {status_pass('OK')}  Full runtime shutdown complete")
        except Exception as exc:
            print(f"  {status_fail('FAIL')}  Shutdown error: {exc}", file=sys.stderr)

    # Mark as uninitialized
    _runtime_state["initialized"] = False
    _runtime_state["registry"] = None
    _runtime_state["controller"] = None
    _runtime_state["bootstrap"] = None
    _runtime_state["started_at"] = None

    print(f"  {status_pass('OK')}  Runtime shut down")
    print(f"\n  {_configure_ansi('dim')}Goodbye.{_configure_ansi('reset')}")
    print("")
    return 0


# ---------------------------------------------------------------------------
# Argument parser setup
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="garvis_cli.py",
        description="GARVIS — Governed Cognition Observation Interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This is NOT a chatbot. This is a governed cognition observation interface.
The operator is an OBSERVER and GOVERNOR of the cognition process.

Every prompt submission shows the full governance pipeline:
  mediation → inference → validation → governance → memory → trace → audit

Exit codes:
  0  — Success / Completed
  1  — General error
  2  — Governance blocked
  3  — Inference degraded
  4  — Fail-closed
        """,
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output as JSON (global default for all commands)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- cognize ---
    cognize_parser = subparsers.add_parser(
        "cognize",
        help="Submit a prompt through governed cognition",
        description="Submit a prompt through the full governed cognition pipeline.",
    )
    cognize_parser.add_argument(
        "--prompt", "-p",
        type=str,
        required=True,
        help="The prompt to submit",
    )
    cognize_parser.add_argument(
        "--model", "-m",
        type=str,
        default=None,
        help="Ollama model to use (default: from config)",
    )
    cognize_parser.add_argument(
        "--show-mediation",
        action="store_true",
        help="Display the mediated prompt",
    )
    cognize_parser.add_argument(
        "--show-governance",
        action="store_true",
        help="Display governance checks applied",
    )
    cognize_parser.add_argument(
        "--show-trace",
        action="store_true",
        help="Display trace graph (text format)",
    )
    cognize_parser.add_argument(
        "--show-audit",
        action="store_true",
        help="Display audit events",
    )
    cognize_parser.add_argument(
        "--show-memory",
        action="store_true",
        help="Display memory influences",
    )
    cognize_parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output as JSON instead of human-readable",
    )

    # --- schemas ---
    schemas_parser = subparsers.add_parser(
        "schemas",
        help="List active governance schemas",
    )
    schemas_parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="Filter by category",
    )
    schemas_parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output as JSON",
    )

    # --- trace ---
    trace_parser = subparsers.add_parser(
        "trace",
        help="Display cognition trace for a session",
    )
    trace_parser.add_argument(
        "--session-id",
        type=str,
        required=True,
        help="The session to trace",
    )
    trace_parser.add_argument(
        "--format",
        type=str,
        choices=["text", "dot", "mermaid", "json"],
        default="text",
        help="Output format (default: text)",
    )

    # --- audit ---
    audit_parser = subparsers.add_parser(
        "audit",
        help="Display audit events for a session",
    )
    audit_parser.add_argument(
        "--session-id",
        type=str,
        required=True,
        help="The session to query",
    )
    audit_parser.add_argument(
        "--event-type",
        type=str,
        default=None,
        help="Filter by event type",
    )
    audit_parser.add_argument(
        "--severity",
        type=str,
        default=None,
        help="Filter by severity",
    )
    audit_parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Max events to show (default: 50)",
    )
    audit_parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output as JSON",
    )

    # --- status ---
    status_parser = subparsers.add_parser(
        "status",
        help="Show runtime status",
    )
    status_parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output as JSON",
    )

    # --- init ---
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize the runtime (bootstrap)",
    )

    # --- shutdown ---
    shutdown_parser = subparsers.add_parser(
        "shutdown",
        help="Graceful shutdown",
    )

    return parser


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def main() -> int:
    """Main async entry point for the GARVIS CLI."""
    parser = build_parser()
    args = parser.parse_args()

    # Configure logging
    log_level = "INFO" if args.verbose else "WARNING"
    _configure_logging(log_level)

    # Dispatch to command handler
    if args.command == "cognize":
        return cmd_cognize(args)
    elif args.command == "schemas":
        return cmd_schemas(args)
    elif args.command == "trace":
        return cmd_trace(args)
    elif args.command == "audit":
        return cmd_audit(args)
    elif args.command == "status":
        return cmd_status(args)
    elif args.command == "init":
        return cmd_init(args)
    elif args.command == "shutdown":
        return cmd_shutdown(args)
    else:
        parser.print_help()
        return 0


def _sync_main() -> int:
    """Synchronous wrapper for the async main."""
    return asyncio.run(main())


if __name__ == "__main__":
    sys.exit(_sync_main())
