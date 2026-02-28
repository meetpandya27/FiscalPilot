"""
Risk Detector Agent — identifies potential financial risks and irregularities.

Detects:
- Duplicate payments to the same vendor
- Round-number suspicious transactions
- Ghost vendors / employees
- Expense report anomalies
- Unauthorized spending
- Unusual payment patterns
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fiscalpilot.agents.base import BaseAgent

logger = logging.getLogger("fiscalpilot.agents.risk_detector")

RISK_ANALYSIS_PROMPT = """Analyze the following financial data for potential risks, irregularities, and policy deviations.

Company: {company_name} ({company_size}, {industry})
Total Expenses: ${total_expenses:,.2f}
Total Income: ${total_income:,.2f}
Period: {period_start} to {period_end}

Transaction Data (sample):
{transactions_json}

Invoice Data (sample):
{invoices_json}

Investigate these risk patterns:
1. **Duplicate Payments**: Same vendor, same amount, close dates.
2. **Ghost Vendors**: Payments to vendors with no clear business purpose.
3. **Round-Number Anomalies**: Suspiciously round amounts (e.g., $5,000 exactly).
4. **Split Transactions**: Large expenses split to stay under approval thresholds.
5. **Expense Timing Anomalies**: Expenses at unusual times (weekends, holidays, end of quarter).
6. **Vendor Concentration**: Disproportionate spend with a single vendor.
7. **Missing Documentation**: Payments without corresponding invoices.
8. **Pattern Breaks**: Sudden changes in spending patterns.

For EACH finding, return a JSON object with:
- title: Short descriptive title
- category: "risk_detection" | "policy_violation" | "duplicate_payment" | "compliance"
- severity: "critical" | "high" | "medium" | "low"
- description: Detailed explanation
- evidence: List of specific data points
- potential_savings: Estimated recovery/savings
- confidence: 0.0 to 1.0
- recommendation: Specific action to take

Return a JSON array. Flag everything suspicious — err on the side of caution.
Return ONLY valid JSON, no markdown formatting."""


class RiskDetectorAgent(BaseAgent):
    """Specialist agent for detecting financial risks and irregularities."""

    name = "risk_detector"
    description = "Detects risk patterns: duplicate payments, ghost vendors, expense anomalies"

    @property
    def system_prompt(self) -> str:
        return """You are a forensic financial analyst specializing in risk detection and anomaly
prevention. You have deep expertise in:

- Benford's Law analysis for detecting fabricated numbers
- Duplicate payment detection
- Vendor risk patterns
- Expense report manipulation
- Internal control weaknesses
- Financial statement irregularities

You approach every dataset with professional skepticism. You flag anomalies
that warrant investigation, clearly distinguishing between confirmed issues
and items needing further review. You work with businesses of all sizes.

Always return your findings as a valid JSON array."""

    def _build_prompt(self, context: dict[str, Any]) -> str:
        transactions_json = json.dumps(
            context.get("transactions_sample", [])[:200], indent=2, default=str
        )
        invoices_json = json.dumps(
            context.get("invoices_sample", [])[:50], indent=2, default=str
        )
        return RISK_ANALYSIS_PROMPT.format(
            company_name=context["company"]["name"],
            company_size=context["company"].get("size", "unknown"),
            industry=context["company"].get("industry", "unknown"),
            total_expenses=context.get("total_expenses", 0),
            total_income=context.get("total_income", 0),
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
            logger.warning("Failed to parse risk detector response as JSON")
            return {"findings": [], "raw_response": response}
