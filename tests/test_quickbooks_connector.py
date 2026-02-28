"""Tests for the QuickBooks Online connector with mocked API responses."""

from __future__ import annotations

from datetime import date

import pytest

from fiscalpilot.connectors.quickbooks_connector import QuickBooksConnector
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
def qbo_connector() -> QuickBooksConnector:
    return QuickBooksConnector(
        credentials={
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "refresh_token": "test_refresh_token",
            "realm_id": "1234567890",
        },
        sandbox=True,
    )


# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------


MOCK_PURCHASE = {
    "Id": "101",
    "TxnDate": "2025-01-15",
    "TotalAmt": 250.00,
    "PaymentType": "CreditCard",
    "EntityRef": {"name": "Office Depot", "value": "42"},
    "AccountRef": {"name": "Office Expenses", "value": "78"},
    "Line": [
        {
            "Amount": 250.00,
            "Description": "Office Supplies Q1",
            "AccountBasedExpenseLineDetail": {
                "AccountRef": {"name": "Office Expenses", "value": "78"},
            },
        }
    ],
    "MetaData": {"CreateTime": "2025-01-15T10:30:00-08:00"},
}

MOCK_DEPOSIT = {
    "Id": "201",
    "TxnDate": "2025-01-20",
    "TotalAmt": 5000.00,
    "DepositToAccountRef": {"name": "Business Checking", "value": "1"},
    "Line": [
        {
            "Amount": 5000.00,
            "Description": "Client Payment - Project Alpha",
            "DepositLineDetail": {
                "Entity": {"name": "Acme Corp"},
            },
        }
    ],
    "MetaData": {"CreateTime": "2025-01-20T14:00:00-08:00"},
}

MOCK_INVOICE = {
    "Id": "301",
    "DocNumber": "INV-001",
    "TxnDate": "2025-01-10",
    "DueDate": "2025-02-10",
    "TotalAmt": 3500.00,
    "Balance": 0,
    "CustomerRef": {"name": "Widget Co", "value": "15"},
    "Line": [
        {
            "DetailType": "SalesItemLineDetail",
            "Amount": 3500.00,
            "Description": "Consulting services - January",
            "SalesItemLineDetail": {
                "ItemRef": {"name": "Consulting", "value": "5"},
                "Qty": 35,
                "UnitPrice": 100.00,
            },
        }
    ],
    "MetaData": {"CreateTime": "2025-01-10T09:00:00-08:00"},
}

MOCK_BILL = {
    "Id": "401",
    "DocNumber": "BILL-001",
    "TxnDate": "2025-01-05",
    "DueDate": "2025-02-05",
    "TotalAmt": 1200.00,
    "Balance": 1200.00,
    "VendorRef": {"name": "AWS", "value": "22"},
    "Line": [
        {
            "DetailType": "AccountBasedExpenseLineDetail",
            "Amount": 1200.00,
            "Description": "Cloud hosting - January",
            "AccountBasedExpenseLineDetail": {
                "AccountRef": {"name": "Hosting", "value": "85"},
            },
        }
    ],
    "MetaData": {"CreateTime": "2025-01-05T12:00:00-08:00"},
}

MOCK_ACCOUNT = {
    "Id": "1",
    "Name": "Business Checking",
    "AccountType": "Bank",
    "Active": True,
    "CurrentBalance": 45000.00,
}

