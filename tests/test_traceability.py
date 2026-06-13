"""Tests for the traceability layer.

Tests cover lineage tracking, audit pipeline, trace graph building,
event buffering, flushing, and violation summaries.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from traceability.audit import AuditPipeline
from traceability.lineage import LineageTracker
from traceability.trace_graph import TraceGraphBuilder
from models.audit import AuditEvent, CognitionTrace
from models.cognition import OperationalState, StateTransition
from models.governance import GovernanceCheckResult, GovernanceViolation
from models.inference import InferenceRequest, GovernedResponse
from models.memory import MemoryInfluence


# ============================================================================
# LineageTracker
# ============================================================================

class TestLineageTracker:
    """Tests for LineageTracker."""

    @pytest.fixture
    def lineage(self, mock_db: MagicMock) -> LineageTracker:
        """Return a LineageTracker with a mock DB."""
        return LineageTracker(mock_db)

    @pytest.fixture
    def sample_request(self) -> InferenceRequest:
        """Return a sample InferenceRequest."""
        return InferenceRequest(
            request_id=uuid4(),
            session_id=uuid4(),
            prompt="What is the capital of France?",
            model="llama3.1",
            governance_context=["uncertainty_management"],
        )

    @pytest.fixture
    def sample_response(self, sample_request: InferenceRequest) -> GovernedResponse:
        """Return a sample GovernedResponse."""
        return GovernedResponse(
            response_id=uuid4(),
            request_id=sample_request.request_id,
            raw_response="Paris is the capital of France. Confidence: 0.95",
            validated_response="Paris is the capital of France. Confidence: 0.95",
            passed_validation=True,
        )

    @pytest.mark.asyncio
    async def test_start_trace(self, lineage: LineageTracker, mock_db: MagicMock) -> None:
        """start_trace() creates a trace with UUID via db.execute."""
        session_id = uuid4()
        trace_id = await lineage.start_trace(session_id)
        assert isinstance(trace_id, UUID)
        # start_trace uses db.execute with TRACE_INSERT
        assert mock_db.execute.call_count >= 1

    @pytest.mark.asyncio
    async def test_record_inference(
        self,
        lineage: LineageTracker,
        sample_request: InferenceRequest,
        sample_response: GovernedResponse,
        mock_db: MagicMock,
    ) -> None:
        """record_inference() records an inference in the trace."""
        trace_id = uuid4()

        await lineage.record_inference(
            trace_id=trace_id,
            request=sample_request,
            response=sample_response,
            state=OperationalState.INFERENCE_EXECUTING,
        )

        mock_db.execute.assert_called()

    @pytest.mark.asyncio
    async def test_record_governance_influence(
        self, lineage: LineageTracker, mock_db: MagicMock
    ) -> None:
        """record_governance_influence() records governance checks."""
        trace_id = uuid4()
        check = GovernanceCheckResult(
            schema_id="uncertainty_management",
            policy_id="confidence_required",
            passed=True,
        )

        await lineage.record_governance_influence(trace_id, [check])

        mock_db.execute.assert_called()

    @pytest.mark.asyncio
    async def test_record_governance_influence_empty(
        self, lineage: LineageTracker, mock_db: MagicMock
    ) -> None:
        """record_governance_influence() handles empty check list gracefully."""
        trace_id = uuid4()

        await lineage.record_governance_influence(trace_id, [])

        # Should not call DB when list is empty
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_record_memory_influence(
        self, lineage: LineageTracker, mock_db: MagicMock
    ) -> None:
        """record_memory_influence() records memory influences."""
        trace_id = uuid4()
        influence = MemoryInfluence(
            memory_id=uuid4(),
            target_inference_id=uuid4(),
            influence_type="retrieval",
            strength=0.8,
        )

        await lineage.record_memory_influence(trace_id, [influence])

        mock_db.execute.assert_called()

    @pytest.mark.asyncio
    async def test_record_memory_influence_empty(
        self, lineage: LineageTracker, mock_db: MagicMock
    ) -> None:
        """record_memory_influence() handles empty influence list gracefully."""
        trace_id = uuid4()

        await lineage.record_memory_influence(trace_id, [])

        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_trace(self, lineage: LineageTracker, mock_db: MagicMock) -> None:
        """get_trace() reconstructs a complete trace."""
        trace_id = uuid4()
        session_id = uuid4()

        mock_db.fetchrow.return_value = {
            "trace_id": str(trace_id),
            "session_id": str(session_id),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "ended_at": None,
            "final_state": "cognition_active",
        }
        mock_db.fetch.return_value = []

        trace = await lineage.get_trace(trace_id)

        assert trace is not None
        assert isinstance(trace, CognitionTrace)
        assert trace.trace_id == trace_id
        assert trace.session_id == session_id

    @pytest.mark.asyncio
    async def test_get_trace_not_found(self, lineage: LineageTracker, mock_db: MagicMock) -> None:
        """get_trace() returns None for non-existent trace."""
        mock_db.fetchrow.return_value = None

        trace = await lineage.get_trace(uuid4())

        assert trace is None

    @pytest.mark.asyncio
    async def test_get_lineage_graph(self, lineage: LineageTracker, mock_db: MagicMock) -> None:
        """get_lineage_graph() returns nodes and edges."""
        trace_id = uuid4()
        session_id = uuid4()

        mock_db.fetchrow.return_value = {
            "trace_id": str(trace_id),
            "session_id": str(session_id),
            "started_at": datetime.now(timezone.utc).isoformat(),
            "ended_at": None,
            "final_state": "cognition_active",
        }
        mock_db.fetch.return_value = []

        graph = await lineage.get_lineage_graph(trace_id)

        assert "nodes" in graph
        assert "edges" in graph
        assert graph["trace_id"] == str(trace_id)

    @pytest.mark.asyncio
    async def test_get_lineage_graph_not_found(
        self, lineage: LineageTracker, mock_db: MagicMock
    ) -> None:
        """get_lineage_graph() returns empty graph for non-existent trace."""
        trace_id = uuid4()
        mock_db.fetchrow.return_value = None

        graph = await lineage.get_lineage_graph(trace_id)

        assert graph["nodes"] == {}
        assert graph["edges"] == []


# ============================================================================
# AuditPipeline
# ============================================================================

class TestAuditPipeline:
    """Tests for AuditPipeline."""

    @pytest.fixture
    def audit(self, mock_db: MagicMock) -> AuditPipeline:
        """Return an AuditPipeline with a mock DB."""
        return AuditPipeline(mock_db, buffer_size=3, flush_interval=60.0)

    @pytest.mark.asyncio
    async def test_audit_event_buffering(self, audit: AuditPipeline, mock_db: MagicMock) -> None:
        """Events are buffered and not immediately written."""
        event = AuditEvent(
            event_type="test",
            severity="info",
            component="test",
        )

        await audit.log_event(event)

        # Event should be buffered, not immediately written
        mock_db.executemany.assert_not_called()

    @pytest.mark.asyncio
    async def test_audit_flush(self, audit: AuditPipeline, mock_db: MagicMock) -> None:
        """flush() writes buffered events to storage."""
        event = AuditEvent(
            event_type="test",
            severity="info",
            component="test",
        )

        await audit.log_event(event)
        await audit.flush()

        mock_db.executemany.assert_called_once()

    @pytest.mark.asyncio
    async def test_audit_auto_flush_on_buffer_full(
        self, audit: AuditPipeline, mock_db: MagicMock
    ) -> None:
        """Buffer auto-flushes when it reaches buffer_size."""
        for i in range(4):  # buffer_size is 3
            event = AuditEvent(
                event_type="test",
                severity="info",
                component=f"test_{i}",
            )
            await audit.log_event(event)

        # At least one flush should have happened
        assert mock_db.executemany.call_count >= 1

    @pytest.mark.asyncio
    async def test_log_state_transition(self, audit: AuditPipeline, mock_db: MagicMock) -> None:
        """log_state_transition() creates an audit event for transitions."""
        transition = StateTransition(
            transition_id=uuid4(),
            from_state=OperationalState.STANDBY,
            to_state=OperationalState.GOVERNANCE_CHECK,
            trigger="test",
            governance_check=True,
            timestamp=datetime.now(timezone.utc),
            trace_id=uuid4(),
        )

        await audit.log_state_transition(transition)

        mock_db.execute.assert_called()

    @pytest.mark.asyncio
    async def test_log_governance_violation(
        self, audit: AuditPipeline, mock_db: MagicMock
    ) -> None:
        """log_governance_violation() logs a violation event."""
        violation = GovernanceViolation(
            schema_id="test_schema",
            policy_id="test_policy",
            severity="critical",
            description="Test violation",
        )

        await audit.log_governance_violation(violation)

        mock_db.execute.assert_called()

    @pytest.mark.asyncio
    async def test_log_inference(
        self,
        audit: AuditPipeline,
        mock_db: MagicMock,
    ) -> None:
        """log_inference() logs an inference event."""
        request = InferenceRequest(
            request_id=uuid4(),
            session_id=uuid4(),
            prompt="Hello?",
            model="llama3.1",
            governance_context=[],
        )
        response = GovernedResponse(
            request_id=request.request_id,
            raw_response="Hello!",
            passed_validation=True,
        )

        await audit.log_inference(request, response)

        # Event buffered, not immediately written
        mock_db.executemany.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_events(self, audit: AuditPipeline, mock_db: MagicMock) -> None:
        """get_events() queries audit events with filters."""
        mock_db.fetch.return_value = []

        events = await audit.get_events(
            session_id=uuid4(),
            event_type="inference",
            severity="info",
        )

        assert isinstance(events, list)
        mock_db.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_violation_summary(self, audit: AuditPipeline, mock_db: MagicMock) -> None:
        """get_violation_summary() returns aggregated violations."""
        mock_db.fetch.return_value = []

        summary = await audit.get_violation_summary()

        assert "by_severity" in summary
        assert "by_schema" in summary
        assert "total" in summary

    @pytest.mark.asyncio
    async def test_start_stop(self, audit: AuditPipeline) -> None:
        """start() and stop() manage the periodic flush task."""
        await audit.start()
        assert audit._flush_task is not None

        await audit.stop()
        assert audit._shutting_down is True

    @pytest.mark.asyncio
    async def test_flush_empty_buffer(self, audit: AuditPipeline, mock_db: MagicMock) -> None:
        """flush() with empty buffer does nothing."""
        await audit.flush()
        mock_db.executemany.assert_not_called()

    @pytest.mark.asyncio
    async def test_violation_summary_with_data(self, audit: AuditPipeline, mock_db: MagicMock) -> None:
        """get_violation_summary() aggregates data correctly."""
        mock_db.fetch.return_value = [
            {"severity": "critical", "schema_id": "schema_a", "count": 3},
            {"severity": "warning", "schema_id": "schema_b", "count": 2},
        ]

        summary = await audit.get_violation_summary()

        assert summary["total"] == 5
        assert summary["by_severity"]["critical"] == 3
        assert summary["by_severity"]["warning"] == 2


# ============================================================================
# TraceGraphBuilder
# ============================================================================

class TestTraceGraphBuilder:
    """Tests for TraceGraphBuilder."""

    @pytest.fixture
    def builder(self) -> TraceGraphBuilder:
        """Return a TraceGraphBuilder (no DB needed for basic tests)."""
        return TraceGraphBuilder(db=None)

    @pytest.mark.asyncio
    async def test_build_graph_no_db(self, builder: TraceGraphBuilder) -> None:
        """build_graph() returns empty graph without DB connection."""
        trace_id = uuid4()

        graph = await builder.build_graph(trace_id)

        assert graph["node_count"] == 0
        assert graph["edge_count"] == 0
        assert graph["nodes"] == {}
        assert graph["edges"] == []

    def test_add_node(self, builder: TraceGraphBuilder) -> None:
        """add_node() adds a node to an existing graph."""
        trace_id = uuid4()

        # Need to build first to create the entry
        # Since build_graph is async, we'll test manually
        builder._graphs[trace_id] = {
            "trace_id": str(trace_id),
            "node_count": 0,
            "edge_count": 0,
            "nodes": {},
            "edges": [],
        }

        builder.add_node(
            trace_id=trace_id,
            node_id="test_node",
            node_type="test",
            data={"value": 42},
            label="Test Node",
        )

        assert builder._graphs[trace_id]["node_count"] == 1
        assert "test_node" in builder._graphs[trace_id]["nodes"]

    def test_add_edge(self, builder: TraceGraphBuilder) -> None:
        """add_edge() adds an edge to an existing graph."""
        trace_id = uuid4()

        builder._graphs[trace_id] = {
            "trace_id": str(trace_id),
            "node_count": 0,
            "edge_count": 0,
            "nodes": {},
            "edges": [],
        }

        builder.add_edge(
            trace_id=trace_id,
            from_id="node_a",
            to_id="node_b",
            edge_type="test",
            weight=0.5,
        )

        assert builder._graphs[trace_id]["edge_count"] == 1
        assert len(builder._graphs[trace_id]["edges"]) == 1

    def test_add_node_no_graph(self, builder: TraceGraphBuilder) -> None:
        """add_node() handles missing graph gracefully."""
        builder.add_node(
            trace_id=uuid4(),
            node_id="test",
            node_type="test",
            data={},
        )
        # Should not raise

    def test_add_edge_no_graph(self, builder: TraceGraphBuilder) -> None:
        """add_edge() handles missing graph gracefully."""
        builder.add_edge(
            trace_id=uuid4(),
            from_id="a",
            to_id="b",
            edge_type="test",
        )
        # Should not raise

    def test_get_critical_path_no_graph(self, builder: TraceGraphBuilder) -> None:
        """get_critical_path() returns empty list when graph not built."""
        result = builder.get_critical_path(uuid4())
        assert result == []

    def test_get_governance_hotspots_no_graph(self, builder: TraceGraphBuilder) -> None:
        """get_governance_hotspots() returns empty result when graph not built."""
        result = builder.get_governance_hotspots(uuid4())
        assert result["total_checks"] == 0
        assert result["failed_checks"] == 0

    def test_export_graph_no_graph(self, builder: TraceGraphBuilder) -> None:
        """export_graph() returns error dict when graph not built."""
        result = builder.export_graph(uuid4())
        assert "error" in result

    def test_invalidate_cache(self, builder: TraceGraphBuilder) -> None:
        """invalidate_cache() clears the graph cache."""
        trace_id = uuid4()
        builder._graphs[trace_id] = {"test": "data"}

        builder.invalidate_cache(trace_id)
        assert trace_id not in builder._graphs

    def test_invalidate_cache_all(self, builder: TraceGraphBuilder) -> None:
        """invalidate_cache() with None clears all caches."""
        builder._graphs[uuid4()] = {"test": "data"}
        builder._graphs[uuid4()] = {"test": "data2"}

        builder.invalidate_cache(None)
        assert len(builder._graphs) == 0

    def test_count_node_types(self, builder: TraceGraphBuilder) -> None:
        """_count_node_types correctly aggregates node types."""
        graph = {
            "nodes": {
                "n1": {"type": "memory"},
                "n2": {"type": "memory"},
                "n3": {"type": "inference"},
            }
        }
        result = builder._count_node_types(graph)
        assert result["memory"] == 2
        assert result["inference"] == 1

    def test_count_edge_types(self, builder: TraceGraphBuilder) -> None:
        """_count_edge_types correctly aggregates edge types."""
        graph = {
            "edges": [
                {"type": "influences"},
                {"type": "affects"},
                {"type": "influences"},
            ]
        }
        result = builder._count_edge_types(graph)
        assert result["influences"] == 2
        assert result["affects"] == 1
