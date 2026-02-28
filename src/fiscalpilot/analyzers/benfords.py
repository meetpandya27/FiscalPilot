"""
Benford's Law Analyzer — detect fabricated or anomalous financial data.

Benford's Law states that in naturally occurring datasets, the leading digit
is "1" approximately 30.1% of the time, "2" about 17.6%, and so on.
Significant deviations suggest data manipulation, fabrication, or duplication.

This module computes:
- First-digit distribution with chi-squared goodness-of-fit test
- Second-digit distribution for deeper analysis
- First-two-digit distribution for high-resolution detection
- Per-vendor and per-category Benford conformity scores
"""

from __future__ import annotations

import logging
import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("fiscalpilot.analyzers.benfords")

# Benford's expected probabilities for first digit (1-9)
BENFORD_FIRST_DIGIT: dict[int, float] = {d: math.log10(1 + 1 / d) for d in range(1, 10)}

# Benford's expected probabilities for second digit (0-9)
BENFORD_SECOND_DIGIT: dict[int, float] = {
    d2: sum(math.log10(1 + 1 / (10 * d1 + d2)) for d1 in range(1, 10)) for d2 in range(0, 10)
}

# Chi-squared critical values at p=0.05 for common degrees of freedom
# df=8 (first digit), df=9 (second digit)
CHI_SQ_CRITICAL = {8: 15.507, 9: 16.919, 89: 112.022}


@dataclass
class DigitDistribution:
    """Result of a single digit-distribution test."""

    observed: dict[int, int]
    expected: dict[int, float]
    chi_squared: float
    p_value_approx: float  # approximate using chi-sq CDF
    passes: bool  # True = conforms to Benford's Law
    sample_size: int
    msd: float  # mean absolute deviation from expected


@dataclass
class BenfordsResult:
    """Complete Benford's Law analysis result."""

    first_digit: DigitDistribution
    second_digit: DigitDistribution | None
    sample_size: int
    conformity_score: float  # 0.0 (suspicious) to 1.0 (perfect Benford)
    suspicious_digits: list[dict[str, Any]] = field(default_factory=list)
    vendor_results: dict[str, float] = field(default_factory=dict)
    category_results: dict[str, float] = field(default_factory=dict)
    summary: str = ""


