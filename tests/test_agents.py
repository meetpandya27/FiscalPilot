"""
Tests for FiscalPilot agents — specialist LLM agents and the coordinator.

These tests mock the LLM (litellm.acompletion) to validate:
- Prompt construction
- Response parsing
- Finding extraction
- Error handling
- Coordinator orchestration
- Local audit mode (no LLM)
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fiscalpilot.agents.coordinator import CoordinatorAgent
from fiscalpilot.agents.cost_cutter import CostCutterAgent
from fiscalpilot.agents.cost_optimizer import CostOptimizerAgent
from fiscalpilot.agents.margin_optimizer import MarginOptimizerAgent
from fiscalpilot.agents.revenue_analyzer import RevenueAnalyzerAgent
from fiscalpilot.agents.risk_detector import RiskDetectorAgent
from fiscalpilot.agents.vendor_auditor import VendorAuditorAgent
from fiscalpilot.config import (
    ConnectorConfig,
    FiscalPilotConfig,
    LLMConfig,
)
from fiscalpilot.connectors.registry import ConnectorRegistry
from fiscalpilot.models.company import CompanyProfile, CompanySize, Industry
from fiscalpilot.models.financial import FinancialDataset, Transaction, TransactionType
from fiscalpilot.models.report import AuditReport, FindingCategory, Severity

# ── Fixtures ────────────────────────────────────────────────────────


def _config() -> FiscalPilotConfig:
    return FiscalPilotConfig(
        llm=LLMConfig(model="gpt-4o", api_key="test-key"),
        connectors=[ConnectorConfig(type="csv", options={"file_path": "test.csv"})],
    )


def _company() -> CompanyProfile:
    return CompanyProfile(
        name="Joe's Diner",
        industry=Industry.RESTAURANT,
        size=CompanySize.SMALL,
        annual_revenue=850_000,
        employee_count=12,
    )


def _context() -> dict[str, Any]:
    """Minimal context dict that agents expect."""
    return {
        "company": {
            "name": "Joe's Diner",
            "industry": "restaurant",
            "size": "small",
        },
        "total_transactions": 100,
        "total_expenses": 425_000,
        "total_income": 850_000,
        "period_start": "2024-01-01",
        "period_end": "2024-12-31",
        "transactions_sample": [
            {
                "id": f"txn_{i:04d}",
                "date": "2024-06-15",
                "amount": 150.0 + i * 10,
                "vendor": f"vendor_{i % 5}",
                "category": "food_supplies",
                "type": "expense",
                "description": f"Purchase #{i}",
            }
            for i in range(50)
        ],
        "invoices_sample": [],
        "balances": [],
    }


def _mock_llm_response(content: str) -> AsyncMock:
    """Create a mock litellm.acompletion that returns the given content."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = content
    return AsyncMock(return_value=mock_response)


def _cost_optimizer_llm_response() -> str:
    """Realistic LLM response for cost optimizer agent."""
    return json.dumps(
        [
            {
                "title": "Duplicate food supplier payments",
                "category": "cost_optimization",
                "severity": "high",
                "description": "Found 3 duplicate payments to vendor_0 totaling $900.",
                "evidence": ["txn_0000 and txn_0005 are identical", "vendor_0 billed twice in June"],
                "potential_savings": 900.0,
                "confidence": 0.85,
                "recommendation": "Review and dispute duplicate charges with vendor_0.",
            },
            {
                "title": "Unused catering subscription",
                "category": "unused_subscription",
                "severity": "medium",
                "description": "Monthly $199 subscription to CaterPro with zero events last quarter.",
                "evidence": ["No catering events in Q3 2024"],
                "potential_savings": 2388.0,
                "confidence": 0.9,
                "recommendation": "Cancel CaterPro subscription — saves $2,388/year.",
            },
        ]
    )


def _risk_detector_llm_response() -> str:
    return json.dumps(
        [
            {
                "title": "Unusual after-hours transaction pattern",
                "category": "risk_detection",
                "severity": "high",
                "description": "12 transactions processed between 2-4 AM on weekdays.",
                "evidence": ["txn_0012: $450 at 2:30 AM", "txn_0023: $320 at 3:15 AM"],
                "potential_savings": 0,
                "confidence": 0.75,
                "recommendation": "Investigate after-hours transaction sources.",
            },
        ]
    )


