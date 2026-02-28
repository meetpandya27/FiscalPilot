"""Tests for SquarePOSConnector — Square POS integration for restaurants."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fiscalpilot.connectors.square_connector import SquarePOSConnector
from fiscalpilot.models.company import CompanyProfile, CompanySize, Industry
from fiscalpilot.models.financial import TransactionType


@pytest.fixture
def mock_company():
    """Create a mock company profile."""
    return CompanyProfile(
        name="Joe's Diner",
        industry=Industry.RESTAURANT,
        size=CompanySize.SMALL,
        annual_revenue=850_000,
    )


@pytest.fixture
def connector():
    """Create a SquarePOSConnector with test credentials."""
    return SquarePOSConnector(
        credentials={
            "access_token": "test_token_123",
            "location_id": "loc_abc123",
        }
    )


class TestSquareConnectorInit:
    """Test SquarePOSConnector initialization."""

    def test_init_with_credentials(self):
        """Test initialization with credentials."""
        connector = SquarePOSConnector(
            credentials={
                "access_token": "test_token",
                "location_id": "loc_123",
            }
        )
        assert connector.access_token == "test_token"
        assert connector.location_id == "loc_123"
        assert connector.name == "square"

    def test_init_sandbox_mode(self):
        """Test sandbox mode uses sandbox URL."""
        connector = SquarePOSConnector(
            credentials={"access_token": "test"},
            sandbox=True,
        )
        assert connector.sandbox is True
        assert "sandbox" in connector._base_url

    def test_init_production_mode(self):
        """Test production mode uses production URL."""
        connector = SquarePOSConnector(
            credentials={"access_token": "test"},
            sandbox=False,
        )
        assert connector.sandbox is False
        assert "sandbox" not in connector._base_url

    def test_init_default_days_back(self):
        """Test default days_back is 90."""
        connector = SquarePOSConnector(credentials={"access_token": "test"})
        assert connector.days_back == 90

    def test_init_custom_days_back(self):
        """Test custom days_back option."""
        connector = SquarePOSConnector(
            credentials={"access_token": "test"},
            days_back=30,
        )
        assert connector.days_back == 30


class TestSquareValidateCredentials:
    """Test credential validation."""

    @pytest.mark.asyncio
    async def test_validate_empty_token_returns_false(self):
        """Test that empty token returns False."""
        connector = SquarePOSConnector(credentials={})
        result = await connector.validate_credentials()
        assert result is False

    @pytest.mark.asyncio
    async def test_validate_with_valid_token(self, connector):
        """Test validation with mock valid token."""
        with patch.object(connector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await connector.validate_credentials()
            assert result is True

    @pytest.mark.asyncio
    async def test_validate_with_invalid_token(self, connector):
        """Test validation with invalid token returns False."""
        with patch.object(connector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            result = await connector.validate_credentials()
            assert result is False


class TestSquarePull:
    """Test data pulling from Square."""

    @pytest.mark.asyncio
    async def test_pull_returns_financial_dataset(self, connector, mock_company):
        """Test that pull returns a FinancialDataset."""
        with patch.object(connector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()

            # Mock locations response
            locations_response = MagicMock()
            locations_response.status_code = 200
            locations_response.json.return_value = {"locations": [{"id": "loc_abc123", "name": "Main Store"}]}

            # Mock payments response
            payments_response = MagicMock()
            payments_response.status_code = 200
            payments_response.raise_for_status = MagicMock()
            payments_response.json.return_value = {
                "payments": [
                    {
                        "id": "pay_001",
                        "created_at": "2024-01-15T12:00:00Z",
                        "status": "COMPLETED",
                        "amount_money": {"amount": 2500, "currency": "USD"},
                        "tip_money": {"amount": 300, "currency": "USD"},
                        "processing_fee": [{"amount_money": {"amount": 75}}],
                        "source_type": "CARD",
                        "card_details": {"card": {"card_brand": "VISA"}},
                    }
                ]
            }

            mock_client.get = AsyncMock(
                side_effect=[
                    locations_response,
                    payments_response,
                ]
            )
            mock_get_client.return_value = mock_client

            result = await connector.pull(mock_company)

            assert result.source.startswith("square:")
            assert len(result.transactions) > 0

    @pytest.mark.asyncio
    async def test_pull_creates_income_and_expense_transactions(self, connector, mock_company):
        """Test that both income and fee expense transactions are created."""
        with patch.object(connector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()

            locations_response = MagicMock()
            locations_response.status_code = 200
            locations_response.json.return_value = {"locations": [{"id": "loc_abc123", "name": "Test Location"}]}

            payments_response = MagicMock()
            payments_response.status_code = 200
            payments_response.raise_for_status = MagicMock()
            payments_response.json.return_value = {
                "payments": [
                    {
                        "id": "pay_001",
                        "created_at": "2024-01-15T10:00:00Z",
                        "status": "COMPLETED",
                        "amount_money": {"amount": 5000, "currency": "USD"},
                        "tip_money": {"amount": 0},
                        "processing_fee": [{"amount_money": {"amount": 150}}],
                        "source_type": "CARD",
                    }
                ]
            }

            mock_client.get = AsyncMock(
                side_effect=[
                    locations_response,
                    payments_response,
                ]
            )
            mock_get_client.return_value = mock_client

            result = await connector.pull(mock_company)

            income_txns = [t for t in result.transactions if t.type == TransactionType.INCOME]
            expense_txns = [t for t in result.transactions if t.type == TransactionType.EXPENSE]

            assert len(income_txns) == 1
            assert len(expense_txns) == 1
            assert income_txns[0].amount == 50.00  # $50.00
            assert expense_txns[0].amount == 1.50  # $1.50 fee

    @pytest.mark.asyncio
    async def test_pull_handles_no_locations(self, connector, mock_company):
        """Test handling when no locations are found."""
        with patch.object(connector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()

            locations_response = MagicMock()
            locations_response.status_code = 200
            locations_response.json.return_value = {"locations": []}

            mock_client.get = AsyncMock(return_value=locations_response)
            mock_get_client.return_value = mock_client

            # Use a different location_id so filtering returns empty
            connector.location_id = "nonexistent"
            result = await connector.pull(mock_company)

            assert result.source == "square:no_locations"
            assert len(result.transactions) == 0


class TestSquarePaymentParsing:
    """Test payment to transaction conversion."""

    def test_payment_to_transactions_card(self, connector):
        """Test card payment conversion."""
        payment = {
            "id": "pay_123",
            "created_at": "2024-01-15T14:30:00Z",
            "status": "COMPLETED",
            "amount_money": {"amount": 3500, "currency": "USD"},
            "tip_money": {"amount": 500, "currency": "USD"},
            "processing_fee": [{"amount_money": {"amount": 100}}],
            "source_type": "CARD",
            "card_details": {"card": {"card_brand": "MASTERCARD"}},
        }

        transactions = connector._payment_to_transactions(payment, "Main Store")

        assert len(transactions) == 2  # Income + fee

        income_txn = transactions[0]
        assert income_txn.type == TransactionType.INCOME
        assert income_txn.amount == 35.00
        assert "MASTERCARD" in income_txn.description

        fee_txn = transactions[1]
        assert fee_txn.type == TransactionType.EXPENSE
        assert fee_txn.amount == 1.00

    def test_payment_to_transactions_cash(self, connector):
        """Test cash payment conversion."""
        payment = {
            "id": "pay_456",
            "created_at": "2024-01-15T15:00:00Z",
            "status": "COMPLETED",
            "amount_money": {"amount": 2000, "currency": "USD"},
            "tip_money": {"amount": 0},
            "processing_fee": [],
            "source_type": "CASH",
        }

        transactions = connector._payment_to_transactions(payment, "Test Store")

        # Cash has no processing fee
        assert len(transactions) == 1
        assert transactions[0].type == TransactionType.INCOME
        assert "Cash" in transactions[0].description

    def test_payment_to_transactions_skips_pending(self, connector):
        """Test that pending payments are skipped."""
        payment = {
            "id": "pay_pending",
            "created_at": "2024-01-15T16:00:00Z",
            "status": "PENDING",
            "amount_money": {"amount": 1000, "currency": "USD"},
        }

        transactions = connector._payment_to_transactions(payment, "Store")
        assert len(transactions) == 0


class TestSquareDailySummary:
    """Test daily summary functionality."""

    @pytest.mark.asyncio
    async def test_get_daily_summary(self, connector):
        """Test daily summary generation."""
        with patch.object(connector, "_get_client") as mock_get_client:
            mock_client = AsyncMock()

            locations_response = MagicMock()
            locations_response.status_code = 200
            locations_response.json.return_value = {"locations": [{"id": "loc_abc123"}]}

            payments_response = MagicMock()
            payments_response.status_code = 200
            payments_response.raise_for_status = MagicMock()
            payments_response.json.return_value = {
                "payments": [
                    {
                        "id": "pay_1",
                        "created_at": "2024-01-15T10:00:00Z",
                        "status": "COMPLETED",
                        "amount_money": {"amount": 5000},
                        "tip_money": {"amount": 500},
                        "processing_fee": [{"amount_money": {"amount": 150}}],
                    },
                    {
                        "id": "pay_2",
                        "created_at": "2024-01-15T14:00:00Z",
                        "status": "COMPLETED",
                        "amount_money": {"amount": 3000},
                        "tip_money": {"amount": 300},
                        "processing_fee": [{"amount_money": {"amount": 90}}],
                    },
                ]
            }

            mock_client.get = AsyncMock(
                side_effect=[
                    locations_response,
                    payments_response,
                ]
            )
            mock_get_client.return_value = mock_client

            summary = await connector.get_daily_summary(
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
            )

            assert len(summary) == 1  # One day
            day = summary[0]
            assert day["total_sales"] == 80.00  # $50 + $30
            assert day["transaction_count"] == 2
            assert day["tips"] == 8.00  # $5 + $3
            assert day["processing_fees"] == 2.40  # $1.50 + $0.90


class TestSquareItemSales:
    """Test item-level sales for menu analysis."""

    @pytest.mark.asyncio
    async def test_get_item_sales(self, connector):
        """Test item sales aggregation."""
        with (
            patch.object(connector, "_get_client") as mock_get_client,
            patch.object(connector, "_get_orders") as mock_get_orders,
        ):
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client

            mock_get_orders.return_value = [
                {
                    "id": "order_1",
                    "line_items": [
                        {
                            "name": "Cheeseburger",
                            "quantity": "2",
                            "base_price_money": {"amount": 1200},
                            "total_money": {"amount": 2400},
                        },
                        {
                            "name": "Fries",
                            "quantity": "2",
                            "base_price_money": {"amount": 400},
                            "total_money": {"amount": 800},
                        },
                    ],
                },
                {
                    "id": "order_2",
                    "line_items": [
                        {
                            "name": "Cheeseburger",
                            "quantity": "1",
                            "base_price_money": {"amount": 1200},
                            "total_money": {"amount": 1200},
                        },
                    ],
                },
            ]

            items = await connector.get_item_sales()

            assert len(items) == 2

            # Cheeseburger should be first (highest sales)
            assert items[0]["item_name"] == "Cheeseburger"
            assert items[0]["quantity_sold"] == 3
            assert items[0]["gross_sales"] == 36.00  # $24 + $12

            assert items[1]["item_name"] == "Fries"
            assert items[1]["quantity_sold"] == 2
            assert items[1]["gross_sales"] == 8.00