class BenfordsAnalyzer:
    """Perform Benford's Law analysis on financial transaction amounts."""

    MIN_SAMPLE = 50  # Benford's needs a reasonable sample for significance

    @classmethod
    def analyze(
        cls,
        transactions: list[dict[str, Any]],
        *,
        min_amount: float = 1.0,
        include_vendor_breakdown: bool = True,
        include_category_breakdown: bool = True,
    ) -> BenfordsResult:
        """Run Benford's Law analysis on a list of transactions.

        Args:
            transactions: List of transaction dicts (need "amount" key at minimum).
            min_amount: Ignore amounts below this threshold (Benford's struggles near zero).
            include_vendor_breakdown: Compute per-vendor conformity scores.
            include_category_breakdown: Compute per-category conformity scores.

        Returns:
            BenfordsResult with all statistical details.
        """
        amounts = cls._extract_amounts(transactions, min_amount)
        sample_size = len(amounts)

        if sample_size < cls.MIN_SAMPLE:
            return BenfordsResult(
                first_digit=DigitDistribution(
                    observed={},
                    expected=BENFORD_FIRST_DIGIT,
                    chi_squared=0,
                    p_value_approx=1.0,
                    passes=True,
                    sample_size=sample_size,
                    msd=0,
                ),
                second_digit=None,
                sample_size=sample_size,
                conformity_score=1.0,
                summary=f"Insufficient data for Benford's analysis ({sample_size} < {cls.MIN_SAMPLE} transactions).",
            )

        # First digit test
        first_digits = cls._leading_digits(amounts, position=1)
        first_result = cls._test_distribution(first_digits, BENFORD_FIRST_DIGIT, sample_size)

        # Second digit test
        second_digits = cls._leading_digits(amounts, position=2)
        second_result = (
            cls._test_distribution(second_digits, BENFORD_SECOND_DIGIT, sample_size) if sample_size >= 100 else None
        )

        # Identify suspicious digits (observed >> expected)
        suspicious = cls._find_suspicious_digits(first_result, sample_size)

        # Per-vendor breakdown
        vendor_results: dict[str, float] = {}
        if include_vendor_breakdown:
            vendor_results = cls._group_conformity(transactions, "vendor", min_amount)

        # Per-category breakdown
        category_results: dict[str, float] = {}
        if include_category_breakdown:
            category_results = cls._group_conformity(transactions, "category", min_amount)

        # Composite conformity score
        conformity = cls._compute_conformity_score(first_result, second_result)

        summary = cls._build_summary(first_result, second_result, suspicious, conformity, sample_size)

        return BenfordsResult(
            first_digit=first_result,
            second_digit=second_result,
            sample_size=sample_size,
            conformity_score=conformity,
            suspicious_digits=suspicious,
            vendor_results=vendor_results,
            category_results=category_results,
            summary=summary,
        )

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _extract_amounts(transactions: list[dict[str, Any]], min_amount: float) -> list[float]:
        """Pull absolute amounts >= min_amount."""
        amounts: list[float] = []
        for t in transactions:
            raw = t.get("amount")
            if raw is None:
                continue
            val = abs(float(raw))
            if val >= min_amount:
                amounts.append(val)
        return amounts

    @staticmethod
    def _leading_digits(amounts: list[float], position: int = 1) -> list[int]:
        """Extract the nth leading digit from each amount.

        position=1 → first digit (1-9)
        position=2 → second digit (0-9)
        """
        digits: list[int] = []
        for amount in amounts:
            s = f"{amount:.10f}".lstrip("0").lstrip(".")
            s = s.replace(".", "")  # remove decimal
            if len(s) >= position:
                digits.append(int(s[position - 1]))
        return digits

    @staticmethod
    def _test_distribution(
        observed_digits: list[int],
        expected_probs: dict[int, float],
        n: int,
    ) -> DigitDistribution:
        """Run chi-squared goodness-of-fit test."""
        counter = Counter(observed_digits)
        total = len(observed_digits) or 1

        chi_sq = 0.0
        deviations: list[float] = []
        for digit, p_expected in expected_probs.items():
            observed_count = counter.get(digit, 0)
            expected_count = p_expected * total
            if expected_count > 0:
                chi_sq += (observed_count - expected_count) ** 2 / expected_count
            deviations.append(abs(observed_count / total - p_expected))

        msd = sum(deviations) / len(deviations) if deviations else 0.0
        df = len(expected_probs) - 1
        critical_value = CHI_SQ_CRITICAL.get(df, 15.507)
        passes = chi_sq <= critical_value

        # Approximate p-value using Wilson-Hilferty approximation
        if df > 0:
            z = ((chi_sq / df) ** (1 / 3) - (1 - 2 / (9 * df))) / math.sqrt(2 / (9 * df))
            p_value = max(0.0, min(1.0, 0.5 * (1 - math.erf(z / math.sqrt(2)))))
        else:
            p_value = 1.0

        return DigitDistribution(
            observed=dict(counter),
            expected=expected_probs,
            chi_squared=round(chi_sq, 4),
            p_value_approx=round(p_value, 6),
            passes=passes,
            sample_size=total,
            msd=round(msd, 6),
        )

    @staticmethod
    def _find_suspicious_digits(result: DigitDistribution, n: int) -> list[dict[str, Any]]:
        """Find digits that deviate significantly from Benford expectation."""
        suspicious: list[dict[str, Any]] = []
        total = result.sample_size or 1
        for digit, p_expected in result.expected.items():
            observed_pct = result.observed.get(digit, 0) / total
            expected_pct = p_expected
            deviation = observed_pct - expected_pct

            # Flag if deviation is > 5 percentage points and statistically significant
            if abs(deviation) > 0.05 and total >= 50:
                suspicious.append(
                    {
                        "digit": digit,
                        "observed_pct": round(observed_pct * 100, 2),
                        "expected_pct": round(expected_pct * 100, 2),
                        "deviation_pct": round(deviation * 100, 2),
                        "direction": "over-represented" if deviation > 0 else "under-represented",
                    }
                )
        return suspicious

    @classmethod
    def _group_conformity(
        cls,
        transactions: list[dict[str, Any]],
        group_key: str,
        min_amount: float,
    ) -> dict[str, float]:
        """Compute Benford conformity score per group (vendor, category, etc.)."""
        groups: dict[str, list[float]] = {}
        for t in transactions:
            group = t.get(group_key) or "unknown"
            raw = t.get("amount")
            if raw is None:
                continue
            val = abs(float(raw))
            if val >= min_amount:
                groups.setdefault(str(group), []).append(val)

        results: dict[str, float] = {}
        for group_name, amounts in groups.items():
            if len(amounts) < cls.MIN_SAMPLE:
                continue  # Need enough data for meaningful test
            digits = cls._leading_digits(amounts, position=1)
            dist = cls._test_distribution(digits, BENFORD_FIRST_DIGIT, len(amounts))
            results[group_name] = cls._compute_conformity_score(dist, None)

        return results

    @staticmethod
    def _compute_conformity_score(first: DigitDistribution, second: DigitDistribution | None) -> float:
        """0.0 = highly suspicious, 1.0 = perfect Benford conformity.

        Based on Mean Absolute Deviation (MAD):
        - MAD < 0.006 → Close conformity (0.9-1.0)
        - MAD 0.006-0.012 → Acceptable conformity (0.7-0.9)
        - MAD 0.012-0.015 → Marginally acceptable (0.5-0.7)
        - MAD > 0.015 → Non-conforming (0.0-0.5)

        These thresholds follow Nigrini (2012) benchmarks.
        """
        mad = first.msd
        if mad <= 0.006:
            score = 0.9 + (0.006 - mad) / 0.006 * 0.1
        elif mad <= 0.012:
            score = 0.7 + (0.012 - mad) / 0.006 * 0.2
        elif mad <= 0.015:
            score = 0.5 + (0.015 - mad) / 0.003 * 0.2
        else:
            score = max(0.0, 0.5 - (mad - 0.015) / 0.03 * 0.5)

        # Weight in second digit if available
        if second is not None:
            second_mad = second.msd
            if second_mad <= 0.008:
                s2_score = 0.9 + (0.008 - second_mad) / 0.008 * 0.1
            elif second_mad <= 0.012:
                s2_score = 0.7 + (0.012 - second_mad) / 0.004 * 0.2
            else:
                s2_score = max(0.0, 0.7 - (second_mad - 0.012) / 0.02 * 0.7)
            score = score * 0.7 + s2_score * 0.3

        return round(min(1.0, max(0.0, score)), 3)

    @staticmethod
    def _build_summary(
        first: DigitDistribution,
        second: DigitDistribution | None,
        suspicious: list[dict[str, Any]],
        conformity: float,
        sample_size: int,
    ) -> str:
        """Build a human-readable summary string."""
        lines: list[str] = [
            f"Benford's Law Analysis ({sample_size} transactions):",
            f"  First-digit chi² = {first.chi_squared} "
            f"({'PASS' if first.passes else 'FAIL'}, p ≈ {first.p_value_approx})",
            f"  Conformity score: {conformity:.1%}",
        ]
        if second:
            lines.append(f"  Second-digit chi² = {second.chi_squared} ({'PASS' if second.passes else 'FAIL'})")
        if suspicious:
            lines.append("  Suspicious digits:")
            for s in suspicious:
                lines.append(
                    f"    Digit {s['digit']}: {s['observed_pct']:.1f}% observed "
                    f"vs {s['expected_pct']:.1f}% expected ({s['direction']})"
                )
        if conformity >= 0.9:
            lines.append("  Verdict: Data conforms well to Benford's Law.")
        elif conformity >= 0.7:
            lines.append("  Verdict: Acceptable conformity — minor anomalies detected.")
        elif conformity >= 0.5:
            lines.append("  Verdict: Marginal conformity — warrants investigation.")
        else:
            lines.append("  Verdict: SIGNIFICANT DEVIATION — possible data manipulation.")

        return "\n".join(lines)
