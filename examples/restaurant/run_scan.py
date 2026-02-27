"""
Example: Scan a restaurant's finances.

Run:
    python examples/restaurant/run_scan.py

Or via CLI:
    fp scan --csv examples/restaurant/transactions.csv \
            --company "Joe's Diner" --industry restaurant
"""

import asyncio

from fiscalpilot import FiscalPilot
from fiscalpilot.config import ConnectorConfig, FiscalPilotConfig
from fiscalpilot.models.company import CompanyProfile, CompanySize, Industry


async def main() -> None:
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

    # Run the audit
    pilot = FiscalPilot(config=config)
    pilot._setup()

    print("🛫 Running FiscalPilot audit for Joe's Diner...")
    report = await pilot.audit(company)

    # Display results
    print(f"\n📊 Audit Complete!")
    print(f"   Findings: {len(report.findings)}")
    print(f"   Potential Savings: ${report.total_potential_savings:,.2f}")
    print(f"   Health Score: {report.executive_summary.health_score}/100")

    # Save report
    from pathlib import Path

    Path("fiscalpilot_reports").mkdir(exist_ok=True)
    Path("fiscalpilot_reports/joes_diner.md").write_text(report.to_markdown())
    print(f"\n✅ Report saved to fiscalpilot_reports/joes_diner.md")


if __name__ == "__main__":
    asyncio.run(main())