MOCK_COMPANY_INFO = {
    "CompanyInfo": {
        "CompanyName": "Test Corp",
        "Country": "US",
        "Id": "1234567890",
    }
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestQuickBooksConnector:
    def test_init(self, qbo_connector: QuickBooksConnector) -> None:
        assert qbo_connector.client_id == "test_client_id"
        assert qbo_connector.realm_id == "1234567890"
        assert qbo_connector.sandbox is True
        assert "sandbox" in qbo_connector._base_url

    def test_init_production(self) -> None:
        conn = QuickBooksConnector(credentials={
            "client_id": "id",
            "client_secret": "secret",
            "refresh_token": "token",
            "realm_id": "realm",
        })
        assert "sandbox" not in conn._base_url
        assert conn.sandbox is False

    def test_date_parsing(self) -> None:
        assert QuickBooksConnector._parse_date("2025-01-15") == date(2025, 1, 15)
        assert QuickBooksConnector._parse_date("2025-01-15T10:30:00") == date(2025, 1, 15)
        assert QuickBooksConnector._parse_date("") == date.today()

    def test_category_mapping(self) -> None:
        from fiscalpilot.models.financial import ExpenseCategory

        assert QuickBooksConnector._map_qbo_category("Rent or Lease") == ExpenseCategory.RENT
        assert QuickBooksConnector._map_qbo_category("Office Expenses") == ExpenseCategory.SUPPLIES
        assert QuickBooksConnector._map_qbo_category("Payroll Expenses") == ExpenseCategory.PAYROLL
        assert QuickBooksConnector._map_qbo_category("Unknown Stuff") == ExpenseCategory.OTHER
        assert QuickBooksConnector._map_qbo_category("") is None

    def test_account_type_mapping(self) -> None:
        assert QuickBooksConnector._map_account_type("Bank") == "checking"
        assert QuickBooksConnector._map_account_type("Credit Card") == "credit"
        assert QuickBooksConnector._map_account_type("Unknown") == "other"

    @pytest.mark.asyncio
    async def test_validate_credentials_missing(self) -> None:
        conn = QuickBooksConnector(credentials={})
        result = await conn.validate_credentials()
        assert result is False

    @pytest.mark.asyncio
    async def test_pull_full(self, qbo_connector: QuickBooksConnector, company: CompanyProfile) -> None:
        """Test the full pull flow with mocked API responses."""

        async def mock_api_get(endpoint: str, params: dict | None = None) -> dict:
            query = (params or {}).get("query", "")
            if "Purchase" in query:
                return {"QueryResponse": {"Purchase": [MOCK_PURCHASE]}}
            elif "Deposit" in query:
                return {"QueryResponse": {"Deposit": [MOCK_DEPOSIT]}}
            elif "Invoice" in query:
                return {"QueryResponse": {"Invoice": [MOCK_INVOICE]}}
            elif "Bill" in query:
                return {"QueryResponse": {"Bill": [MOCK_BILL]}}
            elif "Account" in query:
                return {"QueryResponse": {"Account": [MOCK_ACCOUNT]}}
            return {"QueryResponse": {}}

        qbo_connector._api_get = mock_api_get  # type: ignore

        dataset = await qbo_connector.pull(company)

        # Verify transactions
        assert len(dataset.transactions) == 2
        expense = [t for t in dataset.transactions if t.type.value == "expense"][0]
        income = [t for t in dataset.transactions if t.type.value == "income"][0]

        assert expense.amount == 250.00
        assert expense.vendor == "Office Depot"
        assert expense.id == "qbo-purchase-101"

        assert income.amount == 5000.00
        assert income.id == "qbo-deposit-201"

        # Verify invoices
        assert len(dataset.invoices) == 2
        inv = [i for i in dataset.invoices if "invoice" in (i.id or "")][0]
        assert inv.invoice_number == "INV-001"
        assert inv.amount == 3500.00
        assert inv.status == "paid"
        assert len(inv.line_items) == 1

        bill = [i for i in dataset.invoices if "bill" in (i.id or "")][0]
        assert bill.vendor == "AWS"
        assert bill.amount == 1200.00

        # Verify balances
        assert len(dataset.balances) == 1
        assert dataset.balances[0].account_name == "Business Checking"
        assert dataset.balances[0].balance == 45000.00

        # Verify metadata
        assert dataset.source == "quickbooks"
        assert dataset.metadata["sandbox"] is True
        assert dataset.metadata["purchase_count"] == 1
        assert dataset.metadata["deposit_count"] == 1

    @pytest.mark.asyncio
    async def test_pagination(self, qbo_connector: QuickBooksConnector) -> None:
        """Test that pagination handles multiple pages correctly."""
        call_count = 0

        async def mock_api_get(endpoint: str, params: dict | None = None) -> dict:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First page: return PAGE_SIZE items to trigger next page
                items = [{"Id": str(i), "TxnDate": "2025-01-01", "TotalAmt": 10.0} for i in range(1000)]
                return {"QueryResponse": {"Purchase": items}}
            else:
                # Second page: return fewer items (last page)
                items = [{"Id": str(i + 1000), "TxnDate": "2025-01-01", "TotalAmt": 10.0} for i in range(5)]
                return {"QueryResponse": {"Purchase": items}}

        qbo_connector._api_get = mock_api_get  # type: ignore

        results = await qbo_connector._query("SELECT * FROM Purchase")
        assert len(results) == 1005
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, qbo_connector: QuickBooksConnector) -> None:
        async def mock_api_get(endpoint: str, params: dict | None = None) -> dict:
            return MOCK_COMPANY_INFO

        qbo_connector._api_get = mock_api_get  # type: ignore

        health = await qbo_connector.health_check()
        assert health["healthy"] is True
        assert health["company_name"] == "Test Corp"
        assert health["sandbox"] is True

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, qbo_connector: QuickBooksConnector) -> None:
        async def mock_api_get(endpoint: str, params: dict | None = None) -> dict:
            raise ConnectionError("Network error")

        qbo_connector._api_get = mock_api_get  # type: ignore

        health = await qbo_connector.health_check()
        assert health["healthy"] is False
        assert "Network error" in health["error"]

    def test_authorization_url(self, qbo_connector: QuickBooksConnector) -> None:
        url = qbo_connector.get_authorization_url(
            redirect_uri="https://myapp.com/callback",
            state="csrf_token",
        )
        assert "appcenter.intuit.com" in url
        assert "client_id=test_client_id" in url
        assert "state=csrf_token" in url
