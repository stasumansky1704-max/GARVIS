"""Tests for Production Operations Layer — tests/test_production.py

Tests for:
- ProductionMode (production mode controller)
- SnapshotManager (snapshot and rollback)
- RuntimeMonitor (runtime monitoring)
- SafeOperationGuardrails (safe operation guardrails)
"""

from __future__ import annotations

import asyncio
import os
import pytest
import sys
import tempfile
import shutil

# Pre-populate sys.modules with stubs for heavy dependencies to avoid
# importing the full runtime/__init__.py chain
if "runtime.bootstrap" not in sys.modules:
    import types
    sys.modules["runtime.bootstrap"] = types.ModuleType("runtime.bootstrap")
    sys.modules["runtime.bootstrap"].RuntimeBootstrap = type("RuntimeBootstrap", (), {})

from runtime.config import RuntimeConfig
from runtime.production_mode import ProductionMode, ProductionSession
from runtime.snapshot import SnapshotManager
from runtime.monitor import RuntimeMonitor
from runtime.safe_ops import SafeOperationGuardrails


# ============================================================================
# ProductionMode Tests
# ============================================================================


class TestProductionMode:
    """Tests for the ProductionMode controller."""

    @pytest.fixture
    def config(self):
        """Create a test RuntimeConfig."""
        return RuntimeConfig(
            postgres_host="localhost",
            postgres_port=5432,
            ollama_host="http://localhost:11434",
            log_level="DEBUG",
        )

    @pytest.fixture
    def production(self, config):
        """Create a ProductionMode instance."""
        return ProductionMode(config)

    def test_init(self, production):
        """ProductionMode initializes in standby mode."""
        assert production.mode == "standby"
        assert production.guardrails_active is True
        assert production.is_operating is False
        assert production.is_maintenance is False

    def test_safe_operations_defined(self, production):
        """All expected safe operations are defined."""
        expected = {
            "start", "stop", "restart", "status", "backup",
            "rollback", "health", "schema_reload", "log_view", "alert_ack",
        }
        assert set(production.SAFE_OPERATIONS.keys()) == expected

    def test_destructive_operations_marked(self, production):
        """Destructive operations are properly marked."""
        assert production.DESTRUCTIVE_OPERATIONS["rollback"] is True
        assert production.DESTRUCTIVE_OPERATIONS["schema_reload"] is True
        assert production.DESTRUCTIVE_OPERATIONS["force_stop"] is True
        assert production.DESTRUCTIVE_OPERATIONS["volume_delete"] is True

    def test_start_production_session(self, production):
        """Starting a session returns valid session metadata."""
        result = production.start_production_session("operator_test")
        assert result["status"] == "started"
        assert "session_id" in result
        assert result["operator_id"] == "operator_test"
        assert result["mode"] == "standby"
        assert result["guardrails_active"] is True

    def test_active_sessions_tracking(self, production):
        """Active sessions are tracked correctly."""
        assert len(production.active_sessions) == 0
        production.start_production_session("op_1")
        assert len(production.active_sessions) == 1
        production.start_production_session("op_2")
        assert len(production.active_sessions) == 2

    def test_end_production_session(self, production):
        """Ending a session properly closes it."""
        session = production.start_production_session("operator_test")
        session_id = session["session_id"]
        assert len(production.active_sessions) == 1

        result = production.end_production_session(session_id)
        assert result["status"] == "ended"
        assert len(production.active_sessions) == 0

    def test_end_unknown_session(self, production):
        """Ending an unknown session returns error."""
        result = production.end_production_session("nonexistent-id")
        assert result["status"] == "error"

    def test_execute_safe_operation_status(self, production):
        """Status operation returns system status."""
        result = production.execute_safe_operation("status")
        assert result["operation"] == "status"
        assert result["status"] == "ok"
        assert "mode" in result

    def test_execute_safe_operation_log_view(self, production):
        """Log view operation returns log info."""
        result = production.execute_safe_operation("log_view")
        assert result["status"] == "ok"
        assert result["logs_available"] is True

    def test_execute_unknown_operation(self, production):
        """Unknown operation returns error."""
        result = production.execute_safe_operation("destroy_everything")
        assert result["status"] == "error"

    def test_destructive_operation_requires_confirmation(self, production):
        """Destructive operations require confirmation."""
        result = production.execute_safe_operation("rollback")
        assert result["status"] == "requires_confirmation"
        assert "DESTRUCTIVE" in result.get("reason", "") or "destructive" in result.get("warning", "").lower()

    def test_schema_reload_blocked(self, production):
        """Schema reload is blocked without confirmation."""
        result = production.execute_safe_operation("schema_reload")
        assert result["status"] == "requires_confirmation"
        assert "DESTRUCTIVE" in result.get("reason", "") or "destructive" in result.get("reason", "").lower()

    def test_require_confirmation(self, production):
        """require_confirmation returns proper structure."""
        result = production.require_confirmation("rollback", "Rollback to v1.0")
        assert result["requires_confirmation"] is True
        assert result["is_destructive"] is True
        assert result["details"] == "Rollback to v1.0"
        assert "backup_recommended" in result

    def test_confirm_destructive_operation_wrong_response(self, production):
        """Wrong confirmation response rejects the operation."""
        result = production.confirm_destructive_operation("rollback", "op1", "no")
        assert result["status"] == "rejected"

    def test_confirm_destructive_operation_correct(self, production):
        """Correct 'yes' response confirms the operation."""
        result = production.confirm_destructive_operation("rollback", "op1", "yes")
        assert result["status"] == "confirmed"
        assert result["confirmed_by"] == "op1"

    def test_non_destructive_confirmation_fails(self, production):
        """Confirming a non-destructive operation returns error."""
        result = production.confirm_destructive_operation("status", "op1", "yes")
        assert result["status"] == "error"

    def test_enter_maintenance_mode(self, production):
        """Entering maintenance mode changes the mode."""
        production.start_production_session("op1")
        result = production.enter_maintenance_mode("op1", "system check")
        assert result is True
        assert production.mode == "maintenance"
        assert production.is_maintenance is True
        assert production.is_operating is False

    def test_exit_maintenance_mode(self, production):
        """Exiting maintenance mode returns to standby."""
        production.start_production_session("op1")
        production.enter_maintenance_mode("op1", "test")
        result = production.exit_maintenance_mode("op1")
        assert result is True
        assert production.mode == "standby"

    def test_maintenance_blocks_write_operations(self, production):
        """Write operations are blocked in maintenance mode."""
        production.start_production_session("op1")
        production.enter_maintenance_mode("op1", "test")
        result = production.execute_safe_operation("start")
        assert result["status"] == "blocked"
        assert "maintenance mode" in result.get("reason", "").lower()

    def test_read_only_in_maintenance_allowed(self, production):
        """Read-only operations are allowed in maintenance mode."""
        production.start_production_session("op1")
        production.enter_maintenance_mode("op1", "test")
        result = production.execute_safe_operation("status")
        assert result["status"] == "ok"

    def test_get_daily_status(self, production):
        """Daily status returns expected structure."""
        result = production.get_daily_status()
        assert "date" in result
        assert result["current_mode"] == "standby"
        assert result["guardrails_active"] is True
        assert "available_operations" in result
        assert "destructive_operations" in result

    def test_get_daily_logs_empty(self, production):
        """Daily logs returns empty list when no operations."""
        today = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%d")
        logs = production.get_daily_logs(today)
        assert logs == []

    def test_get_daily_logs_after_operations(self, production):
        """Daily logs accumulate after operations."""
        production.execute_safe_operation("status")
        production.execute_safe_operation("health")
        today = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime("%Y-%m-%d")
        logs = production.get_daily_logs(today)
        assert len(logs) >= 2

    def test_get_guardrail_status(self, production):
        """Guardrail status returns expected structure."""
        result = production.get_guardrail_status()
        assert result["guardrails_active"] is True
        assert "destructive_operations" in result
        assert "safe_operations" in result

    def test_disable_guardrails_warning(self, production):
        """Disabling guardrails requires confirmation."""
        result = production.disable_guardrails("op1", "testing")
        assert result["status"] == "requires_confirmation"
        assert "GUARDRAILS" in result.get("warning", "")

    def test_enable_guardrails(self, production):
        """Enabling guardrails works."""
        result = production.enable_guardrails()
        assert result["status"] == "ok"
        assert result["guardrails_active"] is True


