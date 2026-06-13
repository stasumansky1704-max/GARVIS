"""
Lineage Tracker

Tracks reasoning lineage across all cognition in GARVIS.
Every inference has a complete ancestry chain.

Per SPEC section 5.8:
- start_trace(session_id) -> trace_id (UUID)
- record_inference(trace_id, request, response, state) -> void
- record_governance_influence(trace_id, check_results) -> void
- record_memory_influence(trace_id, influences) -> void
- get_trace(trace_id) -> CognitionTrace | None
- get_lineage_graph(trace_id) -> dict with nodes and edges

Lineage is immutable — once recorded, never modified.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from database.connection import DatabaseConnection
from database.queries import Queries
from models.audit import AuditEvent, CognitionTrace
from models.cognition import OperationalState, StateTransition
from models.governance import GovernanceCheckResult, GovernanceViolation
from models.inference import GovernedResponse, InferenceRequest
from models.memory import MemoryInfluence

logger = logging.getLogger(__name__)


class LineageTracker:
    """Tracks reasoning lineage across all cognition.

    Every inference has a complete ancestry chain.
    Lineage is immutable — once recorded, never modified.
    All timestamps are UTC.
    """

    def __init__(self, db: DatabaseConnection) -> None:
        self.db = db

    async def start_trace(self, session_id: UUID) -> UUID:
        """Start a new cognition trace.

        Creates a new trace record in the database with:
        - A fresh UUID as trace_id
        - The session_id
        - Current UTC timestamp as start_time
        - Initial state as COGNITION_ACTIVE

        Args:
            session_id: The session to trace.

        Returns:
            The trace_id (UUID) for the new trace.
        """
        trace_id = uuid4()
        start_time = datetime.now(timezone.utc)
        initial_state = OperationalState.COGNITION_ACTIVE

        logger.info(
            "Starting cognition trace: trace_id=%s, session=%s",
            trace_id,
            session_id,
        )

        try:
            await self.db.execute(
                Queries.TRACE_INSERT,
                str(trace_id),
                str(session_id),
                start_time,
                None,  # ended_at
                initial_state.value,
                {},  # metadata
            )
            logger.debug("Trace started: %s", trace_id)
        except Exception as exc:
            logger.critical("Failed to start trace: %s", exc)
            raise

        # Log the trace start as an audit event
        await self._log_trace_event(
            trace_id=trace_id,
            session_id=session_id,
            event_type="lifecycle",
            severity="info",
            component="lineage_tracker",
            details={"action": "trace_started", "initial_state": initial_state.value},
        )

        return trace_id

    async def record_inference(
        self,
        trace_id: UUID,
        request: InferenceRequest,
        response: GovernedResponse,
        state: OperationalState,
    ) -> None:
        """Record an inference in the lineage.

        Creates an audit event for the inference, linking:
        - The request and response
        - The governance state at the time
        - Memory influences on the inference

        Args:
            trace_id: The trace to record under.
            request: The inference request.
            response: The governed response.
            state: The operational state during inference.
        """
        logger.info(
            "Recording inference in lineage: trace=%s, request=%s, state=%s",
            trace_id,
            request.request_id,
            state.value,
        )

        details = {
            "request_id": str(request.request_id),
            "response_id": str(response.response_id),
            "model": request.model,
            "prompt_length": len(request.prompt),
            "response_length": len(response.raw_response),
            "passed_validation": response.passed_validation,
            "memory_context_count": len(request.memory_context),
            "operational_state": state.value,
        }

        severity = "info" if response.passed_validation else "warning"

        await self._log_trace_event(
            trace_id=trace_id,
            session_id=request.session_id,
            event_type="inference",
            severity=severity,
            component="inference_executor",
            details=details,
        )

        logger.debug(
            "Inference recorded in lineage: trace=%s, request=%s",
            trace_id,
            request.request_id,
        )

    async def record_governance_influence(
        self,
        trace_id: UUID,
        check_results: list[GovernanceCheckResult],
    ) -> None:
        """Record governance influence on a trace.

        Persists each governance check result and logs any violations.

        Args:
            trace_id: The trace to record under.
            check_results: List of governance check results.
        """
        if not check_results:
            return

        logger.info(
            "Recording governance influence: trace=%s, checks=%d",
            trace_id,
            len(check_results),
        )

        for check in check_results:
            # Persist the check result
            try:
                await self.db.execute(
                    Queries.CHECK_INSERT,
                    str(check.check_id),
                    check.schema_id,
                    check.policy_id,
                    check.passed,
                    check.violation.model_dump_json() if check.violation else None,
                    None,  # session_id — will be resolved from trace
                    str(trace_id),
                    check.timestamp,
                )
            except Exception as exc:
                logger.error("Failed to persist governance check: %s", exc)
                raise

            # Log failed checks as audit events
            if not check.passed:
                severity = (
                    "critical"
                    if check.violation and check.violation.severity == "critical"
                    else "warning"
                )

                await self._log_trace_event(
                    trace_id=trace_id,
                    session_id=None,
                    event_type="governance_check",
                    severity=severity,
                    component="governance_validator",
                    details={
                        "check_id": str(check.check_id),
                        "schema_id": check.schema_id,
                        "policy_id": check.policy_id,
                        "passed": False,
                        "violation": (
                            check.violation.model_dump(mode="json")
                            if check.violation
                            else None
                        ),
                    },
                )

        logger.debug(
            "Governance influence recorded: trace=%s, %d checks",
            trace_id,
            len(check_results),
        )

    async def record_memory_influence(
        self,
        trace_id: UUID,
        influences: list[MemoryInfluence],
    ) -> None:
        """Record memory influence on a trace.

        Persists each memory influence relationship.

        Args:
            trace_id: The trace to record under.
            influences: List of memory influences.
        """
        if not influences:
            return

        logger.info(
            "Recording memory influence: trace=%s, influences=%d",
            trace_id,
            len(influences),
        )

        for influence in influences:
            # Persist the influence
            try:
                await self.db.execute(
                    Queries.INFLUENCE_INSERT,
                    str(influence.influence_id),
                    str(influence.memory_id),
                    str(influence.target_inference_id),
                    influence.influence_type,
                    influence.strength,
                    influence.trace_visible,
                    influence.timestamp,
                )
            except Exception as exc:
                logger.error("Failed to persist memory influence: %s", exc)
                raise

            # Log as audit event
            await self._log_trace_event(
                trace_id=trace_id,
                session_id=None,
                event_type="retrieval",
                severity="info",
                component="memory_store",
                details={
                    "influence_id": str(influence.influence_id),
                    "memory_id": str(influence.memory_id),
                    "inference_id": str(influence.target_inference_id),
                    "influence_type": influence.influence_type,
                    "strength": influence.strength,
                    "trace_visible": influence.trace_visible,
                },
            )

        logger.debug(
            "Memory influence recorded: trace=%s, %d influences",
            trace_id,
            len(influences),
        )

    async def get_trace(self, trace_id: UUID) -> CognitionTrace | None:
        """Retrieve a complete cognition trace.

        Reconstructs the full trace from database records:
        - Trace metadata
        - State transitions
        - Audit events
        - Memory influences
        - Governance checks

        Args:
            trace_id: The trace to retrieve.

        Returns:
            Complete CognitionTrace, or None if not found.
        """
        logger.debug("Retrieving cognition trace: %s", trace_id)

        # Get trace metadata
        trace_row = await self.db.fetchrow(Queries.TRACE_GET_BY_ID, str(trace_id))
        if trace_row is None:
            logger.debug("Trace not found: %s", trace_id)
            return None

        trace_dict = dict(trace_row)
        session_id = UUID(trace_dict["session_id"])

        # Parse timestamps
        start_time = datetime.fromisoformat(trace_dict["started_at"])
        end_time = (
            datetime.fromisoformat(trace_dict["ended_at"])
            if trace_dict.get("ended_at")
            else None
        )

        # Get state transitions
        state_sequence = await self._get_transitions(trace_id)

        # Get audit events
        events = await self._get_events(trace_id)

        # Get memory influences
        memory_influences = await self._get_memory_influences(session_id)

        # Get governance checks
        governance_checks = await self._get_governance_checks(trace_id)

        # Build final state
        try:
            final_state = OperationalState(trace_dict.get("final_state", "cognition_active"))
        except ValueError:
            final_state = OperationalState.COGNITION_ACTIVE

        trace = CognitionTrace(
            trace_id=trace_id,
            session_id=session_id,
            start_time=start_time,
            end_time=end_time,
            state_sequence=state_sequence,
            events=events,
            memory_influences=memory_influences,
            governance_checks=governance_checks,
            final_state=final_state,
        )

        logger.debug(
            "Cognition trace retrieved: %s, %d events, %d transitions, "
            "%d influences, %d checks",
            trace_id,
            len(events),
            len(state_sequence),
            len(memory_influences),
            len(governance_checks),
        )
        return trace

    async def get_lineage_graph(self, trace_id: UUID) -> dict:
        """Get a graph representation of the reasoning lineage.

        Returns a dict with:
        - nodes: inferences, memories, governance checks, state transitions
        - edges: influence relationships, causation

        Args:
            trace_id: The trace to build the graph for.

        Returns:
            Dict with 'nodes' and 'edges' keys.
        """
        logger.debug("Building lineage graph for trace: %s", trace_id)

        trace = await self.get_trace(trace_id)
        if trace is None:
            return {"nodes": {}, "edges": [], "trace_id": str(trace_id)}

        nodes: dict[str, dict] = {}
        edges: list[dict] = []

        # Add trace node
        trace_node = f"trace:{trace_id}"
        nodes[trace_node] = {
            "type": "trace",
            "id": str(trace_id),
            "session_id": str(trace.session_id),
            "start_time": trace.start_time.isoformat(),
            "final_state": trace.final_state.value,
        }

        # Add state transition nodes
        for transition in trace.state_sequence:
            node_id = f"transition:{transition.transition_id}"
            nodes[node_id] = {
                "type": "state_transition",
                "id": str(transition.transition_id),
                "from_state": transition.from_state.value,
                "to_state": transition.to_state.value,
                "trigger": transition.trigger,
                "timestamp": transition.timestamp.isoformat(),
            }
            edges.append({
                "from": trace_node,
                "to": node_id,
                "type": "contains",
            })

        # Add audit event nodes
        for event in trace.events:
            node_id = f"event:{event.event_id}"
            nodes[node_id] = {
                "type": "audit_event",
                "id": str(event.event_id),
                "event_type": event.event_type,
                "severity": event.severity,
                "component": event.component,
                "timestamp": event.timestamp.isoformat(),
            }
            edges.append({
                "from": trace_node,
                "to": node_id,
                "type": "contains",
            })

        # Add memory influence nodes and edges
        for influence in trace.memory_influences:
            influence_node = f"influence:{influence.influence_id}"
            memory_node = f"memory:{influence.memory_id}"
            inference_node = f"inference:{influence.target_inference_id}"

            if influence_node not in nodes:
                nodes[influence_node] = {
                    "type": "influence",
                    "id": str(influence.influence_id),
                    "influence_type": influence.influence_type,
                    "strength": influence.strength,
                    "trace_visible": influence.trace_visible,
                }

            if memory_node not in nodes:
                nodes[memory_node] = {
                    "type": "memory",
                    "id": str(influence.memory_id),
                }

            if inference_node not in nodes:
                nodes[inference_node] = {
                    "type": "inference",
                    "id": str(influence.target_inference_id),
                }

            edges.append({
                "from": memory_node,
                "to": influence_node,
                "type": "influences",
            })
            edges.append({
                "from": influence_node,
                "to": inference_node,
                "type": "affects",
            })

        # Add governance check nodes
        for check in trace.governance_checks:
            node_id = f"check:{check.check_id}"
            nodes[node_id] = {
                "type": "governance_check",
                "id": str(check.check_id),
                "schema_id": check.schema_id,
                "policy_id": check.policy_id,
                "passed": check.passed,
                "timestamp": check.timestamp.isoformat(),
            }
            edges.append({
                "from": trace_node,
                "to": node_id,
                "type": "governed_by",
            })

        graph = {
            "trace_id": str(trace_id),
            "session_id": str(trace.session_id),
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": nodes,
            "edges": edges,
        }

        logger.debug(
            "Lineage graph built: %d nodes, %d edges",
            len(nodes),
            len(edges),
        )
        return graph

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _log_trace_event(
        self,
        trace_id: UUID,
        session_id: UUID | None,
        event_type: str,
        severity: str,
        component: str,
        details: dict,
    ) -> None:
        """Log an audit event for a trace."""
        event = AuditEvent(
            event_id=uuid4(),
            event_type=event_type,
            severity=severity,
            component=component,
            session_id=session_id,
            trace_id=trace_id,
            details=details,
        )

        try:
            await self.db.execute(
                Queries.AUDIT_INSERT,
                str(event.event_id),
                event.event_type,
                event.severity,
                event.component,
                str(event.session_id) if event.session_id else None,
                str(event.trace_id),
                event.timestamp,
                event.details,
                event.governance_context,
            )
        except Exception as exc:
            logger.error("Failed to log trace event: %s", exc)
            raise

    async def _get_transitions(
        self,
        trace_id: UUID,
    ) -> list[StateTransition]:
        """Get state transitions for a trace."""
        try:
            rows = await self.db.fetch(
                Queries.TRANSITION_GET_BY_TRACE, str(trace_id)
            )
        except Exception as exc:
            logger.error("Failed to get transitions for trace %s: %s", trace_id, exc)
            return []

        transitions = []
        for row in rows:
            row_dict = dict(row)
            transitions.append(
                StateTransition(
                    transition_id=UUID(row_dict["transition_id"]),
                    from_state=OperationalState(row_dict["from_state"]),
                    to_state=OperationalState(row_dict["to_state"]),
                    trigger=row_dict["trigger_description"],
                    governance_check=row_dict["governance_check_passed"],
                    timestamp=datetime.fromisoformat(row_dict["created_at"]),
                    trace_id=trace_id,
                )
            )
        return transitions

    async def _get_events(
        self,
        trace_id: UUID,
    ) -> list[AuditEvent]:
        """Get audit events for a trace."""
        try:
            rows = await self.db.fetch(
                Queries.AUDIT_GET_BY_TRACE, str(trace_id)
            )
        except Exception as exc:
            logger.error("Failed to get events for trace %s: %s", trace_id, exc)
            return []

        events = []
        for row in rows:
            row_dict = dict(row)
            events.append(AuditEvent.from_db_row(row_dict))
        return events

    async def _get_memory_influences(
        self,
        session_id: UUID,
    ) -> list[MemoryInfluence]:
        """Get memory influences for a session."""
        try:
            rows = await self.db.fetch(
                Queries.INFLUENCE_GET_BY_SESSION, str(session_id)
            )
        except Exception as exc:
            logger.error(
                "Failed to get memory influences for session %s: %s",
                session_id,
                exc,
            )
            return []

        influences = []
        for row in rows:
            row_dict = dict(row)
            influences.append(MemoryInfluence.from_db_row(row_dict))
        return influences

    async def _get_governance_checks(
        self,
        trace_id: UUID,
    ) -> list[GovernanceCheckResult]:
        """Get governance check results for a trace."""
        try:
            rows = await self.db.fetch(
                Queries.CHECK_GET_BY_TRACE, str(trace_id)
            )
        except Exception as exc:
            logger.error(
                "Failed to get governance checks for trace %s: %s",
                trace_id,
                exc,
            )
            return []

        checks = []
        for row in rows:
            row_dict = dict(row)
            violation = None
            if row_dict.get("violation"):
                import json
                violation_data = row_dict["violation"]
                if isinstance(violation_data, str):
                    violation_data = json.loads(violation_data)
                # Parse timestamp string to datetime if needed
                if isinstance(violation_data.get("timestamp"), str):
                    violation_data["timestamp"] = datetime.fromisoformat(
                        violation_data["timestamp"]
                    )
                violation = GovernanceViolation(**violation_data)

            checks.append(
                GovernanceCheckResult(
                    check_id=UUID(row_dict["check_id"]),
                    schema_id=row_dict["schema_id"],
                    policy_id=row_dict["policy_id"],
                    passed=row_dict["passed"],
                    violation=violation,
                    timestamp=datetime.fromisoformat(row_dict["created_at"]),
                )
            )
        return checks
