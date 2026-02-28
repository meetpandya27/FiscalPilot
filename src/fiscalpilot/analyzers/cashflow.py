"""
Cash Flow Forecaster — time-series projection of future cash position.

Uses historical transaction data to produce:
1. **Monthly cash flow summary** — inflows, outflows, net, running balance.
2. **3-6 month forward projection** using exponential smoothing.
3. **Runway calculation** — months of cash remaining at current burn rate.
4. **Seasonal pattern detection** — identifies recurring high/low spend months.
5. **Risk alerts** — warns about projected negative balances or tight months.

No LLM needed — pure time-series math.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Any

logger = logging.getLogger("fiscalpilot.analyzers.cashflow")


@dataclass
class MonthlyCashFlow:
    """Cash flow data for a single month."""

    period: str  # "2025-03"
    inflows: float
    outflows: float
    net: float
    running_balance: float
    transaction_count: int
    is_forecast: bool = False


@dataclass
class SeasonalPattern:
    """A detected seasonal spending pattern."""

    pattern: str  # "high_outflows_december", "low_inflows_january"
    months: list[int]  # 1-12
    average_deviation_pct: float
    description: str


@dataclass
class CashFlowForecast:
    """Complete cash flow analysis and forecast."""

    historical: list[MonthlyCashFlow] = field(default_factory=list)
    forecast: list[MonthlyCashFlow] = field(default_factory=list)
    current_balance: float = 0.0
    average_monthly_burn: float = 0.0
    average_monthly_inflow: float = 0.0
    runway_months: float = 0.0  # Months until cash runs out at current burn
    seasonal_patterns: list[SeasonalPattern] = field(default_factory=list)
    risk_alerts: list[str] = field(default_factory=list)
    summary: str = ""


class CashFlowForecaster:
    """Project future cash flows from historical transaction data."""

    FORECAST_MONTHS = 6

    @classmethod
    def analyze(
        cls,
        transactions: list[dict[str, Any]],
        current_balance: float = 0.0,
        *,
        forecast_months: int = 6,
        smoothing_alpha: float = 0.3,
    ) -> CashFlowForecast:
        """Run cash flow analysis and forecasting.

        Args:
            transactions: Transaction dicts with "date", "amount", "type" keys.
            current_balance: Current cash/bank balance.
            forecast_months: Number of months to project forward (1-12).
            smoothing_alpha: Exponential smoothing factor (0.1 = smooth, 0.5 = reactive).

        Returns:
            CashFlowForecast with history, projections, and alerts.
        """
        forecast_months = max(1, min(12, forecast_months))

        # Group transactions by month
        monthly: dict[str, dict[str, float | int]] = defaultdict(lambda: {"inflows": 0.0, "outflows": 0.0, "count": 0})

        for t in transactions:
            raw_date = t.get("date")
            if raw_date is None:
                continue
            d = cls._parse_date(raw_date)
            if d is None:
                continue

            period_key = f"{d.year}-{d.month:02d}"
            amount = float(t.get("amount", 0))
            txn_type = t.get("type", "expense")

            if txn_type in ("income", "refund") or amount < 0:
                monthly[period_key]["inflows"] += abs(amount)
            else:
                monthly[period_key]["outflows"] += abs(amount)
            monthly[period_key]["count"] += 1

        if not monthly:
            return CashFlowForecast(
                current_balance=current_balance,
                summary="No transaction data available for cash flow analysis.",
            )

        # Build historical series in chronological order
        sorted_periods = sorted(monthly.keys())
        historical: list[MonthlyCashFlow] = []
        running = current_balance

        # Walk backwards to compute running balance correctly
        # First pass: just compute net flows
        nets: list[float] = []
        for period in sorted_periods:
            data = monthly[period]
            net = data["inflows"] - data["outflows"]
            nets.append(net)

        # Running balance: start from (current_balance - sum of all nets) so last month ends at current_balance
        total_net = sum(nets)
        running = current_balance - total_net

        for i, period in enumerate(sorted_periods):
            data = monthly[period]
            net = nets[i]
            running += net
            historical.append(
                MonthlyCashFlow(
                    period=period,
                    inflows=round(data["inflows"], 2),
                    outflows=round(data["outflows"], 2),
                    net=round(net, 2),
                    running_balance=round(running, 2),
                    transaction_count=int(data["count"]),
                )
            )

        # Compute averages
        inflow_series = [m.inflows for m in historical]
        outflow_series = [m.outflows for m in historical]

        avg_inflow = sum(inflow_series) / len(inflow_series) if inflow_series else 0
        avg_outflow = sum(outflow_series) / len(outflow_series) if outflow_series else 0
        avg_burn = avg_outflow - avg_inflow  # Positive = cash decreasing

        # Exponential smoothing for forecast
        smoothed_inflows = cls._exponential_smoothing(inflow_series, smoothing_alpha)
        smoothed_outflows = cls._exponential_smoothing(outflow_series, smoothing_alpha)

        # Seasonal indices (if we have >= 12 months)
        seasonal_inflow = cls._compute_seasonal_indices(historical, "inflows")
        seasonal_outflow = cls._compute_seasonal_indices(historical, "outflows")

        # Project forward
        forecast: list[MonthlyCashFlow] = []
        last_period = sorted_periods[-1]
        last_year, last_month = int(last_period[:4]), int(last_period[5:7])
        running_forecast = current_balance

        for _ in range(forecast_months):
            last_month += 1
            if last_month > 12:
                last_month = 1
                last_year += 1
            period_key = f"{last_year}-{last_month:02d}"

            # Base forecast from exponential smoothing
            proj_inflow = smoothed_inflows
            proj_outflow = smoothed_outflows

            # Apply seasonal adjustment if available
            if seasonal_inflow:
                proj_inflow *= seasonal_inflow.get(last_month, 1.0)
            if seasonal_outflow:
                proj_outflow *= seasonal_outflow.get(last_month, 1.0)

            net = proj_inflow - proj_outflow
            running_forecast += net

            forecast.append(
                MonthlyCashFlow(
                    period=period_key,
                    inflows=round(proj_inflow, 2),
                    outflows=round(proj_outflow, 2),
                    net=round(net, 2),
                    running_balance=round(running_forecast, 2),
                    transaction_count=0,
                    is_forecast=True,
                )
            )

        # Runway calculation
        monthly_burn = avg_outflow - avg_inflow
        if monthly_burn > 0 and current_balance > 0:
            runway = current_balance / monthly_burn
        elif monthly_burn <= 0:
            runway = float("inf")
        else:
            runway = 0.0

        # Detect seasonal patterns
        seasonal_patterns = cls._detect_patterns(historical)

        # Risk alerts
        risk_alerts = cls._generate_risk_alerts(forecast, runway, avg_burn, current_balance)

        summary = cls._build_summary(
            historical, forecast, current_balance, avg_inflow, avg_outflow, runway, seasonal_patterns, risk_alerts
        )

        return CashFlowForecast(
            historical=historical,
            forecast=forecast,
            current_balance=current_balance,
            average_monthly_burn=round(max(0, monthly_burn), 2),
            average_monthly_inflow=round(avg_inflow, 2),
            runway_months=round(runway, 1) if runway != float("inf") else -1,
            seasonal_patterns=seasonal_patterns,
            risk_alerts=risk_alerts,
            summary=summary,
        )

    # ------------------------------------------------------------------ #
    #  Forecasting utilities                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _exponential_smoothing(series: list[float], alpha: float) -> float:
        """Simple exponential smoothing — returns next forecasted value."""
        if not series:
            return 0.0
        result = series[0]
        for val in series[1:]:
            result = alpha * val + (1 - alpha) * result
        return result

    @staticmethod
    def _compute_seasonal_indices(historical: list[MonthlyCashFlow], field_name: str) -> dict[int, float] | None:
        """Compute monthly seasonal indices (month → multiplier).

        Returns None if < 12 months of data.
        """
        if len(historical) < 12:
            return None

        month_totals: dict[int, list[float]] = defaultdict(list)
        for m in historical:
            month_num = int(m.period.split("-")[1])
            month_totals[month_num].append(getattr(m, field_name))

        overall_avg = sum(getattr(m, field_name) for m in historical) / len(historical)
        if overall_avg == 0:
            return None

        indices: dict[int, float] = {}
        for month, values in month_totals.items():
            month_avg = sum(values) / len(values)
            indices[month] = month_avg / overall_avg

        return indices

    @classmethod
    def _detect_patterns(cls, historical: list[MonthlyCashFlow]) -> list[SeasonalPattern]:
        """Detect seasonal spending patterns."""
        if len(historical) < 6:
            return []

        patterns: list[SeasonalPattern] = []
        overall_outflow = sum(m.outflows for m in historical) / len(historical)
        overall_inflow = sum(m.inflows for m in historical) / len(historical)

        # Group by calendar month
        month_outflows: dict[int, list[float]] = defaultdict(list)
        month_inflows: dict[int, list[float]] = defaultdict(list)
        for m in historical:
            month_num = int(m.period.split("-")[1])
            month_outflows[month_num].append(m.outflows)
            month_inflows[month_num].append(m.inflows)

        month_names = [
            "",
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ]

        # High outflow months (>20% above average)
        high_spend_months = []
        for month, values in month_outflows.items():
            avg = sum(values) / len(values)
            if overall_outflow > 0 and avg > overall_outflow * 1.2:
                dev = ((avg - overall_outflow) / overall_outflow) * 100
                high_spend_months.append((month, dev))

        if high_spend_months:
            months = [m for m, _ in high_spend_months]
            avg_dev = sum(d for _, d in high_spend_months) / len(high_spend_months)
            month_labels = ", ".join(month_names[m] for m in months)
            patterns.append(
                SeasonalPattern(
                    pattern="high_outflows",
                    months=months,
                    average_deviation_pct=round(avg_dev, 1),
                    description=f"Higher-than-average outflows in {month_labels} ({avg_dev:.0f}% above avg).",
                )
            )

        # Low inflow months (>20% below average)
        low_inflow_months = []
        for month, values in month_inflows.items():
            avg = sum(values) / len(values)
            if overall_inflow > 0 and avg < overall_inflow * 0.8:
                dev = ((overall_inflow - avg) / overall_inflow) * 100
                low_inflow_months.append((month, dev))

        if low_inflow_months:
            months = [m for m, _ in low_inflow_months]
            avg_dev = sum(d for _, d in low_inflow_months) / len(low_inflow_months)
            month_labels = ", ".join(month_names[m] for m in months)
            patterns.append(
                SeasonalPattern(
                    pattern="low_inflows",
                    months=months,
                    average_deviation_pct=round(avg_dev, 1),
                    description=f"Lower-than-average inflows in {month_labels} ({avg_dev:.0f}% below avg).",
                )
            )

        return patterns

    @staticmethod
    def _generate_risk_alerts(
        forecast: list[MonthlyCashFlow],
        runway: float,
        avg_burn: float,
        current_balance: float,
    ) -> list[str]:
        """Generate risk warnings based on forecast data."""
        alerts: list[str] = []

        # Negative balance warning
        for m in forecast:
            if m.running_balance < 0:
                alerts.append(f"CRITICAL: Projected negative balance of ${m.running_balance:,.2f} in {m.period}.")
                break

        # Tight months (balance < 1 month of outflows)
        tight = [m for m in forecast if 0 < m.running_balance < m.outflows]
        if tight:
            alerts.append(f"WARNING: {len(tight)} month(s) with less than 1 month of operating expenses in reserve.")

        # Short runway
        if 0 < runway < 6:
            alerts.append(f"WARNING: Cash runway is only {runway:.1f} months at current burn rate.")
        elif runway == 0:
            alerts.append("CRITICAL: Cash position is negative. Immediate action required.")

        # High burn rate
        if current_balance > 0 and avg_burn > current_balance * 0.15:
            alerts.append(f"CAUTION: Monthly burn rate (${avg_burn:,.2f}) exceeds 15% of current balance.")

        return alerts

    @staticmethod
    def _parse_date(raw: Any) -> date | None:
        if isinstance(raw, date):
            return raw
        if isinstance(raw, str):
            try:
                return date.fromisoformat(raw[:10])
            except ValueError:
                return None
        return None

    @staticmethod
    def _build_summary(
        historical: list[MonthlyCashFlow],
        forecast: list[MonthlyCashFlow],
        current_balance: float,
        avg_inflow: float,
        avg_outflow: float,
        runway: float,
        patterns: list[SeasonalPattern],
        alerts: list[str],
    ) -> str:
        lines = [
            f"Cash Flow Forecast ({len(historical)} months history → {len(forecast)} months projection):",
            f"  Current balance: ${current_balance:,.2f}",
            f"  Avg monthly inflows: ${avg_inflow:,.2f}",
            f"  Avg monthly outflows: ${avg_outflow:,.2f}",
            f"  Net monthly: ${avg_inflow - avg_outflow:,.2f}",
        ]

        if runway == float("inf") or runway < 0:
            lines.append("  Runway: Cash positive (net inflows exceed outflows)")
        else:
            lines.append(f"  Runway: {runway:.1f} months")

        if forecast:
            last = forecast[-1]
            lines.append(f"  Projected balance ({last.period}): ${last.running_balance:,.2f}")

        if patterns:
            lines.append("  Seasonal patterns:")
            for p in patterns:
                lines.append(f"    {p.description}")

        if alerts:
            lines.append("  Risk alerts:")
            for a in alerts:
                lines.append(f"    {a}")

        return "\n".join(lines)
