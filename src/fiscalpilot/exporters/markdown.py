"""
Markdown report exporter.

Generates a beautiful Markdown report from an AuditReport,
suitable for GitHub, Notion, or any Markdown viewer.
"""

from __future__ import annotations

from fiscalpilot.models.actions import ApprovalLevel
from fiscalpilot.models.report import AuditReport, Severity


def render_markdown(report: AuditReport) -> str:
    """Render an AuditReport as Markdown."""
    lines: list[str] = []

    # Header
    lines.append(f"# 🛫 FiscalPilot Audit Report — {report.company_name}")
    lines.append("")
    lines.append(f"*Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M UTC')}*")
    if report.period_start and report.period_end:
        lines.append(f"*Period: {report.period_start} to {report.period_end}*")
    lines.append("")

    # Executive Summary
    summary = report.executive_summary
    lines.append("## 📊 Executive Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| **Total Findings** | {summary.total_findings} |")
    lines.append(f"| **Critical Issues** | {summary.critical_findings} |")
    lines.append(f"| **Potential Savings** | ${summary.total_potential_savings:,.2f} |")
    lines.append(f"| **Financial Health Score** | {summary.health_score}/100 |")
    lines.append("")

    if summary.narrative:
        lines.append(summary.narrative)
        lines.append("")

    # Findings by severity
    severity_emoji = {
        Severity.CRITICAL: "🔴",
        Severity.HIGH: "🟠",
        Severity.MEDIUM: "🟡",
        Severity.LOW: "🟢",
        Severity.INFO: "ℹ️",
    }

    lines.append("## 🔍 Findings")
    lines.append("")

    for severity in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]:
        findings = [f for f in report.findings if f.severity == severity]
        if not findings:
            continue

        emoji = severity_emoji[severity]
        lines.append(f"### {emoji} {severity.value.title()} ({len(findings)})")
        lines.append("")

        for finding in findings:
            lines.append(f"#### {finding.title}")
            lines.append("")
            lines.append(f"**Category:** {finding.category.value} | **Confidence:** {finding.confidence:.0%} | **Potential Savings:** ${finding.potential_savings:,.2f}")
            lines.append("")
            lines.append(finding.description)
            lines.append("")

            if finding.evidence:
                lines.append("**Evidence:**")
                for ev in finding.evidence:
                    lines.append(f"- {ev}")
                lines.append("")

            if finding.recommendation:
                lines.append(f"**Recommendation:** {finding.recommendation}")
                lines.append("")

            lines.append("---")
            lines.append("")

    # Action Items
    if report.action_items:
        lines.append("## ✅ Action Items")
        lines.append("")
        lines.append("| # | Action | Priority | Est. Savings | Effort |")
        lines.append("|---|--------|----------|-------------|--------|")
        for i, item in enumerate(report.action_items, 1):
            lines.append(
                f"| {i} | {item.title} | {item.priority.value} | "
                f"${item.estimated_savings:,.2f} | {item.effort} |"
            )
        lines.append("")

    # Proposed Actions (v0.4 Execution Pipeline)
    if report.proposed_actions:
        lines.append("## ⚡ Proposed Actions")
        lines.append("")
        lines.append(
            "These are executable actions that FiscalPilot can take on your behalf. "
            "Each action has an approval level indicating how much human oversight is required."
        )
        lines.append("")

        level_emoji = {
            ApprovalLevel.GREEN: "🟢",
            ApprovalLevel.YELLOW: "🟡",
            ApprovalLevel.RED: "🔴",
            ApprovalLevel.CRITICAL: "⛔",
        }

        lines.append("| # | Action | Approval | Est. Savings | Status |")
        lines.append("|---|--------|----------|-------------|--------|")
        for i, action in enumerate(report.proposed_actions, 1):
            emoji = level_emoji.get(action.approval_level, "⚪")
            lines.append(
                f"| {i} | {action.title} | {emoji} {action.approval_level.value.upper()} | "
                f"${action.estimated_savings:,.2f} | {action.status.value} |"
            )
        lines.append("")

        # Detail section for non-green actions
        notable = [a for a in report.proposed_actions if a.approval_level != ApprovalLevel.GREEN]
        if notable:
            lines.append("### Action Details")
            lines.append("")
            for action in notable[:10]:
                emoji = level_emoji.get(action.approval_level, "⚪")
                lines.append(f"#### {emoji} {action.title}")
                lines.append("")
                lines.append(action.description)
                lines.append("")
                if action.steps:
                    lines.append("**Steps:**")
                    for step in action.steps:
                        reversible = " *(reversible)*" if step.reversible else ""
                        lines.append(f"{step.order}. {step.description}{reversible}")
                    lines.append("")
                lines.append("---")
                lines.append("")

    # Intelligence Summary (v0.3)
    intel = report.intelligence
    has_intel = (
        intel.benfords_summary
        or intel.anomaly_summary
        or intel.benchmark_summary
        or intel.cashflow_summary
        or intel.tax_summary
    )
    if has_intel:
        lines.append("## 🧠 Intelligence Analysis")
        lines.append("")
        if intel.benfords_summary:
            score_label = f" (conformity: {intel.benfords_conformity_score:.0%})" if intel.benfords_conformity_score is not None else ""
            lines.append(f"### Benford's Law{score_label}")
            lines.append("")
            lines.append(intel.benfords_summary)
            lines.append("")
        if intel.anomaly_summary:
            lines.append(f"### Anomaly Detection ({intel.anomaly_flagged_count} flagged)")
            lines.append("")
            lines.append(intel.anomaly_summary)
            lines.append("")
        if intel.benchmark_summary:
            grade_label = f" — Grade: **{intel.benchmark_grade}**" if intel.benchmark_grade else ""
            lines.append(f"### Industry Benchmarks{grade_label}")
            lines.append("")
            lines.append(intel.benchmark_summary)
            lines.append("")
        if intel.cashflow_summary:
            runway_label = f" ({intel.cashflow_runway_months:.1f} months runway)" if intel.cashflow_runway_months else ""
            lines.append(f"### Cash Flow Forecast{runway_label}")
            lines.append("")
            lines.append(intel.cashflow_summary)
            lines.append("")
        if intel.tax_summary:
            tax_label = f" (${intel.tax_savings_estimate:,.2f} potential)" if intel.tax_savings_estimate else ""
            lines.append(f"### Tax Optimization{tax_label}")
            lines.append("")
            lines.append(intel.tax_summary)
            lines.append("")

    # Footer
    lines.append("---")
    lines.append("*Report generated by [FiscalPilot](https://github.com/meetpandya27/FiscalPilot) — The Open-Source AI CFO*")

    return "\n".join(lines)
