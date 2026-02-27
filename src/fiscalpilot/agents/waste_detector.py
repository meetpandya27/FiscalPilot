"""
Waste Detector Agent — identifies wasteful spending patterns.

Detects:
- Unused subscriptions and SaaS tools
- Redundant services (multiple tools doing the same thing)
- Over-provisioned resources
- Unnecessary recurring charges
- Spending that doesn't correlate with revenue
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fiscalpilot.agents.base import BaseAgent

logger = logging.getLogger("fiscalpilot.agents.waste")

WASTE_ANALYSIS_PROMPT = """Analyze the following financial data and identify ALL instances of waste.

Company: {company_name} ({company_size}, {industry})
Total Expenses: ${total_expenses:,.2f}
Period: {period_start} to {period_end}

Transaction Data (sample):
{transactions_json}

Look for these specific patterns:
1. **Unused Subscriptions**: Recurring charges with no corresponding usage or value.
2. **Duplicate Services**: Multiple vendors providing the same service.
3. **Over-provisioning**: Services/resources sized beyond actual need.
4. **Idle Resources**: Assets or services not generating value.
5. **Unnecessary Recurring Charges**: Legacy contracts, forgotten trials.
6. **Spending-Revenue Disconnect**: Categories growing faster than revenue.

For EACH finding, return a JSON object with:
- title: Short descriptive title
- category: "waste" or "unused_subscription"
- severity: "critical" | "high" | "medium" | "low"
- description: Detailed explanation
- evidence: List of specific data points
- potential_savings: Estimated annual savings in dollars
- confidence: 0.0 to 1.0
- recommendation: Specific action to take

Return a JSON array of findings. Be aggressive — find everything.
Return ONLY valid JSON, no markdown formatting."""


class WasteDetectorAgent(BaseAgent):
    """Specialist agent for detecting wasteful spending."""

    name = "waste_detector"
    description = "Detects wasteful spending: unused subscriptions, duplicates, over-provisioning"

    @property
    def system_prompt(self) -> str:
        return """You are an elite financial waste detection specialist. Your job is to find 
every dollar of wasteful spending in a company's finances. You have deep expertise in:

- SaaS subscription auditing
- Vendor consolidation analysis
- Resource right-sizing
- Recurring charge optimization
- Spending pattern analysis

You are ruthlessly thorough. If there's waste, you find it. You always provide 
specific dollar amounts and actionable recommendations. You serve businesses from 
restaurants to Fortune 500 companies, adapting your analysis to their scale.

Always return your findings as a valid JSON array."""

    def _build_prompt(self, context: dict[str, Any]) -> str:
        transactions_json = json.dumps(context.get("transactions_sample", [])[:200], indent=2, default=str)
        return WASTE_ANALYSIS_PROMPT.format(
            company_name=context["company"]["name"],
            company_size=context["company"].get("size", "unknown"),
            industry=context["company"].get("industry", "unknown"),
            total_expenses=context.get("total_expenses", 0),
            period_start=context.get("period_start", "N/A"),
            period_end=context.get("period_end", "N/A"),
            transactions_json=transactions_json,
        )

    def _parse_response(self, response: str, context: dict[str, Any]) -> dict[str, Any]:
        """Parse LLM response into structured findings."""
        try:
            # Try to extract JSON from the response
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
            logger.warning("Failed to parse waste detector response as JSON")
            return {"findings": [], "raw_response": response}
