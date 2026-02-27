# Changelog

All notable changes to FiscalPilot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-02-27

### Added
- **QuickBooks Online** full production integration — OAuth2, paginated QBO Query API, parallel entity fetching (purchases, deposits, invoices, bills, account balances), sandbox/production support
- **Xero** full production integration — OAuth2 with tenant auto-detection, rate limiting (429/Retry-After), .NET JSON date parsing, bank transactions, invoices, trial balance report
- **Plaid** full production integration — cursor-based transaction sync, multi-access-token support, Plaid Link flow (create/exchange tokens), personal_finance_category mapping, sandbox/development/production environments
- Shared **OAuth2 token manager** (`fiscalpilot.auth`) — disk-based token persistence with 0600 permissions, automatic refresh with 5-minute buffer, authorization code exchange, authorization URL generation
- 50 new tests for connector integrations (86 total tests)

### Changed
- Replaced QuickBooks, Xero, and Plaid scaffold connectors with full httpx-based implementations (no third-party SDK wrappers)
- Removed `python-quickbooks`, `xero-python`, `plaid-python` optional dependencies — all connectors now use `httpx` (core dependency)
- Updated project URLs to point to `meetpandya27/FiscalPilot`

### Fixed
- Plaid removed transaction IDs now correctly match prefixed Transaction model IDs

## [0.1.0] - 2026-02-26

### Added
- Core multi-agent architecture with Coordinator orchestration
- 6 specialist agents: Waste Detector, Fraud Detector, Margin Optimizer, Cost Cutter, Revenue Analyzer, Vendor Auditor
- CSV, Excel, and SQL connectors (ready to use)
- QuickBooks, Xero, and Plaid connector scaffolds (community contributions welcome)
- Plugin-style connector system for custom integrations
- CLI interface (`fiscalpilot` / `fp` commands)
- Markdown report exporter
- JSON report exporter
- Multi-LLM support via litellm (OpenAI, Anthropic, Ollama, Azure, etc.)
- Privacy-first design: can run 100% locally with no external API calls
- Pydantic-based data models for type safety
- Company profiles with industry and size classification
- Comprehensive configuration via YAML + environment variables
- Docker support
- GitHub Actions CI/CD pipeline
