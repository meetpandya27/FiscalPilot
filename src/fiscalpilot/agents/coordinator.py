"""
Coordinator Agent — the "brain" that orchestrates all specialist agents.

This is the main agent that:
1. Ingests financial data from connectors.
2. Dispatches work to specialist agents (waste, fraud, margin, etc.).
3. Aggregates findings into a unified audit report.
4. Generates executive summaries and action items.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from fiscalpilot.agents.base import BaseAgent
from fiscalpilot.agents.waste_detector import WasteDetectorAgent
from fiscalpilot.agents.fraud_detector import FraudDetectorAgent
from fiscalpilot.agents.margin_optimizer import MarginOptimizerAgent
from fiscalpilot.agents.cost_cutter import CostCutterAgent
from fiscalpilot.agents.revenue_analyzer import RevenueAnalyzerAgent
from fiscalpilot.agents.vendor_auditor import VendorAuditorAgent
from fiscalpilot.config import FiscalPilotConfig
from fiscalpilot.connectors.registry import ConnectorRegistry
from fiscalpilot.models.company import CompanyProfile
from fiscalpilot.models.financial import FinancialDataset
from fiscalpilot.models.report import (
    ActionItem,
    AuditReport,
    ExecutiveSummary,
    Finding,
    FindingCategory,
    Severity,
)

logger = logging.getLogger("fiscalpilot.agents.coordinator")


class CoordinatorAgent(BaseAgent):
    """Orchestrates all specialist agents and produces the final report."""

    name = "coordinator"
    description = "Master coordinator that orchestrates all financial analysis agents"

    def __init__(
        self,
        config: FiscalPilotConfig,
        connectors: ConnectorRegistry,
    ) -> None:
        super().__init__(config)
        self.connectors = connectors

        # Initialize specialist agents based on config
        self._agents: list[BaseAgent] = []
        analyzers = config.analyzers

        if analyzers.waste_detection:
            self._agents.append(WasteDetectorAgent(config))
        if analyzers.fraud_detection:
            self._agents.append(FraudDetectorAgent(config))
        if analyzers.margin_optimization:
            self._agents.append(MarginOptimizerAgent(config))
        if analyzers.cost_reduction:
            self._agents.append(CostCutterAgent(config))
        if analyzers.revenue_leakage:
            self._agents.append(RevenueAnalyzerAgent(config))
        if analyzers.vendor_analysis:
            self._agents.append(VendorAuditorAgent(config))

        logger.info("Coordinator initialized with %d specialist agents", len(self._agents))

    @property
    def system_prompt(self) -> str:
        return """You are FiscalPilot's Coordinator — an expert AI CFO that orchestrates 
financial analysis. Your role is to:

1. Review all findings from specialist agents (waste, fraud, margin, cost, revenue, vendor).
2. Eliminate duplicates and resolve conflicts between agents.
3. Prioritize findings by impact (potential savings × confidence).
4. Generate a clear, actionable executive summary.
5. Create specific action items ranked by ROI.

You serve businesses of ALL sizes — from a restaurant owner to a Fortune 500 CFO.
Adapt your language and recommendations to the company's scale.

