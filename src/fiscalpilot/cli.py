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
def restaurant(
    csv: str = typer.Option(
        None,
        "--csv",
        help="Path to CSV file with transactions",
    ),
    square: bool = typer.Option(
        False,
        "--square",
        help="Use Square POS connector (requires SQUARE_ACCESS_TOKEN)",
    ),
    company: str = typer.Option(
        "My Restaurant",
        "--company",
        help="Restaurant name",
    ),
    revenue: float = typer.Option(
        0,
        "--revenue",
        help="Annual revenue (for KPI analysis)",
    ),
    output: str = typer.Option(
        "restaurant_report.md",
        "--output",
        "-o",
        help="Output file path",
    ),
    menu: bool = typer.Option(
        False,
        "--menu",
        help="Include menu engineering analysis (requires menu data)",
    ),
    breakeven: bool = typer.Option(
        False,
        "--breakeven",
        help="Calculate break-even point",
    ),
    tips: bool = typer.Option(
        False,
        "--tips",
        help="Estimate FICA tip tax credit",
    ),
    delivery: bool = typer.Option(
        False,
        "--delivery",
        help="Analyze delivery platform ROI",
    ),
) -> None:
    """Complete restaurant financial analysis — KPIs, menu engineering, and more."""
    import os
    from pathlib import Path

    console.print(Panel.fit(
        "[bold blue]🍽️ FiscalPilot[/bold blue] — Restaurant Analysis",
        subtitle=f"v{__version__}",
    ))

    if not csv and not square:
        console.print("[red]Error: Provide --csv file or use --square connector[/red]")
        raise typer.Exit(1)

    from fiscalpilot.analyzers.restaurant import RestaurantAnalyzer
    from fiscalpilot.connectors.csv_connector import CSVConnector
    from fiscalpilot.models.company import CompanyProfile, Industry, CompanySize

    profile = CompanyProfile(
        name=company,
        industry=Industry.RESTAURANT,
        size=CompanySize.SMALL,
        annual_revenue=revenue if revenue > 0 else None,
    )

    # Pull data
    dataset = None
    if csv:
        connector = CSVConnector(credentials={"file_path": csv})
        with console.status("[bold green]Loading transactions...[/bold green]"):
            dataset = asyncio.run(connector.pull(profile))
    elif square:
        access_token = os.environ.get("SQUARE_ACCESS_TOKEN")
        if not access_token:
            console.print("[red]Error: Set SQUARE_ACCESS_TOKEN environment variable[/red]")
            raise typer.Exit(1)
        from fiscalpilot.connectors import SquarePOSConnector
        connector = SquarePOSConnector(access_token=access_token)
        with console.status("[bold green]Pulling from Square POS...[/bold green]"):
            dataset = asyncio.run(connector.pull())

    # Run KPI analysis
    console.print("\n[bold]📊 Restaurant KPIs[/bold]")
    result = RestaurantAnalyzer.analyze(dataset, annual_revenue=revenue if revenue > 0 else None)

    # Display health grade
    grade_colors = {"A": "green", "B": "blue", "C": "yellow", "D": "red", "F": "red bold"}
    grade_color = grade_colors.get(result.health_grade, "white")
    console.print(f"\n[{grade_color}]Health Grade: {result.health_grade}[/{grade_color}] ({result.health_score}/100)")

    # KPI table
    table = Table(title="Key Performance Indicators")
    table.add_column("KPI", style="cyan")
    table.add_column("Actual", justify="right")
    table.add_column("Target", justify="right")
    table.add_column("Status")

    for kpi in result.kpis:
        status_map = {
            "excellent": "🌟",
            "healthy": "✅",
            "warning": "⚠️",
            "critical": "🚨",
        }
        status = status_map.get(kpi.severity.value, "")
        table.add_row(
            kpi.display_name,
            f"{kpi.actual:.1f}%",
            f"{kpi.benchmark_low:.0f}-{kpi.benchmark_high:.0f}%",
            status,
        )

    console.print(table)

    # Critical alerts
    if result.critical_alerts:
        console.print("\n[bold red]🚨 Critical Alerts[/bold red]")
        for alert in result.critical_alerts:
            console.print(f"  • {alert}")

    # Opportunities
    if result.opportunities:
        console.print("\n[bold green]💡 Opportunities[/bold green]")
        for opp in result.opportunities[:5]:
            console.print(f"  • {opp}")

    # Additional analyses (if flags provided)
    if breakeven and revenue > 0:
        from fiscalpilot.analyzers.breakeven import BreakevenCalculator
        console.print("\n[bold]📈 Break-even Analysis[/bold]")
        # Estimate costs based on typical restaurant ratios
        monthly_revenue = revenue / 12
        estimated_rent = monthly_revenue * 0.06  # ~6% of revenue
        estimated_labor = monthly_revenue * 0.10  # Salaried staff ~10%
        be_result = BreakevenCalculator.calculate(
            rent=estimated_rent,
            management_salaries=estimated_labor,
            insurance=monthly_revenue * 0.015,
            base_utilities=monthly_revenue * 0.025,
            food_cost_pct=32,
            hourly_labor_pct=22,
            average_check=35,
        )
        console.print(f"  Break-even Revenue: ${be_result.breakeven_revenue_monthly:,.0f}/month")
        console.print(f"  Break-even Covers: {be_result.breakeven_covers_monthly:,.0f}/month ({be_result.breakeven_covers_daily:.0f}/day)")

    if tips:
        from fiscalpilot.analyzers.tip_credit import TipCreditCalculator
        console.print("\n[bold]💰 Tip Tax Credit Estimate[/bold]")
        # Quick estimate based on typical staffing
        estimate = TipCreditCalculator.quick_estimate(
            num_tipped_employees=8,
            avg_monthly_tips_per_employee=2500,
            avg_hours_per_employee=140,
        )
        console.print(f"  Estimated Monthly Credit: ${estimate['monthly_credit']:,.2f}")
        console.print(f"  Estimated Annual Credit: ${estimate['annual_credit']:,.2f}")

    # Save report
    report_path = Path(output)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    _save_restaurant_report(result, company, str(report_path))
    console.print(f"\n✅ Report saved to {output}")


