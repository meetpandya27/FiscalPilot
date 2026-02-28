"""
Spend Policy Engine — enforce spending rules and approval workflows.

Inspired by Ramp's spend policy features. Define rules for automatic
approval, rejection, or escalation of transactions based on amount,
category, vendor, and other attributes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from fiscalpilot.models.financial import Transaction, ExpenseCategory

logger = logging.getLogger("fiscalpilot.analyzers.policy_engine")


class PolicyAction(str, Enum):
    """Action to take when a policy matches."""
    
    APPROVE = "approve"
    REJECT = "reject"
    ESCALATE = "escalate"
    FLAG = "flag"
    REQUIRE_RECEIPT = "require_receipt"
    REQUIRE_MEMO = "require_memo"


class PolicyPriority(str, Enum):
    """Priority level that determines order of evaluation."""
    
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ConditionType(str, Enum):
    """Types of conditions that can be evaluated."""
    
    AMOUNT_LESS_THAN = "amount_lt"
    AMOUNT_GREATER_THAN = "amount_gt"
    AMOUNT_BETWEEN = "amount_between"
    CATEGORY_IN = "category_in"
    CATEGORY_NOT_IN = "category_not_in"
    VENDOR_IN = "vendor_in"
    VENDOR_NOT_IN = "vendor_not_in"
    VENDOR_MATCHES = "vendor_matches"
    DESCRIPTION_CONTAINS = "description_contains"
    DAY_OF_WEEK = "day_of_week"
    WEEKEND = "weekend"
    AFTER_HOURS = "after_hours"
    MERCHANT_TYPE = "merchant_type"


@dataclass
class PolicyCondition:
    """A single condition in a spend policy."""
    
    condition_type: ConditionType
    value: Any
    
    def evaluate(self, transaction: Transaction) -> bool:
        """Evaluate this condition against a transaction."""
        if self.condition_type == ConditionType.AMOUNT_LESS_THAN:
            return transaction.amount < self.value
        
        elif self.condition_type == ConditionType.AMOUNT_GREATER_THAN:
            return transaction.amount > self.value
        
        elif self.condition_type == ConditionType.AMOUNT_BETWEEN:
            low, high = self.value
            return low <= transaction.amount <= high
        
        elif self.condition_type == ConditionType.CATEGORY_IN:
            if transaction.category:
                return transaction.category.value in self.value
            return False
        
        elif self.condition_type == ConditionType.CATEGORY_NOT_IN:
            if transaction.category:
                return transaction.category.value not in self.value
            return True
        
        elif self.condition_type == ConditionType.VENDOR_IN:
            if transaction.vendor:
                return transaction.vendor.lower() in [v.lower() for v in self.value]
            return False
        
        elif self.condition_type == ConditionType.VENDOR_NOT_IN:
            if transaction.vendor:
                return transaction.vendor.lower() not in [v.lower() for v in self.value]
            return True
        
        elif self.condition_type == ConditionType.VENDOR_MATCHES:
            import re
            if transaction.vendor:
                return bool(re.search(self.value, transaction.vendor, re.IGNORECASE))
            return False
        
        elif self.condition_type == ConditionType.DESCRIPTION_CONTAINS:
            if transaction.description:
                return self.value.lower() in transaction.description.lower()
            return False
        
        elif self.condition_type == ConditionType.DAY_OF_WEEK:
            if transaction.date:
                return transaction.date.weekday() in self.value
            return False
        
        elif self.condition_type == ConditionType.WEEKEND:
            if transaction.date:
                return transaction.date.weekday() >= 5  # Saturday=5, Sunday=6
            return False
        
        elif self.condition_type == ConditionType.AFTER_HOURS:
            # This would require timestamp, not just date
            return False
        
        return False


@dataclass
class SpendPolicy:
    """A spending policy with conditions and actions."""
    
    name: str
    description: str
    conditions: list[PolicyCondition]
    action: PolicyAction
    priority: PolicyPriority = PolicyPriority.MEDIUM
    escalate_to: str | None = None  # Email/user for escalation
    message: str = ""  # Message to show when policy triggers
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    
    # Match logic
    require_all_conditions: bool = True  # AND vs OR
    
    def matches(self, transaction: Transaction) -> bool:
        """Check if this policy matches a transaction."""
        if not self.is_active:
            return False
        
        if not self.conditions:
            return False
        
        results = [cond.evaluate(transaction) for cond in self.conditions]
        
        if self.require_all_conditions:
            return all(results)
        else:
            return any(results)


@dataclass
class PolicyEvaluationResult:
    """Result of evaluating a transaction against policies."""
    
    transaction: Any  # Transaction being evaluated
    matched_policies: list[SpendPolicy] = field(default_factory=list)
    final_action: PolicyAction = PolicyAction.APPROVE
    requires_receipt: bool = False
    requires_memo: bool = False
    escalate_to: str | None = None
    messages: list[str] = field(default_factory=list)
    
    @property
    def is_approved(self) -> bool:
        return self.final_action == PolicyAction.APPROVE
    
    @property
    def is_rejected(self) -> bool:
        return self.final_action == PolicyAction.REJECT
    
    @property
    def needs_review(self) -> bool:
        return self.final_action in (PolicyAction.ESCALATE, PolicyAction.FLAG)


class SpendPolicyEngine:
    """
    Engine for enforcing spending policies on transactions.
    
    Features inspired by Ramp:
    - Multi-condition policies (amount, category, vendor, time)
    - Automatic approval/rejection based on rules
    - Escalation workflows for exceptions
    - Receipt and memo requirements
    - Merchant category blocking
    - Weekend/after-hours restrictions
    
    Example usage:
        engine = SpendPolicyEngine()
        
        # Add auto-approve policy for small amounts
        engine.add_policy(SpendPolicy(
            name="Auto-approve small expenses",
            description="Automatically approve expenses under $50",
            conditions=[
                PolicyCondition(ConditionType.AMOUNT_LESS_THAN, 50)
            ],
            action=PolicyAction.APPROVE,
            priority=PolicyPriority.LOW,
        ))
        
        # Evaluate a transaction
        result = engine.evaluate(transaction)
        if result.is_approved:
            print("Transaction approved!")
    """
    
    # Preset blocked merchant categories (gambling, adult, etc.)
    BLOCKED_MERCHANT_TYPES = [
        "gambling",
        "casino",
        "adult_entertainment",
        "alcohol_store",
        "tobacco",
    ]
    
    # Common policy templates
    PRESET_POLICIES = {
        "auto_approve_small": SpendPolicy(
            name="Auto-approve Small Expenses",
            description="Automatically approve expenses under $50",
            conditions=[PolicyCondition(ConditionType.AMOUNT_LESS_THAN, 50)],
            action=PolicyAction.APPROVE,
            priority=PolicyPriority.LOW,
        ),
        "require_receipt_large": SpendPolicy(
            name="Receipt Required - Large",
            description="Require receipt for expenses over $75",
            conditions=[PolicyCondition(ConditionType.AMOUNT_GREATER_THAN, 75)],
            action=PolicyAction.REQUIRE_RECEIPT,
            priority=PolicyPriority.MEDIUM,
        ),
        "escalate_very_large": SpendPolicy(
            name="Escalate Large Expenses",
            description="Escalate expenses over $1000 to manager",
            conditions=[PolicyCondition(ConditionType.AMOUNT_GREATER_THAN, 1000)],
            action=PolicyAction.ESCALATE,
            priority=PolicyPriority.HIGH,
        ),
        "block_weekend": SpendPolicy(
            name="Block Weekend Purchases",
            description="Flag purchases made on weekends",
            conditions=[PolicyCondition(ConditionType.WEEKEND, True)],
            action=PolicyAction.FLAG,
            priority=PolicyPriority.MEDIUM,
            message="Weekend purchases require justification",
        ),
    }
    
    def __init__(self, policies: list[SpendPolicy] | None = None):
        """Initialize engine with optional policies."""
        self.policies = policies or []
        
    def add_policy(self, policy: SpendPolicy):
        """Add a policy to the engine."""
        self.policies.append(policy)
        logger.info(f"Added policy: {policy.name}")
    
    def remove_policy(self, policy_name: str) -> bool:
        """Remove a policy by name."""
        before = len(self.policies)
        self.policies = [p for p in self.policies if p.name != policy_name]
        return len(self.policies) < before
    
    def add_preset(self, preset_name: str) -> bool:
        """Add a preset policy by name."""
        if preset_name in self.PRESET_POLICIES:
            self.policies.append(self.PRESET_POLICIES[preset_name])
            return True
        return False
    
    def evaluate(self, transaction: Transaction) -> PolicyEvaluationResult:
        """
        Evaluate a transaction against all policies.
        
        Policies are evaluated in priority order (HIGH → MEDIUM → LOW).
        The most restrictive action wins.
        
        Args:
            transaction: Transaction to evaluate.
            
        Returns:
            PolicyEvaluationResult with action and requirements.
        """
        result = PolicyEvaluationResult(transaction=transaction)
        
        # Sort policies by priority
        priority_order = {
            PolicyPriority.HIGH: 0,
            PolicyPriority.MEDIUM: 1,
            PolicyPriority.LOW: 2,
        }
        sorted_policies = sorted(
            self.policies,
            key=lambda p: priority_order.get(p.priority, 1)
        )
        
        # Track most restrictive action
        action_priority = {
            PolicyAction.REJECT: 0,
            PolicyAction.ESCALATE: 1,
            PolicyAction.FLAG: 2,
            PolicyAction.REQUIRE_RECEIPT: 3,
            PolicyAction.REQUIRE_MEMO: 4,
            PolicyAction.APPROVE: 5,
        }
        best_action = PolicyAction.APPROVE
        
        for policy in sorted_policies:
            if policy.matches(transaction):
                result.matched_policies.append(policy)
                
                # Track escalation target
                if policy.action == PolicyAction.ESCALATE and policy.escalate_to:
                    result.escalate_to = policy.escalate_to
                
                # Track requirements
                if policy.action == PolicyAction.REQUIRE_RECEIPT:
                    result.requires_receipt = True
                if policy.action == PolicyAction.REQUIRE_MEMO:
                    result.requires_memo = True
                
                # Track messages
                if policy.message:
                    result.messages.append(policy.message)
                
                # Update action if more restrictive
                if action_priority.get(policy.action, 5) < action_priority.get(best_action, 5):
                    best_action = policy.action
        
        result.final_action = best_action
        return result
    
    def batch_evaluate(
        self,
        transactions: list[Transaction],
    ) -> list[PolicyEvaluationResult]:
        """Evaluate multiple transactions."""
        return [self.evaluate(txn) for txn in transactions]
    
    def get_violations(
        self,
        transactions: list[Transaction],
    ) -> list[PolicyEvaluationResult]:
        """Get transactions that violate policies (not approved)."""
        results = self.batch_evaluate(transactions)
        return [r for r in results if not r.is_approved]
    
    def create_amount_limit_policy(
        self,
        name: str,
        limit: float,
        action: PolicyAction = PolicyAction.ESCALATE,
        categories: list[str] | None = None,
    ) -> SpendPolicy:
        """
        Create an amount limit policy.
        
        Args:
            name: Policy name.
            limit: Amount threshold.
            action: Action when exceeded.
            categories: Optional list of categories to apply to.
            
        Returns:
            Created SpendPolicy.
        """
        conditions = [PolicyCondition(ConditionType.AMOUNT_GREATER_THAN, limit)]
        
        if categories:
            conditions.append(PolicyCondition(ConditionType.CATEGORY_IN, categories))
        
        policy = SpendPolicy(
            name=name,
            description=f"Policy for expenses over ${limit:,.2f}",
            conditions=conditions,
            action=action,
            require_all_conditions=bool(categories),
        )
        self.policies.append(policy)
        return policy
    
    def create_vendor_block_policy(
        self,
        name: str,
        vendors: list[str],
        message: str = "This vendor is not approved",
    ) -> SpendPolicy:
        """
        Create a policy to block specific vendors.
        
        Args:
            name: Policy name.
            vendors: List of vendor names to block.
            message: Message to show when blocked.
            
        Returns:
            Created SpendPolicy.
        """
        policy = SpendPolicy(
            name=name,
            description=f"Block purchases from: {', '.join(vendors)}",
            conditions=[PolicyCondition(ConditionType.VENDOR_IN, vendors)],
            action=PolicyAction.REJECT,
            priority=PolicyPriority.HIGH,
            message=message,
        )
        self.policies.append(policy)
        return policy
    
    def create_category_restriction_policy(
        self,
        name: str,
        blocked_categories: list[str],
        message: str = "This expense category is not allowed",
    ) -> SpendPolicy:
        """
        Create a policy to restrict certain expense categories.
        
        Args:
            name: Policy name.
            blocked_categories: Categories to block.
            message: Message to show when blocked.
            
        Returns:
            Created SpendPolicy.
        """
        policy = SpendPolicy(
            name=name,
            description=f"Block categories: {', '.join(blocked_categories)}",
            conditions=[PolicyCondition(ConditionType.CATEGORY_IN, blocked_categories)],
            action=PolicyAction.REJECT,
            priority=PolicyPriority.HIGH,
            message=message,
        )
        self.policies.append(policy)
        return policy

    def export_policies(self) -> list[dict[str, Any]]:
        """Export policies as serializable dicts."""
        exported = []
        for policy in self.policies:
            exported.append({
                "name": policy.name,
                "description": policy.description,
                "action": policy.action.value,
                "priority": policy.priority.value,
                "is_active": policy.is_active,
                "require_all_conditions": policy.require_all_conditions,
                "conditions": [
                    {"type": c.condition_type.value, "value": c.value}
                    for c in policy.conditions
                ],
                "escalate_to": policy.escalate_to,
                "message": policy.message,
            })
        return exported


# Convenience functions
def evaluate_transaction(
    transaction: Transaction,
    policies: list[SpendPolicy] | None = None,
) -> PolicyEvaluationResult:
    """Quick evaluation of a single transaction."""
    engine = SpendPolicyEngine(policies)
    return engine.evaluate(transaction)


def create_default_policy_engine() -> SpendPolicyEngine:
    """Create an engine with common default policies."""
    engine = SpendPolicyEngine()
    engine.add_preset("auto_approve_small")
    engine.add_preset("require_receipt_large")
    engine.add_preset("escalate_very_large")
    return engine
