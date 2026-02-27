"""
CSV Connector — import financial data from CSV files.

This is the simplest connector and the easiest way to get started.
Supports any CSV with date, amount, description columns.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from fiscalpilot.connectors.base import BaseConnector
from fiscalpilot.models.company import CompanyProfile
from fiscalpilot.models.financial import (
    ExpenseCategory,
    FinancialDataset,
    Transaction,
    TransactionType,
)

logger = logging.getLogger("fiscalpilot.connectors.csv")

# Common column name mappings
_COLUMN_ALIASES: dict[str, list[str]] = {
    "date": ["date", "transaction_date", "txn_date", "posted_date", "posting_date", "trans_date"],
    "amount": ["amount", "total", "value", "debit", "credit", "sum", "net_amount"],
    "description": ["description", "memo", "narrative", "details", "note", "reference", "desc"],
    "category": ["category", "type", "expense_type", "account", "gl_code", "classification"],
    "vendor": ["vendor", "payee", "merchant", "supplier", "from", "paid_to", "company"],
}


class CSVConnector(BaseConnector):
    """Import financial data from CSV files.

    Usage::

        connector = CSVConnector(file_path="transactions.csv")
        dataset = await connector.pull(company_profile)

    Supports automatic column detection and type inference.
    """

    name = "csv"
    description = "Import financial data from CSV files"

    def __init__(
        self,
        credentials: dict[str, Any] | None = None,
        file_path: str | None = None,
        **options: Any,
    ) -> None:
        super().__init__(credentials, **options)
        # file_path can come from: direct param, options, or credentials
        creds = credentials or {}
        self.file_path = (
            file_path
            or options.get("file_path")
            or creds.get("file_path", "")
        )
        self.encoding = options.get("encoding", "utf-8")
        self.delimiter = options.get("delimiter", ",")

    async def pull(self, company: CompanyProfile) -> FinancialDataset:
        """Read and parse the CSV file into a FinancialDataset."""
        path = Path(self.file_path)
        if not path.exists():
            raise FileNotFoundError(f"CSV file not found: {self.file_path}")

        df = pd.read_csv(path, encoding=self.encoding, delimiter=self.delimiter)
        df.columns = df.columns.str.strip().str.lower()

        # Map columns
        col_map = self._detect_columns(df)
        transactions = self._parse_transactions(df, col_map)

        dataset = FinancialDataset(
            transactions=transactions,
            source=f"csv:{path.name}",
        )

        if transactions:
            dates = [t.date for t in transactions]
            dataset.period_start = min(dates)
            dataset.period_end = max(dates)

        logger.info("Parsed %d transactions from %s", len(transactions), path.name)
        return dataset

    async def validate_credentials(self) -> bool:
        """Check if the CSV file exists and is readable."""
        path = Path(self.file_path)
        return path.exists() and path.is_file()

    def _detect_columns(self, df: pd.DataFrame) -> dict[str, str]:
        """Auto-detect column mappings from the DataFrame."""
        col_map: dict[str, str] = {}
        df_cols = set(df.columns)

        for field, aliases in _COLUMN_ALIASES.items():
            for alias in aliases:
                if alias in df_cols:
                    col_map[field] = alias
                    break

        return col_map

    def _parse_transactions(
        self, df: pd.DataFrame, col_map: dict[str, str]
    ) -> list[Transaction]:
        """Convert DataFrame rows to Transaction objects."""
        transactions: list[Transaction] = []

        date_col = col_map.get("date")
        amount_col = col_map.get("amount")
        desc_col = col_map.get("description")
        cat_col = col_map.get("category")
        vendor_col = col_map.get("vendor")

        if not date_col or not amount_col:
            logger.warning("CSV missing required columns (date, amount)")
            return transactions

        for _, row in df.iterrows():
            try:
                # Parse date
                raw_date = row[date_col]
                if isinstance(raw_date, str):
                    txn_date = pd.to_datetime(raw_date).date()
                elif isinstance(raw_date, (datetime, date)):
                    txn_date = raw_date if isinstance(raw_date, date) else raw_date.date()
                else:
                    continue

                # Parse amount
                amount = float(row[amount_col])

                # Determine type
                txn_type = TransactionType.EXPENSE if amount < 0 else TransactionType.INCOME
                amount = abs(amount)

                # Build transaction
                txn = Transaction(
                    date=txn_date,
                    amount=amount,
                    type=txn_type,
                    description=str(row.get(desc_col, "")) if desc_col else "",
                    vendor=str(row.get(vendor_col, "")) if vendor_col else None,
                    category=self._map_category(str(row.get(cat_col, ""))) if cat_col else None,
                    raw_data=row.to_dict(),
                )
                transactions.append(txn)
            except Exception as e:
                logger.debug("Skipping row: %s", e)

        return transactions

    def _map_category(self, raw_category: str) -> ExpenseCategory | None:
        """Map raw category strings to standardized categories."""
        if not raw_category or raw_category == "nan":
            return None

        raw_lower = raw_category.lower()
        mapping: dict[str, ExpenseCategory] = {
            "payroll": ExpenseCategory.PAYROLL,
            "salary": ExpenseCategory.PAYROLL,
            "wages": ExpenseCategory.PAYROLL,
            "rent": ExpenseCategory.RENT,
            "lease": ExpenseCategory.RENT,
            "utility": ExpenseCategory.UTILITIES,
            "utilities": ExpenseCategory.UTILITIES,
            "electric": ExpenseCategory.UTILITIES,
            "gas": ExpenseCategory.UTILITIES,
            "water": ExpenseCategory.UTILITIES,
            "insurance": ExpenseCategory.INSURANCE,
            "software": ExpenseCategory.SOFTWARE,
            "saas": ExpenseCategory.SOFTWARE,
            "subscription": ExpenseCategory.SUBSCRIPTIONS,
            "marketing": ExpenseCategory.MARKETING,
            "advertising": ExpenseCategory.MARKETING,
            "travel": ExpenseCategory.TRAVEL,
            "meals": ExpenseCategory.MEALS,
            "food": ExpenseCategory.MEALS,
            "supplies": ExpenseCategory.SUPPLIES,
            "office": ExpenseCategory.SUPPLIES,
            "inventory": ExpenseCategory.INVENTORY,
            "cogs": ExpenseCategory.INVENTORY,
            "cost of goods": ExpenseCategory.INVENTORY,
            "food": ExpenseCategory.INVENTORY,
            "beverage": ExpenseCategory.INVENTORY,
            "shipping": ExpenseCategory.SHIPPING,
            "freight": ExpenseCategory.SHIPPING,
            "tax": ExpenseCategory.TAXES,
            "equipment": ExpenseCategory.EQUIPMENT,
            "maintenance": ExpenseCategory.MAINTENANCE,
            "repair": ExpenseCategory.MAINTENANCE,
            "miscellaneous": ExpenseCategory.MISCELLANEOUS,
        }

        for keyword, category in mapping.items():
            if keyword in raw_lower:
                return category

        return ExpenseCategory.OTHER
