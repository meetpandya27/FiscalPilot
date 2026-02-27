"""Tests for the Markdown exporter."""

from fiscalpilot.exporters.markdown import render_markdown
from fiscalpilot.models.report import (
    AuditReport,
    ExecutiveSummary,
    Finding,
    FindingCategory,
    Severity,
)


class TestMarkdownExporter:
    def test_basic_render(self) -> None:
        report = AuditReport(
            company_name="Test Corp",
            executive_summary=ExecutiveSummary(
                total_potential_savings=50000,
                total_findings=3,
                health_score=75,
            ),
        )
        md = render_markdown(report)
        assert "Test Corp" in md
        assert "FiscalPilot" in md

    def test_render_with_findings(self) -> None:
        report = AuditReport(
            company_name="Acme",
            findings=[
                Finding(
                    id="f1",
                    title="Duplicate Payment",
                    category=FindingCategory.DUPLICATE_PAYMENT,
                    severity=Severity.CRITICAL,
                    description="Found duplicate payment to vendor X",
                    evidence=["Invoice #123", "Invoice #124"],
                    potential_savings=5000,
                    recommendation="Contact vendor for refund",
                ),
                Finding(
                    id="f2",
                    title="Unused SaaS",
                    category=FindingCategory.UNUSED_SUBSCRIPTION,
                    severity=Severity.MEDIUM,
                    description="Subscription not used in 3 months",
                    potential_savings=1200,
                ),
            ],
            executive_summary=ExecutiveSummary(
                total_potential_savings=6200,
                total_findings=2,
                critical_findings=1,
                health_score=70,
            ),
        )
        md = render_markdown(report)

        assert "Duplicate Payment" in md
        assert "Unused SaaS" in md
        assert "Critical" in md
        assert "5,000" in md
        assert "Invoice #123" in md
