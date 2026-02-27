"""
FiscalPilot Web App — Simple interface for restaurant owners.

Run locally:
    streamlit run app.py

Or with Docker:
    docker-compose up
"""

import asyncio
import tempfile
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="FiscalPilot — AI CFO for Restaurants",
    page_icon="🍽️",
    layout="wide",
)


def main():
    # Header
    st.markdown("""
    <div style="text-align: center; padding: 2rem 0;">
        <h1>🍽️ FiscalPilot</h1>
        <h3 style="color: #666;">Your AI CFO for Restaurants</h3>
        <p>Upload your financial data and get instant insights. No technical skills required.</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Settings")
        
        restaurant_name = st.text_input(
            "Restaurant Name",
            value="My Restaurant",
            help="Your restaurant's name for the report"
        )
        
        annual_revenue = st.number_input(
            "Annual Revenue ($)",
            min_value=0,
            max_value=100_000_000,
            value=850_000,
            step=10_000,
            help="Approximate annual revenue for KPI analysis"
        )
        
        st.divider()
        
        st.header("📊 Analysis Options")
        
        run_menu_analysis = st.checkbox("Menu Engineering", value=False, help="Analyze which menu items are Stars, Dogs, etc.")
        run_breakeven = st.checkbox("Break-even Analysis", value=True, help="Calculate how many covers you need to break even")
        run_tip_credit = st.checkbox("Tip Tax Credit", value=True, help="Estimate FICA tip credits you may be missing")
        run_delivery_roi = st.checkbox("Delivery ROI", value=False, help="Analyze DoorDash/UberEats profitability")
        
        st.divider()
        
        st.markdown("""
        **Need help?**
        
        📧 [support@fiscalpilot.ai](mailto:support@fiscalpilot.ai)
        
        💬 [Join Discord](https://discord.com/invite/kj3q9S2E5)
        """)
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("📁 Upload Your Data")
        
        uploaded_file = st.file_uploader(
            "Drop your transaction file here",
            type=["csv", "xlsx", "xls"],
            help="Export from QuickBooks, Square, or your POS system"
        )
        
        st.markdown("""
        **Where to get your data:**
        - **QuickBooks**: Reports → Transaction List by Date → Export to Excel
        - **Square**: Transactions → Export CSV
        - **Toast**: Reports → Sales Summary → Download
        - **Any POS**: Look for "Export" or "Download" in your reports
        """)
    
    with col2:
        st.header("📋 Sample Format")
        st.markdown("""
        Your file should have columns like:
        - `date` — Transaction date
        - `amount` — Dollar amount
        - `description` — What was purchased
        - `category` — Expense category
        
        Don't worry if columns are named differently — we'll figure it out!
        """)
    
    st.divider()
    
    # Analysis button
    if uploaded_file is not None:
        if st.button("🚀 Analyze My Restaurant", type="primary", use_container_width=True):
            with st.spinner("Analyzing your financial data..."):
                try:
                    results = run_analysis(
                        uploaded_file,
                        restaurant_name,
                        annual_revenue,
                        run_menu_analysis,
                        run_breakeven,
                        run_tip_credit,
                        run_delivery_roi,
                    )
                    display_results(results)
                except Exception as e:
                    st.error(f"Something went wrong: {str(e)}")
                    st.info("Please check your file format or contact support.")
    else:
        st.info("👆 Upload a file to get started")
    
    # Footer
    st.divider()
    st.markdown("""
    <div style="text-align: center; color: #888; padding: 1rem;">
        <p>FiscalPilot — The Open-Source AI CFO</p>
        <p>Your data stays on your computer. We never see it.</p>
    </div>
    """, unsafe_allow_html=True)


def run_analysis(uploaded_file, restaurant_name, annual_revenue, run_menu, run_breakeven, run_tip, run_delivery):
    """Run the analysis and return results."""
    from fiscalpilot.analyzers.restaurant import RestaurantAnalyzer
    from fiscalpilot.connectors.csv_connector import CSVConnector
    from fiscalpilot.connectors.excel_connector import ExcelConnector
    from fiscalpilot.models.company import CompanyProfile, Industry, CompanySize
    
    # Save uploaded file to temp location
    suffix = Path(uploaded_file.name).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = tmp.name
    
    # Create company profile
    profile = CompanyProfile(
        name=restaurant_name,
        industry=Industry.RESTAURANT,
        size=CompanySize.SMALL,
        annual_revenue=annual_revenue,
    )
    
    # Load data based on file type
    if suffix.lower() == ".csv":
        connector = CSVConnector(credentials={"file_path": tmp_path})
    else:
        connector = ExcelConnector(credentials={"file_path": tmp_path})
    
    dataset = asyncio.run(connector.pull(profile))
    
    # Run KPI analysis
    kpi_result = RestaurantAnalyzer.analyze(dataset, annual_revenue=annual_revenue)
    
    results = {
        "kpi": kpi_result,
        "breakeven": None,
        "tip_credit": None,
        "menu": None,
        "delivery": None,
    }
    
    # Optional analyses
    if run_breakeven and annual_revenue > 0:
        from fiscalpilot.analyzers.breakeven import BreakevenCalculator
        monthly_revenue = annual_revenue / 12
        results["breakeven"] = BreakevenCalculator.calculate(
            rent=monthly_revenue * 0.06,
            management_salaries=monthly_revenue * 0.10,
            insurance=monthly_revenue * 0.015,
            base_utilities=monthly_revenue * 0.025,
            food_cost_pct=32,
            hourly_labor_pct=22,
            average_check=35,
        )
    
    if run_tip:
        from fiscalpilot.analyzers.tip_credit import TipCreditCalculator
        results["tip_credit"] = TipCreditCalculator.quick_estimate(
            num_tipped_employees=8,
            avg_monthly_tips_per_employee=2500,
            avg_hours_per_employee=140,
        )
    
    # Clean up temp file
    Path(tmp_path).unlink(missing_ok=True)
    
    return results


def display_results(results):
    """Display analysis results in a nice format."""
    kpi = results["kpi"]
    
    # Health Grade
    st.header("📊 Your Restaurant Health Report")
    
    grade_colors = {"A": "green", "B": "blue", "C": "orange", "D": "red", "F": "red"}
    grade_color = grade_colors.get(kpi.health_grade, "gray")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Health Grade", kpi.health_grade, help="A=Excellent, F=Critical")
    with col2:
        st.metric("Health Score", f"{kpi.health_score}/100")
    with col3:
        st.metric("Net Operating Income", f"${kpi.net_operating_income:,.0f}")
    
    st.divider()
    
    # KPIs
    st.subheader("📈 Key Performance Indicators")
    
    kpi_data = []
    for k in kpi.kpis:
        status_emoji = {"excellent": "🌟", "healthy": "✅", "warning": "⚠️", "critical": "🚨"}.get(k.severity.value, "")
        kpi_data.append({
            "KPI": k.display_name,
            "Your Value": f"{k.actual:.1f}%",
            "Target Range": f"{k.benchmark_low:.0f}–{k.benchmark_high:.0f}%",
            "Status": f"{status_emoji} {k.severity.value.title()}",
        })
    
    st.table(kpi_data)
    
    # Critical Alerts
    if kpi.critical_alerts:
        st.subheader("🚨 Critical Alerts")
        for alert in kpi.critical_alerts:
            st.error(alert)
    
    # Opportunities
    if kpi.opportunities:
        st.subheader("💡 Opportunities")
        for opp in kpi.opportunities[:5]:
            st.success(opp)
    
    # Break-even
    if results.get("breakeven"):
        st.divider()
        st.subheader("📊 Break-even Analysis")
        be = results["breakeven"]
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Monthly Break-even", f"${be.breakeven_revenue_monthly:,.0f}")
        with col2:
            st.metric("Covers Needed/Month", f"{be.breakeven_covers_monthly:,.0f}")
        with col3:
            st.metric("Daily Covers", f"{be.breakeven_covers_daily:.0f}")
        
        if be.insights:
            for insight in be.insights[:2]:
                st.info(insight)
    
    # Tip Credit
    if results.get("tip_credit"):
        st.divider()
        st.subheader("💰 Estimated Tip Tax Credit")
        tc = results["tip_credit"]
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Monthly Credit", f"${tc['monthly_credit']:,.2f}")
        with col2:
            st.metric("Annual Credit", f"${tc['annual_credit']:,.2f}")
        
        st.info("💡 File IRS Form 8846 to claim this credit. Talk to your accountant!")
    
    # Download report
    st.divider()
    st.subheader("📥 Download Your Report")
    
    report_text = generate_report_text(results)
    st.download_button(
        "Download Full Report (Markdown)",
        report_text,
        file_name="restaurant_analysis.md",
        mime="text/markdown",
    )


def generate_report_text(results):
    """Generate a downloadable report."""
    kpi = results["kpi"]
    lines = [
        f"# Restaurant Analysis Report",
        f"",
        f"**Health Grade:** {kpi.health_grade} ({kpi.health_score}/100)",
        f"",
        f"## Key Performance Indicators",
        f"",
        f"| KPI | Value | Target | Status |",
        f"|-----|-------|--------|--------|",
    ]
    
    for k in kpi.kpis:
        lines.append(f"| {k.display_name} | {k.actual:.1f}% | {k.benchmark_low:.0f}–{k.benchmark_high:.0f}% | {k.severity.value} |")
    
    if kpi.critical_alerts:
        lines.extend(["", "## Critical Alerts", ""])
        for alert in kpi.critical_alerts:
            lines.append(f"- ⚠️ {alert}")
    
    if kpi.opportunities:
        lines.extend(["", "## Opportunities", ""])
        for opp in kpi.opportunities:
            lines.append(f"- 💡 {opp}")
    
    if results.get("breakeven"):
        be = results["breakeven"]
        lines.extend([
            "",
            "## Break-even Analysis",
            "",
            f"- Monthly break-even: ${be.breakeven_revenue_monthly:,.0f}",
            f"- Covers needed: {be.breakeven_covers_monthly:,.0f}/month ({be.breakeven_covers_daily:.0f}/day)",
        ])
    
    if results.get("tip_credit"):
        tc = results["tip_credit"]
        lines.extend([
            "",
            "## Tip Tax Credit",
            "",
            f"- Estimated monthly credit: ${tc['monthly_credit']:,.2f}",
            f"- Estimated annual credit: ${tc['annual_credit']:,.2f}",
            f"- File IRS Form 8846 to claim",
        ])
    
    lines.extend([
        "",
        "---",
        "*Generated by FiscalPilot — The Open-Source AI CFO*",
    ])
    
    return "\n".join(lines)


if __name__ == "__main__":
    main()
