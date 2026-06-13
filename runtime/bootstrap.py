"""Runtime bootstrap for GARVIS.

Implements governance-first initialization with strict ordering.
Any bootstrap step failure results in FAIL_CLOSED state.
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from runtime.config import RuntimeConfig

# Database
from database.connection import DatabaseConnection

# Governance layer (MUST be ready before anything else)
from governance.loader import SchemaLoader
from governance.registry import GovernanceRegistry
from governance.validator import RuntimeValidator
from governance.middleware import GovernanceMiddleware
from governance.enforcer import EnforcementEngine

# Cognition layer
from cognition.state_machine import CognitiveStateMachine

# Memory layer
from memory.episodic import EpisodicMemoryStore

# Traceability layer
from traceability.lineage import LineageTracker
from traceability.audit import AuditPipeline

# Inference layer
from inference.ollama_client import OllamaClient
from inference.governed_executor import GovernedInferenceExecutor

# Models
from models.cognition import OperationalState

logger = logging.getLogger(__name__)


class GovernanceInconsistencyError(Exception):
    """Raised when cross-schema consistency validation fails."""

    def __init__(self, inconsistencies: list[str]) -> None:
        self.inconsistencies = inconsistencies
        message = (
            f"Governance inconsistency detected ({len(inconsistencies)} issues): "
            + "; ".join(inconsistencies)
        )
        super().__init__(message)


class BootstrapError(Exception):
    """Raised when bootstrap fails catastrophically."""
    pass


class RuntimeBootstrap:
    """Bootstraps the GARVIS runtime with governance-first initialization.

    Initialization order (strict -- governance must be ready before anything else):
        1.  Load configuration
        2.  Connect to PostgreSQL
        3.  Run database migrations
        4.  Load governance schemas
        5.  Validate cross-schema consistency
        6.  Initialize governance registry
        7.  Initialize governance middleware (inactive)
        8.  Initialize state machine (starts UNINITIALIZED)
        9.  Initialize audit pipeline
        10. Initialize traceability engine
        11. Initialize memory store
        12. Initialize Ollama client
        13. Initialize inference executor
        14. ACTIVATE governance middleware
        15. Transition state machine to STANDBY

    Any step failure -> FAIL_CLOSED. Runtime does not start with partial governance.
    """

    def __init__(self, config_path: str | None = None) -> None:
        self.config: RuntimeConfig | None = None
        self.components: dict[str, Any] = {}
        self._state_machine: CognitiveStateMachine | None = None
        self._initialized: bool = False
        self._shutdown_event: asyncio.Event | None = None

    # ------------------------------------------------------------------
    # Bootstrap sequence
    # ------------------------------------------------------------------

    async def bootstrap(self) -> dict[str, Any]:
        """Execute full bootstrap sequence.

        Returns:
            Dictionary of all initialized components.

        Raises:
            BootstrapError: On any governance or initialization failure.
            GovernanceInconsistencyError: On cross-schema inconsistency.
        """
        logger.info("=" * 60)
        logger.info("GARVIS Runtime Bootstrap Starting")
        logger.info("=" * 60)

        try:
            # ---- Step 1: Load configuration --------------------------------
            logger.info("[Step 1/15] Loading configuration...")
            self.config = RuntimeConfig.from_env()
            self.config.configure_logging()
            logger.info("[Step 1/15] Configuration loaded successfully")

            # ---- Step 2: Connect to PostgreSQL -----------------------------
            logger.info("[Step 2/15] Connecting to PostgreSQL...")
            db = DatabaseConnection()
            await db.initialize_pool(self.config.postgres_dsn)
            self.components["database"] = db
            logger.info("[Step 2/15] PostgreSQL connected")

            # ---- Step 3: Run database migrations ---------------------------
            logger.info("[Step 3/15] Running database migrations...")
            await self._run_migrations(db)
            logger.info("[Step 3/15] Migrations complete")

            # ---- Step 4: Load governance schemas ---------------------------
            logger.info("[Step 4/15] Loading governance schemas...")
            loader = SchemaLoader(self.config.governance_schemas_path)
            schemas = loader.load_all()
            if not schemas:
                logger.warning("No governance schemas found in %s", self.config.governance_schemas_path)
            else:
                logger.info("[Step 4/15] Loaded %d governance schemas", len(schemas))

            # ---- Step 5: Validate cross-schema consistency ----------------
            logger.info("[Step 5/15] Validating cross-schema consistency...")
            registry = GovernanceRegistry(loader)
            registry.initialize()
            inconsistencies = registry.validate_cross_schema_consistency()
            if inconsistencies:
                logger.critical(
                    "[Step 5/15] Cross-schema consistency FAILED: %s",
                    inconsistencies,
                )
                raise GovernanceInconsistencyError(inconsistencies)
            logger.info("[Step 5/15] Cross-schema consistency validated")

            # ---- Step 6: Initialize governance registry -------------------
            logger.info("[Step 6/15] Initializing governance registry...")
            self.components["governance_registry"] = registry
            logger.info("[Step 6/15] Governance registry initialized")

            # ---- Step 7-8: Initialize core governance components ----------
            logger.info("[Step 7/15] Initializing governance middleware...")
            validator = RuntimeValidator(registry)
            enforcer = EnforcementEngine(None, None)  # Will be wired later
            middleware = GovernanceMiddleware(validator, enforcer)
            self.components["governance_validator"] = validator
            self.components["governance_middleware"] = middleware
            self.components["enforcement_engine"] = enforcer
            logger.info("[Step 7/15] Governance middleware created (inactive)")

            logger.info("[Step 8/15] Initializing state machine...")
            state_machine = CognitiveStateMachine(validator, enforcer)
            enforcer.state_machine = state_machine  # Wire back-reference
            self._state_machine = state_machine
            self.components["state_machine"] = state_machine
            logger.info(
                "[Step 8/15] State machine initialized (state=%s)",
                state_machine.get_current_state().value,
            )

            # ---- Step 9: Initialize audit pipeline ------------------------
            logger.info("[Step 9/15] Initializing audit pipeline...")
            audit = AuditPipeline(db)
            self.components["audit_pipeline"] = audit
            logger.info("[Step 9/15] Audit pipeline initialized")

            # ---- Step 10: Initialize traceability engine ------------------
            logger.info("[Step 10/15] Initializing traceability engine...")
            lineage = LineageTracker(db)
            self.components["lineage_tracker"] = lineage
            logger.info("[Step 10/15] Traceability engine initialized")

            # ---- Step 11: Initialize memory store -------------------------
            logger.info("[Step 11/15] Initializing memory store...")
            memory = EpisodicMemoryStore(db, middleware)
            self.components["memory_store"] = memory
            logger.info("[Step 11/15] Memory store initialized")

            # ---- Step 12: Initialize Ollama client ------------------------
            logger.info("[Step 12/15] Initializing Ollama client...")
            ollama = OllamaClient(self.config.ollama_host, self.config.default_model)
            self.components["ollama_client"] = ollama
            logger.info("[Step 12/15] Ollama client initialized (%s)", self.config.ollama_host)

            # ---- Step 13: Initialize inference executor -------------------
            logger.info("[Step 13/15] Initializing inference executor...")
            executor = GovernedInferenceExecutor(
                ollama, middleware, state_machine, memory, lineage, audit
            )
            self.components["inference_executor"] = executor
            logger.info("[Step 13/15] Inference executor initialized")

            # ---- Step 14: ACTIVATE governance middleware ------------------
            logger.info("[Step 14/15] Activating governance middleware...")
            middleware.activate()
            logger.info("[Step 14/15] Governance middleware ACTIVE -- all cognition is now governed")

            # ---- Step 15: Transition to STANDBY ---------------------------
            logger.info("[Step 15/15] Transitioning to STANDBY...")
            success = await state_machine.transition(
                OperationalState.STANDBY, "bootstrap_complete"
            )
            if not success:
                raise BootstrapError(
                    "Failed to transition to STANDBY state -- bootstrap aborted"
                )
            logger.info(
                "[Step 15/15] State machine in STANDBY (state=%s)",
                state_machine.get_current_state().value,
            )

            self._initialized = True
            self._shutdown_event = asyncio.Event()

            logger.info("=" * 60)
            logger.info("GARVIS Runtime Bootstrap COMPLETE")
            logger.info("All %d components initialized and governance-active", len(self.components))
            logger.info("Current state: %s", state_machine.get_current_state().value)
            logger.info("=" * 60)

            return self.components

        except GovernanceInconsistencyError:
            # Re-raise -- this is a fatal governance failure
            await self._enter_fail_closed("governance_inconsistency")
            raise

        except BootstrapError:
            await self._enter_fail_closed("bootstrap_error")
            raise

        except Exception as exc:
            logger.critical("Bootstrap failed with unexpected error: %s", exc, exc_info=True)
            await self._enter_fail_closed(f"unexpected_error: {type(exc).__name__}")
            raise BootstrapError(f"Bootstrap failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    async def shutdown(self) -> None:
        """Graceful shutdown with full audit trail.

        Shutdown sequence:
            1. Transition state machine to SHUTDOWN
            2. Flush audit pipeline
            3. Close Ollama client
            4. Close database connection pool
            5. Mark all components as shut down
        """
        logger.info("=" * 60)
        logger.info("GARVIS Runtime Shutdown Starting")
        logger.info("=" * 60)

        try:
            # Transition to SHUTDOWN
            if self._state_machine is not None:
                current = self._state_machine.get_current_state()
                if current != OperationalState.SHUTDOWN:
                    logger.info("Transitioning state machine to SHUTDOWN...")
                    await self._state_machine.transition(
                        OperationalState.SHUTDOWN, "graceful_shutdown"
                    )
                    logger.info("State machine: %s -> SHUTDOWN", current.value)

            # Flush audit pipeline
            audit = self.components.get("audit_pipeline")
            if audit is not None:
                logger.info("Flushing audit pipeline...")
                await audit.flush()
                logger.info("Audit pipeline flushed")

            # Close Ollama client
            ollama = self.components.get("ollama_client")
            if ollama is not None:
                logger.info("Closing Ollama client...")
                await ollama.close()
                logger.info("Ollama client closed")

            # Close database
            db = self.components.get("database")
            if db is not None:
                logger.info("Closing database connection pool...")
                await db.close()
                logger.info("Database connection pool closed")

            self._initialized = False

            if self._shutdown_event is not None:
                self._shutdown_event.set()

            logger.info("=" * 60)
            logger.info("GARVIS Runtime Shutdown COMPLETE")
            logger.info("=" * 60)

        except Exception as exc:
            logger.critical("Error during shutdown: %s", exc, exc_info=True)
            raise

    # ------------------------------------------------------------------
    # Component access
    # ------------------------------------------------------------------

    def get_component(self, name: str) -> Any:
        """Get an initialized component by name.

        Args:
            name: Component name (e.g., "state_machine", "audit_pipeline").

        Returns:
            The component instance.

        Raises:
            KeyError: If component not found.
        """
        if name not in self.components:
            raise KeyError(f"Component '{name}' not found. Available: {list(self.components.keys())}")
        return self.components[name]

    def _validate_components(self) -> list[str]:
        """Validate that all expected components are initialized.

        Returns:
            List of missing component names (empty = all present).
        """
        expected = [
            "database",
            "governance_registry",
            "governance_validator",
            "governance_middleware",
            "enforcement_engine",
            "state_machine",
            "audit_pipeline",
            "lineage_tracker",
            "memory_store",
            "ollama_client",
            "inference_executor",
        ]
        missing = [name for name in expected if name not in self.components]
        if missing:
            logger.warning("Missing components: %s", missing)
        return missing

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run_migrations(self, db: DatabaseConnection) -> None:
        """Read and execute SQL migration files from database/migrations/."""
        migrations_dir = Path("database/migrations")
        if not migrations_dir.exists():
            logger.warning("Migrations directory not found: %s", migrations_dir)
            return

        migration_files = sorted(migrations_dir.glob("*.sql"))
        if not migration_files:
            logger.warning("No SQL migration files found in %s", migrations_dir)
            return

        logger.info("Found %d migration file(s)", len(migration_files))

        for migration_file in migration_files:
            logger.info("Applying migration: %s", migration_file.name)
            sql = migration_file.read_text(encoding="utf-8")
            # Execute the SQL -- in production this would use a proper migration tool
            try:
                await db.execute(sql)
                logger.info("Migration applied: %s", migration_file.name)
            except Exception as exc:
                logger.error("Migration failed: %s -- %s", migration_file.name, exc)
                raise BootstrapError(
                    f"Migration failed for {migration_file.name}: {exc}"
                ) from exc

        logger.info("All migrations applied successfully")

    async def _enter_fail_closed(self, reason: str) -> None:
        """Enter FAIL_CLOSED state due to bootstrap failure.

        This is the fail-closed safety mechanism: if any bootstrap step
        fails, the runtime enters a halted state where no cognition
        can occur until the issue is resolved by an operator.
        """
        logger.critical("ENTERING FAIL_CLOSED state -- reason: %s", reason)
        if self._state_machine is not None:
            try:
                await self._state_machine.transition(
                    OperationalState.FAIL_CLOSED, reason
                )
            except Exception as exc:
                logger.critical(
                    "Even FAIL_CLOSED transition failed: %s", exc, exc_info=True
                )
        else:
            logger.critical("State machine not available -- cannot transition to FAIL_CLOSED")

    @property
    def is_initialized(self) -> bool:
        """Check if bootstrap completed successfully."""
        return self._initialized

    @property
    def state_machine(self) -> CognitiveStateMachine | None:
        """Access the state machine directly."""
        return self._state_machine
