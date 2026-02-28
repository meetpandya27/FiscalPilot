"""
Margin Optimizer Agent — finds opportunities to improve profit margins.

Analyzes:
- Gross margin by product/service line
- Pricing optimization opportunities
- Cost of goods sold (COGS) reduction
- Revenue mix optimization
- Contribution margin analysis
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fiscalpilot.agents.base import BaseAgent

logger = logging.getLogger("fiscalpilot.agents.margin")

MARGIN_ANALYSIS_PROMPT = """Analyze the following financial data to find margin improvement opportunities.

Company: {company_name} ({company_size}, {industry})
Total Revenue: ${total_income:,.2f}
Total Expenses: ${total_expenses:,.2f}
Current Gross Margin: {gross_margin:.1f}%
Period: {period_start} to {period_end}

Transaction Data (sample):
{transactions_json}

Find opportunities to improve margins:
1. **Pricing Gaps**: Products/services priced below market or not reflecting value.
2. **COGS Reduction**: Ways to reduce cost of goods/services sold.
3. **Revenue Mix**: Shift toward higher-margin offerings.
4. **Volume Optimization**: Better economies of scale opportunities.
5. **Margin Erosion**: Categories where margins are declining over time.
6. **Underbilling**: Services delivered but not fully billed.
7. **Discount Leakage**: Excessive or unauthorized discounting.

For EACH finding, return a JSON object with:
- title: Short descriptive title
- category: "margin_improvement" | "revenue_leakage" | "cost_reduction"
- severity: "critical" | "high" | "medium" | "low"
- description: Detailed explanation
- evidence: List of specific data points
- potential_savings: Estimated annual impact in dollars
- confidence: 0.0 to 1.0
- recommendation: Specific action to take

Return a JSON array. Think like a management consultant — find every basis point.
Return ONLY valid JSON, no markdown formatting."""


class MarginOptimizerAgent(BaseAgent):
    """Specialist agent for profit margin optimization."""

    name = "margin_optimizer"
    description = "Identifies margin improvement opportunities: pricing, COGS, revenue mix"

    @property
    def system_prompt(self) -> str:
        return """You are a profit margin optimization expert with deep experience in
management consulting and financial strategy. You specialize in:

- Gross margin analysis and improvement
- Pricing strategy optimization
- Cost of goods sold (COGS) reduction
- Revenue mix optimization
- Contribution margin analysis
- Break-even analysis

You think in basis points and percentages. Every fraction of a percent matters.
You provide specific, quantified recommendations that any business — from a
restaurant to a billion-dollar enterprise — can act on immediately.

Always return your findings as a valid JSON array."""

    def _build_prompt(self, context: dict[str, Any]) -> str:
        total_income = context.get("total_income", 0)
        total_expenses = context.get("total_expenses", 0)
        gross_margin = ((total_income - total_expenses) / max(total_income, 1)) * 100

        transactions_json = json.dumps(
            context.get("transactions_sample", [])[:200], indent=2, default=str
        )
        return MARGIN_ANALYSIS_PROMPT.format(
            company_name=context["company"]["name"],
            company_size=context["company"].get("size", "unknown"),
            industry=context["company"].get("industry", "unknown"),
            total_income=total_income,
            total_expenses=total_expenses,
            gross_margin=gross_margin,
            period_start=context.get("period_start", "N/A"),
            period_end=context.get("period_end", "N/A"),
            transactions_json=transactions_json,
        )

    def _parse_response(self, response: str, context: dict[str, Any]) -> dict[str, Any]:
        try:
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            findings = json.loads(response)
            if isinstance(findings, dict):
                findings = findings.get("findings", [findings])
            return {"findings": findings}
        except json.JSONDecodeError:
            logger.warning("Failed to parse margin optimizer response as JSON")
            return {"findings": [], "raw_response": response}
