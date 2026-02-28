"""
SQL Connector — pull financial data from any SQL database.

Works with PostgreSQL, MySQL, SQLite, SQL Server, etc. via SQLAlchemy.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import pandas as pd
from sqlalchemy import create_engine, text

from fiscalpilot.connectors.csv_connector import CSVConnector
from fiscalpilot.models.financial import FinancialDataset

if TYPE_CHECKING:
    from fiscalpilot.models.company import CompanyProfile

logger = logging.getLogger("fiscalpilot.connectors.sql")


class SQLConnector(CSVConnector):
    """Pull financial data from a SQL database.

    Uses SQLAlchemy for broad database compatibility.

    Usage::

        connector = SQLConnector(
            credentials={"connection_string": "postgresql://..."},
            query="SELECT * FROM transactions WHERE date >= '2024-01-01'"
        )
        dataset = await connector.pull(company_profile)
    """

    name = "sql"
    description = "Pull financial data from SQL databases"

    def __init__(
        self,
        credentials: dict[str, Any] | None = None,
        query: str | None = None,
        **options: Any,
    ) -> None:
        super().__init__(credentials, **options)
        self.connection_string = (credentials or {}).get("connection_string", "")
        self.query = query or options.get("query", "SELECT * FROM transactions")

    async def pull(self, company: CompanyProfile) -> FinancialDataset:
        """Execute query and parse results into a FinancialDataset."""
        engine = create_engine(self.connection_string)

        with engine.connect() as conn:
            df = pd.read_sql(text(self.query), conn)

        df.columns = df.columns.str.strip().str.lower()
        col_map = self._detect_columns(df)
        transactions = self._parse_transactions(df, col_map)

        dataset = FinancialDataset(
            transactions=transactions,
            source=f"sql:{engine.url.database or 'db'}",
        )

        if transactions:
            dates = [t.date for t in transactions]
            dataset.period_start = min(dates)
            dataset.period_end = max(dates)

        logger.info("Pulled %d transactions from SQL", len(transactions))
        return dataset

    async def validate_credentials(self) -> bool:
        """Test database connectivity."""
        try:
            engine = create_engine(self.connection_string)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