def _margin_optimizer_llm_response() -> str:
    return json.dumps(
        [
            {
                "title": "Menu pricing below food cost threshold",
                "category": "margin_improvement",
                "severity": "medium",
                "description": "5 menu items have food cost ratios above 40%.",
                "evidence": ["Pasta dish: 48% food cost", "Seafood platter: 52% food cost"],
                "potential_savings": 12_000.0,
                "confidence": 0.7,
                "recommendation": "Reprice menu items or renegotiate supplier costs.",
            },
        ]
    )


# ── Specialist Agent Tests ──────────────────────────────────────────


class TestCostOptimizerAgent:
    @pytest.mark.asyncio
    @patch("fiscalpilot.agents.base.litellm.acompletion")
    async def test_analyze_returns_findings(self, mock_llm: AsyncMock) -> None:
        mock_llm.side_effect = _mock_llm_response(_cost_optimizer_llm_response())
        agent = CostOptimizerAgent(_config())
        result = await agent.analyze(_context())

        assert "findings" in result
        assert len(result["findings"]) == 2
        assert result["findings"][0]["title"] == "Duplicate food supplier payments"
        assert result["findings"][1]["potential_savings"] == 2388.0

    @pytest.mark.asyncio
    @patch("fiscalpilot.agents.base.litellm.acompletion")
    async def test_prompt_contains_company_info(self, mock_llm: AsyncMock) -> None:
        mock_llm.side_effect = _mock_llm_response("[]")
        agent = CostOptimizerAgent(_config())
        await agent.analyze(_context())

        # Verify the LLM was called with a prompt containing company info
        call_args = mock_llm.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
        user_msg = [m for m in messages if m["role"] == "user"][0]["content"]
        assert "Joe's Diner" in user_msg
        assert "425,000" in user_msg  # total expenses

    @pytest.mark.asyncio
    @patch("fiscalpilot.agents.base.litellm.acompletion")
    async def test_handles_invalid_json(self, mock_llm: AsyncMock) -> None:
        mock_llm.side_effect = _mock_llm_response("This is not JSON at all")
        agent = CostOptimizerAgent(_config())
        result = await agent.analyze(_context())
        assert result["findings"] == []
        assert "raw_response" in result

    @pytest.mark.asyncio
    @patch("fiscalpilot.agents.base.litellm.acompletion")
    async def test_handles_markdown_wrapped_json(self, mock_llm: AsyncMock) -> None:
        wrapped = "```json\n" + _cost_optimizer_llm_response() + "\n```"
        mock_llm.side_effect = _mock_llm_response(wrapped)
        agent = CostOptimizerAgent(_config())
        result = await agent.analyze(_context())
        assert len(result["findings"]) == 2


class TestRiskDetectorAgent:
    @pytest.mark.asyncio
    @patch("fiscalpilot.agents.base.litellm.acompletion")
    async def test_analyze_returns_findings(self, mock_llm: AsyncMock) -> None:
        mock_llm.side_effect = _mock_llm_response(_risk_detector_llm_response())
        agent = RiskDetectorAgent(_config())
        result = await agent.analyze(_context())
        assert len(result["findings"]) == 1
        assert result["findings"][0]["severity"] == "high"


class TestMarginOptimizerAgent:
    @pytest.mark.asyncio
    @patch("fiscalpilot.agents.base.litellm.acompletion")
    async def test_analyze_returns_findings(self, mock_llm: AsyncMock) -> None:
        mock_llm.side_effect = _mock_llm_response(_margin_optimizer_llm_response())
        agent = MarginOptimizerAgent(_config())
        result = await agent.analyze(_context())
        assert len(result["findings"]) == 1
        assert result["findings"][0]["potential_savings"] == 12_000.0


class TestCostCutterAgent:
    @pytest.mark.asyncio
    @patch("fiscalpilot.agents.base.litellm.acompletion")
    async def test_analyze_returns_findings(self, mock_llm: AsyncMock) -> None:
        response = json.dumps(
            [
                {
                    "title": "Reduce linen service frequency",
                    "category": "cost_reduction",
                    "severity": "low",
                    "description": "Switch from daily to 3x/week linen service.",
                    "evidence": ["Current cost: $800/month"],
                    "potential_savings": 3200.0,
                    "confidence": 0.8,
                    "recommendation": "Renegotiate linen contract to 3x/week pickup.",
                }
            ]
        )
        mock_llm.side_effect = _mock_llm_response(response)
        agent = CostCutterAgent(_config())
        result = await agent.analyze(_context())
        assert len(result["findings"]) == 1


