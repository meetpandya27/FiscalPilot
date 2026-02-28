"""
Delivery Platform ROI Analyzer — calculate true profitability of delivery orders.

Most restaurant owners see delivery revenue as "extra money" but fail to account for:
- Platform commissions (15-30% of order value)
- Packaging costs ($0.50-2.00 per order)
- Additional labor for order prep
- Tablet/POS fees
- Refunds and adjustments eaten by restaurant
- Marketing/promotion spend

This analyzer shows TRUE profit per delivery order vs dine-in to help owners decide:
1. Is delivery worth it at all?
2. Should I raise delivery menu prices?
3. Which platforms should I prioritize?
4. Should I push customers to direct ordering?
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("fiscalpilot.analyzers.delivery_roi")


class DeliveryPlatform(str, Enum):
    """Major delivery platforms."""

    DOORDASH = "doordash"
    UBER_EATS = "uber_eats"
    GRUBHUB = "grubhub"
    POSTMATES = "postmates"  # Now part of Uber Eats
    CAVIAR = "caviar"  # Now part of DoorDash
    DIRECT = "direct"  # Restaurant's own ordering
    PHONE = "phone"  # Phone orders with in-house delivery


@dataclass
class PlatformFees:
    """Fee structure for a delivery platform."""

    platform: DeliveryPlatform

    # Commission (% of subtotal)
    commission_pct: float = 15.0

    # Per-order fees
    per_order_fee: float = 0.0
    tablet_fee_monthly: float = 0.0

    # Payment processing (if applicable)
    payment_processing_pct: float = 0.0

    # Marketing fees (if opted in)
    marketing_fee_pct: float = 0.0

    # Typical adjustment/error rate
    adjustment_rate_pct: float = 2.0  # % of orders with refunds/adjustments


# Typical fee structures by platform (2024 estimates)
DEFAULT_PLATFORM_FEES: dict[DeliveryPlatform, PlatformFees] = {
    DeliveryPlatform.DOORDASH: PlatformFees(
        platform=DeliveryPlatform.DOORDASH,
        commission_pct=15.0,  # Basic plan, can go up to 30%
        per_order_fee=0.0,
        tablet_fee_monthly=0.0,
        payment_processing_pct=2.9,
        marketing_fee_pct=0.0,  # DashPass ads extra
        adjustment_rate_pct=2.5,
    ),
    DeliveryPlatform.UBER_EATS: PlatformFees(
        platform=DeliveryPlatform.UBER_EATS,
        commission_pct=15.0,  # Lite plan, up to 30% for full
        per_order_fee=0.0,
        tablet_fee_monthly=0.0,
        payment_processing_pct=2.9,
        marketing_fee_pct=0.0,
        adjustment_rate_pct=3.0,
    ),
    DeliveryPlatform.GRUBHUB: PlatformFees(
        platform=DeliveryPlatform.GRUBHUB,
        commission_pct=15.0,  # Basic, up to 30%
        per_order_fee=0.0,
        tablet_fee_monthly=0.0,
        payment_processing_pct=2.9,
        marketing_fee_pct=0.0,
        adjustment_rate_pct=2.0,
    ),
    DeliveryPlatform.DIRECT: PlatformFees(
        platform=DeliveryPlatform.DIRECT,
        commission_pct=0.0,
        per_order_fee=0.0,
        tablet_fee_monthly=0.0,
        payment_processing_pct=2.5,  # Stripe/Square
        marketing_fee_pct=0.0,
        adjustment_rate_pct=1.0,
    ),
}


@dataclass
class DeliveryOrderData:
    """Aggregated delivery data for analysis."""

    platform: DeliveryPlatform

    # Volume metrics
    total_orders: int = 0
    total_gross_revenue: float = 0.0  # Before platform takes cut

    # Cost inputs
    food_cost_pct: float = 30.0  # Same as dine-in or higher?
    packaging_cost_per_order: float = 0.75
    labor_cost_per_order: float = 0.50  # Incremental labor

    # Platform fees (override defaults)
    commission_pct: float | None = None
    per_order_fee: float | None = None
    payment_processing_pct: float | None = None
    marketing_spend: float = 0.0  # Total marketing spend on platform

    # Adjustments
    total_refunds: float = 0.0
    total_adjustments: float = 0.0  # Error charges, missing items


@dataclass
class PlatformROIResult:
    """ROI analysis for a single platform."""

    platform: DeliveryPlatform
    platform_name: str = ""

    # Volume
    total_orders: int = 0
    total_gross_revenue: float = 0.0
    average_order_value: float = 0.0

    # Revenue after platform fees
    commission_paid: float = 0.0
    per_order_fees_paid: float = 0.0
    payment_processing_paid: float = 0.0
    marketing_spent: float = 0.0
    total_platform_fees: float = 0.0
    net_revenue: float = 0.0

    # Costs
    food_cost: float = 0.0
    packaging_cost: float = 0.0
    labor_cost: float = 0.0
    refunds_adjustments: float = 0.0
    total_costs: float = 0.0

    # Profitability
    gross_profit: float = 0.0
    gross_margin_pct: float = 0.0
    profit_per_order: float = 0.0

    # Comparison metrics
    effective_commission_pct: float = 0.0  # All-in platform take rate


@dataclass
class DeliveryROIResult:
    """Complete delivery profitability analysis."""

    # Overall summary
    total_delivery_orders: int = 0
    total_delivery_revenue: float = 0.0
    total_delivery_profit: float = 0.0
    overall_delivery_margin_pct: float = 0.0

    # Dine-in comparison
    dine_in_margin_pct: float = 0.0
    delivery_margin_gap_pct: float = 0.0  # How much worse delivery is

    # Per-platform breakdown
    platform_results: list[PlatformROIResult] = field(default_factory=list)

    # Rankings
    most_profitable_platform: str = ""
    least_profitable_platform: str = ""

    # Recommendations
    recommended_price_increase_pct: float = 0.0  # To match dine-in margins
    direct_ordering_savings: float = 0.0  # If all orders were direct

    # Insights
    insights: list[str] = field(default_factory=list)

    # Period
    period_description: str = ""


@dataclass
class DineInComparison:
    """Dine-in metrics for comparison."""

    average_check: float = 25.0
    food_cost_pct: float = 30.0
    labor_cost_pct: float = 28.0  # All labor
    overhead_cost_pct: float = 15.0  # Rent, utilities, etc.

    @property
    def gross_margin_pct(self) -> float:
        """Dine-in gross margin (before overhead)."""
        return 100 - self.food_cost_pct - self.labor_cost_pct

    @property
    def net_margin_pct(self) -> float:
        """Dine-in net margin."""
        return 100 - self.food_cost_pct - self.labor_cost_pct - self.overhead_cost_pct


class DeliveryROIAnalyzer:
    """Analyze profitability of delivery platforms."""

    @classmethod
    def analyze(
        cls,
        platform_data: list[DeliveryOrderData],
        *,
        dine_in_comparison: DineInComparison | None = None,
        period_description: str = "Last 30 days",
    ) -> DeliveryROIResult:
        """
        Analyze delivery profitability across platforms.

        Args:
            platform_data: Order data for each platform.
            dine_in_comparison: Dine-in metrics for comparison.
            period_description: Description of the analysis period.

        Returns:
            DeliveryROIResult with complete analysis.
        """
        if dine_in_comparison is None:
            dine_in_comparison = DineInComparison()

        platform_results: list[PlatformROIResult] = []
        total_orders = 0
        total_revenue = 0.0
        total_profit = 0.0

        for data in platform_data:
            result = cls._analyze_platform(data)
            platform_results.append(result)

            total_orders += result.total_orders
            total_revenue += result.total_gross_revenue  # Customer-paid gross revenue
            total_profit += result.gross_profit

        # Calculate overall margin
        overall_margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
        margin_gap = dine_in_comparison.gross_margin_pct - overall_margin

        # Find best/worst platforms
        sorted_by_profit = sorted(platform_results, key=lambda x: x.profit_per_order, reverse=True)
        best_platform = sorted_by_profit[0].platform_name if sorted_by_profit else ""
        worst_platform = sorted_by_profit[-1].platform_name if sorted_by_profit else ""

        # Calculate recommended price increase to match dine-in
        if overall_margin > 0:
            price_increase_needed = ((dine_in_comparison.gross_margin_pct / overall_margin) - 1) * 100
        else:
            price_increase_needed = 30.0  # Default suggestion

        # Calculate direct ordering savings
        direct_savings = cls._calculate_direct_savings(platform_data, platform_results)

        # Generate insights
        insights = cls._generate_insights(
            platform_results=platform_results,
            overall_margin=overall_margin,
            dine_in_margin=dine_in_comparison.gross_margin_pct,
            margin_gap=margin_gap,
            price_increase_needed=price_increase_needed,
            direct_savings=direct_savings,
        )

        return DeliveryROIResult(
            total_delivery_orders=total_orders,
            total_delivery_revenue=total_revenue,
            total_delivery_profit=total_profit,
            overall_delivery_margin_pct=overall_margin,
            dine_in_margin_pct=dine_in_comparison.gross_margin_pct,
            delivery_margin_gap_pct=margin_gap,
            platform_results=platform_results,
            most_profitable_platform=best_platform,
            least_profitable_platform=worst_platform,
            recommended_price_increase_pct=max(0, price_increase_needed),
            direct_ordering_savings=direct_savings,
            insights=insights,
            period_description=period_description,
        )

    @classmethod
    def quick_analysis(
        cls,
        *,
        # Single platform quick analysis
        platform: DeliveryPlatform = DeliveryPlatform.DOORDASH,
        monthly_orders: int = 500,
        average_order_value: float = 35.0,
        commission_pct: float = 20.0,
        food_cost_pct: float = 32.0,  # Often higher for delivery
        packaging_cost_per_order: float = 1.00,
        # Dine-in comparison
        dine_in_food_cost_pct: float = 30.0,
        dine_in_labor_pct: float = 28.0,
    ) -> DeliveryROIResult:
        """
        Quick delivery ROI analysis with minimal inputs.

        Useful for quick estimates without detailed transaction data.
        """
        platform_data = [
            DeliveryOrderData(
                platform=platform,
                total_orders=monthly_orders,
                total_gross_revenue=monthly_orders * average_order_value,
                food_cost_pct=food_cost_pct,
                packaging_cost_per_order=packaging_cost_per_order,
                commission_pct=commission_pct,
            )
        ]

        dine_in = DineInComparison(
            food_cost_pct=dine_in_food_cost_pct,
            labor_cost_pct=dine_in_labor_pct,
        )

        return cls.analyze(
            platform_data,
            dine_in_comparison=dine_in,
            period_description="Monthly estimate",
        )

    @classmethod
    def _analyze_platform(cls, data: DeliveryOrderData) -> PlatformROIResult:
        """Analyze a single platform's profitability."""
        # Get default fees if not overridden
        defaults = DEFAULT_PLATFORM_FEES.get(data.platform, DEFAULT_PLATFORM_FEES[DeliveryPlatform.DIRECT])

        commission_pct = data.commission_pct or defaults.commission_pct
        per_order_fee = data.per_order_fee or defaults.per_order_fee
        processing_pct = data.payment_processing_pct or defaults.payment_processing_pct

        # Calculate fees
        commission = data.total_gross_revenue * (commission_pct / 100)
        order_fees = data.total_orders * per_order_fee
        processing = data.total_gross_revenue * (processing_pct / 100)
        total_platform_fees = commission + order_fees + processing + data.marketing_spend

        net_revenue = data.total_gross_revenue - total_platform_fees

        # Calculate costs
        food_cost = data.total_gross_revenue * (data.food_cost_pct / 100)
        packaging = data.total_orders * data.packaging_cost_per_order
        labor = data.total_orders * data.labor_cost_per_order
        refunds = data.total_refunds + data.total_adjustments
        total_costs = food_cost + packaging + labor + refunds

        # Profitability
        gross_profit = net_revenue - total_costs
        aov = data.total_gross_revenue / data.total_orders if data.total_orders > 0 else 0
        profit_per_order = gross_profit / data.total_orders if data.total_orders > 0 else 0
        gross_margin = (gross_profit / data.total_gross_revenue * 100) if data.total_gross_revenue > 0 else 0

        # Effective take rate (all-in %)
        effective_commission = (
            (total_platform_fees / data.total_gross_revenue * 100) if data.total_gross_revenue > 0 else 0
        )

        return PlatformROIResult(
            platform=data.platform,
            platform_name=data.platform.value.replace("_", " ").title(),
            total_orders=data.total_orders,
            total_gross_revenue=data.total_gross_revenue,
            average_order_value=aov,
            commission_paid=commission,
            per_order_fees_paid=order_fees,
            payment_processing_paid=processing,
            marketing_spent=data.marketing_spend,
            total_platform_fees=total_platform_fees,
            net_revenue=net_revenue,
            food_cost=food_cost,
            packaging_cost=packaging,
            labor_cost=labor,
            refunds_adjustments=refunds,
            total_costs=total_costs,
            gross_profit=gross_profit,
            gross_margin_pct=gross_margin,
            profit_per_order=profit_per_order,
            effective_commission_pct=effective_commission,
        )

    @classmethod
    def _calculate_direct_savings(
        cls,
        platform_data: list[DeliveryOrderData],
        platform_results: list[PlatformROIResult],
    ) -> float:
        """Calculate savings if all orders went through direct ordering."""
        total_platform_fees = sum(r.total_platform_fees for r in platform_results)

        # Direct would only have payment processing (~2.5%)
        total_revenue = sum(d.total_gross_revenue for d in platform_data)
        direct_fees = total_revenue * 0.025

        return max(0, total_platform_fees - direct_fees)

    @classmethod
    def _generate_insights(
        cls,
        platform_results: list[PlatformROIResult],
        overall_margin: float,
        dine_in_margin: float,
        margin_gap: float,
        price_increase_needed: float,
        direct_savings: float,
    ) -> list[str]:
        """Generate actionable insights."""
        insights = []

        # Overall profitability
        if overall_margin > 0:
            insights.append(
                f"💰 DELIVERY MARGIN: {overall_margin:.1f}% gross margin on delivery orders "
                f"vs {dine_in_margin:.1f}% for dine-in ({margin_gap:.1f}% gap)."
            )
        else:
            insights.append(
                "🚨 DELIVERY LOSING MONEY: Delivery orders are unprofitable after all costs. "
                "Consider dropping platforms or raising prices significantly."
            )

        # Platform comparison
        if len(platform_results) > 1:
            sorted_results = sorted(platform_results, key=lambda x: x.profit_per_order, reverse=True)
            best = sorted_results[0]
            worst = sorted_results[-1]

            if best.profit_per_order - worst.profit_per_order > 1:
                insights.append(
                    f"📊 PLATFORM GAP: {best.platform_name} earns ${best.profit_per_order:.2f}/order "
                    f"vs {worst.platform_name} at ${worst.profit_per_order:.2f}. "
                    f"Consider prioritizing {best.platform_name}."
                )

        # High commission alert
        for result in platform_results:
            if result.effective_commission_pct > 25:
                insights.append(
                    f"⚠️ HIGH FEES on {result.platform_name}: {result.effective_commission_pct:.1f}% "
                    f"all-in take rate. Negotiate lower commission or raise menu prices."
                )

        # Price increase recommendation
        if price_increase_needed > 5:
            insights.append(
                f"💡 PRICE SUGGESTION: Increase delivery menu prices by {price_increase_needed:.0f}% "
                "to match dine-in margins. Most platforms allow separate delivery pricing."
            )

        # Direct ordering opportunity
        if direct_savings > 500:
            insights.append(
                f"🎯 DIRECT ORDERING: You could save ${direct_savings:,.0f}/period by shifting "
                "orders to your own website. Consider loyalty incentives for direct orders."
            )

        # Per-order profit alert
        for result in platform_results:
            if 0 < result.profit_per_order < 2:
                insights.append(
                    f"⚠️ THIN MARGIN: {result.platform_name} only nets ${result.profit_per_order:.2f}/order. "
                    "Any refund or error wipes out profit."
                )
            elif result.profit_per_order <= 0:
                insights.append(
                    f"🚨 LOSING MONEY: {result.platform_name} loses ${abs(result.profit_per_order):.2f}/order! "
                    "Reconsider participation or raise prices immediately."
                )

        return insights


def analyze_delivery_roi(
    platform_data: list[DeliveryOrderData],
    **kwargs: Any,
) -> DeliveryROIResult:
    """Convenience function for delivery ROI analysis.

    See DeliveryROIAnalyzer.analyze() for full parameter documentation.
    """
    return DeliveryROIAnalyzer.analyze(platform_data, **kwargs)


def quick_delivery_analysis(**kwargs: Any) -> DeliveryROIResult:
    """Convenience function for quick delivery analysis.

    See DeliveryROIAnalyzer.quick_analysis() for full parameter documentation.
    """
    return DeliveryROIAnalyzer.quick_analysis(**kwargs)
