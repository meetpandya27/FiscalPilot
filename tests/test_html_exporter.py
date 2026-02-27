"""Tests for HTML report exporter."""

from datetime import date, datetime
from uuid import uuid4

import pytest

from fiscalpilot.exporters.html import (
    render_html,
    _escape,
    _severity_color,
    _category_color,
    _health_score_color,
    _render_findings_html,
    _render_action_items_html,
    _render_proposed_actions_html,
)
from fiscalpilot.models.actions import (
    ActionStep,
    ActionType,
    ApprovalLevel,
    ProposedAction,
)
from fiscalpilot.models.report import (
    ActionItem,
    AuditReport,
    ExecutiveSummary,
    Finding,
    FindingCategory,
    Severity,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_finding():
    """Create a sample finding."""
    return Finding(
        id="f1",
        title="High Food Cost Detected",
        category=FindingCategory.COST_OPTIMIZATION,
        severity=Severity.HIGH,
        description="Food cost is 38% of revenue, exceeding the 32% benchmark.",
        evidence=["January food spend: $12,500", "Monthly revenue: $32,000"],
        potential_savings=2400.0,
        confidence=0.92,
        recommendation="Consider renegotiating vendor contracts or reviewing portion sizes.",
    )


@pytest.fixture
def sample_action_item():
    """Create a sample action item."""
    return ActionItem(
        title="Renegotiate Sysco contract",
        description="Contact Sysco to renegotiate pricing terms.",
        priority=Severity.HIGH,
        estimated_savings=1800.0,
        effort="Medium",
    )


@pytest.fixture
def sample_proposed_action():
    """Create a sample proposed action."""
    return ProposedAction(
        id="pa1",
        title="Switch to local produce vendor",
        description="Local vendor offers 15% lower prices with same quality.",
        action_type=ActionType.RENEGOTIATE_VENDOR,
        approval_level=ApprovalLevel.RED,
        estimated_savings=3000.0,
        steps=[
            ActionStep(order=1, description="Contact: Reach out to Farm Fresh Local"),
            ActionStep(order=2, description="Compare: Request quote for top 20 SKUs"),
            ActionStep(order=3, description="Negotiate: Negotiate delivery terms"),
        ],
    )


@pytest.fixture
def sample_report(sample_finding, sample_action_item, sample_proposed_action):
    """Create a complete sample report."""
    return AuditReport(
        id=str(uuid4()),
        company_name="Downtown Bistro",
        generated_at=datetime(2024, 2, 15, 14, 30, 0),
        period_start="2024-01-01",
        period_end="2024-01-31",
        executive_summary=ExecutiveSummary(
            total_findings=5,
            critical_findings=1,
            total_potential_savings=8500.0,
            health_score=72,
            narrative="Overall financial health is moderate with opportunities for cost optimization.",
        ),
        findings=[sample_finding],
        action_items=[sample_action_item],
        proposed_actions=[sample_proposed_action],
    )


@pytest.fixture
def minimal_report():
    """Create a minimal report with no findings."""
    return AuditReport(
        id=str(uuid4()),
        company_name="Empty Corp",
        generated_at=datetime(2024, 2, 15, 14, 30, 0),
        executive_summary=ExecutiveSummary(
            total_findings=0,
            critical_findings=0,
            total_potential_savings=0.0,
            health_score=95,
        ),
        findings=[],
        action_items=[],
    )


# ---------------------------------------------------------------------------
# Helper Function Tests
# ---------------------------------------------------------------------------

class TestHelperFunctions:
    """Test helper functions."""

    def test_escape_html_entities(self):
        """Test HTML escaping."""
        assert _escape("<script>alert('xss')</script>") == "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;"
        assert _escape("Normal text") == "Normal text"
        assert _escape("&") == "&amp;"

    def test_severity_colors(self):
        """Test severity color mapping."""
        assert _severity_color(Severity.CRITICAL) == "#dc2626"
        assert _severity_color(Severity.HIGH) == "#ea580c"
        assert _severity_color(Severity.MEDIUM) == "#ca8a04"
        assert _severity_color(Severity.LOW) == "#16a34a"
        assert _severity_color(Severity.INFO) == "#2563eb"

    def test_category_colors(self):
        """Test category color mapping returns a color."""
        for category in FindingCategory:
            color = _category_color(category)
            assert color.startswith("#")
            assert len(color) == 7

    def test_health_score_colors(self):
        """Test health score color thresholds."""
        assert _health_score_color(95) == "#16a34a"  # green - excellent
        assert _health_score_color(80) == "#16a34a"  # green - good
        assert _health_score_color(70) == "#ca8a04"  # yellow - moderate
        assert _health_score_color(50) == "#ea580c"  # orange - at risk
        assert _health_score_color(30) == "#dc2626"  # red - critical


# ---------------------------------------------------------------------------
# Render HTML Tests
# ---------------------------------------------------------------------------

class TestRenderHtml:
    """Test main HTML rendering function."""

    def test_renders_complete_html_document(self, sample_report):
        """Test that render_html produces a complete HTML document."""
        html = render_html(sample_report)
        
        assert "<!DOCTYPE html>" in html
        assert "<html lang=\"en\">" in html
        assert "</html>" in html
        assert "<head>" in html
        assert "</head>" in html
        assert "<body>" in html
        assert "</body>" in html

    def test_includes_company_name(self, sample_report):
        """Test that company name appears in the report."""
        html = render_html(sample_report)
        assert "Downtown Bistro" in html

    def test_includes_chart_js_cdn(self, sample_report):
        """Test that Chart.js is loaded from CDN."""
        html = render_html(sample_report)
        assert "chart.js" in html
        assert "cdn.jsdelivr.net" in html

    def test_includes_executive_summary_stats(self, sample_report):
        """Test that executive summary stats are displayed."""
        html = render_html(sample_report)
        assert "5" in html  # total findings
        assert "1" in html  # critical findings
        assert "$8,500" in html  # potential savings
        assert "72" in html  # health score

    def test_includes_chart_data_json(self, sample_report):
        """Test that chart data is embedded as JSON."""
        html = render_html(sample_report)
        # Should have severity chart data
        assert "severityChart" in html
        assert "savingsChart" in html

    def test_includes_findings(self, sample_report):
        """Test that findings are rendered."""
        html = render_html(sample_report)
        assert "High Food Cost Detected" in html
        assert "38%" in html

    def test_includes_action_items(self, sample_report):
        """Test that action items table is rendered."""
        html = render_html(sample_report)
        assert "Renegotiate Sysco contract" in html
        assert "$1,800" in html

    def test_includes_proposed_actions(self, sample_report):
        """Test that proposed actions are rendered."""
        html = render_html(sample_report)
        assert "Switch to local produce vendor" in html
        assert "Farm Fresh Local" in html

    def test_escapes_html_in_content(self, sample_report):
        """Test that user content is properly escaped."""
        sample_report.company_name = "<script>alert('xss')</script>"
        html = render_html(sample_report)
        assert "<script>alert" not in html
        assert "&lt;script&gt;" in html

    def test_handles_empty_report(self, minimal_report):
        """Test rendering a report with no findings."""
        html = render_html(minimal_report)
        assert "Empty Corp" in html
        assert "95" in html  # health score
        assert "No findings to display" in html

    def test_responsive_meta_viewport(self, sample_report):
        """Test that responsive viewport meta tag is present."""
        html = render_html(sample_report)
        assert 'name="viewport"' in html
        assert "width=device-width" in html


# ---------------------------------------------------------------------------
# Component Rendering Tests
# ---------------------------------------------------------------------------

class TestRenderFindingsHtml:
    """Test findings HTML rendering."""

    def test_renders_finding_card(self, sample_finding):
        """Test that a finding is rendered as a card."""
        html = _render_findings_html([sample_finding])
        assert "finding-card" in html
        assert "High Food Cost Detected" in html

    def test_renders_severity_badge(self, sample_finding):
        """Test that severity badge is shown."""
        html = _render_findings_html([sample_finding])
        assert "badge-high" in html
        assert "high" in html.lower()

    def test_renders_evidence_list(self, sample_finding):
        """Test that evidence is rendered as a list."""
        html = _render_findings_html([sample_finding])
        assert "January food spend" in html
        assert "Monthly revenue" in html

    def test_renders_recommendation(self, sample_finding):
        """Test that recommendation is rendered."""
        html = _render_findings_html([sample_finding])
        assert "Recommendation" in html
        assert "renegotiating vendor" in html

    def test_renders_savings_amount(self, sample_finding):
        """Test that potential savings are shown."""
        html = _render_findings_html([sample_finding])
        assert "$2,400" in html

    def test_handles_empty_findings(self):
        """Test rendering with no findings."""
        html = _render_findings_html([])
        assert "No findings to display" in html


class TestRenderActionItemsHtml:
    """Test action items HTML rendering."""

    def test_renders_table(self, sample_action_item):
        """Test that action items are rendered as a table."""
        html = _render_action_items_html([sample_action_item])
        assert "<table>" in html
        assert "Renegotiate Sysco contract" in html

    def test_renders_priority_badge(self, sample_action_item):
        """Test that priority badge is shown."""
        html = _render_action_items_html([sample_action_item])
        assert "badge" in html

    def test_handles_empty_action_items(self):
        """Test that empty list returns empty string."""
        html = _render_action_items_html([])
        assert html == ""


class TestRenderProposedActionsHtml:
    """Test proposed actions HTML rendering."""

    def test_renders_action_card(self, sample_proposed_action):
        """Test that proposed action is rendered as a card."""
        html = _render_proposed_actions_html([sample_proposed_action])
        assert "Switch to local produce vendor" in html
        assert "finding-card" in html

    def test_renders_approval_level_badge(self, sample_proposed_action):
        """Test that approval level is shown."""
        html = _render_proposed_actions_html([sample_proposed_action])
        assert "red" in html.lower()

    def test_renders_execution_steps(self, sample_proposed_action):
        """Test that execution steps are listed."""
        html = _render_proposed_actions_html([sample_proposed_action])
        assert "Contact" in html
        assert "Compare" in html
        assert "Negotiate" in html

    def test_renders_impact_amount(self, sample_proposed_action):
        """Test that estimated impact is shown."""
        html = _render_proposed_actions_html([sample_proposed_action])
        assert "$3,000" in html

    def test_handles_empty_proposed_actions(self):
        """Test that empty list returns empty string."""
        html = _render_proposed_actions_html([])
        assert html == ""


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_long_company_name(self, minimal_report):
        """Test handling of very long company name."""
        minimal_report.company_name = "A" * 500
        html = render_html(minimal_report)
        assert "A" * 500 in html

    def test_special_characters_in_description(self, sample_finding):
        """Test handling of special characters."""
        sample_finding.description = "Cost is > 32% & < 50% for \"premium\" items"
        html = _render_findings_html([sample_finding])
        assert "&gt;" in html
        assert "&lt;" in html
        assert "&amp;" in html
        assert "&quot;" in html

    def test_zero_health_score(self, minimal_report):
        """Test rendering with zero health score."""
        minimal_report.executive_summary.health_score = 0
        html = render_html(minimal_report)
        assert ">0<" in html or '"gauge-value">0' in html

    def test_max_health_score(self, minimal_report):
        """Test rendering with maximum health score."""
        minimal_report.executive_summary.health_score = 100
        html = render_html(minimal_report)
        assert "100" in html

    def test_large_savings_amount(self, sample_finding):
        """Test formatting of large savings amounts."""
        sample_finding.potential_savings = 1_500_000.00
        html = _render_findings_html([sample_finding])
        assert "$1,500,000" in html

    def test_all_severity_levels(self):
        """Test that all severity levels render correctly."""
        findings = []
        for severity in Severity:
            findings.append(Finding(
                id=f"f-{severity.value}",
                title=f"Finding with {severity.value} severity",
                category=FindingCategory.COST_OPTIMIZATION,
                severity=severity,
                description="Test description",
                potential_savings=100.0,
            ))
        
        html = _render_findings_html(findings)
        for severity in Severity:
            assert f"badge-{severity.value}" in html

    def test_finding_without_evidence_or_recommendation(self):
        """Test finding with minimal data."""
        finding = Finding(
            id="f-minimal",
            title="Minimal Finding",
            category=FindingCategory.RISK_DETECTION,
            severity=Severity.INFO,
            description="Just a description",
            potential_savings=0.0,
        )
        html = _render_findings_html([finding])
        assert "Minimal Finding" in html
        assert "Recommendation" not in html

    def test_proposed_action_without_steps(self):
        """Test proposed action with no execution steps."""
        action = ProposedAction(
            id="pa-nosteps",
            title="Simple Action",
            description="Simple action description",
            action_type=ActionType.CUSTOM,
            approval_level=ApprovalLevel.GREEN,
            estimated_savings=500.0,
            steps=[],
        )
        html = _render_proposed_actions_html([action])
        assert "Simple Action" in html
        assert "Execution Steps" not in html


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

class TestIntegration:
    """Integration tests for complete report rendering."""

    def test_full_report_is_valid_html(self, sample_report):
        """Test that generated HTML is structurally valid."""
        html = render_html(sample_report)
        
        # Check for balanced tags (using > to avoid partial matches like <header matching <head)
        assert html.count("<html") == html.count("</html>")
        assert html.count("<head>") == html.count("</head>")
        assert html.count("<body>") == html.count("</body>")
        assert html.count("<script") == html.count("</script>")

    def test_charts_have_canvas_elements(self, sample_report):
        """Test that chart canvas elements exist."""
        html = render_html(sample_report)
        assert '<canvas id="severityChart">' in html
        assert '<canvas id="savingsChart">' in html

    def test_css_is_embedded(self, sample_report):
        """Test that CSS styles are embedded."""
        html = render_html(sample_report)
        assert "<style>" in html
        assert "</style>" in html
        assert "--primary:" in html  # CSS variables

    def test_javascript_is_embedded(self, sample_report):
        """Test that JavaScript for charts is embedded."""
        html = render_html(sample_report)
        assert "new Chart(" in html
        assert "severityCtx" in html
        assert "savingsCtx" in html