class TestRevenueAnalyzerAgent:
    @pytest.mark.asyncio
    @patch("fiscalpilot.agents.base.litellm.acompletion")
    async def test_analyze_returns_findings(self, mock_llm: AsyncMock) -> None:
        response = json.dumps(
            [
                {
                    "title": "Uncollected catering deposits",
                    "category": "revenue_leakage",
                    "severity": "medium",
                    "description": "3 catering events with no deposit collected.",
                    "evidence": ["Event #12: $2,500", "Event #15: $1,800"],
                    "potential_savings": 4300.0,
                    "confidence": 0.7,
                    "recommendation": "Implement mandatory deposit policy for catering.",
                }
            ]
        )
        mock_llm.side_effect = _mock_llm_response(response)
        agent = RevenueAnalyzerAgent(_config())
        result = await agent.analyze(_context())
        assert len(result["findings"]) == 1
        assert result["findings"][0]["category"] == "revenue_leakage"


class TestVendorAuditorAgent:
    @pytest.mark.asyncio
    @patch("fiscalpilot.agents.base.litellm.acompletion")
    async def test_analyze_returns_findings(self, mock_llm: AsyncMock) -> None:
        response = json.dumps(
            [
                {
                    "title": "Produce supplier 20% above market",
                    "category": "vendor_overcharge",
                    "severity": "high",
                    "description": "Fresh produce costs 20% above comparable wholesalers.",
                    "evidence": ["Average cost: $4.50/lb vs market $3.60/lb"],
                    "potential_savings": 8500.0,
                    "confidence": 0.8,
                    "recommendation": "Get competitive bids from 2-3 alternative produce suppliers.",
                }
            ]
        )
        mock_llm.side_effect = _mock_llm_response(response)
        agent = VendorAuditorAgent(_config())
        result = await agent.analyze(_context())
        assert len(result["findings"]) == 1
        assert result["findings"][0]["potential_savings"] == 8500.0


# ── BaseAgent Tests ─────────────────────────────────────────────────


class TestBaseAgent:
    @pytest.mark.asyncio
    @patch("fiscalpilot.agents.base.litellm.acompletion")
    async def test_call_llm_uses_config(self, mock_llm: AsyncMock) -> None:
        mock_llm.side_effect = _mock_llm_response("test response")
        agent = CostOptimizerAgent(_config())
        result = await agent._call_llm([{"role": "user", "content": "hello"}])

        assert result == "test response"
        call_kwargs = mock_llm.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o"
        assert call_kwargs["api_key"] == "test-key"

    @pytest.mark.asyncio
    @patch("fiscalpilot.agents.base.litellm.acompletion")
    async def test_system_prompt_injected(self, mock_llm: AsyncMock) -> None:
        mock_llm.side_effect = _mock_llm_response("resp")
        agent = CostOptimizerAgent(_config())
        await agent._call_llm([{"role": "user", "content": "test"}])

        messages = mock_llm.call_args.kwargs["messages"]
        assert messages[0]["role"] == "system"
        assert "cost optimization" in messages[0]["content"].lower()

    @pytest.mark.asyncio
    @patch("fiscalpilot.agents.base.litellm.acompletion")
    async def test_llm_exception_propagates(self, mock_llm: AsyncMock) -> None:
        mock_llm.side_effect = Exception("API rate limit exceeded")
        agent = CostOptimizerAgent(_config())
        with pytest.raises(Exception, match="rate limit"):
            await agent.analyze(_context())


# ── Coordinator Tests ───────────────────────────────────────────────


def _make_dataset(n: int = 65) -> FinancialDataset:
    """Create a dataset with enough transactions for all analyzers."""
    import random

    rng = random.Random(42)
    txns = []
    base = date(2024, 1, 1)
    categories = ["supplies", "rent", "utilities", "payroll", "marketing", "equipment"]
    vendors = ["FreshCo", "CityRent", "PowerGrid", "StaffAll", "AdWorks", "EquipLease"]

    for i in range(n):
        from datetime import timedelta

        txn_date = base + timedelta(days=i * 5 % 365)
        cat_idx = i % len(categories)
        txns.append(
            Transaction(
                id=f"txn_{i:04d}",
                date=txn_date,
                amount=rng.uniform(50, 5000),
                vendor=vendors[cat_idx],
                category=categories[cat_idx],
                type=TransactionType.EXPENSE if i % 5 != 0 else TransactionType.INCOME,
                description=f"Transaction {i}",
            )
        )
    return FinancialDataset(transactions=txns)