def _save_restaurant_report(result, company_name: str, output: str) -> None:
    """Save restaurant analysis to markdown."""
    from pathlib import Path
    lines = [
        f"# Restaurant Analysis: {company_name}",
        "",
        f"**Health Grade:** {result.health_grade} ({result.health_score}/100)",
        "",
        "## Key Performance Indicators",
        "",
        "| KPI | Actual | Target | Status |",
        "|-----|--------|--------|--------|",
    ]
    for kpi in result.kpis:
        lines.append(f"| {kpi.display_name} | {kpi.actual:.1f}% | {kpi.benchmark_low:.0f}-{kpi.benchmark_high:.0f}% | {kpi.severity.value} |")
    
    if result.critical_alerts:
        lines.extend(["", "## Critical Alerts", ""])
        for alert in result.critical_alerts:
            lines.append(f"- {alert}")
    
    if result.opportunities:
        lines.extend(["", "## Opportunities", ""])
        for opp in result.opportunities:
            lines.append(f"- {opp}")
    
    lines.extend(["", "---", "*Generated by FiscalPilot — The Open-Source AI CFO*"])
    Path(output).write_text("\n".join(lines))


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


@app.command()
def connect(
    provider: str = typer.Argument(
        ...,
        help="Provider to connect: quickbooks, xero, square, plaid",
    ),
    sandbox: bool = typer.Option(
        False,
        "--sandbox",
        help="Use sandbox/development environment",
    ),
    port: int = typer.Option(
        8080,
        "--port",
        help="Local port for OAuth callback",
    ),
) -> None:
    """Connect to an accounting platform via OAuth2."""
    provider_lower = provider.lower()
    
    if provider_lower == "quickbooks":
        _connect_quickbooks_interactive(sandbox=sandbox, port=port)
    elif provider_lower == "xero":
        _connect_xero_interactive(port=port)
    elif provider_lower == "square":
        _connect_square_interactive(sandbox=sandbox)
    elif provider_lower == "plaid":
        _connect_plaid_interactive(sandbox=sandbox, port=port)
    else:
        console.print(f"[red]Unknown provider: {provider}[/red]")
        console.print("Supported: quickbooks, xero, square, plaid")
        raise typer.Exit(1)


