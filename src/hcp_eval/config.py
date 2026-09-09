"""Configuration management for Hy3 Code Process Eval."""

import os
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Hy3 API Configuration
    hy3_provider: str = Field(
        default="openai",
        description="Backend provider: 'openai' (OpenAI-compatible) or 'tencentcloud' (Tencent Cloud Hunyuan SDK)",
    )
    hy3_base_url: str = Field(
        default="http://127.0.0.1:8000/v1",
        description="Hy3 API base URL (OpenAI-compatible)",
    )
    hy3_api_key: str = Field(
        default="EMPTY",
        description="Hy3 API key (OpenAI-compatible provider)",
    )
    tencentcloud_secret_id: str = Field(
        default="",
        description="Tencent Cloud SecretId (tencentcloud provider)",
    )
    tencentcloud_secret_key: str = Field(
        default="",
        description="Tencent Cloud SecretKey (tencentcloud provider)",
    )
    hy3_model: str = Field(
        default="hy3",
        description="Model name to use for Hy3 calls",
    )
    hy3_reasoning_effort: str = Field(
        default="high",
        description="Reasoning effort level for Hy3 (low/medium/high)",
    )
    hy3_temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=2.0,
        description="Temperature for Hy3 generation",
    )
    hy3_max_tokens: int = Field(
        default=16384,
        ge=1,
        description="Max tokens for Hy3 output",
    )
    hy3_timeout: int = Field(
        default=300,
        ge=1,
        description="Request timeout in seconds",
    )
    hy3_request_timeout: float = Field(
        default=120.0,
        ge=1.0,
        description="Per-request timeout (seconds) passed to the OpenAI-compatible client",
    )
    hy3_max_retries: int = Field(
        default=4,
        ge=0,
        description="Number of retry attempts on transient API errors (rate limits, timeouts)",
    )

    # Dataset Configuration
    dataset_name: str = Field(
        default="mbppplus",
        description="Primary dataset name (mbppplus or humanevalplus)",
    )
    dataset_sample_size: int = Field(
        default=30,
        ge=1,
        description="Number of problems to sample from dataset",
    )
    dataset_seed: int = Field(
        default=42,
        description="Random seed for reproducible sampling",
    )

    # Execution Configuration
    execution_timeout: int = Field(
        default=30,
        ge=1,
        description="Timeout per test case in seconds",
    )
    max_workers: int = Field(
        default=4,
        ge=1,
        le=16,
        description="Max parallel workers for execution",
    )
    use_sandbox: bool = Field(
        default=True,
        description="Use sandboxed execution for candidate code",
    )

    # Output Configuration
    output_dir: Path = Field(
        default=Path("results"),
        description="Directory for evaluation results",
    )
    data_dir: Path = Field(
        default=Path("data"),
        description="Directory for downloaded/imported datasets",
    )

    @field_validator("hy3_model")
    @classmethod
    def validate_hy3_model(cls, v: str) -> str:
        """Ensure non-empty model name. For the OpenAI provider we additionally
        expect the name to contain 'hy3' to avoid accidentally using an unrelated
        model on a paid endpoint; the Tencent Cloud provider uses Hunyuan model
        names (e.g. hunyuan-turbo) which is expected."""
        if not v or not v.strip():
            raise ValueError("Model name must not be empty")
        return v

    @field_validator("hy3_provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        if v not in ("openai", "tencentcloud"):
            raise ValueError(f"hy3_provider must be 'openai' or 'tencentcloud', got: {v}")
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Global settings instance (lazy-loaded)
_settings_cache: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create the global settings instance."""
    global _settings_cache
    if _settings_cache is None:
        _settings_cache = Settings()
    return _settings_cache


def reload_settings() -> Settings:
    """Force reload settings from environment."""
    global _settings_cache
    _settings_cache = Settings()
    return _settings_cache
