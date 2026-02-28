"""
HTML report exporter with interactive charts.

Generates a beautiful, responsive HTML report from an AuditReport,
complete with Chart.js visualizations for findings, savings, and health scores.
"""

from __future__ import annotations

import html
import json

from fiscalpilot.models.actions import ApprovalLevel
from fiscalpilot.models.report import AuditReport, FindingCategory, Severity


def _escape(text: str) -> str:
    """HTML-escape a string."""
    return html.escape(str(text))


def _severity_color(severity: Severity) -> str:
    """Get color for severity level."""
    return {
        Severity.CRITICAL: "#dc2626",  # red-600
        Severity.HIGH: "#ea580c",  # orange-600
        Severity.MEDIUM: "#ca8a04",  # yellow-600
        Severity.LOW: "#16a34a",  # green-600
        Severity.INFO: "#2563eb",  # blue-600
    }.get(severity, "#6b7280")


def _category_color(category: FindingCategory) -> str:
    """Get color for finding category."""
    colors = [
        "#3b82f6",  # blue
        "#10b981",  # emerald
        "#f59e0b",  # amber
        "#ef4444",  # red
        "#8b5cf6",  # violet
        "#ec4899",  # pink
        "#06b6d4",  # cyan
        "#84cc16",  # lime
        "#f97316",  # orange
        "#6366f1",  # indigo
        "#14b8a6",  # teal
        "#a855f7",  # purple
    ]
    categories = list(FindingCategory)
    idx = categories.index(category) if category in categories else 0
    return colors[idx % len(colors)]


def _health_score_color(score: int) -> str:
    """Get color based on health score."""
    if score >= 80:
        return "#16a34a"  # green
    elif score >= 60:
        return "#ca8a04"  # yellow
    elif score >= 40:
        return "#ea580c"  # orange
    else:
        return "#dc2626"  # red


