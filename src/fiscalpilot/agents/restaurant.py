"""
Restaurant Agent — specialized AI CFO for food service businesses.

Combines pure-computation KPI analysis with LLM-powered strategic recommendations.
Designed for restaurants, cafes, bars, food trucks, and catering businesses.

Key Features:
- Industry-standard KPI calculations (Food Cost %, Labor Cost %, Prime Cost)
- QuickBooks/POS data integration with 80+ account mappings
- Menu engineering recommendations (BCG matrix: Stars/Plowhorses/Puzzles/Dogs)
- Break-even analysis (covers needed to break even)
- Tip tax credit calculator (FICA/45B credit estimation)
- Delivery platform ROI analysis (DoorDash/UberEats profitability)
- Vendor negotiation insights
- Labor optimization suggestions
- Seasonal pattern detection
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from typing import Any

from fiscalpilot.agents.base import BaseAgent
from fiscalpilot.analyzers.restaurant import RestaurantAnalyzer, RestaurantAnalysisResult
from fiscalpilot.analyzers.menu_engineering import (
    MenuEngineeringAnalyzer,
    MenuEngineeringResult,
    MenuItemData,
)
from fiscalpilot.analyzers.breakeven import (
    BreakevenCalculator,
    BreakevenResult,
)
from fiscalpilot.analyzers.tip_credit import (
    TipCreditCalculator,
    TipCreditResult,
    TippedEmployee,
)
from fiscalpilot.analyzers.delivery_roi import (
    DeliveryROIAnalyzer,
    DeliveryROIResult,
    DeliveryOrderData,
    DeliveryPlatform,
)
from fiscalpilot.models.actions import ActionStep, ActionType, ProposedAction, ApprovalLevel
from fiscalpilot.models.financial import FinancialDataset

logger = logging.getLogger("fiscalpilot.agents.restaurant")


RESTAURANT_STRATEGY_PROMPT = """You are an expert restaurant financial consultant analyzing {restaurant_name}.

## Current Financial Performance

**Health Grade: {health_grade} ({health_score}/100)**

Annual Revenue: ${revenue:,.0f}
Total Expenses: ${expenses:,.0f}
Net Operating Income: ${noi:,.0f}

## Key Performance Indicators

{kpi_summary}

## Expense Breakdown

{expense_breakdown}

## Critical Alerts
{critical_alerts}

## Your Task

Based on this data, provide **3-5 specific, actionable recommendations** to improve financial performance.

For each recommendation, include:
1. **title**: Short action title (e.g., "Renegotiate food supplier contracts")
2. **category**: One of: food_cost | labor_cost | occupancy | marketing | operations | revenue
3. **priority**: critical | high | medium | low
4. **description**: Detailed explanation of the issue and opportunity
5. **estimated_savings**: Annual dollar savings (be specific, not just "significant")
6. **implementation_steps**: List of 3-5 concrete steps to implement
7. **timeline**: How long to implement (days/weeks/months)
8. **quick_win**: true/false — can this be done in under 2 weeks?

Focus on:
- **Food cost > 32%**: Portion control, supplier negotiations, menu engineering, waste reduction
- **Labor cost > 32%**: Scheduling optimization, cross-training, peak hour staffing
- **Prime cost > 65%**: Urgent margin protection needed
- **Low marketing**: Customer acquisition opportunities
- **Seasonal patterns**: Prep for slow seasons, capitalize on peaks

Return ONLY valid JSON array. No markdown, no explanations outside JSON."""


class RestaurantAgent(BaseAgent):
    """Specialized agent for restaurant financial analysis and optimization.
    
    Combines:
    1. Pure-computation KPI analysis (no LLM) via RestaurantAnalyzer
    2. LLM-powered strategic recommendations
    3. Industry-specific action proposals
    """
    
    name = "restaurant"
    description = "Restaurant-specialized AI CFO: KPI analysis, menu engineering, labor optimization"
    
    def __init__(self, config):
        super().__init__(config)
        self._last_analysis: RestaurantAnalysisResult | None = None
    
    @property
    def system_prompt(self) -> str:
        return """You are an elite restaurant financial consultant with 20+ years of experience 
