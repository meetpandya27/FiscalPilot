"""
Connector Registry — discovers and manages all data connectors.

Supports auto-discovery from config and manual registration of custom connectors.
"""

from __future__ import annotations

import logging
from typing import Any

from fiscalpilot.config import ConnectorConfig, FiscalPilotConfig
from fiscalpilot.connectors.base import BaseConnector

logger = logging.getLogger("fiscalpilot.connectors.registry")

# Built-in connector type mapping
_BUILTIN_CONNECTORS: dict[str, str] = {
    "csv": "fiscalpilot.connectors.csv_connector.CSVConnector",
    "excel": "fiscalpilot.connectors.excel_connector.ExcelConnector",
    "sql": "fiscalpilot.connectors.sql_connector.SQLConnector",
    "quickbooks": "fiscalpilot.connectors.quickbooks_connector.QuickBooksConnector",
    "xero": "fiscalpilot.connectors.xero_connector.XeroConnector",
    "plaid": "fiscalpilot.connectors.plaid_connector.PlaidConnector",
}


class ConnectorRegistry:
    """Manages all active data connectors.

    Supports:
    - Auto-discovery from config file.
    - Manual registration of custom connectors.
    - Plugin-style connector loading.
    """

    def __init__(self) -> None:
        self._connectors: dict[str, BaseConnector] = {}

    def __len__(self) -> int:
        return len(self._connectors)

    @property
    def active_connectors(self) -> list[BaseConnector]:
        """Return all active connectors."""
        return list(self._connectors.values())

    def register(self, connector: BaseConnector) -> None:
        """Register a connector instance."""
        self._connectors[connector.name] = connector
        logger.info("Registered connector: %s", connector.name)

    def get(self, name: str) -> BaseConnector | None:
        """Get a connector by name."""
        return self._connectors.get(name)

    def auto_discover(self, config: FiscalPilotConfig) -> None:
        """Auto-discover and register connectors from config."""
        for conn_config in config.connectors:
            if not conn_config.enabled:
                continue
            try:
                connector = self._create_connector(conn_config)
                if connector:
                    self.register(connector)
            except Exception as e:
                logger.error("Failed to create connector '%s': %s", conn_config.type, e)

    def _create_connector(self, config: ConnectorConfig) -> BaseConnector | None:
        """Instantiate a connector from config."""
        connector_path = _BUILTIN_CONNECTORS.get(config.type)
        if not connector_path:
            # Try loading as a fully qualified class path (plugin support)
            connector_path = config.type

        try:
            module_path, class_name = connector_path.rsplit(".", 1)
            import importlib

            module = importlib.import_module(module_path)
            connector_cls = getattr(module, class_name)
            return connector_cls(credentials=config.credentials, **config.options)
        except (ImportError, AttributeError) as e:
            logger.error("Cannot load connector '%s': %s", config.type, e)
            return None
