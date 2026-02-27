<div align="center">

# 🛫 FiscalPilot

### The Open-Source AI Financial Copilot

**Find waste. Detect fraud. Cut costs. Maximize margins.**  
**Your AI-powered CFO that runs on YOUR infrastructure.**

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![GitHub Stars](https://img.shields.io/github/stars/fiscalpilot/fiscalpilot?style=social)](https://github.com/fiscalpilot/fiscalpilot)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Discord](https://img.shields.io/badge/Discord-Join%20Community-7289DA?logo=discord&logoColor=white)](https://discord.gg/fiscalpilot)

<br />

[**Quickstart**](#-quickstart) · [**How It Works**](#-how-it-works) · [**Connectors**](#-connectors) · [**Examples**](#-examples) · [**Contributing**](#-contributing) · [**Roadmap**](#-roadmap)

<br />

<img src="docs/assets/hero.png" alt="FiscalPilot" width="700" />

</div>

---

## 🤔 What is FiscalPilot?

FiscalPilot is an **open-source AI agent** that acts as your company's automated Chief Financial Officer. It connects to your financial systems, analyzes every transaction, and finds:

- 💸 **Waste** — Unused subscriptions, duplicate services, over-provisioned resources
- 🚨 **Fraud** — Duplicate payments, ghost vendors, expense anomalies
- 📉 **Revenue Leakage** — Unbilled work, missed invoices, pricing gaps
- 📈 **Margin Improvements** — Pricing optimization, COGS reduction, revenue mix
- ✂️ **Cost Reductions** — Vendor renegotiation, consolidation, tax optimization
- 🔍 **Vendor Issues** — Overcharges, lock-in risk, market rate deviations

### Works for ANY business size

| 🍕 Restaurant | 🏪 Retail Shop | 💻 SaaS Startup | 🏭 Enterprise |
|---|---|---|---|
| Find food waste | Optimize inventory costs | Audit SaaS stack | Detect fraud at scale |
| Cut supplier costs | Reduce shrinkage | Reduce cloud spend | Consolidate vendors |
| Improve menu margins | Negotiate vendor terms | Optimize pricing | Compliance monitoring |

### 🔒 Privacy First

FiscalPilot runs **entirely on your infrastructure**. No data leaves your systems. Use local LLMs (Ollama, vLLM) for complete privacy, or connect to any cloud provider.

---

## ⚡ Quickstart

### Install

```bash
pip install fiscalpilot
```

### Scan a CSV in 30 seconds

```bash
# Scan your transaction data
fiscalpilot scan --csv transactions.csv --company "Joe's Diner" --industry restaurant

# Or use the short alias
fp scan --csv data.csv --company "Acme Corp" --industry saas
```

### Use as a Python library

```python
import asyncio
from fiscalpilot import FiscalPilot
from fiscalpilot.models.company import CompanyProfile, Industry, CompanySize

# Define your company
company = CompanyProfile(
    name="Joe's Diner",
    industry=Industry.RESTAURANT,
    size=CompanySize.SMALL,
    annual_revenue=850_000,
)

# Run the audit
pilot = FiscalPilot.from_config("fiscalpilot.yaml")
report = asyncio.run(pilot.audit(company))

# See results
print(f"Found {len(report.findings)} issues")
print(f"Potential savings: ${report.total_potential_savings:,.2f}")

# Export
report.to_markdown()  # → Markdown report
report.to_json()      # → JSON data
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

  # - type: sql
  #   credentials:
  #     connection_string: "postgresql://user:pass@localhost/mydb"
  #   options:
  #     query: "SELECT * FROM transactions WHERE date >= '2024-01-01'"

analyzers:
  waste_detection: true
  fraud_detection: true
  margin_optimization: true
  cost_reduction: true
  revenue_leakage: true
  vendor_analysis: true

security:
  local_only: false        # Set true to never send data externally
  encrypt_at_rest: true
  redact_pii: true
```

---

## 🧠 How It Works

FiscalPilot uses a **multi-agent architecture** where specialized AI agents work in parallel:

```
                    ┌─────────────────┐
                    │   FiscalPilot   │
                    │  (Orchestrator) │
                    └───────┬─────────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
              ▼             ▼             ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │  Data    │ │  Agent   │ │  Report  │
        │Connectors│ │  Engine  │ │Generator │
        └────┬─────┘ └────┬─────┘ └────┬─────┘
             │             │             │
    ┌────────┼───┐    ┌────┼────┐       │
    │  CSV   │SQL│    │Waste│   │       ▼
    │  Excel │QB │    │Fraud│...│   📊 Report
    │  Xero  │...│    │Margin   │   (MD/JSON/PDF)
    └────────┴───┘    └─────────┘
```

### Agent Pipeline

1. **Connectors** pull data from your financial systems (CSV, QuickBooks, Xero, SQL, Plaid, etc.)
2. **Coordinator Agent** distributes the data to specialist agents
3. **Specialist Agents** run in parallel:
   - 🗑️ **Waste Detector** — Finds unused subscriptions, duplicate services
   - 🔍 **Fraud Detector** — Identifies duplicate payments, suspicious patterns
   - 📈 **Margin Optimizer** — Finds pricing and revenue mix improvements
   - ✂️ **Cost Cutter** — Identifies vendor and operational savings
   - 💰 **Revenue Analyzer** — Detects leakage and growth opportunities
   - 🏪 **Vendor Auditor** — Audits vendor relationships and contracts
4. **Coordinator** deduplicates, ranks by impact, and generates the final report

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

## 🔌 Connectors

| Connector | Status | Install |
|-----------|--------|---------|
| **CSV** | ✅ Ready | Built-in |
| **Excel** | ✅ Ready | Built-in |
| **SQL** (PostgreSQL, MySQL, SQLite) | ✅ Ready | Built-in |
| **QuickBooks Online** | 🔧 Scaffold | `pip install fiscalpilot[quickbooks]` |
| **Xero** | 🔧 Scaffold | `pip install fiscalpilot[xero]` |
| **Plaid** (bank data) | 🔧 Scaffold | `pip install fiscalpilot[plaid]` |
| **SAP** | 🗓️ Planned | — |
| **NetSuite** | 🗓️ Planned | — |
| **FreshBooks** | 🗓️ Planned | — |
| **Stripe** | 🗓️ Planned | — |
| **Wave** | 🗓️ Planned | — |

### Build Your Own Connector

```python
from fiscalpilot.connectors.base import BaseConnector
from fiscalpilot.models.financial import FinancialDataset

class MyERPConnector(BaseConnector):
    name = "my_erp"
    description = "Pull data from My Custom ERP"

    async def pull(self, company):
        # Your integration logic here
        transactions = fetch_from_erp()
        return FinancialDataset(transactions=transactions)

    async def validate_credentials(self):
        return True
```

Register it in your config:

```yaml
connectors:
  - type: "my_package.MyERPConnector"
    credentials:
      api_key: "..."
```

---

## 📋 Examples

### Restaurant Owner ($850K revenue)

```bash
fp scan --csv restaurant_expenses.csv --company "Joe's Diner" --industry restaurant
```

<details>
<summary>📊 Sample Output</summary>

```
┌──────────────────────────────┐
│ 🛫 FiscalPilot — Quick Scan │
└──────────────────────────────┘

┌──────────────────────────────┐
│       Audit Summary          │
├──────────────────┬───────────┤
│ Total Findings   │        12 │
│ Critical Issues  │         2 │
│ Potential Savings│  $47,200  │
│ Health Score     │     72/100│
└──────────────────┴───────────┘

Top Findings:
  1. [CRITICAL] Duplicate food vendor payments — $8,400
  2. [HIGH] Unused POS software subscription — $3,600/yr
  3. [HIGH] Food cost ratio above benchmark — $12,000
  4. [MEDIUM] Better payment terms available — $2,400
  5. [MEDIUM] Insurance policy overlap — $1,800
```

</details>

### SaaS Company ($5M ARR)

```bash
fp audit --config saas_config.yaml --company "CloudTech" --industry saas
```

### Enterprise ($500M revenue)

```python
from fiscalpilot import FiscalPilot
from fiscalpilot.models.company import CompanyProfile, Industry, CompanySize

company = CompanyProfile(
    name="GlobalCorp",
    industry=Industry.MANUFACTURING,
    size=CompanySize.LARGE,
    annual_revenue=500_000_000,
    employee_count=2500,
)

pilot = FiscalPilot.from_config("enterprise_config.yaml")
report = await pilot.audit(company)

# Potential output: 200+ findings, $2.4M in savings
```

---

## 🗺️ Roadmap

### v0.1 — Foundation (Current)
- [x] Core agent architecture
- [x] CSV/Excel/SQL connectors
- [x] 6 specialist agents
- [x] Markdown report export
- [x] CLI interface
- [x] Multi-LLM support

### v0.2 — Integrations
- [ ] QuickBooks Online full integration
- [ ] Xero full integration
- [ ] Plaid bank sync
- [ ] Stripe payment data
- [ ] PDF/receipt OCR scanning
- [ ] HTML report with charts

### v0.3 — Intelligence
- [ ] Benford's Law statistical analysis
- [ ] Time-series anomaly detection
- [ ] Industry benchmark database
- [ ] Cash flow forecasting
- [ ] Tax optimization engine

### v0.4 — Enterprise
- [ ] Multi-tenant support
- [ ] Role-based access control
- [ ] Scheduled automated audits
- [ ] Dashboard UI (web)
- [ ] API server mode
- [ ] SAP / NetSuite / Oracle connectors

### v1.0 — Production
- [ ] SOC 2 compliance
- [ ] Audit trail logging
- [ ] Custom agent builder
- [ ] Plugin marketplace
- [ ] Mobile app

---

## 🤝 Contributing

**We need you!** FiscalPilot is designed for community-driven development. Every connector, analyzer, and improvement makes this better for every business.

### Good First Issues

| Area | Task | Difficulty |
|------|------|-----------|
| 🔌 Connectors | Implement QuickBooks full integration | Medium |
| 🔌 Connectors | Implement Xero full integration | Medium |
| 🔌 Connectors | Add Stripe connector | Easy |
| 🔌 Connectors | Add FreshBooks connector | Easy |
| 🧠 Agents | Add Benford's Law analysis to fraud detector | Medium |
| 🧠 Agents | Add subscription audit agent | Easy |
| 🧠 Agents | Add payroll analysis agent | Medium |
| 📊 Reports | HTML report with charts | Medium |
| 📊 Reports | PDF export | Easy |
| 📱 UI | Web dashboard | Hard |
| 🧪 Tests | Add integration tests | Easy |
| 📖 Docs | Industry-specific guides | Easy |

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

**⭐ Star us on GitHub — it helps more businesses discover FiscalPilot!**

[GitHub](https://github.com/fiscalpilot/fiscalpilot) · [Discord](https://discord.gg/fiscalpilot) · [Documentation](https://fiscalpilot.dev) · [Twitter](https://twitter.com/fiscalpilot)

*Built with ❤️ by the FiscalPilot community*

</div>
