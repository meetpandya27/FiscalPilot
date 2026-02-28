"""
Break-even Calculator — determine covers/revenue needed to cover all costs.

Helps restaurant owners answer:
- "How many covers do I need to make money?"
- "What's my minimum daily/weekly revenue target?"
- "At what point do I start making profit?"

Break-even Formula:
  Break-even Revenue = Fixed Costs / (1 - Variable Cost Ratio)
  Break-even Covers = Break-even Revenue / Average Check
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from fiscalpilot.models.financial import ExpenseCategory, FinancialDataset

logger = logging.getLogger("fiscalpilot.analyzers.breakeven")


class CostType(str, Enum):
    """Classification of restaurant costs."""
    FIXED = "fixed"        # Doesn't change with sales volume
    VARIABLE = "variable"  # Changes proportionally with sales
    SEMI_VARIABLE = "semi_variable"  # Has fixed and variable components


# Default classification of expense categories
DEFAULT_COST_CLASSIFICATION: dict[ExpenseCategory, CostType] = {
    # Fixed costs
    ExpenseCategory.RENT: CostType.FIXED,
    ExpenseCategory.INSURANCE: CostType.FIXED,
    ExpenseCategory.SOFTWARE: CostType.FIXED,
    ExpenseCategory.SUBSCRIPTIONS: CostType.FIXED,
    ExpenseCategory.PROFESSIONAL_FEES: CostType.FIXED,
    ExpenseCategory.INTEREST: CostType.FIXED,
    ExpenseCategory.DEPRECIATION: CostType.FIXED,

    # Variable costs
    ExpenseCategory.INVENTORY: CostType.VARIABLE,  # Food cost
    ExpenseCategory.SUPPLIES: CostType.VARIABLE,
    ExpenseCategory.SHIPPING: CostType.VARIABLE,

    # Semi-variable (default to fixed for simplicity)
    ExpenseCategory.PAYROLL: CostType.SEMI_VARIABLE,
    ExpenseCategory.UTILITIES: CostType.SEMI_VARIABLE,
    ExpenseCategory.MAINTENANCE: CostType.SEMI_VARIABLE,
    ExpenseCategory.MARKETING: CostType.SEMI_VARIABLE,
    ExpenseCategory.EQUIPMENT: CostType.FIXED,
    ExpenseCategory.TRAVEL: CostType.FIXED,
    ExpenseCategory.MEALS: CostType.VARIABLE,
    ExpenseCategory.TAXES: CostType.FIXED,
    ExpenseCategory.MISCELLANEOUS: CostType.SEMI_VARIABLE,
    ExpenseCategory.OTHER: CostType.SEMI_VARIABLE,
}


@dataclass
class CostBreakdown:
    """Breakdown of fixed and variable costs."""

    # Fixed costs
    rent: float = 0.0
    insurance: float = 0.0
    management_salaries: float = 0.0
    loan_payments: float = 0.0
    equipment_leases: float = 0.0
    software_subscriptions: float = 0.0
    base_utilities: float = 0.0
    other_fixed: float = 0.0

    # Variable costs (as % of revenue)
    food_cost_pct: float = 30.0
    hourly_labor_pct: float = 20.0
    supplies_pct: float = 2.0
    credit_card_fees_pct: float = 2.5
    delivery_commissions_pct: float = 0.0
    other_variable_pct: float = 1.0

    @property
    def total_fixed(self) -> float:
        """Total fixed costs per period."""
        return (
            self.rent +
            self.insurance +
            self.management_salaries +
            self.loan_payments +
            self.equipment_leases +
            self.software_subscriptions +
            self.base_utilities +
            self.other_fixed
        )

    @property
    def total_variable_pct(self) -> float:
        """Total variable costs as % of revenue."""
        return (
            self.food_cost_pct +
            self.hourly_labor_pct +
            self.supplies_pct +
            self.credit_card_fees_pct +
            self.delivery_commissions_pct +
            self.other_variable_pct
        )

    @property
    def contribution_margin_pct(self) -> float:
        """Contribution margin = 100% - variable cost %."""
        return 100.0 - self.total_variable_pct


@dataclass
class BreakevenResult:
    """Complete break-even analysis results."""

    # Core break-even metrics
    breakeven_revenue_daily: float = 0.0
    breakeven_revenue_weekly: float = 0.0
    breakeven_revenue_monthly: float = 0.0
    breakeven_revenue_annual: float = 0.0

    # Break-even in covers (guests)
    average_check: float = 0.0
    breakeven_covers_daily: float = 0.0
    breakeven_covers_weekly: float = 0.0
    breakeven_covers_monthly: float = 0.0

    # Cost breakdown
    total_fixed_monthly: float = 0.0
    total_variable_pct: float = 0.0
    contribution_margin_pct: float = 0.0

    # Scenario analysis
    current_revenue: float = 0.0
    current_covers: float = 0.0
    margin_of_safety_pct: float = 0.0  # How far above break-even
    profit_at_current_level: float = 0.0

    # Target scenarios
    scenarios: list[dict[str, Any]] = field(default_factory=list)

    # Insights
    insights: list[str] = field(default_factory=list)

    # Status
    is_above_breakeven: bool = False
    days_operating_per_week: int = 7


@dataclass
class ScenarioResult:
    """Result of a what-if scenario."""
    name: str
    revenue: float
    covers: float
    profit: float
    margin_pct: float


class BreakevenCalculator:
    """Calculate break-even point for restaurants."""

    @classmethod
    def calculate(
        cls,
        *,
        # Fixed costs (monthly)
        rent: float = 0.0,
        insurance: float = 0.0,
        management_salaries: float = 0.0,
        loan_payments: float = 0.0,
        equipment_leases: float = 0.0,
        software_subscriptions: float = 0.0,
        base_utilities: float = 0.0,
        other_fixed: float = 0.0,

        # Variable costs (% of revenue)
        food_cost_pct: float = 30.0,
        hourly_labor_pct: float = 20.0,
        supplies_pct: float = 2.0,
        credit_card_fees_pct: float = 2.5,
        delivery_commissions_pct: float = 0.0,
        other_variable_pct: float = 1.0,

        # Operating parameters
        average_check: float = 25.0,
        days_operating_per_week: int = 7,

        # Current performance (for comparison)
        current_monthly_revenue: float | None = None,
        current_monthly_covers: float | None = None,
    ) -> BreakevenResult:
        """
        Calculate break-even point with detailed analysis.

        Args:
            rent: Monthly rent
            insurance: Monthly insurance
            management_salaries: Monthly salaried labor (not hourly)
            loan_payments: Monthly loan/lease payments
            equipment_leases: Monthly equipment lease payments
            software_subscriptions: Monthly software costs
            base_utilities: Base monthly utilities (fixed portion)
            other_fixed: Other fixed monthly costs

            food_cost_pct: Food cost as % of revenue (typically 28-35%)
            hourly_labor_pct: Hourly labor as % of revenue (typically 18-25%)
            supplies_pct: Supplies as % of revenue (typically 2-4%)
            credit_card_fees_pct: CC processing fees (typically 2-3%)
            delivery_commissions_pct: Delivery platform fees (0% if no delivery, 15-30% for heavy delivery)
            other_variable_pct: Other variable costs

            average_check: Average check per guest ($/cover)
            days_operating_per_week: Days open per week

            current_monthly_revenue: Current revenue for comparison
            current_monthly_covers: Current covers for comparison

        Returns:
            BreakevenResult with complete analysis.
        """
        # Build cost breakdown
        costs = CostBreakdown(
            rent=rent,
            insurance=insurance,
            management_salaries=management_salaries,
            loan_payments=loan_payments,
            equipment_leases=equipment_leases,
            software_subscriptions=software_subscriptions,
            base_utilities=base_utilities,
            other_fixed=other_fixed,
            food_cost_pct=food_cost_pct,
            hourly_labor_pct=hourly_labor_pct,
            supplies_pct=supplies_pct,
            credit_card_fees_pct=credit_card_fees_pct,
            delivery_commissions_pct=delivery_commissions_pct,
            other_variable_pct=other_variable_pct,
        )

        # Calculate break-even
        contribution_margin_ratio = costs.contribution_margin_pct / 100.0

        if contribution_margin_ratio <= 0:
            # Can't break even if variable costs >= 100%
            return BreakevenResult(
                insights=["ERROR: Variable costs exceed 100% of revenue. Break-even impossible."],
            )

        # Monthly break-even
        breakeven_monthly = costs.total_fixed / contribution_margin_ratio

        # Convert to other periods
        days_per_month = days_operating_per_week * 4.33
        breakeven_daily = breakeven_monthly / days_per_month
        breakeven_weekly = breakeven_daily * days_operating_per_week
        breakeven_annual = breakeven_monthly * 12

        # Convert to covers
        if average_check > 0:
            breakeven_covers_daily = breakeven_daily / average_check
            breakeven_covers_weekly = breakeven_weekly / average_check
            breakeven_covers_monthly = breakeven_monthly / average_check
        else:
            breakeven_covers_daily = 0
            breakeven_covers_weekly = 0
            breakeven_covers_monthly = 0

        # Analyze current performance
        margin_of_safety = 0.0
        profit_at_current = 0.0
        is_above_breakeven = False

        if current_monthly_revenue and current_monthly_revenue > 0:
            margin_of_safety = ((current_monthly_revenue - breakeven_monthly) / current_monthly_revenue) * 100
            variable_costs_at_current = current_monthly_revenue * (costs.total_variable_pct / 100)
            profit_at_current = current_monthly_revenue - variable_costs_at_current - costs.total_fixed
            is_above_breakeven = current_monthly_revenue > breakeven_monthly

        # Generate scenarios
        scenarios = cls._generate_scenarios(
            breakeven_monthly=breakeven_monthly,
            costs=costs,
            average_check=average_check,
            current_revenue=current_monthly_revenue,
        )

        # Generate insights
        insights = cls._generate_insights(
            costs=costs,
            breakeven_monthly=breakeven_monthly,
            breakeven_daily=breakeven_daily,
            breakeven_covers_daily=breakeven_covers_daily,
            average_check=average_check,
            current_revenue=current_monthly_revenue,
            margin_of_safety=margin_of_safety,
            days_operating=days_operating_per_week,
        )

        return BreakevenResult(
            breakeven_revenue_daily=breakeven_daily,
            breakeven_revenue_weekly=breakeven_weekly,
            breakeven_revenue_monthly=breakeven_monthly,
            breakeven_revenue_annual=breakeven_annual,
            average_check=average_check,
            breakeven_covers_daily=breakeven_covers_daily,
            breakeven_covers_weekly=breakeven_covers_weekly,
            breakeven_covers_monthly=breakeven_covers_monthly,
            total_fixed_monthly=costs.total_fixed,
            total_variable_pct=costs.total_variable_pct,
            contribution_margin_pct=costs.contribution_margin_pct,
            current_revenue=current_monthly_revenue or 0,
            current_covers=current_monthly_covers or 0,
            margin_of_safety_pct=margin_of_safety,
            profit_at_current_level=profit_at_current,
            scenarios=scenarios,
            insights=insights,
            is_above_breakeven=is_above_breakeven,
            days_operating_per_week=days_operating_per_week,
        )

    @classmethod
    def from_dataset(
        cls,
        dataset: FinancialDataset,
        *,
        average_check: float = 25.0,
        days_operating_per_week: int = 7,
        labor_fixed_pct: float = 40.0,  # % of labor that's salaried/fixed
        utilities_fixed_pct: float = 50.0,  # % of utilities that's fixed
    ) -> BreakevenResult:
        """
        Calculate break-even from transaction data.

        Automatically classifies expenses as fixed or variable.

        Args:
            dataset: Financial data with transactions.
            average_check: Average check per guest.
            days_operating_per_week: Days open per week.
            labor_fixed_pct: % of payroll that's salaried (not hourly).
            utilities_fixed_pct: % of utilities that's base/fixed.

        Returns:
            BreakevenResult with analysis.
        """
        # Calculate totals by category
        totals_by_category: dict[ExpenseCategory, float] = {}
        total_income = 0.0

        for txn in dataset.transactions:
            if txn.type.value == "income":
                total_income += txn.amount
            elif txn.type.value == "expense" and txn.category:
                totals_by_category[txn.category] = (
                    totals_by_category.get(txn.category, 0) + txn.amount
                )

        # Annualize if partial year
        if dataset.period_start and dataset.period_end:
            days = (dataset.period_end - dataset.period_start).days + 1
            monthly_factor = 30.44 / days  # Convert to monthly
        else:
            monthly_factor = 1.0

        # Separate fixed and variable costs
        fixed_costs = 0.0
        variable_costs = 0.0

        for cat, amount in totals_by_category.items():
            monthly_amount = amount * monthly_factor
            classification = DEFAULT_COST_CLASSIFICATION.get(cat, CostType.FIXED)

            if classification == CostType.FIXED:
                fixed_costs += monthly_amount
            elif classification == CostType.VARIABLE:
                variable_costs += monthly_amount
            else:  # SEMI_VARIABLE
                # Split based on type
                if cat == ExpenseCategory.PAYROLL:
                    fixed_costs += monthly_amount * (labor_fixed_pct / 100)
                    variable_costs += monthly_amount * ((100 - labor_fixed_pct) / 100)
                elif cat == ExpenseCategory.UTILITIES:
                    fixed_costs += monthly_amount * (utilities_fixed_pct / 100)
                    variable_costs += monthly_amount * ((100 - utilities_fixed_pct) / 100)
                else:
                    # Default 50/50 split
                    fixed_costs += monthly_amount * 0.5
                    variable_costs += monthly_amount * 0.5

        # Calculate variable cost percentage
        monthly_revenue = total_income * monthly_factor
        variable_cost_pct = (variable_costs / monthly_revenue) * 100 if monthly_revenue > 0 else 55.0

        # Calculate with extracted values
        return cls.calculate(
            other_fixed=fixed_costs,
            food_cost_pct=0,  # Already in variable_costs
            hourly_labor_pct=0,
            supplies_pct=0,
            credit_card_fees_pct=2.5,  # Assume standard
            other_variable_pct=variable_cost_pct,
            average_check=average_check,
            days_operating_per_week=days_operating_per_week,
            current_monthly_revenue=monthly_revenue,
        )

    @classmethod
    def _generate_scenarios(
        cls,
        breakeven_monthly: float,
        costs: CostBreakdown,
        average_check: float,
        current_revenue: float | None,
    ) -> list[dict[str, Any]]:
        """Generate what-if scenarios."""
        scenarios = []
        cm_ratio = costs.contribution_margin_pct / 100

        # Scenario 1: 10% above break-even
        rev_110 = breakeven_monthly * 1.10
        profit_110 = (rev_110 * cm_ratio) - costs.total_fixed
        scenarios.append({
            "name": "10% Above Break-even",
            "revenue": rev_110,
            "covers": rev_110 / average_check if average_check > 0 else 0,
            "profit": profit_110,
            "margin_pct": (profit_110 / rev_110 * 100) if rev_110 > 0 else 0,
        })

        # Scenario 2: 25% above break-even
        rev_125 = breakeven_monthly * 1.25
        profit_125 = (rev_125 * cm_ratio) - costs.total_fixed
        scenarios.append({
            "name": "25% Above Break-even",
            "revenue": rev_125,
            "covers": rev_125 / average_check if average_check > 0 else 0,
            "profit": profit_125,
            "margin_pct": (profit_125 / rev_125 * 100) if rev_125 > 0 else 0,
        })

        # Scenario 3: Target 10% net margin
        target_margin = 0.10
        # Profit = Revenue * CM_ratio - Fixed
        # Revenue * target_margin = Revenue * CM_ratio - Fixed
        # Revenue * (CM_ratio - target_margin) = Fixed
        if cm_ratio > target_margin:
            rev_10pct = costs.total_fixed / (cm_ratio - target_margin)
            profit_10pct = rev_10pct * target_margin
            scenarios.append({
                "name": "Target 10% Net Margin",
                "revenue": rev_10pct,
                "covers": rev_10pct / average_check if average_check > 0 else 0,
                "profit": profit_10pct,
                "margin_pct": 10.0,
            })

        # Scenario 4: If food cost reduced by 3%
        if costs.food_cost_pct > 3:
            new_variable_pct = costs.total_variable_pct - 3
            new_cm_ratio = (100 - new_variable_pct) / 100
            new_breakeven = costs.total_fixed / new_cm_ratio
            savings = breakeven_monthly - new_breakeven
            scenarios.append({
                "name": "If Food Cost -3%",
                "breakeven_reduction": savings,
                "new_breakeven": new_breakeven,
                "description": f"Reducing food cost by 3% lowers break-even by ${savings:,.0f}/month",
            })

        return scenarios

    @classmethod
    def _generate_insights(
        cls,
        costs: CostBreakdown,
        breakeven_monthly: float,
        breakeven_daily: float,
        breakeven_covers_daily: float,
        average_check: float,
        current_revenue: float | None,
        margin_of_safety: float,
        days_operating: int,
    ) -> list[str]:
        """Generate actionable insights."""
        insights = []

        # Core break-even insight
        insights.append(
            f"📊 BREAK-EVEN: You need ${breakeven_daily:,.0f}/day "
            f"({breakeven_covers_daily:.0f} covers at ${average_check:.0f} avg check) "
            f"to cover all costs."
        )

        # Fixed cost analysis
        if costs.total_fixed > breakeven_monthly * 0.4:
            insights.append(
                f"⚠️ HIGH FIXED COSTS: Fixed costs are ${costs.total_fixed:,.0f}/month. "
                "Consider negotiating rent or reducing management overhead."
            )

        # Variable cost analysis
        if costs.food_cost_pct > 32:
            insights.append(
                f"⚠️ FOOD COST HIGH: At {costs.food_cost_pct:.1f}%, food cost is above the 32% benchmark. "
                "Each 1% reduction lowers break-even significantly."
            )

        if costs.hourly_labor_pct > 25:
            insights.append(
                f"⚠️ LABOR COST HIGH: Hourly labor at {costs.hourly_labor_pct:.1f}% is elevated. "
                "Review scheduling efficiency and consider cross-training."
            )

        if costs.delivery_commissions_pct > 10:
            insights.append(
                f"⚠️ DELIVERY COSTS: {costs.delivery_commissions_pct:.1f}% going to delivery platforms. "
                "Consider direct ordering incentives or renegotiating rates."
            )

        # Margin of safety
        if current_revenue and margin_of_safety > 0:
            if margin_of_safety > 20:
                insights.append(
                    f"✅ HEALTHY BUFFER: {margin_of_safety:.1f}% margin of safety above break-even. "
                    "Well-positioned for slow periods or unexpected costs."
                )
            elif margin_of_safety > 10:
                insights.append(
                    f"⚠️ MODERATE BUFFER: {margin_of_safety:.1f}% above break-even. "
                    "Limited cushion for slow periods."
                )
            else:
                insights.append(
                    f"🚨 THIN MARGIN: Only {margin_of_safety:.1f}% above break-even. "
                    "Very vulnerable to any revenue dip."
                )
        elif current_revenue and margin_of_safety < 0:
            insights.append(
                f"🚨 BELOW BREAK-EVEN: Currently {abs(margin_of_safety):.1f}% below break-even. "
                "Urgent action needed to increase revenue or cut costs."
            )

        # Contribution margin insight
        if costs.contribution_margin_pct < 40:
            insights.append(
                f"⚠️ LOW CONTRIBUTION MARGIN: Only {costs.contribution_margin_pct:.1f}% of each dollar "
                "contributes to fixed costs and profit. Consider menu price increases."
            )

        return insights


def calculate_breakeven(**kwargs: Any) -> BreakevenResult:
    """Convenience function for break-even calculation.

    See BreakevenCalculator.calculate() for full parameter documentation.
    """
    return BreakevenCalculator.calculate(**kwargs)
