"""
Tax Optimization Engine — rule-based tax savings detection.

Scans financial data for common tax optimization opportunities:
1. **Miscategorized expenses** — deductible expenses coded incorrectly
2. **Missing deductions** — common business deductions that appear unused
3. **Timing opportunities** — expenses that could be shifted for tax benefit
4. **Entity structure** — flags when S-Corp/LLC might save self-employment tax
5. **Retirement contributions** — detects under-utilization of tax-advantaged accounts
6. **Depreciation** — identifies assets that could use accelerated depreciation

No LLM calls — rule-based pattern matching with configurable tax rates.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("fiscalpilot.analyzers.tax_optimizer")


def _enum_str(val: Any) -> str:
    """Extract string from enum or return str(val). Handles Pydantic model_dump() enum instances."""
    return val.value if hasattr(val, "value") else str(val)


# Common deductible categories and typical deduction rates
DEDUCTIBLE_CATEGORIES = {
    "meals": 0.50,  # 50% deductible for business meals
    "travel": 1.00,
    "software": 1.00,
    "subscriptions": 1.00,
    "insurance": 1.00,
    "professional_fees": 1.00,
    "supplies": 1.00,
    "marketing": 1.00,
    "rent": 1.00,
    "utilities": 1.00,
    "equipment": 1.00,  # Section 179 / depreciation
    "maintenance": 1.00,
    "shipping": 1.00,
    "interest": 1.00,
    "depreciation": 1.00,
}

# Keywords that suggest deductible expenses miscategorized as "other"/"miscellaneous"
DEDUCTION_KEYWORDS = {
    "office": "supplies",
    "quickbooks": "software",
    "adobe": "software",
    "slack": "software",
    "zoom": "software",
    "microsoft": "software",
    "google workspace": "software",
    "aws": "software",
    "hosting": "software",
    "domain": "marketing",
    "advertising": "marketing",
    "facebook ads": "marketing",
    "google ads": "marketing",
    "legal": "professional_fees",
    "attorney": "professional_fees",
    "accountant": "professional_fees",
    "cpa": "professional_fees",
    "bookkeeper": "professional_fees",
    "consulting": "professional_fees",
    "mileage": "travel",
    "uber": "travel",
    "lyft": "travel",
    "airline": "travel",
    "hotel": "travel",
    "parking": "travel",
    "toll": "travel",
    "cell phone": "utilities",
    "internet": "utilities",
    "phone": "utilities",
    "electricity": "utilities",
    "water": "utilities",
    "repair": "maintenance",
    "cleaning": "maintenance",
    "insurance": "insurance",
    "premium": "insurance",
}


@dataclass
class TaxOpportunity:
    """A single tax optimization opportunity."""

    title: str
    category: str  # "miscategorized", "missing_deduction", "timing", "entity", "retirement", "depreciation"
    estimated_savings: float
    confidence: float  # 0.0-1.0
    description: str
    recommendation: str
    affected_transactions: list[str] = field(default_factory=list)


@dataclass
class TaxOptimizationResult:
    """Complete tax optimization analysis."""

    opportunities: list[TaxOpportunity] = field(default_factory=list)
    total_estimated_savings: float = 0.0
    effective_tax_rate: float = 0.25  # Assumed
    total_deductible: float = 0.0
    total_potentially_deductible: float = 0.0
    uncategorized_spend: float = 0.0
    summary: str = ""


class TaxOptimizer:
    """Rule-based tax optimization scanner."""

    DEFAULT_TAX_RATE = 0.25  # 25% combined federal + state estimate
    SE_TAX_RATE = 0.153  # 15.3% self-employment tax

    @classmethod
    def analyze(
        cls,
        transactions: list[dict[str, Any]],
        *,
        annual_revenue: float = 0,
        entity_type: str = "unknown",  # sole_prop, llc, s_corp, c_corp
        tax_rate: float = 0.25,
        has_retirement_plan: bool | None = None,
    ) -> TaxOptimizationResult:
        """Scan transactions for tax optimization opportunities.

        Args:
            transactions: Transaction dicts with "amount", "type", "category", "description".
            annual_revenue: Annual revenue for ratio calculations.
            entity_type: Business entity type for structure-specific advice.
            tax_rate: Effective tax rate for savings calculations.
            has_retirement_plan: Whether the business has retirement contributions.

        Returns:
            TaxOptimizationResult with all detected opportunities.
        """
        opportunities: list[TaxOpportunity] = []

        # Compute spend breakdown
        category_spend, uncategorized, total_expenses = cls._categorize_spend(transactions)

        # 1. Miscategorized expenses — deductible items coded as "other"/"miscellaneous"
        miscat = cls._find_miscategorized(transactions, tax_rate)
        opportunities.extend(miscat)

        # 2. Missing common deductions
        missing = cls._find_missing_deductions(category_spend, annual_revenue, tax_rate)
        opportunities.extend(missing)

        # 3. Equipment / Section 179 depreciation
        depreciation = cls._find_depreciation_opportunities(transactions, tax_rate)
        opportunities.extend(depreciation)

        # 4. Entity structure optimization
        if entity_type in ("sole_prop", "llc", "unknown") and annual_revenue > 50_000:
            entity_opp = cls._evaluate_entity_structure(annual_revenue, total_expenses, tax_rate)
            if entity_opp:
                opportunities.append(entity_opp)

        # 5. Retirement contribution opportunities
        if has_retirement_plan is not True and annual_revenue > 30_000:
            retirement = cls._evaluate_retirement(annual_revenue, total_expenses, tax_rate)
            if retirement:
                opportunities.append(retirement)

        # 6. Meal deduction optimization
        meal_opp = cls._evaluate_meal_deductions(transactions, tax_rate)
        if meal_opp:
            opportunities.append(meal_opp)

        # Compute totals
        total_savings = sum(o.estimated_savings for o in opportunities)
        total_deductible = sum(
            spend * DEDUCTIBLE_CATEGORIES.get(cat, 0)
            for cat, spend in category_spend.items()
        )

        opportunities.sort(key=lambda o: o.estimated_savings, reverse=True)

        summary = cls._build_summary(
            opportunities, total_savings, total_deductible, uncategorized, tax_rate
        )

        return TaxOptimizationResult(
            opportunities=opportunities,
            total_estimated_savings=round(total_savings, 2),
            effective_tax_rate=tax_rate,
            total_deductible=round(total_deductible, 2),
            total_potentially_deductible=round(total_deductible + uncategorized * 0.5, 2),
            uncategorized_spend=round(uncategorized, 2),
            summary=summary,
        )

    # ------------------------------------------------------------------ #
    #  Detection methods                                                  #
    # ------------------------------------------------------------------ #

    @classmethod
    def _find_miscategorized(
        cls,
        transactions: list[dict[str, Any]],
        tax_rate: float,
    ) -> list[TaxOpportunity]:
        """Find expenses in 'other'/'miscellaneous' that match deductible keywords."""
        miscat_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for t in transactions:
            cat = _enum_str(t.get("category", "")).lower()
            if cat not in ("other", "miscellaneous", ""):
                continue

            desc = _enum_str(t.get("description", "")).lower()
            vendor = _enum_str(t.get("vendor", "")).lower()
            combined = f"{desc} {vendor}"

            for keyword, proper_cat in DEDUCTION_KEYWORDS.items():
                if keyword in combined:
                    miscat_groups[proper_cat].append(t)
                    break

        opportunities: list[TaxOpportunity] = []
        for proper_cat, txns in miscat_groups.items():
            total = sum(abs(float(t.get("amount", 0))) for t in txns)
            if total < 100:  # Skip trivial amounts
                continue
            deduction_rate = DEDUCTIBLE_CATEGORIES.get(proper_cat, 1.0)
            savings = total * deduction_rate * tax_rate
            cat_label = proper_cat.replace("_", " ").title()

            opportunities.append(TaxOpportunity(
                title=f"Reclassify {len(txns)} transactions as {cat_label}",
                category="miscategorized",
                estimated_savings=round(savings, 2),
                confidence=0.75,
                description=(
                    f"Found {len(txns)} transactions (${total:,.2f}) categorized as 'other' "
                    f"that appear to be {cat_label} expenses — fully deductible."
                ),
                recommendation=(
                    f"Reclassify these as '{proper_cat}' for proper tax deduction. "
                    f"Estimated tax savings: ${savings:,.2f}/yr."
                ),
                affected_transactions=[t.get("id", "") for t in txns if t.get("id")],
            ))

        return opportunities

    @staticmethod
    def _find_missing_deductions(
        category_spend: dict[str, float],
        annual_revenue: float,
        tax_rate: float,
    ) -> list[TaxOpportunity]:
        """Flag common deduction categories with zero spend."""
        if annual_revenue <= 0:
            return []

        opportunities: list[TaxOpportunity] = []

        # Common deductions every business should have
        expected_deductions = {
            "professional_fees": (
                "Accounting/legal fees",
                "Most businesses benefit from professional tax and legal advice. "
                "Estimated deduction: 2-5% of revenue.",
                0.02,
            ),
            "insurance": (
                "Business insurance",
                "Business liability, property, and professional insurance premiums are deductible.",
                0.015,
            ),
        }

        for cat, (title, desc, pct) in expected_deductions.items():
            if category_spend.get(cat, 0) == 0:
                estimated_deduction = annual_revenue * pct
                savings = estimated_deduction * tax_rate
                if savings >= 100:
                    opportunities.append(TaxOpportunity(
                        title=f"No {title} deductions found",
                        category="missing_deduction",
                        estimated_savings=round(savings, 2),
                        confidence=0.5,
                        description=f"No transactions found for '{cat}'. {desc}",
                        recommendation=(
                            f"Verify if {title.lower()} are being tracked. If currently "
                            f"uncategorized, properly classify them for ~${savings:,.2f} in tax savings."
                        ),
                    ))

        return opportunities

    @classmethod
    def _find_depreciation_opportunities(
        cls,
        transactions: list[dict[str, Any]],
        tax_rate: float,
    ) -> list[TaxOpportunity]:
        """Identify equipment purchases eligible for Section 179 or bonus depreciation."""
        equipment_txns = [
            t for t in transactions
            if _enum_str(t.get("category", "")).lower() == "equipment"
            and abs(float(t.get("amount", 0))) >= 500
        ]

        if not equipment_txns:
            return []

        total_equipment = sum(abs(float(t.get("amount", 0))) for t in equipment_txns)
        savings = total_equipment * tax_rate  # Full deduction via Section 179

        return [TaxOpportunity(
            title=f"Section 179 deduction for {len(equipment_txns)} equipment purchases",
            category="depreciation",
            estimated_savings=round(savings, 2),
            confidence=0.7,
            description=(
                f"Found ${total_equipment:,.2f} in equipment purchases. Under Section 179, "
                f"businesses can deduct the full cost of qualifying equipment in the year purchased "
                f"(up to $1.16M for 2025)."
            ),
            recommendation=(
                f"Elect Section 179 expensing for qualifying equipment to deduct "
                f"${total_equipment:,.2f} immediately instead of depreciating over multiple years. "
                f"Consult your CPA for eligibility."
            ),
            affected_transactions=[t.get("id", "") for t in equipment_txns if t.get("id")],
        )]

    @classmethod
    def _evaluate_entity_structure(
        cls,
        revenue: float,
        expenses: float,
        tax_rate: float,
    ) -> TaxOpportunity | None:
        """Evaluate if S-Corp election could save self-employment tax."""
        net_income = revenue - expenses
        if net_income < 40_000:
            return None

        # S-Corp: pay reasonable salary, rest as distributions (no SE tax)
        reasonable_salary = min(net_income * 0.6, 160_200)  # SS wage base
        distribution = net_income - reasonable_salary
        se_savings = distribution * cls.SE_TAX_RATE * 0.5  # Rough savings

        if se_savings < 2_000:
            return None

        return TaxOpportunity(
            title="Evaluate S-Corp election for self-employment tax savings",
            category="entity_structure",
            estimated_savings=round(se_savings, 2),
            confidence=0.6,
            description=(
                f"Net income of ${net_income:,.2f} could benefit from S-Corp election. "
                f"As a sole proprietor/LLC, the full amount is subject to 15.3% self-employment tax. "
                f"As an S-Corp, only a reasonable salary is subject to payroll tax."
            ),
            recommendation=(
                f"Consult a CPA about S-Corp election. With a reasonable salary of "
                f"${reasonable_salary:,.2f} and distributions of ${distribution:,.2f}, "
                f"estimated annual savings: ${se_savings:,.2f}."
            ),
        )

    @classmethod
    def _evaluate_retirement(
        cls,
        revenue: float,
        expenses: float,
        tax_rate: float,
    ) -> TaxOpportunity | None:
        """Check for retirement contribution optimization."""
        net_income = revenue - expenses
        if net_income < 20_000:
            return None

        # SEP IRA: up to 25% of net self-employment income, max $69,000 (2025)
        max_contribution = min(net_income * 0.25, 69_000)
        savings = max_contribution * tax_rate

        if savings < 500:
            return None

        return TaxOpportunity(
            title="Tax-deferred retirement contributions",
            category="retirement",
            estimated_savings=round(savings, 2),
            confidence=0.7,
            description=(
                f"No retirement plan contributions detected. A SEP IRA allows "
                f"contributions up to 25% of net income (${max_contribution:,.2f} estimated)."
            ),
            recommendation=(
                f"Open a SEP IRA or Solo 401(k) before tax year end. "
                f"Maximum contribution: ${max_contribution:,.2f}. "
                f"Tax savings at {tax_rate:.0%} rate: ${savings:,.2f}. "
                f"This also builds retirement wealth."
            ),
        )

    @staticmethod
    def _evaluate_meal_deductions(
        transactions: list[dict[str, Any]],
        tax_rate: float,
    ) -> TaxOpportunity | None:
        """Check if business meals are being properly deducted at 50%."""
        meal_txns = [
            t for t in transactions
            if _enum_str(t.get("category", "")).lower() == "meals"
        ]
        if not meal_txns:
            return None

        total_meals = sum(abs(float(t.get("amount", 0))) for t in meal_txns)
        if total_meals < 200:
            return None

        deductible = total_meals * 0.50
        savings = deductible * tax_rate

        return TaxOpportunity(
            title="Verify business meal documentation for 50% deduction",
            category="documentation",
            estimated_savings=round(savings, 2),
            confidence=0.65,
            description=(
                f"Found ${total_meals:,.2f} in meal expenses. Business meals are "
                f"50% deductible when properly documented with business purpose, "
                f"attendees, and receipts."
            ),
            recommendation=(
                f"Ensure all {len(meal_txns)} meal transactions have proper documentation. "
                f"The 50% deduction on ${total_meals:,.2f} = ${deductible:,.2f} deductible, "
                f"saving ~${savings:,.2f} in taxes."
            ),
        )

    # ------------------------------------------------------------------ #
    #  Helpers                                                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _categorize_spend(
        transactions: list[dict[str, Any]],
    ) -> tuple[dict[str, float], float, float]:
        """Returns (category_spend, uncategorized_total, total_expenses)."""
        category_spend: dict[str, float] = defaultdict(float)
        uncategorized = 0.0
        total = 0.0

        for t in transactions:
            txn_type = _enum_str(t.get("type", "expense"))
            if txn_type not in ("expense", "payroll", "tax"):
                continue
            amount = abs(float(t.get("amount", 0)))
            total += amount
            cat = _enum_str(t.get("category", "")).lower()
            if cat in ("", "other", "miscellaneous"):
                uncategorized += amount
            else:
                category_spend[cat] += amount

        return dict(category_spend), uncategorized, total

    @staticmethod
    def _build_summary(
        opportunities: list[TaxOpportunity],
        total_savings: float,
        total_deductible: float,
        uncategorized: float,
        tax_rate: float,
    ) -> str:
        lines = [
            f"Tax Optimization Analysis (effective rate: {tax_rate:.0%}):",
            f"  Opportunities found: {len(opportunities)}",
            f"  Total estimated tax savings: ${total_savings:,.2f}",
            f"  Currently deductible spend: ${total_deductible:,.2f}",
            f"  Uncategorized spend: ${uncategorized:,.2f}",
        ]
        if opportunities:
            lines.append("  Top opportunities:")
            for o in opportunities[:5]:
                lines.append(f"    ${o.estimated_savings:,.2f} — {o.title}")
        return "\n".join(lines)
