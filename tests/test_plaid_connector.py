"""Tests for the Plaid connector with mocked API responses."""

from __future__ import annotations

from datetime import date

import pytest

from fiscalpilot.connectors.plaid_connector import PlaidConnector
from fiscalpilot.models.company import CompanyProfile, CompanySize, Industry

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def company() -> CompanyProfile:
    return CompanyProfile(
        name="Test Restaurant",
        industry=Industry.RESTAURANT,
        size=CompanySize.MICRO,
    )


@pytest.fixture
def plaid_connector() -> PlaidConnector:
    return PlaidConnector(
        credentials={
            "client_id": "test_client_id",
            "secret": "test_secret",
            "access_tokens": ["access-sandbox-token-1"],
        },
        environment="sandbox",
    )


# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------


MOCK_TRANSACTIONS_SYNC = {
    "added": [
        {
            "transaction_id": "txn-001",
            "date": "2025-01-15",
            "amount": 42.50,  # Positive = spending in Plaid
            "name": "Uber Eats",
            "merchant_name": "Uber Eats",
            "payment_channel": "online",
            "pending": False,
            "account_id": "acct-001",
            "personal_finance_category": {
                "primary": "FOOD_AND_DRINK",
                "detailed": "FOOD_AND_DRINK_RESTAURANTS",
            },
        },
        {
            "transaction_id": "txn-002",
            "date": "2025-01-18",
            "amount": -3500.00,  # Negative = income in Plaid
            "name": "Direct Deposit - Acme Corp",
            "merchant_name": None,
            "payment_channel": "other",
            "pending": False,
            "account_id": "acct-001",
            "personal_finance_category": {
                "primary": "INCOME",
                "detailed": "INCOME_WAGES",
            },
        },
        {
            "transaction_id": "txn-003",
            "date": "2025-01-20",
            "amount": 1200.00,
            "name": "January Rent",
            "merchant_name": "Sunrise Properties",
            "payment_channel": "other",
            "pending": False,
            "account_id": "acct-001",
            "personal_finance_category": {
                "primary": "RENT_AND_UTILITIES",
                "detailed": "RENT_AND_UTILITIES_RENT",
            },
        },
        {
            "transaction_id": "txn-004",
            "date": "2025-01-22",
            "amount": 89.99,
            "name": "AWS Monthly",
            "merchant_name": "Amazon Web Services",
            "payment_channel": "online",
            "pending": True,
            "account_id": "acct-001",
            "personal_finance_category": {
                "primary": "GENERAL_MERCHANDISE",
                "detailed": "GENERAL_MERCHANDISE_SOFTWARE",
            },
        },
    ],
    "modified": [],
    "removed": [],
    "has_more": False,
    "next_cursor": "cursor_abc",
}

MOCK_BALANCES = {
    "accounts": [
        {
            "account_id": "acct-001",
            "name": "Business Checking",
            "official_name": "Business Premium Checking",
            "type": "depository",
            "subtype": "checking",
            "balances": {
                "current": 25000.00,
                "available": 24500.00,
                "limit": None,
            },
        },
        {
            "account_id": "acct-002",
            "name": "Business Savings",
            "type": "depository",
            "subtype": "savings",
            "balances": {
                "current": 100000.00,
                "available": 100000.00,
                "limit": None,
            },
        },
        {
            "account_id": "acct-003",
            "name": "Business Credit Card",
            "type": "credit",
            "subtype": "credit card",
            "balances": {
                "current": 3200.00,
                "available": 16800.00,
                "limit": 20000.00,
            },
        },
    ],
    "item": {
        "institution_id": "ins_109511",
    },
}