# ============================================================================
# SnapshotManager Tests
# ============================================================================


class TestSnapshotManager:
    """Tests for the SnapshotManager."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for snapshots."""
        tmp = tempfile.mkdtemp()
        yield tmp
        shutil.rmtree(tmp, ignore_errors=True)

    @pytest.fixture
    def manager(self, temp_dir):
        """Create a SnapshotManager with temp directory."""
        return SnapshotManager(snapshot_dir=temp_dir)

    def test_init(self, manager):
        """SnapshotManager initializes with empty snapshots."""
        assert manager.list_snapshots() == []

    def test_create_snapshot(self, manager):
        """Creating a snapshot returns metadata."""
        result = manager.create_snapshot("before_schema_change", "op1")
        assert "snapshot_id" in result
        assert result["label"] == "before_schema_change"
        assert result["operator_id"] == "op1"
        assert result["git_commit"] is not None
        assert "components" in result

    def test_create_snapshot_persists(self, manager, temp_dir):
        """Snapshot metadata is persisted to disk."""
        result = manager.create_snapshot("test", "op1")
        snapshot_id = result["snapshot_id"]
        filepath = os.path.join(temp_dir, f"{snapshot_id}.json")
        assert os.path.exists(filepath)

    def test_list_snapshots(self, manager):
        """Listing snapshots returns them in reverse chronological order."""
        manager.create_snapshot("snapshot_a", "op1")
        manager.create_snapshot("snapshot_b", "op1")
        snapshots = manager.list_snapshots()
        assert len(snapshots) == 2
        # Newest first
        assert snapshots[0]["label"] == "snapshot_b"
        assert snapshots[1]["label"] == "snapshot_a"

    def test_verify_snapshot(self, manager):
        """Verifying a snapshot checks integrity."""
        result = manager.create_snapshot("test", "op1")
        snapshot_id = result["snapshot_id"]
        verification = manager.verify_snapshot(snapshot_id)
        assert verification["status"] == "verified"
        assert verification["integrity"] == "ok"

    def test_verify_unknown_snapshot(self, manager):
        """Verifying unknown snapshot returns error."""
        result = manager.verify_snapshot("nonexistent")
        assert result["status"] == "error"

    def test_restore_snapshot_requires_confirmation(self, manager):
        """Restoring without confirmation is rejected."""
        result = manager.create_snapshot("test", "op1")
        snapshot_id = result["snapshot_id"]
        restore_result = manager.restore_snapshot(snapshot_id, "op1", "no")
        assert restore_result["status"] == "requires_confirmation"
        assert "ROLLBACK" in restore_result.get("warning", "")

    def test_restore_snapshot_with_confirmation(self, manager):
        """Restoring with 'yes' confirmation succeeds."""
        result = manager.create_snapshot("test", "op1")
        snapshot_id = result["snapshot_id"]
        restore_result = manager.restore_snapshot(snapshot_id, "op1", "yes")
        assert restore_result["status"] == "restored"
        assert restore_result["restored_by"] == "op1"

    def test_restore_unknown_snapshot(self, manager):
        """Restoring unknown snapshot returns error."""
        result = manager.restore_snapshot("nonexistent", "op1", "yes")
        assert result["status"] == "error"
        assert "not found" in result.get("reason", "").lower()

    def test_delete_snapshot(self, manager):
        """Deleting a snapshot removes it."""
        result = manager.create_snapshot("to_delete", "op1")
        snapshot_id = result["snapshot_id"]
        assert len(manager.list_snapshots()) == 1

        delete_result = manager.delete_snapshot(snapshot_id, "op1")
        assert delete_result["status"] == "deleted"
        assert len(manager.list_snapshots()) == 0

    def test_delete_unknown_snapshot(self, manager):
        """Deleting unknown snapshot returns error."""
        result = manager.delete_snapshot("nonexistent", "op1")
        assert result["status"] == "error"

    def test_snapshot_diff(self, manager):
        """Diff between snapshots shows differences."""
        a = manager.create_snapshot("snapshot_a", "op1")
        b = manager.create_snapshot("snapshot_b", "op1")
        diff = manager.get_snapshot_diff(a["snapshot_id"], b["snapshot_id"])
        assert diff["status"] == "ok"
        assert "differences" in diff
        assert "time_delta_seconds" in diff

    def test_snapshot_diff_unknown(self, manager):
        """Diff with unknown snapshot returns error."""
        a = manager.create_snapshot("snapshot_a", "op1")
        diff = manager.get_snapshot_diff(a["snapshot_id"], "nonexistent")
        assert diff["status"] == "error"

    def test_rollback_history(self, manager):
        """Rollback history tracks restorations."""
        result = manager.create_snapshot("test", "op1")
        snapshot_id = result["snapshot_id"]
        assert len(manager.get_rollback_history()) == 0

        manager.restore_snapshot(snapshot_id, "op1", "yes")
        history = manager.get_rollback_history()
        assert len(history) == 1
        assert history[0]["snapshot_id"] == snapshot_id


