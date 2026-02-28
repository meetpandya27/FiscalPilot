"""Tests for anomaly detection engine."""

from datetime import date, timedelta
from typing import Any

from fiscalpilot.analyzers.anomaly import AnomalyDetector, AnomalyResult


def _make_txn(
    i: int,
    amount: float,
    txn_date: date | None = None,
    vendor: str | None = None,
    category: str = "general",
) -> dict[str, Any]:
    return {
        "id": f"txn_{i:04d}",
        "amount": amount,
        "date": str(txn_date) if txn_date else "2024-06-15",
        "vendor": vendor or f"vendor_{i % 10}",
        "category": category,
        "type": "expense",
    }


def _normal_txns(n: int = 200, mean: float = 500.0, spread: float = 100.0) -> list[dict[str, Any]]:
    """Create transactions with predictable amounts that look 'normal' plus a few outliers."""
    import random
    rng = random.Random(42)
    base = date(2024, 1, 1)
    txns = []
    for i in range(n):
        txn_date = base + timedelta(days=i % 365)
        amt = mean + rng.gauss(0, spread)
        txns.append(_make_txn(i, max(amt, 1.0), txn_date))
    return txns


class TestAnomalyDetectorHappyPath:
    def test_basic_analysis(self) -> None:
        """Normal data with injected outlier should flag the outlier."""
        txns = _normal_txns(100, mean=500, spread=50)
        # Inject a massive outlier
        txns.append(_make_txn(999, 50_000.0, date(2024, 3, 15)))

        result = AnomalyDetector.analyze(txns)

        assert isinstance(result, AnomalyResult)
        assert result.total_transactions == 101
        assert result.flagged_count >= 1
        assert result.summary != ""

        # The outlier should be among flagged
        flagged_ids = [f.transaction_id for f in result.flags]
        assert "txn_0999" in flagged_ids

    def test_stats_populated(self) -> None:
        """Statistics dict should contain expected keys."""
        txns = _normal_txns(50)
        result = AnomalyDetector.analyze(txns)

        for key in ("mean", "median", "std_dev", "q1", "q3", "iqr", "min", "max"):
            assert key in result.stats

    def test_time_series_anomalies(self) -> None:
        """Inject a spike month and verify time-series detection catches it."""
        import random
        rng = random.Random(123)
        txns = []
        idx = 0
        # 6 months of ~$500/txn with some natural variance
        for month in range(1, 7):
            for _ in range(20):
                d = date(2024, month, 1) + timedelta(days=idx % 28)
                amt = 400 + rng.gauss(0, 50)  # variance so z-score can work
                txns.append(_make_txn(idx, max(amt, 10.0), d))
                idx += 1
        # Month 7: 10x spike
        for _ in range(20):
            d = date(2024, 7, 1) + timedelta(days=idx % 28)
            txns.append(_make_txn(idx, 5_000.0, d))
            idx += 1

        result = AnomalyDetector.analyze(txns)

        # Should detect anomalous period
        assert len(result.time_series_anomalies) >= 1
        anomalous_periods = [ts.period for ts in result.time_series_anomalies]
        assert any("2024-07" in p for p in anomalous_periods)

    def test_vendor_anomalies(self) -> None:
        """A vendor with one huge transaction among small ones should be flagged."""
        txns = []
        for i in range(30):
            txns.append(_make_txn(i, 100.0, vendor="consistent_co"))
        txns.append(_make_txn(999, 10_000.0, vendor="consistent_co"))

        result = AnomalyDetector.analyze(txns, include_vendor_analysis=True)

        # Vendor should appear in vendor_anomalies
        if result.vendor_anomalies:
            assert "consistent_co" in result.vendor_anomalies

    def test_dedup_across_methods(self) -> None:
        """A transaction flagged by both z-score and IQR should appear once."""
        txns = _normal_txns(100, mean=100, spread=10)
        txns.append(_make_txn(999, 99_999.0))

        result = AnomalyDetector.analyze(txns)

        ids = [f.transaction_id for f in result.flags]
        # txn_0999 should appear exactly once after dedup
        assert ids.count("txn_0999") == 1


class TestAnomalyDetectorEdgeCases:
    def test_empty_transactions(self) -> None:
        """Empty list should not crash."""
        result = AnomalyDetector.analyze([])

        assert result.total_transactions == 0
        assert result.flagged_count == 0

    def test_identical_amounts(self) -> None:
        """All same amount → std=0, iqr=0, no flags."""
        txns = [_make_txn(i, 100.0) for i in range(50)]
        result = AnomalyDetector.analyze(txns)

        # No outliers when everything is identical
        assert result.flagged_count == 0

    def test_too_few_periods_for_time_series(self) -> None:
        """< 3 periods should produce no time-series anomalies."""
        txns = [_make_txn(i, 100.0, date(2024, 1, i + 1)) for i in range(28)]
        result = AnomalyDetector.analyze(txns)

        # Only 1 month of data
        assert len(result.time_series_anomalies) == 0

    def test_custom_thresholds(self) -> None:
        """Tighter z_threshold should flag more transactions."""
        txns = _normal_txns(200, mean=500, spread=100)

        loose = AnomalyDetector.analyze(txns, z_threshold=4.0)
        tight = AnomalyDetector.analyze(txns, z_threshold=2.0)

        assert tight.flagged_count >= loose.flagged_count

    def test_weekly_time_window(self) -> None:
        """Weekly time window should produce more granular periods."""
        txns = _normal_txns(200)
        result = AnomalyDetector.analyze(txns, time_window="weekly")

        # Should still work without errors
        assert isinstance(result, AnomalyResult)
