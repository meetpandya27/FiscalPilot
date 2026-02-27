"""
Cost Cutter Agent — finds specific cost reduction opportunities.

Analyzes:
- Vendor renegotiation opportunities
- Contract optimization
- Operational efficiency improvements
- Overhead reduction
- Resource consolidation
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fiscalpilot.agents.base import BaseAgent

logger = logging.getLogger("fiscalpilot.agents.cost")

COST_ANALYSIS_PROMPT = """Analyze the following financial data to find cost reduction opportunities.

Company: {company_name} ({company_size}, {industry})
Total Expenses: ${total_expenses:,.2f}
Total Revenue: ${total_income:,.2f}
Expense Ratio: {expense_ratio:.1f}%
Period: {period_start} to {period_end}

Transaction Data (sample):
{transactions_json}

Find every possible way to cut costs:
1. **Vendor Renegotiation**: Contracts where better terms are likely available.
2. **Consolidation**: Multiple services that could be combined.
3. **Timing Optimization**: Better payment timing for cash flow (early pay discounts).
4. **Overhead Reduction**: Administrative costs that can be streamlined.
5. **Volume Discounts**: Spend that should qualify for better pricing.
6. **Alternative Vendors**: Categories where switching vendors would save money.
7. **Process Automation**: Manual processes that could be automated.
8. **Tax Optimization**: Deductions, credits, or structures being missed.

For EACH finding, return a JSON object with:
- title: Short descriptive title
- category: "cost_reduction" | "tax_opportunity" | "vendor_overcharge"
- severity: "critical" | "high" | "medium" | "low"
- description: Detailed explanation
- evidence: List of specific data points
- potential_savings: Estimated annual savings in dollars
- confidence: 0.0 to 1.0
- recommendation: Specific action to take

Return a JSON array. Be aggressive — find every dollar that can be saved.
Return ONLY valid JSON, no markdown formatting."""


class CostCutterAgent(BaseAgent):
    """Specialist agent for cost reduction analysis."""

    name = "cost_cutter"
    description = "Finds cost reduction opportunities: vendor renegotiation, consolidation, tax"

    @property
    def system_prompt(self) -> str:
        return """You are a cost reduction specialist with expertise in procurement, 
vendor management, and operational efficiency. You specialize in:

- Strategic sourcing and vendor negotiation
- Contract optimization
- Operational cost reduction
- Tax optimization strategies
- Process automation ROI analysis
- Overhead reduction

You've helped businesses from local restaurants to global enterprises cut costs.
You provide specific, implementable recommendations with clear dollar savings.
You think about both quick wins and structural improvements.

Always return your findings as a valid JSON array."""

    def _build_prompt(self, context: dict[str, Any]) -> str:
        total_income = context.get("total_income", 0)
        total_expenses = context.get("total_expenses", 0)
        expense_ratio = (total_expenses / max(total_income, 1)) * 100

        transactions_json = json.dumps(
            context.get("transactions_sample", [])[:200], indent=2, default=str
        )
        return COST_ANALYSIS_PROMPT.format(
            company_name=context["company"]["name"],
            company_size=context["company"].get("size", "unknown"),
            industry=context["company"].get("industry", "unknown"),
            total_expenses=total_expenses,
            total_income=total_income,
            expense_ratio=expense_ratio,
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
            logger.warning("Failed to parse cost cutter response as JSON")
            return {"findings": [], "raw_response": response}
