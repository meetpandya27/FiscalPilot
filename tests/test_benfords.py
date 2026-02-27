"""Tests for Benford's Law analyzer."""

import math
import random
from typing import Any

import pytest

from fiscalpilot.analyzers.benfords import BenfordsAnalyzer, BenfordsResult


def _make_txns(amounts: list[float]) -> list[dict[str, Any]]:
    """Helper to build transaction dicts from a list of amounts."""
    return [{"id": str(i), "amount": a, "vendor": f"v{i % 5}", "category": f"c{i % 3}"} for i, a in enumerate(amounts)]


def _benford_distributed_amounts(n: int, seed: int = 42) -> list[float]:
    """Generate amounts that follow Benford's Law (reciprocal distribution)."""
    rng = random.Random(seed)
    # 1/x distribution over [1, 10000] closely follows Benford's Law
    return [10 ** rng.uniform(0, 4) for _ in range(n)]


class TestBenfordsAnalyzerHappyPath:
    def test_conforming_data(self) -> None:
        """Benford-distributed data should yield high conformity (>0.7)."""
        amounts = _benford_distributed_amounts(500)
        result = BenfordsAnalyzer.analyze(_make_txns(amounts))

        assert isinstance(result, BenfordsResult)
        assert result.conformity_score >= 0.7
        assert result.first_digit is not None
        assert result.first_digit.passes is True
        assert result.sample_size == 500
        assert result.summary != ""

    def test_second_digit_present_for_large_samples(self) -> None:
        """With >=100 transactions, second digit analysis should be present."""
        amounts = _benford_distributed_amounts(200)
        result = BenfordsAnalyzer.analyze(_make_txns(amounts))

        assert result.second_digit is not None
        assert result.second_digit.sample_size >= 100

    def test_vendor_breakdown(self) -> None:
        """Vendor-level conformity scores should be populated."""
        # 300 txns, 5 vendors → 60 each, above MIN_SAMPLE of 50
        amounts = _benford_distributed_amounts(300)
        result = BenfordsAnalyzer.analyze(_make_txns(amounts))

        assert len(result.vendor_results) > 0

    def test_category_breakdown(self) -> None:
        """Category-level conformity scores should be populated."""
        amounts = _benford_distributed_amounts(300)
        result = BenfordsAnalyzer.analyze(_make_txns(amounts))

        assert len(result.category_results) > 0


class TestBenfordsAnalyzerEdgeCases:
    def test_too_few_transactions(self) -> None:
        """Below 50 transactions, should return early with conformity=1.0."""
        amounts = _benford_distributed_amounts(30)
        result = BenfordsAnalyzer.analyze(_make_txns(amounts))

        assert result.conformity_score == 1.0
        assert "insufficient" in result.summary.lower() or "too few" in result.summary.lower()

    def test_empty_transactions(self) -> None:
        """Empty list should not crash."""
        result = BenfordsAnalyzer.analyze([])
        assert result.conformity_score == 1.0
        assert result.sample_size == 0

    def test_negative_amounts_handled(self) -> None:
        """Negative amounts should be abs()'d and included."""
        amounts = [-a for a in _benford_distributed_amounts(100)]
        result = BenfordsAnalyzer.analyze(_make_txns(amounts))

        assert result.sample_size == 100
        assert result.conformity_score > 0.0

    def test_sub_threshold_amounts_filtered(self) -> None:
        """Amounts below min_amount should be excluded."""
        amounts = [0.5] * 80 + _benford_distributed_amounts(30)
        result = BenfordsAnalyzer.analyze(_make_txns(amounts), min_amount=1.0)

        # Only 30 valid → below MIN_SAMPLE (50)
        assert result.conformity_score == 1.0

    def test_skip_vendor_category_with_flag(self) -> None:
        """Can disable vendor/category breakdown."""
        amounts = _benford_distributed_amounts(100)
        result = BenfordsAnalyzer.analyze(
            _make_txns(amounts),
            include_vendor_breakdown=False,
            include_category_breakdown=False,
        )
        assert len(result.vendor_results) == 0
        assert len(result.category_results) == 0


class TestBenfordsNonConforming:
    def test_uniform_amounts_flag_non_conformity(self) -> None:
        """Uniformly distributed leading digits should score poorly."""
        # Create amounts where all leading digits are equally likely
        rng = random.Random(99)
        amounts = [rng.randint(1, 9) * 1000 + rng.randint(0, 999) for _ in range(500)]
        result = BenfordsAnalyzer.analyze(_make_txns(amounts))

        # Uniform ≠ Benford → should fail
        assert result.conformity_score < 0.7
        assert result.first_digit.passes is False

    def test_suspicious_digits_populated(self) -> None:
        """With non-conforming data, suspicious_digits should be non-empty."""
        # All amounts start with 9 → extremely non-Benford
        amounts = [9000 + i for i in range(200)]
        result = BenfordsAnalyzer.analyze(_make_txns(amounts))

        assert len(result.suspicious_digits) > 0
        assert result.conformity_score < 0.5
        # Digit 9 should be in suspicious list
        digits = [s["digit"] for s in result.suspicious_digits]
        assert 9 in digits
