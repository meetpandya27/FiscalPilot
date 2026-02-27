"""
QuickBooks Connector — pull data from QuickBooks Online.

Requires the `quickbooks` optional dependency:
    pip install fiscalpilot[quickbooks]
"""

from __future__ import annotations

import logging
from typing import Any

from fiscalpilot.connectors.base import BaseConnector
from fiscalpilot.models.company import CompanyProfile
from fiscalpilot.models.financial import FinancialDataset

logger = logging.getLogger("fiscalpilot.connectors.quickbooks")


class QuickBooksConnector(BaseConnector):
    """Pull financial data from QuickBooks Online.

    Requires OAuth2 credentials (client_id, client_secret, refresh_token, realm_id).

    Usage::

        connector = QuickBooksConnector(credentials={
            "client_id": "...",
            "client_secret": "...",
            "refresh_token": "...",
            "realm_id": "...",
        })
        dataset = await connector.pull(company_profile)
    """

    name = "quickbooks"
    description = "Pull financial data from QuickBooks Online"

    def __init__(self, credentials: dict[str, Any] | None = None, **options: Any) -> None:
        super().__init__(credentials, **options)
        self.client_id = (credentials or {}).get("client_id", "")
        self.client_secret = (credentials or {}).get("client_secret", "")
        self.refresh_token = (credentials or {}).get("refresh_token", "")
        self.realm_id = (credentials or {}).get("realm_id", "")

    async def pull(self, company: CompanyProfile) -> FinancialDataset:
        """Pull transactions, invoices, and balances from QuickBooks.

        This is a scaffold — community contributors can implement the full
        QuickBooks API integration using python-quickbooks.
        """
        try:
            from quickbooks import QuickBooks
            from quickbooks.objects.purchase import Purchase
        except ImportError:
            raise ImportError(
                "QuickBooks connector requires python-quickbooks. "
                "Install with: pip install fiscalpilot[quickbooks]"
            )

        # TODO: Implement full QuickBooks integration
        # This scaffold shows the expected pattern for contributors
        logger.info("QuickBooks connector: scaffold — contribute at github.com/fiscalpilot/fiscalpilot")
        return FinancialDataset(source="quickbooks")

    async def validate_credentials(self) -> bool:
        """Validate QuickBooks OAuth2 credentials."""
        return bool(self.client_id and self.client_secret and self.refresh_token)
