"""
Execution engine — orchestrates the execution of approved actions.

The engine:
  1. Takes approved actions from the approval gate.
  2. Routes each action to the correct executor.
  3. Supports dry-run (preview without side effects).
  4. Enforces rate limits.
  5. Logs all results to an immutable audit trail.
  6. Supports rollback for reversible actions.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fiscalpilot.execution.approval import ApprovalGate
from fiscalpilot.execution.executors.base import BaseExecutor, LogOnlyExecutor
from fiscalpilot.models.actions import (
    ActionStatus,
    ExecutionResult,
    ProposedAction,
)

logger = logging.getLogger("fiscalpilot.execution.engine")


class ExecutionEngine:
    """Core execution engine for FiscalPilot's action pipeline.

    Manages:
    - Executor registration and routing
    - Approval gate integration
    - Dry-run and real execution
    - Rate limiting
    - Audit trail
    """

    def __init__(
        self,
        approval_gate: ApprovalGate | None = None,
        executors: list[BaseExecutor] | None = None,
        max_actions_per_run: int = 50,
        dry_run_by_default: bool = True,
    ) -> None:
        self._approval_gate = approval_gate or ApprovalGate()
        self._executors: list[BaseExecutor] = executors or []
        self._fallback_executor = LogOnlyExecutor()
        self._max_actions_per_run = max_actions_per_run
        self._dry_run_by_default = dry_run_by_default

        # Audit trail
        self._execution_log: list[ExecutionResult] = []
        self._executed_results: dict[str, ExecutionResult] = {}  # action_id → result

    @property
    def approval_gate(self) -> ApprovalGate:
        return self._approval_gate

    @property
    def execution_log(self) -> list[ExecutionResult]:
        """Full immutable execution log."""
        return list(self._execution_log)

    @property
    def executors(self) -> list[BaseExecutor]:
        return list(self._executors)

    def register_executor(self, executor: BaseExecutor) -> None:
        """Register an executor plugin."""
        self._executors.append(executor)
        logger.info("Registered executor: %s", executor.name)

    def get_executor(self, action: ProposedAction) -> BaseExecutor:
        """Find the best executor for a given action.

        Falls back to LogOnlyExecutor if no match.
        """
        for executor in self._executors:
            if executor.can_handle(action):
                return executor
        return self._fallback_executor

    def propose(self, actions: list[ProposedAction]) -> tuple[list[ProposedAction], list[ProposedAction]]:
        """Submit actions to the approval gate.

        Returns:
            (auto_approved, needs_approval) — auto_approved can be executed immediately.
        """
        return self._approval_gate.process(actions)

    def approve(
        self,
        action_ids: list[str],
        approved_by: str = "user",
        reason: str = "",
    ) -> list[ProposedAction]:
        """Approve pending actions through the gate."""
        return self._approval_gate.approve(action_ids, approved_by, reason)

    def reject(
        self,
        action_ids: list[str],
        rejected_by: str = "user",
        reason: str = "",
    ) -> list[ProposedAction]:
        """Reject pending actions."""
        return self._approval_gate.reject(action_ids, rejected_by, reason)

    async def execute(
        self,
        actions: list[ProposedAction],
        dry_run: bool | None = None,
    ) -> list[ExecutionResult]:
        """Execute a list of approved actions.

        Args:
            actions: Actions that have been approved (status=APPROVED).
            dry_run: Override dry-run setting. None uses engine default.

        Returns:
            List of ExecutionResults.
        """
        is_dry_run = dry_run if dry_run is not None else self._dry_run_by_default
        results: list[ExecutionResult] = []

        # Filter to only approved actions
        actionable = [a for a in actions if a.status == ActionStatus.APPROVED]
        if not actionable:
            logger.warning("No approved actions to execute.")
            return results

        # Enforce rate limit
        if len(actionable) > self._max_actions_per_run:
            logger.warning(
                "Rate limit: only executing %d of %d actions",
                self._max_actions_per_run,
                len(actionable),
            )
            actionable = actionable[: self._max_actions_per_run]

        for action in actionable:
            executor = self.get_executor(action)

            # Validate
            is_valid, error_msg = await executor.validate(action)
            if not is_valid:
                result = ExecutionResult(
                    action_id=action.id,
                    status=ActionStatus.FAILED,
                    summary=f"Validation failed: {error_msg}",
                    error=error_msg,
                    finished_at=datetime.utcnow(),
                    dry_run=is_dry_run,
                )
                action.status = ActionStatus.FAILED
                results.append(result)
                self._execution_log.append(result)
                continue

            # Execute
            action.status = ActionStatus.EXECUTING
            action.executed_at = datetime.utcnow()

            try:
                result = await executor.execute(action, dry_run=is_dry_run)
                action.status = result.status
                if result.status == ActionStatus.COMPLETED:
                    action.completed_at = datetime.utcnow()
            except Exception as e:
                logger.error("Executor %s failed on action %s: %s", executor.name, action.id, e)
                result = ExecutionResult(
                    action_id=action.id,
                    status=ActionStatus.FAILED,
                    summary=f"Execution error: {e}",
                    error=str(e),
                    finished_at=datetime.utcnow(),
                    dry_run=is_dry_run,
                )
                action.status = ActionStatus.FAILED

            results.append(result)
            self._execution_log.append(result)
            self._executed_results[action.id] = result

        logger.info(
            "Execution complete: %d actions, %d succeeded, %d failed (dry_run=%s)",
            len(results),
            sum(1 for r in results if r.succeeded),
            sum(1 for r in results if r.status == ActionStatus.FAILED),
            is_dry_run,
        )

        return results

    async def execute_approved(self, dry_run: bool | None = None) -> list[ExecutionResult]:
        """Execute all currently approved actions from the approval gate.

        Convenience method that gathers approved actions from the gate
        and executes them in one pass.
        """
        approved = [a for a in self._approval_gate._pending.values() if a.status == ActionStatus.APPROVED]
        return await self.execute(approved, dry_run=dry_run)

    async def rollback(self, action_ids: list[str]) -> list[ExecutionResult]:
        """Roll back previously executed actions.

        Only works for actions whose executor supports rollback.
        """
        results: list[ExecutionResult] = []

        for action_id in action_ids:
            prev_result = self._executed_results.get(action_id)
            if prev_result is None:
                logger.warning("No execution record for action %s", action_id)
                continue
            if not prev_result.rollback_available:
                logger.warning("Action %s does not support rollback", action_id)
                results.append(
                    ExecutionResult(
                        action_id=action_id,
                        status=ActionStatus.FAILED,
                        summary="Rollback not available for this action.",
                        error="rollback_not_available",
                    )
                )
                continue

            # Find the action in pending
            action = self._approval_gate.get_action(action_id)
            if action is None:
                logger.warning("Action %s not found", action_id)
                continue

            executor = self.get_executor(action)
            try:
                result = await executor.rollback(action, prev_result)
                action.status = result.status
                results.append(result)
                self._execution_log.append(result)
            except Exception as e:
                logger.error("Rollback failed for action %s: %s", action_id, e)
                results.append(
                    ExecutionResult(
                        action_id=action_id,
                        status=ActionStatus.FAILED,
                        summary=f"Rollback error: {e}",
                        error=str(e),
                    )
                )

        return results

    def summary(self) -> dict[str, Any]:
        """Summary of the engine's current state."""
        return {
            "registered_executors": [e.name for e in self._executors],
            "pending_actions": len(self._approval_gate.pending_actions),
            "total_executed": len(self._execution_log),
            "successful": sum(1 for r in self._execution_log if r.succeeded),
            "failed": sum(1 for r in self._execution_log if r.status == ActionStatus.FAILED),
            "dry_run_by_default": self._dry_run_by_default,
            "max_actions_per_run": self._max_actions_per_run,
        }
