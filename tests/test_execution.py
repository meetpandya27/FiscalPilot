"""
Tests for the execution engine (v0.4).
"""

import pytest

from fiscalpilot.execution.approval import ApprovalGate
from fiscalpilot.execution.engine import ExecutionEngine
from fiscalpilot.execution.executors.base import (
    BaseExecutor,
    CategorizationExecutor,
    LogOnlyExecutor,
    NotificationExecutor,
)
from fiscalpilot.models.actions import (
    ActionStatus,
    ActionStep,
    ActionType,
    ApprovalLevel,
    ExecutionResult,
    ProposedAction,
)


def _make_action(
    action_id: str = "act_001",
    level: ApprovalLevel = ApprovalLevel.GREEN,
    action_type: ActionType = ActionType.TAG_EXPENSE,
    status: ActionStatus = ActionStatus.APPROVED,
    savings: float = 100.0,
    **params,
) -> ProposedAction:
    return ProposedAction(
        id=action_id,
        title=f"Test action {action_id}",
        description="Test action",
        action_type=action_type,
        approval_level=level,
        status=status,
        estimated_savings=savings,
        parameters=params,
    )


class TestLogOnlyExecutor:
    @pytest.mark.asyncio
    async def test_execute(self) -> None:
        executor = LogOnlyExecutor()
        action = _make_action()
        result = await executor.execute(action, dry_run=False)
        assert result.succeeded
        assert "[LOGGED]" in result.summary

    @pytest.mark.asyncio
    async def test_dry_run(self) -> None:
        executor = LogOnlyExecutor()
        action = _make_action()
        result = await executor.execute(action, dry_run=True)
        assert result.succeeded
        assert result.dry_run
        assert "[DRY-RUN]" in result.summary

    @pytest.mark.asyncio
    async def test_validate_always_passes(self) -> None:
        executor = LogOnlyExecutor()
        action = _make_action()
        valid, err = await executor.validate(action)
        assert valid
        assert err == ""


class TestCategorizationExecutor:
    @pytest.mark.asyncio
    async def test_execute_categorize(self) -> None:
        executor = CategorizationExecutor()
        action = _make_action(
            action_type=ActionType.CATEGORIZE_TRANSACTION,
            transaction_ids=["tx1", "tx2", "tx3"],
            category="office_supplies",
        )
        result = await executor.execute(action, dry_run=False)
        assert result.succeeded
        assert "3 transaction(s)" in result.summary
        assert result.rollback_available

    @pytest.mark.asyncio
    async def test_dry_run_categorize(self) -> None:
        executor = CategorizationExecutor()
        action = _make_action(
            action_type=ActionType.CATEGORIZE_TRANSACTION,
            transaction_ids=["tx1"],
            category="meals",
        )
        result = await executor.execute(action, dry_run=True)
        assert result.succeeded
        assert result.dry_run
        assert "Would categorize" in result.summary

    @pytest.mark.asyncio
    async def test_validate_missing_params(self) -> None:
        executor = CategorizationExecutor()
        action = _make_action(action_type=ActionType.CATEGORIZE_TRANSACTION)
        # No transaction_ids or category in params
        valid, err = await executor.validate(action)
        assert not valid
        assert "Missing" in err

    @pytest.mark.asyncio
    async def test_can_handle(self) -> None:
        executor = CategorizationExecutor()
        assert executor.can_handle(_make_action(action_type=ActionType.CATEGORIZE_TRANSACTION))
        assert executor.can_handle(_make_action(action_type=ActionType.TAG_EXPENSE))
        assert executor.can_handle(_make_action(action_type=ActionType.UPDATE_CATEGORY_BULK))
        assert not executor.can_handle(_make_action(action_type=ActionType.PAY_INVOICE))


class TestNotificationExecutor:
    @pytest.mark.asyncio
    async def test_execute_notification(self) -> None:
        executor = NotificationExecutor()
        action = _make_action(
            action_type=ActionType.SEND_REMINDER,
            recipients=["user@co.com"],
            channel="email",
            message="Invoice overdue",
        )
        result = await executor.execute(action, dry_run=False)
        assert result.succeeded
        assert "1 recipient(s)" in result.summary
        assert not result.rollback_available

    @pytest.mark.asyncio
    async def test_validate_missing_recipients(self) -> None:
        executor = NotificationExecutor()
        action = _make_action(action_type=ActionType.SEND_REMINDER)
        valid, err = await executor.validate(action)
        assert not valid


