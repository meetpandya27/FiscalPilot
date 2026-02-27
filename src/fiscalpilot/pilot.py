"""
FiscalPilot — Main orchestrator.

The FiscalPilot class is the top-level entry point that coordinates
all agents, connectors, and analyzers to perform a comprehensive
financial audit of any business.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from fiscalpilot.agents.coordinator import CoordinatorAgent
from fiscalpilot.config import FiscalPilotConfig
from fiscalpilot.connectors.registry import ConnectorRegistry
from fiscalpilot.models.company import CompanyProfile
from fiscalpilot.models.report import AuditReport

logger = logging.getLogger("fiscalpilot")


@dataclass
class FiscalPilot:
    """Top-level orchestrator for the FiscalPilot system.

    Usage::

        from fiscalpilot import FiscalPilot

        pilot = FiscalPilot.from_config("fiscalpilot.yaml")
        report = await pilot.audit(company_profile)
        report.to_pdf("audit.pdf")

    The FiscalPilot coordinates:
    - **Connectors**: Pull data from accounting systems, banks, ERPs.
    - **Analyzers**: Detect cost optimization, risk, and savings opportunities.
    - **Agents**: LLM-powered agents that reason about financial data.
    - **Reports**: Generate actionable executive-ready reports.
    """

    config: FiscalPilotConfig
    connector_registry: ConnectorRegistry = field(default_factory=ConnectorRegistry)
    _coordinator: CoordinatorAgent | None = field(default=None, init=False, repr=False)

    @classmethod
    def from_config(cls, config_path: str | None = None, **overrides: Any) -> FiscalPilot:
        """Create a FiscalPilot instance from a config file or keyword arguments."""
        config = FiscalPilotConfig.load(config_path, **overrides)
        instance = cls(config=config)
        instance._setup()
        return instance

    def _setup(self) -> None:
        """Initialize connectors, agents, and analyzers."""
        self.connector_registry = ConnectorRegistry()
        self.connector_registry.auto_discover(self.config)
        self._coordinator = CoordinatorAgent(
            config=self.config,
            connectors=self.connector_registry,
        )
        logger.info(
            "FiscalPilot initialized with %d connectors",
            len(self.connector_registry),
        )

    async def audit(self, company: CompanyProfile) -> AuditReport:
        """Run a full financial audit on the given company.

        This is the main entry point. It will:
        1. Pull data from all configured connectors.
        2. Run cost optimization and risk detection analyzers.
        3. Identify cost-cutting and margin-improvement opportunities.
        4. Generate an actionable report with recommendations and proposed actions.

        Args:
            company: Company profile with metadata about the business.

        Returns:
            AuditReport with findings, savings opportunities, and action items.
        """
        if self._coordinator is None:
            self._setup()
        assert self._coordinator is not None
        logger.info("Starting audit for %s", company.name)
        report = await self._coordinator.run_audit(company)
        logger.info(
            "Audit complete: %d findings, $%.2f potential savings",
            len(report.findings),
            report.total_potential_savings,
        )
        return report

    def audit_sync(self, company: CompanyProfile) -> AuditReport:
        """Synchronous wrapper around :meth:`audit`."""
        return asyncio.run(self.audit(company))

    async def quick_scan(self, company: CompanyProfile) -> AuditReport:
        """Run a lightweight scan (no deep analysis) — great for demos."""
        if self._coordinator is None:
            self._setup()
        assert self._coordinator is not None
        return await self._coordinator.run_quick_scan(company)
