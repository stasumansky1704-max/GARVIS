"""Configuration management for GARVIS runtime."""
from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RuntimeConfig:
    """Configuration loaded from environment variables.

    Follows the 12-factor app methodology: all configuration
    is injected via environment variables. Sensible defaults
    are provided for local development.
    """

    # --- PostgreSQL ---
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "garvis"
    postgres_password: str = "garvis_secret"
    postgres_db: str = "garvis_runtime"

    # --- Ollama ---
    ollama_host: str = "http://localhost:11434"
    default_model: str = "llama3.1"

    # --- Governance ---
    governance_schemas_path: str = "./governance/schemas"

    # --- Logging ---
    log_level: str = "INFO"

    # --- Inference ---
    max_inference_retries: int = 3
    inference_timeout: int = 120

    # --- Audit ---
    audit_buffer_size: int = 100
    audit_flush_interval: int = 5

    @property
    def postgres_dsn(self) -> str:
        """Build PostgreSQL DSN from individual components."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @classmethod
    def from_env(cls) -> "RuntimeConfig":
        """Load configuration from environment variables.

        Each field can be overridden by setting an environment
        variable with the same name in UPPER_SNAKE_CASE.

        Examples:
            POSTGRES_HOST=db.example.com
            LOG_LEVEL=DEBUG
            MAX_INFERENCE_RETRIES=5
        """
        logger.debug("Loading configuration from environment variables")

        def _env(var: str, default: str | None = None) -> str | None:
            return os.environ.get(var, default)

        def _env_int(var: str, default: int) -> int:
            val = _env(var)
            return int(val) if val is not None else default

        config = cls(
            postgres_host=_env("POSTGRES_HOST", "localhost"),
            postgres_port=_env_int("POSTGRES_PORT", 5432),
            postgres_user=_env("POSTGRES_USER", "garvis"),
            postgres_password=_env("POSTGRES_PASSWORD", "garvis_secret"),
            postgres_db=_env("POSTGRES_DB", "garvis_runtime"),
            ollama_host=_env("OLLAMA_HOST", "http://localhost:11434"),
            default_model=_env("OLLAMA_DEFAULT_MODEL", "llama3.1"),
            governance_schemas_path=_env(
                "GOVERNANCE_SCHEMAS_PATH", "./governance/schemas"
            ),
            log_level=_env("LOG_LEVEL", "INFO"),
            max_inference_retries=_env_int("MAX_INFERENCE_RETRIES", 3),
            inference_timeout=_env_int("INFERENCE_TIMEOUT", 120),
            audit_buffer_size=_env_int("AUDIT_BUFFER_SIZE", 100),
            audit_flush_interval=_env_int("AUDIT_FLUSH_INTERVAL", 5),
        )

        logger.info(
            "Configuration loaded: postgres_host=%s, ollama_host=%s, log_level=%s",
            config.postgres_host,
            config.ollama_host,
            config.log_level,
        )
        return config

    def configure_logging(self) -> None:
        """Configure Python logging from runtime config."""
        level = getattr(logging, self.log_level.upper(), logging.INFO)
        logging.basicConfig(
            level=level,
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        )
        logger.info("Logging configured at level %s", self.log_level)
