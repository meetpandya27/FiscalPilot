"""Tests for tax optimization engine."""

from typing import Any

import pytest

from fiscalpilot.analyzers.tax_optimizer import TaxOptimizationResult, TaxOptimizer


def _make_txns(entries: list[tuple[str, float, str]]) -> list[dict[str, Any]]:
    """Build transaction dicts from (category, amount, description) tuples."""
    return [
        {
            "id": f"txn_{i:04d}",
            "amount": amt,
            "category": cat,
            "type": "expense",
            "date": "2024-06-15",
            "description": desc,
            "vendor": f"vendor_{i}",
        }
        for i, (cat, amt, desc) in enumerate(entries)
    ]


class TestTaxOptimizerHappyPath:
    def test_miscategorized_detection(self) -> None:
        """Transactions with deductible keywords in 'other' category should be flagged."""
        txns = _make_txns([
            ("other", 2_000, "QuickBooks subscription"),
            ("other", 500, "Zoom Pro plan"),
            ("other", 300, "Adobe Creative Cloud"),
            ("other", 200, "Slack annual"),
            ("other", 100, "Microsoft 365"),
            # Above $100 total for the group
        ])

        result = TaxOptimizer.analyze(txns, annual_revenue=200_000)

        assert isinstance(result, TaxOptimizationResult)
        miscat = [o for o in result.opportunities if o.category == "miscategorized"]
        assert len(miscat) >= 1
        assert result.total_estimated_savings > 0

    def test_section_179_depreciation(self) -> None:
        """Equipment purchases >= $500 should trigger Section 179 opportunity."""
        txns = _make_txns([
            ("equipment", 15_000, "New server hardware"),
            ("equipment", 5_000, "Office furniture"),
            ("payroll", 50_000, "Employee wages"),
        ])

        result = TaxOptimizer.analyze(txns, annual_revenue=500_000)

        depreciation = [o for o in result.opportunities if o.category == "depreciation"]
        assert len(depreciation) >= 1
        assert depreciation[0].estimated_savings > 0

    def test_entity_structure_for_sole_prop(self) -> None:
        """Sole prop with high income should get S-Corp suggestion."""
        txns = _make_txns([
            ("payroll", 60_000, "Salary"),
            ("rent", 12_000, "Office rent"),
            ("software", 3_000, "Tools"),
        ])

        result = TaxOptimizer.analyze(
            txns,
            annual_revenue=200_000,
            entity_type="sole_prop",
        )

        entity = [o for o in result.opportunities if o.category == "entity_structure"]
        assert len(entity) >= 1
        assert "s-corp" in entity[0].description.lower() or "s corp" in entity[0].description.lower()

    def test_retirement_opportunity(self) -> None:
        """No retirement plan + income > $30k should suggest SEP IRA."""
        txns = _make_txns([
            ("payroll", 40_000, "Salary"),
            ("rent", 6_000, "Rent"),
        ])

        result = TaxOptimizer.analyze(
            txns,
            annual_revenue=100_000,
            has_retirement_plan=False,
        )

        retirement = [o for o in result.opportunities if o.category == "retirement"]
        assert len(retirement) >= 1

    def test_meal_deduction(self) -> None:
        """Meals category should trigger 50% deduction opportunity."""
        txns = _make_txns([
            ("meals", 50, "Client lunch 1"),
            ("meals", 50, "Client lunch 2"),
            ("meals", 50, "Team dinner"),
            ("meals", 50, "Client lunch 3"),
            ("meals", 50, "Networking dinner"),
        ])

        result = TaxOptimizer.analyze(txns, annual_revenue=100_000)

        meal_opps = [o for o in result.opportunities if o.category == "documentation"]
        # Meals total = $250, above $200 threshold
        assert len(meal_opps) >= 1

    def test_total_savings_aggregation(self) -> None:
        """total_estimated_savings should be sum of individual opportunities."""
        txns = _make_txns([
            ("other", 5_000, "QuickBooks subscription"),
            ("other", 3_000, "AWS hosting"),
            ("equipment", 20_000, "Server purchase"),
            ("meals", 500, "Client dinners"),
        ])

        result = TaxOptimizer.analyze(txns, annual_revenue=200_000)

        individual_sum = sum(o.estimated_savings for o in result.opportunities)
        assert result.total_estimated_savings == pytest.approx(individual_sum, rel=0.01)


