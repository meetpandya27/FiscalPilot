"""
Example: Scan a restaurant's finances.

Run (local mode — no API key required):
    python examples/restaurant/run_scan.py

Run (with LLM — requires OPENAI_API_KEY):
    python examples/restaurant/run_scan.py --llm

Or via CLI:
    fp scan --csv examples/restaurant/transactions.csv \
            --company "Joe's Diner" --industry restaurant
"""

import asyncio
import os
import sys

from fiscalpilot import FiscalPilot
from fiscalpilot.config import ConnectorConfig, FiscalPilotConfig
from fiscalpilot.models.company import CompanyProfile, CompanySize, Industry


async def main() -> None:
    use_llm = "--llm" in sys.argv

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
                options={"file_path": "examples/restaurant/transactions.csv"},
            )
        ]
    )

    pilot = FiscalPilot(config=config)
    pilot._setup()

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
    from pathlib import Path

    Path("fiscalpilot_reports").mkdir(exist_ok=True)
    Path("fiscalpilot_reports/joes_diner.md").write_text(report.to_markdown())
    print(f"\nReport saved to fiscalpilot_reports/joes_diner.md")


if __name__ == "__main__":
    asyncio.run(main())
