"""
Anomaly Detector — statistical anomaly detection for financial data.

Implements three complementary detection methods:
1. **Z-score**: Flags individual transactions > N standard deviations from mean.
2. **IQR (Interquartile Range)**: Robust outlier detection resistant to extreme values.
3. **Time-series**: Detects monthly/weekly spend anomalies using rolling statistics.

Each method produces anomaly scores and flags — no LLM calls required.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

logger = logging.getLogger("fiscalpilot.analyzers.anomaly")


@dataclass
class AnomalyFlag:
    """A single flagged transaction or period."""

    transaction_id: str | None
    amount: float
    score: float  # 0.0 (normal) to 1.0 (extreme)
    method: str  # z_score, iqr, time_series
    reason: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class TimeSeriesAnomaly:
    """A time-period level anomaly."""

    period: str  # "2025-03" or "2025-W12"
    total_spend: float
    expected_range: tuple[float, float]  # (low, high)
    deviation_pct: float
    score: float
    contributing_transactions: list[str] = field(default_factory=list)


@dataclass
class AnomalyResult:
    """Complete anomaly detection result."""

    total_transactions: int
    flagged_count: int
    flags: list[AnomalyFlag] = field(default_factory=list)
    time_series_anomalies: list[TimeSeriesAnomaly] = field(default_factory=list)
    vendor_anomalies: dict[str, list[AnomalyFlag]] = field(default_factory=dict)
    stats: dict[str, float] = field(default_factory=dict)
    summary: str = ""


class AnomalyDetector:
    """Statistical anomaly detection engine for financial transactions."""

    @classmethod
    def analyze(
        cls,
        transactions: list[dict[str, Any]],
        *,
        z_threshold: float = 3.0,
        iqr_multiplier: float = 1.5,
        time_window: str = "monthly",  # monthly, weekly
        include_vendor_analysis: bool = True,
    ) -> AnomalyResult:
        """Run all anomaly detection methods on transaction data.

        Args:
            transactions: List of transaction dicts with at least "amount" and "date".
            z_threshold: Number of standard deviations for Z-score flagging.
            iqr_multiplier: IQR multiplier for fence calculation (1.5 = standard, 3.0 = extreme).
            time_window: Granularity for time-series analysis.
            include_vendor_analysis: Whether to detect per-vendor anomalies.

        Returns:
            AnomalyResult with all flagged transactions and period anomalies.
        """
        if not transactions:
            return AnomalyResult(total_transactions=0, flagged_count=0, summary="No transactions to analyze.")

        amounts = [abs(float(t.get("amount", 0))) for t in transactions if t.get("amount") is not None]
        if not amounts:
            return AnomalyResult(total_transactions=len(transactions), flagged_count=0, summary="No valid amounts.")

        # Compute global stats
        mean_val = sum(amounts) / len(amounts)
        variance = sum((x - mean_val) ** 2 for x in amounts) / max(len(amounts) - 1, 1)
        std_val = math.sqrt(variance)
        sorted_amounts = sorted(amounts)
        median_val = cls._median(sorted_amounts)
        q1 = cls._percentile(sorted_amounts, 25)
        q3 = cls._percentile(sorted_amounts, 75)
        iqr = q3 - q1

        stats = {
            "mean": round(mean_val, 2),
            "median": round(median_val, 2),
            "std_dev": round(std_val, 2),
            "q1": round(q1, 2),
            "q3": round(q3, 2),
            "iqr": round(iqr, 2),
            "min": round(sorted_amounts[0], 2),
            "max": round(sorted_amounts[-1], 2),
        }

        all_flags: list[AnomalyFlag] = []

        # Method 1: Z-score
        z_flags = cls._z_score_detection(transactions, mean_val, std_val, z_threshold)
        all_flags.extend(z_flags)

        # Method 2: IQR
        iqr_flags = cls._iqr_detection(transactions, q1, q3, iqr, iqr_multiplier)
        all_flags.extend(iqr_flags)

        # Method 3: Time-series
        ts_anomalies = cls._time_series_detection(transactions, time_window)

        # Vendor analysis
        vendor_anomalies: dict[str, list[AnomalyFlag]] = {}
        if include_vendor_analysis:
            vendor_anomalies = cls._vendor_anomaly_detection(transactions, z_threshold)

        # Deduplicate flags (same transaction flagged by multiple methods)
        unique_flags = cls._deduplicate_flags(all_flags)
        unique_flags.sort(key=lambda f: f.score, reverse=True)

        summary = cls._build_summary(unique_flags, ts_anomalies, stats, len(transactions))

        return AnomalyResult(
            total_transactions=len(transactions),
            flagged_count=len(unique_flags),
            flags=unique_flags,
            time_series_anomalies=ts_anomalies,
            vendor_anomalies=vendor_anomalies,
            stats=stats,
            summary=summary,
        )

    # ------------------------------------------------------------------ #
    #  Detection methods                                                  #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _z_score_detection(
        transactions: list[dict[str, Any]],
        mean_val: float,
        std_val: float,
        threshold: float,
    ) -> list[AnomalyFlag]:
        """Flag transactions with |z-score| > threshold."""
        if std_val == 0:
            return []

        flags: list[AnomalyFlag] = []
        for t in transactions:
            amount = abs(float(t.get("amount", 0)))
            if amount == 0:
                continue
            z = (amount - mean_val) / std_val
            if abs(z) > threshold:
                score = min(1.0, abs(z) / (threshold * 2))  # Normalize to 0-1
                flags.append(AnomalyFlag(
                    transaction_id=t.get("id"),
                    amount=amount,
                    score=round(score, 3),
                    method="z_score",
                    reason=f"Amount ${amount:,.2f} is {abs(z):.1f} std devs from mean ${mean_val:,.2f}",
                    context={"z_score": round(z, 3), "mean": round(mean_val, 2), "std": round(std_val, 2)},
                ))
        return flags

    @staticmethod
    def _iqr_detection(
        transactions: list[dict[str, Any]],
        q1: float,
        q3: float,
        iqr: float,
        multiplier: float,
    ) -> list[AnomalyFlag]:
        """Flag transactions outside IQR fences."""
        if iqr == 0:
            return []

        lower_fence = q1 - multiplier * iqr
        upper_fence = q3 + multiplier * iqr

        flags: list[AnomalyFlag] = []
        for t in transactions:
            amount = abs(float(t.get("amount", 0)))
            if amount == 0:
                continue
            if amount > upper_fence:
                distance = (amount - upper_fence) / iqr
                score = min(1.0, distance / (multiplier * 2))
                flags.append(AnomalyFlag(
                    transaction_id=t.get("id"),
                    amount=amount,
                    score=round(score, 3),
                    method="iqr",
                    reason=f"Amount ${amount:,.2f} exceeds upper fence ${upper_fence:,.2f} (IQR: ${iqr:,.2f})",
                    context={"upper_fence": round(upper_fence, 2), "iqr": round(iqr, 2)},
                ))
            elif amount < lower_fence and lower_fence > 0:
                distance = (lower_fence - amount) / iqr
                score = min(1.0, distance / (multiplier * 2))
                flags.append(AnomalyFlag(
                    transaction_id=t.get("id"),
                    amount=amount,
                    score=round(score, 3),
                    method="iqr",
                    reason=f"Amount ${amount:,.2f} below lower fence ${lower_fence:,.2f}",
                    context={"lower_fence": round(lower_fence, 2), "iqr": round(iqr, 2)},
                ))
        return flags

    @classmethod
    def _time_series_detection(
        cls,
        transactions: list[dict[str, Any]],
        window: str,
    ) -> list[TimeSeriesAnomaly]:
        """Detect anomalous spending periods using rolling statistics."""
        # Group transactions by period
        period_totals: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for t in transactions:
            raw_date = t.get("date")
            if raw_date is None:
                continue
            if isinstance(raw_date, str):
                try:
                    d = date.fromisoformat(raw_date[:10])
                except ValueError:
                    continue
            elif isinstance(raw_date, date):
                d = raw_date
            else:
                continue

            if window == "weekly":
                iso = d.isocalendar()
                period_key = f"{iso[0]}-W{iso[1]:02d}"
            else:
                period_key = f"{d.year}-{d.month:02d}"

            period_totals[period_key].append(t)

        if len(period_totals) < 3:
            return []  # Need at least 3 periods for meaningful comparison

        # Compute per-period spend
        period_spend: dict[str, float] = {}
        period_txn_ids: dict[str, list[str]] = {}
        for period, txns in period_totals.items():
            period_spend[period] = sum(abs(float(t.get("amount", 0))) for t in txns)
            period_txn_ids[period] = [t.get("id", "") for t in txns if t.get("id")]

        sorted_periods = sorted(period_spend.keys())
        values = [period_spend[p] for p in sorted_periods]

        # Rolling stats (use all-except-current for expected range)
        anomalies: list[TimeSeriesAnomaly] = []
        for i, period in enumerate(sorted_periods):
            others = values[:i] + values[i + 1:]
            if not others:
                continue
            other_mean = sum(others) / len(others)
            other_std = math.sqrt(sum((x - other_mean) ** 2 for x in others) / max(len(others) - 1, 1))

            actual = values[i]
            if other_std > 0:
                z = (actual - other_mean) / other_std
            else:
                z = 0

            low_bound = max(0, other_mean - 2 * other_std)
            high_bound = other_mean + 2 * other_std

            if abs(z) > 2.0:
                dev_pct = ((actual - other_mean) / max(other_mean, 1)) * 100
                score = min(1.0, abs(z) / 4.0)
                anomalies.append(TimeSeriesAnomaly(
                    period=period,
                    total_spend=round(actual, 2),
                    expected_range=(round(low_bound, 2), round(high_bound, 2)),
                    deviation_pct=round(dev_pct, 1),
                    score=round(score, 3),
                    contributing_transactions=period_txn_ids.get(period, [])[:20],
                ))

        return anomalies

    @classmethod
    def _vendor_anomaly_detection(
        cls,
        transactions: list[dict[str, Any]],
        z_threshold: float,
    ) -> dict[str, list[AnomalyFlag]]:
        """Detect per-vendor anomalies — sudden spikes from a specific vendor."""
        vendor_txns: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for t in transactions:
            vendor = t.get("vendor") or "unknown"
            vendor_txns[str(vendor)].append(t)

        results: dict[str, list[AnomalyFlag]] = {}
        for vendor, txns in vendor_txns.items():
            if len(txns) < 5:
                continue  # Need enough data per vendor

            amounts = [abs(float(t.get("amount", 0))) for t in txns]
            mean_val = sum(amounts) / len(amounts)
            variance = sum((x - mean_val) ** 2 for x in amounts) / max(len(amounts) - 1, 1)
            std_val = math.sqrt(variance)

            if std_val == 0:
                continue

            flags: list[AnomalyFlag] = []
            for i, t in enumerate(txns):
                z = (amounts[i] - mean_val) / std_val
                if abs(z) > z_threshold:
                    score = min(1.0, abs(z) / (z_threshold * 2))
                    flags.append(AnomalyFlag(
                        transaction_id=t.get("id"),
                        amount=amounts[i],
                        score=round(score, 3),
                        method="vendor_z_score",
                        reason=(
                            f"Vendor '{vendor}' payment ${amounts[i]:,.2f} is "
                            f"{abs(z):.1f}σ from vendor mean ${mean_val:,.2f}"
                        ),
                        context={"vendor": vendor, "vendor_mean": round(mean_val, 2)},
                    ))

            if flags:
                results[vendor] = flags

        return results

    # ------------------------------------------------------------------ #
    #  Utilities                                                          #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _median(sorted_vals: list[float]) -> float:
        n = len(sorted_vals)
        if n == 0:
            return 0.0
        mid = n // 2
        if n % 2 == 0:
            return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0
        return sorted_vals[mid]

    @staticmethod
    def _percentile(sorted_vals: list[float], pct: float) -> float:
        if not sorted_vals:
            return 0.0
        k = (len(sorted_vals) - 1) * (pct / 100.0)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_vals[int(k)]
        return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)

    @staticmethod
    def _deduplicate_flags(flags: list[AnomalyFlag]) -> list[AnomalyFlag]:
        """Merge flags for the same transaction, keeping the highest score."""
        by_id: dict[str | None, AnomalyFlag] = {}
        for f in flags:
            key = f.transaction_id or id(f)
            existing = by_id.get(key)
            if existing is None or f.score > existing.score:
                if existing and f.transaction_id:
                    # Merge methods
                    f = AnomalyFlag(
                        transaction_id=f.transaction_id,
                        amount=f.amount,
                        score=f.score,
                        method=f"{existing.method}+{f.method}",
                        reason=f.reason,
                        context={**existing.context, **f.context},
                    )
                by_id[key] = f
        return list(by_id.values())

    @staticmethod
    def _build_summary(
        flags: list[AnomalyFlag],
        ts_anomalies: list[TimeSeriesAnomaly],
        stats: dict[str, float],
        total: int,
    ) -> str:
        lines = [
            f"Anomaly Detection ({total} transactions):",
            f"  Mean: ${stats['mean']:,.2f} | Median: ${stats['median']:,.2f} | Std: ${stats['std_dev']:,.2f}",
            f"  Flagged: {len(flags)} transactions ({len(flags)/max(total,1)*100:.1f}%)",
        ]
        if ts_anomalies:
            lines.append(f"  Time-series anomalies: {len(ts_anomalies)} periods")
            for a in ts_anomalies[:3]:
                lines.append(f"    {a.period}: ${a.total_spend:,.2f} ({a.deviation_pct:+.1f}% vs expected)")

        high_score = [f for f in flags if f.score >= 0.7]
        if high_score:
            lines.append(f"  High-confidence anomalies: {len(high_score)}")
            for f in high_score[:3]:
                lines.append(f"    ${f.amount:,.2f} — {f.reason}")

        return "\n".join(lines)