class TestExecutionEngine:
    @pytest.mark.asyncio
    async def test_execute_approved(self) -> None:
        engine = ExecutionEngine(dry_run_by_default=False)
        action = _make_action(status=ActionStatus.APPROVED)
        results = await engine.execute([action])
        assert len(results) == 1
        assert results[0].succeeded

    @pytest.mark.asyncio
    async def test_skip_unapproved(self) -> None:
        engine = ExecutionEngine()
        action = _make_action(status=ActionStatus.PROPOSED)
        results = await engine.execute([action])
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_dry_run_default(self) -> None:
        engine = ExecutionEngine(dry_run_by_default=True)
        action = _make_action(status=ActionStatus.APPROVED)
        results = await engine.execute([action])
        assert len(results) == 1
        assert results[0].dry_run

    @pytest.mark.asyncio
    async def test_rate_limiting(self) -> None:
        engine = ExecutionEngine(max_actions_per_run=2, dry_run_by_default=False)
        actions = [_make_action(f"act_{i}", status=ActionStatus.APPROVED) for i in range(5)]
        results = await engine.execute(actions)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_registered_executor(self) -> None:
        engine = ExecutionEngine(dry_run_by_default=False)
        engine.register_executor(CategorizationExecutor())
        action = _make_action(
            action_type=ActionType.CATEGORIZE_TRANSACTION,
            status=ActionStatus.APPROVED,
            transaction_ids=["tx1"],
            category="travel",
        )
        results = await engine.execute([action])
        assert len(results) == 1
        assert results[0].succeeded
        assert "1 transaction(s)" in results[0].summary

    @pytest.mark.asyncio
    async def test_fallback_to_log_only(self) -> None:
        engine = ExecutionEngine(dry_run_by_default=False)
        action = _make_action(
            action_type=ActionType.PAY_INVOICE,
            status=ActionStatus.APPROVED,
        )
        results = await engine.execute([action])
        # Falls back to LogOnlyExecutor
        assert results[0].succeeded
        assert "[LOGGED]" in results[0].summary

    @pytest.mark.asyncio
    async def test_execution_log(self) -> None:
        engine = ExecutionEngine(dry_run_by_default=False)
        actions = [
            _make_action("a1", status=ActionStatus.APPROVED),
            _make_action("a2", status=ActionStatus.APPROVED),
        ]
        await engine.execute(actions)
        assert len(engine.execution_log) == 2

    def test_summary(self) -> None:
        engine = ExecutionEngine()
        engine.register_executor(CategorizationExecutor())
        s = engine.summary()
        assert "categorization" in s["registered_executors"]
        assert s["dry_run_by_default"] is True

    @pytest.mark.asyncio
    async def test_propose_and_approve_flow(self) -> None:
        gate = ApprovalGate()
        engine = ExecutionEngine(approval_gate=gate, dry_run_by_default=False)
        engine.register_executor(CategorizationExecutor())

        action = _make_action(
            action_type=ActionType.CATEGORIZE_TRANSACTION,
            level=ApprovalLevel.RED,
            status=ActionStatus.PROPOSED,
            transaction_ids=["tx1"],
            category="meals",
        )

        # Submit to approval gate
        auto, pending = engine.propose([action])
        assert len(auto) == 0
        assert len(pending) == 1

        # Approve
        approved = engine.approve(["act_001"], approved_by="admin")
        assert len(approved) == 1

        # Execute
        results = await engine.execute(approved)
        assert len(results) == 1
        assert results[0].succeeded


class TestEndToEndFlow:
    """Integration-style test for the full propose → approve → execute → rollback cycle."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self) -> None:
        gate = ApprovalGate()
        engine = ExecutionEngine(
            approval_gate=gate,
            executors=[CategorizationExecutor(), NotificationExecutor()],
            dry_run_by_default=False,
        )

        # Create actions at different levels
        green_action = _make_action(
            "green_1",
            level=ApprovalLevel.GREEN,
            action_type=ActionType.TAG_EXPENSE,
            status=ActionStatus.PROPOSED,
            transaction_ids=["tx1"],
            category="supplies",
        )
        red_action = _make_action(
            "red_1",
            level=ApprovalLevel.RED,
            action_type=ActionType.CANCEL_SUBSCRIPTION,
            status=ActionStatus.PROPOSED,
            savings=1200.0,
        )

        # Process through gate
        auto, pending = engine.propose([green_action, red_action])
        assert len(auto) == 1  # Green auto-approved
        assert len(pending) == 1  # Red pending
        assert green_action.status == ActionStatus.APPROVED
        assert red_action.status == ActionStatus.PROPOSED

        # Execute auto-approved
        results = await engine.execute(auto)
        assert len(results) == 1
        assert results[0].succeeded

        # Approve red action
        engine.approve(["red_1"], approved_by="cfo@co.com")
        assert red_action.status == ActionStatus.APPROVED

        # Execute red action
        results = await engine.execute([red_action])
        assert len(results) == 1
        assert results[0].succeeded

        # Check full execution log
        assert len(engine.execution_log) == 2
