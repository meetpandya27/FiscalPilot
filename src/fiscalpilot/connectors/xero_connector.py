"""
Xero Connector — pull data from Xero accounting.

Requires the `xero` optional dependency:
    pip install fiscalpilot[xero]
"""

from __future__ import annotations

import logging
from typing import Any

from fiscalpilot.connectors.base import BaseConnector
from fiscalpilot.models.company import CompanyProfile
from fiscalpilot.models.financial import FinancialDataset

logger = logging.getLogger("fiscalpilot.connectors.xero")


class XeroConnector(BaseConnector):
    """Pull financial data from Xero.

    Requires OAuth2 credentials (client_id, client_secret, tenant_id).

    Usage::

        connector = XeroConnector(credentials={
            "client_id": "...",
            "client_secret": "...",
            "tenant_id": "...",
        })
        dataset = await connector.pull(company_profile)
    """

    name = "xero"
    description = "Pull financial data from Xero accounting"

    async def pull(self, company: CompanyProfile) -> FinancialDataset:
        """Pull transactions from Xero.

        Scaffold for community contributors to implement using xero-python SDK.
        """
        try:
            import xero_python  # noqa: F401
        except ImportError:
            raise ImportError(
                "Xero connector requires xero-python. "
                "Install with: pip install fiscalpilot[xero]"
            )

        logger.info("Xero connector: scaffold — contribute at github.com/fiscalpilot/fiscalpilot")
        return FinancialDataset(source="xero")

    async def validate_credentials(self) -> bool:
        return bool(self.credentials.get("client_id"))