class TestTaxOptimizerEdgeCases:
    def test_empty_transactions(self) -> None:
        """No transactions with zero revenue should produce zero opportunities."""
        result = TaxOptimizer.analyze([], annual_revenue=0)

        assert isinstance(result, TaxOptimizationResult)
        assert result.total_estimated_savings == 0.0
        assert len(result.opportunities) == 0

    def test_zero_revenue(self) -> None:
        """Zero revenue should skip revenue-dependent checks gracefully."""
        txns = _make_txns([
            ("payroll", 30_000, "Wages"),
            ("rent", 5_000, "Office"),
        ])

        result = TaxOptimizer.analyze(txns, annual_revenue=0)

        # Should not crash; missing deduction checks skipped
        assert isinstance(result, TaxOptimizationResult)

    def test_s_corp_skips_entity_structure(self) -> None:
        """S-Corp entities should NOT get entity structure suggestion."""
        txns = _make_txns([
            ("payroll", 100_000, "Salary"),
        ])

        result = TaxOptimizer.analyze(
            txns,
            annual_revenue=300_000,
            entity_type="s_corp",
        )

        entity = [o for o in result.opportunities if o.category == "entity_structure"]
        assert len(entity) == 0

    def test_has_retirement_plan_skips_retirement(self) -> None:
        """If user already has a retirement plan, skip that suggestion."""
        txns = _make_txns([("payroll", 40_000, "Salary")])

        result = TaxOptimizer.analyze(
            txns,
            annual_revenue=100_000,
            has_retirement_plan=True,
        )

        retirement = [o for o in result.opportunities if o.category == "retirement"]
        assert len(retirement) == 0

    def test_properly_categorized_not_flagged(self) -> None:
        """Transactions already in correct categories shouldn't be flagged as miscategorized."""
        txns = _make_txns([
            ("software", 2_000, "QuickBooks"),
            ("travel", 1_500, "Flight"),
            ("insurance", 3_000, "Liability coverage"),
        ])

        result = TaxOptimizer.analyze(txns, annual_revenue=100_000)

        miscat = [o for o in result.opportunities if o.category == "miscategorized"]
        assert len(miscat) == 0

    def test_low_income_skips_entity_retirement(self) -> None:
        """Below thresholds, entity and retirement checks should not fire."""
        txns = _make_txns([
            ("payroll", 5_000, "Part-time work"),
        ])

        result = TaxOptimizer.analyze(
            txns,
            annual_revenue=10_000,
            entity_type="sole_prop",
            has_retirement_plan=False,
        )

        entity = [o for o in result.opportunities if o.category == "entity_structure"]
        retirement = [o for o in result.opportunities if o.category == "retirement"]
        assert len(entity) == 0
        assert len(retirement) == 0

    def test_effective_tax_rate(self) -> None:
        """Result should carry the configured tax rate."""
        result = TaxOptimizer.analyze([], annual_revenue=0, tax_rate=0.30)
        assert result.effective_tax_rate == 0.30

    def test_uncategorized_spend_tracked(self) -> None:
        """Transactions with 'other'/'miscellaneous'/'' categories count as uncategorized."""
        txns = _make_txns([
            ("other", 1_000, "Random stuff"),
            ("miscellaneous", 500, "Misc purchase"),
            ("", 300, "Unknown"),
            ("payroll", 5_000, "Wages"),
        ])

        result = TaxOptimizer.analyze(txns, annual_revenue=100_000)
        assert result.uncategorized_spend >= 1_800
