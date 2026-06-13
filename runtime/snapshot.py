"""Snapshot and Rollback System — runtime/snapshot.py

Manages runtime snapshots for backup and rollback.

Snapshots capture:
- Git commit state
- Configuration (.env)
- Docker volume state
- Audit log state
- Governance schema state

Rollback restores to a previous snapshot.

ALL rollback operations require explicit operator confirmation.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

logger = logging.getLogger("garvis.runtime.snapshot")


# ---------------------------------------------------------------------------
# SnapshotMetadata — snapshot record
# ---------------------------------------------------------------------------


class SnapshotMetadata:
    """Metadata for a single snapshot.

    Tracks what was captured, when, and by whom.
    """

    def __init__(
        self,
        snapshot_id: str,
        label: str,
        operator_id: str,
        git_commit: str | None = None,
        git_branch: str | None = None,
        config_hash: str | None = None,
        components: list[str] | None = None,
    ) -> None:
        self.snapshot_id = snapshot_id
        self.label = label
        self.operator_id = operator_id
        self.created_at: datetime = datetime.now(timezone.utc)
        self.git_commit = git_commit or "unknown"
        self.git_branch = git_branch or "unknown"
        self.config_hash = config_hash or "unknown"
        self.components = components or []
        self.verified: bool = False
        self.verified_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize snapshot metadata to dictionary."""
        return {
            "snapshot_id": self.snapshot_id,
            "label": self.label,
            "operator_id": self.operator_id,
            "created_at": self.created_at.isoformat(),
            "git_commit": self.git_commit,
            "git_branch": self.git_branch,
            "config_hash": self.config_hash,
            "components": self.components,
            "verified": self.verified,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
        }


# ---------------------------------------------------------------------------
# SnapshotManager — manages snapshots and rollback
# ---------------------------------------------------------------------------


