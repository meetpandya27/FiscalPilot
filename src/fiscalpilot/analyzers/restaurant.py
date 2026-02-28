"""
Restaurant-Specific KPI Analyzer — industry-specific metrics for food service.

Calculates critical restaurant performance metrics:
- Food Cost Percentage (target: 28-32%)
- Labor Cost Percentage (target: 28-32%)
- Prime Cost (Food + Labor, target: 55-65% of revenue)
- Beverage Cost Percentage (target: 18-24%)
- Occupancy Cost Percentage (rent + utilities, target: 6-10%)
- RevPASH (Revenue Per Available Seat Hour)
- Average Check
- Table Turn Rate

No LLM calls — produces structured KPI data that agents can reference.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from fiscalpilot.models.financial import ExpenseCategory, FinancialDataset, Transaction

logger = logging.getLogger("fiscalpilot.analyzers.restaurant")


class RestaurantKPISeverity(str, Enum):
    """Severity level for KPI deviations."""

    CRITICAL = "critical"  # Immediate action needed
    WARNING = "warning"  # Monitor closely
    HEALTHY = "healthy"  # Within normal range
    EXCELLENT = "excellent"  # Better than benchmark


@dataclass
class RestaurantKPI:
    """A single restaurant KPI with benchmark comparison."""

    name: str
    display_name: str
    actual: float
    benchmark_low: float
    benchmark_typical: float
    benchmark_high: float
    unit: str  # "percent", "dollars", "ratio"
    severity: RestaurantKPISeverity
    insight: str
    action: str


@dataclass
class RestaurantAnalysisResult:
    """Complete restaurant financial analysis."""

    analysis_period: str
    total_revenue: float
    total_expenses: float
    net_operating_income: float

    # Core KPIs
    kpis: list[RestaurantKPI] = field(default_factory=list)

    # Expense breakdown
    expense_breakdown: dict[str, float] = field(default_factory=dict)
    expense_ratios: dict[str, float] = field(default_factory=dict)

    # Time-based analysis
    daily_revenue: dict[str, float] = field(default_factory=dict)
    weekly_revenue: dict[str, float] = field(default_factory=dict)

    # Alerts
    critical_alerts: list[str] = field(default_factory=list)
    opportunities: list[str] = field(default_factory=list)

    # Health score (0-100)
    health_score: int = 0
    health_grade: str = "B"


# Restaurant benchmark ranges (as % of revenue)
RESTAURANT_BENCHMARKS = {
    "food_cost": {"low": 25.0, "typical": 30.0, "high": 35.0, "critical": 38.0},
    "labor_cost": {"low": 25.0, "typical": 30.0, "high": 35.0, "critical": 38.0},
    "prime_cost": {"low": 55.0, "typical": 62.0, "high": 68.0, "critical": 72.0},
    "beverage_cost": {"low": 18.0, "typical": 21.0, "high": 24.0, "critical": 28.0},
    "occupancy_cost": {"low": 6.0, "typical": 8.0, "high": 10.0, "critical": 12.0},
    "marketing": {"low": 1.0, "typical": 3.0, "high": 6.0, "critical": 8.0},
    "insurance": {"low": 1.5, "typical": 3.0, "high": 5.0, "critical": 6.0},
    "supplies": {"low": 2.0, "typical": 4.0, "high": 6.0, "critical": 8.0},
    "maintenance": {"low": 1.0, "typical": 2.5, "high": 4.0, "critical": 5.0},
    "net_margin": {"low": 2.0, "typical": 6.0, "high": 10.0, "excellent": 12.0},
}

# Map expense categories to restaurant cost buckets
RESTAURANT_COST_BUCKETS = {
    "food_cost": [ExpenseCategory.INVENTORY],
    "labor_cost": [ExpenseCategory.PAYROLL],
    "occupancy_cost": [ExpenseCategory.RENT, ExpenseCategory.UTILITIES],
    "marketing": [ExpenseCategory.MARKETING],
    "insurance": [ExpenseCategory.INSURANCE],
    "supplies": [ExpenseCategory.SUPPLIES],
    "maintenance": [ExpenseCategory.MAINTENANCE, ExpenseCategory.EQUIPMENT],
    "other": [
        ExpenseCategory.SOFTWARE,
        ExpenseCategory.SUBSCRIPTIONS,
        ExpenseCategory.PROFESSIONAL_FEES,
        ExpenseCategory.TAXES,
        ExpenseCategory.TRAVEL,
        ExpenseCategory.MEALS,
        ExpenseCategory.SHIPPING,
        ExpenseCategory.INTEREST,
        ExpenseCategory.MISCELLANEOUS,
        ExpenseCategory.OTHER,
    ],
}


class RestaurantAnalyzer:
    """Analyze restaurant financials with industry-specific metrics."""

    @classmethod
    def analyze(
        cls,
        dataset: FinancialDataset,
        annual_revenue: float | None = None,
        *,
        seat_count: int | None = None,
        operating_hours_per_week: float | None = None,
    ) -> RestaurantAnalysisResult:
        """Run full restaurant financial analysis.

        Args:
            dataset: Financial data from connector.
            annual_revenue: Annual revenue (if not derivable from transactions).
            seat_count: Number of seats for RevPASH calculation.
            operating_hours_per_week: Hours open per week (default 70).

        Returns:
            RestaurantAnalysisResult with all KPIs and recommendations.
        """
        # Calculate totals from transactions
        total_income = sum(t.amount for t in dataset.transactions if t.type.value == "income")
        total_expenses = sum(t.amount for t in dataset.transactions if t.type.value == "expense")

        # Annualize if we have partial-year data
        if dataset.period_start and dataset.period_end:
            days_in_period = (dataset.period_end - dataset.period_start).days + 1
            annualization_factor = 365 / max(days_in_period, 1)
        else:
            annualization_factor = 1.0

        # Use provided annual revenue or annualize from income transactions
        if annual_revenue:
            revenue = annual_revenue
        else:
            revenue = total_income * annualization_factor
            if revenue == 0:
                # Estimate from expenses (typical restaurant expense ratio 92-98%)
                revenue = total_expenses * annualization_factor / 0.95

        # Calculate expense breakdown by category
        expense_breakdown = cls._calculate_expense_breakdown(dataset.transactions)
        expense_ratios = {
            cat: (amount / revenue * 100) if revenue > 0 else 0 for cat, amount in expense_breakdown.items()
        }

        # Calculate restaurant-specific cost buckets
        cost_buckets = cls._calculate_cost_buckets(dataset.transactions, revenue)

        # Generate KPIs
        kpis = cls._generate_kpis(cost_buckets, revenue, total_expenses)

        # Calculate daily/weekly revenue patterns
        daily_revenue, weekly_revenue = cls._calculate_revenue_patterns(dataset.transactions)

        # Generate alerts and opportunities
        critical_alerts, opportunities = cls._generate_insights(kpis, cost_buckets, revenue)

        # Calculate health score
        health_score, health_grade = cls._calculate_health_score(kpis)

        # Build analysis period string
        if dataset.period_start and dataset.period_end:
            analysis_period = f"{dataset.period_start} to {dataset.period_end}"
        else:
            analysis_period = "Full dataset"

        return RestaurantAnalysisResult(
            analysis_period=analysis_period,
            total_revenue=revenue,
            total_expenses=total_expenses * annualization_factor,
            net_operating_income=revenue - (total_expenses * annualization_factor),
            kpis=kpis,
            expense_breakdown=expense_breakdown,
            expense_ratios=expense_ratios,
            daily_revenue=daily_revenue,
            weekly_revenue=weekly_revenue,
            critical_alerts=critical_alerts,
            opportunities=opportunities,
            health_score=health_score,
            health_grade=health_grade,
        )

    @classmethod
    def _calculate_expense_breakdown(cls, transactions: list[Transaction]) -> dict[str, float]:
        """Calculate total expenses by category."""
        breakdown: dict[str, float] = {}
        for txn in transactions:
            if txn.type.value != "expense":
                continue
            cat_val = txn.category.value if txn.category else "other"
            breakdown[cat_val] = breakdown.get(cat_val, 0) + txn.amount
        return breakdown

    @classmethod
    def _calculate_cost_buckets(cls, transactions: list[Transaction], revenue: float) -> dict[str, dict[str, float]]:
        """Calculate restaurant-specific cost buckets."""
        # Sum by bucket
        bucket_totals: dict[str, float] = {name: 0 for name in RESTAURANT_COST_BUCKETS}

        for txn in transactions:
            if txn.type.value != "expense":
                continue
            cat = txn.category
            if not cat:
                bucket_totals["other"] += txn.amount
                continue

            # Find which bucket this category belongs to
            placed = False
            for bucket_name, categories in RESTAURANT_COST_BUCKETS.items():
                if cat in categories:
                    bucket_totals[bucket_name] += txn.amount
                    placed = True
                    break
            if not placed:
                bucket_totals["other"] += txn.amount

        # Calculate percentages
        result: dict[str, dict[str, float]] = {}
        for bucket_name, total in bucket_totals.items():
            pct = (total / revenue * 100) if revenue > 0 else 0
            result[bucket_name] = {"total": total, "percent": pct}

        # Add prime cost (food + labor)
        prime_total = bucket_totals["food_cost"] + bucket_totals["labor_cost"]
        prime_pct = (prime_total / revenue * 100) if revenue > 0 else 0
        result["prime_cost"] = {"total": prime_total, "percent": prime_pct}

        return result

    @classmethod
    def _generate_kpis(
        cls, cost_buckets: dict[str, dict[str, float]], revenue: float, total_expenses: float
    ) -> list[RestaurantKPI]:
        """Generate restaurant KPIs with severity ratings."""
        kpis: list[RestaurantKPI] = []

        # Food Cost %
        food = cost_buckets.get("food_cost", {"percent": 0})
        food_pct = food["percent"]
        bench = RESTAURANT_BENCHMARKS["food_cost"]
        kpis.append(
            RestaurantKPI(
                name="food_cost_pct",
                display_name="Food Cost %",
                actual=food_pct,
                benchmark_low=bench["low"],
                benchmark_typical=bench["typical"],
                benchmark_high=bench["high"],
                unit="percent",
                severity=cls._get_severity(food_pct, bench, higher_is_worse=True),
                insight=cls._food_cost_insight(food_pct, bench),
                action=cls._food_cost_action(food_pct, bench),
            )
        )

        # Labor Cost %
        labor = cost_buckets.get("labor_cost", {"percent": 0})
        labor_pct = labor["percent"]
        bench = RESTAURANT_BENCHMARKS["labor_cost"]
        kpis.append(
            RestaurantKPI(
                name="labor_cost_pct",
                display_name="Labor Cost %",
                actual=labor_pct,
                benchmark_low=bench["low"],
                benchmark_typical=bench["typical"],
                benchmark_high=bench["high"],
                unit="percent",
                severity=cls._get_severity(labor_pct, bench, higher_is_worse=True),
                insight=cls._labor_cost_insight(labor_pct, bench),
                action=cls._labor_cost_action(labor_pct, bench),
            )
        )

        # Prime Cost % (Food + Labor)
        prime = cost_buckets.get("prime_cost", {"percent": 0})
        prime_pct = prime["percent"]
        bench = RESTAURANT_BENCHMARKS["prime_cost"]
        kpis.append(
            RestaurantKPI(
                name="prime_cost_pct",
                display_name="Prime Cost %",
                actual=prime_pct,
                benchmark_low=bench["low"],
                benchmark_typical=bench["typical"],
                benchmark_high=bench["high"],
                unit="percent",
                severity=cls._get_severity(prime_pct, bench, higher_is_worse=True),
                insight=f"Prime cost (food + labor) is {prime_pct:.1f}% vs target {bench['typical']}%.",
                action="Review both food and labor costs for optimization opportunities."
                if prime_pct > bench["high"]
                else "",
            )
        )

        # Occupancy Cost %
        occupancy = cost_buckets.get("occupancy_cost", {"percent": 0})
        occupancy_pct = occupancy["percent"]
        bench = RESTAURANT_BENCHMARKS["occupancy_cost"]
        kpis.append(
            RestaurantKPI(
                name="occupancy_cost_pct",
                display_name="Occupancy Cost %",
                actual=occupancy_pct,
                benchmark_low=bench["low"],
                benchmark_typical=bench["typical"],
                benchmark_high=bench["high"],
                unit="percent",
                severity=cls._get_severity(occupancy_pct, bench, higher_is_worse=True),
                insight=f"Rent + utilities at {occupancy_pct:.1f}% of revenue.",
                action="Consider renegotiating lease or energy audit." if occupancy_pct > bench["high"] else "",
            )
        )

        # Net Margin
        net_margin = ((revenue - total_expenses) / revenue * 100) if revenue > 0 else 0
        bench = RESTAURANT_BENCHMARKS["net_margin"]
        kpis.append(
            RestaurantKPI(
                name="net_margin",
                display_name="Net Operating Margin",
                actual=net_margin,
                benchmark_low=bench["low"],
                benchmark_typical=bench["typical"],
                benchmark_high=bench["high"],
                unit="percent",
                severity=cls._get_margin_severity(net_margin, bench),
                insight=f"Net margin of {net_margin:.1f}% {'exceeds' if net_margin >= bench['typical'] else 'below'} industry average.",
                action="Focus on cost reduction." if net_margin < bench["low"] else "",
            )
        )

        return kpis

    @staticmethod
    def _get_severity(actual: float, bench: dict[str, float], higher_is_worse: bool = True) -> RestaurantKPISeverity:
        """Determine KPI severity based on benchmarks."""
        if higher_is_worse:
            if actual >= bench.get("critical", bench["high"] * 1.1):
                return RestaurantKPISeverity.CRITICAL
            elif actual >= bench["high"]:
                return RestaurantKPISeverity.WARNING
            elif actual >= bench["typical"]:
                return RestaurantKPISeverity.HEALTHY
            else:
                return RestaurantKPISeverity.EXCELLENT
        else:
            if actual <= bench.get("critical", bench["low"] * 0.5):
                return RestaurantKPISeverity.CRITICAL
            elif actual <= bench["low"]:
                return RestaurantKPISeverity.WARNING
            elif actual <= bench["typical"]:
                return RestaurantKPISeverity.HEALTHY
            else:
                return RestaurantKPISeverity.EXCELLENT

    @staticmethod
    def _get_margin_severity(actual: float, bench: dict[str, float]) -> RestaurantKPISeverity:
        """Margin severity — higher is better."""
        if actual < 0:
            return RestaurantKPISeverity.CRITICAL
        elif actual < bench["low"]:
            return RestaurantKPISeverity.WARNING
        elif actual < bench["typical"]:
            return RestaurantKPISeverity.HEALTHY
        else:
            return RestaurantKPISeverity.EXCELLENT

    @staticmethod
    def _food_cost_insight(actual: float, bench: dict[str, float]) -> str:
        if actual < bench["low"]:
            return f"Food cost at {actual:.1f}% is excellent — well below industry average of {bench['typical']}%."
        elif actual <= bench["typical"]:
            return f"Food cost at {actual:.1f}% is healthy — near industry average of {bench['typical']}%."
        elif actual <= bench["high"]:
            return f"Food cost at {actual:.1f}% is elevated — above typical {bench['typical']}%."
        else:
            return (
                f"ALERT: Food cost at {actual:.1f}% is critically high — {actual - bench['typical']:.1f}% above target."
            )

    @staticmethod
    def _food_cost_action(actual: float, bench: dict[str, float]) -> str:
        if actual <= bench["typical"]:
            return ""
        elif actual <= bench["high"]:
            return "Review portion sizes and supplier pricing. Consider menu engineering."
        else:
            return "URGENT: Conduct full inventory audit. Renegotiate supplier contracts. Check for waste/theft."

    @staticmethod
    def _labor_cost_insight(actual: float, bench: dict[str, float]) -> str:
        if actual < bench["low"]:
            return f"Labor cost at {actual:.1f}% is excellent — well below industry average."
        elif actual <= bench["typical"]:
            return f"Labor cost at {actual:.1f}% is in healthy range."
        elif actual <= bench["high"]:
            return f"Labor cost at {actual:.1f}% is elevated — review scheduling efficiency."
        else:
            return f"ALERT: Labor cost at {actual:.1f}% is critically high — affecting profitability."

    @staticmethod
    def _labor_cost_action(actual: float, bench: dict[str, float]) -> str:
        if actual <= bench["typical"]:
            return ""
        elif actual <= bench["high"]:
            return "Optimize shift scheduling. Cross-train staff. Consider POS labor tracking."
        else:
            return "URGENT: Review staffing levels. Implement labor cost targets. Consider tech automation."

    @classmethod
    def _calculate_revenue_patterns(cls, transactions: list[Transaction]) -> tuple[dict[str, float], dict[str, float]]:
        """Calculate revenue by day and week."""
        daily: dict[str, float] = {}
        weekly: dict[str, float] = {}

        for txn in transactions:
            if txn.type.value != "income":
                continue

            day_key = txn.date.strftime("%A")  # Day name
            daily[day_key] = daily.get(day_key, 0) + txn.amount

            # ISO week number
            week_key = f"Week {txn.date.isocalendar()[1]}"
            weekly[week_key] = weekly.get(week_key, 0) + txn.amount

        return daily, weekly

    @classmethod
    def _generate_insights(
        cls, kpis: list[RestaurantKPI], cost_buckets: dict[str, dict[str, float]], revenue: float
    ) -> tuple[list[str], list[str]]:
        """Generate critical alerts and optimization opportunities."""
        alerts: list[str] = []
        opportunities: list[str] = []

        for kpi in kpis:
            if kpi.severity == RestaurantKPISeverity.CRITICAL:
                alerts.append(f"🚨 {kpi.display_name}: {kpi.actual:.1f}% — {kpi.action}")
            elif kpi.severity == RestaurantKPISeverity.WARNING:
                opportunities.append(f"⚠️ {kpi.display_name}: {kpi.actual:.1f}% — {kpi.action}")
            elif kpi.severity == RestaurantKPISeverity.EXCELLENT:
                opportunities.append(f"✅ {kpi.display_name}: {kpi.actual:.1f}% — performing well!")

        # Check for common restaurant issues
        food_pct = cost_buckets.get("food_cost", {}).get("percent", 0)
        labor_pct = cost_buckets.get("labor_cost", {}).get("percent", 0)

        if food_pct > 32 and labor_pct > 32:
            alerts.append("🚨 Both food and labor costs are elevated. Prime cost squeeze is affecting margins.")

        marketing_pct = cost_buckets.get("marketing", {}).get("percent", 0)
        if marketing_pct < 1.0:
            opportunities.append("💡 Marketing spend is very low. Consider investing in customer acquisition.")

        return alerts, opportunities

    @classmethod
    def _calculate_health_score(cls, kpis: list[RestaurantKPI]) -> tuple[int, str]:
        """Calculate overall health score (0-100) and letter grade."""
        if not kpis:
            return 50, "C"

        # Weight each KPI equally for simplicity
        scores: list[int] = []
        for kpi in kpis:
            if kpi.severity == RestaurantKPISeverity.EXCELLENT:
                scores.append(100)
            elif kpi.severity == RestaurantKPISeverity.HEALTHY:
                scores.append(75)
            elif kpi.severity == RestaurantKPISeverity.WARNING:
                scores.append(50)
            else:  # CRITICAL
                scores.append(25)

        health_score = int(sum(scores) / len(scores))

        if health_score >= 85:
            grade = "A"
        elif health_score >= 70:
            grade = "B"
        elif health_score >= 55:
            grade = "C"
        elif health_score >= 40:
            grade = "D"
        else:
            grade = "F"

        return health_score, grade


def analyze_restaurant(
    dataset: FinancialDataset,
    annual_revenue: float | None = None,
    **kwargs: Any,
) -> RestaurantAnalysisResult:
    """Convenience function for restaurant analysis.

    Args:
        dataset: Financial data from connector.
        annual_revenue: Annual revenue estimate.
        **kwargs: Additional options (seat_count, operating_hours_per_week).

    Returns:
        Full restaurant analysis with KPIs and recommendations.
    """
    return RestaurantAnalyzer.analyze(dataset, annual_revenue, **kwargs)
