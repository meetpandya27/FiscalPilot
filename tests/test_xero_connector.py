"""Tests for the Xero connector with mocked API responses."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from fiscalpilot.connectors.xero_connector import XeroConnector
from fiscalpilot.models.company import CompanyProfile, CompanySize, Industry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def company() -> CompanyProfile:
    return CompanyProfile(
        name="Test Corp",
        industry=Industry.SAAS,
        size=CompanySize.SMALL,
    )


@pytest.fixture
def xero_connector() -> XeroConnector:
    return XeroConnector(
        credentials={
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "refresh_token": "test_refresh_token",
            "tenant_id": "abc-def-123",
        },
    )


# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------


MOCK_BANK_TRANSACTION_SPEND = {
    "BankTransactionID": "bt-001",
    "Type": "SPEND",
    "Status": "AUTHORISED",
    "Date": "2025-01-15",
    "Total": 150.00,
    "Contact": {"Name": "Staples"},
    "BankAccount": {"Name": "Business Checking"},
    "LineItems": [
        {
            "Description": "Office supplies",
            "AccountCode": "office expenses",
            "LineAmount": 150.00,
        }
    ],
}

MOCK_BANK_TRANSACTION_RECEIVE = {
    "BankTransactionID": "bt-002",
    "Type": "RECEIVE",
    "Status": "AUTHORISED",
    "Date": "2025-01-20",
    "Total": 8000.00,
    "Contact": {"Name": "Client Corp"},
    "BankAccount": {"Name": "Business Checking"},
    "LineItems": [
        {
            "Description": "Consulting invoice payment",
            "LineAmount": 8000.00,
        }
    ],
}

MOCK_INVOICE_AR = {
    "InvoiceID": "inv-001",
    "InvoiceNumber": "INV-2025-001",
    "Type": "ACCREC",
    "Status": "PAID",
    "Date": "2025-01-05",
    "DueDate": "2025-02-05",
    "Total": 5000.00,
    "AmountPaid": 5000.00,
    "Contact": {"Name": "Widget Co"},
    "Payments": [
        {"Date": "2025-01-25", "Amount": 5000.00},
    ],
    "LineItems": [
        {
            "Description": "Development services",
            "Quantity": 50,
            "UnitAmount": 100.00,
            "LineAmount": 5000.00,
            "AccountCode": "200",
        }
    ],
}

MOCK_INVOICE_AP = {
    "InvoiceID": "inv-002",
    "InvoiceNumber": "BILL-2025-001",
    "Type": "ACCPAY",
    "Status": "AUTHORISED",
    "Date": "2025-01-10",
    "DueDate": "2099-12-10",
    "Total": 2400.00,
    "AmountPaid": 0,
    "Contact": {"Name": "AWS"},
    "Payments": [],
    "LineItems": [
        {
            "Description": "Cloud infrastructure",
            "Quantity": 1,
            "UnitAmount": 2400.00,
            "LineAmount": 2400.00,
            "AccountCode": "software",
        }
    ],
}

MOCK_TRIAL_BALANCE = {
    "Reports": [{
        "ReportName": "TrialBalance",
        "Rows": [
            {
                "RowType": "Section",
                "Title": "Bank Accounts",
                "Rows": [
                    {
                        "RowType": "Row",
                        "Cells": [
                            {"Value": "Business Checking"},
                            {"Value": "50000.00"},
                            {"Value": "0"},
                        ],
                    },
                ],
            },
            {
                "RowType": "Section",
                "Title": "Accounts Receivable",
                "Rows": [
                    {
                        "RowType": "Row",
                        "Cells": [
                            {"Value": "Trade Debtors"},
                            {"Value": "12000.00"},
                            {"Value": "0"},
                        ],
                    },
                ],
            },
        ],
    }],
}

MOCK_CONNECTIONS = [
    {
        "tenantId": "abc-def-123",
        "tenantName": "Test Corp Xero",
        "tenantType": "ORGANISATION",
    },
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestXeroConnector:
    def test_init(self, xero_connector: XeroConnector) -> None:
        assert xero_connector.client_id == "test_client_id"
        assert xero_connector.tenant_id == "abc-def-123"

    def test_parse_xero_date_iso(self) -> None:
        assert XeroConnector._parse_xero_date("2025-01-15") == date(2025, 1, 15)
        assert XeroConnector._parse_xero_date("2025-01-15T10:30:00") == date(2025, 1, 15)

    def test_parse_xero_date_dotnet(self) -> None:
        # .NET JSON date format: /Date(milliseconds+timezone)/
        # 1705276800000 = 2024-01-15T00:00:00 UTC
        result = XeroConnector._parse_xero_date("/Date(1705276800000+0000)/")
        assert result.year == 2024
        assert result.month == 1

    def test_parse_xero_date_empty(self) -> None:
        assert XeroConnector._parse_xero_date("") == date.today()

    def test_category_mapping(self) -> None:
        from fiscalpilot.models.financial import ExpenseCategory

        assert XeroConnector._map_xero_category("rent") == ExpenseCategory.RENT
        assert XeroConnector._map_xero_category("insurance") == ExpenseCategory.INSURANCE
        assert XeroConnector._map_xero_category("salaries") == ExpenseCategory.PAYROLL
        assert XeroConnector._map_xero_category("") is None
        assert XeroConnector._map_xero_category("unknown_thing") == ExpenseCategory.OTHER

    @pytest.mark.asyncio
    async def test_validate_credentials_missing(self) -> None:
        conn = XeroConnector(credentials={})
        result = await conn.validate_credentials()
        assert result is False

    @pytest.mark.asyncio
    async def test_pull_full(self, xero_connector: XeroConnector, company: CompanyProfile) -> None:
        """Test the full pull flow with mocked API responses."""

        async def mock_api_get(endpoint: str, params: dict | None = None) -> dict:
            if "BankTransactions" in endpoint:
                return {"BankTransactions": [
                    MOCK_BANK_TRANSACTION_SPEND,
                    MOCK_BANK_TRANSACTION_RECEIVE,
                ]}
            elif "Invoices" in endpoint:
                return {"Invoices": [MOCK_INVOICE_AR, MOCK_INVOICE_AP]}
            elif "TrialBalance" in endpoint:
                return MOCK_TRIAL_BALANCE
            return {}

        xero_connector._api_get = mock_api_get  # type: ignore

        dataset = await xero_connector.pull(company)

        # Verify transactions
        assert len(dataset.transactions) == 2

        expenses = [t for t in dataset.transactions if t.type.value == "expense"]
        income = [t for t in dataset.transactions if t.type.value == "income"]
        assert len(expenses) == 1
        assert len(income) == 1

        assert expenses[0].amount == 150.00
        assert expenses[0].vendor == "Staples"
        assert expenses[0].id == "xero-bt-bt-001"

        assert income[0].amount == 8000.00
        assert income[0].vendor == "Client Corp"

        # Verify invoices
        assert len(dataset.invoices) == 2

        ar = [i for i in dataset.invoices if i.invoice_number == "INV-2025-001"][0]
        assert ar.amount == 5000.00
        assert ar.status == "paid"
        assert ar.paid_date == date(2025, 1, 25)
        assert len(ar.line_items) == 1

        ap = [i for i in dataset.invoices if i.invoice_number == "BILL-2025-001"][0]
        assert ap.vendor == "AWS"
        assert ap.amount == 2400.00
        assert ap.status == "pending"

        # Verify balances
        assert len(dataset.balances) == 2
        checking = [b for b in dataset.balances if b.account_name == "Business Checking"][0]
        assert checking.balance == 50000.00
        assert checking.account_type == "checking"

        # Verify metadata
        assert dataset.source == "xero"
        assert dataset.metadata["tenant_id"] == "abc-def-123"

    @pytest.mark.asyncio
    async def test_fetch_bank_transactions_skips_deleted(self, xero_connector: XeroConnector) -> None:
        """Verify deleted transactions are skipped."""
        deleted_txn = {**MOCK_BANK_TRANSACTION_SPEND, "Status": "DELETED"}

        async def mock_api_get(endpoint: str, params: dict | None = None) -> dict:
            return {"BankTransactions": [deleted_txn, MOCK_BANK_TRANSACTION_RECEIVE]}

        xero_connector._api_get = mock_api_get  # type: ignore
        txns = await xero_connector._fetch_bank_transactions()
        assert len(txns) == 1
        assert txns[0].type.value == "income"

    @pytest.mark.asyncio
    async def test_auto_detect_tenant(self, xero_connector: XeroConnector) -> None:
        """Test automatic tenant ID detection."""
        xero_connector.tenant_id = ""  # Clear tenant ID

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_CONNECTIONS
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.is_closed = False
        xero_connector._http = mock_client

        # Mock token manager
        mock_mgr = MagicMock()
        mock_mgr.get_access_token = AsyncMock(return_value="test_token")
        xero_connector._token_manager = mock_mgr

        await xero_connector._auto_detect_tenant()
        assert xero_connector.tenant_id == "abc-def-123"

    def test_authorization_url(self, xero_connector: XeroConnector) -> None:
        url = xero_connector.get_authorization_url(
            redirect_uri="https://myapp.com/callback",
            state="csrf_token",
        )
        assert "login.xero.com" in url
        assert "client_id=test_client_id" in url
        assert "state=csrf_token" in url

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, xero_connector: XeroConnector) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_CONNECTIONS
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.is_closed = False
        xero_connector._http = mock_client

        mock_mgr = MagicMock()
        mock_mgr.get_access_token = AsyncMock(return_value="test_token")
        xero_connector._token_manager = mock_mgr

        health = await xero_connector.health_check()
        assert health["healthy"] is True
        assert health["organisation"] == "Test Corp Xero"