def render_html(report: AuditReport) -> str:
    """Render an AuditReport as a responsive HTML page with charts."""
    summary = report.executive_summary

    # Calculate chart data
    severity_counts = {s: 0 for s in Severity}
    category_savings: dict[str, float] = {}

    for finding in report.findings:
        severity_counts[finding.severity] += 1
        cat_name = finding.category.value.replace("_", " ").title()
        category_savings[cat_name] = category_savings.get(cat_name, 0) + finding.potential_savings

    # Prepare chart data as JSON
    severity_chart_data = {
        "labels": [s.value.title() for s in Severity if severity_counts[s] > 0],
        "data": [severity_counts[s] for s in Severity if severity_counts[s] > 0],
        "colors": [_severity_color(s) for s in Severity if severity_counts[s] > 0],
    }

    # Sort categories by savings
    sorted_categories = sorted(category_savings.items(), key=lambda x: x[1], reverse=True)[:8]
    savings_chart_data = {
        "labels": [cat for cat, _ in sorted_categories],
        "data": [savings for _, savings in sorted_categories],
    }

    # Build HTML
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FiscalPilot Report — {_escape(report.company_name)}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <style>
        :root {{
            --primary: #2563eb;
            --primary-dark: #1d4ed8;
            --success: #16a34a;
            --warning: #ca8a04;
            --danger: #dc2626;
            --gray-50: #f9fafb;
            --gray-100: #f3f4f6;
            --gray-200: #e5e7eb;
            --gray-300: #d1d5db;
            --gray-600: #4b5563;
            --gray-700: #374151;
            --gray-800: #1f2937;
            --gray-900: #111827;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: var(--gray-50);
            color: var(--gray-800);
            line-height: 1.6;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }}

        header {{
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
            color: white;
            padding: 3rem 2rem;
            margin-bottom: 2rem;
            border-radius: 1rem;
            box-shadow: 0 10px 40px rgba(37, 99, 235, 0.3);
        }}

        header h1 {{
            font-size: 2.5rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }}

        header .subtitle {{
            opacity: 0.9;
            font-size: 1.1rem;
        }}

        .card {{
            background: white;
            border-radius: 1rem;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
            border: 1px solid var(--gray-200);
        }}

        .card-title {{
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--gray-800);
            margin-bottom: 1rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}

        .stat-card {{
            background: white;
            border-radius: 1rem;
            padding: 1.5rem;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
            border: 1px solid var(--gray-200);
            transition: transform 0.2s, box-shadow 0.2s;
        }}

        .stat-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.08);
        }}

        .stat-value {{
            font-size: 2.5rem;
            font-weight: 700;
            color: var(--primary);
        }}

        .stat-value.success {{ color: var(--success); }}
        .stat-value.warning {{ color: var(--warning); }}
        .stat-value.danger {{ color: var(--danger); }}

        .stat-label {{
            font-size: 0.875rem;
            color: var(--gray-600);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-top: 0.5rem;
        }}

        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}

        .chart-container {{
            position: relative;
            height: 300px;
        }}

        .health-gauge {{
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 2rem;
        }}

        .gauge-circle {{
            width: 180px;
            height: 180px;
            border-radius: 50%;
            background: conic-gradient(
                {_health_score_color(summary.health_score)} 0deg,
                {_health_score_color(summary.health_score)} {summary.health_score * 3.6}deg,
                var(--gray-200) {summary.health_score * 3.6}deg
            );
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
        }}

        .gauge-inner {{
            width: 140px;
            height: 140px;
            border-radius: 50%;
            background: white;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }}

        .gauge-value {{
            font-size: 3rem;
            font-weight: 700;
            color: {_health_score_color(summary.health_score)};
        }}

        .gauge-label {{
            font-size: 0.875rem;
            color: var(--gray-600);
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
        }}

        th, td {{
            padding: 1rem;
            text-align: left;
            border-bottom: 1px solid var(--gray-200);
        }}

        th {{
            background: var(--gray-50);
            font-weight: 600;
            font-size: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--gray-600);
        }}

        tr:hover {{
            background: var(--gray-50);
        }}

        .badge {{
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }}

        .badge-critical {{ background: #fee2e2; color: #991b1b; }}
        .badge-high {{ background: #ffedd5; color: #9a3412; }}
        .badge-medium {{ background: #fef3c7; color: #92400e; }}
        .badge-low {{ background: #dcfce7; color: #166534; }}
        .badge-info {{ background: #dbeafe; color: #1e40af; }}

        .finding-card {{
            border-left: 4px solid var(--primary);
            margin-bottom: 1rem;
            padding: 1rem 1.5rem;
            background: var(--gray-50);
            border-radius: 0 0.5rem 0.5rem 0;
        }}

        .finding-card.critical {{ border-left-color: var(--danger); }}
        .finding-card.high {{ border-left-color: #ea580c; }}
        .finding-card.medium {{ border-left-color: var(--warning); }}
        .finding-card.low {{ border-left-color: var(--success); }}

        .finding-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 0.5rem;
        }}

        .finding-title {{
            font-weight: 600;
            font-size: 1.1rem;
        }}

        .finding-meta {{
            display: flex;
            gap: 1rem;
            font-size: 0.875rem;
            color: var(--gray-600);
            margin-bottom: 0.5rem;
        }}

        .finding-description {{
            color: var(--gray-700);
        }}

        .finding-recommendation {{
            margin-top: 0.75rem;
            padding: 0.75rem;
            background: white;
            border-radius: 0.5rem;
            font-size: 0.9rem;
        }}

        .finding-recommendation strong {{
            color: var(--primary);
        }}

        .savings-highlight {{
            font-size: 1.1rem;
            font-weight: 600;
            color: var(--success);
        }}

        footer {{
            text-align: center;
            padding: 2rem;
            color: var(--gray-600);
            font-size: 0.875rem;
        }}

        @media (max-width: 768px) {{
            .container {{
                padding: 1rem;
            }}

            header {{
                padding: 2rem 1.5rem;
            }}

            header h1 {{
                font-size: 1.75rem;
            }}

            .charts-grid {{
                grid-template-columns: 1fr;
            }}

            .chart-container {{
                height: 250px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🛫 FiscalPilot Audit Report</h1>
            <div class="subtitle">
                <strong>{_escape(report.company_name)}</strong> •
                Generated {report.generated_at.strftime('%B %d, %Y at %H:%M UTC')}
                {f" • Period: {report.period_start} to {report.period_end}" if report.period_start else ""}
            </div>
        </header>

        <!-- Executive Summary Stats -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{summary.total_findings}</div>
                <div class="stat-label">Total Findings</div>
            </div>
            <div class="stat-card">
                <div class="stat-value danger">{summary.critical_findings}</div>
                <div class="stat-label">Critical Issues</div>
            </div>
            <div class="stat-card">
                <div class="stat-value success">${summary.total_potential_savings:,.0f}</div>
                <div class="stat-label">Potential Savings</div>
            </div>
            <div class="stat-card">
                <div class="health-gauge">
                    <div class="gauge-circle">
                        <div class="gauge-inner">
                            <div class="gauge-value">{summary.health_score}</div>
                            <div class="gauge-label">Health Score</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        {f'<div class="card"><p>{_escape(summary.narrative)}</p></div>' if summary.narrative else ''}

        <!-- Charts Section -->
        <div class="charts-grid">
            <div class="card">
                <h2 class="card-title">📊 Findings by Severity</h2>
                <div class="chart-container">
                    <canvas id="severityChart"></canvas>
                </div>
            </div>
            <div class="card">
                <h2 class="card-title">💰 Savings by Category</h2>
                <div class="chart-container">
                    <canvas id="savingsChart"></canvas>
                </div>
            </div>
        </div>

        <!-- Findings Detail -->
        <div class="card">
            <h2 class="card-title">🔍 Detailed Findings</h2>
            {_render_findings_html(report.findings)}
        </div>

        <!-- Action Items Table -->
        {_render_action_items_html(report.action_items) if report.action_items else ''}

        <!-- Proposed Actions -->
        {_render_proposed_actions_html(report.proposed_actions) if report.proposed_actions else ''}

        <footer>
            <p>Generated by <strong>FiscalPilot</strong> — AI-Powered Financial Operations</p>
            <p>© {report.generated_at.year} FiscalPilot. All rights reserved.</p>
        </footer>
    </div>

    <script>
        // Severity Doughnut Chart
        const severityCtx = document.getElementById('severityChart').getContext('2d');
        new Chart(severityCtx, {{
            type: 'doughnut',
            data: {{
                labels: {json.dumps(severity_chart_data['labels'])},
                datasets: [{{
                    data: {json.dumps(severity_chart_data['data'])},
                    backgroundColor: {json.dumps(severity_chart_data['colors'])},
                    borderWidth: 0,
                    hoverOffset: 10
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: 'bottom',
                        labels: {{
                            padding: 20,
                            usePointStyle: true,
                            font: {{ size: 12 }}
                        }}
                    }}
                }},
                cutout: '60%'
            }}
        }});

        // Savings Bar Chart
        const savingsCtx = document.getElementById('savingsChart').getContext('2d');
        new Chart(savingsCtx, {{
            type: 'bar',
            data: {{
                labels: {json.dumps(savings_chart_data['labels'])},
                datasets: [{{
                    label: 'Potential Savings ($)',
                    data: {json.dumps(savings_chart_data['data'])},
                    backgroundColor: '#16a34a',
                    borderRadius: 6,
                    borderSkipped: false
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                plugins: {{
                    legend: {{
                        display: false
                    }}
                }},
                scales: {{
                    x: {{
                        grid: {{ display: false }},
                        ticks: {{
                            callback: function(value) {{
                                return '$' + value.toLocaleString();
                            }}
                        }}
                    }},
                    y: {{
                        grid: {{ display: false }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>"""


def _render_findings_html(findings: list) -> str:
    """Render findings as HTML cards."""
    if not findings:
        return '<p style="color: var(--gray-600);">No findings to display.</p>'

    # Group by severity
    severity_order = [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]
    html_parts = []

    for severity in severity_order:
        severity_findings = [f for f in findings if f.severity == severity]
        if not severity_findings:
            continue

        for finding in severity_findings:
            badge_class = f"badge-{finding.severity.value}"
            card_class = finding.severity.value

            evidence_html = ""
            if finding.evidence:
                evidence_items = "".join(f"<li>{_escape(ev)}</li>" for ev in finding.evidence[:5])
                evidence_html = f'<ul style="margin: 0.5rem 0; padding-left: 1.5rem; color: var(--gray-600);">{evidence_items}</ul>'

            recommendation_html = ""
            if finding.recommendation:
                recommendation_html = f'''
                <div class="finding-recommendation">
                    <strong>💡 Recommendation:</strong> {_escape(finding.recommendation)}
                </div>'''

            html_parts.append(f'''
            <div class="finding-card {card_class}">
                <div class="finding-header">
                    <span class="finding-title">{_escape(finding.title)}</span>
                    <span class="badge {badge_class}">{finding.severity.value}</span>
                </div>
                <div class="finding-meta">
                    <span>📁 {finding.category.value.replace("_", " ").title()}</span>
                    <span>🎯 {finding.confidence:.0%} confidence</span>
                    <span class="savings-highlight">💰 ${finding.potential_savings:,.2f}</span>
                </div>
                <div class="finding-description">{_escape(finding.description)}</div>
                {evidence_html}
                {recommendation_html}
            </div>
            ''')

    return "".join(html_parts)


def _render_action_items_html(action_items: list) -> str:
    """Render action items as an HTML table."""
    if not action_items:
        return ""

    rows = []
    for i, item in enumerate(action_items, 1):
        priority_class = "badge-high" if item.priority.value in ["critical", "high"] else "badge-medium"
        rows.append(f'''
        <tr>
            <td>{i}</td>
            <td><strong>{_escape(item.title)}</strong></td>
            <td><span class="badge {priority_class}">{item.priority.value}</span></td>
            <td class="savings-highlight">${item.estimated_savings:,.2f}</td>
            <td>{_escape(item.effort)}</td>
        </tr>
        ''')

    return f'''
    <div class="card">
        <h2 class="card-title">✅ Action Items</h2>
        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>Action</th>
                    <th>Priority</th>
                    <th>Est. Savings</th>
                    <th>Effort</th>
                </tr>
            </thead>
            <tbody>
                {"".join(rows)}
            </tbody>
        </table>
    </div>
    '''


def _render_proposed_actions_html(proposed_actions: list) -> str:
    """Render proposed actions with approval levels."""
    if not proposed_actions:
        return ""

    approval_emoji = {
        ApprovalLevel.GREEN: "🟢",
        ApprovalLevel.YELLOW: "🟡",
        ApprovalLevel.RED: "🔴",
        ApprovalLevel.CRITICAL: "⛔",
    }

    cards = []
    for action in proposed_actions:
        emoji = approval_emoji.get(action.approval_level, "📋")

        steps_html = ""
        if action.steps:
            step_items = "".join(
                f'<li style="margin-bottom: 0.5rem;">{_escape(step.description)}</li>'
                for step in action.steps[:10]
            )
            steps_html = f'''
            <div style="margin-top: 1rem;">
                <strong>Execution Steps:</strong>
                <ol style="margin-top: 0.5rem; padding-left: 1.5rem;">{step_items}</ol>
            </div>
            '''

        cards.append(f'''
        <div class="finding-card" style="border-left-color: var(--primary);">
            <div class="finding-header">
                <span class="finding-title">{emoji} {_escape(action.title)}</span>
                <span class="badge badge-info">{action.approval_level.value}</span>
            </div>
            <div class="finding-meta">
                <span>⚡ {action.action_type.value.replace("_", " ").title()}</span>
                <span class="savings-highlight">💰 ${action.estimated_savings:,.2f} savings</span>
            </div>
            <div class="finding-description">{_escape(action.description)}</div>
            {steps_html}
        </div>
        ''')

    return f'''
    <div class="card">
        <h2 class="card-title">⚡ Proposed Actions (Execution Pipeline)</h2>
        {"".join(cards)}
    </div>
    '''
