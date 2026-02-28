"""
Base connector — abstract interface for all data source connectors.

Connectors are the bridge between FiscalPilot and external financial systems.
They pull data from accounting software, banks, ERPs, spreadsheets, etc. and
normalize it into FiscalPilot's standard FinancialDataset format.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fiscalpilot.models.company import CompanyProfile
    from fiscalpilot.models.financial import FinancialDataset


class BaseConnector(ABC):
    """Abstract base class for all data connectors.

    To create a new connector, subclass this and implement:
    - `name`: Unique connector identifier.
    - `pull()`: Async method that returns a FinancialDataset.
    - `validate_credentials()`: Check if credentials are valid.

    Example::

        class MyERPConnector(BaseConnector):
            name = "my_erp"

            async def pull(self, company: CompanyProfile) -> FinancialDataset:
                # Pull data from your ERP
                ...

            async def validate_credentials(self) -> bool:
                # Check API keys, etc.
                ...
    """

    name: str = "base"
    description: str = "Base connector"

    def __init__(self, credentials: dict[str, Any] | None = None, **options: Any) -> None:
        self.credentials = credentials or {}
        self.options = options

    @abstractmethod
    async def pull(self, company: CompanyProfile) -> FinancialDataset:
        """Pull financial data from the source.

        Args:
            company: Company profile for context.

        Returns:
            Normalized FinancialDataset.
        """
        ...

    @abstractmethod
    async def validate_credentials(self) -> bool:
        """Validate that credentials are correct and the source is accessible."""
        ...

    async def health_check(self) -> dict[str, Any]:
        """Check connector health and connectivity."""
        try:
            valid = await self.validate_credentials()
            return {"connector": self.name, "healthy": valid, "error": None}
        except Exception as e:
            return {"connector": self.name, "healthy": False, "error": str(e)}