@app.command()
def disconnect(
    provider: str = typer.Argument(
        ...,
        help="Provider to disconnect: quickbooks, xero, square",
    ),
) -> None:
    """Remove stored credentials for a provider."""
    from pathlib import Path
    
    token_dir = Path.home() / ".fiscalpilot" / "tokens"
    token_file = token_dir / f"{provider.lower()}.json"
    
    if token_file.exists():
        token_file.unlink()
        console.print(f"[green]✓[/green] Disconnected from {provider}")
    else:
        console.print(f"[yellow]No credentials found for {provider}[/yellow]")


@app.command()
def connections() -> None:
    """Show connected integrations."""
    from pathlib import Path
    
    token_dir = Path.home() / ".fiscalpilot" / "tokens"
    
    table = Table(title="Connected Integrations")
    table.add_column("Provider", style="bold cyan")
    table.add_column("Status")
    table.add_column("Token File")
    
    providers = ["quickbooks", "xero", "square", "plaid"]
    
    for provider in providers:
        token_file = token_dir / f"{provider}.json"
        if token_file.exists():
            status = "[green]✓ Connected[/green]"
            file_info = str(token_file)
        else:
            status = "[dim]Not connected[/dim]"
            file_info = "-"
        table.add_row(provider.title(), status, file_info)
    
    console.print(table)
    console.print()
    console.print("[dim]Connect with:[/dim] fp connect <provider>")
    console.print("[dim]Disconnect with:[/dim] fp disconnect <provider>")


def _connect_quickbooks_interactive(sandbox: bool = False, port: int = 8080) -> None:
    """Interactive QuickBooks OAuth2 connection."""
    from fiscalpilot.connectors.quickbooks_connector import QuickBooksConnector
    
    console.print(Panel.fit(
        "[bold blue]🔗 QuickBooks Connection[/bold blue]",
        subtitle="OAuth2 Setup",
    ))
    console.print()
    
    # Get credentials
    console.print("[bold]Step 1: Enter API Credentials[/bold]")
    console.print("Get these from: [link]https://developer.intuit.com/app/developer/dashboard[/link]")
    console.print()
    
    client_id = typer.prompt("Client ID")
    client_secret = typer.prompt("Client Secret", hide_input=True)
    
    connector = QuickBooksConnector(
        credentials={
            "client_id": client_id,
            "client_secret": client_secret,
        },
        sandbox=sandbox,
    )
    
    console.print()
    console.print("[bold]Step 2: Authorize in Browser[/bold]")
    console.print("[dim]Opening browser for QuickBooks login...[/dim]")
    console.print()
    
    try:
        realm_id = asyncio.run(connector.authorize(port=port, timeout=300))
        console.print()
        console.print("[green]✓ QuickBooks connected successfully![/green]")
        console.print()
        console.print(f"Company ID: [bold]{realm_id}[/bold]")
        console.print(f"Tokens saved to: [bold]~/.fiscalpilot/tokens/quickbooks.json[/bold]")
        console.print()
        console.print("Add to fiscalpilot.yaml:")
        console.print("[dim]connectors:")
        console.print(f"  - type: quickbooks")
        console.print(f"    credentials:")
        console.print(f"      client_id: {client_id}")
        console.print(f"      client_secret: <YOUR_SECRET>")
        console.print(f"      realm_id: {realm_id}")
        console.print(f"    sandbox: {sandbox}[/dim]")
    except TimeoutError:
        console.print("[red]Authorization timed out. Please try again.[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Connection failed: {e}[/red]")
        raise typer.Exit(1)


