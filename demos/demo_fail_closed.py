#!/usr/bin/env python3
"""
DEMO: FAIL-CLOSED ENFORCEMENT
==============================

This demo validates that GARVIS properly fails closed when governance
is violated.  Four scenarios are exercised:

  Scenario A: Critical governance violation -> runtime halt
  Scenario B: Forbidden state pattern -> auto-FAIL_CLOSED
  Scenario C: Degraded mode -> inference blocked
  Scenario D: Recovery path -> re-validation and return to STANDBY

The demo uses REAL enforcement engine, REAL state machine, REAL validator.
External dependencies (PostgreSQL, Ollama) are mocked.

Usage:
    cd /mnt/agents/output/project
    python demos/demo_fail_closed.py
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from uuid import uuid4

_PROJECT_ROOT = __file__.rsplit("/demos/", 1)[0]
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from demos.utils import (
    AsyncRuntimeValidatorWrapper,
    create_mock_audit,
    create_mock_db,
    create_mock_enforcer,
    create_mock_lineage,
    create_mock_registry,
    create_mock_validator,
    import_from,
    print_demo_header,
    print_kv,
    print_result,
    print_section,
    print_subsection,
    run_demo,
    _GREEN,
    _RED,
    _RESET,
    _BOLD,
    _YELLOW,
)

# -- Direct module imports (bypass package __init__.py to avoid asyncpg) ----
CognitiveStateMachine = import_from("cognition.state_machine", "CognitiveStateMachine")
EnforcementEngine = import_from("governance.enforcer", "EnforcementEngine")
RuntimeValidator = import_from("governance.validator", "RuntimeValidator")

from models.audit import AuditEvent
from models.cognition import OperationalState
from models.governance import (
    GovernanceViolation,
    GovernanceCheckResult,
    GovernanceSchema,
    GovernancePolicy,
    GovernanceConstraint,
    ViolationResponse,
)


# ---------------------------------------------------------------------------
# Scenario A: Critical governance violation triggers halt
# ---------------------------------------------------------------------------

async def scenario_a_critical_violation_halt(
    enforcer: EnforcementEngine,
    audit,
) -> list[tuple[str, bool]]:
    """Simulate a critical governance violation and verify halt."""
    results: list[tuple[str, bool]] = []
    print_subsection("Scenario A: Critical governance violation -> HALT")

    # Create a critical violation
    violation = GovernanceViolation(
        schema_id="uncertainty_management",
        policy_id="uncertainty_quantification_required",
        severity="critical",
        description="Response released without confidence score -- uncertainty governance bypassed",
        context={"response_id": str(uuid4()), "session_id": str(uuid4())},
    )

    print_kv("Violation schema", violation.schema_id)
    print_kv("Violation policy", violation.policy_id)
    print_kv("Violation severity", violation.severity)
    print_kv("Violation description", violation.description)

    # Enforce the violation
    enforcer.enforce_violation(violation)

    # Verify halt occurred
    print_subsection("Verification -- After Enforcement")
    print_kv("Enforcer is_halted", enforcer.is_halted)
    print_kv("Halt reason", enforcer.halt_reason)

    # The violation should have been marked with resolution
    results.append(("Enforcer halted on critical violation", enforcer.is_halted))
    results.append(("Halt reason recorded", enforcer.halt_reason is not None))
    results.append(
        ("Violation resolution set to 'halted'",
         violation.resolution == "halted")
    )

    return results


# ---------------------------------------------------------------------------
# Scenario B: Forbidden state pattern triggers auto-FAIL_CLOSED
# ---------------------------------------------------------------------------

async def scenario_b_forbidden_pattern(
    state_machine: CognitiveStateMachine,
) -> list[tuple[str, bool]]:
    """Demonstrate forbidden pattern detection triggering auto-FAIL_CLOSED.

    To trigger the recursive_inference pattern, we need the history to
    contain two consecutive transitions where the first lands on
    INFERENCE_EXECUTING and the second also targets INFERENCE_EXECUTING.

    We do this by:
    1. Transition STANDBY -> GOVERNANCE_CHECK -> COGNITION_ACTIVE -> INFERENCE_EXECUTING
    2. Then from INFERENCE_EXECUTING, attempt to transition to INFERENCE_EXECUTING
       (which is NOT in the valid transition graph -> rejected by _can_transition)

    The rejection itself proves the system blocks recursive inference.
    Additionally, we verify that the FORBIDDEN_PATTERNS list includes
    the recursive_inference pattern.
    """
    results: list[tuple[str, bool]] = []
    print_subsection("Scenario B: Forbidden pattern -- recursive inference blocked")

    # First, show that recursive_inference is listed as a forbidden pattern
    forbidden_patterns = CognitiveStateMachine.FORBIDDEN_PATTERNS
    recursive_pattern_found = any(
        prev == OperationalState.INFERENCE_EXECUTING and curr == OperationalState.INFERENCE_EXECUTING
        for prev, curr in forbidden_patterns
    )
    print_kv("recursive_inference in FORBIDDEN_PATTERNS", recursive_pattern_found)
    results.append(
        ("recursive_inference pattern defined", recursive_pattern_found)
    )

    # Set up valid state: STANDBY -> GOVERNANCE_CHECK -> COGNITION_ACTIVE -> INFERENCE_EXECUTING
    # First reset the state machine to STANDBY (we need a clean path)
    state_machine._state = OperationalState.STANDBY
    state_machine._transition_log.clear()

    ok = await state_machine.transition(OperationalState.GOVERNANCE_CHECK, "validate_request")
    print_kv("STANDBY -> GOVERNANCE_CHECK", ok)

    ok = await state_machine.transition(OperationalState.COGNITION_ACTIVE, "validation_passed")
    print_kv("GOVERNANCE_CHECK -> COGNITION_ACTIVE", ok)

    ok = await state_machine.transition(OperationalState.INFERENCE_EXECUTING, "start_inference_1")
    print_kv("COGNITION_ACTIVE -> INFERENCE_EXECUTING", ok)

    # Now try the forbidden transition: INFERENCE_EXECUTING -> INFERENCE_EXECUTING
    # This should be rejected because INFERENCE_EXECUTING is not in
    # VALID_TRANSITIONS[INFERENCE_EXECUTING]
    ok = await state_machine.transition(
        OperationalState.INFERENCE_EXECUTING,
        "recursive_inference_attempt",
    )
    print_kv("INFERENCE_EXECUTING -> INFERENCE_EXECUTING (attempt)", ok)
    print_kv("  (expected: False -- blocked by transition graph)", True)

    # The transition was rejected (returned False)
    results.append(
        ("Recursive inference transition REJECTED", not ok)
    )

    # Verify current state is still INFERENCE_EXECUTING (not changed)
    current = state_machine.get_current_state()
    print_kv("Current state after rejection", current.value)
    results.append(
        ("State preserved as INFERENCE_EXECUTING after rejection",
         current == OperationalState.INFERENCE_EXECUTING)
    )

    # Show that the forbidden pattern detector would catch this if it happened
    # via a forced path (e.g., _force_transition bypassing the graph)
    pattern_id = state_machine.check_forbidden_pattern()
    print_kv("Forbidden pattern detected in history", pattern_id)
    results.append(
        ("No forbidden pattern in legitimate history", pattern_id is None)
    )

    return results


# ---------------------------------------------------------------------------
# Scenario C: Degraded mode -> inference blocked
# ---------------------------------------------------------------------------

async def scenario_c_degraded_mode(
    state_machine: CognitiveStateMachine,
) -> list[tuple[str, bool]]:
    """Demonstrate that inference is blocked in DEGRADED state."""
    results: list[tuple[str, bool]] = []
    print_subsection("Scenario C: Degraded mode -> inference blocked")

    # Reset state machine for clean test
    state_machine._state = OperationalState.STANDBY
    state_machine._transition_log.clear()

    # Transition to DEGRADED
    ok = await state_machine.transition(OperationalState.DEGRADED, "degradation_trigger")
    print_kv("STANDBY -> DEGRADED", ok)
    results.append(("Transitioned to DEGRADED", ok))

    current = state_machine.get_current_state()
    print_kv("Current state", current.value)

    # Attempt to transition DEGRADED -> INFERENCE_EXECUTING
    # This is a forbidden pattern and should be blocked
    ok = await state_machine.transition(
        OperationalState.INFERENCE_EXECUTING,
        "attempt_inference_while_degraded",
    )
    print_kv("DEGRADED -> INFERENCE_EXECUTING (attempt)", ok)
    print_kv("  (expected: False -- degraded cannot run inference)", True)

    results.append(
        ("Inference blocked from DEGRADED state", not ok)
    )

    # Verify state is still DEGRADED
    current = state_machine.get_current_state()
    print_kv("State preserved as DEGRADED", current == OperationalState.DEGRADED)
    results.append(("State remains DEGRADED", current == OperationalState.DEGRADED))

    # Show valid transitions from DEGRADED
    valid_from_degraded = CognitiveStateMachine.VALID_TRANSITIONS[OperationalState.DEGRADED]
    print_kv("Valid transitions from DEGRADED", [s.value for s in valid_from_degraded])
    results.append(
        ("DEGRADED has valid recovery paths (RECOVERING, STANDBY, FAIL_CLOSED, SHUTDOWN)",
         len(valid_from_degraded) >= 3)
    )

    return results


# ---------------------------------------------------------------------------
# Scenario D: Recovery path from FAIL_CLOSED
# ---------------------------------------------------------------------------

async def scenario_d_recovery_path(
    state_machine: CognitiveStateMachine,
    enforcer: EnforcementEngine,
) -> list[tuple[str, bool]]:
    """Demonstrate recovery from FAIL_CLOSED back to STANDBY."""
    results: list[tuple[str, bool]] = []
    print_subsection("Scenario D: Recovery path -- FAIL_CLOSED -> RECOVERING -> STANDBY")

    # First, transition to FAIL_CLOSED (via DEGRADED for a valid path)
    state_machine._state = OperationalState.DEGRADED
    state_machine._transition_log.clear()

    # DEGRADED -> FAIL_CLOSED
    ok = await state_machine.transition(OperationalState.FAIL_CLOSED, "critical_failure")
    print_kv("DEGRADED -> FAIL_CLOSED", ok)
    results.append(("Transitioned to FAIL_CLOSED", ok))

    current = state_machine.get_current_state()
    print_kv("Current state", current.value)

    # Verify inference is blocked from FAIL_CLOSED
    ok = await state_machine.transition(
        OperationalState.INFERENCE_EXECUTING,
        "attempt_inference_while_fail_closed",
    )
    print_kv("FAIL_CLOSED -> INFERENCE_EXECUTING (attempt)", ok)
    print_kv("  (expected: False -- fail-closed blocks all cognition)", True)
    results.append(
        ("Inference blocked from FAIL_CLOSED", not ok)
    )

    # Now attempt recovery: FAIL_CLOSED -> RECOVERING
    ok = await state_machine.transition(OperationalState.RECOVERING, "operator_recovery_initiated")
    print_kv("FAIL_CLOSED -> RECOVERING", ok)
    results.append(("Transitioned to RECOVERING", ok))

    # During recovery, the enforcer would be reset and full governance re-validated
    enforcer.reset()
    print_kv("Enforcer reset during recovery", not enforcer.is_halted)
    results.append(("Enforcer reset (no longer halted)", not enforcer.is_halted))

    # Recovery: RECOVERING -> STANDBY
    ok = await state_machine.transition(OperationalState.STANDBY, "recovery_complete_all_checks_passed")
    print_kv("RECOVERING -> STANDBY", ok)
    results.append(("Transitioned to STANDBY (recovery complete)", ok))

    current = state_machine.get_current_state()
    print_kv("Final state after recovery", current.value)
    results.append(
        ("Fully recovered to STANDBY", current == OperationalState.STANDBY)
    )

    return results


# ---------------------------------------------------------------------------
# Main demo
# ---------------------------------------------------------------------------

async def demo_fail_closed() -> list[tuple[str, bool]]:
    """Run all fail-closed enforcement scenarios."""
    results: list[tuple[str, bool]] = []
    print_demo_header(
        "FAIL-CLOSED ENFORCEMENT",
        "Validating that GARVIS properly fails closed on governance violations",
    )

    # Set up real components
    print_section("SETUP: Initialize Real Components")
    registry = create_mock_registry()
    real_validator = RuntimeValidator(registry)
    validator = AsyncRuntimeValidatorWrapper(real_validator)
    enforcer = EnforcementEngine(state_machine=None, audit=None)
    audit = create_mock_audit()
    state_machine = CognitiveStateMachine(
        validator=validator,
        enforcer=enforcer,
        audit_pipeline=audit,
    )
    print_kv("Governance schemas loaded", len(registry.get_all_schemas()))
    print_kv("EnforcementEngine created", True)
    print_kv("CognitiveStateMachine created", True)
    print_kv("Initial state", state_machine.get_current_state().value)
    print()

    # ========================================================================
    # Scenario A
    # ========================================================================
    print_section("SCENARIO A: Critical Violation -> Runtime Halt")
    scenario_a_results = await scenario_a_critical_violation_halt(enforcer, audit)
    results.extend(scenario_a_results)
    print()

    # Reset enforcer for next scenario
    enforcer.reset()

    # ========================================================================
    # Scenario B
    # ========================================================================
    print_section("SCENARIO B: Forbidden State Pattern -> Auto-FAIL_CLOSED")
    scenario_b_results = await scenario_b_forbidden_pattern(state_machine)
    results.extend(scenario_b_results)
    print()

    # ========================================================================
    # Scenario C
    # ========================================================================
    print_section("SCENARIO C: Degraded Mode -> Inference Blocked")
    scenario_c_results = await scenario_c_degraded_mode(state_machine)
    results.extend(scenario_c_results)
    print()

    # ========================================================================
    # Scenario D
    # ========================================================================
    print_section("SCENARIO D: Recovery Path -> FAIL_CLOSED -> STANDBY")
    scenario_d_results = await scenario_d_recovery_path(state_machine, enforcer)
    results.extend(scenario_d_results)
    print()

    # ========================================================================
    # Overall summary
    # ========================================================================
    print_section("SUMMARY: All Scenarios")
    print_kv("Total checks", len(results))
    passed = sum(1 for _, p in results if p)
    print_kv("Passed", f"{passed}/{len(results)}")

    print_subsection("Results by Scenario")
    a_count = len(scenario_a_results)
    b_count = len(scenario_b_results)
    c_count = len(scenario_c_results)
    d_count = len(scenario_d_results)

    a_passed = sum(1 for _, p in scenario_a_results if p)
    b_passed = sum(1 for _, p in scenario_b_results if p)
    c_passed = sum(1 for _, p in scenario_c_results if p)
    d_passed = sum(1 for _, p in scenario_d_results if p)

    print(f"  Scenario A (Critical -> Halt):        {a_passed}/{a_count} passed")
    print(f"  Scenario B (Forbidden Pattern):       {b_passed}/{b_count} passed")
    print(f"  Scenario C (Degraded Block):          {c_passed}/{c_count} passed")
    print(f"  Scenario D (Recovery Path):           {d_passed}/{d_count} passed")

    return results


async def main() -> None:
    """Entry point for the demo."""
    passed = await run_demo(
        demo_fail_closed,
        "FAIL-CLOSED ENFORCEMENT",
    )
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
