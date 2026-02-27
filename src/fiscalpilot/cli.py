"""
FiscalPilot CLI — command-line interface.

Usage:
    fiscalpilot audit --config fiscalpilot.yaml
    fiscalpilot scan --csv transactions.csv
    fp scan --csv data.csv --company "Joe's Diner" --industry restaurant
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from fiscalpilot import __version__

app = typer.Typer(
    name="fiscalpilot",
    help="🛫 FiscalPilot — The Open-Source AI Financial Copilot",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"[bold]FiscalPilot[/bold] v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """🛩 FiscalPilot — Your AI CFO. Analyze. Recommend. Execute."""


@app.command()
def audit(
    config: str = typer.Option(
        "fiscalpilot.yaml",
        "--config",
        "-c",
        help="Path to config file",
    ),
    company: str = typer.Option(
        "My Company",
        "--company",
        help="Company name",
    ),
    industry: str = typer.Option(
        "other",
        "--industry",
        "-i",
        help="Industry: restaurant, retail, saas, manufacturing, etc.",
    ),
    output: str = typer.Option(
        "report.md",
        "--output",
        "-o",
        help="Output file path (.md, .json)",
    ),
    local: bool = typer.Option(
        False,
        "--local",
        help="Run using only intelligence engines (no LLM/API key required)",
    ),
) -> None:
    """Run a full financial audit."""
    from fiscalpilot.config import FiscalPilotConfig
    from fiscalpilot.models.company import CompanyProfile, Industry
    from fiscalpilot.pilot import FiscalPilot

    console.print(Panel.fit(
        "[bold blue]🛫 FiscalPilot[/bold blue] — Full Financial Audit",
        subtitle=f"v{__version__}",
    ))

    try:
        industry_enum = Industry(industry.lower())
    except ValueError:
        industry_enum = Industry.OTHER

    profile = CompanyProfile(name=company, industry=industry_enum)

    config_path = config if Path(config).exists() else None
    pilot = FiscalPilot.from_config(config_path)

    if local:
        console.print("[dim]Running in local mode (no LLM) — using intelligence engines only[/dim]")
        with console.status("[bold green]Running local audit...[/bold green]"):
            report = asyncio.run(pilot.local_audit(profile))
    else:
        with console.status("[bold green]Running audit...[/bold green]"):
            report = asyncio.run(pilot.audit(profile))

    _display_report(report)
    _save_report(report, output)


@app.command()
def scan(
    csv: str = typer.Option(
        None,
        "--csv",
        help="Path to CSV file with transactions",
    ),
    excel: str = typer.Option(
        None,
        "--excel",
        help="Path to Excel file with transactions",
    ),
    company: str = typer.Option(
        "My Company",
        "--company",
        help="Company name",
    ),
    industry: str = typer.Option(
        "other",
        "--industry",
        "-i",
        help="Industry type",
    ),
    output: str = typer.Option(
        "scan_report.md",
        "--output",
        "-o",
        help="Output file path",
    ),
    local: bool = typer.Option(
        False,
        "--local",
        help="Force local mode (no LLM). Auto-detected when no API key is set.",
    ),
) -> None:
    """Quick scan from a CSV or Excel file — easiest way to get started."""
    import os

    from fiscalpilot.config import ConnectorConfig, FiscalPilotConfig
    from fiscalpilot.models.company import CompanyProfile, Industry
    from fiscalpilot.pilot import FiscalPilot

    console.print(Panel.fit(
        "[bold blue]🛫 FiscalPilot[/bold blue] — Quick Scan",
        subtitle=f"v{__version__}",
    ))

    if not csv and not excel:
        console.print("[red]Error: Provide --csv or --excel file path[/red]")
        raise typer.Exit(1)

    try:
        industry_enum = Industry(industry.lower())
    except ValueError:
        industry_enum = Industry.OTHER

    profile = CompanyProfile(name=company, industry=industry_enum)

    # Build config with file connector
    connectors = []
    if csv:
        connectors.append(ConnectorConfig(type="csv", options={"file_path": csv}))
    if excel:
        connectors.append(ConnectorConfig(type="excel", options={"file_path": excel}))

    config = FiscalPilotConfig(connectors=connectors)
    pilot = FiscalPilot(config=config)
    pilot._setup()

    # Auto-detect local mode: if no API key is set and --local not explicitly given
    has_api_key = bool(
        config.llm.api_key
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("FISCALPILOT_API_KEY")
        or os.environ.get("ANTHROPIC_API_KEY")
    )
    use_local = local or not has_api_key

    if use_local:
        if not local:
            console.print(
                "[dim]No API key detected — running in local mode "
                "(intelligence engines only, no LLM). Set OPENAI_API_KEY for full analysis.[/dim]"
            )
        else:
            console.print("[dim]Running in local mode (no LLM) — using intelligence engines only[/dim]")
        with console.status("[bold green]Scanning...[/bold green]"):
            report = asyncio.run(pilot.local_audit(profile))
    else:
        with console.status("[bold green]Scanning...[/bold green]"):
            report = asyncio.run(pilot.quick_scan(profile))

    _display_report(report)
    _save_report(report, output)


@app.command()
def connectors() -> None:
    """List all available connectors."""
    from fiscalpilot.connectors.registry import _BUILTIN_CONNECTORS

    table = Table(title="Available Connectors")
    table.add_column("Type", style="bold cyan")
    table.add_column("Module")
    table.add_column("Status")

    for name, path in _BUILTIN_CONNECTORS.items():
        module = path.rsplit(".", 1)[0]
        try:
            __import__(module)
            status = "✅ Available"
        except ImportError:
            status = "📦 Needs install"
        table.add_row(name, path, status)

    console.print(table)


def _display_report(report) -> None:  # noqa: ANN001
    """Display report summary in the terminal."""
    from fiscalpilot.models.report import Severity

    console.print()

    # Summary table
    table = Table(title="Audit Summary", show_lines=True)
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    table.add_row("Total Findings", str(len(report.findings)))
    table.add_row("Critical Findings", str(len(report.critical_findings)))
    table.add_row(
        "Total Potential Savings",
        f"${report.total_potential_savings:,.2f}",
    )
    table.add_row(
        "Health Score",
        f"{report.executive_summary.health_score}/100",
    )
    if report.proposed_actions:
        table.add_row("Proposed Actions", str(len(report.proposed_actions)))
    if report.intelligence.benchmark_grade:
        table.add_row("Benchmark Grade", report.intelligence.benchmark_grade)
    if report.intelligence.cashflow_runway_months:
        table.add_row("Cash Runway", f"{report.intelligence.cashflow_runway_months:.1f} months")

    console.print(table)
    console.print()

    # Top findings
    if report.findings:
        console.print("[bold]Top Findings:[/bold]")
        for i, finding in enumerate(report.findings[:5], 1):
            severity_colors = {
                Severity.CRITICAL: "red",
                Severity.HIGH: "yellow",
                Severity.MEDIUM: "blue",
                Severity.LOW: "green",
            }
            color = severity_colors.get(finding.severity, "white")
            console.print(
                f"  {i}. [{color}][{finding.severity.value.upper()}][/{color}] "
                f"{finding.title} — ${finding.potential_savings:,.2f}"
            )
        console.print()


def _save_report(report, output: str) -> None:  # noqa: ANN001
    """Save report to file."""
    path = Path(output)
    if path.suffix == ".json":
        content = report.to_json()
    else:
        content = report.to_markdown()

    path.write_text(content)
    console.print(f"[green]✓[/green] Report saved to [bold]{path}[/bold]")


if __name__ == "__main__":
    app()
