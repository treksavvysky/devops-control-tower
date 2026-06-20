"""
Configuration management for DevOps Control Tower.
"""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    # Application
    app_name: str = Field(default="DevOps Control Tower", validation_alias="APP_NAME")
    debug: bool = Field(default=False, validation_alias="DEBUG")
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")

    # API
    api_host: str = Field(default="0.0.0.0", validation_alias="API_HOST")
    api_port: int = Field(default=8000, validation_alias="API_PORT")
    api_workers: int = Field(default=1, validation_alias="API_WORKERS")

    # Database
    database_url: str = Field(
        default="sqlite:///./devops_control_tower.db", validation_alias="DATABASE_URL"
    )

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")

    # Security
    secret_key: str = Field(default="your-secret-key-here", validation_alias="SECRET_KEY")
    access_token_expire_minutes: int = Field(
        default=30, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES"
    )

    # Monitoring
    enable_metrics: bool = Field(default=True, validation_alias="ENABLE_METRICS")
    metrics_port: int = Field(default=9090, validation_alias="METRICS_PORT")

    # Logging
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    log_format: str = Field(default="json", validation_alias="LOG_FORMAT")

    # AI Configuration
    openai_api_key: Optional[str] = Field(default=None, validation_alias="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, validation_alias="ANTHROPIC_API_KEY")

    # Agent Configuration
    max_concurrent_agents: int = Field(default=10, validation_alias="MAX_CONCURRENT_AGENTS")
    agent_heartbeat_interval: int = Field(default=30, validation_alias="AGENT_HEARTBEAT_INTERVAL")
    agent_timeout_seconds: int = Field(default=300, validation_alias="AGENT_TIMEOUT_SECONDS")

    # Workflow Configuration
    max_concurrent_workflows: int = Field(default=5, validation_alias="MAX_CONCURRENT_WORKFLOWS")
    workflow_timeout_seconds: int = Field(default=3600, validation_alias="WORKFLOW_TIMEOUT_SECONDS")

    # Event Processing
    event_batch_size: int = Field(default=100, validation_alias="EVENT_BATCH_SIZE")
    event_processing_interval: int = Field(default=5, validation_alias="EVENT_PROCESSING_INTERVAL")

    # Policy Configuration
    jct_allowed_repo_prefixes: str = Field(
        default="",
        validation_alias="JCT_ALLOWED_REPO_PREFIXES",
        description="Comma-separated list of allowed repository namespace prefixes (e.g., 'myorg/,anotherorg/'). Empty string = deny all.",
    )

    # Worker Configuration
    jct_trace_root: str = Field(
        default="file:///var/lib/jct/runs",
        validation_alias="JCT_TRACE_ROOT",
        description="URI for trace storage root. Supports file:// (v0) and s3:// (v2).",
    )
    worker_poll_interval: int = Field(
        default=5,
        validation_alias="WORKER_POLL_INTERVAL",
        description="Seconds between polling for queued tasks.",
    )
    worker_claim_limit: int = Field(
        default=1,
        validation_alias="WORKER_CLAIM_LIMIT",
        description="Number of tasks to claim per poll cycle.",
    )

    # ChatGPT Actions Integration
    jct_api_key: Optional[str] = Field(
        default=None,
        validation_alias="JCT_API_KEY",
        description="Static API key for external integrations (ChatGPT Actions). If unset, auth is disabled.",
    )
    jct_api_base_url: str = Field(
        default="http://localhost:8000",
        validation_alias="JCT_API_BASE_URL",
        description="Public base URL for OpenAPI spec (used by ChatGPT Actions).",
    )

    # Review Configuration (Step 5: Review → Merge Gate)
    jct_review_auto_approve: bool = Field(
        default=False,
        validation_alias="JCT_REVIEW_AUTO_APPROVE",
        description="Enable auto-approval of passing evidence packs.",
    )
    jct_review_auto_approve_verdicts: str = Field(
        default="pass",
        validation_alias="JCT_REVIEW_AUTO_APPROVE_VERDICTS",
        description="Comma-separated verdicts that qualify for auto-approval.",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra env vars not defined in Settings
        populate_by_name=True,
    )


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings.

    Returns the module-level ``settings`` instance. To override in tests,
    patch ``config.settings`` directly.
    """
    return settings


def reset_settings() -> Settings:
    """Force re-creation of settings from current environment.

    Useful when environment variables change after initial import
    (e.g., in MCP server processes).
    """
    global settings
    settings = Settings()
    return settings
