"""
Industry Benchmark Analyzer — compare spend ratios against industry norms.

Compares a company's actual expense-category percentages against published
industry benchmarks and flags significant deviations (above "high" or
below "low" thresholds).

No LLM calls — produces structured deviation data that agents can reference.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("fiscalpilot.analyzers.benchmarks")

_BENCHMARKS: dict[str, Any] | None = None


def _load_benchmarks() -> dict[str, Any]:
    """Lazy-load the industry benchmarks JSON."""
    global _BENCHMARKS
    if _BENCHMARKS is None:
        data_path = Path(__file__).parent.parent / "data" / "industry_benchmarks.json"
        with open(data_path) as f:
            _BENCHMARKS = json.load(f)
    return _BENCHMARKS


@dataclass
class BenchmarkDeviation:
    """A single expense-category deviation from benchmark."""

    category: str
    actual_pct: float
    benchmark_low: float
    benchmark_typical: float
    benchmark_high: float
    deviation_from_typical: float  # positive = over, negative = under
    severity: str  # "critical", "high", "medium", "low", "ok"
    annual_excess: float  # Estimated annual $ overspend (positive) or underspend (negative)
    recommendation: str


@dataclass
class BenchmarkResult:
    """Complete benchmark comparison result."""

    industry: str
    industry_display: str
    revenue: float
    deviations: list[BenchmarkDeviation] = field(default_factory=list)
    kpi_comparisons: dict[str, dict[str, float]] = field(default_factory=dict)
    total_excess_spend: float = 0.0
    health_grade: str = "B"  # A, B, C, D, F
    summary: str = ""


class BenchmarkAnalyzer:
    """Compare company financials against industry benchmarks."""

    @classmethod
    def analyze(
        cls,
        transactions: list[dict[str, Any]],
        industry: str,
        annual_revenue: float,
        *,
        kpis: dict[str, float] | None = None,
    ) -> BenchmarkResult:
        """Run benchmark comparison.

        Args:
            transactions: Transaction dicts with "amount", "type", "category" keys.
            industry: Industry identifier matching keys in benchmarks JSON.
            annual_revenue: Annual revenue for ratio calculations.
            kpis: Optional dict of actual KPI values to compare (e.g. {"gross_margin": 62.0}).

        Returns:
            BenchmarkResult with all deviations and recommendations.
        """
        benchmarks = _load_benchmarks()

        # Normalize industry key
        industry_key = industry.lower().replace(" ", "_").replace("-", "_")
        industry_data = benchmarks.get(industry_key)
        if industry_data is None:
            industry_data = benchmarks.get("other", {})
            industry_key = "other"

        display_name = industry_data.get("display_name", industry_key.replace("_", " ").title())
        expense_benchmarks = industry_data.get("expense_ratios", {})
        kpi_benchmarks = industry_data.get("kpis", {})

        # Compute actual expense ratios
        category_spend = cls._compute_category_spend(transactions)
        total_expenses = sum(category_spend.values())

        if annual_revenue <= 0:
            annual_revenue = max(total_expenses * 1.2, 1)  # Fallback estimate

        # Compare each category
        deviations: list[BenchmarkDeviation] = []
        total_excess = 0.0

        for category, benchmark in expense_benchmarks.items():
            actual_spend = category_spend.get(category, 0.0)
            actual_pct = (actual_spend / annual_revenue) * 100

            low = benchmark["low"]
            typical = benchmark["typical"]
            high = benchmark["high"]

            deviation = actual_pct - typical
            severity = cls._assess_severity(actual_pct, low, typical, high)
            excess = max(0, (actual_pct - high) / 100 * annual_revenue) if actual_pct > high else 0
            total_excess += excess

            recommendation = cls._generate_recommendation(category, actual_pct, low, typical, high, annual_revenue)

            if severity != "ok":
                deviations.append(
                    BenchmarkDeviation(
                        category=category,
                        actual_pct=round(actual_pct, 2),
                        benchmark_low=low,
                        benchmark_typical=typical,
                        benchmark_high=high,
                        deviation_from_typical=round(deviation, 2),
                        severity=severity,
                        annual_excess=round(excess, 2),
                        recommendation=recommendation,
                    )
                )

        # Sort by severity priority, then by excess
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        deviations.sort(key=lambda d: (severity_order.get(d.severity, 9), -d.annual_excess))

        # KPI comparisons
        kpi_comparisons: dict[str, dict[str, float]] = {}
        if kpis:
            for kpi_name, actual_val in kpis.items():
                if kpi_name in kpi_benchmarks:
                    bench = kpi_benchmarks[kpi_name]
                    kpi_comparisons[kpi_name] = {
                        "actual": actual_val,
                        "low": bench["low"],
                        "typical": bench["typical"],
                        "high": bench["high"],
                        "deviation": round(actual_val - bench["typical"], 2),
                    }

        health_grade = cls._compute_grade(deviations, total_excess, annual_revenue)
        summary = cls._build_summary(
            display_name, deviations, kpi_comparisons, total_excess, health_grade, annual_revenue
        )

        return BenchmarkResult(
            industry=industry_key,
            industry_display=display_name,
            revenue=annual_revenue,
            deviations=deviations,
            kpi_comparisons=kpi_comparisons,
            total_excess_spend=round(total_excess, 2),
            health_grade=health_grade,
            summary=summary,
        )

    @classmethod
    def available_industries(cls) -> list[str]:
        """Return list of supported industry keys."""
        benchmarks = _load_benchmarks()
        return [k for k in benchmarks if k != "_meta"]

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _compute_category_spend(transactions: list[dict[str, Any]]) -> dict[str, float]:
        """Aggregate spend by expense category."""
        spend: dict[str, float] = {}
        for t in transactions:
            txn_type = t.get("type", "")
            # Handle both enum instances and plain strings
            txn_type_str = txn_type.value if hasattr(txn_type, "value") else str(txn_type)
            if txn_type_str not in ("expense", "payroll", "tax"):
                continue
            category = t.get("category") or "other"
            # Handle both enum instances and plain strings
            cat_str = category.value if hasattr(category, "value") else str(category)
            amount = abs(float(t.get("amount", 0)))
            spend[cat_str] = spend.get(cat_str, 0) + amount
        return spend

    @staticmethod
    def _assess_severity(actual: float, low: float, typical: float, high: float) -> str:
        """Classify the severity of a deviation."""
        if actual > high * 1.5:
            return "critical"
        if actual > high:
            return "high"
        if actual > typical * 1.15:  # 15% above typical
            return "medium"
        if actual < low * 0.5 and low > 0:
            return "medium"  # Suspiciously low
        if actual < low and low > 0:
            return "low"
        return "ok"

    @staticmethod
    def _generate_recommendation(
        category: str,
        actual_pct: float,
        low: float,
        typical: float,
        high: float,
        revenue: float,
    ) -> str:
        """Generate a specific recommendation for a deviation."""
        cat_label = category.replace("_", " ").title()

        if actual_pct > high * 1.5:
            excess = (actual_pct - high) / 100 * revenue
            return (
                f"CRITICAL: {cat_label} at {actual_pct:.1f}% of revenue is far above the industry "
                f"ceiling of {high:.1f}%. This represents ~${excess:,.0f}/yr in excess spending. "
                f"Immediately audit this category for duplicate charges, overpricing, or optimization opportunities."
            )
        if actual_pct > high:
            excess = (actual_pct - high) / 100 * revenue
            return (
                f"{cat_label} at {actual_pct:.1f}% exceeds the industry high of {high:.1f}% "
                f"(~${excess:,.0f}/yr above benchmark). Review vendor contracts and negotiate better terms."
            )
        if actual_pct > typical * 1.15:
            excess = (actual_pct - typical) / 100 * revenue
            return (
                f"{cat_label} at {actual_pct:.1f}% is above the typical {typical:.1f}%. "
                f"Potential to save ~${excess:,.0f}/yr by bringing spend in line with peers."
            )
        if actual_pct < low * 0.5 and low > 0:
            return (
                f"{cat_label} at {actual_pct:.1f}% is suspiciously below the industry low of "
                f"{low:.1f}%. Verify data completeness — this may indicate uncategorized spend "
                f"or underinvestment that could hurt growth."
            )
        if actual_pct < low and low > 0:
            return (
                f"{cat_label} at {actual_pct:.1f}% is below the industry floor of {low:.1f}%. "
                f"Confirm whether this reflects genuine efficiency or missing data."
            )
        return ""

    @staticmethod
    def _compute_grade(deviations: list[BenchmarkDeviation], total_excess: float, revenue: float) -> str:
        """Compute an overall health grade A-F."""
        critical = sum(1 for d in deviations if d.severity == "critical")
        high = sum(1 for d in deviations if d.severity == "high")
        medium = sum(1 for d in deviations if d.severity == "medium")

        excess_pct = (total_excess / max(revenue, 1)) * 100

        score = 100
        score -= critical * 20
        score -= high * 10
        score -= medium * 5
        score -= excess_pct * 2

        if score >= 90:
            return "A"
        if score >= 80:
            return "B"
        if score >= 65:
            return "C"
        if score >= 50:
            return "D"
        return "F"

    @staticmethod
    def _build_summary(
        industry_name: str,
        deviations: list[BenchmarkDeviation],
        kpis: dict[str, dict[str, float]],
        total_excess: float,
        grade: str,
        revenue: float,
    ) -> str:
        lines = [
            f"Industry Benchmark Analysis — {industry_name}:",
            f"  Health Grade: {grade}",
            f"  Deviations found: {len(deviations)}",
            f"  Estimated excess spend: ${total_excess:,.0f}/yr",
        ]
        if deviations:
            lines.append("  Top deviations:")
            for d in deviations[:5]:
                lines.append(
                    f"    {d.category.replace('_', ' ').title()}: {d.actual_pct:.1f}% "
                    f"(benchmark: {d.benchmark_low:.0f}-{d.benchmark_high:.0f}%) "
                    f"[{d.severity.upper()}]"
                )
        if kpis:
            lines.append("  KPI comparisons:")
            for name, vals in kpis.items():
                status = "OK" if vals["low"] <= vals["actual"] <= vals["high"] else "DEVIATION"
                lines.append(
                    f"    {name.replace('_', ' ').title()}: {vals['actual']:.1f}% "
                    f"(range: {vals['low']:.0f}-{vals['high']:.0f}%) [{status}]"
                )
        return "\n".join(lines)