# ============================================================================
# RuntimeMonitor Tests
# ============================================================================


class TestRuntimeMonitor:
    """Tests for the RuntimeMonitor."""

    @pytest.fixture
    def config(self):
        """Create a test RuntimeConfig."""
        return RuntimeConfig(
            postgres_host="localhost",
            postgres_port=5432,
            ollama_host="http://localhost:11434",
        )

    @pytest.fixture
    def monitor(self, config):
        """Create a RuntimeMonitor instance."""
        return RuntimeMonitor(config)

    def test_init(self, monitor):
        """RuntimeMonitor initializes correctly."""
        assert monitor._monitoring_active is False

    def test_get_service_status(self, monitor):
        """Service status returns structure for all services."""
        result = monitor.get_service_status()
        assert "overall" in result
        assert "services" in result
        for service_name in ["api", "ollama", "postgres", "governance"]:
            assert service_name in result["services"]

    def test_get_container_status(self, monitor):
        """Container status returns a list (may be empty if no docker)."""
        result = monitor.get_container_status()
        assert isinstance(result, list)

    def test_get_resource_usage(self, monitor):
        """Resource usage returns CPU and memory info."""
        result = monitor.get_resource_usage()
        assert "timestamp" in result
        assert "cpu" in result
        assert "memory" in result

    def test_get_ollama_status(self, monitor):
        """Ollama status returns structured info."""
        result = monitor.get_ollama_status()
        assert "status" in result

    def test_get_database_status(self, monitor):
        """Database status returns structured info."""
        result = monitor.get_database_status()
        assert "status" in result

    def test_get_full_report(self, monitor):
        """Full report combines all monitoring checks."""
        result = monitor.get_full_report()
        assert "timestamp" in result
        assert "services" in result
        assert "containers" in result
        assert "resources" in result
        assert "ollama" in result
        assert "database" in result
        assert "overall" in result

    def test_get_dashboard_status(self, monitor):
        """Dashboard status returns condensed info."""
        result = monitor.get_dashboard_status()
        assert "overall" in result
        assert "services" in result
        assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_continuous_monitoring_starts(self, monitor):
        """Continuous monitoring loop starts."""
        # Start monitoring with short interval
        task = asyncio.create_task(monitor.continuous_monitoring(interval=1))
        await asyncio.sleep(0.5)
        assert monitor._monitoring_active is True
        monitor.stop_monitoring()
        await asyncio.sleep(0.1)

    def test_stop_monitoring(self, monitor):
        """Stop monitoring sets flag to False."""
        monitor._monitoring_active = True
        monitor.stop_monitoring()
        assert monitor._monitoring_active is False


