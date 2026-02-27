"""Tests for configuration management."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from fiscalpilot.config import FiscalPilotConfig


class TestConfig:
    def test_default_config(self) -> None:
        config = FiscalPilotConfig()
        assert config.llm.model == "gpt-4o"
        assert config.llm.temperature == 0.1
        assert config.security.encrypt_at_rest is True
        assert config.analyzers.cost_optimization is True
        assert config.analyzers.risk_detection is True

    def test_load_from_yaml(self, tmp_path: Path) -> None:
        yaml_content = {
            "llm": {"model": "claude-sonnet-4-20250514", "temperature": 0.2},
            "connectors": [{"type": "csv", "options": {"file_path": "data.csv"}}],
            "security": {"local_only": True},
        }
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(yaml.dump(yaml_content))

        config = FiscalPilotConfig.load(str(config_file))
        assert config.llm.model == "claude-sonnet-4-20250514"
        assert config.llm.temperature == 0.2
        assert config.security.local_only is True
        assert len(config.connectors) == 1

    def test_load_with_overrides(self) -> None:
        config = FiscalPilotConfig.load(
            None,
            llm={"model": "ollama/llama3.1"},
            currency="EUR",
        )
        assert config.llm.model == "ollama/llama3.1"
        assert config.currency == "EUR"

    def test_env_var_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FISCALPILOT_MODEL", "gpt-4-turbo")
        monkeypatch.setenv("FISCALPILOT_API_KEY", "test-key-123")

        config = FiscalPilotConfig.load()
        assert config.llm.model == "gpt-4-turbo"
        assert config.llm.api_key == "test-key-123"

    def test_local_only_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FISCALPILOT_LOCAL_ONLY", "true")
        config = FiscalPilotConfig.load()
        assert config.security.local_only is True

    def test_missing_config_file(self) -> None:
        config = FiscalPilotConfig.load("/nonexistent/config.yaml")
        # Should use defaults without error
        assert config.llm.model == "gpt-4o"
