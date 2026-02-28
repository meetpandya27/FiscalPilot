"""
Board Report Templates — executive-level reporting.

Provides:
- Board deck generation
- Executive summaries
- KPI dashboards for leadership
- Variance analysis reports
- Financial highlights
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum


class ReportSection(str, Enum):
    """Sections available for board reports."""
    
    EXECUTIVE_SUMMARY = "executive_summary"
    FINANCIAL_HIGHLIGHTS = "financial_highlights"
    REVENUE_ANALYSIS = "revenue_analysis"
    EXPENSE_ANALYSIS = "expense_analysis"
    CASH_FLOW = "cash_flow"
    BALANCE_SHEET = "balance_sheet"
    KPI_DASHBOARD = "kpi_dashboard"
    BUDGET_VARIANCE = "budget_variance"
    FORECAST = "forecast"
    RISKS_OPPORTUNITIES = "risks_opportunities"
    STRATEGIC_INITIATIVES = "strategic_initiatives"
    APPENDIX = "appendix"


class TrendIndicator(str, Enum):
    """Trend indicators for metrics."""
    
    UP = "up"
    DOWN = "down"
    FLAT = "flat"
    UP_GOOD = "up_good"  # Up trend is positive
    DOWN_GOOD = "down_good"  # Down trend is positive
    UP_BAD = "up_bad"  # Up trend is negative
    DOWN_BAD = "down_bad"  # Down trend is negative


@dataclass
class HighlightMetric:
    """A highlighted metric for executive view."""
    
    label: str
    value: str  # Formatted value
    raw_value: Decimal | None = None
    
    # Comparison
    prior_value: str | None = None
    change_value: str | None = None
    change_pct: float | None = None
    
    trend: TrendIndicator | None = None
    
    # Context
    target: str | None = None
    target_pct: float | None = None  # Progress toward target
    
    commentary: str | None = None


@dataclass
class VarianceItem:
    """A budget variance line item."""
    
    category: str
    actual: Decimal
    budget: Decimal
    variance: Decimal
    variance_pct: float
    
    is_favorable: bool
    explanation: str | None = None


@dataclass
class RiskItem:
    """A risk or opportunity item."""
    
    title: str
    description: str
    impact: str  # High, Medium, Low
    likelihood: str  # High, Medium, Low
    
    category: str  # Financial, Operational, Market, etc.
    mitigation: str | None = None
    owner: str | None = None
    status: str = "Open"


@dataclass
class InitiativeItem:
    """A strategic initiative update."""
    
    title: str
    description: str
    status: str  # On Track, At Risk, Behind, Complete
    
    progress_pct: float
    budget_used: Decimal | None = None
    budget_total: Decimal | None = None
    
    owner: str | None = None
    target_date: datetime | None = None
    updates: list[str] = field(default_factory=list)


@dataclass
class BoardReportSection:
    """A section in a board report."""
    
    section_type: ReportSection
    title: str
    
    content_html: str | None = None
    content_markdown: str | None = None
    
    # Structured content
    metrics: list[HighlightMetric] = field(default_factory=list)
    variances: list[VarianceItem] = field(default_factory=list)
    risks: list[RiskItem] = field(default_factory=list)
    initiatives: list[InitiativeItem] = field(default_factory=list)
    
    # Charts/visuals
    charts: list[dict] = field(default_factory=list)  # Chart configs


@dataclass
class BoardReport:
    """A complete board report."""
    
    id: str
    title: str
    period_description: str  # e.g., "Q4 2024" or "December 2024"
    
    period_start: datetime
    period_end: datetime
    
    # Sections
    sections: list[BoardReportSection] = field(default_factory=list)
    
    # Metadata
    generated_at: datetime = field(default_factory=datetime.now)
    generated_by: str | None = None
    version: int = 1
    
    # Status
    is_draft: bool = True
    approved_by: str | None = None
    approved_at: datetime | None = None


@dataclass
class ReportTemplate:
    """A board report template."""
    
    id: str
    name: str
    description: str | None = None
    
    # Sections to include
    sections: list[ReportSection] = field(default_factory=list)
    
    # Styling
    logo_url: str | None = None
    color_scheme: str = "default"
    
    # Default settings
    include_prior_period: bool = True
    include_budget_comparison: bool = True
    include_forecast: bool = True


class BoardReportGenerator:
    """Generate executive-level board reports.

    Usage::

        generator = BoardReportGenerator()
        
        # Set company info
        generator.set_company_info(
            name="ACME Corp",
            logo_url="https://example.com/logo.png",
        )
        
        # Provide financial data
        generator.set_financial_data(
            revenue=Decimal("1500000"),
            expenses=Decimal("1200000"),
            ...
        )
        
        # Generate report
        report = generator.generate_report(
            template_id="monthly_board",
            period_start=datetime(2024, 1, 1),
            period_end=datetime(2024, 1, 31),
        )
    """

    def __init__(self) -> None:
        self.templates: dict[str, ReportTemplate] = {}
        self.reports: dict[str, BoardReport] = {}
        
        # Company info
        self.company_name: str = ""
        self.company_logo: str | None = None
        
        # Financial data
        self._revenue: Decimal = Decimal("0")
        self._prior_revenue: Decimal = Decimal("0")
        self._expenses: Decimal = Decimal("0")
        self._prior_expenses: Decimal = Decimal("0")
        self._cash: Decimal = Decimal("0")
        self._receivables: Decimal = Decimal("0")
        self._payables: Decimal = Decimal("0")
        
        # Budget data
        self._budget_revenue: Decimal = Decimal("0")
        self._budget_expenses: Decimal = Decimal("0")
        
        # KPIs
        self._kpis: dict[str, tuple[Decimal, Decimal | None]] = {}  # name -> (value, target)
        
        # Risks and initiatives
        self._risks: list[RiskItem] = []
        self._initiatives: list[InitiativeItem] = []
        
        # Report counter
        self._report_counter = 0
        
        # Set up default templates
        self._setup_default_templates()

    def _setup_default_templates(self) -> None:
        """Create default report templates."""
        # Monthly board report
        self.templates["monthly_board"] = ReportTemplate(
            id="monthly_board",
            name="Monthly Board Report",
            description="Standard monthly report for board of directors",
            sections=[
                ReportSection.EXECUTIVE_SUMMARY,
                ReportSection.FINANCIAL_HIGHLIGHTS,
                ReportSection.REVENUE_ANALYSIS,
                ReportSection.EXPENSE_ANALYSIS,
                ReportSection.CASH_FLOW,
                ReportSection.KPI_DASHBOARD,
                ReportSection.BUDGET_VARIANCE,
                ReportSection.RISKS_OPPORTUNITIES,
            ],
        )
        
        # Quarterly report
        self.templates["quarterly_board"] = ReportTemplate(
            id="quarterly_board",
            name="Quarterly Board Report",
            description="Comprehensive quarterly review",
            sections=[
                ReportSection.EXECUTIVE_SUMMARY,
                ReportSection.FINANCIAL_HIGHLIGHTS,
                ReportSection.REVENUE_ANALYSIS,
                ReportSection.EXPENSE_ANALYSIS,
                ReportSection.BALANCE_SHEET,
                ReportSection.CASH_FLOW,
                ReportSection.KPI_DASHBOARD,
                ReportSection.BUDGET_VARIANCE,
                ReportSection.FORECAST,
                ReportSection.STRATEGIC_INITIATIVES,
                ReportSection.RISKS_OPPORTUNITIES,
                ReportSection.APPENDIX,
            ],
        )
        
        # Executive summary only
        self.templates["executive_brief"] = ReportTemplate(
            id="executive_brief",
            name="Executive Brief",
            description="One-page executive summary",
            sections=[
                ReportSection.EXECUTIVE_SUMMARY,
                ReportSection.FINANCIAL_HIGHLIGHTS,
                ReportSection.KPI_DASHBOARD,
            ],
        )

    def set_company_info(
        self,
        name: str,
        logo_url: str | None = None,
    ) -> None:
        """Set company information."""
        self.company_name = name
        self.company_logo = logo_url

    def set_financial_data(
        self,
        revenue: Decimal,
        expenses: Decimal,
        prior_revenue: Decimal | None = None,
        prior_expenses: Decimal | None = None,
        cash: Decimal | None = None,
        receivables: Decimal | None = None,
        payables: Decimal | None = None,
        budget_revenue: Decimal | None = None,
        budget_expenses: Decimal | None = None,
    ) -> None:
        """Set financial data for report generation."""
        self._revenue = revenue
        self._expenses = expenses
        self._prior_revenue = prior_revenue or Decimal("0")
        self._prior_expenses = prior_expenses or Decimal("0")
        self._cash = cash or Decimal("0")
        self._receivables = receivables or Decimal("0")
        self._payables = payables or Decimal("0")
        self._budget_revenue = budget_revenue or Decimal("0")
        self._budget_expenses = budget_expenses or Decimal("0")

    def set_kpi(
        self,
        name: str,
        value: Decimal,
        target: Decimal | None = None,
    ) -> None:
        """Set a KPI value."""
        self._kpis[name] = (value, target)

    def add_risk(self, risk: RiskItem) -> None:
        """Add a risk item."""
        self._risks.append(risk)

    def add_initiative(self, initiative: InitiativeItem) -> None:
        """Add a strategic initiative."""
        self._initiatives.append(initiative)

    def add_template(self, template: ReportTemplate) -> None:
        """Add a custom template."""
        self.templates[template.id] = template

    def _format_currency(self, amount: Decimal) -> str:
        """Format amount as currency."""
        if abs(amount) >= 1000000:
            return f"${amount / 1000000:,.1f}M"
        elif abs(amount) >= 1000:
            return f"${amount / 1000:,.0f}K"
        else:
            return f"${amount:,.2f}"

    def _calculate_change(
        self,
        current: Decimal,
        prior: Decimal,
    ) -> tuple[Decimal, float]:
        """Calculate change amount and percentage."""
        change = current - prior
        pct = float((change / prior * 100)) if prior != 0 else 0.0
        return change, pct

    def _build_executive_summary(
        self,
        period_start: datetime,
        period_end: datetime,
    ) -> BoardReportSection:
        """Build executive summary section."""
        net_income = self._revenue - self._expenses
        prior_net_income = self._prior_revenue - self._prior_expenses
        
        net_change, net_pct = self._calculate_change(net_income, prior_net_income)
        rev_change, rev_pct = self._calculate_change(self._revenue, self._prior_revenue)
        
        # Generate summary text
        period_desc = period_start.strftime("%B %Y")
        
        summary_md = f"""
