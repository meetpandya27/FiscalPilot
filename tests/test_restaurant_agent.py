"""Tests for RestaurantAgent — restaurant-specific AI CFO agent."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fiscalpilot.agents.restaurant import RestaurantAgent, create_restaurant_agent
from fiscalpilot.config import FiscalPilotConfig, LLMConfig
from fiscalpilot.models.financial import (
    ExpenseCategory,
    FinancialDataset,
    Transaction,
    TransactionType,
)


@pytest.fixture
def mock_config():
    """Create a mock FiscalPilotConfig."""
    config = MagicMock(spec=FiscalPilotConfig)
    config.llm = LLMConfig(
        model="gpt-4o-mini",
        api_key="test-key",
        temperature=0.7,
        max_tokens=2000,
        timeout=30,
    )
    return config


@pytest.fixture
def sample_dataset():
    """Create sample restaurant financial data."""
    transactions = [
        # Food costs - 30% of revenue
        Transaction(
            id="1",
            date=date(2024, 1, 15),
            amount=2500,
            description="Sysco Foods",
            vendor="Sysco",
            type=TransactionType.EXPENSE,
            category=ExpenseCategory.INVENTORY,
        ),
        Transaction(
            id="2",
            date=date(2024, 1, 20),
            amount=1800,
            description="US Foods",
            vendor="US Foods",
            type=TransactionType.EXPENSE,
            category=ExpenseCategory.INVENTORY,
        ),
        # Labor costs - 32%
        Transaction(
            id="3",
            date=date(2024, 1, 15),
            amount=3200,
            description="Bi-weekly payroll",
            vendor="ADP Payroll",
            type=TransactionType.EXPENSE,
            category=ExpenseCategory.PAYROLL,
        ),
        Transaction(
            id="4",
            date=date(2024, 1, 31),
            amount=3000,
            description="Bi-weekly payroll",
            vendor="ADP Payroll",
            type=TransactionType.EXPENSE,
            category=ExpenseCategory.PAYROLL,
        ),
        # Rent - 8%
        Transaction(
            id="5",
            date=date(2024, 1, 1),
            amount=1500,
            description="Monthly rent",
            vendor="Property Management",
            type=TransactionType.EXPENSE,
            category=ExpenseCategory.RENT,
        ),
        # Utilities - 2%
        Transaction(
            id="6",
            date=date(2024, 1, 10),
            amount=400,
            description="Electric bill",
            vendor="ComEd",
            type=TransactionType.EXPENSE,
            category=ExpenseCategory.UTILITIES,
        ),
        # Income
        Transaction(
            id="7",
            date=date(2024, 1, 31),
            amount=15000,
            description="January sales",
            vendor="POS System",
            type=TransactionType.INCOME,
            category=None,
        ),
    ]

    dataset = FinancialDataset(
        transactions=transactions,
        source="test",
        period_start=date(2024, 1, 1),
        period_end=date(2024, 1, 31),
    )
    return dataset


class TestRestaurantAgentInit:
    """Test RestaurantAgent initialization."""

    def test_create_agent(self, mock_config):
        """Test agent creation."""
        agent = RestaurantAgent(mock_config)
        assert agent.name == "restaurant"
        assert "Restaurant" in agent.description

    def test_factory_function(self, mock_config):
        """Test create_restaurant_agent factory."""
        agent = create_restaurant_agent(mock_config)
        assert isinstance(agent, RestaurantAgent)

    def test_system_prompt(self, mock_config):
        """Test system prompt contains restaurant expertise."""
        agent = RestaurantAgent(mock_config)
        prompt = agent.system_prompt
        assert "restaurant" in prompt.lower()
        assert "menu" in prompt.lower()
        assert "labor" in prompt.lower()


class TestRestaurantAgentAnalyze:
    """Test RestaurantAgent analysis capabilities."""

    @pytest.mark.asyncio
    async def test_analyze_returns_kpi_results(self, mock_config, sample_dataset):
        """Test that analyze returns KPI results."""
        agent = RestaurantAgent(mock_config)

        # Mock LLM call to avoid actual API call
        with patch.object(agent, "_call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "[]"  # Empty recommendations

            result = await agent.analyze(
                {
                    "dataset": sample_dataset,
                    "annual_revenue": 180_000,
                    "company": {"name": "Test Restaurant"},
                }
            )

        assert "kpi_results" in result
        assert "health_grade" in result
        assert "health_score" in result
        assert "findings" in result

    @pytest.mark.asyncio
    async def test_analyze_generates_findings(self, mock_config, sample_dataset):
        """Test that findings are generated from KPIs."""
        agent = RestaurantAgent(mock_config)

        with patch.object(agent, "_call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "[]"

            result = await agent.analyze(
                {
                    "dataset": sample_dataset,
                    "annual_revenue": 180_000,
                    "company": {"name": "Test Restaurant"},
                }
            )

        findings = result["findings"]
        assert len(findings) > 0

        # Check finding structure
        for finding in findings:
            assert "title" in finding
            assert "category" in finding
            assert "severity" in finding

    @pytest.mark.asyncio
    async def test_analyze_generates_actions(self, mock_config, sample_dataset):
        """Test that action proposals are generated."""
        agent = RestaurantAgent(mock_config)

        with patch.object(agent, "_call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "[]"

            result = await agent.analyze(
                {
                    "dataset": sample_dataset,
                    "annual_revenue": 180_000,
                    "company": {"name": "Test Restaurant"},
                }
            )

        # Should have action proposals
        assert "proposed_actions" in result

    @pytest.mark.asyncio
    async def test_analyze_without_dataset_returns_error(self, mock_config):
        """Test that missing dataset returns error."""
        agent = RestaurantAgent(mock_config)

        result = await agent.analyze(
            {
                "company": {"name": "Test Restaurant"},
            }
        )

        assert "error" in result
        assert "dataset" in result["error"].lower()


class TestRestaurantAgentActionGeneration:
    """Test action proposal generation."""

    @pytest.mark.asyncio
    async def test_high_food_cost_generates_action(self, mock_config):
        """Test that high food cost triggers action proposal."""
        # Create dataset with high food cost (>32%)
        # With $10,000 annual revenue and $4,000 food cost = 40%
        transactions = [
            Transaction(
                id="1",
                date=date(2024, 1, 15),
                amount=4000,
                description="Food supplies",
                vendor="Sysco",
                type=TransactionType.EXPENSE,
                category=ExpenseCategory.INVENTORY,
            ),
            Transaction(
                id="2",
                date=date(2024, 1, 31),
                amount=10000,
                description="January sales",
                vendor="POS",
                type=TransactionType.INCOME,
                category=None,
            ),
        ]
        dataset = FinancialDataset(
            transactions=transactions,
            source="test",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 31),
        )

        agent = RestaurantAgent(mock_config)

        with patch.object(agent, "_call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "[]"

            # Use $10,000 annual revenue so $4000 food cost = 40%
            result = await agent.analyze(
                {
                    "dataset": dataset,
                    "annual_revenue": 10_000,
                    "company": {"name": "Test Restaurant"},
                }
            )

        # Should generate food cost action since 40% > 32% threshold
        actions = result.get("proposed_actions", [])
        food_actions = [a for a in actions if "food" in a.get("title", "").lower()]
        assert len(food_actions) > 0

    @pytest.mark.asyncio
    async def test_low_marketing_generates_opportunity(self, mock_config):
        """Test that low marketing spend generates opportunity."""
        # Create dataset with no marketing spend
        transactions = [
            Transaction(
                id="1",
                date=date(2024, 1, 15),
                amount=3000,
                description="Food",
                vendor="Sysco",
                type=TransactionType.EXPENSE,
                category=ExpenseCategory.INVENTORY,
            ),
            Transaction(
                id="2",
                date=date(2024, 1, 15),
                amount=3000,
                description="Payroll",
                vendor="ADP",
                type=TransactionType.EXPENSE,
                category=ExpenseCategory.PAYROLL,
            ),
            Transaction(
                id="3",
                date=date(2024, 1, 31),
                amount=10000,
                description="Sales",
                vendor="POS",
                type=TransactionType.INCOME,
                category=None,
            ),
        ]
        dataset = FinancialDataset(
            transactions=transactions,
            source="test",
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 31),
        )

        agent = RestaurantAgent(mock_config)

        with patch.object(agent, "_call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "[]"

            result = await agent.analyze(
                {
                    "dataset": dataset,
                    "annual_revenue": 120_000,
                    "company": {"name": "Test Restaurant"},
                }
            )

        # Should generate marketing action
        actions = result.get("proposed_actions", [])
        marketing_actions = [a for a in actions if "marketing" in a.get("title", "").lower()]
        assert len(marketing_actions) > 0


class TestRestaurantAgentLLMIntegration:
    """Test LLM recommendation parsing."""

    @pytest.mark.asyncio
    async def test_parse_valid_recommendations(self, mock_config, sample_dataset):
        """Test parsing of valid JSON recommendations."""
        agent = RestaurantAgent(mock_config)

        mock_recommendations = """[
            {
                "title": "Renegotiate food supplier contracts",
                "category": "food_cost",
                "priority": "high",
                "description": "Current food costs are above target",
                "estimated_savings": 5000,
                "implementation_steps": ["Step 1", "Step 2"],
                "timeline": "2 weeks",
                "quick_win": true
            }
        ]"""

        with patch.object(agent, "_call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = mock_recommendations

            result = await agent.analyze(
                {
                    "dataset": sample_dataset,
                    "annual_revenue": 180_000,
                    "company": {"name": "Test Restaurant"},
                }
            )

        recommendations = result.get("recommendations", [])
        assert len(recommendations) == 1
        assert recommendations[0]["title"] == "Renegotiate food supplier contracts"

    @pytest.mark.asyncio
    async def test_handle_invalid_json(self, mock_config, sample_dataset):
        """Test graceful handling of invalid JSON from LLM."""
        agent = RestaurantAgent(mock_config)

        with patch.object(agent, "_call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = "This is not valid JSON"

            result = await agent.analyze(
                {
                    "dataset": sample_dataset,
                    "annual_revenue": 180_000,
                    "company": {"name": "Test Restaurant"},
                }
            )

        # Should still return KPI results even if LLM fails
        assert "kpi_results" in result
        assert result.get("recommendations") == []

    @pytest.mark.asyncio
    async def test_handle_llm_exception(self, mock_config, sample_dataset):
        """Test graceful handling of LLM exceptions."""
        agent = RestaurantAgent(mock_config)

        with patch.object(agent, "_call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.side_effect = Exception("API error")

            result = await agent.analyze(
                {
                    "dataset": sample_dataset,
                    "annual_revenue": 180_000,
                    "company": {"name": "Test Restaurant"},
                }
            )

        # Should still return KPI results
        assert "kpi_results" in result
        assert "health_grade" in result