class TestCoordinatorLocalAudit:
    """Test the local audit mode (no LLM required)."""

    @pytest.mark.asyncio
    async def test_local_audit_produces_report(self) -> None:
        config = _config()
        registry = ConnectorRegistry()

        # Mock the connector to return our dataset
        mock_connector = AsyncMock()
        mock_connector.name = "test_csv"
        mock_connector.pull = AsyncMock(return_value=_make_dataset(65))
        registry._connectors = {"test_csv": mock_connector}

        coordinator = CoordinatorAgent(config=config, connectors=registry)
        report = await coordinator.run_local_audit(_company())

        assert isinstance(report, AuditReport)
        assert report.company_name == "Joe's Diner"
        assert report.metadata.get("scan_type") == "local"
        assert report.metadata.get("llm_required") is False

    @pytest.mark.asyncio
    async def test_local_audit_runs_intelligence_engines(self) -> None:
        config = _config()
        registry = ConnectorRegistry()

        mock_connector = AsyncMock()
        mock_connector.name = "test_csv"
        mock_connector.pull = AsyncMock(return_value=_make_dataset(100))
        registry._connectors = {"test_csv": mock_connector}

        coordinator = CoordinatorAgent(config=config, connectors=registry)
        report = await coordinator.run_local_audit(_company())

        # With 100 transactions, anomaly + benchmark + cashflow + tax should run
        # (Benford's needs 50+)
        intel = report.intelligence
        assert intel.anomaly_summary != "" or intel.benchmark_summary != "" or intel.tax_summary != ""

    @pytest.mark.asyncio
    async def test_local_audit_generates_executive_summary(self) -> None:
        config = _config()
        registry = ConnectorRegistry()

        mock_connector = AsyncMock()
        mock_connector.name = "test_csv"
        mock_connector.pull = AsyncMock(return_value=_make_dataset(80))
        registry._connectors = {"test_csv": mock_connector}

        coordinator = CoordinatorAgent(config=config, connectors=registry)
        report = await coordinator.run_local_audit(_company())

        assert report.executive_summary.narrative != ""
        assert "Joe's Diner" in report.executive_summary.narrative
        assert report.executive_summary.health_score >= 0
        assert report.executive_summary.health_score <= 100

    @pytest.mark.asyncio
    async def test_local_audit_generates_proposed_actions(self) -> None:
        config = _config()
        registry = ConnectorRegistry()

        mock_connector = AsyncMock()
        mock_connector.name = "test_csv"
        mock_connector.pull = AsyncMock(return_value=_make_dataset(100))
        registry._connectors = {"test_csv": mock_connector}

        coordinator = CoordinatorAgent(config=config, connectors=registry)
        report = await coordinator.run_local_audit(_company())

        # If there are findings, there should be proposed actions
        if report.findings:
            assert len(report.proposed_actions) > 0
            assert len(report.action_items) > 0

    @pytest.mark.asyncio
    async def test_local_audit_no_llm_calls(self) -> None:
        """Ensure local audit makes zero LLM calls."""
        config = _config()
        registry = ConnectorRegistry()

        mock_connector = AsyncMock()
        mock_connector.name = "test_csv"
        mock_connector.pull = AsyncMock(return_value=_make_dataset(65))
        registry._connectors = {"test_csv": mock_connector}

        coordinator = CoordinatorAgent(config=config, connectors=registry)

        with patch("fiscalpilot.agents.base.litellm.acompletion") as mock_llm:
            await coordinator.run_local_audit(_company())
            mock_llm.assert_not_called()


