<div align="center">

# 🛫 FiscalPilot

### The Open-Source AI CFO

**Your AI Chief Financial Officer that doesn't just analyze — it acts.**  
**Analyze. Recommend. Execute. All on YOUR infrastructure.**

[![CI](https://github.com/meetpandya27/FiscalPilot/actions/workflows/ci.yml/badge.svg)](https://github.com/meetpandya27/FiscalPilot/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/meetpandya27/FiscalPilot/branch/main/graph/badge.svg)](https://codecov.io/gh/meetpandya27/FiscalPilot)
[![PyPI version](https://img.shields.io/pypi/v/fiscalpilot.svg)](https://pypi.org/project/fiscalpilot/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
<br />
[![GitHub Stars](https://img.shields.io/github/stars/meetpandya27/FiscalPilot?style=social)](https://github.com/meetpandya27/FiscalPilot)
[![Discord](https://img.shields.io/badge/Discord-Join%20Community-7289DA?logo=discord&logoColor=white)](https://discord.com/invite/kj3q9S2E5)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

<br />

[**Quickstart**](#-quickstart) · [**How It Works**](#-how-it-works) · [**Real Examples**](#-real-examples) · [**Execution Engine**](#-execution-engine) · [**Connectors**](#-connectors) · [**Contributing**](#-contributing) · [**Roadmap**](#-roadmap)

<br />

<img src="docs/assets/hero.png" alt="FiscalPilot" width="700" />

</div>

---

## 🤔 What is FiscalPilot?

FiscalPilot is the **first open-source AI CFO** — an autonomous agent that connects to your financial systems, understands your business, and takes action. Not just reports. Not just dashboards. An actual AI-powered Chief Financial Officer that can think, recommend, and — with your approval — **execute**.

### What your AI CFO does

- 📊 **Analyzes** — Scans every transaction, invoice, and account balance across all your systems
- 🧠 **Understands** — Applies Benford's Law, anomaly detection, industry benchmarks, and cash flow modeling
- 💡 **Recommends** — Surfaces specific, dollar-quantified opportunities with clear next steps
- ⚡ **Executes** — With your approval, takes action: categorizes expenses, pays bills, cancels subscriptions, files reports
- 🛡️ **Asks first** — Human-in-the-loop by default. Nothing happens without your say-so. You control the autonomy level.

### Built for every business — from one person to one thousand

Unlike tools that only serve tech startups or only serve enterprises, FiscalPilot adapts to **any business, any industry, any size**.

| 👤 Freelancer | 🍕 Restaurant | 🏥 Healthcare Practice | 💻 SaaS Startup | 🏗️ Construction Co | 🏭 Enterprise |
|---|---|---|---|---|---|
| Auto-categorize expenses | Track food cost ratios | Manage insurance billing | Monitor burn rate | Track project costs | Multi-entity consolidation |
| Estimate quarterly taxes | Negotiate supplier prices | Flag compliance gaps | Optimize SaaS stack | Verify subcontractor invoices | Treasury optimization |
| Send invoice reminders | Schedule vendor payments | Reconcile patient payments | Recognize revenue (ASC 606) | Manage retainage | Global tax provisioning |
| Find missed deductions | Detect POS discrepancies | Verify CPT code billing | Calculate R&D tax credits | Benchmark material costs | Automated month-end close |

### 🔒 Privacy first. Open source forever.

FiscalPilot runs **entirely on your infrastructure**. Your financial data never leaves your systems. Use local LLMs (Ollama, vLLM) for complete privacy, or connect to any cloud provider. No vendor lock-in. No data harvesting. Apache 2.0 licensed.

> **Why open source matters for financial tools:** Closed-source SaaS products like Ramp, Stampli, and Vic.ai do great work — but they require you to upload your most sensitive data to someone else's cloud. FiscalPilot gives you the same capabilities with zero trust requirements.

---

## 🍽️ Restaurant Owners: Start Here

**No technical skills needed.** Just three steps:

### Step 1: Start the App

```bash
# If you have Docker installed (ask your IT person):
git clone https://github.com/meetpandya27/FiscalPilot.git
cd FiscalPilot
docker-compose up
```

Then open **http://localhost:8501** in your browser.

### Step 2: Upload Your Data

Export your transactions from QuickBooks, Square, or your POS:
- **QuickBooks:** Reports → Transaction List → Export to Excel
- **Square:** Transactions → Export CSV
- **Toast:** Reports → Sales Summary → Download

### Step 3: Get Your Report

Click "Analyze" and instantly see:
- ✅ Health Grade (A–F)
- 📊 Food Cost, Labor Cost, Prime Cost analysis
- 💰 Tip tax credits you may be missing ($5,000–$15,000/year!)
- 📈 Break-even: how many covers you need daily

**Not tech-savvy?** Check out our [Getting Started Guide](GETTING_STARTED.md) with step-by-step instructions.

---

## ⚡ Quickstart (For Developers)

### Install

```bash
pip install fiscalpilot
```

### Run your first analysis

```bash
# Quick scan from CSV — works in 60 seconds
fp scan --csv expenses.csv --company "My Business" --industry restaurant

# Full analysis with config file
fp audit --config fiscalpilot.yaml
```

### Use as a Python library

```python
import asyncio
from fiscalpilot import FiscalPilot
from fiscalpilot.models.company import CompanyProfile, Industry, CompanySize

company = CompanyProfile(
    name="Riverside Dental",
    industry=Industry.HEALTHCARE,
    size=CompanySize.SMALL,
    annual_revenue=800_000,
)

pilot = FiscalPilot.from_config("fiscalpilot.yaml")
report = asyncio.run(pilot.audit(company))

print(f"Identified {len(report.findings)} opportunities")
print(f"Potential savings: ${report.total_potential_savings:,.2f}")
print(f"Proposed actions: {len(report.proposed_actions)}")

# Review proposed actions before execution
for action in report.proposed_actions:
    print(f"  [{action.approval_level}] {action.title} — saves ${action.estimated_savings:,.2f}")

# Approve and execute (human-in-the-loop)
pilot.approve(action_ids=["act_001", "act_003"])
results = asyncio.run(pilot.execute_approved())
```

### Configuration

Create a `fiscalpilot.yaml`:

```yaml
llm:
  model: "gpt-4o"                    # Or "ollama/llama3.1" for local
  # api_key: set OPENAI_API_KEY env var

connectors:
  - type: csv
    options:
      file_path: "./data/transactions.csv"

  # - type: quickbooks
  #   credentials:
  #     client_id: "..."
  #     client_secret: "..."

  # - type: plaid
  #   credentials:
  #     client_id: "..."
  #     secret: "..."

analyzers:
  cost_optimization: true
  risk_detection: true
  margin_optimization: true
  cost_reduction: true
  revenue_leakage: true
  vendor_analysis: true
  # Intelligence engines (all enabled by default)
  benfords_analysis: true
  anomaly_detection: true
  benchmark_comparison: true
  cashflow_forecast: true
  tax_optimization: true

# Execution & Action Engine (v0.4)
execution:
  enabled: true
  dry_run: true                      # Preview actions without executing
  require_approval: true             # Human-in-the-loop by default

  # Autonomy levels control what needs approval
  autonomy:
    green:                           # Auto-execute (low risk)
      - categorize_transaction
      - tag_expense
      - generate_report
    yellow:                          # Execute + notify
      - send_reminder
      - update_category_bulk
    red:                             # Require explicit approval
      - cancel_subscription
      - pay_invoice
      - renegotiate_vendor
    critical:                        # Require multi-party approval
      - change_payroll
      - modify_tax_filing
      - transfer_large_amount

  approval:
    timeout_hours: 48                # Auto-reject if not approved
    approvers:                       # Who can approve
      - email: "cfo@company.com"
        level: critical
      - email: "controller@company.com"
        level: red

security:
  local_only: false                  # Set true to never send data externally
  encrypt_at_rest: true
  redact_pii: true
  audit_trail: true                  # Log every action for compliance
```

---

## 🍕 Restaurant Vertical (Production Ready)

FiscalPilot includes a **complete solution for restaurant operators** — the first industry vertical to reach production status.

### One-Command Restaurant Analysis

```bash
# Full restaurant analysis from CLI
fp restaurant --csv transactions.csv --company "Joe's Diner" --revenue 850000

# Or with Square POS integration
fp restaurant --square --company "Joe's Diner"
```

### What's Included

| Feature | What It Does | CFO Question Answered |
|---------|-------------|----------------------|
| **15+ KPIs** | Food cost %, labor %, prime cost, RevPASH, covers/day | "How healthy is my restaurant?" |
| **Menu Engineering** | BCG matrix (Stars/Plowhorses/Puzzles/Dogs) | "Which menu items are actually profitable?" |
| **Break-even Calculator** | Revenue & covers needed to not lose money | "Can I make payroll this month?" |
| **Tip Tax Credit** | FICA Section 45B credit estimation | "Am I leaving money on the table?" |
| **Delivery ROI** | DoorDash/UberEats vs dine-in margin analysis | "Is DoorDash actually worth it?" |
| **Square POS Integration** | Pull payments, menu items, daily summaries | "What happened at my registers today?" |

### Python Usage

```python
from fiscalpilot.agents.restaurant import create_restaurant_agent
from fiscalpilot.analyzers.menu_engineering import MenuEngineeringAnalyzer, MenuItemData
from fiscalpilot.analyzers.breakeven import BreakevenCalculator
from fiscalpilot.analyzers.tip_credit import TipCreditCalculator
from fiscalpilot.analyzers.delivery_roi import DeliveryROIAnalyzer, DeliveryOrderData

# Menu Engineering — find your Stars and Dogs
menu_items = [
    MenuItemData(name="Margherita Pizza", menu_price=16, food_cost=4, quantity_sold=450),
    MenuItemData(name="Truffle Pasta", menu_price=28, food_cost=12, quantity_sold=80),
    MenuItemData(name="House Salad", menu_price=8, food_cost=2.50, quantity_sold=300),
    MenuItemData(name="Lobster Tail", menu_price=55, food_cost=28, quantity_sold=25),
]
result = MenuEngineeringAnalyzer.analyze(menu_items)
print(f"Stars: {[i.name for i in result.stars]}")  # High profit, high sales
print(f"Dogs: {[i.name for i in result.dogs]}")    # Consider removing

# Break-even — how many covers do you need?
breakeven = BreakevenCalculator.calculate(
    fixed_costs=45000,      # Monthly rent, insurance, etc.
    variable_cost_pct=35,   # Food + labor as % of revenue
    avg_check=42,
)
print(f"Break-even: ${breakeven.breakeven_revenue:,.0f}/month ({breakeven.breakeven_covers} covers)")

# Tip Credit — are you claiming FICA credits?
from fiscalpilot.analyzers.tip_credit import TippedEmployee
employees = [
    TippedEmployee(name="Maria", hours_worked=160, tips_received=2800, cash_wage=2.13),
    TippedEmployee(name="Jake", hours_worked=140, tips_received=2100, cash_wage=2.13),
]
credit = TipCreditCalculator.calculate(employees, state="TX")
print(f"Monthly tip credit: ${credit.total_credit:,.2f}")
print(f"Annual projection: ${credit.annual_projection:,.2f}")

# Delivery ROI — is DoorDash worth it?
orders = [
    DeliveryOrderData(platform="doordash", gross_revenue=45, food_cost=12, order_count=150),
    DeliveryOrderData(platform="ubereats", gross_revenue=42, food_cost=11, order_count=80),
]
roi = DeliveryROIAnalyzer.analyze(orders, dine_in_margin=65)
for platform in roi.platforms:
    print(f"{platform.platform}: {platform.effective_margin:.1f}% margin (gap: {platform.margin_gap:+.1f}%)")
```

### Square POS Connection

```python
from fiscalpilot.connectors import SquarePOSConnector

connector = SquarePOSConnector(
    access_token="sq0atp-xxxxx",  # From Square Developer Dashboard
    sandbox=False,
)

# Pull all financial data
dataset = await connector.pull()

# Get daily summary
summary = await connector.get_daily_summary("2026-02-27")
print(f"Today: ${summary['gross_sales']:,.2f} gross, {summary['transaction_count']} txns")

# Get menu item sales
item_sales = await connector.get_item_sales(days_back=30)
for item in item_sales[:5]:
    print(f"  {item['name']}: {item['quantity_sold']} sold, ${item['total_revenue']:,.2f}")
```

---

## 🧠 How It Works

FiscalPilot uses a **multi-agent architecture** with an **execution pipeline**. Agents don't just find opportunities — they propose specific actions, route them through approval, and execute them.

```
                         ┌──────────────────┐
                         │    FiscalPilot    │
                         │   (Coordinator)   │
                         └────────┬─────────┘
                                  │
           ┌──────────────────────┼──────────────────────┐
           │                      │                      │
           ▼                      ▼                      ▼
   ┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
   │     Data     │     │  Intelligence │     │    Specialist    │
   │  Connectors  │     │   Engines    │     │     Agents       │
   └──────┬───────┘     └──────┬───────┘     └────────┬─────────┘
          │                    │                      │
   ┌──────┼──────┐      ┌─────┼─────┐        ┌──────┼──────┐
   │CSV  SQL  QB │      │Benford    │        │Optimizer  │
   │Xero Plaid...│      │Anomaly    │        │Revenue    │
   └─────────────┘      │Benchmark  │        │Tax Advisor│
                        │Cashflow   │        │Cost Mgr   │
                        │Tax Engine │        │Vendor Mgr │
                        └───────────┘        └───────────┘
                                  │
                                  ▼
                      ┌──────────────────┐
                      │ Action Proposals │← Dollar-quantified, specific
                      └────────┬─────────┘
                               │
                      ┌────────▼─────────┐
                      │  Approval Gate   │← Human-in-the-loop
                      │  (You decide)    │
                      └────────┬─────────┘
                               │
                      ┌────────▼─────────┐
                      │ Execution Engine │← Pluggable executors
                      │  (Acts on your   │   with dry-run, rollback,
                      │   behalf)        │   and full audit trail
                      └────────┬─────────┘
                               │
                      ┌────────▼─────────┐
                      │   📊 Report +    │
                      │   Action Log     │
                      └──────────────────┘
```

### Pipeline: Analyze → Propose → Approve → Execute

1. **Connectors** pull data from your financial systems (CSV, QuickBooks, Xero, SQL, Plaid, etc.)
2. **Intelligence Engines** run pure-computation analysis (no LLM needed):
   - 📐 **Benford's Law** — Chi-squared test, MAD scoring, per-vendor digit analysis
   - 📈 **Anomaly Detection** — Z-score, IQR, time-series deviation tracking
   - 🏭 **Industry Benchmarks** — Compare spend ratios against 13 industry profiles
   - 💰 **Cash Flow Forecast** — Exponential smoothing, runway, seasonal patterns
   - 🧾 **Tax Optimizer** — Miscategorized deductions, Section 179, entity structure
3. **Specialist Agents** run in parallel (LLM-powered):
   - 💡 **Cost Optimizer** — Finds savings in subscriptions, services, and operations
   - 🛡️ **Risk Detector** — Identifies anomalous payments, duplicate transactions, policy gaps
   - 📈 **Margin Optimizer** — Finds pricing and revenue mix improvements
   - 💰 **Revenue Analyzer** — Detects growth opportunities and billing gaps
   - 🏪 **Vendor Manager** — Audits vendor relationships, renegotiation opportunities
   - 🧾 **Tax Advisor** — Surfaces missed deductions, credits, and entity strategies
4. **Action Proposals** — Each finding generates specific, executable actions with dollar estimates
5. **Approval Gate** — You review and approve. Nothing executes without consent.
6. **Execution Engine** — Approved actions are carried out with dry-run preview, rollback capability, and complete audit trail

---

## ⚡ Execution Engine

> **Most financial tools stop at "here's what we found." FiscalPilot keeps going.**

The execution engine turns findings into actions. Instead of printing "you have a duplicate payment" and expecting you to fix it, FiscalPilot proposes: *"Cancel duplicate payment #4821 to Sysco Foods for $1,400. Mark original payment #4819 as retained. Notify AP team."*

### How it works

```python
# After analysis, review proposed actions
report = await pilot.audit(company)

for action in report.proposed_actions:
    print(f"""
    Action: {action.title}
    Type:   {action.action_type}
    Saves:  ${action.estimated_savings:,.2f}
    Level:  {action.approval_level}   # GREEN / YELLOW / RED / CRITICAL
    Steps:  {action.steps}
    """)

# Approve specific actions
pilot.approve(["act_001", "act_002", "act_005"])

# Execute with dry-run first
results = await pilot.execute(dry_run=True)   # Preview what would happen
results = await pilot.execute(dry_run=False)  # Actually do it

# Every action is logged immutably
for r in results:
    print(f"{r.action_id}: {r.status} — {r.summary}")
```

### Tiered Autonomy — You Control the Trust Level

Not all actions are equal. Categorizing an expense is low-risk. Canceling a subscription is significant. Changing payroll is critical. FiscalPilot uses **tiered autonomy** so you control exactly what happens automatically:

| Level | Risk | What happens | Examples |
|-------|------|--------------|----------|
| 🟢 **Green** | Low | Auto-executes silently | Categorize expense, tag transaction, generate report |
| 🟡 **Yellow** | Medium | Executes, then notifies you | Send payment reminder, bulk-update categories, flag for review |
| 🔴 **Red** | High | Waits for your approval | Cancel subscription, pay invoice, contact vendor |
| ⚫ **Critical** | Very High | Requires multi-party approval | Modify payroll, change tax filing, large transfers |

You configure the autonomy level per action type. Start conservative (everything requires approval), then grant more trust as you see fit. **Progressive trust, not blind automation.**

### Built-in Safety

- **Dry-run mode** — Preview every action before it touches anything
- **Rollback capability** — Undo actions when possible (e.g., restore a category change)
- **Immutable audit trail** — Every action, approval, and execution is logged with timestamp, actor, and outcome
- **Rate limiting** — Prevent runaway execution (max actions per hour/day)
- **Scope boundaries** — Actions are sandboxed to their financial system; no lateral movement

---

## 🛡️ Human-in-the-Loop

FiscalPilot is built on a core principle: **AI proposes, humans decide.**

This isn't a checkbox feature — it's the architecture. Every action flows through an approval gate before execution. The system is designed so that:

1. **Nothing executes by default** — `require_approval: true` out of the box
2. **You see exactly what will happen** — Every proposed action shows the specific steps, affected accounts, and dollar impact
3. **You approve individually or in bulk** — Review each action, or approve a category of low-risk actions
4. **You can revoke trust** — Downgrade any action type's autonomy level at any time
5. **Everything is logged** — Full audit trail for compliance, tax, and peace of mind

### Approval Workflow

```
Finding: "Unused Slack subscription — 3 seats inactive for 6+ months"
    │
    ▼
Proposed Action: "Reduce Slack plan from 25 to 22 seats"
    │   Saves: $1,080/year
    │   Level: RED (requires approval)
    │   Steps:
    │     1. Log into Slack admin
    │     2. Deactivate seats: jsmith, mwilson, klee
    │     3. Downgrade plan from 25 → 22
    │     4. Confirm billing change
    │
    ▼
You: ✅ "Approved" / ❌ "Rejected" / ✏️ "Modify: keep klee, only remove 2"
    │
    ▼
Execution: Carries out approved version with full audit log
```

---

## 🔌 Connectors

| Connector | Status | Auth | Install |
|-----------|--------|------|---------|
| **CSV** | ✅ Ready | File | Built-in |
| **Excel** | ✅ Ready | File | Built-in |
| **SQL** (PostgreSQL, MySQL, SQLite) | ✅ Ready | Connection string | Built-in |
| **QuickBooks Online** | ✅ Ready | OAuth2 + PKCE | Built-in |
| **Xero** | ✅ Ready | OAuth2 + PKCE | Built-in |
| **Plaid** (bank data) | ✅ Ready | Plaid Link | Built-in |
| **Square** (POS) | ✅ Ready | Access Token | Built-in |
| **SAP** | 🗓️ Planned | — | — |
| **NetSuite** | 🗓️ Planned | — | — |
| **FreshBooks** | 🗓️ Planned | — | — |
| **Stripe** | 🗓️ Planned | — | — |
| **Wave** | 🗓️ Planned | — | — |

### Connect to Accounting Platforms

```bash
# QuickBooks
fp connect quickbooks

# Xero
fp connect xero

# Plaid (bank connections)
fp connect plaid

# Square POS
fp connect square

# Check what's connected
fp connections
```

### Build Your Own Connector

```python
from fiscalpilot.connectors.base import BaseConnector
from fiscalpilot.models.financial import FinancialDataset

class MyERPConnector(BaseConnector):
    name = "my_erp"
    description = "Pull data from My Custom ERP"

    async def pull(self, company):
        transactions = fetch_from_erp()
        return FinancialDataset(transactions=transactions)

    async def validate_credentials(self):
        return True
```

---

## 🍽️ Restaurant Industry — Complete Solution

FiscalPilot's first **fully production-ready industry package**. Built specifically for food service businesses with industry-standard KPIs, QuickBooks integration, and actionable insights.

### Restaurant KPI Dashboard

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                     🍽️  JOE'S DINER — FINANCIAL HEALTH                        ║
║                          Health Grade: A (87/100)                             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ┌─────────────────────────────────────────────────────────────────────┐     ║
║  │ KEY PERFORMANCE INDICATORS                                          │     ║
║  ├─────────────────────────────────────────────────────────────────────┤     ║
║  │                                                                     │     ║
║  │ Food Cost %      [████████░░░░░░░░░░░░]  29.1%   ✅ HEALTHY         │     ║
║  │                  Target: 28-32%  │  Industry: 30%                   │     ║
║  │                                                                     │     ║
║  │ Labor Cost %     [███████████░░░░░░░░░]  33.2%   ⚠️  WARNING        │     ║
║  │                  Target: 28-32%  │  Industry: 30%                   │     ║
║  │                                                                     │     ║
║  │ Prime Cost %     [████████████████░░░░]  62.3%   ✅ HEALTHY         │     ║
║  │                  Target: 55-65%  │  Industry: 62%                   │     ║
║  │                                                                     │     ║
║  │ Occupancy %      [████░░░░░░░░░░░░░░░░]   7.8%   ✅ HEALTHY         │     ║
║  │                  Target: 6-10%   │  Industry: 8%                    │     ║
║  │                                                                     │     ║
║  │ Net Margin       [██████░░░░░░░░░░░░░░]   6.2%   ✅ HEALTHY         │     ║
║  │                  Target: 3-6%    │  Industry: 5%                    │     ║
║  └─────────────────────────────────────────────────────────────────────┘     ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

### Restaurant Architecture

```
                    ┌────────────────────────────────────┐
                    │      🍽️ Restaurant Analysis        │
                    │         fiscalpilot restaurant     │
                    └─────────────────┬──────────────────┘
                                      │
            ┌─────────────────────────┼─────────────────────────┐
            │                         │                         │
            ▼                         ▼                         ▼
    ┌───────────────┐        ┌───────────────┐        ┌───────────────┐
    │   Data Input  │        │   KPI Engine  │        │  Intelligence │
    └───────┬───────┘        └───────┬───────┘        └───────┬───────┘
            │                        │                        │
    ┌───────┴───────┐        ┌───────┴───────┐        ┌───────┴───────┐
    │ • QuickBooks  │        │ • Food Cost % │        │ • Anomaly     │
    │ • Square POS  │        │ • Labor Cost  │        │ • Benford's   │
    │ • Toast POS   │        │ • Prime Cost  │        │ • Benchmarks  │
    │ • CSV Export  │        │ • Occupancy   │        │ • Cash Flow   │
    │ • Bank (Plaid)│        │ • Net Margin  │        │ • Tax Savings │
    └───────────────┘        └───────────────┘        └───────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                 │
                    ▼                 ▼                 ▼
            ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
            │  Critical   │   │   Warnings  │   │ Opportuni-  │
            │   Alerts    │   │  & Actions  │   │    ties     │
            │   🚨        │   │   ⚠️         │   │   💡        │
            └─────────────┘   └─────────────┘   └─────────────┘
```

### QuickBooks Integration — 80+ Restaurant Mappings

FiscalPilot automatically maps QuickBooks accounts to restaurant cost categories:

| QuickBooks Account | → FiscalPilot Category | Industry Benchmark |
|:-------------------|:-----------------------|:-------------------|
| Cost of Goods Sold | `INVENTORY` (Food Cost) | 28-32% |
| Food Purchases | `INVENTORY` | — |
| Kitchen Wages | `PAYROLL` (Labor Cost) | 28-32% |
| Server Wages | `PAYROLL` | — |
| Bar Wages | `PAYROLL` | — |
| Beverage Costs | `INVENTORY` | 18-24% |
| Liquor Purchases | `INVENTORY` | — |
| Rent - Restaurant | `RENT` (Occupancy) | 6-10% |
| Utility Expense | `UTILITIES` | — |
| **+ 70 more...** | | |

### Get Started in 60 Seconds

**Option 1: Quick CSV scan**
```bash
# Install
pip install fiscalpilot

# Run restaurant analysis
fiscalpilot restaurant --csv transactions.csv --company "Joe's Diner" --revenue 850000
```

**Option 2: Connect QuickBooks**
```bash
# Interactive OAuth wizard
fiscalpilot connect quickbooks

# Then run industry-specific analysis
fiscalpilot restaurant --quickbooks
```

**Option 3: Python API**
```python
from fiscalpilot.analyzers.restaurant import RestaurantAnalyzer
from fiscalpilot.connectors.csv_connector import CSVConnector
from fiscalpilot.models.company import CompanyProfile, Industry, CompanySize

# Setup
company = CompanyProfile(
    name="Joe's Diner",
    industry=Industry.RESTAURANT,
    size=CompanySize.SMALL,
    annual_revenue=850_000,
)

connector = CSVConnector(file_path="transactions.csv")
dataset = await connector.pull(company)

# Analyze
result = RestaurantAnalyzer.analyze(dataset, annual_revenue=850_000)

# View results
print(f"Health Grade: {result.health_grade} ({result.health_score}/100)")
for kpi in result.kpis:
    print(f"  {kpi.display_name}: {kpi.actual:.1f}% — {kpi.severity.value}")
```

### Sample Output

```
🍽️  Restaurant Financial Health Report
============================================================
Health Grade: B (78/100)

Financials:
  Annual Revenue (Est):  $850,000.00
  Total Expenses (Est):  $799,000.00
  Net Operating Income:  $51,000.00

Key Performance Indicators:
────────────────────────────────────────────────────────────
  Food Cost %           29.1%  ✅ healthy     Target: 28-32%
  Labor Cost %          33.2%  ⚠️  warning     Target: 28-32%
  Prime Cost %          62.3%  ✅ healthy     Target: 55-65%
  Occupancy Cost %       7.8%  ✅ healthy     Target: 6-10%
  Net Operating Margin   6.0%  ✅ healthy     Target: 3-6%

🚨 Critical Alerts:
  Labor Cost % at 33.2% — above target range. Review scheduling.

💡 Opportunities:
  ⚠️ Labor Cost %: 33.2% — Optimize shift scheduling. Cross-train staff.
  💡 Marketing spend very low — consider customer acquisition investment.
  ✅ Food Cost % and Occupancy % performing well!
```

### Restaurant Industry Benchmarks

| KPI | Target | Warning | Critical | What It Means |
|:----|:------:|:-------:|:--------:|:--------------|
| **Food Cost %** | 28-32% | >35% | >38% | Cost of ingredients ÷ revenue |
| **Labor Cost %** | 28-32% | >35% | >38% | All wages & benefits ÷ revenue |
| **Prime Cost %** | 55-65% | >68% | >72% | Food + labor (most critical) |
| **Beverage Cost %** | 18-24% | >26% | >28% | Bar/drink cost ÷ bar revenue |
| **Occupancy Cost %** | 6-10% | >11% | >12% | Rent + utilities ÷ revenue |
| **Net Margin** | 3-6% | <2% | <0% | Bottom line profitability |

---

## 📋 Real Examples

Real scenarios for real businesses. Not toy demos — these are the exact kinds of findings and actions FiscalPilot produces for each business type.

### 🧑‍💻 Solo Freelancer — Maria, UX Designer ($95K/year)

Maria is a freelance UX designer. She uses FiscalPilot connected to her Plaid bank account and a CSV of invoices.

```bash
fp scan --plaid --csv invoices.csv --company "Maria Chen Design" --industry professional_services
```

| Finding | Savings | Action |
|---------|---------|--------|
| Home office deduction not claimed (190 sq ft) | $2,400/yr | **Auto-calculate** deduction, add to tax prep file |
| 3 clients with overdue invoices (avg 47 days) | $8,200 cash flow | **Send reminder emails** with customizable templates |
| Adobe Creative Cloud on monthly billing | $60/yr | **Compare rates** → suggest switching to annual plan |
| Quarterly tax estimates off by ~$1,200 | Avoid penalty | **Recalculate** estimates based on YTD income |
| Business meals not properly categorized (23 transactions) | $340/yr tax | **Recategorize** transactions in accounting system |
| SEP IRA contribution room unused | $4,800 tax savings | **Flag for financial advisor** with calculation |

### 🍕 Restaurant — Joe's Diner ($850K revenue, 15 employees)

Joe runs a sit-down restaurant. Connected to QuickBooks + POS system CSV.

```bash
fp audit --quickbooks --csv pos_data.csv --company "Joe's Diner" --industry restaurant
```

| Finding | Savings | Action |
|---------|---------|--------|
| Food cost ratio at 38% (benchmark: 28-32%) | $51,000/yr | **Generate supplier price comparison** report, draft RFQ to 3 alternative suppliers |
| Duplicate payments to Sysco Foods (months: Mar, Jun) | $2,800 | **Flag duplicates** in QuickBooks, draft vendor credit requests |
| Unused Toast feature (online ordering module) | $1,200/yr | **Review usage data** → propose plan downgrade |
| POS voids higher on Friday night shift (3.2x avg) | $8,400/yr | **Generate staff analysis** report, recommend review of shift procedures |
| Liquor license renewal 45 days out — not budgeted | Avoid lapse | **Create calendar reminder** + budget allocation |
| Employee meals not tracked for tax deduction | $2,100/yr | **Set up meal tracking** category in QuickBooks |

### 🏥 Dental Practice — Riverside Dental ($1.2M revenue, 8 staff)

Dr. Patel runs a dental practice. Connected to practice management CSV + QuickBooks.

| Finding | Savings | Action |
|---------|---------|--------|
| Supply costs 22% above dental benchmark | $18,000/yr | **Run vendor benchmarking**, generate RFQ for top 5 supply categories |
| 12% of insurance claims denied on first submission | $14,400/yr | **Analyze denial codes**, identify top 3 preventable categories |
| X-ray machine lease vs. purchase analysis | $4,200/yr | **Build lease-vs-buy model** with 5-year NPV comparison |
| Staff overtime averaging 8 hrs/week above budget | $12,000/yr | **Generate schedule optimization** model based on appointment patterns |
| Section 179 deduction available on new CEREC machine | $8,500 one-time | **Calculate deduction**, prepare documentation for CPA |
| Patient no-show rate creating unbilled gaps | $22,000/yr | **Draft automated reminder** workflow for 48hr + 2hr pre-appointment |

### 💻 SaaS Startup — CloudSync ($5M ARR, 40 employees)

A B2B SaaS company with $5M ARR. Connected to Xero + Plaid + CSV exports from internal tools.

```bash
fp audit --config saas_config.yaml --company "CloudSync" --industry saas
```

| Finding | Savings | Action |
|---------|---------|--------|
| AWS spend increased 34% QoQ but MAU grew 12% | $48,000/yr | **Break down AWS costs** by service, identify over-provisioned resources |
| 7 SaaS tools with overlapping functionality | $22,000/yr | **Map feature overlap**, propose consolidation plan with migration timeline |
| Rev rec not ASC 606 compliant (3 multi-year contracts) | Audit risk | **Reclassify revenue** entries, generate compliance report for auditor |
| R&D tax credit underutilized (~$180K eligible) | $180,000 | **Tag qualifying expenses**, generate R&D credit documentation |
| Contractor payments missing W-9s (4 vendors) | Compliance risk | **Draft W-9 request emails**, set compliance flag in AP workflow |
| CAC payback period drifting (now 18 months, was 11) | Strategic alert | **Build unit economics dashboard** with cohort analysis |

### 🏗️ Construction Company — Apex Builders ($15M revenue, 60 employees)

A general contractor. Connected to QuickBooks + project management CSV exports.

| Finding | Savings | Action |
|---------|---------|--------|
| Material costs 18% above industry benchmark on concrete | $120,000/yr | **Aggregate purchase volumes** across projects, draft bulk-buy RFP |
| Retainage receivable aging — $340K over 120 days | Cash flow | **Generate retainage collection** schedule, draft lien notices |
| 3 subcontractors without current COI on file | Liability risk | **Send COI request** emails with 30-day compliance deadline |
| Equipment idle time averaging 23% across fleet | $45,000/yr | **Build utilization report** by asset, propose fleet optimization |
| Workers' comp classification may be incorrect (2 roles) | $18,000/yr | **Audit classification codes**, prepare reclassification request |
| Project #2847 trending 12% over budget at 60% completion | $90,000 exposure | **Generate variance report** with line-item analysis, flag for PM review |

### 🏭 Manufacturing Enterprise — Precision Parts Inc ($500M revenue, 2,500 employees)

Large manufacturer with multi-entity operations. Full ERP integration.

```python
company = CompanyProfile(
    name="Precision Parts Inc",
    industry=Industry.MANUFACTURING,
    size=CompanySize.ENTERPRISE,
    annual_revenue=500_000_000,
    employee_count=2500,
)
report = await pilot.audit(company)
# Typical result: 200+ findings, $2.4M in addressable savings
```

| Finding | Savings | Action |
|---------|---------|--------|
| Intercompany pricing creating tax inefficiency across 3 entities | $340,000/yr | **Run transfer pricing analysis**, generate recommended adjustments |
| Duplicate vendor master records (47 vendors, 3 entities) | Process efficiency | **Merge vendor records**, establish golden record, apply dedup rules |
| Raw material price variance trending unfavorable (steel +8%) | $480,000/yr | **Model hedging strategies**, generate RFP for forward contracts |
| AP discount capture rate at 34% (benchmark: 65%+) | $290,000/yr | **Prioritize invoices** by discount value, recommend payment acceleration |
| 12 lease agreements hitting ASC 842 threshold, not on balance sheet | Compliance risk | **Classify leases**, generate journal entries for balance sheet recognition |
| Energy costs 15% above industry benchmark in Plant 3 | $120,000/yr | **Benchmark utility rates** by plant, generate energy audit recommendations |

---

## 🌍 How FiscalPilot Compares

The financial AI landscape is evolving fast. Here's where FiscalPilot fits:

| Feature | FiscalPilot | Ramp | Stampli | Vic.ai | Docyt |
|---------|:-----------:|:----:|:-------:|:------:|:-----:|
| Open source | ✅ | ❌ | ❌ | ❌ | ❌ |
| Self-hosted / data stays local | ✅ | ❌ | ❌ | ❌ | ❌ |
| Multi-industry | ✅ | Finance only | AP only | AP only | Bookkeeping |
| Analysis engine | ✅ | ✅ | ⚠️ | ✅ | ✅ |
| Execution engine | ✅ | ✅ | ✅ | ✅ | ⚠️ |
| Human-in-the-loop | ✅ | ⚠️ | ✅ | ⚠️ | ❌ |
| Any LLM (local or cloud) | ✅ | ❌ | ❌ | ❌ | ❌ |
| Custom agents/connectors | ✅ | ❌ | ❌ | ❌ | ❌ |
| Free | ✅ | Freemium | ❌ | ❌ | ❌ |

**FiscalPilot is the only open-source project that combines financial analysis with execution capabilities.** Existing open-source agent frameworks (LangChain, CrewAI, AutoGen) can build analysis agents, but none include financial execution, approval workflows, or industry-specific knowledge. That's our whitespace.

### Multi-LLM Support

FiscalPilot supports **any LLM provider** via [litellm](https://github.com/BerriAI/litellm):

```yaml
# OpenAI
llm:
  model: "gpt-4o"

# Anthropic
llm:
  model: "claude-sonnet-4-20250514"

# Local (Ollama) — 100% private
llm:
  model: "ollama/llama3.1:70b"
  api_base: "http://localhost:11434"

# Azure OpenAI
llm:
  model: "azure/gpt-4o"
  api_base: "https://your-resource.openai.azure.com/"
```

---

## 🗺️ Roadmap

### v0.1 — Foundation ✅
- [x] Core agent architecture
- [x] CSV/Excel/SQL connectors
- [x] 6 specialist agents
- [x] Markdown report export
- [x] CLI interface
- [x] Multi-LLM support

### v0.2 — Integrations ✅
- [x] QuickBooks Online full integration
- [x] Xero full integration
- [x] Plaid bank sync
- [ ] Stripe payment data
- [ ] PDF/receipt OCR scanning

### v0.3 — Intelligence ✅
- [x] Benford's Law statistical analysis (chi-squared, MAD, per-vendor)
- [x] Time-series anomaly detection (Z-score, IQR, seasonal)
- [x] Industry benchmark database (13 industries, grading A–F)
- [x] Cash flow forecasting (exponential smoothing, runway, seasonal)
- [x] Tax optimization engine (Section 179, S-Corp, SEP IRA, meals)

### v0.4 — Execution & Actions ✅
- [x] Execution engine with pluggable action executors
- [x] Human-in-the-loop approval system with tiered autonomy
- [x] Action proposal pipeline (findings → actions → approval → execution)
- [x] Dry-run mode with preview and rollback
- [x] Immutable audit trail for all actions
- [x] **Restaurant Industry Package** — complete vertical solution:
  - RestaurantAgent (KPI + LLM hybrid analysis)
  - Square POS connector (payments, items, daily summaries)
  - RestaurantAnalyzer (15+ industry KPIs)
  - QuickBooks class/item mappings for food service
- [x] **Interactive HTML Reports** — Chart.js visualizations:
  - Severity distribution doughnut chart
  - Savings by category bar chart
  - Health score gauge
  - Responsive design with CSS variables
- [x] 300 comprehensive tests
- [ ] Email/Slack notification executors
- [ ] QuickBooks/Xero write-back executors

### v0.5 — Dashboard & API
- [ ] Web dashboard UI
- [ ] REST API server mode
- [ ] Scheduled automated analysis
- [ ] Real-time monitoring & alerts
- [ ] Multi-user with RBAC

### v0.6 — Enterprise
- [ ] Multi-entity consolidation
- [ ] SAP / NetSuite / Oracle connectors
- [ ] Custom agent builder (YAML-defined agents)
- [ ] SOC 2 compliance mode
- [ ] Webhook integrations

### v1.0 — Production
- [ ] Plugin marketplace
- [ ] Mobile companion app
- [ ] Industry-specific agent packs
- [ ] Continuous monitoring mode
- [ ] Self-improving recommendations (learns from approvals/rejections)

---

## 🤝 Contributing

**We need you!** FiscalPilot is designed for community-driven development. Every connector, executor, agent, and improvement makes this better for every business.

### Good First Issues

| Area | Task | Difficulty |
|------|------|-----------|
| 🔌 Connectors | Add Stripe connector | Easy |
| 🔌 Connectors | Add FreshBooks connector | Easy |
| 🔌 Connectors | Add NetSuite connector | Medium |
| ⚡ Executors | Email notification executor | Easy |
| ⚡ Executors | Slack notification executor | Easy |
| ⚡ Executors | QuickBooks write-back executor | Medium |
| 🧠 Intelligence | Extend benchmark database with more industries | Easy |
| 🧠 Agents | Add subscription optimization agent | Easy |
| 🧠 Agents | Add payroll analysis agent | Medium |
| 📊 Reports | HTML report with charts | Medium |
| 📊 Reports | PDF export | Easy |
| 📱 UI | Web dashboard | Hard |
| 🧪 Tests | Add integration tests | Easy |
| 📖 Docs | Industry-specific playbooks | Easy |

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide.

### Quick Contribution

```bash
# Fork and clone
git clone https://github.com/YOUR_USERNAME/fiscalpilot.git
cd fiscalpilot

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Make your changes, then submit a PR!
```

---

## 📄 License

Apache 2.0 — Use it freely in your business, modify it, contribute back.

---

<div align="center">

**⭐ Star us on GitHub — it helps more businesses discover their AI CFO**

[GitHub](https://github.com/meetpandya27/FiscalPilot) · [Discord](https://discord.gg/fiscalpilot) · [Documentation](https://fiscalpilot.dev) · [Twitter](https://twitter.com/fiscalpilot)

*The open-source AI CFO. Built with ❤️ by the FiscalPilot community.*

</div>
