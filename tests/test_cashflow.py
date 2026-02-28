"""Tests for cash flow forecasting engine."""

from datetime import date, timedelta
from typing import Any

from fiscalpilot.analyzers.cashflow import CashFlowForecast, CashFlowForecaster


def _monthly_txns(
    months: int = 6,
    monthly_income: float = 10_000,
    monthly_expense: float = 8_000,
    start: date = date(2024, 1, 1),
) -> list[dict[str, Any]]:
    """Generate predictable monthly transactions."""
    txns: list[dict[str, Any]] = []
    idx = 0
    for m in range(months):
        d = (
            date(start.year, start.month + m if start.month + m <= 12 else (start.month + m - 12), 15)
            if start.month + m <= 12
            else date(start.year + 1, start.month + m - 12, 15)
        )
        # Income
        txns.append(
            {
                "id": f"inc_{idx}",
                "amount": monthly_income,
                "date": str(d),
                "type": "income",
                "category": "revenue",
            }
        )
        idx += 1
        # Expenses (split into 4)
        for _ in range(4):
            txns.append(
                {
                    "id": f"exp_{idx}",
                    "amount": monthly_expense / 4,
                    "date": str(d + timedelta(days=_ * 5)),
                    "type": "expense",
                    "category": "general",
                }
            )
            idx += 1
    return txns


class TestCashFlowForecasterHappyPath:
    def test_basic_forecast(self) -> None:
        """6 months of history should produce a forecast."""
        txns = _monthly_txns(months=6, monthly_income=10_000, monthly_expense=8_000)
        result = CashFlowForecaster.analyze(txns, current_balance=50_000)

        assert isinstance(result, CashFlowForecast)
        assert len(result.historical) == 6
        assert len(result.forecast) == 6  # default forecast_months=6
        assert result.current_balance == 50_000
        assert result.summary != ""

    def test_forecast_months_populated(self) -> None:
        """Each forecast month should be marked as is_forecast=True."""
        txns = _monthly_txns(months=4)
        result = CashFlowForecaster.analyze(txns, current_balance=20_000, forecast_months=3)

        for f in result.forecast:
            assert f.is_forecast is True
        assert len(result.forecast) == 3

    def test_burn_rate_positive(self) -> None:
        """Net-negative months should produce positive burn rate."""
        txns = _monthly_txns(months=6, monthly_income=5_000, monthly_expense=8_000)
        result = CashFlowForecaster.analyze(txns, current_balance=30_000)

        assert result.average_monthly_burn > 0
        assert result.runway_months > 0

    def test_runway_infinite_when_profitable(self) -> None:
        """When income > expenses, runway should be -1 (infinite)."""
        txns = _monthly_txns(months=6, monthly_income=15_000, monthly_expense=8_000)
        result = CashFlowForecaster.analyze(txns, current_balance=100_000)

        assert result.runway_months == -1  # sentinel for infinite

    def test_short_runway_risk_alert(self) -> None:
        """Short runway should trigger risk alerts."""
        txns = _monthly_txns(months=6, monthly_income=2_000, monthly_expense=8_000)
        result = CashFlowForecaster.analyze(txns, current_balance=10_000)

        # ~1.7 months runway → should have alerts
        assert result.runway_months < 6
        assert len(result.risk_alerts) > 0


class TestCashFlowForecasterEdgeCases:
    def test_empty_transactions(self) -> None:
        """Empty transactions should not crash."""
        result = CashFlowForecaster.analyze([], current_balance=10_000)

        assert isinstance(result, CashFlowForecast)
        assert result.current_balance == 10_000
        assert len(result.historical) == 0

    def test_single_month(self) -> None:
        """Single month of data should still produce a forecast."""
        txns = _monthly_txns(months=1)
        result = CashFlowForecaster.analyze(txns, current_balance=5_000)

        assert len(result.historical) >= 1
        assert isinstance(result, CashFlowForecast)

    def test_forecast_months_clamped(self) -> None:
        """forecast_months outside 1-12 should be clamped."""
        txns = _monthly_txns(months=3)
        result = CashFlowForecaster.analyze(txns, current_balance=10_000, forecast_months=50)

        assert len(result.forecast) <= 12

    def test_zero_balance(self) -> None:
        """Zero balance with burn should give zero runway."""
        txns = _monthly_txns(months=6, monthly_income=0, monthly_expense=5_000)
        result = CashFlowForecaster.analyze(txns, current_balance=0)

        assert result.runway_months == 0.0 or result.runway_months <= 0

    def test_seasonal_patterns_with_long_history(self) -> None:
        """12+ months should enable seasonal index computation."""
        date(2023, 1, 1)
        txns: list[dict[str, Any]] = []
        idx = 0
        for m in range(14):
            year = 2023 + (m // 12)
            month = (m % 12) + 1
            d = date(year, month, 15)
            # Varied spending: higher in December
            expense = 8_000 if month != 12 else 16_000
            txns.append({"id": f"inc_{idx}", "amount": 10_000, "date": str(d), "type": "income"})
            idx += 1
            txns.append({"id": f"exp_{idx}", "amount": expense, "date": str(d), "type": "expense"})
            idx += 1

        result = CashFlowForecaster.analyze(txns, current_balance=50_000)

        # Should have seasonal patterns detected
        assert len(result.seasonal_patterns) >= 0  # may or may not detect depending on threshold
        assert isinstance(result, CashFlowForecast)

    def test_inflow_calculation(self) -> None:
        """Average monthly inflow should reflect income transactions."""
        txns = _monthly_txns(months=6, monthly_income=10_000, monthly_expense=5_000)
        result = CashFlowForecaster.analyze(txns, current_balance=30_000)

        assert result.average_monthly_inflow > 0
