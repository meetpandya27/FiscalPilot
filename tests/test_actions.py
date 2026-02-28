"""
Tests for the action models (v0.4).
"""

from fiscalpilot.models.actions import (
    DEFAULT_APPROVAL_MAP,
    ActionStatus,
    ActionStep,
    ActionType,
    ApprovalDecision,
    ApprovalLevel,
    ApprovalRule,
    ExecutionResult,
    ProposedAction,
)


class TestActionStatus:
    def test_values(self) -> None:
        assert ActionStatus.PROPOSED == "proposed"
        assert ActionStatus.APPROVED == "approved"
        assert ActionStatus.REJECTED == "rejected"
        assert ActionStatus.EXECUTING == "executing"
        assert ActionStatus.COMPLETED == "completed"
        assert ActionStatus.FAILED == "failed"
        assert ActionStatus.ROLLED_BACK == "rolled_back"


class TestApprovalLevel:
    def test_values(self) -> None:
        assert ApprovalLevel.GREEN == "green"
        assert ApprovalLevel.YELLOW == "yellow"
        assert ApprovalLevel.RED == "red"
        assert ApprovalLevel.CRITICAL == "critical"


class TestActionType:
    def test_green_types(self) -> None:
        assert DEFAULT_APPROVAL_MAP[ActionType.CATEGORIZE_TRANSACTION] == ApprovalLevel.GREEN
        assert DEFAULT_APPROVAL_MAP[ActionType.TAG_EXPENSE] == ApprovalLevel.GREEN
        assert DEFAULT_APPROVAL_MAP[ActionType.GENERATE_REPORT] == ApprovalLevel.GREEN

    def test_yellow_types(self) -> None:
        assert DEFAULT_APPROVAL_MAP[ActionType.SEND_REMINDER] == ApprovalLevel.YELLOW
        assert DEFAULT_APPROVAL_MAP[ActionType.UPDATE_CATEGORY_BULK] == ApprovalLevel.YELLOW

    def test_red_types(self) -> None:
        assert DEFAULT_APPROVAL_MAP[ActionType.CANCEL_SUBSCRIPTION] == ApprovalLevel.RED
        assert DEFAULT_APPROVAL_MAP[ActionType.PAY_INVOICE] == ApprovalLevel.RED

    def test_critical_types(self) -> None:
        assert DEFAULT_APPROVAL_MAP[ActionType.CHANGE_PAYROLL] == ApprovalLevel.CRITICAL
        assert DEFAULT_APPROVAL_MAP[ActionType.MODIFY_TAX_FILING] == ApprovalLevel.CRITICAL


class TestProposedAction:
    def test_creation(self) -> None:
        action = ProposedAction(
            id="act_001",
            title="Cancel unused Slack subscription",
            description="3 seats unused for 6+ months",
            action_type=ActionType.CANCEL_SUBSCRIPTION,
            approval_level=ApprovalLevel.RED,
            estimated_savings=1080.0,
            finding_ids=["f1"],
        )
        assert action.status == ActionStatus.PROPOSED
        assert action.estimated_savings == 1080.0
        assert action.is_actionable is False
        assert action.is_terminal is False

    def test_approved_is_actionable(self) -> None:
        action = ProposedAction(
            id="act_002",
            title="Tag transactions",
            description="Categorize 20 transactions",
            status=ActionStatus.APPROVED,
        )
        assert action.is_actionable is True

    def test_terminal_states(self) -> None:
        for status in [ActionStatus.COMPLETED, ActionStatus.FAILED, ActionStatus.REJECTED, ActionStatus.ROLLED_BACK]:
            action = ProposedAction(id="act_t", title="T", description="T", status=status)
            assert action.is_terminal is True

    def test_non_terminal_states(self) -> None:
        for status in [ActionStatus.PROPOSED, ActionStatus.APPROVED, ActionStatus.EXECUTING]:
            action = ProposedAction(id="act_nt", title="T", description="T", status=status)
            assert action.is_terminal is False

    def test_steps(self) -> None:
        action = ProposedAction(
            id="act_steps",
            title="Multi-step action",
            description="Test",
            steps=[
                ActionStep(order=1, description="Step 1", reversible=False),
                ActionStep(order=2, description="Step 2", reversible=True),
            ],
        )
        assert len(action.steps) == 2
        assert action.steps[0].reversible is False
        assert action.steps[1].reversible is True


class TestExecutionResult:
    def test_success(self) -> None:
        result = ExecutionResult(
            action_id="act_001",
            status=ActionStatus.COMPLETED,
            summary="Done",
        )
        assert result.succeeded is True
        assert result.error is None

    def test_failure(self) -> None:
        result = ExecutionResult(
            action_id="act_001",
            status=ActionStatus.FAILED,
            summary="Failed",
            error="Something went wrong",
        )
        assert result.succeeded is False
        assert result.error == "Something went wrong"

    def test_dry_run_flag(self) -> None:
        result = ExecutionResult(
            action_id="act_001",
            status=ActionStatus.COMPLETED,
            summary="Preview",
            dry_run=True,
        )
        assert result.dry_run is True


class TestApprovalRule:
    def test_single_approver(self) -> None:
        rule = ApprovalRule(
            level=ApprovalLevel.RED,
            approver_emails=["cfo@co.com"],
            require_all=False,
            timeout_hours=24,
        )
        assert rule.timeout_hours == 24
        assert not rule.require_all

    def test_multi_party(self) -> None:
        rule = ApprovalRule(
            level=ApprovalLevel.CRITICAL,
            approver_emails=["cfo@co.com", "ceo@co.com"],
            require_all=True,
        )
        assert rule.require_all
        assert len(rule.approver_emails) == 2


class TestApprovalDecision:
    def test_creation(self) -> None:
        d = ApprovalDecision(
            action_id="act_001",
            decision="approved",
            decided_by="cfo@co.com",
            reason="Looks good",
        )
        assert d.decision == "approved"
        assert d.decided_by == "cfo@co.com"
