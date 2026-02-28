"""Tests for the Restaurant KPI Analyzer."""

from __future__ import annotations

from datetime import date

import pytest

from fiscalpilot.analyzers.restaurant import (
    RestaurantAnalyzer,
    RestaurantKPISeverity,
    analyze_restaurant,
)
from fiscalpilot.models.financial import (
    ExpenseCategory,
    FinancialDataset,
    Transaction,
    TransactionType,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_transactions() -> list[Transaction]:
    """Generate sample restaurant transactions with realistic ratios.

    Using annual totals directly (full year data):
    - Revenue: $1,000,000
    - Food cost: $300,000 (30%)
    - Labor: $300,000 (30%)
    - Rent: $80,000 (8%)
    - Utilities: $40,000 (4%)
    - Marketing: $30,000 (3%)
    - Supplies: $40,000 (4%)
    """
    return [
        # Income - $1M annual
        Transaction(
            date=date(2024, 1, 15),
            amount=1_000_000,
            type=TransactionType.INCOME,
            description="Annual sales",
        ),
        # Food costs (inventory) - 30%
        Transaction(
            date=date(2024, 1, 10),
            amount=300_000,
            type=TransactionType.EXPENSE,
            category=ExpenseCategory.INVENTORY,
            description="Sysco food order",
            vendor="Sysco",
        ),
        # Labor costs (payroll) - 30%
        Transaction(
            date=date(2024, 1, 15),
            amount=300_000,
            type=TransactionType.EXPENSE,
            category=ExpenseCategory.PAYROLL,
            description="Annual payroll",
        ),
        # Rent - 8%
        Transaction(
            date=date(2024, 1, 1),
            amount=80_000,
            type=TransactionType.EXPENSE,
            category=ExpenseCategory.RENT,
            description="Annual rent",
        ),
        # Utilities - 4%
        Transaction(
            date=date(2024, 1, 15),
            amount=40_000,
            type=TransactionType.EXPENSE,
            category=ExpenseCategory.UTILITIES,
            description="Annual utilities",
        ),
        # Marketing - 3%
        Transaction(
            date=date(2024, 1, 5),
            amount=30_000,
            type=TransactionType.EXPENSE,
            category=ExpenseCategory.MARKETING,
            description="Annual marketing",
        ),
        # Supplies - 4%
        Transaction(
            date=date(2024, 1, 8),
            amount=40_000,
            type=TransactionType.EXPENSE,
            category=ExpenseCategory.SUPPLIES,
            description="Annual supplies",
        ),
    ]


@pytest.fixture
def sample_dataset(sample_transactions: list[Transaction]) -> FinancialDataset:
    """Build financial dataset from sample transactions."""
    return FinancialDataset(
        transactions=sample_transactions,
        period_start=date(2024, 1, 1),
        period_end=date(2024, 12, 31),  # Full year
        source="test",
    )


@pytest.fixture
def high_food_cost_transactions() -> list[Transaction]:
    """Transactions with critically high food cost (42%)."""
    return [
        Transaction(
            date=date(2024, 1, 15),
            amount=1_000_000,
            type=TransactionType.INCOME,
            description="Sales",
        ),
        # 42% food cost (critical)
        Transaction(
            date=date(2024, 1, 10),
            amount=420_000,
            type=TransactionType.EXPENSE,
            category=ExpenseCategory.INVENTORY,
            description="Food",
        ),
        Transaction(
            date=date(2024, 1, 15),
            amount=300_000,
            type=TransactionType.EXPENSE,
            category=ExpenseCategory.PAYROLL,
            description="Labor",
        ),
    ]


# ---------------------------------------------------------------------------
# Basic Tests
# ---------------------------------------------------------------------------


class TestRestaurantAnalyzer:
    def test_analyze_returns_result(self, sample_dataset: FinancialDataset) -> None:
        result = RestaurantAnalyzer.analyze(sample_dataset, annual_revenue=1_000_000)

        assert result is not None
        assert result.kpis is not None
        assert len(result.kpis) >= 4  # At least food, labor, prime, occupancy, margin

    def test_analyze_calculates_food_cost(self, sample_dataset: FinancialDataset) -> None:
        # $300k food on $1M revenue = 30%
        result = RestaurantAnalyzer.analyze(sample_dataset, annual_revenue=1_000_000)

        food_kpi = next(k for k in result.kpis if k.name == "food_cost_pct")
        assert 28 <= food_kpi.actual <= 32  # Should be around 30%

    def test_analyze_calculates_labor_cost(self, sample_dataset: FinancialDataset) -> None:
        # $300k labor on $1M revenue = 30%
        result = RestaurantAnalyzer.analyze(sample_dataset, annual_revenue=1_000_000)

        labor_kpi = next(k for k in result.kpis if k.name == "labor_cost_pct")
        assert 28 <= labor_kpi.actual <= 32  # Should be around 30%

    def test_analyze_calculates_prime_cost(self, sample_dataset: FinancialDataset) -> None:
        # Prime = food (30%) + labor (30%) = 60%
        result = RestaurantAnalyzer.analyze(sample_dataset, annual_revenue=1_000_000)

        prime_kpi = next(k for k in result.kpis if k.name == "prime_cost_pct")
        assert 58 <= prime_kpi.actual <= 62  # Should be around 60%

    def test_analyze_calculates_occupancy_cost(self, sample_dataset: FinancialDataset) -> None:
        # Rent (8%) + Utilities (4%) = 12%
        result = RestaurantAnalyzer.analyze(sample_dataset, annual_revenue=1_000_000)

        occupancy_kpi = next(k for k in result.kpis if k.name == "occupancy_cost_pct")
        assert 10 <= occupancy_kpi.actual <= 14  # Should be around 12%

    def test_health_grade_calculation(self, sample_dataset: FinancialDataset) -> None:
        result = RestaurantAnalyzer.analyze(sample_dataset, annual_revenue=1_000_000)

        assert result.health_grade in ["A", "B", "C", "D", "F"]
        assert 0 <= result.health_score <= 100


class TestSeverityRatings:
    def test_critical_food_cost(self) -> None:
        """Food cost >38% should be critical."""
        transactions = [
            Transaction(date=date(2024, 1, 1), amount=1_000_000, type=TransactionType.INCOME),
            Transaction(
                date=date(2024, 1, 1), amount=420_000, type=TransactionType.EXPENSE, category=ExpenseCategory.INVENTORY
            ),
        ]
        dataset = FinancialDataset(
            transactions=transactions, period_start=date(2024, 1, 1), period_end=date(2024, 12, 31)
        )

        result = RestaurantAnalyzer.analyze(dataset, annual_revenue=1_000_000)
        food_kpi = next(k for k in result.kpis if k.name == "food_cost_pct")

        assert food_kpi.actual > 38
        assert food_kpi.severity == RestaurantKPISeverity.CRITICAL

    def test_excellent_food_cost(self) -> None:
        """Food cost <25% should be excellent."""
        transactions = [
            Transaction(date=date(2024, 1, 1), amount=1_000_000, type=TransactionType.INCOME),
            Transaction(
                date=date(2024, 1, 1), amount=200_000, type=TransactionType.EXPENSE, category=ExpenseCategory.INVENTORY
            ),
        ]
        dataset = FinancialDataset(
            transactions=transactions, period_start=date(2024, 1, 1), period_end=date(2024, 12, 31)
        )

        result = RestaurantAnalyzer.analyze(dataset, annual_revenue=1_000_000)
        food_kpi = next(k for k in result.kpis if k.name == "food_cost_pct")

        assert food_kpi.actual < 25
        assert food_kpi.severity == RestaurantKPISeverity.EXCELLENT

    def test_warning_labor_cost(self) -> None:
        """Labor cost between 35-38% should be warning."""
        transactions = [
            Transaction(date=date(2024, 1, 1), amount=1_000_000, type=TransactionType.INCOME),
            Transaction(
                date=date(2024, 1, 1), amount=360_000, type=TransactionType.EXPENSE, category=ExpenseCategory.PAYROLL
            ),
        ]
        dataset = FinancialDataset(
            transactions=transactions, period_start=date(2024, 1, 1), period_end=date(2024, 12, 31)
        )

        result = RestaurantAnalyzer.analyze(dataset, annual_revenue=1_000_000)
        labor_kpi = next(k for k in result.kpis if k.name == "labor_cost_pct")

        assert 35 <= labor_kpi.actual <= 38
        assert labor_kpi.severity in [RestaurantKPISeverity.WARNING, RestaurantKPISeverity.CRITICAL]


class TestAlertsAndOpportunities:
    def test_critical_alerts_generated(self) -> None:
        """Critical KPIs should generate alerts."""
        transactions = [
            Transaction(date=date(2024, 1, 1), amount=1_000_000, type=TransactionType.INCOME),
            Transaction(
                date=date(2024, 1, 1), amount=450_000, type=TransactionType.EXPENSE, category=ExpenseCategory.INVENTORY
            ),
        ]
        dataset = FinancialDataset(
            transactions=transactions, period_start=date(2024, 1, 1), period_end=date(2024, 12, 31)
        )

        result = RestaurantAnalyzer.analyze(dataset, annual_revenue=1_000_000)

        assert len(result.critical_alerts) > 0
        assert any("food" in alert.lower() for alert in result.critical_alerts)

    def test_low_marketing_opportunity(self) -> None:
        """Low marketing spend should generate opportunity."""
        transactions = [
            Transaction(date=date(2024, 1, 1), amount=1_000_000, type=TransactionType.INCOME),
            Transaction(
                date=date(2024, 1, 1), amount=280_000, type=TransactionType.EXPENSE, category=ExpenseCategory.INVENTORY
            ),
            Transaction(
                date=date(2024, 1, 1), amount=280_000, type=TransactionType.EXPENSE, category=ExpenseCategory.PAYROLL
            ),
            Transaction(
                date=date(2024, 1, 1), amount=5_000, type=TransactionType.EXPENSE, category=ExpenseCategory.MARKETING
            ),
        ]
        dataset = FinancialDataset(
            transactions=transactions, period_start=date(2024, 1, 1), period_end=date(2024, 12, 31)
        )

        result = RestaurantAnalyzer.analyze(dataset, annual_revenue=1_000_000)

        assert any("marketing" in opp.lower() for opp in result.opportunities)


class TestHealthScore:
    def test_all_critical_gives_low_score(self) -> None:
        """All critical KPIs should result in low health score."""
        transactions = [
            Transaction(date=date(2024, 1, 1), amount=1_000_000, type=TransactionType.INCOME),
            Transaction(
                date=date(2024, 1, 1), amount=450_000, type=TransactionType.EXPENSE, category=ExpenseCategory.INVENTORY
            ),  # 45% food
            Transaction(
                date=date(2024, 1, 1), amount=420_000, type=TransactionType.EXPENSE, category=ExpenseCategory.PAYROLL
            ),  # 42% labor
            Transaction(
                date=date(2024, 1, 1), amount=80_000, type=TransactionType.EXPENSE, category=ExpenseCategory.RENT
            ),
            Transaction(
                date=date(2024, 1, 1), amount=60_000, type=TransactionType.EXPENSE, category=ExpenseCategory.UTILITIES
            ),
        ]
        dataset = FinancialDataset(
            transactions=transactions, period_start=date(2024, 1, 1), period_end=date(2024, 12, 31)
        )

        result = RestaurantAnalyzer.analyze(dataset, annual_revenue=1_000_000)

        assert result.health_score < 50
        assert result.health_grade in ["D", "F"]

    def test_healthy_kpis_give_high_score(self) -> None:
        """All healthy KPIs should result in high health score."""
        transactions = [
            Transaction(date=date(2024, 1, 1), amount=1_000_000, type=TransactionType.INCOME),
            Transaction(
                date=date(2024, 1, 1), amount=280_000, type=TransactionType.EXPENSE, category=ExpenseCategory.INVENTORY
            ),  # 28% food
            Transaction(
                date=date(2024, 1, 1), amount=280_000, type=TransactionType.EXPENSE, category=ExpenseCategory.PAYROLL
            ),  # 28% labor
            Transaction(
                date=date(2024, 1, 1), amount=60_000, type=TransactionType.EXPENSE, category=ExpenseCategory.RENT
            ),
            Transaction(
                date=date(2024, 1, 1), amount=20_000, type=TransactionType.EXPENSE, category=ExpenseCategory.UTILITIES
            ),
        ]
        dataset = FinancialDataset(
            transactions=transactions, period_start=date(2024, 1, 1), period_end=date(2024, 12, 31)
        )

        result = RestaurantAnalyzer.analyze(dataset, annual_revenue=1_000_000)

        assert result.health_score >= 60
        assert result.health_grade in ["A", "B", "C"]


class TestConvenienceFunction:
    def test_analyze_restaurant_function(self, sample_dataset: FinancialDataset) -> None:
        """Test the convenience function works."""
        result = analyze_restaurant(sample_dataset, annual_revenue=1_000_000)

        assert result is not None
        assert result.kpis is not None
        assert len(result.kpis) >= 4


class TestExpenseBreakdown:
    def test_expense_breakdown_calculated(self, sample_dataset: FinancialDataset) -> None:
        result = RestaurantAnalyzer.analyze(sample_dataset, annual_revenue=1_000_000)

        assert result.expense_breakdown is not None
        assert "inventory" in result.expense_breakdown
        assert "payroll" in result.expense_breakdown

    def test_expense_ratios_calculated(self, sample_dataset: FinancialDataset) -> None:
        result = RestaurantAnalyzer.analyze(sample_dataset, annual_revenue=1_000_000)

        assert result.expense_ratios is not None
        # Ratios should be percentages
        for ratio in result.expense_ratios.values():
            assert 0 <= ratio <= 100


class TestEdgeCases:
    def test_empty_transactions(self) -> None:
        """Handle empty transaction list gracefully."""
        dataset = FinancialDataset(
            transactions=[],
            period_start=date(2024, 1, 1),
            period_end=date(2024, 12, 31),
        )

        result = RestaurantAnalyzer.analyze(dataset, annual_revenue=100000)

        assert result is not None
        assert result.health_score >= 0

    def test_zero_revenue(self) -> None:
        """Handle zero revenue gracefully."""
        transactions = [
            Transaction(
                date=date(2024, 1, 1), amount=1000, type=TransactionType.EXPENSE, category=ExpenseCategory.INVENTORY
            ),
        ]
        dataset = FinancialDataset(
            transactions=transactions, period_start=date(2024, 1, 1), period_end=date(2024, 12, 31)
        )

        result = RestaurantAnalyzer.analyze(dataset, annual_revenue=0)

        # Should estimate revenue from expenses
        assert result is not None
        assert result.total_revenue > 0  # Estimated

    def test_missing_categories(self) -> None:
        """Handle transactions with no category."""
        transactions = [
            Transaction(date=date(2024, 1, 1), amount=1_000_000, type=TransactionType.INCOME),
            Transaction(date=date(2024, 1, 1), amount=50_000, type=TransactionType.EXPENSE),  # No category
        ]
        dataset = FinancialDataset(
            transactions=transactions, period_start=date(2024, 1, 1), period_end=date(2024, 12, 31)
        )

        result = RestaurantAnalyzer.analyze(dataset, annual_revenue=1_000_000)

        assert result is not None
        # Should be placed in "other" bucket