def _connect_xero_interactive(port: int = 8080) -> None:
    """Interactive Xero OAuth2 connection."""
    from fiscalpilot.connectors.xero_connector import XeroConnector
    
    console.print(Panel.fit(
        "[bold blue]🔗 Xero Connection[/bold blue]",
        subtitle="OAuth2 Setup",
    ))
    console.print()
    
    # Get credentials
    console.print("[bold]Step 1: Enter API Credentials[/bold]")
    console.print("Get these from: [link]https://developer.xero.com/myapps/[/link]")
    console.print()
    
    client_id = typer.prompt("Client ID")
    client_secret = typer.prompt("Client Secret", hide_input=True)
    
    connector = XeroConnector(
        credentials={
            "client_id": client_id,
            "client_secret": client_secret,
        },
    )
    
    console.print()
    console.print("[bold]Step 2: Authorize in Browser[/bold]")
    console.print("[dim]Opening browser for Xero login...[/dim]")
    console.print()
    
    try:
        tenant_id = asyncio.run(connector.authorize(port=port, timeout=300))
        console.print()
        console.print("[green]✓ Xero connected successfully![/green]")
        console.print()
        console.print(f"Organization ID: [bold]{tenant_id}[/bold]")
        console.print(f"Tokens saved to: [bold]~/.fiscalpilot/tokens/xero.json[/bold]")
        console.print()
        console.print("Add to fiscalpilot.yaml:")
        console.print("[dim]connectors:")
        console.print(f"  - type: xero")
        console.print(f"    credentials:")
        console.print(f"      client_id: {client_id}")
        console.print(f"      client_secret: <YOUR_SECRET>")
        console.print(f"      tenant_id: {tenant_id}[/dim]")
    except TimeoutError:
        console.print("[red]Authorization timed out. Please try again.[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Connection failed: {e}[/red]")
        raise typer.Exit(1)


def _connect_square_interactive(sandbox: bool = False) -> None:
    """Interactive Square connection (access token based)."""
    console.print(Panel.fit(
        "[bold blue]🔗 Square Connection[/bold blue]",
        subtitle="Access Token Setup",
    ))
    console.print()
    
    console.print("[bold]Square uses personal access tokens[/bold]")
    console.print("Get yours from: [link]https://developer.squareup.com/apps[/link]")
    console.print()
    
    access_token = typer.prompt("Access Token", hide_input=True)
    location_id = typer.prompt("Location ID (optional, press Enter to skip)", default="")
    
    # Save to a config suggestion
    console.print()
    console.print("[green]✓ Square credentials ready![/green]")
    console.print()
    console.print("Add to fiscalpilot.yaml:")
    console.print("[dim]connectors:")
    console.print(f"  - type: square")
    console.print(f"    credentials:")
    console.print(f"      access_token: <YOUR_TOKEN>")
    if location_id:
        console.print(f"      location_id: {location_id}")
    console.print(f"    sandbox: {sandbox}[/dim]")
    console.print()
    console.print("[yellow]Note: Square tokens are not stored. Add them to your config file.[/yellow]")


