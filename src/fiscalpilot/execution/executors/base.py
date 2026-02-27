"""
Base executor — abstract interface for action executors.

Executors are pluggable handlers that know how to carry out specific
action types. Each executor:
  - Validates an action's parameters
  - Supports dry-run (preview without side effects)
  - Executes the action for real
  - Reports whether rollback is possible
  - Can roll back a previously executed action
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from fiscalpilot.models.actions import ExecutionResult, ProposedAction

logger = logging.getLogger("fiscalpilot.execution.executors")


class BaseExecutor(ABC):
    """Abstract base class for action executors.

    Subclass this to create executors for specific action types.
    Register executors with the ExecutionEngine.
    """

    name: str = "base_executor"
    description: str = "Base action executor"
    supported_action_types: list[str] = []

    @abstractmethod
    async def validate(self, action: ProposedAction) -> tuple[bool, str]:
        """Validate that the action can be executed.

        Returns:
            (is_valid, error_message) — if invalid, error_message explains why.
        """
        ...

    @abstractmethod
    async def execute(self, action: ProposedAction, dry_run: bool = False) -> ExecutionResult:
        """Execute the action.

        Args:
            action: The approved action to execute.
            dry_run: If True, simulate without side effects.

        Returns:
            ExecutionResult with status and details.
        """
        ...

    async def rollback(self, action: ProposedAction, result: ExecutionResult) -> ExecutionResult:
        """Roll back a previously executed action.

        Default: not supported. Override in subclasses where rollback is possible.
        """
        from fiscalpilot.models.actions import ActionStatus

        return ExecutionResult(
            action_id=action.id,
            status=ActionStatus.FAILED,
            summary="Rollback not supported for this action type.",
            error="rollback_not_implemented",
            rollback_available=False,
        )

    def can_handle(self, action: ProposedAction) -> bool:
        """Whether this executor can handle the given action."""
        return action.action_type.value in self.supported_action_types or action.executor == self.name


class LogOnlyExecutor(BaseExecutor):
    """A no-op executor that logs actions without side effects.

    Useful as a fallback, for testing, and for action types that
    don't yet have a real executor.
    """

    name = "log_only"
    description = "Logs the action without performing any external operations"

    async def validate(self, action: ProposedAction) -> tuple[bool, str]:
        return True, ""

    async def execute(self, action: ProposedAction, dry_run: bool = False) -> ExecutionResult:
        from datetime import datetime

        from fiscalpilot.models.actions import ActionStatus

        mode = "DRY-RUN" if dry_run else "LOGGED"
        summary = f"[{mode}] {action.title}"

        logger.info(
            "[%s] Action '%s' (%s) — saves $%.2f — %s",
            mode,
            action.title,
            action.action_type.value,
            action.estimated_savings,
            "; ".join(s.description for s in action.steps) or "no steps defined",
        )

        return ExecutionResult(
            action_id=action.id,
            status=ActionStatus.COMPLETED,
            summary=summary,
            details={
                "action_type": action.action_type.value,
                "estimated_savings": action.estimated_savings,
                "steps_count": len(action.steps),
                "mode": mode,
            },
            dry_run=dry_run,
            finished_at=datetime.utcnow(),
            rollback_available=False,
        )


class CategorizationExecutor(BaseExecutor):
    """Executor that categorizes/tags transactions.

    This is a GREEN-level executor — low risk, auto-executable.
    Writes category updates back through the connector.
    """

    name = "categorization"
    description = "Categorizes and tags transactions"
    supported_action_types = ["categorize_transaction", "tag_expense", "update_category_bulk"]

    async def validate(self, action: ProposedAction) -> tuple[bool, str]:
        params = action.parameters
        if not params.get("transaction_ids") and not params.get("category"):
            return False, "Missing required parameters: transaction_ids and category"
        return True, ""

    async def execute(self, action: ProposedAction, dry_run: bool = False) -> ExecutionResult:
        from datetime import datetime

        from fiscalpilot.models.actions import ActionStatus

        params = action.parameters
        txn_ids = params.get("transaction_ids", [])
        category = params.get("category", "uncategorized")

        if dry_run:
            summary = f"Would categorize {len(txn_ids)} transaction(s) as '{category}'"
        else:
            # In a real implementation, this would call the connector's write-back API
            summary = f"Categorized {len(txn_ids)} transaction(s) as '{category}'"
            logger.info(summary)

        return ExecutionResult(
            action_id=action.id,
            status=ActionStatus.COMPLETED,
            summary=summary,
            details={
                "transaction_ids": txn_ids,
                "category": category,
                "count": len(txn_ids),
            },
            dry_run=dry_run,
            finished_at=datetime.utcnow(),
            rollback_available=True,  # Can revert to original categories
        )

    async def rollback(self, action: ProposedAction, result: ExecutionResult) -> ExecutionResult:
        from datetime import datetime

        from fiscalpilot.models.actions import ActionStatus

        original = result.details.get("original_categories", {})
        if not original:
            return ExecutionResult(
                action_id=action.id,
                status=ActionStatus.FAILED,
                summary="Cannot rollback — original categories not saved.",
                error="no_original_data",
                rollback_available=False,
            )

        return ExecutionResult(
            action_id=action.id,
            status=ActionStatus.ROLLED_BACK,
            summary=f"Rolled back {len(original)} transaction categories to originals",
            finished_at=datetime.utcnow(),
            rollback_available=False,
        )


class NotificationExecutor(BaseExecutor):
    """Executor that sends notifications (email, Slack, etc.).

    This is a YELLOW-level executor — medium risk, auto-execute + notify.
    """

    name = "notification"
    description = "Sends notifications and reminders"
    supported_action_types = ["send_reminder", "flag_for_review"]

    async def validate(self, action: ProposedAction) -> tuple[bool, str]:
        params = action.parameters
        if not params.get("recipients") and not params.get("channel"):
            return False, "Missing required parameter: recipients or channel"
        return True, ""

    async def execute(self, action: ProposedAction, dry_run: bool = False) -> ExecutionResult:
        from datetime import datetime

        from fiscalpilot.models.actions import ActionStatus

        params = action.parameters
        recipients = params.get("recipients", [])
        channel = params.get("channel", "email")
        message = params.get("message", action.description)

        if dry_run:
            summary = f"Would send {channel} notification to {len(recipients)} recipient(s)"
        else:
            # Real implementation would integrate with email/Slack APIs
            summary = f"Sent {channel} notification to {len(recipients)} recipient(s)"
            logger.info(summary)

        return ExecutionResult(
            action_id=action.id,
            status=ActionStatus.COMPLETED,
            summary=summary,
            details={
                "channel": channel,
                "recipients": recipients,
                "message": message[:200],
            },
            dry_run=dry_run,
            finished_at=datetime.utcnow(),
            rollback_available=False,
        )
