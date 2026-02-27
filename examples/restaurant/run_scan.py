"""
Example: Scan a restaurant's finances.

Run (local mode — no API key required):
    python examples/restaurant/run_scan.py

Run (full restaurant KPI analysis):
    python examples/restaurant/run_scan.py --kpi

Run (menu engineering analysis):
    python examples/restaurant/run_scan.py --menu

Run (breakeven calculator):
    python examples/restaurant/run_scan.py --breakeven

Run (tip credit estimation):
    python examples/restaurant/run_scan.py --tips

Run (delivery platform ROI):
    python examples/restaurant/run_scan.py --delivery

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
    use_menu = "--menu" in sys.argv
    use_breakeven = "--breakeven" in sys.argv
    use_tips = "--tips" in sys.argv
    use_delivery = "--delivery" in sys.argv
    
    # Show all demos if no specific flag
    show_all = not any([use_kpi, use_menu, use_breakeven, use_tips, use_delivery, use_llm])

    # Define the company
    company = CompanyProfile(
        name="Joe's Diner",
        industry=Industry.RESTAURANT,
        size=CompanySize.SMALL,
        annual_revenue=850_000,
        employee_count=12,
    )

    # ─────────────────────────────────────────────────────────────
    # Menu Engineering Demo
    # ─────────────────────────────────────────────────────────────
    if use_menu or show_all:
        print("\n" + "=" * 60)
        print("🍽️  MENU ENGINEERING ANALYSIS (BCG Matrix)")
        print("=" * 60)
        
        from fiscalpilot.analyzers.menu_engineering import MenuEngineeringAnalyzer, MenuItemData
        
        # Sample menu items for Joe's Diner
        menu_items = [
            # Entrees
            MenuItemData(name="Classic Burger", category="Entrees", menu_price=14.99, food_cost=4.20, quantity_sold=520),
            MenuItemData(name="Grilled Salmon", category="Entrees", menu_price=24.99, food_cost=10.50, quantity_sold=180),
            MenuItemData(name="Chicken Parmesan", category="Entrees", menu_price=18.99, food_cost=5.80, quantity_sold=310),
            MenuItemData(name="Ribeye Steak", category="Entrees", menu_price=32.99, food_cost=16.00, quantity_sold=95),
            MenuItemData(name="Veggie Wrap", category="Entrees", menu_price=11.99, food_cost=3.50, quantity_sold=85),
            # Appetizers
            MenuItemData(name="Mozzarella Sticks", category="Appetizers", menu_price=9.99, food_cost=2.20, quantity_sold=380),
            MenuItemData(name="Loaded Nachos", category="Appetizers", menu_price=12.99, food_cost=3.80, quantity_sold=290),
            MenuItemData(name="Soup of the Day", category="Appetizers", menu_price=5.99, food_cost=1.20, quantity_sold=420),
            MenuItemData(name="Calamari", category="Appetizers", menu_price=14.99, food_cost=7.50, quantity_sold=45),
            # Desserts
            MenuItemData(name="Chocolate Cake", category="Desserts", menu_price=8.99, food_cost=2.00, quantity_sold=210),
            MenuItemData(name="Cheesecake", category="Desserts", menu_price=9.99, food_cost=2.80, quantity_sold=165),
            MenuItemData(name="Fruit Tart", category="Desserts", menu_price=7.99, food_cost=3.50, quantity_sold=35),
        ]
        
        result = MenuEngineeringAnalyzer.analyze(menu_items)
        
        print(f"\nTotal Menu Items: {result.total_menu_items}")
        print(f"Total Revenue: ${result.total_revenue:,.2f}")
        print(f"Overall Food Cost: {result.overall_food_cost_pct:.1f}%")
        print(f"Avg Contribution Margin: ${result.avg_contribution_margin:.2f}")
        
        print(f"\n📊 BCG Classification:")
        print(f"  ⭐ Stars (high profit, high sales): {result.star_count}")
        for item in result.stars[:3]:
            print(f"     • {item.name}: ${item.contribution_margin:.2f} CM, {item.quantity_sold} sold")
        
        print(f"  🐴 Plowhorses (low profit, high sales): {result.plowhorse_count}")
        for item in result.plowhorses[:3]:
            print(f"     • {item.name}: ${item.contribution_margin:.2f} CM, {item.quantity_sold} sold")
        
        print(f"  🧩 Puzzles (high profit, low sales): {result.puzzle_count}")
        for item in result.puzzles[:3]:
            print(f"     • {item.name}: ${item.contribution_margin:.2f} CM, {item.quantity_sold} sold")
        
        print(f"  🐕 Dogs (low profit, low sales): {result.dog_count}")
        for item in result.dogs[:3]:
            print(f"     • {item.name}: ${item.contribution_margin:.2f} CM, {item.quantity_sold} sold")
        
        if result.potential_profit_increase > 0:
            print(f"\n💰 Potential Profit Increase: ${result.potential_profit_increase:,.2f}")
        
        print(f"\n📝 Recommendations:")
        for rec in result.recommendations[:5]:
            print(f"  • {rec}")

    # ─────────────────────────────────────────────────────────────
    # Break-even Calculator Demo
    # ─────────────────────────────────────────────────────────────
    if use_breakeven or show_all:
        print("\n" + "=" * 60)
        print("📊 BREAK-EVEN ANALYSIS")
        print("=" * 60)
        
        from fiscalpilot.analyzers.breakeven import BreakevenCalculator
        
        # Joe's Diner costs (monthly)
        result = BreakevenCalculator.calculate(
            rent=8500,
            insurance=1200,
            management_salaries=12000,
            loan_payments=2500,
            equipment_leases=800,
            software_subscriptions=500,
            base_utilities=1800,
            food_cost_pct=32,
            hourly_labor_pct=22,
            supplies_pct=2,
            credit_card_fees_pct=2.5,
            average_check=35,
        )
        
        print(f"\n📈 Break-even Point:")
        print(f"  Monthly Revenue Needed: ${result.breakeven_revenue_monthly:,.2f}")
        print(f"  Covers Needed: {result.breakeven_covers_monthly:,.0f}/month")
        print(f"  Daily Covers: {result.breakeven_covers_daily:.0f}")
        
        print(f"\n📊 Cost Structure:")
        print(f"  Fixed Costs: ${result.total_fixed_monthly:,.2f}/month")
        print(f"  Variable Cost %: {result.total_variable_pct:.1f}%")
        print(f"  Contribution Margin: {result.contribution_margin_pct:.1f}%")
        
        if result.scenarios:
            print(f"\n🎯 Scenarios:")
            for scenario in result.scenarios[:4]:
                status = "✅" if scenario.get("is_profitable", False) else "❌"
                print(f"  {status} {scenario.get('name', 'N/A')}: ${scenario.get('revenue', 0):,.0f} → ${scenario.get('profit', 0):+,.0f}")
        
        if result.insights:
            print(f"\n💡 Insights:")
            for insight in result.insights[:3]:
                print(f"  • {insight}")

    # ─────────────────────────────────────────────────────────────
    # Tip Tax Credit Demo
    # ─────────────────────────────────────────────────────────────
    if use_tips or show_all:
        print("\n" + "=" * 60)
        print("💰 FICA TIP TAX CREDIT (Section 45B)")
        print("=" * 60)
        
        from fiscalpilot.analyzers.tip_credit import TipCreditCalculator, TippedEmployee
        
        # Joe's Diner tipped employees (monthly data)
        employees = [
            TippedEmployee(name="Maria (Server)", hours_worked=168, tips_received=3200, cash_wage=2.13),
            TippedEmployee(name="Jake (Server)", hours_worked=152, tips_received=2800, cash_wage=2.13),
            TippedEmployee(name="Sofia (Server)", hours_worked=140, tips_received=2400, cash_wage=2.13),
            TippedEmployee(name="Carlos (Bartender)", hours_worked=160, tips_received=3600, cash_wage=2.13),
            TippedEmployee(name="Amy (Host)", hours_worked=120, tips_received=800, cash_wage=5.00),
        ]
        
        result = TipCreditCalculator.calculate(employees, state="TX")
        
        print(f"\n📊 Tip Credit Summary (Texas):")
        print(f"  Federal Minimum Wage: ${result.federal_minimum_wage:.2f}/hr")
        print(f"  State Tipped Minimum: ${result.state_tipped_minimum:.2f}/hr")
        print(f"  Eligible Employees: {result.eligible_employee_count}")
        
        print(f"\n💵 Credit Calculation:")
        print(f"  Total Tips This Month: ${result.total_tips:,.2f}")
        print(f"  Total Hours: {result.total_hours:,.0f}")
        print(f"  Monthly Credit: ${result.total_credit:,.2f}")
        print(f"  📅 Annual Projection: ${result.annual_projection:,.2f}")
        
        print(f"\n👥 Per-Employee Breakdown:")
        for emp in result.employees[:5]:
            print(f"  • {emp.name}: ${emp.credit_amount:,.2f} credit ({emp.tips_per_hour:.2f}/hr tips)")
        
        print(f"\n📋 Tax Filing Notes:")
        for note in result.compliance_notes[:3]:
            print(f"  • {note}")

    # ─────────────────────────────────────────────────────────────
    # Delivery ROI Demo
    # ─────────────────────────────────────────────────────────────
    if use_delivery or show_all:
        print("\n" + "=" * 60)
        print("🚗 DELIVERY PLATFORM ROI ANALYSIS")
        print("=" * 60)
        
        from fiscalpilot.analyzers.delivery_roi import DeliveryROIAnalyzer, DeliveryOrderData
        
        # Joe's Diner delivery data (monthly)
        orders = [
            DeliveryOrderData(
                platform="doordash",
                gross_revenue=8500,
                food_cost=2720,  # 32%
                order_count=285,
                commission_rate=0.22,
                packaging_cost_per_order=0.85,
            ),
            DeliveryOrderData(
                platform="ubereats",
                gross_revenue=5200,
                food_cost=1664,
                order_count=165,
                commission_rate=0.25,
                packaging_cost_per_order=0.85,
            ),
            DeliveryOrderData(
                platform="grubhub",
                gross_revenue=2800,
                food_cost=896,
                order_count=95,
                commission_rate=0.20,
                packaging_cost_per_order=0.85,
            ),
        ]
        
        result = DeliveryROIAnalyzer.analyze(orders, dine_in_margin=62)
        
        print(f"\n📊 Delivery Overview:")
        print(f"  Total Delivery Revenue: ${result.total_delivery_revenue:,.2f}")
        print(f"  Total Orders: {result.total_orders}")
        print(f"  Avg Order Value: ${result.total_delivery_revenue / result.total_orders:.2f}")
        
        print(f"\n📈 Platform Comparison:")
        print(f"  {'Platform':<12} {'Revenue':<12} {'Margin':<10} {'vs Dine-in':<12}")
        print(f"  {'-'*46}")
        for p in result.platforms:
            gap_str = f"{p.margin_gap:+.1f}%" if p.margin_gap else "N/A"
            print(f"  {p.platform.title():<12} ${p.total_gross_revenue:>8,.0f}   {p.effective_margin:>5.1f}%     {gap_str}")
        
        if result.best_platform:
            print(f"\n🏆 Best Platform: {result.best_platform.title()}")
        if result.worst_platform:
            print(f"⚠️  Least Profitable: {result.worst_platform.title()}")
        
        # Direct ordering savings
        if result.direct_ordering_recommendation:
            print(f"\n🎯 Direct Ordering Opportunity:")
            savings = result.potential_direct_savings_annual or 0
            print(f"  If 30% of orders moved to direct: ~${savings:,.0f}/year saved")
        
        print(f"\n💡 Insights:")
        for insight in result.insights[:4]:
            print(f"  • {insight}")

    # ─────────────────────────────────────────────────────────────
    # KPI Analysis (existing)
    # ─────────────────────────────────────────────────────────────
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

    # ─────────────────────────────────────────────────────────────
    # Full LLM Audit (requires API key)
    # ─────────────────────────────────────────────────────────────
    if use_llm:
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
        
        if not any(os.environ.get(k) for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "FISCALPILOT_API_KEY")):
            print("ERROR: --llm flag requires an API key. Set OPENAI_API_KEY or ANTHROPIC_API_KEY.")
            sys.exit(1)
        print("\n" + "=" * 60)
        print("🤖 FULL LLM AUDIT")
        print("=" * 60)
        print("Running FiscalPilot FULL audit for Joe's Diner (LLM mode)...")
        report = await pilot.audit(company)
        
        # Display results
        print(f"\nAudit Complete!")
        print(f"   Findings: {len(report.findings)}")
        print(f"   Potential Savings: ${report.total_potential_savings:,.2f}")
        print(f"   Health Score: {report.executive_summary.health_score}/100")

        # Save report
        Path("fiscalpilot_reports").mkdir(exist_ok=True)
        Path("fiscalpilot_reports/joes_diner.md").write_text(report.to_markdown())
        print(f"\nReport saved to fiscalpilot_reports/joes_diner.md")
    
    # Summary if showing all demos
    if show_all:
        print("\n" + "=" * 60)
        print("✅ DEMO COMPLETE")
        print("=" * 60)
        print("\nRun with specific flags for focused analysis:")
        print("  --menu       Menu engineering (BCG matrix)")
        print("  --breakeven  Break-even calculator")
        print("  --tips       FICA tip tax credit")
        print("  --delivery   Delivery platform ROI")
        print("  --kpi        Restaurant KPI analysis")
        print("  --llm        Full AI audit (requires API key)")


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
