"""
Vendor Auditor Agent — audits vendor relationships and spending.

Analyzes:
- Vendor consolidation opportunities
- Contract terms optimization
- Vendor performance vs. cost
- Vendor concentration risk
- Alternative vendor opportunities
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fiscalpilot.agents.base import BaseAgent

logger = logging.getLogger("fiscalpilot.agents.vendor")

VENDOR_ANALYSIS_PROMPT = """Analyze the following financial data to audit vendor relationships and spending.

Company: {company_name} ({company_size}, {industry})
Total Expenses: ${total_expenses:,.2f}
Period: {period_start} to {period_end}

Transaction Data (sample):
{transactions_json}

Perform a thorough vendor audit:
1. **Vendor Consolidation**: Multiple vendors that could be consolidated.
2. **Contract Renegotiation**: Vendors where better terms should be available.
3. **Vendor Duplication**: Same service from multiple providers.
4. **Vendor Lock-in Risk**: Critical single-source dependencies.
5. **Payment Terms**: Opportunities for early payment discounts or better net terms.
6. **Vendor Performance**: Poor value vendors (high cost, low perceived value).
7. **Market Rate Comparison**: Vendors charging above market average.

For EACH finding, return a JSON object with:
- title: Short descriptive title
- category: "vendor_overcharge" | "cost_reduction" | "cost_optimization"
- severity: "critical" | "high" | "medium" | "low"
- description: Detailed explanation
- evidence: List of specific data points (vendor names, amounts)
- potential_savings: Estimated annual savings from optimization
- confidence: 0.0 to 1.0
- recommendation: Specific action to take

Return a JSON array. Scrutinize every vendor relationship.
Return ONLY valid JSON, no markdown formatting."""


class VendorAuditorAgent(BaseAgent):
    """Specialist agent for vendor relationship auditing."""

    name = "vendor_auditor"
    description = "Audits vendor spending: consolidation, renegotiation, alternatives"

    @property
    def system_prompt(self) -> str:
        return """You are a procurement and vendor management specialist. You have deep
expertise in:

- Strategic sourcing and procurement
- Vendor negotiation and contract optimization
- Supplier risk management
- Market rate benchmarking
- Vendor consolidation strategies
- Payment terms optimization

You know market rates for most common business services and can identify
when a company is overpaying. You provide specific renegotiation strategies
and alternative vendor suggestions. You work with all business sizes.

Always return your findings as a valid JSON array."""

    def _build_prompt(self, context: dict[str, Any]) -> str:
        transactions_json = json.dumps(
            context.get("transactions_sample", [])[:200], indent=2, default=str
        )
        return VENDOR_ANALYSIS_PROMPT.format(
            company_name=context["company"]["name"],
            company_size=context["company"].get("size", "unknown"),
            industry=context["company"].get("industry", "unknown"),
            total_expenses=context.get("total_expenses", 0),
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
            logger.warning("Failed to parse vendor auditor response as JSON")
            return {"findings": [], "raw_response": response}
