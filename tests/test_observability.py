"""
Tests for GARVIS observability layer.

Covers:
- TraceRenderer: text, DOT, Mermaid, JSON rendering
- AuditStreamViewer: event display, filtering, colour formatting
- TraceExporter: all format exports, bulk export
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from traceability.renderer import TraceRenderer
from traceability.stream_viewer import AuditStreamViewer, display_events
from traceability.trace_exporter import TraceExporter


# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_trace_data() -> dict:
    """Build a realistic trace dict for testing."""
    trace_id = uuid4()
    session_id = uuid4()
    return {
        "trace_id": trace_id,
        "session_id": session_id,
        "start_time": datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        "end_time": datetime(2024, 1, 15, 10, 30, 2, 350000, tzinfo=timezone.utc),
        "status": "failed",
        "final_state": "fail_closed",
        "duration_ms": 2350,
        "original_prompt": "What is the capital of France?",
        "mediated_prompt": "What is the capital of France?\nAcknowledge uncertainty where present.",
        "mediation_schemas": ["uncertainty_management", "truthfulness_governance"],
        "response_status": "blocked",
        "blocking_violation": "boundary_preservation::within_operational_scope",
        "response": None,
        "state_sequence": [
            {
                "transition_id": uuid4(),
                "from_state": "uninitialized",
                "to_state": "standby",
                "trigger": "bootstrap",
                "governance_check": True,
                "timestamp": datetime(2024, 1, 15, 10, 30, 0, 100000, tzinfo=timezone.utc),
                "trace_id": trace_id,
            },
            {
                "transition_id": uuid4(),
                "from_state": "standby",
                "to_state": "governance_check",
                "trigger": "prompt_received",
                "governance_check": False,
                "timestamp": datetime(2024, 1, 15, 10, 30, 0, 200000, tzinfo=timezone.utc),
                "trace_id": trace_id,
            },
            {
                "transition_id": uuid4(),
                "from_state": "inference_executing",
                "to_state": "fail_closed",
                "trigger": "governance_violation_critical",
                "governance_check": True,
                "timestamp": datetime(2024, 1, 15, 10, 30, 2, 300000, tzinfo=timezone.utc),
                "trace_id": trace_id,
            },
        ],
        "governance_checks": [
            {
                "check_id": uuid4(),
                "schema_id": "uncertainty_management",
                "policy_id": "uncertainty_quantification_required",
                "passed": True,
                "violation": None,
                "timestamp": datetime(2024, 1, 15, 10, 30, 0, 300000, tzinfo=timezone.utc),
            },
            {
                "check_id": uuid4(),
                "schema_id": "boundary_preservation",
                "policy_id": "within_operational_scope",
                "passed": False,
                "violation": {
                    "violation_id": str(uuid4()),
                    "schema_id": "boundary_preservation",
                    "policy_id": "within_operational_scope",
                    "severity": "critical",
                    "description": "Scope exceeded",
                    "context": {},
                    "timestamp": datetime(2024, 1, 15, 10, 30, 2, 250000, tzinfo=timezone.utc).isoformat(),
                    "resolution": None,
                },
                "timestamp": datetime(2024, 1, 15, 10, 30, 2, 250000, tzinfo=timezone.utc),
            },
        ],
        "memory_influences": [
            {
                "influence_id": uuid4(),
                "memory_id": uuid4(),
                "target_inference_id": uuid4(),
                "influence_type": "retrieval",
                "strength": 0.85,
                "trace_visible": True,
                "timestamp": datetime(2024, 1, 15, 10, 30, 1, 0, tzinfo=timezone.utc),
                "content": "Paris is the capital of France",
                "provenance": {"source_schema": "uncertainty_management"},
            },
        ],
        "events": [
            {
                "event_id": uuid4(),
                "event_type": "state_transition",
                "severity": "info",
                "component": "state_machine",
                "session_id": session_id,
                "trace_id": trace_id,
                "timestamp": datetime(2024, 1, 15, 10, 30, 0, 100000, tzinfo=timezone.utc),
                "details": {"from_state": "standby", "to_state": "governance_check"},
                "governance_context": ["uncertainty_management"],
            },
            {
                "event_id": uuid4(),
                "event_type": "governance_violation",
                "severity": "critical",
                "component": "governance_validator",
                "session_id": session_id,
                "trace_id": trace_id,
                "timestamp": datetime(2024, 1, 15, 10, 30, 2, 250000, tzinfo=timezone.utc),
                "details": {
                    "schema_id": "boundary_preservation",
                    "policy_id": "within_operational_scope",
                    "severity": "critical",
                    "description": "Operational scope exceeded",
                },
                "governance_context": ["boundary_preservation"],
            },
            {
                "event_id": uuid4(),
                "event_type": "inference",
                "severity": "warning",
                "component": "inference_executor",
                "session_id": session_id,
                "trace_id": trace_id,
                "timestamp": datetime(2024, 1, 15, 10, 30, 1, 500000, tzinfo=timezone.utc),
                "details": {
                    "model": "llama3.1",
                    "prompt_length": 42,
                    "response_length": 0,
                    "passed_validation": False,
                    "governance_checks_count": 3,
                    "memory_influences_count": 2,
                },
                "governance_context": ["boundary_preservation", "truthfulness_governance"],
            },
        ],
    }


@pytest.fixture
def sample_events() -> list[dict]:
    """Simple event dicts for stream-viewer testing."""
    sid = uuid4()
    tid = uuid4()
    return [
        {
            "event_id": uuid4(),
            "event_type": "state_transition",
            "severity": "info",
            "component": "state_machine",
            "session_id": sid,
            "trace_id": tid,
            "timestamp": datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            "details": {"from_state": "standby", "to_state": "cognition_active"},
            "governance_context": [],
        },
        {
            "event_id": uuid4(),
            "event_type": "governance_check",
            "severity": "critical",
            "component": "governance_validator",
            "session_id": sid,
            "trace_id": tid,
            "timestamp": datetime(2024, 1, 15, 10, 30, 1, tzinfo=timezone.utc),
            "details": {"schema_id": "x", "policy_id": "y", "passed": False},
            "governance_context": [],
        },
        {
            "event_id": uuid4(),
            "event_type": "inference",
            "severity": "warning",
            "component": "inference_executor",
            "session_id": sid,
            "trace_id": tid,
            "timestamp": datetime(2024, 1, 15, 10, 30, 2, tzinfo=timezone.utc),
            "details": {"model": "llama3.1", "prompt_length": 10},
            "governance_context": [],
        },
    ]


# ---------------------------------------------------------------------------
# TraceRenderer tests
# ---------------------------------------------------------------------------


class TestTraceRenderer:
    """Tests for TraceRenderer text, DOT, Mermaid, and JSON output."""

    # -- text --

    def test_render_text_header_contains_trace_id(self, sample_trace_data: dict) -> None:
        renderer = TraceRenderer()
        renderer.disable_color()
        out = renderer.render_text(sample_trace_data)
        tid = str(sample_trace_data["trace_id"])
        assert "GARVIS COGNITION TRACE" in out
        assert tid in out

    def test_render_text_shows_state_transitions(self, sample_trace_data: dict) -> None:
        renderer = TraceRenderer()
        renderer.disable_color()
        out = renderer.render_text(sample_trace_data)
        assert "STATE TRANSITIONS" in out
        assert "uninitialized" in out
        assert "fail_closed" in out
        assert "bootstrap" in out

    def test_render_text_shows_governance_checks(self, sample_trace_data: dict) -> None:
        renderer = TraceRenderer()
        renderer.disable_color()
        out = renderer.render_text(sample_trace_data)
        assert "GOVERNANCE CHECKS" in out
        assert "uncertainty_management" in out
        assert "boundary_preservation" in out
        assert "within_operational_scope" in out

    def test_render_text_shows_memory_influences(self, sample_trace_data: dict) -> None:
        renderer = TraceRenderer()
        renderer.disable_color()
        out = renderer.render_text(sample_trace_data)
        assert "MEMORY INFLUENCES" in out
        assert "retrieval" in out
        assert "0.85" in out

    def test_render_text_shows_audit_events(self, sample_trace_data: dict) -> None:
        renderer = TraceRenderer()
        renderer.disable_color()
        out = renderer.render_text(sample_trace_data)
        assert "AUDIT EVENTS" in out
        assert "state_transition" in out
        assert "governance_violation" in out

    def test_render_text_shows_prompt_mediation(self, sample_trace_data: dict) -> None:
        renderer = TraceRenderer()
        renderer.disable_color()
        out = renderer.render_text(sample_trace_data)
        assert "PROMPT MEDIATION" in out
        assert "What is the capital of France?" in out

    def test_render_text_shows_summary(self, sample_trace_data: dict) -> None:
        renderer = TraceRenderer()
        renderer.disable_color()
        out = renderer.render_text(sample_trace_data)
        assert "SUMMARY" in out
        assert "State transitions: 3" in out
        assert "Governance checks: 2" in out or "Governance checks:" in out

    def test_render_text_ansi_color_enabled(self, sample_trace_data: dict) -> None:
        renderer = TraceRenderer()
        renderer.enable_color()
        out = renderer.render_text(sample_trace_data)
        assert "\033[" in out  # ANSI escape codes present

    def test_render_text_ansi_color_disabled(self, sample_trace_data: dict) -> None:
        renderer = TraceRenderer()
        renderer.disable_color()
        out = renderer.render_text(sample_trace_data)
        assert "\033[" not in out  # No ANSI escape codes

    def test_render_text_empty_trace(self) -> None:
        renderer = TraceRenderer()
        renderer.disable_color()
        out = renderer.render_text({"trace_id": uuid4(), "session_id": uuid4()})
        assert "GARVIS COGNITION TRACE" in out
        assert "(no state transitions recorded)" in out
        assert "(no governance checks recorded)" in out

    # -- DOT --

    def test_render_dot_valid_structure(self, sample_trace_data: dict) -> None:
        renderer = TraceRenderer()
        renderer.disable_color()
        out = renderer.render_dot(sample_trace_data)
        assert "digraph garvis_trace {" in out
        assert "}" in out

    def test_render_dot_contains_nodes(self, sample_trace_data: dict) -> None:
        renderer = TraceRenderer()
        out = renderer.render_dot(sample_trace_data)
        assert "trace_root" in out
        assert "trans_0" in out
        assert "check_0" in out

    def test_render_dot_contains_edges(self, sample_trace_data: dict) -> None:
        renderer = TraceRenderer()
        out = renderer.render_dot(sample_trace_data)
        assert "->" in out
        assert "trace_root" in out

    def test_render_dot_color_coding(self, sample_trace_data: dict) -> None:
        renderer = TraceRenderer()
        out = renderer.render_dot(sample_trace_data)
        # Check node has fill colors
        assert "fillcolor" in out
        # Green for pass, red for fail
        assert "#69db7c" in out  # green
        assert "#ff6b6b" in out  # red

    def test_render_dot_has_legend(self, sample_trace_data: dict) -> None:
        renderer = TraceRenderer()
        out = renderer.render_dot(sample_trace_data)
        assert "cluster_legend" in out
        assert "Legend" in out

    # -- Mermaid --

    def test_render_mermaid_valid_structure(self, sample_trace_data: dict) -> None:
        renderer = TraceRenderer()
        out = renderer.render_mermaid(sample_trace_data)
        assert "flowchart TD" in out

    def test_render_mermaid_contains_subgraphs(self, sample_trace_data: dict) -> None:
        renderer = TraceRenderer()
        out = renderer.render_mermaid(sample_trace_data)
        assert "subgraph GOV" in out
        assert "subgraph STM" in out
        assert "subgraph MEM" in out

    def test_render_mermaid_contains_nodes(self, sample_trace_data: dict) -> None:
        renderer = TraceRenderer()
        out = renderer.render_mermaid(sample_trace_data)
        assert "root" in out
        assert "GC0" in out

    def test_render_mermaid_contains_edges(self, sample_trace_data: dict) -> None:
        renderer = TraceRenderer()
        out = renderer.render_mermaid(sample_trace_data)
        assert "-->" in out or "-.->" in out

    def test_render_mermaid_class_defs(self, sample_trace_data: dict) -> None:
        renderer = TraceRenderer()
        out = renderer.render_mermaid(sample_trace_data)
        assert "classDef" in out

    # -- JSON --

    def test_render_json_valid(self, sample_trace_data: dict) -> None:
        renderer = TraceRenderer()
        out = renderer.render_json(sample_trace_data)
        parsed = json.loads(out)
        assert isinstance(parsed, dict)
        assert "trace_id" in parsed
        assert "state_sequence" in parsed

    def test_render_json_uuid_as_string(self, sample_trace_data: dict) -> None:
        renderer = TraceRenderer()
        out = renderer.render_json(sample_trace_data)
        parsed = json.loads(out)
        assert isinstance(parsed["trace_id"], str)
        assert isinstance(parsed["session_id"], str)

    def test_render_json_datetime_as_iso(self, sample_trace_data: dict) -> None:
        renderer = TraceRenderer()
        out = renderer.render_json(sample_trace_data)
        parsed = json.loads(out)
        assert isinstance(parsed["start_time"], str)
        assert "T" in parsed["start_time"]  # ISO format

    def test_render_json_pretty_printed(self, sample_trace_data: dict) -> None:
        renderer = TraceRenderer()
        out = renderer.render_json(sample_trace_data)
        assert "\n" in out  # Multi-line (pretty-printed)
        assert "  " in out  # Indented

    # -- Status derivation --

    def test_derive_status_from_failed_checks(self) -> None:
        renderer = TraceRenderer()
        data = {
            "trace_id": uuid4(),
            "session_id": uuid4(),
            "governance_checks": [
                {"passed": False, "violation": {"severity": "critical"}}
            ],
        }
        assert renderer._derive_status(data) == "failed"

    def test_derive_status_from_warning_checks(self) -> None:
        renderer = TraceRenderer()
        data = {
            "trace_id": uuid4(),
            "session_id": uuid4(),
            "governance_checks": [
                {"passed": False, "violation": {"severity": "warning"}}
            ],
        }
        assert renderer._derive_status(data) == "warning"

    def test_derive_status_success(self) -> None:
        renderer = TraceRenderer()
        data = {
            "trace_id": uuid4(),
            "session_id": uuid4(),
            "governance_checks": [{"passed": True}],
            "events": [],
        }
        assert renderer._derive_status(data) == "success"


# ---------------------------------------------------------------------------
# AuditStreamViewer tests
# ---------------------------------------------------------------------------


class TestAuditStreamViewer:
    """Tests for AuditStreamViewer event display and filtering."""

    def test_init_no_pipeline(self) -> None:
        viewer = AuditStreamViewer()
        assert viewer.audit is None
        assert viewer.filters == {}
        assert not viewer._running

    def test_set_filter(self) -> None:
        viewer = AuditStreamViewer()
        viewer.set_filter(event_type="inference", severity="critical")
        assert viewer.filters["event_type"] == "inference"
        assert viewer.filters["severity"] == "critical"

    def test_clear_filters(self) -> None:
        viewer = AuditStreamViewer()
        viewer.set_filter(event_type="inference")
        viewer.clear_filters()
        assert viewer.filters == {}

    def test_stop_streaming(self) -> None:
        viewer = AuditStreamViewer()
        viewer._running = True
        viewer.stop_streaming()
        assert not viewer._running

    def test_display_event_info(self, sample_events: list[dict], capsys) -> None:
        viewer = AuditStreamViewer()
        viewer.disable_color()
        viewer.display_event(sample_events[0])  # info severity
        captured = capsys.readouterr()
        assert "state_machine::state_transition" in captured.out
        assert "INFO" in captured.out

    def test_display_event_critical(self, sample_events: list[dict], capsys) -> None:
        viewer = AuditStreamViewer()
        viewer.disable_color()
        viewer.display_event(sample_events[1])  # critical severity
        captured = capsys.readouterr()
        assert "governance_validator::governance_check" in captured.out
        assert "CRITICAL" in captured.out

    def test_display_event_warning(self, sample_events: list[dict], capsys) -> None:
        viewer = AuditStreamViewer()
        viewer.disable_color()
        viewer.display_event(sample_events[2])  # warning severity
        captured = capsys.readouterr()
        assert "inference_executor::inference" in captured.out
        assert "WARNING" in capsys.readouterr().out or "WARNING" in captured.out

    def test_display_event_with_dict(self, capsys) -> None:
        viewer = AuditStreamViewer()
        viewer.disable_color()
        event = {
            "event_type": "test_event",
            "severity": "info",
            "component": "test_component",
            "timestamp": datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            "details": {"key": "value"},
            "governance_context": ["schema1"],
            "session_id": uuid4(),
            "trace_id": uuid4(),
        }
        viewer.display_event(event)
        captured = capsys.readouterr()
        assert "test_component::test_event" in captured.out

    def test_color_toggle(self) -> None:
        viewer = AuditStreamViewer()
        viewer.enable_color()
        assert AuditStreamViewer._color_enabled
        viewer.disable_color()
        assert not AuditStreamViewer._color_enabled
        # Re-enable for other tests
        viewer.enable_color()


# ---------------------------------------------------------------------------
# TraceExporter tests
# ---------------------------------------------------------------------------


class TestTraceExporter:
    """Tests for TraceExporter multi-format export."""

    def test_export_json_creates_file(self, sample_trace_data: dict) -> None:
        exporter = TraceExporter()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "trace.json")
            exporter.export_json(sample_trace_data, path)
            assert os.path.isfile(path)
            with open(path) as f:
                parsed = json.load(f)
            assert "trace_id" in parsed

    def test_export_text_creates_file(self, sample_trace_data: dict) -> None:
        exporter = TraceExporter()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "trace.txt")
            exporter.export_text(sample_trace_data, path)
            assert os.path.isfile(path)
            with open(path) as f:
                content = f.read()
            assert "GARVIS COGNITION TRACE" in content

    def test_export_dot_creates_file(self, sample_trace_data: dict) -> None:
        exporter = TraceExporter()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "trace.dot")
            exporter.export_dot(sample_trace_data, path)
            assert os.path.isfile(path)
            with open(path) as f:
                content = f.read()
            assert "digraph garvis_trace {" in content

    def test_export_markdown_creates_file(self, sample_trace_data: dict) -> None:
        exporter = TraceExporter()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "trace.md")
            exporter.export_markdown(sample_trace_data, path)
            assert os.path.isfile(path)
            with open(path) as f:
                content = f.read()
            assert "# GARVIS Cognition Trace" in content
            assert "```mermaid" in content
            assert "flowchart TD" in content

    def test_export_markdown_has_tables(self, sample_trace_data: dict) -> None:
        exporter = TraceExporter()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "trace.md")
            exporter.export_markdown(sample_trace_data, path)
            with open(path) as f:
                content = f.read()
            assert "| # | From | To | Trigger |" in content  # State transitions table
            assert "| Result | Schema | Policy |" in content  # Governance checks table
            assert "| Memory ID | Type | Strength |" in content  # Memory influences table

    def test_export_all_returns_paths(self, sample_trace_data: dict) -> None:
        exporter = TraceExporter()
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = exporter.export_all(sample_trace_data, "test_trace", tmpdir)
            assert len(paths) == 4
            for p in paths:
                assert os.path.isfile(p)
            exts = {os.path.splitext(p)[1] for p in paths}
            assert exts == {".json", ".md", ".dot", ".txt"}

    def test_export_all_creates_directory(self, sample_trace_data: dict) -> None:
        exporter = TraceExporter()
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = os.path.join(tmpdir, "nested", "output")
            paths = exporter.export_all(sample_trace_data, "test", subdir)
            assert len(paths) == 4
            for p in paths:
                assert os.path.isfile(p)

    def test_empty_trace_data(self) -> None:
        """All exporters should handle minimal trace data gracefully."""
        exporter = TraceExporter()
        renderer = TraceRenderer()
        renderer.disable_color()
        empty = {"trace_id": uuid4(), "session_id": uuid4()}
        with tempfile.TemporaryDirectory() as tmpdir:
            exporter.export_json(empty, os.path.join(tmpdir, "e.json"))
            exporter.export_text(empty, os.path.join(tmpdir, "e.txt"))
            exporter.export_dot(empty, os.path.join(tmpdir, "e.dot"))
            exporter.export_markdown(empty, os.path.join(tmpdir, "e.md"))
            for ext in (".json", ".txt", ".dot", ".md"):
                assert os.path.isfile(os.path.join(tmpdir, f"e{ext}"))