## Executive Summary

### {period_desc} Financial Overview

**Net Income: {self._format_currency(net_income)}** ({'+' if net_pct >= 0 else ''}{net_pct:.1f}% vs prior period)

- **Revenue:** {self._format_currency(self._revenue)} ({'+' if rev_pct >= 0 else ''}{rev_pct:.1f}%)
- **Expenses:** {self._format_currency(self._expenses)}
- **Cash Position:** {self._format_currency(self._cash)}

### Key Highlights

"""
        
        # Add revenue insight
        if rev_pct >= 10:
            summary_md += "- ✅ Strong revenue growth exceeding targets\n"
        elif rev_pct >= 0:
            summary_md += "- ➡️ Revenue tracking to plan\n"
        else:
            summary_md += "- ⚠️ Revenue below prior period\n"
        
        # Add margin insight
        margin = float((net_income / self._revenue * 100)) if self._revenue > 0 else 0
        summary_md += f"- Profit margin at {margin:.1f}%\n"
        
        # Add cash insight
        if self._cash > 0:
            months_runway = float(self._cash / self._expenses) if self._expenses > 0 else 0
            summary_md += f"- Cash runway: {months_runway:.1f} months\n"
        
        return BoardReportSection(
            section_type=ReportSection.EXECUTIVE_SUMMARY,
            title="Executive Summary",
            content_markdown=summary_md,
        )

    def _build_financial_highlights(
        self,
        period_start: datetime,
        period_end: datetime,
    ) -> BoardReportSection:
        """Build financial highlights section."""
        net_income = self._revenue - self._expenses
        prior_net_income = self._prior_revenue - self._prior_expenses
        
        metrics = []
        
        # Revenue
        rev_change, rev_pct = self._calculate_change(self._revenue, self._prior_revenue)
        metrics.append(HighlightMetric(
            label="Revenue",
            value=self._format_currency(self._revenue),
            raw_value=self._revenue,
            prior_value=self._format_currency(self._prior_revenue),
            change_value=self._format_currency(rev_change),
            change_pct=rev_pct,
            trend=TrendIndicator.UP_GOOD if rev_pct >= 0 else TrendIndicator.DOWN_BAD,
            target=self._format_currency(self._budget_revenue) if self._budget_revenue else None,
        ))
        
        # Expenses
        exp_change, exp_pct = self._calculate_change(self._expenses, self._prior_expenses)
        metrics.append(HighlightMetric(
            label="Expenses",
            value=self._format_currency(self._expenses),
            raw_value=self._expenses,
            prior_value=self._format_currency(self._prior_expenses),
            change_value=self._format_currency(exp_change),
            change_pct=exp_pct,
            trend=TrendIndicator.UP_BAD if exp_pct > 5 else TrendIndicator.FLAT,
            target=self._format_currency(self._budget_expenses) if self._budget_expenses else None,
        ))
        
        # Net Income
        net_change, net_pct = self._calculate_change(net_income, prior_net_income)
        metrics.append(HighlightMetric(
            label="Net Income",
            value=self._format_currency(net_income),
            raw_value=net_income,
            prior_value=self._format_currency(prior_net_income),
            change_value=self._format_currency(net_change),
            change_pct=net_pct,
            trend=TrendIndicator.UP_GOOD if net_pct >= 0 else TrendIndicator.DOWN_BAD,
        ))
        
        # Gross Margin
        if self._revenue > 0:
            margin = float(net_income / self._revenue * 100)
            metrics.append(HighlightMetric(
                label="Profit Margin",
                value=f"{margin:.1f}%",
                raw_value=Decimal(str(margin)),
            ))
        
        # Cash
        metrics.append(HighlightMetric(
            label="Cash",
            value=self._format_currency(self._cash),
            raw_value=self._cash,
        ))
        
        return BoardReportSection(
            section_type=ReportSection.FINANCIAL_HIGHLIGHTS,
            title="Financial Highlights",
            metrics=metrics,
        )

    def _build_kpi_dashboard(self) -> BoardReportSection:
        """Build KPI dashboard section."""
        metrics = []
        
        for name, (value, target) in self._kpis.items():
            target_pct = None
            if target and target > 0:
                target_pct = float(value / target * 100)
            
            # Determine trend
            trend = None
            if target_pct:
                if target_pct >= 100:
                    trend = TrendIndicator.UP_GOOD
                elif target_pct >= 80:
                    trend = TrendIndicator.FLAT
                else:
                    trend = TrendIndicator.DOWN_BAD
            
            metrics.append(HighlightMetric(
                label=name,
                value=f"{value:,.2f}",
                raw_value=value,
                target=f"{target:,.2f}" if target else None,
                target_pct=target_pct,
                trend=trend,
            ))
        
        return BoardReportSection(
            section_type=ReportSection.KPI_DASHBOARD,
            title="KPI Dashboard",
            metrics=metrics,
        )

    def _build_budget_variance(self) -> BoardReportSection:
        """Build budget variance section."""
        variances = []
        
        # Revenue variance
        if self._budget_revenue > 0:
            rev_var = self._revenue - self._budget_revenue
            rev_var_pct = float(rev_var / self._budget_revenue * 100)
            variances.append(VarianceItem(
                category="Revenue",
                actual=self._revenue,
                budget=self._budget_revenue,
                variance=rev_var,
                variance_pct=rev_var_pct,
                is_favorable=rev_var >= 0,
            ))
        
        # Expense variance
        if self._budget_expenses > 0:
            exp_var = self._budget_expenses - self._expenses  # Favorable if under budget
            exp_var_pct = float(exp_var / self._budget_expenses * 100)
            variances.append(VarianceItem(
                category="Total Expenses",
                actual=self._expenses,
                budget=self._budget_expenses,
                variance=exp_var,
                variance_pct=exp_var_pct,
                is_favorable=exp_var >= 0,
            ))
        
        return BoardReportSection(
            section_type=ReportSection.BUDGET_VARIANCE,
            title="Budget Variance Analysis",
            variances=variances,
        )

    def _build_risks_opportunities(self) -> BoardReportSection:
        """Build risks and opportunities section."""
        return BoardReportSection(
            section_type=ReportSection.RISKS_OPPORTUNITIES,
            title="Risks & Opportunities",
            risks=self._risks.copy(),
        )

    def _build_strategic_initiatives(self) -> BoardReportSection:
        """Build strategic initiatives section."""
        return BoardReportSection(
            section_type=ReportSection.STRATEGIC_INITIATIVES,
            title="Strategic Initiatives",
            initiatives=self._initiatives.copy(),
        )

    def generate_report(
        self,
        template_id: str = "monthly_board",
        period_start: datetime | None = None,
        period_end: datetime | None = None,
        title: str | None = None,
        generated_by: str | None = None,
    ) -> BoardReport:
        """Generate a board report.
        
        Args:
            template_id: Template to use.
            period_start: Report period start.
            period_end: Report period end.
            title: Report title.
            generated_by: User generating report.
        
        Returns:
            Generated board report.
        """
        template = self.templates.get(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")
        
        # Default to last month if not specified
        if not period_end:
            period_end = datetime.now().replace(day=1) - timedelta(days=1)
        if not period_start:
            period_start = period_end.replace(day=1)
        
        # Generate period description
        if period_end.month == period_start.month:
            period_desc = period_start.strftime("%B %Y")
        else:
            period_desc = f"{period_start.strftime('%b')} - {period_end.strftime('%b %Y')}"
        
        # Build sections
        sections = []
        
        section_builders = {
            ReportSection.EXECUTIVE_SUMMARY: lambda: self._build_executive_summary(period_start, period_end),
            ReportSection.FINANCIAL_HIGHLIGHTS: lambda: self._build_financial_highlights(period_start, period_end),
            ReportSection.KPI_DASHBOARD: self._build_kpi_dashboard,
            ReportSection.BUDGET_VARIANCE: self._build_budget_variance,
            ReportSection.RISKS_OPPORTUNITIES: self._build_risks_opportunities,
            ReportSection.STRATEGIC_INITIATIVES: self._build_strategic_initiatives,
        }
        
        for section_type in template.sections:
            builder = section_builders.get(section_type)
            if builder:
                sections.append(builder())
            else:
                # Placeholder for unimplemented sections
                sections.append(BoardReportSection(
                    section_type=section_type,
                    title=section_type.value.replace("_", " ").title(),
                ))
        
        self._report_counter += 1
        
        report = BoardReport(
            id=f"board_report_{self._report_counter}",
            title=title or f"{self.company_name} Board Report - {period_desc}",
            period_description=period_desc,
            period_start=period_start,
            period_end=period_end,
            sections=sections,
            generated_by=generated_by,
        )
        
        self.reports[report.id] = report
        return report

    def export_to_markdown(self, report_id: str) -> str:
        """Export report to markdown format."""
        report = self.reports.get(report_id)
        if not report:
            raise ValueError(f"Report not found: {report_id}")
        
        md = f"# {report.title}\n\n"
        md += f"*{report.period_description}*\n\n"
        md += f"Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M')}\n\n"
        md += "---\n\n"
        
        for section in report.sections:
            if section.content_markdown:
                md += section.content_markdown + "\n\n"
            else:
                md += f"## {section.title}\n\n"
                
                # Render metrics
                if section.metrics:
                    md += "| Metric | Value | Change | Trend |\n"
                    md += "|--------|-------|--------|-------|\n"
                    for m in section.metrics:
                        change_str = f"{'+' if (m.change_pct or 0) >= 0 else ''}{m.change_pct:.1f}%" if m.change_pct else "-"
                        trend_emoji = {"up_good": "📈", "down_bad": "📉", "flat": "➡️"}.get(m.trend.value if m.trend else "", "")
                        md += f"| {m.label} | {m.value} | {change_str} | {trend_emoji} |\n"
                    md += "\n"
                
                # Render variances
                if section.variances:
                    md += "| Category | Actual | Budget | Variance | Status |\n"
                    md += "|----------|--------|--------|----------|--------|\n"
                    for v in section.variances:
                        status = "✅" if v.is_favorable else "❌"
                        md += f"| {v.category} | ${v.actual:,.0f} | ${v.budget:,.0f} | {v.variance_pct:+.1f}% | {status} |\n"
                    md += "\n"
                
                # Render risks
                if section.risks:
                    for r in section.risks:
                        md += f"- **{r.title}** ({r.impact} impact / {r.likelihood} likelihood)\n"
                        md += f"  - {r.description}\n"
                    md += "\n"
                
                # Render initiatives
                if section.initiatives:
                    for i in section.initiatives:
                        status_emoji = {"On Track": "🟢", "At Risk": "🟡", "Behind": "🔴", "Complete": "✅"}.get(i.status, "⚪")
                        md += f"- **{i.title}** {status_emoji} ({i.progress_pct:.0f}%)\n"
                        md += f"  - {i.description}\n"
                    md += "\n"
        
        return md
