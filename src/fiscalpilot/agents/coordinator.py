"""
Coordinator Agent — the "brain" that orchestrates all specialist agents.

This is the main agent that:
1. Ingests financial data from connectors.
2. Dispatches work to specialist agents (optimization, risk, margin, etc.).
3. Aggregates findings into a unified audit report.
4. Generates executive summaries and action items.
5. Proposes executable actions with approval routing.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from fiscalpilot.agents.base import BaseAgent
from fiscalpilot.agents.cost_optimizer import CostOptimizerAgent
from fiscalpilot.agents.risk_detector import RiskDetectorAgent
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
    IntelligenceData,
    Severity,
)
from fiscalpilot.models.actions import (
    ActionStep,
    ActionType,
    ApprovalLevel,
    DEFAULT_APPROVAL_MAP,
    ProposedAction,
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

        if analyzers.cost_optimization:
            self._agents.append(CostOptimizerAgent(config))
        if analyzers.risk_detection:
            self._agents.append(RiskDetectorAgent(config))
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

1. Review all findings from specialist agents (optimization, risk, margin, cost, revenue, vendor).
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
        2. Run intelligence engines (Benford, anomaly, benchmark, cashflow, tax).
        3. Fan out to specialist agents in parallel.
        4. Aggregate and deduplicate findings.
        5. Generate executive summary via LLM.
        6. Return the final AuditReport.
        """
        # Step 1: Pull data from all connectors
        dataset = await self._pull_data(company)

        # Step 2: Run intelligence engines (pure computation, no LLM)
        intelligence, intel_findings, intel_context = self._run_intelligence(company, dataset)

        # Step 3: Build shared context (includes intelligence results)
        context = self._build_context(company, dataset)
        context.update(intel_context)

        # Step 4: Fan out to all specialist agents in parallel
        logger.info("Dispatching to %d specialist agents...", len(self._agents))
        tasks = [agent.analyze(context) for agent in self._agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Step 5: Aggregate findings (intelligence + agent results)
        all_findings: list[Finding] = list(intel_findings)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error("Agent %s failed: %s", self._agents[i].name, result)
                continue
            findings = self._extract_findings(result, self._agents[i].name)
            all_findings.extend(findings)

        # Step 6: Deduplicate and rank
        all_findings = self._deduplicate_findings(all_findings)
        all_findings.sort(key=lambda f: f.potential_savings * f.confidence, reverse=True)

        # Step 7: Generate action items
        action_items = self._generate_action_items(all_findings)

        # Step 8: Generate proposed actions (v0.4 execution pipeline)
        proposed_actions = self._generate_proposed_actions(all_findings, company)

        # Step 9: Generate executive summary
        executive_summary = await self._generate_executive_summary(
            company, all_findings, dataset
        )

        # Build final report
        report = AuditReport(
            id=str(uuid.uuid4()),
            company_name=company.name,
            findings=all_findings,
            action_items=action_items,
            proposed_actions=proposed_actions,
            executive_summary=executive_summary,
            intelligence=intelligence,
            period_start=str(dataset.period_start) if dataset.period_start else None,
            period_end=str(dataset.period_end) if dataset.period_end else None,
            metadata={
                "agents_used": [a.name for a in self._agents],
                "connectors_used": [c.name for c in self.connectors.active_connectors],
                "total_transactions_analyzed": len(dataset.transactions),
                "intelligence_engines": self._active_intelligence_engines(),
            },
        )

        return report

    async def run_quick_scan(self, company: CompanyProfile) -> AuditReport:
        """Run a lightweight scan — useful for demos and onboarding."""
        dataset = await self._pull_data(company)
        context = self._build_context(company, dataset)

        # Only run cost optimization and cost cutter agents for quick scan
        quick_agents = [a for a in self._agents if a.name in ("cost_optimizer", "cost_cutter")]
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

    def _run_intelligence(
        self,
        company: CompanyProfile,
        dataset: FinancialDataset,
    ) -> tuple[IntelligenceData, list[Finding], dict[str, Any]]:
        """Run all enabled intelligence engines.

        Returns (IntelligenceData, list of generated Findings, context additions for agents).
        """
        analyzers = self.config.analyzers
        txn_dicts = [t.model_dump() for t in dataset.transactions]
        intelligence = IntelligenceData()
        findings: list[Finding] = []
        extra_context: dict[str, Any] = {}

        # 1. Benford's Law
        if analyzers.benfords_analysis and len(txn_dicts) >= 50:
            try:
                from fiscalpilot.analyzers.benfords import BenfordsAnalyzer

                result = BenfordsAnalyzer.analyze(txn_dicts)
                intelligence.benfords_summary = result.summary
                intelligence.benfords_conformity_score = result.conformity_score
                extra_context["benfords_analysis"] = result.summary
                extra_context["benfords_conformity_score"] = result.conformity_score

                # Generate finding if non-conforming
                if result.conformity_score < 0.5:
                    findings.append(Finding(
                        id=f"benfords_{uuid.uuid4().hex[:8]}",
                        title="Significant Benford's Law Deviation Detected",
                        category=FindingCategory.RISK_DETECTION,
                        severity=Severity.HIGH,
                        description=(
                            f"Transaction amounts deviate significantly from Benford's Law "
                            f"(conformity: {result.conformity_score:.1%}). This may indicate "
                            f"fabricated data, duplicate entries, or systematic manipulation."
                        ),
                        evidence=[result.summary] + [
                            f"Digit {s['digit']}: {s['observed_pct']}% vs expected {s['expected_pct']}%"
                            for s in result.suspicious_digits[:5]
                        ],
                        confidence=min(0.9, 1.0 - result.conformity_score),
                        recommendation="Conduct a forensic review of transaction sources.",
                    ))
                elif result.conformity_score < 0.7:
                    findings.append(Finding(
                        id=f"benfords_{uuid.uuid4().hex[:8]}",
                        title="Marginal Benford's Law Conformity",
                        category=FindingCategory.COMPLIANCE,
                        severity=Severity.MEDIUM,
                        description=(
                            f"Transaction amounts show marginal conformity to Benford's Law "
                            f"(score: {result.conformity_score:.1%}). Worth investigating."
                        ),
                        evidence=[result.summary],
                        confidence=0.6,
                        recommendation="Review flagged digit patterns for potential data quality issues.",
                    ))

                logger.info("Benford's analysis complete: conformity=%.1f%%", result.conformity_score * 100)
            except Exception as e:
                logger.warning("Benford's analysis failed: %s", e)

        # 2. Anomaly Detection
        if analyzers.anomaly_detection and txn_dicts:
            try:
                from fiscalpilot.analyzers.anomaly import AnomalyDetector

                result = AnomalyDetector.analyze(txn_dicts)
                intelligence.anomaly_summary = result.summary
                intelligence.anomaly_flagged_count = result.flagged_count
                extra_context["anomaly_detection"] = result.summary
                extra_context["anomaly_flagged_count"] = result.flagged_count

                # Inject top flagged transactions into context for agents
                if result.flags:
                    top_flags = result.flags[:20]
                    extra_context["anomaly_flags"] = [
                        {"id": f.transaction_id, "amount": f.amount, "score": f.score, "reason": f.reason}
                        for f in top_flags
                    ]

                # Time-series anomalies → findings
                for ts in result.time_series_anomalies:
                    if ts.score >= 0.6:
                        findings.append(Finding(
                            id=f"anomaly_ts_{uuid.uuid4().hex[:8]}",
                            title=f"Anomalous spending in {ts.period}",
                            category=FindingCategory.COST_OPTIMIZATION,
                            severity=Severity.MEDIUM if ts.score < 0.8 else Severity.HIGH,
                            description=(
                                f"Spending of ${ts.total_spend:,.2f} in {ts.period} deviates "
                                f"{ts.deviation_pct:+.1f}% from expected range "
                                f"(${ts.expected_range[0]:,.2f}–${ts.expected_range[1]:,.2f})."
                            ),
                            evidence=[f"Period: {ts.period}, Score: {ts.score:.2f}"],
                            potential_savings=max(0, ts.total_spend - ts.expected_range[1]),
                            confidence=ts.score,
                            recommendation="Review this period for unusual purchases or billing errors.",
                            affected_transactions=ts.contributing_transactions,
                        ))

                logger.info("Anomaly detection complete: %d flagged", result.flagged_count)
            except Exception as e:
                logger.warning("Anomaly detection failed: %s", e)

        # 3. Industry Benchmarks
        if analyzers.benchmark_comparison and txn_dicts:
            try:
                from fiscalpilot.analyzers.benchmarks import BenchmarkAnalyzer

                industry = company.industry.value if company.industry else "other"
                revenue = company.annual_revenue or 0

                result = BenchmarkAnalyzer.analyze(
                    txn_dicts, industry=industry, annual_revenue=revenue
                )
                intelligence.benchmark_summary = result.summary
                intelligence.benchmark_grade = result.health_grade
                intelligence.benchmark_excess_spend = result.total_excess_spend
                extra_context["benchmark_analysis"] = result.summary
                extra_context["benchmark_grade"] = result.health_grade

                # Benchmark deviations → findings
                for dev in result.deviations:
                    if dev.severity in ("critical", "high"):
                        findings.append(Finding(
                            id=f"benchmark_{uuid.uuid4().hex[:8]}",
                            title=f"{dev.category.replace('_', ' ').title()} exceeds industry benchmark",
                            category=FindingCategory.BENCHMARK_DEVIATION,
                            severity=Severity.HIGH if dev.severity == "high" else Severity.CRITICAL,
                            description=dev.recommendation,
                            evidence=[
                                f"Actual: {dev.actual_pct:.1f}% of revenue",
                                f"Industry range: {dev.benchmark_low:.0f}%–{dev.benchmark_high:.0f}%",
                                f"Typical: {dev.benchmark_typical:.0f}%",
                            ],
                            potential_savings=dev.annual_excess,
                            confidence=0.75,
                            recommendation=dev.recommendation,
                        ))

                logger.info("Benchmark analysis complete: grade=%s", result.health_grade)
            except Exception as e:
                logger.warning("Benchmark analysis failed: %s", e)

        # 4. Cash Flow Forecast
        if analyzers.cashflow_forecast and txn_dicts:
            try:
                from fiscalpilot.analyzers.cashflow import CashFlowForecaster

                balance = sum(b.balance for b in dataset.balances) if dataset.balances else 0

                result = CashFlowForecaster.analyze(txn_dicts, current_balance=balance)
                intelligence.cashflow_summary = result.summary
                intelligence.cashflow_runway_months = result.runway_months
                extra_context["cashflow_forecast"] = result.summary
                extra_context["cashflow_runway_months"] = result.runway_months

                # Critical runway → finding
                if 0 < result.runway_months < 6:
                    findings.append(Finding(
                        id=f"cashflow_{uuid.uuid4().hex[:8]}",
                        title=f"Cash runway is only {result.runway_months:.1f} months",
                        category=FindingCategory.CASH_FLOW,
                        severity=Severity.CRITICAL if result.runway_months < 3 else Severity.HIGH,
                        description=(
                            f"At the current burn rate of ${result.average_monthly_burn:,.2f}/month, "
                            f"cash reserves will be depleted in ~{result.runway_months:.1f} months."
                        ),
                        evidence=result.risk_alerts[:5],
                        confidence=0.8,
                        recommendation="Immediately reduce expenses or secure additional funding.",
                    ))

                for alert in result.risk_alerts:
                    if "negative balance" in alert.lower():
                        findings.append(Finding(
                            id=f"cashflow_{uuid.uuid4().hex[:8]}",
                            title="Projected negative cash balance",
                            category=FindingCategory.CASH_FLOW,
                            severity=Severity.CRITICAL,
                            description=alert,
                            confidence=0.7,
                            recommendation="Review upcoming expenses and accelerate receivables collection.",
                        ))
                        break

                logger.info("Cash flow forecast complete: runway=%.1f months", result.runway_months)
            except Exception as e:
                logger.warning("Cash flow forecast failed: %s", e)

        # 5. Tax Optimization
        if analyzers.tax_optimization and txn_dicts:
            try:
                from fiscalpilot.analyzers.tax_optimizer import TaxOptimizer

                result = TaxOptimizer.analyze(
                    txn_dicts,
                    annual_revenue=company.annual_revenue or 0,
                )
                intelligence.tax_summary = result.summary
                intelligence.tax_savings_estimate = result.total_estimated_savings
                extra_context["tax_analysis"] = result.summary

                # Tax opportunities → findings
                for opp in result.opportunities:
                    if opp.estimated_savings >= 500:
                        findings.append(Finding(
                            id=f"tax_{uuid.uuid4().hex[:8]}",
                            title=opp.title,
                            category=FindingCategory.TAX_OPPORTUNITY,
                            severity=Severity.MEDIUM if opp.estimated_savings < 5000 else Severity.HIGH,
                            description=opp.description,
                            evidence=[],
                            potential_savings=opp.estimated_savings,
                            confidence=opp.confidence,
                            recommendation=opp.recommendation,
                            affected_transactions=opp.affected_transactions,
                        ))

                logger.info("Tax optimization complete: $%.2f potential savings", result.total_estimated_savings)
            except Exception as e:
                logger.warning("Tax optimization failed: %s", e)

        return intelligence, findings, extra_context

    def _active_intelligence_engines(self) -> list[str]:
        """Return names of enabled intelligence engines."""
        analyzers = self.config.analyzers
        engines = []
        if analyzers.benfords_analysis:
            engines.append("benfords_law")
        if analyzers.anomaly_detection:
            engines.append("anomaly_detection")
        if analyzers.benchmark_comparison:
            engines.append("industry_benchmarks")
        if analyzers.cashflow_forecast:
            engines.append("cashflow_forecast")
        if analyzers.tax_optimization:
            engines.append("tax_optimization")
        return engines

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
                    category=FindingCategory(raw.get("category", "cost_optimization")),
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

    def _generate_proposed_actions(
        self, findings: list[Finding], company: CompanyProfile
    ) -> list[ProposedAction]:
        """Generate executable ProposedAction objects from findings.

        Maps each finding to an appropriate action type, assigns an
        approval level, and builds execution steps.
        """
        actions: list[ProposedAction] = []

        # Category → action type mapping
        category_action_map: dict[FindingCategory, ActionType] = {
            FindingCategory.COST_OPTIMIZATION: ActionType.FLAG_FOR_REVIEW,
            FindingCategory.RISK_DETECTION: ActionType.FLAG_FOR_REVIEW,
            FindingCategory.POLICY_VIOLATION: ActionType.FLAG_FOR_REVIEW,
            FindingCategory.UNUSED_SUBSCRIPTION: ActionType.CANCEL_SUBSCRIPTION,
            FindingCategory.DUPLICATE_PAYMENT: ActionType.FLAG_FOR_REVIEW,
            FindingCategory.VENDOR_OVERCHARGE: ActionType.RENEGOTIATE_VENDOR,
            FindingCategory.TAX_OPPORTUNITY: ActionType.GENERATE_REPORT,
            FindingCategory.REVENUE_LEAKAGE: ActionType.SEND_REMINDER,
            FindingCategory.CASH_FLOW: ActionType.CREATE_BUDGET_ALERT,
            FindingCategory.BENCHMARK_DEVIATION: ActionType.GENERATE_REPORT,
            FindingCategory.COMPLIANCE: ActionType.FLAG_FOR_REVIEW,
            FindingCategory.MARGIN_IMPROVEMENT: ActionType.GENERATE_REPORT,
            FindingCategory.COST_REDUCTION: ActionType.RENEGOTIATE_VENDOR,
        }

        for finding in findings[:30]:  # Top 30 findings
            action_type = category_action_map.get(finding.category, ActionType.CUSTOM)
            approval_level = DEFAULT_APPROVAL_MAP.get(action_type, ApprovalLevel.RED)

            # Build steps based on category
            steps = self._build_action_steps(finding, action_type)

            action = ProposedAction(
                id=f"act_{uuid.uuid4().hex[:8]}",
                title=self._action_title_for_finding(finding),
                description=finding.recommendation or finding.description,
                action_type=action_type,
                approval_level=approval_level,
                estimated_savings=finding.potential_savings,
                confidence=finding.confidence,
                steps=steps,
                finding_ids=[finding.id],
            )
            actions.append(action)

        return actions

    def _action_title_for_finding(self, finding: Finding) -> str:
        """Generate an action-oriented title for a finding."""
        category_verbs: dict[FindingCategory, str] = {
            FindingCategory.UNUSED_SUBSCRIPTION: "Cancel",
            FindingCategory.DUPLICATE_PAYMENT: "Recover",
            FindingCategory.VENDOR_OVERCHARGE: "Renegotiate",
            FindingCategory.TAX_OPPORTUNITY: "Claim",
            FindingCategory.REVENUE_LEAKAGE: "Collect",
            FindingCategory.CASH_FLOW: "Address",
            FindingCategory.COST_OPTIMIZATION: "Optimize",
            FindingCategory.RISK_DETECTION: "Investigate",
            FindingCategory.POLICY_VIOLATION: "Remediate",
            FindingCategory.BENCHMARK_DEVIATION: "Review",
            FindingCategory.COMPLIANCE: "Fix",
            FindingCategory.MARGIN_IMPROVEMENT: "Improve",
            FindingCategory.COST_REDUCTION: "Reduce",
        }
        verb = category_verbs.get(finding.category, "Address")
        return f"{verb}: {finding.title}"

    def _build_action_steps(self, finding: Finding, action_type: ActionType) -> list[ActionStep]:
        """Build concrete execution steps for an action."""
        if action_type == ActionType.CANCEL_SUBSCRIPTION:
            return [
                ActionStep(order=1, description="Review subscription usage data", reversible=False),
                ActionStep(order=2, description="Confirm cancellation with stakeholders", reversible=False),
                ActionStep(order=3, description=f"Cancel subscription: {finding.title}", reversible=True),
                ActionStep(order=4, description="Update recurring expense forecast", reversible=True),
            ]
        elif action_type == ActionType.RENEGOTIATE_VENDOR:
            return [
                ActionStep(order=1, description="Pull current vendor pricing and contract terms", reversible=False),
                ActionStep(order=2, description="Research market rates for comparable services", reversible=False),
                ActionStep(order=3, description="Draft renegotiation request with target pricing", reversible=False),
                ActionStep(order=4, description="Send renegotiation request to vendor", reversible=False),
            ]
        elif action_type == ActionType.SEND_REMINDER:
            return [
                ActionStep(order=1, description="Identify overdue invoices/items", reversible=False),
                ActionStep(order=2, description="Generate reminder message from template", reversible=False),
                ActionStep(order=3, description="Send reminder to recipient(s)", reversible=False),
            ]
        elif action_type == ActionType.GENERATE_REPORT:
            return [
                ActionStep(order=1, description="Compile relevant data and analysis", reversible=False),
                ActionStep(order=2, description="Generate detailed report", reversible=False),
                ActionStep(order=3, description="Deliver report to stakeholders", reversible=False),
            ]
        elif action_type == ActionType.FLAG_FOR_REVIEW:
            return [
                ActionStep(order=1, description=f"Flag for review: {finding.title}", reversible=True),
                ActionStep(order=2, description="Assign to responsible party", reversible=True),
            ]
        elif action_type == ActionType.CREATE_BUDGET_ALERT:
            return [
                ActionStep(order=1, description="Analyze current spending trends", reversible=False),
                ActionStep(order=2, description="Set threshold-based budget alert", reversible=True),
                ActionStep(order=3, description="Configure notification recipients", reversible=True),
            ]
        else:
            return [
                ActionStep(order=1, description=f"Review: {finding.title}", reversible=False),
                ActionStep(order=2, description=finding.recommendation or "Take appropriate action", reversible=False),
            ]

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
