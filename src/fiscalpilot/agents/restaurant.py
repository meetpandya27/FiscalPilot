"""
Restaurant Agent — specialized AI CFO for food service businesses.

Combines pure-computation KPI analysis with LLM-powered strategic recommendations.
Designed for restaurants, cafes, bars, food trucks, and catering businesses.

Key Features:
- Industry-standard KPI calculations (Food Cost %, Labor Cost %, Prime Cost)
- QuickBooks/POS data integration with 80+ account mappings
- Menu engineering recommendations
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


def create_restaurant_agent(config) -> RestaurantAgent:
    """Factory function to create a RestaurantAgent."""
    return RestaurantAgent(config)