# ============================================================================
# SafeOperationGuardrails Tests
# ============================================================================


class TestSafeOperationGuardrails:
    """Tests for the SafeOperationGuardrails."""

    @pytest.fixture
    def guardrails(self):
        """Create a SafeOperationGuardrails instance."""
        return SafeOperationGuardrails()

    def test_init(self, guardrails):
        """Guardrails initialize enabled."""
        assert guardrails._guardrails_enabled is True
        assert len(guardrails._intervention_log) == 0

    def test_destructive_commands_list(self, guardrails):
        """Destructive commands list is populated."""
        assert len(guardrails.DESTRUCTIVE_COMMANDS) > 0
        assert "rm -rf" in guardrails.DESTRUCTIVE_COMMANDS
        assert "docker volume rm" in guardrails.DESTRUCTIVE_COMMANDS
        assert "git reset --hard" in guardrails.DESTRUCTIVE_COMMANDS

    def test_safe_command_passes(self, guardrails):
        """Safe command passes validation."""
        result = guardrails.validate_command("ls -la")
        assert result["safe"] is True
        assert result["blocked"] is False
        assert result["requires_confirmation"] is False

    def test_rm_rf_blocked(self, guardrails):
        """rm -rf is blocked."""
        result = guardrails.validate_command("rm -rf /")
        assert result["safe"] is False
        assert result["blocked"] is True

    def test_docker_volume_rm_blocked(self, guardrails):
        """docker volume rm is blocked."""
        result = guardrails.validate_command("docker volume rm my_volume")
        assert result["safe"] is False
        assert result["blocked"] is True

    def test_git_reset_hard_blocked(self, guardrails):
        """git reset --hard is blocked."""
        result = guardrails.validate_command("git reset --hard HEAD~1")
        assert result["safe"] is False
        assert result["blocked"] is True

    def test_docker_compose_down_v_blocked(self, guardrails):
        """docker compose down -v is blocked."""
        result = guardrails.validate_command("docker compose down -v")
        assert result["safe"] is False

    def test_docker_stop_needs_confirmation(self, guardrails):
        """docker stop requires confirmation."""
        result = guardrails.validate_command("docker stop my_container")
        assert result["requires_confirmation"] is True

    def test_git_push_force_needs_confirmation(self, guardrails):
        """git push --force requires confirmation."""
        result = guardrails.validate_command("git push --force origin main")
        assert result["requires_confirmation"] is True

    def test_sql_drop_blocked(self, guardrails):
        """SQL drop is blocked."""
        result = guardrails.validate_command("mysql -e 'DROP TABLE users;'")
        assert result["safe"] is False

    def test_rm_with_flags_blocked(self, guardrails):
        """rm with recursive flags is blocked."""
        result = guardrails.validate_command("rm -r /some/dir")
        assert result["safe"] is False

    def test_intervention_logged_on_block(self, guardrails):
        """Guardrail intervention is logged when command is blocked."""
        guardrails.validate_command("rm -rf /tmp")
        assert len(guardrails._intervention_log) >= 1

    def test_get_intervention_log(self, guardrails):
        """Intervention log is retrievable."""
        guardrails.validate_command("rm -rf /tmp")
        log = guardrails.get_intervention_log()
        assert isinstance(log, list)
        assert len(log) >= 1

    def test_get_intervention_summary(self, guardrails):
        """Intervention summary has correct structure."""
        guardrails.validate_command("rm -rf /tmp")
        summary = guardrails.get_intervention_summary()
        assert "total_interventions" in summary
        assert "by_operation" in summary
        assert summary["guardrails_enabled"] is True

    def test_validate_schema_change_allowed(self, guardrails):
        """Allowed schema change passes."""
        result = guardrails.validate_schema_change("review", "epistemic_safety")
        assert result["allowed"] is True
        assert result["risk_level"] == "low"

    def test_validate_schema_change_risky(self, guardrails):
        """Risky schema change is flagged."""
        result = guardrails.validate_schema_change("deactivate", "operational_integrity")
        assert result["allowed"] is False
        assert result["requires_confirmation"] is True
        assert result["risk_level"] == "high"

    def test_validate_critical_schema_blocked(self, guardrails):
        """Modifying critical schema requires multi-operator approval."""
        result = guardrails.validate_schema_change("deactivate", "boundary_enforcement")
        assert result["allowed"] is False
        assert result["risk_level"] == "critical"
        assert result["required_approval"] == "operator_multi"

    def test_validate_workflow_low_risk(self, guardrails):
        """Low-risk workflow passes."""
        workflow = {
            "name": "status_check",
            "operations": [
                {"type": "status"},
                {"type": "check"},
            ],
        }
        result = guardrails.validate_workflow_proposal(workflow)
        assert result["valid"] is True
        assert result["risk_level"] == "low"

    def test_validate_workflow_critical_risk(self, guardrails):
        """Critical-risk workflow is blocked."""
        workflow = {
            "name": "cleanup",
            "operations": [
                {"type": "delete"},
                {"type": "purge"},
            ],
        }
        result = guardrails.validate_workflow_proposal(workflow)
        assert result["valid"] is True
        assert result["allowed"] is False
        assert result["risk_level"] == "critical"

    def test_validate_workflow_missing_fields(self, guardrails):
        """Workflow with missing required fields fails."""
        workflow = {"operations": [{"type": "status"}]}
        result = guardrails.validate_workflow_proposal(workflow)
        assert result["valid"] is False

    def test_preserve_fail_closed(self, guardrails):
        """Fail-closed state is preserved."""
        result = guardrails.preserve_fail_closed("fail_closed")
        assert result["fail_closed_preserved"] is True
        assert result["recommendation"] == "maintain"

    def test_preserve_fail_closed_safe_state(self, guardrails):
        """Safe state allows maintain_or_progress."""
        result = guardrails.preserve_fail_closed("standby")
        assert result["fail_closed_preserved"] is True
        assert result["recommendation"] == "maintain_or_progress"

    def test_preserve_fail_closed_active_state(self, guardrails):
        """Active state recommends monitoring."""
        result = guardrails.preserve_fail_closed("cognition_active")
        assert result["fail_closed_preserved"] is True
        assert result["recommendation"] == "monitor"

    def test_enable_guardrails(self, guardrails):
        """Enabling guardrails works."""
        result = guardrails.enable_guardrails()
        assert result["status"] == "enabled"
        assert result["action"] == "enable_guardrails"

    def test_disable_guardrails_requires_confirmation(self, guardrails):
        """Disabling guardrails requires confirmation."""
        result = guardrails.disable_guardrails("op1", "testing")
        assert result["status"] == "requires_confirmation"
        assert "DANGEROUS" in result.get("warning", "")

    def test_get_status(self, guardrails):
        """Status returns expected structure."""
        result = guardrails.get_status()
        assert result["enabled"] is True
        assert result["destructive_patterns_blocked"] > 0
        assert result["confirmation_required_patterns"] > 0

    def test_guardrails_disabled_allows_all(self, guardrails):
        """When guardrails are disabled, all commands pass with warning."""
        guardrails._guardrails_enabled = False
        result = guardrails.validate_command("rm -rf /")
        assert result["safe"] is True
        assert "GUARDRAILS ARE DISABLED" in result.get("warning", "")