Always be specific with dollar amounts and percentages. 
Never be vague. Every recommendation should have a clear next step."""

    async def run_audit(self, company: CompanyProfile) -> AuditReport:
        """Run a full audit using all specialist agents.

        1. Pull data from all connectors.
        2. Fan out to specialist agents in parallel.
        3. Aggregate and deduplicate findings.
        4. Generate executive summary via LLM.
        5. Return the final AuditReport.
        """
        # Step 1: Pull data from all connectors
        dataset = await self._pull_data(company)

        # Step 2: Build shared context
        context = self._build_context(company, dataset)

        # Step 3: Fan out to all specialist agents in parallel
        logger.info("Dispatching to %d specialist agents...", len(self._agents))
        tasks = [agent.analyze(context) for agent in self._agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Step 4: Aggregate findings
        all_findings: list[Finding] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error("Agent %s failed: %s", self._agents[i].name, result)
                continue
            findings = self._extract_findings(result, self._agents[i].name)
            all_findings.extend(findings)

        # Step 5: Deduplicate and rank
        all_findings = self._deduplicate_findings(all_findings)
        all_findings.sort(key=lambda f: f.potential_savings * f.confidence, reverse=True)

        # Step 6: Generate action items
        action_items = self._generate_action_items(all_findings)

        # Step 7: Generate executive summary
        executive_summary = await self._generate_executive_summary(
            company, all_findings, dataset
        )

        # Build final report
        report = AuditReport(
            id=str(uuid.uuid4()),
            company_name=company.name,
            findings=all_findings,
            action_items=action_items,
            executive_summary=executive_summary,
            period_start=str(dataset.period_start) if dataset.period_start else None,
            period_end=str(dataset.period_end) if dataset.period_end else None,
            metadata={
                "agents_used": [a.name for a in self._agents],
                "connectors_used": [c.name for c in self.connectors.active_connectors],
                "total_transactions_analyzed": len(dataset.transactions),
            },
        )

        return report

    async def run_quick_scan(self, company: CompanyProfile) -> AuditReport:
        """Run a lightweight scan — useful for demos and onboarding."""
        dataset = await self._pull_data(company)
        context = self._build_context(company, dataset)

        # Only run waste and cost agents for quick scan
        quick_agents = [a for a in self._agents if a.name in ("waste_detector", "cost_cutter")]
        if not quick_agents:
            quick_agents = self._agents[:2]

        tasks = [agent.analyze(context) for agent in quick_agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_findings: list[Finding] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                continue
            findings = self._extract_findings(result, quick_agents[i].name)
            all_findings.extend(findings)

        return AuditReport(
            id=str(uuid.uuid4()),
            company_name=company.name,
            findings=all_findings,
            metadata={"scan_type": "quick"},
        )

    async def _pull_data(self, company: CompanyProfile) -> FinancialDataset:
        """Pull and merge data from all active connectors."""
        datasets: list[FinancialDataset] = []
        for connector in self.connectors.active_connectors:
            try:
                ds = await connector.pull(company)
                datasets.append(ds)
                logger.info("Pulled %d transactions from %s", len(ds.transactions), connector.name)
            except Exception as e:
                logger.error("Connector %s failed: %s", connector.name, e)

        return self._merge_datasets(datasets)

    def _merge_datasets(self, datasets: list[FinancialDataset]) -> FinancialDataset:
        """Merge multiple datasets into one."""
        merged = FinancialDataset()
        for ds in datasets:
            merged.transactions.extend(ds.transactions)
            merged.invoices.extend(ds.invoices)
            merged.balances.extend(ds.balances)
            if ds.period_start:
                if merged.period_start is None or ds.period_start < merged.period_start:
                    merged.period_start = ds.period_start
            if ds.period_end:
                if merged.period_end is None or ds.period_end > merged.period_end:
                    merged.period_end = ds.period_end
        return merged

    def _build_context(
        self, company: CompanyProfile, dataset: FinancialDataset
    ) -> dict[str, Any]:
        """Build the shared context dict that all agents receive."""
        return {
            "company": company.model_dump(),
            "total_transactions": len(dataset.transactions),
            "total_expenses": dataset.total_expenses,
            "total_income": dataset.total_income,
            "transactions_sample": [
                t.model_dump() for t in dataset.transactions[:500]
            ],
            "invoices_sample": [inv.model_dump() for inv in dataset.invoices[:100]],
            "balances": [b.model_dump() for b in dataset.balances],
            "period_start": str(dataset.period_start) if dataset.period_start else None,
            "period_end": str(dataset.period_end) if dataset.period_end else None,
        }

    def _extract_findings(self, result: dict[str, Any], agent_name: str) -> list[Finding]:
        """Extract Finding objects from an agent's raw result."""
        findings: list[Finding] = []
        for raw in result.get("findings", []):
            try:
                finding = Finding(
                    id=f"{agent_name}_{uuid.uuid4().hex[:8]}",
                    title=raw.get("title", "Untitled Finding"),
                    category=FindingCategory(raw.get("category", "waste")),
                    severity=Severity(raw.get("severity", "medium")),
                    description=raw.get("description", ""),
                    evidence=raw.get("evidence", []),
                    potential_savings=float(raw.get("potential_savings", 0)),
                    confidence=float(raw.get("confidence", 0.7)),
                    recommendation=raw.get("recommendation", ""),
                )
                findings.append(finding)
            except Exception as e:
                logger.warning("Failed to parse finding from %s: %s", agent_name, e)
        return findings

    def _deduplicate_findings(self, findings: list[Finding]) -> list[Finding]:
        """Remove duplicate findings (by title similarity)."""
        seen_titles: set[str] = set()
        unique: list[Finding] = []
        for f in findings:
            normalized = f.title.lower().strip()
            if normalized not in seen_titles:
                seen_titles.add(normalized)
                unique.append(f)
        return unique

    def _generate_action_items(self, findings: list[Finding]) -> list[ActionItem]:
        """Convert top findings into concrete action items."""
        action_items: list[ActionItem] = []
        for f in findings[:20]:  # Top 20 findings
            action_items.append(
                ActionItem(
                    title=f"Address: {f.title}",
                    description=f.recommendation or f.description,
                    priority=f.severity,
                    estimated_savings=f.potential_savings,
                    effort="low" if f.potential_savings < 1000 else "medium" if f.potential_savings < 10000 else "high",
                    finding_ids=[f.id],
                )
            )
        return action_items

    async def _generate_executive_summary(
        self,
        company: CompanyProfile,
        findings: list[Finding],
        dataset: FinancialDataset,
    ) -> ExecutiveSummary:
        """Use LLM to generate a compelling executive summary."""
        total_savings = sum(f.potential_savings for f in findings)
        critical_count = sum(1 for f in findings if f.severity == Severity.CRITICAL)
        top_opps = [f.title for f in findings[:5]]

        prompt = f"""Generate a concise executive summary for {company.name} ({company.size_label}, {company.industry.value} industry).

Key metrics:
- Total transactions analyzed: {len(dataset.transactions)}
- Total expenses: ${dataset.total_expenses:,.2f}
- Total income: ${dataset.total_income:,.2f}
- Findings: {len(findings)} total, {critical_count} critical
- Total potential savings: ${total_savings:,.2f}
- Top opportunities: {', '.join(top_opps)}

Write a 3-4 paragraph executive summary that:
1. Opens with the most impactful finding.
2. Quantifies the total savings opportunity.
3. Highlights the top 3 action items.
4. Ends with a recommended next step.

Be specific, use dollar amounts, and be direct. No fluff."""

        narrative = await self._call_llm([{"role": "user", "content": prompt}])

        # Calculate health score (simple heuristic)
        savings_pct = (total_savings / max(dataset.total_expenses, 1)) * 100
        health_score = max(0, min(100, 100 - savings_pct * 2 - critical_count * 10))

        return ExecutiveSummary(
            total_potential_savings=total_savings,
            total_findings=len(findings),
            critical_findings=critical_count,
            top_opportunities=top_opps,
            health_score=round(health_score, 1),
            narrative=narrative,
        )

    def _build_prompt(self, context: dict[str, Any]) -> str:
        return ""  # Coordinator uses custom flow, not the base analyze()

    def _parse_response(self, response: str, context: dict[str, Any]) -> dict[str, Any]:
        return {}  # Coordinator uses custom flow
