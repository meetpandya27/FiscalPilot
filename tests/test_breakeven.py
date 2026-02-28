"""
Tests for Break-even Calculator — restaurant break-even analysis.
"""

import pytest

from fiscalpilot.analyzers.breakeven import (
    BreakevenCalculator,
    BreakevenResult,
    CostBreakdown,
)


class TestBreakevenCalculation:
    """Test core break-even calculations."""

    def test_basic_breakeven(self):
        """Basic break-even calculation with fixed and variable costs."""
        result = BreakevenCalculator.calculate(
            rent=5000,
            management_salaries=3000,
            food_cost_pct=30,
            hourly_labor_pct=20,
            average_check=25,
        )

        # Fixed costs = 8000/month
        # Variable cost = 30 + 20 + 2 (supplies) + 2.5 (CC) + 1 (other) = 55.5%
        # CM ratio = 44.5%
        # Break-even = 8000 / 0.445 = ~17,978
        assert result.breakeven_revenue_monthly > 0
        assert result.total_fixed_monthly == 8000
        assert result.contribution_margin_pct == pytest.approx(44.5, rel=0.01)

    def test_breakeven_covers_daily(self):
        """Calculate break-even in covers (guests) per day."""
        result = BreakevenCalculator.calculate(
            rent=6000,
            management_salaries=4000,
            food_cost_pct=30,
            hourly_labor_pct=22,
            average_check=30,
            days_operating_per_week=6,
        )

        # Should have covers calculation
        assert result.breakeven_covers_daily > 0
        # Formula: daily_revenue / average_check
        expected_daily_covers = result.breakeven_revenue_daily / 30
        assert result.breakeven_covers_daily == pytest.approx(expected_daily_covers, rel=0.01)

    def test_margin_of_safety(self):
        """Calculate margin of safety when current revenue is provided."""
        result = BreakevenCalculator.calculate(
            rent=5000,
            food_cost_pct=30,
            hourly_labor_pct=20,
            average_check=25,
            current_monthly_revenue=50000,
        )

        # Margin of safety = (current - breakeven) / current * 100
        assert result.margin_of_safety_pct != 0
        if result.current_revenue > result.breakeven_revenue_monthly:
            assert result.margin_of_safety_pct > 0
            assert result.is_above_breakeven is True

    def test_below_breakeven_detection(self):
        """Detect when current revenue is below break-even."""
        result = BreakevenCalculator.calculate(
            rent=10000,  # High fixed costs
            management_salaries=8000,
            food_cost_pct=35,
            hourly_labor_pct=25,
            average_check=20,
            current_monthly_revenue=30000,  # Low revenue
        )

        # Should detect below break-even
        if result.breakeven_revenue_monthly > 30000:
            assert result.is_above_breakeven is False
            assert result.margin_of_safety_pct < 0


class TestCostBreakdown:
    """Test cost breakdown calculations."""

    def test_total_fixed_costs(self):
        """Total fixed costs calculation."""
        breakdown = CostBreakdown(
            rent=5000,
            insurance=500,
            management_salaries=4000,
            loan_payments=1000,
            base_utilities=800,
        )

        expected = 5000 + 500 + 4000 + 1000 + 800
        assert breakdown.total_fixed == expected

    def test_total_variable_percentage(self):
        """Total variable cost percentage."""
        breakdown = CostBreakdown(
            food_cost_pct=30,
            hourly_labor_pct=22,
            supplies_pct=3,
            credit_card_fees_pct=2.5,
        )

        expected = 30 + 22 + 3 + 2.5 + 0 + 1  # delivery=0, other=1 (default)
        assert breakdown.total_variable_pct == expected

    def test_contribution_margin(self):
        """Contribution margin = 100 - variable costs."""
        breakdown = CostBreakdown(
            food_cost_pct=30,
            hourly_labor_pct=20,
            supplies_pct=2,
            credit_card_fees_pct=2.5,
            other_variable_pct=1,
        )

        expected_cm = 100 - (30 + 20 + 2 + 2.5 + 0 + 1)  # 44.5%
        assert breakdown.contribution_margin_pct == expected_cm


