"""
Approval gate — human-in-the-loop approval for proposed actions.

Implements tiered autonomy:
  GREEN    → auto-approve (low risk)
  YELLOW   → auto-approve + notify
  RED      → require explicit approval
  CRITICAL → require multi-party approval
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fiscalpilot.models.actions import (
    ActionStatus,
    ApprovalDecision,
    ApprovalLevel,
    ApprovalRule,
    ProposedAction,
)

logger = logging.getLogger("fiscalpilot.execution.approval")


class ApprovalGate:
    """Routes proposed actions through the appropriate approval workflow.

    The gate applies the configured autonomy rules:
    - GREEN actions auto-approve immediately.
    - YELLOW actions auto-approve and queue a notification.
    - RED actions wait for explicit human approval.
    - CRITICAL actions wait for multi-party approval.
    """

    def __init__(
        self,
        rules: list[ApprovalRule] | None = None,
        require_approval: bool = True,
        auto_approve_green: bool = True,
        auto_approve_yellow: bool = True,
    ) -> None:
        self._rules: dict[ApprovalLevel, ApprovalRule] = {}
        if rules:
            for rule in rules:
                self._rules[rule.level] = rule

        self._require_approval = require_approval
        self._auto_approve_green = auto_approve_green
        self._auto_approve_yellow = auto_approve_yellow

        # Pending actions indexed by ID
        self._pending: dict[str, ProposedAction] = {}
        # Decision log (immutable audit trail)
        self._decisions: list[ApprovalDecision] = []
        # Notifications to send (for YELLOW actions)
        self._notifications: list[dict[str, Any]] = []

    @property
    def pending_actions(self) -> list[ProposedAction]:
        """Actions waiting for human approval."""
        return [a for a in self._pending.values() if a.status == ActionStatus.PROPOSED]

    @property
    def decisions(self) -> list[ApprovalDecision]:
        """Full audit trail of all approval decisions."""
        return list(self._decisions)

    @property
    def notifications(self) -> list[dict[str, Any]]:
        """Queued notifications for YELLOW auto-approved actions."""
        return list(self._notifications)

    def process(self, actions: list[ProposedAction]) -> tuple[list[ProposedAction], list[ProposedAction]]:
        """Route actions through the approval gate.

        Returns:
            (auto_approved, needs_approval) — two lists.
            Auto-approved actions have status=APPROVED and can be executed immediately.
            Needs-approval actions have status=PROPOSED and are held in the pending queue.
        """
        auto_approved: list[ProposedAction] = []
        needs_approval: list[ProposedAction] = []

        for action in actions:
            if not self._require_approval:
                # Approval disabled — approve everything
                action.status = ActionStatus.APPROVED
                action.approved_at = datetime.utcnow()
                action.approved_by = "system:auto"
                auto_approved.append(action)
                self._record_decision(action, "approved", "system:auto", "Approval disabled globally")
                continue

            level = action.approval_level

            if level == ApprovalLevel.GREEN and self._auto_approve_green:
                action.status = ActionStatus.APPROVED
                action.approved_at = datetime.utcnow()
                action.approved_by = "system:auto"
                auto_approved.append(action)
                self._record_decision(action, "approved", "system:auto", "Green auto-approve")
                logger.debug("Auto-approved GREEN action: %s", action.title)

            elif level == ApprovalLevel.YELLOW and self._auto_approve_yellow:
                action.status = ActionStatus.APPROVED
                action.approved_at = datetime.utcnow()
                action.approved_by = "system:auto"
                auto_approved.append(action)
                self._record_decision(action, "approved", "system:auto", "Yellow auto-approve + notify")
                # Queue notification
                self._notifications.append({
                    "action_id": action.id,
                    "title": action.title,
                    "level": level.value,
                    "message": f"Auto-approved action: {action.title} (saves ${action.estimated_savings:,.2f})",
                })
                logger.debug("Auto-approved YELLOW action: %s (notification queued)", action.title)

            else:
                # RED or CRITICAL — hold for human approval
                self._pending[action.id] = action
                needs_approval.append(action)
                logger.info(
                    "Action '%s' requires %s approval — queued for review",
                    action.title,
                    level.value,
                )

        return auto_approved, needs_approval

    def approve(
        self,
        action_ids: list[str],
        approved_by: str = "user",
        reason: str = "",
        modifications: dict[str, dict[str, Any]] | None = None,
    ) -> list[ProposedAction]:
        """Approve one or more pending actions.

        Args:
            action_ids: IDs of actions to approve.
            approved_by: Email/username of the approver.
            reason: Optional reason for the approval.
            modifications: Optional per-action modifications (action_id → changes).

        Returns:
            List of newly approved actions.
        """
        approved: list[ProposedAction] = []
        mods = modifications or {}

        for action_id in action_ids:
            action = self._pending.get(action_id)
            if action is None:
                logger.warning("Action %s not found in pending queue", action_id)
                continue
            if action.status != ActionStatus.PROPOSED:
                logger.warning("Action %s is in state %s, cannot approve", action_id, action.status)
                continue

            # Check if this level requires multi-party approval
            rule = self._rules.get(action.approval_level)
            if rule and rule.require_all and rule.approver_emails:
                # For multi-party: track partial approvals in metadata
                partial = action.metadata.get("_approvals", [])
                if approved_by not in partial:
                    partial.append(approved_by)
                    action.metadata["_approvals"] = partial

                if len(partial) < len(rule.approver_emails):
                    logger.info(
                        "Action %s: %d/%d approvals received",
                        action_id,
                        len(partial),
                        len(rule.approver_emails),
                    )
                    self._record_decision(
                        action, "partial_approval", approved_by, f"Multi-party: {len(partial)}/{len(rule.approver_emails)}"
                    )
                    continue

            # Apply modifications if any
            if action_id in mods:
                for key, value in mods[action_id].items():
                    if hasattr(action, key):
                        setattr(action, key, value)

            action.status = ActionStatus.APPROVED
            action.approved_at = datetime.utcnow()
            action.approved_by = approved_by
            approved.append(action)
            self._record_decision(action, "approved", approved_by, reason)
            logger.info("Approved action: %s (by %s)", action.title, approved_by)

        return approved

    def reject(
        self,
        action_ids: list[str],
        rejected_by: str = "user",
        reason: str = "",
    ) -> list[ProposedAction]:
        """Reject one or more pending actions.

        Returns:
            List of rejected actions.
        """
        rejected: list[ProposedAction] = []
        for action_id in action_ids:
            action = self._pending.get(action_id)
            if action is None:
                logger.warning("Action %s not found in pending queue", action_id)
                continue
            if action.status != ActionStatus.PROPOSED:
                logger.warning("Action %s is in state %s, cannot reject", action_id, action.status)
                continue

            action.status = ActionStatus.REJECTED
            rejected.append(action)
            self._record_decision(action, "rejected", rejected_by, reason)
            logger.info("Rejected action: %s (by %s, reason: %s)", action.title, rejected_by, reason)

        return rejected

    def get_action(self, action_id: str) -> ProposedAction | None:
        """Look up a pending action by ID."""
        return self._pending.get(action_id)

    def _record_decision(
        self,
        action: ProposedAction,
        decision: str,
        decided_by: str,
        reason: str,
    ) -> None:
        """Record an immutable approval decision in the audit trail."""
        self._decisions.append(ApprovalDecision(
            action_id=action.id,
            decision=decision,
            decided_by=decided_by,
            reason=reason,
        ))