def _connect_plaid_interactive(sandbox: bool = False, port: int = 8080) -> None:
    """Interactive Plaid Link connection."""
    from fiscalpilot.connectors.plaid_connector import PlaidConnector
    
    console.print(Panel.fit(
        "[bold blue]🏦 Plaid Bank Connection[/bold blue]",
        subtitle="Plaid Link Setup",
    ))
    console.print()
    
    # Get credentials
    console.print("[bold]Step 1: Enter API Credentials[/bold]")
    console.print("Get these from: [link]https://dashboard.plaid.com/developers/keys[/link]")
    console.print()
    
    client_id = typer.prompt("Client ID")
    secret = typer.prompt("Secret", hide_input=True)
    
    environment = "sandbox" if sandbox else "development"
    
    connector = PlaidConnector(
        credentials={
            "client_id": client_id,
            "secret": secret,
        },
        environment=environment,
    )
    
    console.print()
    console.print("[bold]Step 2: Connect Bank via Plaid Link[/bold]")
    console.print("[dim]Opening browser for bank connection...[/dim]")
    console.print()
    
    try:
        access_token = asyncio.run(connector.authorize(port=port, timeout=300))
        console.print()
        console.print("[green]✓ Bank connected successfully![/green]")
        console.print()
        console.print(f"Access token: [bold]{access_token[:20]}...[/bold]")
        console.print(f"Tokens saved to: [bold]~/.fiscalpilot/tokens/plaid.json[/bold]")
        console.print()
        console.print("Add to fiscalpilot.yaml:")
        console.print("[dim]connectors:")
        console.print(f"  - type: plaid")
        console.print(f"    credentials:")
        console.print(f"      client_id: {client_id}")
        console.print(f"      secret: <YOUR_SECRET>")
        console.print(f"    environment: {environment}[/dim]")
        console.print()
        console.print("[dim]Run 'fp connect plaid' again to connect additional banks[/dim]")
    except TimeoutError:
        console.print("[red]Authorization timed out. Please try again.[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Connection failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def restaurant(
    csv: str = typer.Option(
        None,
        "--csv",
        help="Path to CSV with transactions",
    ),
    quickbooks: bool = typer.Option(
        False,
        "--quickbooks",
        "--qb",
        help="Use QuickBooks connector (requires setup via 'fiscalpilot connect quickbooks')",
    ),
    company: str = typer.Option(
        "My Restaurant",
        "--company",
        help="Restaurant name",
    ),
    revenue: float = typer.Option(
        None,
        "--revenue",
        "-r",
        help="Annual revenue estimate (for ratio calculations)",
    ),
    output: str = typer.Option(
        "restaurant_analysis.md",
        "--output",
        "-o",
        help="Output file path",
    ),
) -> None:
    """Restaurant-specific financial analysis with industry KPIs.
    
    Analyzes your restaurant's financials against industry benchmarks:
    - Food Cost % (target: 28-32%)
    - Labor Cost % (target: 28-32%)
    - Prime Cost (Food + Labor, target: 55-65%)
    - Occupancy Cost % (rent + utilities)
    - Net Operating Margin
    """
    from fiscalpilot.analyzers.restaurant import RestaurantAnalyzer
    from fiscalpilot.connectors.csv_connector import CSVConnector
    from fiscalpilot.models.company import CompanyProfile, Industry

    console.print(Panel.fit(
        "[bold blue]🍽️ FiscalPilot Restaurant Analysis[/bold blue]",
        subtitle=f"v{__version__}",
    ))

    if not csv and not quickbooks:
        console.print("[red]Error: Provide --csv file or --quickbooks flag[/red]")
        raise typer.Exit(1)

    profile = CompanyProfile(name=company, industry=Industry.RESTAURANT)

    # Load data
    if csv:
        console.print(f"[dim]Loading transactions from {csv}...[/dim]")
        connector = CSVConnector(credentials={"file_path": csv})
        dataset = asyncio.run(connector.pull(profile))
        asyncio.run(connector.close())
    else:
        # QuickBooks
        console.print("[dim]Loading transactions from QuickBooks...[/dim]")
        from fiscalpilot.connectors.quickbooks_connector import QuickBooksConnector
        from pathlib import Path
        import json

        # Load saved tokens
        token_file = Path.home() / ".fiscalpilot" / "tokens" / "quickbooks.json"
        if not token_file.exists():
            console.print("[red]QuickBooks not connected. Run 'fiscalpilot connect quickbooks' first.[/red]")
            raise typer.Exit(1)

        tokens = json.loads(token_file.read_text())
        connector = QuickBooksConnector(credentials={
            "refresh_token": tokens.get("refresh_token", ""),
            # Other credentials need to come from config
        })
        dataset = asyncio.run(connector.pull(profile))
        asyncio.run(connector.close())

    # Run restaurant analysis
    console.print("[dim]Running restaurant KPI analysis...[/dim]")
    result = RestaurantAnalyzer.analyze(dataset, annual_revenue=revenue)

    # Display results
    _display_restaurant_analysis(result)

    # Save detailed report
    _save_restaurant_report(result, company, output)


