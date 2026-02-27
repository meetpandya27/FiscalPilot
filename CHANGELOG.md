# Changelog

All notable changes to FiscalPilot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.5.0] - 2026-02-27

### Added
- **Menu Engineering Analyzer** — BCG matrix classification for menu items:
  - Star/Plowhorse/Puzzle/Dog classification based on popularity + profitability
  - Per-item recommendations (feature, reprice, promote, remove)
  - Category-level summaries with food cost percentages
  - Potential profit increase estimation
  - 16 new tests
- **Break-even Calculator** — Know exactly when you stop losing money:
  - Revenue and covers needed to break even
  - Scenario modeling (best/worst/seasonal cases)
  - What-if analysis (price changes, cost reductions)
  - Actionable insights based on margin proximity
  - 15 new tests
- **FICA Tip Tax Credit Calculator** — Claim Section 45B credits:
  - Per-employee tip credit calculation
  - State minimum wage support (all 50 states)
  - Annualized projections
  - Compliance notes and Form 8846 guidance
  - 17 new tests
- **Delivery Platform ROI Analyzer** — Is DoorDash worth it?
  - Multi-platform comparison (DoorDash, UberEats, Grubhub, Direct)
  - True margin calculation after commissions + packaging
  - Dine-in vs delivery margin gap analysis
  - Direct ordering savings projection
  - Platform-specific recommendations
  - 27 new tests
- **CLI `fp restaurant` subcommand** — One-command restaurant analysis
- **RestaurantAgent new methods**: `analyze_menu()`, `calculate_breakeven()`, `estimate_tip_credit()`, `calculate_tip_credit_detailed()`, `analyze_delivery_roi()`, `quick_delivery_check()`
- **375 total passing tests** (was 300)

### Changed
- RestaurantAgent now integrates all 4 new analyzers
- Restaurant example (`examples/restaurant/run_scan.py`) updated with new feature demos
- README updated with restaurant-specific quickstart

## [0.4.1] - 2026-02-27

### Added
- **Restaurant Industry Package** — Complete vertical solution for food service businesses:
  - `RestaurantAgent` — AI-powered analysis combining pure-computation KPIs with LLM strategic recommendations
  - `SquarePOSConnector` — Full Square API integration for payments, menu items, and daily summaries
  - `RestaurantAnalyzer` — 15+ industry-specific KPIs (food cost %, labor %, prime cost, RevPASH, etc.)
  - QuickBooks class/item mappings for restaurant chart of accounts
  - Industry benchmarks (food ≤32%, labor ≤30%, prime ≤60%)
- **Interactive HTML Reports** — Beautiful, responsive report export with Chart.js visualizations:
  - Severity distribution doughnut chart
  - Savings by category horizontal bar chart  
  - Health score circular gauge
  - Finding detail cards with recommendations
  - Action items table and proposed actions section
  - Fully responsive CSS with modern design
- 41 new tests for HTML exporter
- 44 new tests for restaurant package (RestaurantAgent + SquarePOSConnector)
- **300 total passing tests**

### Changed
- Exporters package now exports both `render_markdown` and `render_html`
- Connector registry includes Square POS
- Agent registry includes RestaurantAgent

## [0.4.0] - 2026-02-27

### Added
- **Execution engine** — Actions pipeline that moves FiscalPilot from analysis-only to analysis + execution. Proposed actions are generated from audit findings, routed through approval, and executed by pluggable executors
- **Human-in-the-loop approval gate** — Tiered autonomy system with four levels: GREEN (auto-execute), YELLOW (auto-execute + notify), RED (require explicit approval), CRITICAL (require multi-party approval). Full immutable audit trail of all decisions
- **Action models** (`models/actions.py`) — `ActionStatus` (7 lifecycle states), `ApprovalLevel`, `ActionType` (13 built-in + CUSTOM), `ProposedAction`, `ExecutionResult`, `ApprovalRule`, `ApprovalDecision` with `DEFAULT_APPROVAL_MAP`
- **Executor plugin system** (`execution/executors/`) — `BaseExecutor` ABC with validate/execute/rollback interface, `LogOnlyExecutor` (testing/fallback), `CategorizationExecutor` (GREEN-level transaction tagging), `NotificationExecutor` (YELLOW-level reminders)
- **Execution orchestrator** (`execution/engine.py`) — Executor registration, dry-run mode (default), rate limiting, rollback support, immutable execution log, summary reporting
- `ExecutionConfig` in config — `enabled`, `dry_run`, `require_approval`, `max_actions_per_run`, `approval_timeout_hours`
- `proposed_actions` field on `AuditReport` — actions generated per finding with concrete steps
- Coordinator action generation — `_generate_proposed_actions()`, `_action_title_for_finding()`, `_build_action_steps()` methods mapping findings → action types → approval levels
- 48 new tests for execution framework (190 total tests)

### Changed
- **Complete rebrand** from "waste, fraud, abuse" to AI CFO positioning:
  - `FindingCategory.WASTE` → `COST_OPTIMIZATION`
  - `FindingCategory.FRAUD` → `RISK_DETECTION`
  - `FindingCategory.ABUSE` → `POLICY_VIOLATION`
  - Waste Detector agent → "Cost Optimizer Agent"
  - Fraud Detector agent → "Risk Detector Agent"
  - CLI tagline → "Your AI CFO. Analyze. Recommend. Execute."
- Config fields renamed: `waste_detection` → `cost_optimization`, `fraud_detection` → `risk_detection`
- README fully rewritten — new "Open-Source AI CFO" positioning, 6 real-world business examples (Freelancer → Enterprise), execution engine docs, human-in-the-loop section, competitive comparison table, expanded roadmap
- `SecurityConfig` now includes `audit_trail` flag

## [0.3.0] - 2026-02-27

### Added
- **Benford's Law analyzer** — First/second digit distribution, chi-squared goodness-of-fit, MAD-based conformity scoring (Nigrini 2012 thresholds), per-vendor and per-category digit breakdown, suspicious digit detection
- **Anomaly detection engine** — Z-score, IQR (Interquartile Range), time-series monthly/weekly deviation tracking, vendor-level anomaly detection, automatic deduplication across methods
- **Industry benchmark database** — 13 industry profiles (restaurant, retail, SaaS, ecommerce, healthcare, manufacturing, professional services, construction, real estate, logistics, education, nonprofit, other) with expense ratios and KPIs, health grading A–F, excess spend quantification
- **Cash flow forecasting** — Exponential smoothing projections, seasonal index computation, runway calculation, risk alerts (negative balance, tight months, short runway)
- **Tax optimization engine** — Miscategorized expense detection (30+ keyword mappings), missing deduction identification, Section 179 depreciation opportunities, S-Corp entity structure evaluation, SEP IRA retirement suggestions, meal documentation (50% rule)
- **Intelligence pipeline** in coordinator — 5 pure-computation engines run before LLM agents, results injected into agent context for enhanced analysis
- `IntelligenceData` model in audit reports with summaries from all 5 engines
- 5 new config flags: `benfords_analysis`, `anomaly_detection`, `benchmark_comparison`, `cashflow_forecast`, `tax_optimization`
- 56 new tests for intelligence engines (142 total tests)

### Changed
- Coordinator `run_audit()` now runs intelligence engines as pre-computation step before agent dispatch
- Audit reports now include `intelligence` field with statistical summaries
- Intelligence findings (benchmark deviations, tax opportunities, cash flow warnings, anomalies, Benford violations) are merged with agent findings and ranked by impact

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
- 6 specialist agents: Cost Optimizer, Risk Detector, Margin Optimizer, Cost Cutter, Revenue Analyzer, Vendor Auditor
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