MOCK_LINK_TOKEN = {
    "link_token": "link-sandbox-abc123",
    "expiration": "2025-02-01T00:00:00Z",
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPlaidConnector:
    def test_init_single_token(self) -> None:
        conn = PlaidConnector(credentials={
            "client_id": "id",
            "secret": "secret",
            "access_token": "single_token",
        })
        assert conn.access_tokens == ["single_token"]

    def test_init_multiple_tokens(self) -> None:
        conn = PlaidConnector(credentials={
            "client_id": "id",
            "secret": "secret",
            "access_tokens": ["token1", "token2"],
        })
        assert len(conn.access_tokens) == 2

    def test_init_no_tokens(self) -> None:
        conn = PlaidConnector(credentials={
            "client_id": "id",
            "secret": "secret",
        })
        assert conn.access_tokens == []

    def test_environment_urls(self) -> None:
        sandbox = PlaidConnector(credentials={}, environment="sandbox")
        assert "sandbox.plaid.com" in sandbox._base_url

        dev = PlaidConnector(credentials={}, environment="development")
        assert "development.plaid.com" in dev._base_url

        prod = PlaidConnector(credentials={}, environment="production")
        assert "production.plaid.com" in prod._base_url

    def test_plaid_category_mapping(self) -> None:
        from fiscalpilot.models.financial import ExpenseCategory

        # Detailed categories (more specific)
        assert PlaidConnector._map_plaid_category("RENT_AND_UTILITIES", "RENT_AND_UTILITIES_RENT") == ExpenseCategory.RENT
        assert PlaidConnector._map_plaid_category("RENT_AND_UTILITIES", "RENT_AND_UTILITIES_GAS_AND_ELECTRICITY") == ExpenseCategory.UTILITIES
        assert PlaidConnector._map_plaid_category("FOOD_AND_DRINK", "FOOD_AND_DRINK_RESTAURANTS") == ExpenseCategory.MEALS
        assert PlaidConnector._map_plaid_category("GENERAL_MERCHANDISE", "GENERAL_MERCHANDISE_SOFTWARE") == ExpenseCategory.SOFTWARE

        # Primary categories (fallback)
        assert PlaidConnector._map_plaid_category("TRAVEL", "") == ExpenseCategory.TRAVEL
        assert PlaidConnector._map_plaid_category("TRANSPORTATION", "") == ExpenseCategory.TRAVEL

        # Empty
        assert PlaidConnector._map_plaid_category("", "") is None

    def test_plaid_account_type_mapping(self) -> None:
        assert PlaidConnector._map_plaid_account_type("depository", "checking") == "checking"
        assert PlaidConnector._map_plaid_account_type("depository", "savings") == "savings"
        assert PlaidConnector._map_plaid_account_type("credit", "credit card") == "credit"
        assert PlaidConnector._map_plaid_account_type("loan", "mortgage") == "loan"
        assert PlaidConnector._map_plaid_account_type("other", "something") == "other"

    def test_parse_plaid_transaction_expense(self, plaid_connector: PlaidConnector) -> None:
        txn_data = MOCK_TRANSACTIONS_SYNC["added"][0]
        txn = plaid_connector._parse_plaid_transaction(txn_data)
        assert txn is not None
        assert txn.amount == 42.50
        assert txn.type.value == "expense"
        assert txn.vendor == "Uber Eats"
        assert txn.date == date(2025, 1, 15)
        assert "plaid:online" in txn.tags

    def test_parse_plaid_transaction_income(self, plaid_connector: PlaidConnector) -> None:
        txn_data = MOCK_TRANSACTIONS_SYNC["added"][1]
        txn = plaid_connector._parse_plaid_transaction(txn_data)
        assert txn is not None
        assert txn.amount == 3500.00
        assert txn.type.value == "income"

    def test_parse_plaid_transaction_pending(self, plaid_connector: PlaidConnector) -> None:
        txn_data = MOCK_TRANSACTIONS_SYNC["added"][3]
        txn = plaid_connector._parse_plaid_transaction(txn_data)
        assert txn is not None
        assert "plaid:pending" in txn.tags

    @pytest.mark.asyncio
    async def test_pull_no_tokens_raises(self) -> None:
        conn = PlaidConnector(credentials={"client_id": "id", "secret": "secret"})
        company = CompanyProfile(name="Test")
        with pytest.raises(ValueError, match="No Plaid access tokens"):
            await conn.pull(company)

    @pytest.mark.asyncio
    async def test_pull_full(self, plaid_connector: PlaidConnector, company: CompanyProfile) -> None:
        """Test the full pull flow with mocked API responses."""

        async def mock_api_post(endpoint: str, payload: dict) -> dict:
            if "transactions/sync" in endpoint:
                return MOCK_TRANSACTIONS_SYNC
            elif "accounts/balance/get" in endpoint:
                return MOCK_BALANCES
            return {}

        plaid_connector._api_post = mock_api_post  # type: ignore

        dataset = await plaid_connector.pull(company)

        # Verify transactions
        assert len(dataset.transactions) == 4

        expenses = [t for t in dataset.transactions if t.type.value == "expense"]
        income = [t for t in dataset.transactions if t.type.value == "income"]
        assert len(expenses) == 3
        assert len(income) == 1

        # Check the rent transaction
        rent = [t for t in expenses if t.vendor == "Sunrise Properties"][0]
        assert rent.amount == 1200.00
        from fiscalpilot.models.financial import ExpenseCategory
        assert rent.category == ExpenseCategory.RENT

        # Verify balances
        assert len(dataset.balances) == 3
        checking = [b for b in dataset.balances if "Checking" in b.account_name][0]
        assert checking.balance == 25000.00
        assert checking.account_type == "checking"

        savings = [b for b in dataset.balances if "Savings" in b.account_name][0]
        assert savings.balance == 100000.00
        assert savings.account_type == "savings"

        credit = [b for b in dataset.balances if "Credit" in b.account_name][0]
        assert credit.balance == 3200.00
        assert credit.account_type == "credit"

        # Verify metadata
        assert dataset.source == "plaid"
        assert dataset.metadata["environment"] == "sandbox"
        assert dataset.metadata["transaction_count"] == 4

    @pytest.mark.asyncio
    async def test_transactions_sync_pagination(self, plaid_connector: PlaidConnector) -> None:
        """Test that cursor-based pagination works correctly."""
        call_count = 0

        async def mock_api_post(endpoint: str, payload: dict) -> dict:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "added": [
                        {"transaction_id": f"txn-{i}", "date": "2025-01-15", "amount": 10.0,
                         "name": f"Store {i}", "payment_channel": "in store", "pending": False,
                         "account_id": "acct-1"} for i in range(50)
                    ],
                    "modified": [],
                    "removed": [],
                    "has_more": True,
                    "next_cursor": "cursor_page2",
                }
            else:
                return {
                    "added": [
                        {"transaction_id": f"txn-{i}", "date": "2025-01-15", "amount": 10.0,
                         "name": f"Store {i}", "payment_channel": "in store", "pending": False,
                         "account_id": "acct-1"} for i in range(50, 55)
                    ],
                    "modified": [],
                    "removed": [],
                    "has_more": False,
                    "next_cursor": "cursor_end",
                }

        plaid_connector._api_post = mock_api_post  # type: ignore
        txns = await plaid_connector._fetch_transactions_for_token("token")
        assert len(txns) == 55
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_transactions_removed(self, plaid_connector: PlaidConnector) -> None:
        """Test that removed transactions are excluded."""

        async def mock_api_post(endpoint: str, payload: dict) -> dict:
            return {
                "added": [
                    {"transaction_id": "txn-keep", "date": "2025-01-15", "amount": 10.0,
                     "name": "Keep Me", "payment_channel": "online", "pending": False,
                     "account_id": "acct-1"},
                    {"transaction_id": "txn-remove", "date": "2025-01-16", "amount": 20.0,
                     "name": "Remove Me", "payment_channel": "online", "pending": False,
                     "account_id": "acct-1"},
                ],
                "modified": [],
                "removed": [{"transaction_id": "txn-remove"}],
                "has_more": False,
            }

        plaid_connector._api_post = mock_api_post  # type: ignore
        txns = await plaid_connector._fetch_transactions_for_token("token")
        assert len(txns) == 1
        assert txns[0].id == "plaid-txn-keep"

    @pytest.mark.asyncio
    async def test_create_link_token(self, plaid_connector: PlaidConnector) -> None:
        async def mock_api_post(endpoint: str, payload: dict) -> dict:
            assert "link/token/create" in endpoint
            assert payload["user"]["client_user_id"] == "user-123"
            assert payload["client_name"] == "FiscalPilot"
            return MOCK_LINK_TOKEN

        plaid_connector._api_post = mock_api_post  # type: ignore
        result = await plaid_connector.create_link_token("user-123")
        assert result == "link-sandbox-abc123"

    @pytest.mark.asyncio
    async def test_exchange_public_token(self, plaid_connector: PlaidConnector) -> None:
        async def mock_api_post(endpoint: str, payload: dict) -> dict:
            assert "public_token/exchange" in endpoint
            return {"access_token": "access-new-token"}

        plaid_connector._api_post = mock_api_post  # type: ignore
        token = await plaid_connector.exchange_public_token("public-sandbox-abc")
        assert token == "access-new-token"
        assert "access-new-token" in plaid_connector.access_tokens

    @pytest.mark.asyncio
    async def test_validate_credentials_no_keys(self) -> None:
        conn = PlaidConnector(credentials={})
        result = await conn.validate_credentials()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_no_tokens(self) -> None:
        conn = PlaidConnector(credentials={"client_id": "id", "secret": "secret"})
        health = await conn.health_check()
        assert health["healthy"] is False
        assert "No bank accounts linked" in health["error"]

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, plaid_connector: PlaidConnector) -> None:
        async def mock_api_post(endpoint: str, payload: dict) -> dict:
            return {
                "accounts": [{"account_id": "acct-1"}],
                "item": {"institution_id": "ins_109511"},
            }

        plaid_connector._api_post = mock_api_post  # type: ignore
        health = await plaid_connector.health_check()
        assert health["healthy"] is True
        assert health["linked_accounts"] == 1

    @pytest.mark.asyncio
    async def test_multi_account_pull(self, company: CompanyProfile) -> None:
        """Test pulling from multiple linked bank accounts."""
        conn = PlaidConnector(credentials={
            "client_id": "id",
            "secret": "secret",
            "access_tokens": ["token-bank-a", "token-bank-b"],
        })

        call_tokens: list[str] = []

        async def mock_api_post(endpoint: str, payload: dict) -> dict:
            token = payload.get("access_token", "")
            call_tokens.append(token)
            if "transactions/sync" in endpoint:
                return {
                    "added": [
                        {"transaction_id": f"txn-{token[-1]}", "date": "2025-01-15",
                         "amount": 100.0, "name": f"TXN from {token}",
                         "payment_channel": "online", "pending": False,
                         "account_id": f"acct-{token[-1]}"}
                    ],
                    "modified": [], "removed": [], "has_more": False,
                }
            elif "accounts/balance/get" in endpoint:
                return {
                    "accounts": [
                        {"account_id": f"acct-{token[-1]}", "name": f"Account {token[-1]}",
                         "type": "depository", "subtype": "checking",
                         "balances": {"current": 5000.0}},
                    ],
                    "item": {"institution_id": f"ins-{token[-1]}"},
                }
            return {}

        conn._api_post = mock_api_post  # type: ignore
        dataset = await conn.pull(company)

        assert len(dataset.transactions) == 2
        assert len(dataset.balances) == 2
        assert dataset.metadata["linked_accounts"] == 2