def _display_restaurant_analysis(result) -> None:
    """Display restaurant analysis summary in terminal."""
    from fiscalpilot.analyzers.restaurant import RestaurantKPISeverity

    console.print()

    # Health grade banner
    grade_colors = {"A": "green", "B": "cyan", "C": "yellow", "D": "orange1", "F": "red"}
    color = grade_colors.get(result.health_grade, "white")
    console.print(Panel(
        f"[bold {color}]{result.health_grade}[/bold {color}]",
        title="Health Grade",
        subtitle=f"Score: {result.health_score}/100",
    ))

    # KPI Table
    table = Table(title="Restaurant KPIs", show_lines=True)
    table.add_column("Metric", style="bold")
    table.add_column("Actual", justify="right")
    table.add_column("Target", justify="right")
    table.add_column("Status")

    severity_icons = {
        RestaurantKPISeverity.CRITICAL: "🚨",
        RestaurantKPISeverity.WARNING: "⚠️",
        RestaurantKPISeverity.HEALTHY: "✅",
        RestaurantKPISeverity.EXCELLENT: "🌟",
    }

    for kpi in result.kpis:
        icon = severity_icons.get(kpi.severity, "")
        actual_str = f"{kpi.actual:.1f}%"
        target_str = f"{kpi.benchmark_low:.0f}-{kpi.benchmark_high:.0f}%"
        table.add_row(kpi.display_name, actual_str, target_str, f"{icon} {kpi.severity.value}")

    console.print(table)
    console.print()

    # Financial summary
    table2 = Table(title="Financial Summary")
    table2.add_column("Metric", style="bold")
    table2.add_column("Value", justify="right")

    table2.add_row("Annual Revenue (Est)", f"${result.total_revenue:,.2f}")
    table2.add_row("Total Expenses (Est)", f"${result.total_expenses:,.2f}")
    table2.add_row("Net Operating Income", f"${result.net_operating_income:,.2f}")

    console.print(table2)
    console.print()

    # Critical alerts
    if result.critical_alerts:
        console.print("[bold red]Critical Alerts:[/bold red]")
        for alert in result.critical_alerts:
            console.print(f"  {alert}")
        console.print()

    # Opportunities
    if result.opportunities:
        console.print("[bold]Insights & Opportunities:[/bold]")
        for opp in result.opportunities[:5]:
            console.print(f"  {opp}")
        console.print()


def _save_restaurant_report(result, company_name: str, output: str) -> None:
    """Save detailed restaurant report to markdown."""
    from fiscalpilot.analyzers.restaurant import RestaurantKPISeverity

    lines = [
        f"# Restaurant Financial Analysis: {company_name}",
        "",
        f"**Analysis Period:** {result.analysis_period}",
        f"**Health Grade:** {result.health_grade} ({result.health_score}/100)",
        "",
        "## Executive Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
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

    lines.extend([
        "",
        "## KPI Analysis",
        "",
    ])

    for kpi in result.kpis:
        lines.append(f"### {kpi.display_name}")
        lines.append("")
        lines.append(f"**Actual:** {kpi.actual:.1f}%  ")
        lines.append(f"**Industry Benchmark:** {kpi.benchmark_typical:.1f}% (range: {kpi.benchmark_low:.0f}-{kpi.benchmark_high:.0f}%)")
        lines.append("")
        lines.append(f"**Insight:** {kpi.insight}")
        if kpi.action:
            lines.append(f"  ")
            lines.append(f"**Action:** {kpi.action}")
        lines.append("")

    if result.critical_alerts:
        lines.extend([
            "## Critical Alerts",
            "",
        ])
        for alert in result.critical_alerts:
            lines.append(f"- {alert}")
        lines.append("")

    if result.opportunities:
        lines.extend([
            "## Optimization Opportunities",
            "",
        ])
        for opp in result.opportunities:
            lines.append(f"- {opp}")
        lines.append("")

    # Expense breakdown
    lines.extend([
        "## Expense Breakdown",
        "",
        "| Category | % of Revenue |",
        "|----------|-------------|",
    ])
    for cat, pct in sorted(result.expense_ratios.items(), key=lambda x: -x[1]):
        if pct > 0.1:
            lines.append(f"| {cat.replace('_', ' ').title()} | {pct:.1f}% |")

    lines.extend([
        "",
        "---",
        "*Generated by [FiscalPilot](https://github.com/meetpandya27/FiscalPilot) — The Open-Source AI CFO*",
    ])

    Path(output).write_text("\n".join(lines))
    console.print(f"[green]✓[/green] Report saved to [bold]{output}[/bold]")


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
