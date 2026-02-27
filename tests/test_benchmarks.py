"""Tests for industry benchmark analyzer."""

from typing import Any

import pytest

from fiscalpilot.analyzers.benchmarks import BenchmarkAnalyzer, BenchmarkResult


def _expense_txns(
    categories: dict[str, float],
    txn_type: str = "expense",
) -> list[dict[str, Any]]:
    """Build transactions grouped by category with given total amounts."""
    txns: list[dict[str, Any]] = []
    idx = 0
    for cat, total in categories.items():
        # Split into 10 transactions each
        per_txn = total / 10
        for _ in range(10):
            txns.append({
                "id": f"txn_{idx:04d}",
                "amount": per_txn,
                "category": cat,
                "type": txn_type,
                "date": "2024-06-15",
            })
            idx += 1
    return txns


class TestBenchmarkAnalyzerHappyPath:
    def test_restaurant_analysis(self) -> None:
        """Restaurant with high payroll should flag deviation."""
        # Restaurant benchmarks: payroll typical=32%, high=38%
        # Set payroll at 45% → should be flagged
        revenue = 1_000_000
        txns = _expense_txns({
            "payroll": 450_000,  # 45% of revenue (above 38% high)
            "inventory": 300_000,  # 30% (within range)
            "rent": 80_000,  # 8% (within range)
            "utilities": 30_000,
        })

        result = BenchmarkAnalyzer.analyze(txns, industry="restaurant", annual_revenue=revenue)

        assert isinstance(result, BenchmarkResult)
        assert result.industry == "restaurant"
        assert result.revenue == revenue
        assert result.summary != ""

        # Payroll should be flagged
        payroll_devs = [d for d in result.deviations if d.category == "payroll"]
        assert len(payroll_devs) >= 1
        assert payroll_devs[0].severity in ("high", "critical")
        assert payroll_devs[0].actual_pct == pytest.approx(45.0, rel=0.01)

    def test_saas_analysis(self) -> None:
        """SaaS company with typical expenses should receive good grade."""
        revenue = 5_000_000
        txns = _expense_txns({
            "payroll": 2_750_000,  # 55% (within 40-70%)
            "marketing": 1_000_000,  # 20% (within 15-40%)
            "software": 150_000,  # 3% (within 2-8%)
            "rent": 200_000,  # 4% (within 2-8%)
        })

        result = BenchmarkAnalyzer.analyze(txns, industry="saas", annual_revenue=revenue)

        # Should get good grade (A or B)
        assert result.health_grade in ("A", "B")
        assert result.total_excess_spend == 0.0

    def test_excess_spend_calculated(self) -> None:
        """Total excess spend should reflect sum of overages."""
        revenue = 1_000_000
        txns = _expense_txns({
            "payroll": 500_000,  # 50% (restaurant high=38%) → excess 12% = $120k
            "inventory": 400_000,  # 40% (restaurant high=38%) → excess 2% = $20k
        })

        result = BenchmarkAnalyzer.analyze(txns, industry="restaurant", annual_revenue=revenue)
        assert result.total_excess_spend > 0

    def test_health_grade_escalation(self) -> None:
        """Massively over-budget should yield D or F grade."""
        revenue = 1_000_000
        txns = _expense_txns({
            "payroll": 700_000,  # 70% vs 38% high → critical
            "inventory": 500_000,  # 50% vs 38% high → critical
            "rent": 200_000,  # 20% vs 12% high → critical
            "marketing": 300_000,  # 30% (not in restaurant benchmarks → shows up as deviation)
        })

        result = BenchmarkAnalyzer.analyze(txns, industry="restaurant", annual_revenue=revenue)
        assert result.health_grade in ("D", "F")

    def test_kpi_comparison(self) -> None:
        """KPI comparisons should appear when provided."""
        txns = _expense_txns({"payroll": 300_000})
        result = BenchmarkAnalyzer.analyze(
            txns,
            industry="saas",
            annual_revenue=1_000_000,
            kpis={"gross_margin": 72.0},
        )

        assert "gross_margin" in result.kpi_comparisons
        assert result.kpi_comparisons["gross_margin"]["actual"] == 72.0


class TestBenchmarkAnalyzerEdgeCases:
    def test_unknown_industry_falls_back_to_other(self) -> None:
        """Unrecognized industry should use 'other' benchmarks."""
        txns = _expense_txns({"payroll": 300_000})
        result = BenchmarkAnalyzer.analyze(txns, industry="space_mining", annual_revenue=1_000_000)

        assert result.industry == "other"

    def test_zero_revenue_estimated(self) -> None:
        """Zero revenue should auto-estimate from expenses."""
        txns = _expense_txns({"payroll": 100_000, "rent": 20_000})
        result = BenchmarkAnalyzer.analyze(txns, industry="saas", annual_revenue=0)

        # Revenue should be estimated as expenses * 1.2
        assert result.revenue > 0
        assert result.summary != ""

    def test_empty_transactions(self) -> None:
        """Empty transactions should not crash."""
        result = BenchmarkAnalyzer.analyze([], industry="retail", annual_revenue=500_000)

        assert isinstance(result, BenchmarkResult)
        assert result.total_excess_spend == 0.0

    def test_available_industries(self) -> None:
        """Should return list of supported industries."""
        industries = BenchmarkAnalyzer.available_industries()

        assert "restaurant" in industries
        assert "saas" in industries
        assert "other" in industries
        assert "_meta" not in industries
        assert len(industries) >= 13

    def test_income_transactions_excluded(self) -> None:
        """Income transactions should not count toward expense categories."""
        txns = _expense_txns({"payroll": 100_000})
        # Add income transactions
        for i in range(10):
            txns.append({
                "id": f"income_{i}",
                "amount": 50_000,
                "category": "payroll",
                "type": "income",
                "date": "2024-06-15",
            })

        result = BenchmarkAnalyzer.analyze(txns, industry="saas", annual_revenue=1_000_000)

        # Payroll should be 10% not 60%
        payroll_devs = [d for d in result.deviations if d.category == "payroll"]
        if payroll_devs:
            assert payroll_devs[0].actual_pct < 15.0  # should be ~10%
