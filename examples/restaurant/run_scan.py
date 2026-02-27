"""
Example: Scan a restaurant's finances.

Run (local mode — no API key required):
    python examples/restaurant/run_scan.py

Run (full restaurant KPI analysis):
    python examples/restaurant/run_scan.py --kpi

Run (with LLM — requires OPENAI_API_KEY):
    python examples/restaurant/run_scan.py --llm

Or via CLI:
    fiscalpilot restaurant --csv examples/restaurant/transactions.csv \
            --company "Joe's Diner" --revenue 850000
"""

import asyncio
import os
import sys
from pathlib import Path

# Get the directory where this script lives
SCRIPT_DIR = Path(__file__).parent.resolve()
CSV_PATH = SCRIPT_DIR / "transactions.csv"

from fiscalpilot import FiscalPilot
from fiscalpilot.config import ConnectorConfig, FiscalPilotConfig
from fiscalpilot.models.company import CompanyProfile, CompanySize, Industry


async def main() -> None:
    use_llm = "--llm" in sys.argv
    use_kpi = "--kpi" in sys.argv

    # Define the company
    company = CompanyProfile(
        name="Joe's Diner",
        industry=Industry.RESTAURANT,
        size=CompanySize.SMALL,
        annual_revenue=850_000,
        employee_count=12,
    )

    # Configure with CSV connector
    config = FiscalPilotConfig(
        connectors=[
            ConnectorConfig(
                type="csv",
                options={"file_path": str(CSV_PATH)},
            )
        ]
    )

    pilot = FiscalPilot(config=config)
    pilot._setup()

    if use_kpi:
        # Run restaurant-specific KPI analysis
        print("Running Restaurant KPI Analysis for Joe's Diner...")
        print("=" * 60)
        
        from fiscalpilot.analyzers.restaurant import RestaurantAnalyzer
        from fiscalpilot.connectors.csv_connector import CSVConnector
        
        connector = CSVConnector(credentials={"file_path": str(CSV_PATH)})
        dataset = await connector.pull(company)
        
        result = RestaurantAnalyzer.analyze(dataset, annual_revenue=850_000)
        
        print(f"\n🍽️  Restaurant Financial Health Report")
        print(f"{'=' * 60}")
        print(f"Health Grade: {result.health_grade} ({result.health_score}/100)")
        print(f"\nFinancials:")
        print(f"  Annual Revenue (Est):  ${result.total_revenue:,.2f}")
        print(f"  Total Expenses (Est):  ${result.total_expenses:,.2f}")
        print(f"  Net Operating Income:  ${result.net_operating_income:,.2f}")
        
        print(f"\nKey Performance Indicators:")
        print(f"{'─' * 60}")
        
        for kpi in result.kpis:
            severity_symbols = {
                "critical": "🚨",
                "warning": "⚠️ ",
                "healthy": "✅",
                "excellent": "🌟",
            }
            symbol = severity_symbols.get(kpi.severity.value, "")
            print(f"  {kpi.display_name:25} {kpi.actual:6.1f}%  {symbol} {kpi.severity.value}")
        
        if result.critical_alerts:
            print(f"\n🚨 Critical Alerts:")
            for alert in result.critical_alerts:
                print(f"  {alert}")
        
        if result.opportunities:
            print(f"\n💡 Insights & Opportunities:")
            for opp in result.opportunities[:5]:
                print(f"  {opp}")
        
        # Save detailed report
        Path("fiscalpilot_reports").mkdir(exist_ok=True)
        _save_kpi_report(result, company.name, "fiscalpilot_reports/joes_diner_kpi.md")
        print(f"\n✓ Detailed report saved to fiscalpilot_reports/joes_diner_kpi.md")
        return
    
    if use_llm:
        if not any(os.environ.get(k) for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "FISCALPILOT_API_KEY")):
            print("ERROR: --llm flag requires an API key. Set OPENAI_API_KEY or ANTHROPIC_API_KEY.")
            sys.exit(1)
        print("Running FiscalPilot FULL audit for Joe's Diner (LLM mode)...")
        report = await pilot.audit(company)
    else:
        print("Running FiscalPilot LOCAL audit for Joe's Diner (no LLM required)...")
        report = await pilot.local_audit(company)

    # Display results
    print(f"\nAudit Complete!")
    print(f"   Findings: {len(report.findings)}")
    print(f"   Potential Savings: ${report.total_potential_savings:,.2f}")
    print(f"   Health Score: {report.executive_summary.health_score}/100")

    # Save report
    Path("fiscalpilot_reports").mkdir(exist_ok=True)
    Path("fiscalpilot_reports/joes_diner.md").write_text(report.to_markdown())
    print(f"\nReport saved to fiscalpilot_reports/joes_diner.md")


def _save_kpi_report(result, company_name: str, output: str) -> None:
    """Save detailed restaurant KPI report to markdown."""
    lines = [
        f"# Restaurant KPI Analysis: {company_name}",
        "",
        f"**Analysis Period:** {result.analysis_period}",
        f"**Health Grade:** {result.health_grade} ({result.health_score}/100)",
        "",
        "## Executive Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Annual Revenue (Est) | ${result.total_revenue:,.2f} |",
        f"| Total Expenses (Est) | ${result.total_expenses:,.2f} |",
        f"| Net Operating Income | ${result.net_operating_income:,.2f} |",
        "",
        "## Key Performance Indicators",
        "",
        "| KPI | Actual | Target Range | Status |",
        "|-----|--------|--------------|--------|",
    ]

    for kpi in result.kpis:
        status = kpi.severity.value.upper()
        lines.append(
            f"| {kpi.display_name} | {kpi.actual:.1f}% | "
            f"{kpi.benchmark_low:.0f}-{kpi.benchmark_high:.0f}% | {status} |"
        )

    lines.extend(["", "## Detailed Analysis", ""])
    
    for kpi in result.kpis:
        lines.append(f"### {kpi.display_name}")
        lines.append("")
        lines.append(f"**Actual:** {kpi.actual:.1f}%  ")
        lines.append(f"**Industry Benchmark:** {kpi.benchmark_typical:.1f}% (range: {kpi.benchmark_low:.0f}-{kpi.benchmark_high:.0f}%)")
        lines.append("")
        lines.append(f"{kpi.insight}")
        if kpi.action:
            lines.append(f"  ")
            lines.append(f"**Recommended Action:** {kpi.action}")
        lines.append("")

    if result.critical_alerts:
        lines.extend(["## ⚠️ Critical Alerts", ""])
        for alert in result.critical_alerts:
            lines.append(f"- {alert}")
        lines.append("")

    if result.opportunities:
        lines.extend(["## 💡 Optimization Opportunities", ""])
        for opp in result.opportunities:
            lines.append(f"- {opp}")
        lines.append("")

    lines.extend([
        "---",
        "*Generated by [FiscalPilot](https://github.com/meetpandya27/FiscalPilot) — The Open-Source AI CFO*",
    ])

    Path(output).write_text("\n".join(lines))


if __name__ == "__main__":
    asyncio.run(main())
