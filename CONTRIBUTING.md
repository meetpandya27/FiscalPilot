# Contributing to FiscalPilot

Thank you for your interest in contributing to FiscalPilot! 🛫

Every contribution — whether it's a bug fix, new connector, improved analysis, or documentation — makes FiscalPilot better for every business.

## 🚀 Quick Start

```bash
# 1. Fork the repo on GitHub
# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/fiscalpilot.git
cd fiscalpilot

# 3. Install in development mode
pip install -e ".[dev,all]"

# 4. Set up pre-commit hooks
pre-commit install

# 5. Run tests to make sure everything works
pytest

# 6. Create a branch for your work
git checkout -b feat/my-awesome-feature
```

## 📋 What to Work On

### 🔌 Connectors (High Impact)

The more systems FiscalPilot connects to, the more businesses it helps. Connector contributions are the most impactful.

**How to build a connector:**

1. Create a new file: `src/fiscalpilot/connectors/my_connector.py`
2. Subclass `BaseConnector`
3. Implement `pull()` and `validate_credentials()`
4. Add to the registry in `connectors/registry.py`
5. Add tests in `tests/connectors/`

```python
from fiscalpilot.connectors.base import BaseConnector
from fiscalpilot.models.financial import FinancialDataset

class MyConnector(BaseConnector):
    name = "my_system"
    description = "Pull data from My System"

    async def pull(self, company):
        # Your integration logic
        return FinancialDataset(transactions=[...])

    async def validate_credentials(self):
        return True
```

**Needed connectors:**
- Stripe (payments)
- FreshBooks (accounting)
- Wave (small business)
- SAP (enterprise ERP)
- NetSuite (ERP)
- Sage (accounting)
- Shopify (ecommerce)
- Square (POS)

### 🧠 Agents (Medium Impact)

Agents are the AI brain. Each agent is a specialist that analyzes one aspect of finances.

**How to build an agent:**

1. Create a new file: `src/fiscalpilot/agents/my_agent.py`
2. Subclass `BaseAgent`
3. Implement `system_prompt`, `_build_prompt()`, `_parse_response()`
4. Register in the Coordinator

**Needed agents:**
- Subscription Audit Agent (SaaS stack analysis)
- Payroll Analysis Agent
- Tax Optimization Agent
- Cash Flow Forecasting Agent
- Compliance Check Agent

### 📊 Reports & Exporters

- HTML report with interactive charts
- PDF export
- Dashboard web UI

### 🧪 Tests

We use pytest. Tests live in `tests/`. Good areas for testing:
- Unit tests for models
- Connector tests with sample data
- Agent response parsing tests

## 🎨 Code Style

- We use **Ruff** for linting and formatting
- Type hints required (`mypy --strict`)
- Docstrings for all public functions
- Max line length: 100

```bash
# Lint
ruff check src/ tests/

# Type check
mypy src/

# Format
ruff format src/ tests/
```

## 📝 Commit Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add Stripe connector
fix: handle empty CSV files gracefully
docs: add restaurant industry guide
test: add fraud detector agent tests
refactor: simplify connector registry
```

## 🔄 Pull Request Process

1. Ensure tests pass: `pytest`
2. Ensure lint passes: `ruff check src/`
3. Ensure types pass: `mypy src/`
4. Write a clear PR description
5. Link to any related issues
6. Request review

## 🏗️ Architecture Overview

```
src/fiscalpilot/
├── __init__.py          # Package entry point
├── pilot.py             # Main orchestrator
├── config.py            # Configuration management
├── cli.py               # CLI interface
├── agents/              # AI agents
│   ├── base.py          # Base agent class
│   ├── coordinator.py   # Master coordinator
│   ├── waste_detector.py
│   ├── fraud_detector.py
│   ├── margin_optimizer.py
│   ├── cost_cutter.py
│   ├── revenue_analyzer.py
│   └── vendor_auditor.py
├── connectors/          # Data source connectors
│   ├── base.py          # Base connector class
│   ├── registry.py      # Connector discovery
│   ├── csv_connector.py
│   ├── excel_connector.py
│   ├── sql_connector.py
│   ├── quickbooks_connector.py
│   ├── xero_connector.py
│   └── plaid_connector.py
├── models/              # Data models
│   ├── company.py       # Company profile
│   ├── financial.py     # Transactions, invoices
│   └── report.py        # Audit report, findings
└── exporters/           # Report exporters
    └── markdown.py      # Markdown export
```

## 💬 Community

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: General questions and ideas
- **Discord**: Real-time chat and collaboration

## 📜 License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.

---

**Thank you for helping make financial optimization accessible to every business!** 🛫
