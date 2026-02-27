"""Tests for the connector registry."""

import pytest

from fiscalpilot.config import ConnectorConfig, FiscalPilotConfig
from fiscalpilot.connectors.base import BaseConnector
from fiscalpilot.connectors.registry import ConnectorRegistry
from fiscalpilot.models.company import CompanyProfile
from fiscalpilot.models.financial import FinancialDataset


class MockConnector(BaseConnector):
    """A simple mock connector for testing."""

    name = "mock"
    description = "Mock connector"

    async def pull(self, company: CompanyProfile) -> FinancialDataset:
        return FinancialDataset(source="mock")

    async def validate_credentials(self) -> bool:
        return True


class TestConnectorRegistry:
    def test_register_connector(self) -> None:
        registry = ConnectorRegistry()
        connector = MockConnector()
        registry.register(connector)

        assert len(registry) == 1
        assert registry.get("mock") is connector

    def test_active_connectors(self) -> None:
        registry = ConnectorRegistry()
        registry.register(MockConnector())

        assert len(registry.active_connectors) == 1

    def test_get_nonexistent(self) -> None:
        registry = ConnectorRegistry()
        assert registry.get("nonexistent") is None

    def test_auto_discover_csv(self, tmp_path) -> None:
        # Create a temp CSV
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("date,amount\n2025-01-01,100")

        config = FiscalPilotConfig(
            connectors=[
                ConnectorConfig(type="csv", options={"file_path": str(csv_file)})
            ]
        )

        registry = ConnectorRegistry()
        registry.auto_discover(config)

        assert len(registry) == 1

    def test_disabled_connector_skipped(self) -> None:
        config = FiscalPilotConfig(
            connectors=[
                ConnectorConfig(type="csv", enabled=False, options={"file_path": "test.csv"})
            ]
        )

        registry = ConnectorRegistry()
        registry.auto_discover(config)

        assert len(registry) == 0
