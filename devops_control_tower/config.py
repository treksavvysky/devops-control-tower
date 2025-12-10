"""
Configuration management for DevOps Control Tower.
"""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Application
    app_name: str = Field(default="DevOps Control Tower", env="APP_NAME")
    debug: bool = Field(default=False, env="DEBUG")
    environment: str = Field(default="development", env="ENVIRONMENT")

    # API
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8000, env="API_PORT")
    api_workers: int = Field(default=1, env="API_WORKERS")

    # Database
    database_url: str = Field(
        default="sqlite:///./devops_control_tower.db", env="DATABASE_URL"
    )

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")

    # Security
    secret_key: str = Field(default="your-secret-key-here", env="SECRET_KEY")
    access_token_expire_minutes: int = Field(
        default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES"
    )

    # Monitoring
    enable_metrics: bool = Field(default=True, env="ENABLE_METRICS")
    metrics_port: int = Field(default=9090, env="METRICS_PORT")

    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="json", env="LOG_FORMAT")

    # AI Configuration
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")

    # Agent Configuration
    max_concurrent_agents: int = Field(default=10, env="MAX_CONCURRENT_AGENTS")
    agent_heartbeat_interval: int = Field(default=30, env="AGENT_HEARTBEAT_INTERVAL")
    agent_timeout_seconds: int = Field(default=300, env="AGENT_TIMEOUT_SECONDS")

    # Workflow Configuration
    max_concurrent_workflows: int = Field(default=5, env="MAX_CONCURRENT_WORKFLOWS")
    workflow_timeout_seconds: int = Field(default=3600, env="WORKFLOW_TIMEOUT_SECONDS")

    # Event Processing
    event_batch_size: int = Field(default=100, env="EVENT_BATCH_SIZE")
    event_processing_interval: int = Field(default=5, env="EVENT_PROCESSING_INTERVAL")

    # Policy Configuration
    jct_allowed_repo_prefixes: str = Field(
        default="",
        env="JCT_ALLOWED_REPO_PREFIXES",
        description="Comma-separated list of allowed repository namespace prefixes (e.g., 'myorg/,anotherorg/'). Empty string = deny all.",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings."""
    return settings
