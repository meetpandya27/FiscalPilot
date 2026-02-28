"""
Tests for the approval gate (v0.4 human-in-the-loop).
"""

from fiscalpilot.execution.approval import ApprovalGate
from fiscalpilot.models.actions import (
    ActionStatus,
    ActionType,
    ApprovalLevel,
    ApprovalRule,
    ProposedAction,
)


def _make_action(
    action_id: str = "act_001",
    level: ApprovalLevel = ApprovalLevel.RED,
    action_type: ActionType = ActionType.CUSTOM,
    savings: float = 1000.0,
) -> ProposedAction:
    return ProposedAction(
        id=action_id,
        title=f"Test action {action_id}",
        description="Test",
        action_type=action_type,
        approval_level=level,
        estimated_savings=savings,
    )


class TestApprovalGateAutoApprove:
    def test_green_auto_approved(self) -> None:
        gate = ApprovalGate()
        action = _make_action(level=ApprovalLevel.GREEN)
        auto, pending = gate.process([action])
        assert len(auto) == 1
        assert len(pending) == 0
        assert action.status == ActionStatus.APPROVED
        assert action.approved_by == "system:auto"

    def test_yellow_auto_approved_with_notification(self) -> None:
        gate = ApprovalGate()
        action = _make_action(level=ApprovalLevel.YELLOW)
        auto, pending = gate.process([action])
        assert len(auto) == 1
        assert len(pending) == 0
        assert action.status == ActionStatus.APPROVED
        # Should have a notification queued
        assert len(gate.notifications) == 1
        assert "act_001" in gate.notifications[0]["action_id"]

    def test_red_needs_approval(self) -> None:
        gate = ApprovalGate()
        action = _make_action(level=ApprovalLevel.RED)
        auto, pending = gate.process([action])
        assert len(auto) == 0
        assert len(pending) == 1
        assert action.status == ActionStatus.PROPOSED

    def test_critical_needs_approval(self) -> None:
        gate = ApprovalGate()
        action = _make_action(level=ApprovalLevel.CRITICAL)
        auto, pending = gate.process([action])
        assert len(auto) == 0
        assert len(pending) == 1


class TestApprovalGateDisabled:
    def test_all_auto_approved_when_disabled(self) -> None:
        gate = ApprovalGate(require_approval=False)
        actions = [
            _make_action("a1", ApprovalLevel.GREEN),
            _make_action("a2", ApprovalLevel.YELLOW),
            _make_action("a3", ApprovalLevel.RED),
            _make_action("a4", ApprovalLevel.CRITICAL),
        ]
        auto, pending = gate.process(actions)
        assert len(auto) == 4
        assert len(pending) == 0
        for a in actions:
            assert a.status == ActionStatus.APPROVED


class TestApproveReject:
    def test_approve_action(self) -> None:
        gate = ApprovalGate()
        action = _make_action(level=ApprovalLevel.RED)
        gate.process([action])
        approved = gate.approve(["act_001"], approved_by="cfo@co.com", reason="Looks good")
        assert len(approved) == 1
        assert action.status == ActionStatus.APPROVED
        assert action.approved_by == "cfo@co.com"

    def test_reject_action(self) -> None:
        gate = ApprovalGate()
        action = _make_action(level=ApprovalLevel.RED)
        gate.process([action])
        rejected = gate.reject(["act_001"], rejected_by="cfo@co.com", reason="Not needed")
        assert len(rejected) == 1
        assert action.status == ActionStatus.REJECTED

    def test_approve_nonexistent(self) -> None:
        gate = ApprovalGate()
        approved = gate.approve(["nonexistent"])
        assert len(approved) == 0

    def test_reject_already_approved(self) -> None:
        gate = ApprovalGate()
        action = _make_action(level=ApprovalLevel.RED)
        gate.process([action])
        gate.approve(["act_001"])
        # Can't reject an already-approved action
        rejected = gate.reject(["act_001"])
        assert len(rejected) == 0


class TestMultiPartyApproval:
    def test_requires_all_approvers(self) -> None:
        rule = ApprovalRule(
            level=ApprovalLevel.CRITICAL,
            approver_emails=["cfo@co.com", "ceo@co.com"],
            require_all=True,
        )
        gate = ApprovalGate(rules=[rule])
        action = _make_action(level=ApprovalLevel.CRITICAL)
        gate.process([action])

        # First approver — not enough
        approved = gate.approve(["act_001"], approved_by="cfo@co.com")
        assert len(approved) == 0
        assert action.status == ActionStatus.PROPOSED

        # Second approver — now approved
        approved = gate.approve(["act_001"], approved_by="ceo@co.com")
        assert len(approved) == 1
        assert action.status == ActionStatus.APPROVED


class TestAuditTrail:
    def test_decisions_logged(self) -> None:
        gate = ApprovalGate()
        actions = [
            _make_action("a1", ApprovalLevel.GREEN),
            _make_action("a2", ApprovalLevel.RED),
        ]
        gate.process(actions)
        gate.approve(["a2"], approved_by="user")

        decisions = gate.decisions
        assert len(decisions) == 2  # green auto + red manual
        assert decisions[0].action_id == "a1"
        assert decisions[0].decision == "approved"
        assert decisions[1].action_id == "a2"
        assert decisions[1].decision == "approved"


class TestMixedBatch:
    def test_mixed_levels(self) -> None:
        gate = ApprovalGate()
        actions = [
            _make_action("a1", ApprovalLevel.GREEN, savings=100),
            _make_action("a2", ApprovalLevel.YELLOW, savings=500),
            _make_action("a3", ApprovalLevel.RED, savings=5000),
            _make_action("a4", ApprovalLevel.CRITICAL, savings=50000),
        ]
        auto, pending = gate.process(actions)
        assert len(auto) == 2  # green + yellow
        assert len(pending) == 2  # red + critical
        assert len(gate.pending_actions) == 2
