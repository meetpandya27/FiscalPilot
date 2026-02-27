"""
Plaid Connector — pull bank transaction data via Plaid API.

Requires the `plaid` optional dependency:
    pip install fiscalpilot[plaid]
"""

from __future__ import annotations

import logging
from typing import Any

from fiscalpilot.connectors.base import BaseConnector
from fiscalpilot.models.company import CompanyProfile
from fiscalpilot.models.financial import FinancialDataset

logger = logging.getLogger("fiscalpilot.connectors.plaid")


class PlaidConnector(BaseConnector):
    """Pull bank transaction data via Plaid.

    Requires Plaid credentials (client_id, secret, access_token).

    Usage::

        connector = PlaidConnector(credentials={
            "client_id": "...",
            "secret": "...",
            "access_token": "...",
        })
        dataset = await connector.pull(company_profile)
    """

    name = "plaid"
    description = "Pull bank transaction data via Plaid API"

    async def pull(self, company: CompanyProfile) -> FinancialDataset:
        """Pull transactions from Plaid.

        Scaffold for community contributors to implement using plaid-python SDK.
        """
        try:
            import plaid  # noqa: F401
        except ImportError:
            raise ImportError(
                "Plaid connector requires plaid-python. "
                "Install with: pip install fiscalpilot[plaid]"
            )

        logger.info("Plaid connector: scaffold — contribute at github.com/fiscalpilot/fiscalpilot")
        return FinancialDataset(source="plaid")

    async def validate_credentials(self) -> bool:
        return bool(self.credentials.get("client_id") and self.credentials.get("access_token"))