turnaround struggling restaurants and optimizing profitable ones. You've worked with:

- Fast casual chains ($5M-$50M revenue)
- Fine dining establishments ($1M-$10M revenue)
- Food trucks and pop-ups ($100K-$500K revenue)
- Multi-location restaurant groups ($50M+ revenue)

Your expertise spans:
- Menu engineering and pricing psychology
- Food cost optimization (portion control, supplier negotiation, waste reduction)
- Labor scheduling and productivity optimization
- Kitchen operations and equipment efficiency
- Marketing ROI for restaurants (especially local marketing)
- Seasonal planning and cash flow management

You always provide SPECIFIC dollar amounts and CONCRETE action steps.
You understand that restaurants operate on thin margins (3-6% net) and every percentage point matters.

Always return your recommendations as a valid JSON array."""
    
    async def analyze(self, context: dict[str, Any]) -> dict[str, Any]:
        """Run complete restaurant analysis: KPIs + strategic recommendations.
        
        Args:
            context: Must include 'dataset' (FinancialDataset) and optionally 'annual_revenue'.
            
        Returns:
            Dict with 'kpi_results', 'findings', 'actions', and 'recommendations'.
        """
        # Step 1: Run pure-computation KPI analysis (no LLM)
        dataset: FinancialDataset = context.get("dataset")
        if not dataset:
            logger.error("No dataset provided to RestaurantAgent")
            return {"findings": [], "error": "Missing financial dataset"}
        
        annual_revenue = context.get("annual_revenue", context.get("company", {}).get("annual_revenue"))
        
        kpi_result = RestaurantAnalyzer.analyze(
            dataset,
            annual_revenue=annual_revenue,
            seat_count=context.get("seat_count"),
            operating_hours_per_week=context.get("operating_hours_per_week"),
        )
        self._last_analysis = kpi_result
        
        # Step 2: Build strategic prompt with KPI data
        prompt = self._build_prompt({
            **context,
            "kpi_result": kpi_result,
        })
        
        # Step 3: Get LLM recommendations
        messages = [{"role": "user", "content": prompt}]
        try:
            raw_response = await self._call_llm(messages)
            recommendations = self._parse_recommendations(raw_response)
        except Exception as e:
            logger.warning("LLM call failed, returning KPI-only results: %s", e)
            recommendations = []
        
        # Step 4: Generate action proposals from KPIs
        actions = self._generate_actions(kpi_result)
        
        # Step 5: Combine KPI findings with LLM recommendations
        findings = self._kpi_to_findings(kpi_result)
        
        return {
            "kpi_results": asdict(kpi_result),
            "health_grade": kpi_result.health_grade,
            "health_score": kpi_result.health_score,
            "findings": findings,
            "recommendations": recommendations,
            "proposed_actions": [a.model_dump() for a in actions],
            "critical_alerts": kpi_result.critical_alerts,
            "opportunities": kpi_result.opportunities,
        }
    
    def _build_prompt(self, context: dict[str, Any]) -> str:
        """Build the strategic analysis prompt."""
        kpi_result: RestaurantAnalysisResult = context["kpi_result"]
        company = context.get("company", {})
        
        # Format KPI summary
        kpi_lines = []
        for kpi in kpi_result.kpis:
            status_icon = {
                "critical": "🚨",
                "warning": "⚠️",
                "healthy": "✅",
                "excellent": "🌟",
            }.get(kpi.severity.value, "")
            kpi_lines.append(
                f"- **{kpi.display_name}**: {kpi.actual:.1f}% "
                f"(target: {kpi.benchmark_low:.0f}-{kpi.benchmark_high:.0f}%) "
                f"{status_icon} {kpi.severity.value}"
            )
        
        # Format expense breakdown
        expense_lines = []
        for cat, amount in sorted(kpi_result.expense_breakdown.items(), key=lambda x: -x[1])[:10]:
            pct = kpi_result.expense_ratios.get(cat, 0)
            expense_lines.append(f"- {cat}: ${amount:,.0f} ({pct:.1f}% of revenue)")
        
        # Format alerts
        alerts = kpi_result.critical_alerts if kpi_result.critical_alerts else ["None — performing within targets"]
        
        return RESTAURANT_STRATEGY_PROMPT.format(
            restaurant_name=company.get("name", "Restaurant"),
            health_grade=kpi_result.health_grade,
            health_score=kpi_result.health_score,
            revenue=kpi_result.total_revenue,
            expenses=kpi_result.total_expenses,
            noi=kpi_result.net_operating_income,
            kpi_summary="\n".join(kpi_lines),
            expense_breakdown="\n".join(expense_lines) or "No expense breakdown available",
            critical_alerts="\n".join(f"- {a}" for a in alerts),
        )
    
    def _parse_response(self, response: str, context: dict[str, Any]) -> dict[str, Any]:
        """Parse LLM response into structured findings.
        
        Note: RestaurantAgent overrides analyze() and uses _parse_recommendations instead.
        This method exists to satisfy the BaseAgent abstract method requirement.
        """
        recommendations = self._parse_recommendations(response)
        return {"recommendations": recommendations}
    
    def _parse_recommendations(self, response: str) -> list[dict[str, Any]]:
        """Parse LLM recommendations from JSON response."""
        try:
            response = response.strip()
            # Handle markdown code blocks
            if "```" in response:
                parts = response.split("```")
                for part in parts:
                    if part.strip().startswith("json"):
                        response = part.strip()[4:]
                        break
                    elif part.strip().startswith("["):
                        response = part.strip()
                        break
            
            recommendations = json.loads(response)
            if isinstance(recommendations, dict):
                recommendations = recommendations.get("recommendations", [recommendations])
            return recommendations
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse restaurant recommendations: %s", e)
            return []
    
    def _kpi_to_findings(self, result: RestaurantAnalysisResult) -> list[dict[str, Any]]:
        """Convert KPI analysis to standard findings format."""
        findings = []
        
        for kpi in result.kpis:
            severity_map = {
                "critical": "critical",
                "warning": "high",
                "healthy": "low",
                "excellent": "info",
            }
            
            finding = {
                "title": f"{kpi.display_name}: {kpi.actual:.1f}%",
                "category": "restaurant_kpi",
                "severity": severity_map.get(kpi.severity.value, "medium"),
                "description": kpi.insight,
                "kpi_name": kpi.name,
                "actual_value": kpi.actual,
                "benchmark": {
                    "low": kpi.benchmark_low,
                    "typical": kpi.benchmark_typical,
                    "high": kpi.benchmark_high,
                },
                "recommendation": kpi.action,
            }
            findings.append(finding)
        
        return findings
    
    def _make_steps(self, descriptions: list[str]) -> list[ActionStep]:
        """Convert step descriptions to ActionStep objects."""
        return [
            ActionStep(order=i + 1, description=desc, reversible=False)
            for i, desc in enumerate(descriptions)
        ]
    
    def _generate_actions(self, result: RestaurantAnalysisResult) -> list[ProposedAction]:
        """Generate action proposals based on KPI analysis."""
        actions = []
        
        for kpi in result.kpis:
            if kpi.severity.value not in ("critical", "warning"):
                continue
            
            if kpi.name == "food_cost_pct" and kpi.actual > 32:
                # Food cost action
                excess_pct = kpi.actual - 30  # vs typical
                potential_savings = result.total_revenue * (excess_pct / 100)
                
                actions.append(ProposedAction(
                    id=f"act_food_cost_{int(kpi.actual)}",
                    title=f"Reduce Food Cost from {kpi.actual:.1f}% to 30%",
                    description=(
                        f"Food cost is {kpi.actual:.1f}%, which is {excess_pct:.1f}% above the "
                        f"industry target of 30%. This represents ${potential_savings:,.0f}/year "
                        f"in potential savings."
                    ),
                    action_type=ActionType.CUSTOM,
                    estimated_savings=potential_savings,
                    confidence=0.85,
                    approval_level=ApprovalLevel.YELLOW,
                    steps=self._make_steps([
                        "Conduct full inventory audit",
                        "Review portion sizes against recipe cards",
                        "Request quotes from 2-3 alternative food suppliers",
                        "Analyze waste logs for top 10 waste items",
                        "Consider menu engineering to promote high-margin items",
                    ]),
                ))
            
            elif kpi.name == "labor_cost_pct" and kpi.actual > 32:
                # Labor cost action
                excess_pct = kpi.actual - 30
                potential_savings = result.total_revenue * (excess_pct / 100)
                
                actions.append(ProposedAction(
                    id=f"act_labor_cost_{int(kpi.actual)}",
                    title=f"Optimize Labor Cost from {kpi.actual:.1f}% to 30%",
                    description=(
                        f"Labor cost at {kpi.actual:.1f}% exceeds target by {excess_pct:.1f}%. "
                        f"Potential savings: ${potential_savings:,.0f}/year through scheduling "
                        f"optimization and productivity improvements."
                    ),
                    action_type=ActionType.CUSTOM,
                    estimated_savings=potential_savings,
                    confidence=0.80,
                    approval_level=ApprovalLevel.RED,  # Labor changes are sensitive
                    steps=self._make_steps([
                        "Analyze hourly sales data vs. staff schedules",
                        "Identify overstaffed shifts (labor % > 40%)",
                        "Cross-train FOH and BOH staff for flexibility",
                        "Implement staggered shift starts based on traffic patterns",
                        "Review overtime patterns and adjust scheduling",
                    ]),
                ))
            
            elif kpi.name == "prime_cost_pct" and kpi.actual > 68:
                # Prime cost critical action
                actions.append(ProposedAction(
                    id=f"act_prime_cost_{int(kpi.actual)}",
                    title=f"URGENT: Prime Cost at {kpi.actual:.1f}% — Margin Crisis",
                    description=(
                        f"Prime cost (food + labor) at {kpi.actual:.1f}% is critically high. "
                        f"Industry target is 55-65%. Immediate action required to protect margins."
                    ),
                    action_type=ActionType.CUSTOM,
                    estimated_savings=result.total_revenue * 0.05,  # Target 5% improvement
                    confidence=0.90,
                    approval_level=ApprovalLevel.RED,
                    steps=self._make_steps([
                        "Emergency review of food and labor costs",
                        "Implement immediate portion control measures",
                        "Freeze non-essential hiring",
                        "Review menu prices — consider 5-10% increase",
                        "Weekly prime cost tracking until below 65%",
                    ]),
                ))
        
        # Add marketing opportunity if spend is low
        marketing_pct = result.expense_ratios.get("marketing", 0)
        if marketing_pct < 1.0:
            actions.append(ProposedAction(
                id="act_marketing_invest",
                title="Invest in Customer Acquisition — Marketing at <1%",
                description=(
                    f"Marketing spend is only {marketing_pct:.1f}% of revenue. "
                    f"Industry recommends 2-4% for growth. Consider local marketing, "
                    f"social media, or loyalty programs."
                ),
                action_type=ActionType.CUSTOM,
                estimated_savings=result.total_revenue * 0.05,  # 5% revenue growth potential
                confidence=0.70,
                approval_level=ApprovalLevel.YELLOW,
                steps=self._make_steps([
                    "Set marketing budget at 2-3% of revenue",
                    "Launch or optimize Google Business Profile",
                    "Implement customer loyalty/rewards program",
                    "Plan 2-3 seasonal promotions",
                    "Track marketing ROI by channel",
                ]),
            ))
        
        return actions
    
    # =========================================================================
    # NEW: Menu Engineering Analysis
    # =========================================================================
    
    def analyze_menu(
        self,
        menu_items: list[dict[str, Any]],
    ) -> MenuEngineeringResult:
        """
        Analyze menu items using BCG matrix (Stars/Plowhorses/Puzzles/Dogs).
        
        Args:
            menu_items: List of dicts with keys:
                - name: str
                - menu_price: float
                - food_cost: float
                - quantity_sold: int
                - category: str (optional)
        
        Returns:
            MenuEngineeringResult with classifications and recommendations.
        
        Example:
            result = agent.analyze_menu([
                {"name": "Burger", "menu_price": 16, "food_cost": 4.50, "quantity_sold": 500},
                {"name": "Lobster", "menu_price": 45, "food_cost": 22, "quantity_sold": 50},
            ])
        """
        items = [
            MenuItemData(
                name=item["name"],
                menu_price=item["menu_price"],
                food_cost=item["food_cost"],
                quantity_sold=item["quantity_sold"],
                category=item.get("category", "Main"),
            )
            for item in menu_items
        ]
        return MenuEngineeringAnalyzer.analyze(items)
    
    # =========================================================================
    # NEW: Break-even Calculator
    # =========================================================================
    
    def calculate_breakeven(
        self,
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
    ) -> BreakevenResult:
        """
        Calculate break-even point: how many covers/revenue needed to cover costs.
        
        Answers the critical question: "How many customers do I need to make money?"
        
        Example:
            result = agent.calculate_breakeven(
                rent=5000,
                management_salaries=8000,
                food_cost_pct=30,
                hourly_labor_pct=22,
                average_check=28,
                current_monthly_revenue=85000,
            )
            print(f"Break-even: {result.breakeven_covers_daily:.0f} covers/day")
        """
        return BreakevenCalculator.calculate(
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
            average_check=average_check,
            days_operating_per_week=days_operating_per_week,
            current_monthly_revenue=current_monthly_revenue,
        )
    
    # =========================================================================
    # NEW: Tip Tax Credit Calculator
    # =========================================================================
    
    def estimate_tip_credit(
        self,
        *,
        # Quick estimate parameters
        num_tipped_employees: int,
        avg_hours_per_employee: float = 30.0,  # Per week
        avg_tips_per_hour: float = 15.0,
        avg_cash_wage: float = 2.13,
        state: str | None = None,
    ) -> TipCreditResult:
        """
        Estimate annual FICA tip credit (Section 45B) — "free money" most owners miss.
        
        The IRS allows restaurants to claim a tax credit for employer FICA taxes
        paid on tips that exceed minimum wage requirements.
        
        Example:
            result = agent.estimate_tip_credit(
                num_tipped_employees=15,
                avg_hours_per_employee=32,
                avg_tips_per_hour=18,
                avg_cash_wage=2.13,
                state="TX",
            )
            print(f"Annual tip credit: ${result.annual_credit_projection:,.0f}")
        """
        return TipCreditCalculator.quick_estimate(
            num_tipped_employees=num_tipped_employees,
            avg_hours_per_employee=avg_hours_per_employee,
            avg_tips_per_hour=avg_tips_per_hour,
            avg_cash_wage=avg_cash_wage,
            state=state,
        )
    
    def calculate_tip_credit_detailed(
        self,
        employees: list[dict[str, Any]],
        *,
        state: str | None = None,
        period_type: str = "month",
    ) -> TipCreditResult:
        """
        Calculate tip credit with detailed employee data.
        
        Args:
            employees: List of dicts with keys:
                - name: str
                - hourly_wage: float (cash wage before tips)
                - hours_worked: float (in period)
                - tips_received: float (in period)
            state: Two-letter state code for state minimum wage.
            period_type: "month", "quarter", or "year"
        
        Returns:
            TipCreditResult with per-employee breakdown.
        """
        tipped_employees = [
            TippedEmployee(
                name=emp.get("name", f"Employee {i+1}"),
                hourly_wage=emp["hourly_wage"],
                hours_worked=emp["hours_worked"],
                tips_received=emp["tips_received"],
            )
            for i, emp in enumerate(employees)
        ]
        return TipCreditCalculator.calculate(
            tipped_employees,
            state=state,
            period_type=period_type,
        )
    
    # =========================================================================
    # NEW: Delivery Platform ROI Analyzer
    # =========================================================================
    
    def analyze_delivery_roi(
        self,
        platform_data: list[dict[str, Any]],
        *,
        dine_in_food_cost_pct: float = 30.0,
        dine_in_labor_pct: float = 28.0,
    ) -> DeliveryROIResult:
        """
        Analyze true profitability of delivery platforms (DoorDash, UberEats, etc.).
        
        Most owners see delivery revenue as "extra" but don't account for:
        - Platform commissions (15-30%)
        - Packaging costs ($0.50-2.00/order)
        - Refunds/adjustments
        - Additional labor
        
        Args:
            platform_data: List of dicts with keys:
                - platform: str ("doordash", "uber_eats", "grubhub", "direct")
                - total_orders: int
                - total_gross_revenue: float
                - food_cost_pct: float (optional, default 30)
                - packaging_cost_per_order: float (optional, default 0.75)
                - commission_pct: float (optional, uses platform default)
                - marketing_spend: float (optional)
                - total_refunds: float (optional)
            dine_in_food_cost_pct: For comparison
            dine_in_labor_pct: For comparison
        
        Example:
            result = agent.analyze_delivery_roi([
                {"platform": "doordash", "total_orders": 800, "total_gross_revenue": 24000, "commission_pct": 20},
                {"platform": "uber_eats", "total_orders": 400, "total_gross_revenue": 14000, "commission_pct": 25},
            ])
            print(f"Most profitable: {result.most_profitable_platform}")
            print(f"Direct ordering would save: ${result.direct_ordering_savings:,.0f}")
        """
        platform_map = {
            "doordash": DeliveryPlatform.DOORDASH,
            "uber_eats": DeliveryPlatform.UBER_EATS,
            "grubhub": DeliveryPlatform.GRUBHUB,
            "postmates": DeliveryPlatform.POSTMATES,
            "caviar": DeliveryPlatform.CAVIAR,
            "direct": DeliveryPlatform.DIRECT,
            "phone": DeliveryPlatform.PHONE,
        }
        
        delivery_data = []
        for data in platform_data:
            platform_str = data.get("platform", "doordash").lower().replace(" ", "_")
            platform = platform_map.get(platform_str, DeliveryPlatform.DOORDASH)
            
            delivery_data.append(DeliveryOrderData(
                platform=platform,
                total_orders=data.get("total_orders", 0),
                total_gross_revenue=data.get("total_gross_revenue", 0),
                food_cost_pct=data.get("food_cost_pct", 32),  # Often higher for delivery
                packaging_cost_per_order=data.get("packaging_cost_per_order", 0.75),
                labor_cost_per_order=data.get("labor_cost_per_order", 0.50),
                commission_pct=data.get("commission_pct"),
                marketing_spend=data.get("marketing_spend", 0),
                total_refunds=data.get("total_refunds", 0),
                total_adjustments=data.get("total_adjustments", 0),
            ))
        
        from fiscalpilot.analyzers.delivery_roi import DineInComparison
        
        dine_in = DineInComparison(
            food_cost_pct=dine_in_food_cost_pct,
            labor_cost_pct=dine_in_labor_pct,
        )
        
        return DeliveryROIAnalyzer.analyze(delivery_data, dine_in_comparison=dine_in)
    
    def quick_delivery_check(
        self,
        *,
        platform: str = "doordash",
        monthly_orders: int = 500,
        average_order_value: float = 35.0,
        commission_pct: float = 20.0,
        food_cost_pct: float = 32.0,
    ) -> DeliveryROIResult:
        """
        Quick delivery ROI check with minimal inputs.
        
        Example:
            result = agent.quick_delivery_check(
                platform="doordash",
                monthly_orders=600,
                average_order_value=32,
                commission_pct=18,
            )
            for insight in result.insights:
                print(insight)
        """
        return DeliveryROIAnalyzer.quick_analysis(
            platform=DeliveryPlatform(platform.lower()),
            monthly_orders=monthly_orders,
            average_order_value=average_order_value,
            commission_pct=commission_pct,
            food_cost_pct=food_cost_pct,
        )


def create_restaurant_agent(config) -> RestaurantAgent:
    """Factory function to create a RestaurantAgent."""
    return RestaurantAgent(config)