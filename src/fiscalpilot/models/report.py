"""
Audit report model — findings, savings, recommendations.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Severity(str, Enum):
    """Finding severity levels."""

    CRITICAL = "critical"  # Fraud, major compliance violation
    HIGH = "high"  # Significant waste (>5% of category spend)
    MEDIUM = "medium"  # Moderate savings opportunity
    LOW = "low"  # Minor optimization
    INFO = "info"  # Informational insight


class FindingCategory(str, Enum):
    """What kind of issue was found."""

    WASTE = "waste"
    FRAUD = "fraud"
    ABUSE = "abuse"
    REVENUE_LEAKAGE = "revenue_leakage"
    MARGIN_IMPROVEMENT = "margin_improvement"
    COST_REDUCTION = "cost_reduction"
    DUPLICATE_PAYMENT = "duplicate_payment"
    VENDOR_OVERCHARGE = "vendor_overcharge"
    UNUSED_SUBSCRIPTION = "unused_subscription"
    TAX_OPPORTUNITY = "tax_opportunity"
    CASH_FLOW = "cash_flow"
    COMPLIANCE = "compliance"
    BENCHMARK_DEVIATION = "benchmark_deviation"


class Finding(BaseModel):
    """A single audit finding.

    Each finding represents a specific issue, opportunity, or risk
    discovered during the financial audit.
    """

    id: str
    title: str
    category: FindingCategory
    severity: Severity
    description: str = Field(description="Detailed explanation of the finding")
    evidence: list[str] = Field(default_factory=list, description="Supporting data points")
    potential_savings: float = Field(default=0.0, ge=0.0, description="Estimated annual savings in base currency")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="Confidence score 0-1")
    recommendation: str = Field(default="", description="Actionable recommendation")
    affected_transactions: list[str] = Field(default_factory=list, description="Transaction IDs")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ActionItem(BaseModel):
    """A concrete action the business should take."""

    title: str
    description: str
    priority: Severity
    estimated_savings: float = 0.0
    effort: str = "medium"  # low, medium, high
    finding_ids: list[str] = Field(default_factory=list)


class ExecutiveSummary(BaseModel):
    """High-level summary for business owners / executives."""

    total_potential_savings: float = 0.0
    total_findings: int = 0
    critical_findings: int = 0
    top_opportunities: list[str] = Field(default_factory=list)
    health_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Financial health score 0-100")
    narrative: str = Field(default="", description="AI-generated executive narrative")


class IntelligenceData(BaseModel):
    """Structured results from v0.3 intelligence engines (non-LLM)."""

    benfords_summary: str = ""
    benfords_conformity_score: float | None = None
    anomaly_summary: str = ""
    anomaly_flagged_count: int = 0
    benchmark_summary: str = ""
    benchmark_grade: str = ""
    benchmark_excess_spend: float = 0.0
    cashflow_summary: str = ""
    cashflow_runway_months: float = 0.0
    tax_summary: str = ""
    tax_savings_estimate: float = 0.0


class AuditReport(BaseModel):
    """Complete audit report — the main output of FiscalPilot.

    Contains all findings, recommendations, and an executive summary.
    Can be exported to PDF, JSON, Markdown, or HTML.
    """

    id: str = Field(default="")
    company_name: str = ""
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    period_start: str | None = None
    period_end: str | None = None
    findings: list[Finding] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    executive_summary: ExecutiveSummary = Field(default_factory=ExecutiveSummary)
    intelligence: IntelligenceData = Field(default_factory=IntelligenceData)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def total_potential_savings(self) -> float:
        """Total potential annual savings across all findings."""
        return sum(f.potential_savings for f in self.findings)

    @property
    def critical_findings(self) -> list[Finding]:
        """Findings with critical severity."""
        return [f for f in self.findings if f.severity == Severity.CRITICAL]

    @property
    def high_priority_findings(self) -> list[Finding]:
        """Findings with critical or high severity."""
        return [f for f in self.findings if f.severity in (Severity.CRITICAL, Severity.HIGH)]

    def to_markdown(self) -> str:
        """Export report as Markdown."""
        from fiscalpilot.exporters.markdown import render_markdown

        return render_markdown(self)

    def to_json(self) -> str:
        """Export report as JSON."""
        return self.model_dump_json(indent=2)

    def to_dict(self) -> dict[str, Any]:
        """Export report as dictionary."""
        return self.model_dump()