class TestCoordinatorExtractFindings:
    def test_extract_valid_findings(self) -> None:
        config = _config()
        registry = ConnectorRegistry()
        coordinator = CoordinatorAgent(config=config, connectors=registry)

        raw = {
            "findings": [
                {
                    "title": "Test finding",
                    "category": "cost_optimization",
                    "severity": "high",
                    "description": "A test finding.",
                    "evidence": ["ev1"],
                    "potential_savings": 1000.0,
                    "confidence": 0.9,
                    "recommendation": "Do the thing.",
                }
            ]
        }
        findings = coordinator._extract_findings(raw, "test_agent")
        assert len(findings) == 1
        assert findings[0].title == "Test finding"
        assert findings[0].severity == Severity.HIGH
        assert findings[0].potential_savings == 1000.0

    def test_extract_handles_invalid_finding(self) -> None:
        config = _config()
        registry = ConnectorRegistry()
        coordinator = CoordinatorAgent(config=config, connectors=registry)

        # With totally invalid category value, it should skip the finding
        raw = {"findings": [{"category": "not_a_valid_category_at_all"}]}
        findings = coordinator._extract_findings(raw, "test_agent")
        assert len(findings) == 0  # Should skip, not crash

    def test_deduplicate_findings(self) -> None:
        config = _config()
        registry = ConnectorRegistry()
        coordinator = CoordinatorAgent(config=config, connectors=registry)

        from fiscalpilot.models.report import Finding

        findings = [
            Finding(
                id="f1",
                title="Duplicate Payment",
                category=FindingCategory.COST_OPTIMIZATION,
                severity=Severity.HIGH,
                description="d1",
            ),
            Finding(
                id="f2",
                title="duplicate payment",
                category=FindingCategory.COST_OPTIMIZATION,
                severity=Severity.HIGH,
                description="d2",
            ),
            Finding(
                id="f3",
                title="Different Finding",
                category=FindingCategory.RISK_DETECTION,
                severity=Severity.MEDIUM,
                description="d3",
            ),
        ]
        deduped = coordinator._deduplicate_findings(findings)
        assert len(deduped) == 2


class TestCoordinatorProposedActions:
    def test_generates_proposed_actions(self) -> None:
        config = _config()
        registry = ConnectorRegistry()
        coordinator = CoordinatorAgent(config=config, connectors=registry)

        from fiscalpilot.models.report import Finding

        findings = [
            Finding(
                id="f1",
                title="Unused subscription",
                category=FindingCategory.UNUSED_SUBSCRIPTION,
                severity=Severity.MEDIUM,
                description="Unused sub",
                potential_savings=1200.0,
                recommendation="Cancel it.",
            ),
            Finding(
                id="f2",
                title="Vendor overcharge",
                category=FindingCategory.VENDOR_OVERCHARGE,
                severity=Severity.HIGH,
                description="Overcharged",
                potential_savings=5000.0,
                recommendation="Renegotiate.",
            ),
        ]
        actions = coordinator._generate_proposed_actions(findings, _company())
        assert len(actions) == 2
        # Check that approval levels are assigned correctly
        from fiscalpilot.models.actions import ActionType, ApprovalLevel

        sub_action = [a for a in actions if "Unused" in a.title or "Cancel" in a.title][0]
        assert sub_action.action_type == ActionType.CANCEL_SUBSCRIPTION
        assert sub_action.approval_level == ApprovalLevel.RED


class TestCoordinatorFullAudit:
    @pytest.mark.asyncio
    @patch("fiscalpilot.agents.base.litellm.acompletion")
    async def test_full_audit_with_mocked_llm(self, mock_llm: AsyncMock) -> None:
        """Full run_audit with mocked LLM — verifies the complete pipeline."""
        # Each agent call + exec summary = multiple LLM calls
        responses = [
            _cost_optimizer_llm_response(),
            _risk_detector_llm_response(),
            _margin_optimizer_llm_response(),
            json.dumps([]),  # cost cutter
            json.dumps([]),  # revenue analyzer
            json.dumps([]),  # vendor auditor
            "FiscalPilot identified $15,288 in savings for Joe's Diner.",  # exec summary
        ]

        def make_mock_response(content: str) -> MagicMock:
            resp = MagicMock()
            resp.choices = [MagicMock()]
            resp.choices[0].message.content = content
            return resp

        mock_llm.side_effect = [make_mock_response(r) for r in responses]

        config = _config()
        registry = ConnectorRegistry()

        mock_connector = AsyncMock()
        mock_connector.name = "test_csv"
        mock_connector.pull = AsyncMock(return_value=_make_dataset(65))
        registry._connectors = {"test_csv": mock_connector}

        coordinator = CoordinatorAgent(config=config, connectors=registry)
        report = await coordinator.run_audit(_company())

        assert isinstance(report, AuditReport)
        assert report.company_name == "Joe's Diner"
        assert len(report.findings) > 0  # Should have intelligence + agent findings
        assert report.executive_summary.narrative != ""