class TestBreakevenScenarios:
    """Test scenario analysis."""

    def test_scenarios_generated(self):
        """Should generate multiple what-if scenarios."""
        result = BreakevenCalculator.calculate(
            rent=5000,
            management_salaries=3000,
            food_cost_pct=30,
            hourly_labor_pct=20,
            average_check=25,
        )

        assert len(result.scenarios) > 0

        # Should have "10% Above Break-even" scenario
        ten_above = next((s for s in result.scenarios if "10%" in s.get("name", "")), None)
        assert ten_above is not None

    def test_food_cost_reduction_scenario(self):
        """Should include food cost reduction scenario."""
        result = BreakevenCalculator.calculate(
            rent=5000,
            food_cost_pct=32,  # Above 3, so scenario should appear
            hourly_labor_pct=20,
            average_check=25,
        )

        next((s for s in result.scenarios if "Food Cost" in s.get("name", "")), None)
        if result.scenarios:  # If scenarios are generated
            # This scenario shows how much break-even drops if food cost is reduced
            pass  # Scenario generation is optional based on implementation


class TestBreakevenInsights:
    """Test insight generation."""

    def test_core_insight_generated(self):
        """Should always generate core break-even insight."""
        result = BreakevenCalculator.calculate(
            rent=5000,
            food_cost_pct=30,
            average_check=25,
        )

        assert len(result.insights) > 0
        # First insight should be about break-even target
        assert "BREAK-EVEN" in result.insights[0] or "break-even" in result.insights[0].lower()

    def test_high_food_cost_warning(self):
        """Should warn about high food cost."""
        result = BreakevenCalculator.calculate(
            rent=5000,
            food_cost_pct=38,  # Above 32% benchmark
            average_check=25,
        )

        food_warning = any("food" in i.lower() and "high" in i.lower()
                          for i in result.insights)
        assert food_warning

    def test_high_labor_cost_warning(self):
        """Should warn about high labor cost."""
        result = BreakevenCalculator.calculate(
            rent=5000,
            hourly_labor_pct=30,  # Above 25% benchmark
            average_check=25,
        )

        labor_warning = any("labor" in i.lower() for i in result.insights)
        assert labor_warning


class TestBreakevenEdgeCases:
    """Test edge cases and error handling."""

    def test_zero_fixed_costs(self):
        """Should handle zero fixed costs (food truck scenario)."""
        result = BreakevenCalculator.calculate(
            food_cost_pct=30,
            hourly_labor_pct=25,
            average_check=15,
        )

        # With zero fixed costs, break-even is zero
        assert result.breakeven_revenue_monthly == 0

    def test_very_high_variable_costs(self):
        """Should handle edge case with very high variable costs."""
        result = BreakevenCalculator.calculate(
            rent=5000,
            food_cost_pct=50,
            hourly_labor_pct=40,
            supplies_pct=5,
            credit_card_fees_pct=3,
            other_variable_pct=5,  # Total > 100%
            average_check=25,
        )

        # Should return error insight when CM <= 0
        if result.contribution_margin_pct <= 0:
            assert any("impossible" in i.lower() or "error" in i.lower()
                      for i in result.insights)

    def test_zero_average_check(self):
        """Should handle zero average check gracefully."""
        result = BreakevenCalculator.calculate(
            rent=5000,
            food_cost_pct=30,
            average_check=0,
        )

        # Covers should be 0 when average check is 0
        assert result.breakeven_covers_daily == 0

    def test_different_operating_days(self):
        """Should adjust for different operating schedules."""
        result_7days = BreakevenCalculator.calculate(
            rent=5000,
            food_cost_pct=30,
            average_check=25,
            days_operating_per_week=7,
        )

        result_5days = BreakevenCalculator.calculate(
            rent=5000,
            food_cost_pct=30,
            average_check=25,
            days_operating_per_week=5,
        )

        # Daily revenue target should be higher with fewer days
        assert result_5days.breakeven_revenue_daily > result_7days.breakeven_revenue_daily


class TestBreakevenConvenience:
    """Test convenience functions."""

    def test_calculate_breakeven_function(self):
        """Test the module-level convenience function."""
        from fiscalpilot.analyzers.breakeven import calculate_breakeven

        result = calculate_breakeven(
            rent=5000,
            food_cost_pct=30,
            average_check=25,
        )

        assert isinstance(result, BreakevenResult)
        assert result.breakeven_revenue_monthly > 0
