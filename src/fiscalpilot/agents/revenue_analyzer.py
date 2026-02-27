"""
Revenue Analyzer Agent — identifies revenue leakage and growth opportunities.

Analyzes:
- Revenue leakage (unbilled work, missed invoices)
- Revenue trend analysis
- Customer concentration risk
- Pricing optimization
- Upsell/cross-sell opportunities
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fiscalpilot.agents.base import BaseAgent

logger = logging.getLogger("fiscalpilot.agents.revenue")

REVENUE_ANALYSIS_PROMPT = """Analyze the following financial data for revenue leakage and growth opportunities.

Company: {company_name} ({company_size}, {industry})
Total Revenue: ${total_income:,.2f}
Total Expenses: ${total_expenses:,.2f}
Period: {period_start} to {period_end}

Transaction Data (sample):
{transactions_json}

Invoice Data (sample):
{invoices_json}

Investigate these revenue patterns:
1. **Revenue Leakage**: Work delivered but not billed, or underbilled.
2. **Late Payments**: Invoice aging and collection process gaps.
3. **Customer Concentration**: Over-reliance on few revenue sources.
4. **Pricing Inconsistencies**: Same service priced differently for different customers.
5. **Missed Renewals**: Subscriptions/contracts not renewed on time.
6. **Revenue Trend Anomalies**: Unexplained dips or stagnation.
7. **Seasonal Patterns**: Revenue seasonality not being optimized.

For EACH finding, return a JSON object with:
- title: Short descriptive title
- category: "revenue_leakage" | "margin_improvement" | "cash_flow"
- severity: "critical" | "high" | "medium" | "low"
- description: Detailed explanation
- evidence: List of specific data points
- potential_savings: Estimated annual revenue recovery/improvement
- confidence: 0.0 to 1.0
- recommendation: Specific action to take

Return a JSON array. Find every dollar of leaked or missing revenue.
Return ONLY valid JSON, no markdown formatting."""


class RevenueAnalyzerAgent(BaseAgent):
    """Specialist agent for revenue analysis and leakage detection."""

    name = "revenue_analyzer"
    description = "Identifies revenue leakage, growth opportunities, and pricing gaps"

    @property
    def system_prompt(self) -> str:
        return """You are a revenue optimization expert specializing in finding money left 
on the table. You have deep expertise in:

- Revenue leakage detection
- Accounts receivable optimization
- Pricing strategy analysis
- Customer lifetime value optimization
- Revenue forecasting and trend analysis
- Billing process improvement

You leave no dollar uncollected. Every invoice, every contract, every pricing 
decision gets scrutinized. You work with businesses of all sizes and always 
provide specific, actionable recommendations.

Always return your findings as a valid JSON array."""

    def _build_prompt(self, context: dict[str, Any]) -> str:
        transactions_json = json.dumps(
            context.get("transactions_sample", [])[:200], indent=2, default=str
        )
        invoices_json = json.dumps(
            context.get("invoices_sample", [])[:50], indent=2, default=str
        )
        return REVENUE_ANALYSIS_PROMPT.format(
            company_name=context["company"]["name"],
            company_size=context["company"].get("size", "unknown"),
            industry=context["company"].get("industry", "unknown"),
            total_income=context.get("total_income", 0),
            total_expenses=context.get("total_expenses", 0),
            period_start=context.get("period_start", "N/A"),
            period_end=context.get("period_end", "N/A"),
            transactions_json=transactions_json,
            invoices_json=invoices_json,
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
            logger.warning("Failed to parse revenue analyzer response as JSON")
            return {"findings": [], "raw_response": response}
