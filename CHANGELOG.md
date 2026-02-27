# Changelog

All notable changes to FiscalPilot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

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