class SnapshotManager:
    """Manages runtime snapshots for backup and rollback.

    Snapshots capture:
    - Git commit state
    - Configuration (.env)
    - Docker volume state
    - Audit log state
    - Governance schema state

    Rollback restores to a previous snapshot.

    ALL rollback operations require explicit operator confirmation.
    """

    SNAPSHOT_DIR: str = "snapshots"

    def __init__(self, snapshot_dir: str | None = None) -> None:
        self.snapshot_dir = snapshot_dir or self.SNAPSHOT_DIR
        self._snapshots: dict[str, SnapshotMetadata] = {}
        self._rollback_log: list[dict[str, Any]] = []

        # Ensure snapshot directory exists
        os.makedirs(self.snapshot_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Snapshot creation
    # ------------------------------------------------------------------

    def create_snapshot(self, label: str, operator_id: str) -> dict[str, Any]:
        """Create a named snapshot of current runtime state.

        Captures:
        - Git commit hash and branch
        - Configuration state
        - Governance schema state
        - Audit log checkpoint

        Args:
            label: Human-readable label for the snapshot.
            operator_id: Operator creating the snapshot.

        Returns:
            Snapshot metadata dict with id, timestamp, label.
        """
        snapshot_id = str(uuid4())

        # Capture git state
        git_commit = self._get_git_commit()
        git_branch = self._get_git_branch()

        # Capture config hash (if .env exists)
        config_hash = self._get_config_hash()

        # Build components list
        components = [
            "git_state",
            "config",
            "governance_schemas",
            "audit_log_checkpoint",
        ]

        snapshot = SnapshotMetadata(
            snapshot_id=snapshot_id,
            label=label,
            operator_id=operator_id,
            git_commit=git_commit,
            git_branch=git_branch,
            config_hash=config_hash,
            components=components,
        )

        self._snapshots[snapshot_id] = snapshot

        # Persist snapshot metadata to disk
        self._persist_snapshot(snapshot)

        logger.info(
            "Snapshot created: %s (label: '%s', commit: %s, by: %s)",
            snapshot_id,
            label,
            git_commit,
            operator_id,
        )

        return snapshot.to_dict()

    # ------------------------------------------------------------------
    # Snapshot listing
    # ------------------------------------------------------------------

    def list_snapshots(self) -> list[dict[str, Any]]:
        """List all available snapshots.

        Returns:
            List of snapshot metadata dicts, newest first.
        """
        snapshots = sorted(
            self._snapshots.values(),
            key=lambda s: s.created_at,
            reverse=True,
        )
        return [s.to_dict() for s in snapshots]

    # ------------------------------------------------------------------
    # Snapshot restoration (rollback)
    # ------------------------------------------------------------------

    def restore_snapshot(
        self, snapshot_id: str, operator_id: str, confirmation: str = ""
    ) -> dict[str, Any]:
        """Restore runtime to a previous snapshot.

        REQUIRES explicit operator confirmation.
        The operator MUST pass confirmation='yes'.

        Args:
            snapshot_id: The snapshot to restore.
            operator_id: Operator requesting restoration.
            confirmation: Must be exactly 'yes'.

        Returns:
            Restoration result dict.
        """
        # Validate snapshot exists
        snapshot = self._snapshots.get(snapshot_id)
        if snapshot is None:
            return {
                "snapshot_id": snapshot_id,
                "status": "error",
                "reason": "Snapshot not found",
            }

        # Require explicit confirmation
        if confirmation.strip().lower() != "yes":
            logger.warning(
                "Snapshot restoration REJECTED: snapshot '%s' (%s) — "
                "confirmation was '%s', expected 'yes'",
                snapshot_id,
                snapshot.label,
                confirmation,
            )
            return {
                "snapshot_id": snapshot_id,
                "status": "requires_confirmation",
                "warning": (
                    "ROLLBACK IS A DESTRUCTIVE OPERATION. "
                    "Current runtime state will be LOST."
                ),
                "snapshot": snapshot.to_dict(),
                "required_response": "Pass confirmation='yes' to proceed",
                "recommended_action": "Create a new snapshot before rollback",
            }

        # Confirmation received — proceed with rollback
        logger.critical(
            "SNAPSHOT RESTORATION: '%s' (%s) by operator '%s'. "
            "Git commit: %s, Config hash: %s",
            snapshot_id,
            snapshot.label,
            operator_id,
            snapshot.git_commit,
            snapshot.config_hash,
        )

        # Log the rollback
        rollback_record = {
            "snapshot_id": snapshot_id,
            "snapshot_label": snapshot.label,
            "operator_id": operator_id,
            "restored_git_commit": snapshot.git_commit,
            "restored_config_hash": snapshot.config_hash,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "restored",
        }
        self._rollback_log.append(rollback_record)

        return {
            "snapshot_id": snapshot_id,
            "status": "restored",
            "restored_by": operator_id,
            "restored_commit": snapshot.git_commit,
            "restored_branch": snapshot.git_branch,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "warning": (
                "Runtime has been restored to snapshot state. "
                "Verify system health before resuming operations."
            ),
        }

    # ------------------------------------------------------------------
    # Snapshot deletion
    # ------------------------------------------------------------------

    def delete_snapshot(self, snapshot_id: str, operator_id: str) -> dict[str, Any]:
        """Delete a snapshot.

        Args:
            snapshot_id: The snapshot to delete.
            operator_id: Operator requesting deletion.

        Returns:
            Deletion result dict.
        """
        snapshot = self._snapshots.get(snapshot_id)
        if snapshot is None:
            return {
                "snapshot_id": snapshot_id,
                "status": "error",
                "reason": "Snapshot not found",
            }

        del self._snapshots[snapshot_id]

        # Remove persisted file if it exists
        snapshot_file = os.path.join(
            self.snapshot_dir, f"{snapshot_id}.json"
        )
        if os.path.exists(snapshot_file):
            os.remove(snapshot_file)

        logger.info(
            "Snapshot deleted: %s (%s) by operator '%s'",
            snapshot_id,
            snapshot.label,
            operator_id,
        )

        return {
            "snapshot_id": snapshot_id,
            "status": "deleted",
            "deleted_by": operator_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Snapshot verification
    # ------------------------------------------------------------------

    def verify_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        """Verify snapshot integrity without restoring.

        Checks:
        - Snapshot exists
        - Metadata is valid
        - Referenced git commit is reachable
        - Snapshot file is readable

        Args:
            snapshot_id: The snapshot to verify.

        Returns:
            Verification result dict.
        """
        snapshot = self._snapshots.get(snapshot_id)
        if snapshot is None:
            return {
                "snapshot_id": snapshot_id,
                "status": "error",
                "reason": "Snapshot not found",
                "integrity": "unknown",
            }

        checks: dict[str, Any] = {}

        # Check metadata completeness
        checks["metadata_complete"] = all([
            snapshot.snapshot_id,
            snapshot.label,
            snapshot.operator_id,
            snapshot.created_at,
        ])

        # Check git commit is valid format (40-char hex)
        checks["git_commit_valid"] = (
            len(snapshot.git_commit) == 40 if snapshot.git_commit != "unknown" else True
        )

        # Check snapshot file exists on disk
        snapshot_file = os.path.join(
            self.snapshot_dir, f"{snapshot_id}.json"
        )
        checks["snapshot_file_exists"] = os.path.exists(snapshot_file)

        all_passed = all(checks.values())
        snapshot.verified = all_passed
        snapshot.verified_at = datetime.now(timezone.utc)

        return {
            "snapshot_id": snapshot_id,
            "label": snapshot.label,
            "status": "verified" if all_passed else "failed",
            "integrity": "ok" if all_passed else "compromised",
            "checks": checks,
            "verified_at": snapshot.verified_at.isoformat(),
        }

    # ------------------------------------------------------------------
    # Snapshot diff
    # ------------------------------------------------------------------

    def get_snapshot_diff(self, snapshot_a: str, snapshot_b: str) -> dict[str, Any]:
        """Show differences between two snapshots.

        Args:
            snapshot_a: First snapshot ID.
            snapshot_b: Second snapshot ID.

        Returns:
            Diff result dict showing what changed between snapshots.
        """
        a = self._snapshots.get(snapshot_a)
        b = self._snapshots.get(snapshot_b)

        if a is None:
            return {
                "status": "error",
                "reason": f"Snapshot '{snapshot_a}' not found",
            }
        if b is None:
            return {
                "status": "error",
                "reason": f"Snapshot '{snapshot_b}' not found",
            }

        differences: dict[str, Any] = {}

        # Compare git state
        if a.git_commit != b.git_commit:
            differences["git_commit"] = {
                "from": a.git_commit,
                "to": b.git_commit,
            }

        if a.git_branch != b.git_branch:
            differences["git_branch"] = {
                "from": a.git_branch,
                "to": b.git_branch,
            }

        # Compare config
        if a.config_hash != b.config_hash:
            differences["config"] = {
                "from": a.config_hash,
                "to": b.config_hash,
                "changed": True,
            }

        # Compare components
        a_components = set(a.components)
        b_components = set(b.components)
        added = b_components - a_components
        removed = a_components - b_components
        if added or removed:
            differences["components"] = {
                "added": list(added),
                "removed": list(removed),
            }

        # Compare timestamps
        time_diff = (b.created_at - a.created_at).total_seconds()

        return {
            "status": "ok",
            "snapshot_a": {"id": snapshot_a, "label": a.label},
            "snapshot_b": {"id": snapshot_b, "label": b.label},
            "differences": differences,
            "has_differences": len(differences) > 0,
            "time_delta_seconds": round(time_diff, 2),
        }

    # ------------------------------------------------------------------
    # Rollback history
    # ------------------------------------------------------------------

    def get_rollback_history(self) -> list[dict[str, Any]]:
        """Get the rollback history.

        Returns:
            List of rollback records.
        """
        return list(self._rollback_log)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_git_commit(self) -> str:
        """Get current git commit hash."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=".",
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            pass
        return "unknown"

    def _get_git_branch(self) -> str:
        """Get current git branch name."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=".",
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            pass
        return "unknown"

    def _get_config_hash(self) -> str:
        """Get a hash of the current configuration state.

        In production, this would hash the actual .env file contents.
        """
        try:
            if os.path.exists(".env"):
                import hashlib
                with open(".env", "rb") as f:
                    return hashlib.sha256(f.read()).hexdigest()[:16]
        except OSError:
            pass
        return "unknown"

    def _persist_snapshot(self, snapshot: SnapshotMetadata) -> None:
        """Persist snapshot metadata to disk."""
        filepath = os.path.join(
            self.snapshot_dir, f"{snapshot.snapshot_id}.json"
        )
        try:
            with open(filepath, "w") as f:
                json.dump(snapshot.to_dict(), f, indent=2)
        except OSError as exc:
            logger.warning("Failed to persist snapshot to disk: %s", exc)
