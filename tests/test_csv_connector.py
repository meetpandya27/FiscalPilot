"""Tests for the CSV connector."""

import tempfile
from pathlib import Path

import pytest

from fiscalpilot.connectors.csv_connector import CSVConnector
from fiscalpilot.models.company import CompanyProfile
from fiscalpilot.models.financial import TransactionType


SAMPLE_CSV = """date,amount,description,category,vendor
2025-01-01,-500.00,Office rent,Rent,Landlord Inc
2025-01-02,2000.00,Client payment,Income,Acme Corp
2025-01-03,-89.99,Software subscription,Software,Zoom
2025-01-04,-45.00,Office supplies,Supplies,Staples
2025-01-05,1500.00,Consulting fee,Income,BigCo
2025-01-05,-89.99,Software subscription,Software,Zoom
"""


@pytest.fixture
def csv_file(tmp_path: Path) -> str:
    """Create a temporary CSV file."""
    file = tmp_path / "test_transactions.csv"
    file.write_text(SAMPLE_CSV)
    return str(file)


@pytest.fixture
def company() -> CompanyProfile:
    return CompanyProfile(name="Test Company")


class TestCSVConnector:
    @pytest.mark.asyncio
    async def test_pull_csv(self, csv_file: str, company: CompanyProfile) -> None:
        connector = CSVConnector(file_path=csv_file)
        dataset = await connector.pull(company)

        assert len(dataset.transactions) == 6
        assert dataset.source.startswith("csv:")

    @pytest.mark.asyncio
    async def test_expense_income_detection(self, csv_file: str, company: CompanyProfile) -> None:
        connector = CSVConnector(file_path=csv_file)
        dataset = await connector.pull(company)

        expenses = [t for t in dataset.transactions if t.is_expense]
        income = [t for t in dataset.transactions if t.is_income]

        assert len(expenses) == 4
        assert len(income) == 2

    @pytest.mark.asyncio
    async def test_period_detection(self, csv_file: str, company: CompanyProfile) -> None:
        connector = CSVConnector(file_path=csv_file)
        dataset = await connector.pull(company)

        assert dataset.period_start is not None
        assert dataset.period_end is not None
        assert dataset.period_start <= dataset.period_end

    @pytest.mark.asyncio
    async def test_category_mapping(self, csv_file: str, company: CompanyProfile) -> None:
        connector = CSVConnector(file_path=csv_file)
        dataset = await connector.pull(company)

        categories = [t.category for t in dataset.transactions if t.category]
        assert len(categories) > 0

    @pytest.mark.asyncio
    async def test_validate_credentials(self, csv_file: str) -> None:
        connector = CSVConnector(file_path=csv_file)
        assert await connector.validate_credentials()

    @pytest.mark.asyncio
    async def test_missing_file(self) -> None:
        connector = CSVConnector(file_path="/nonexistent/file.csv")
        assert not await connector.validate_credentials()

    @pytest.mark.asyncio
    async def test_missing_file_pull(self, company: CompanyProfile) -> None:
        connector = CSVConnector(file_path="/nonexistent/file.csv")
        with pytest.raises(FileNotFoundError):
            await connector.pull(company)
