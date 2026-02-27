"""
FiscalPilot configuration management.

Supports loading from YAML files, environment variables, and keyword overrides.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    """LLM provider configuration (powered by litellm)."""

    model: str = Field(default="gpt-4o", description="Model identifier (litellm format)")
    api_key: str | None = Field(default=None, description="API key (or set env var)")
    api_base: str | None = Field(default=None, description="Custom API base URL")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1)
    timeout: int = Field(default=120, description="Request timeout in seconds")


class ConnectorConfig(BaseModel):
    """Configuration for a single data connector."""

    type: str = Field(description="Connector type: csv, quickbooks, xero, plaid, sql, etc.")
    enabled: bool = True
    credentials: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)


class AnalyzerConfig(BaseModel):
    """Configuration for analyzer modules."""

    waste_detection: bool = True
    fraud_detection: bool = True
    margin_optimization: bool = True
    cost_reduction: bool = True
    revenue_leakage: bool = True
    compliance_check: bool = True
    vendor_analysis: bool = True
    subscription_audit: bool = True


class SecurityConfig(BaseModel):
    """Security and privacy settings."""

    encrypt_at_rest: bool = Field(default=True, description="Encrypt stored data")
    redact_pii: bool = Field(default=True, description="Redact personally identifiable info")
    audit_log: bool = Field(default=True, description="Log all operations")
    local_only: bool = Field(
        default=False,
        description="Never send data to external APIs (use local LLM only)",
    )


class FiscalPilotConfig(BaseModel):
    """Root configuration for FiscalPilot."""

    llm: LLMConfig = Field(default_factory=LLMConfig)
    connectors: list[ConnectorConfig] = Field(default_factory=list)
    analyzers: AnalyzerConfig = Field(default_factory=AnalyzerConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)

    # Output settings
    output_dir: str = Field(default="./fiscalpilot_reports")
    currency: str = Field(default="USD")
    locale: str = Field(default="en_US")

    @classmethod
    def load(cls, config_path: str | None = None, **overrides: Any) -> FiscalPilotConfig:
        """Load configuration from file, env vars, and overrides.

        Priority: overrides > env vars > config file > defaults.
        """
        data: dict[str, Any] = {}

        # 1. Load from YAML file if provided
        if config_path:
            path = Path(config_path)
            if path.exists():
                with open(path) as f:
                    data = yaml.safe_load(f) or {}

        # 2. Override from environment variables
        env_model = os.environ.get("FISCALPILOT_MODEL")
        env_key = os.environ.get("FISCALPILOT_API_KEY") or os.environ.get("OPENAI_API_KEY")
        env_base = os.environ.get("FISCALPILOT_API_BASE")
        env_local = os.environ.get("FISCALPILOT_LOCAL_ONLY")

        if env_model or env_key or env_base:
            llm = data.get("llm", {})
            if env_model:
                llm["model"] = env_model
            if env_key:
                llm["api_key"] = env_key
            if env_base:
                llm["api_base"] = env_base
            data["llm"] = llm

        if env_local and env_local.lower() in ("1", "true", "yes"):
            security = data.get("security", {})
            security["local_only"] = True
            data["security"] = security

        # 3. Apply keyword overrides
        data.update(overrides)

        return cls.model_validate(data)
