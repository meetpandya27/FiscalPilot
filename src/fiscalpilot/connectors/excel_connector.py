"""
Excel Connector — import financial data from Excel (xlsx/xls) files.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from fiscalpilot.connectors.csv_connector import CSVConnector
from fiscalpilot.models.company import CompanyProfile
from fiscalpilot.models.financial import FinancialDataset

logger = logging.getLogger("fiscalpilot.connectors.excel")


class ExcelConnector(CSVConnector):
    """Import financial data from Excel files.

    Inherits column detection and parsing logic from CSVConnector.

    Usage::

        connector = ExcelConnector(file_path="financials.xlsx", sheet_name="Transactions")
        dataset = await connector.pull(company_profile)
    """

    name = "excel"
    description = "Import financial data from Excel files"

    def __init__(
        self,
        credentials: dict[str, Any] | None = None,
        file_path: str | None = None,
        sheet_name: str | int = 0,
        **options: Any,
    ) -> None:
        super().__init__(credentials, file_path=file_path, **options)
        self.sheet_name = sheet_name

    async def pull(self, company: CompanyProfile) -> FinancialDataset:
        """Read and parse the Excel file into a FinancialDataset."""
        path = Path(self.file_path)
        if not path.exists():
            raise FileNotFoundError(f"Excel file not found: {self.file_path}")

        df = pd.read_excel(path, sheet_name=self.sheet_name, engine="openpyxl")
        df.columns = df.columns.str.strip().str.lower()

        col_map = self._detect_columns(df)
        transactions = self._parse_transactions(df, col_map)

        dataset = FinancialDataset(
            transactions=transactions,
            source=f"excel:{path.name}",
        )

        if transactions:
            dates = [t.date for t in transactions]
            dataset.period_start = min(dates)
            dataset.period_end = max(dates)

        logger.info("Parsed %d transactions from %s", len(transactions), path.name)
        return dataset
