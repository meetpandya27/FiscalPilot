"""Tests for the Spend Policy Engine module."""

import pytest
from datetime import date, datetime
from fiscalpilot.analyzers.policy_engine import (
    SpendPolicyEngine,
    SpendPolicy,
    PolicyCondition,
    PolicyAction,
    PolicyPriority,
    ConditionType,
    PolicyEvaluationResult,
    evaluate_transaction,
    create_default_policy_engine,
)
from fiscalpilot.models.financial import Transaction, TransactionType, ExpenseCategory


class TestPolicyCondition:
    """Test PolicyCondition class."""
    
    def test_amount_less_than(self):
        """Test amount less than condition."""
        condition = PolicyCondition(
            condition_type=ConditionType.AMOUNT_LESS_THAN,
            value=100.0
        )
        
        txn_under = Transaction(
            date=date(2025, 1, 15),
            amount=50.0,
            description="Small expense",
            type=TransactionType.EXPENSE,
        )
        txn_over = Transaction(
            date=date(2025, 1, 15),
            amount=150.0,
            description="Large expense",
            type=TransactionType.EXPENSE,
        )
        
        assert condition.evaluate(txn_under) is True
        assert condition.evaluate(txn_over) is False
    
    def test_amount_greater_than(self):
        """Test amount greater than condition."""
        condition = PolicyCondition(
            condition_type=ConditionType.AMOUNT_GREATER_THAN,
            value=100.0
        )
        
        txn_over = Transaction(
            date=date(2025, 1, 15),
            amount=150.0,
            description="Large expense",
            type=TransactionType.EXPENSE,
        )
        txn_under = Transaction(
            date=date(2025, 1, 15),
            amount=50.0,
            description="Small expense",
            type=TransactionType.EXPENSE,
        )
        
        assert condition.evaluate(txn_over) is True
        assert condition.evaluate(txn_under) is False
    
    def test_amount_between(self):
        """Test amount between condition."""
        condition = PolicyCondition(
            condition_type=ConditionType.AMOUNT_BETWEEN,
            value=(50.0, 150.0)
        )
        
        txn_in_range = Transaction(
            date=date(2025, 1, 15),
            amount=100.0,
            description="In range",
            type=TransactionType.EXPENSE,
        )
        txn_out_range = Transaction(
            date=date(2025, 1, 15),
            amount=200.0,
            description="Out of range",
            type=TransactionType.EXPENSE,
        )
        
        assert condition.evaluate(txn_in_range) is True
        assert condition.evaluate(txn_out_range) is False
    
    def test_category_in(self):
        """Test category in list condition."""
        condition = PolicyCondition(
            condition_type=ConditionType.CATEGORY_IN,
            value=["marketing", "advertising"]
        )
        
        txn_marketing = Transaction(
            date=date(2025, 1, 15),
            amount=100.0,
            description="Ad spend",
            type=TransactionType.EXPENSE,
            category=ExpenseCategory.MARKETING,
        )
        txn_other = Transaction(
            date=date(2025, 1, 15),
            amount=100.0,
            description="Office supplies",
            type=TransactionType.EXPENSE,
            category=ExpenseCategory.SUPPLIES,
        )
        
        assert condition.evaluate(txn_marketing) is True
        assert condition.evaluate(txn_other) is False
    
    def test_vendor_in(self):
        """Test vendor in list condition."""
        condition = PolicyCondition(
            condition_type=ConditionType.VENDOR_IN,
            value=["AWS", "Google Cloud"]
        )
        
        txn_aws = Transaction(
            date=date(2025, 1, 15),
            amount=100.0,
            description="Cloud services",
            type=TransactionType.EXPENSE,
            vendor="AWS",
        )
        txn_other = Transaction(
            date=date(2025, 1, 15),
            amount=100.0,
            description="Other vendor",
            type=TransactionType.EXPENSE,
            vendor="Staples",
        )
        
        assert condition.evaluate(txn_aws) is True
        assert condition.evaluate(txn_other) is False
    
    def test_weekend_condition(self):
        """Test weekend condition."""
        condition = PolicyCondition(
            condition_type=ConditionType.WEEKEND,
            value=True
        )
        
        # Jan 18, 2025 is a Saturday
        txn_weekend = Transaction(
            date=date(2025, 1, 18),
            amount=100.0,
            description="Weekend purchase",
            type=TransactionType.EXPENSE,
        )
        # Jan 15, 2025 is a Wednesday
        txn_weekday = Transaction(
            date=date(2025, 1, 15),
            amount=100.0,
            description="Weekday purchase",
            type=TransactionType.EXPENSE,
        )
        
        assert condition.evaluate(txn_weekend) is True
        assert condition.evaluate(txn_weekday) is False


class TestSpendPolicy:
    """Test SpendPolicy class."""
    
    def test_policy_creation(self):
        """Test basic policy creation."""
        policy = SpendPolicy(
            name="Test Policy",
            description="Test description",
            conditions=[
                PolicyCondition(ConditionType.AMOUNT_LESS_THAN, 100.0)
            ],
            action=PolicyAction.APPROVE,
        )
        
        assert policy.name == "Test Policy"
        assert policy.action == PolicyAction.APPROVE
        assert policy.is_active is True
    
    def test_policy_matches_all_conditions(self):
        """Test policy matching with require_all_conditions=True."""
        policy = SpendPolicy(
            name="Multi-condition",
            description="Requires all conditions",
            conditions=[
                PolicyCondition(ConditionType.AMOUNT_LESS_THAN, 100.0),
                PolicyCondition(ConditionType.CATEGORY_IN, ["marketing"]),
            ],
            action=PolicyAction.APPROVE,
            require_all_conditions=True,
        )
        
        # Matches both conditions
        txn_match_all = Transaction(
            date=date(2025, 1, 15),
            amount=50.0,
            description="Small marketing",
            type=TransactionType.EXPENSE,
            category=ExpenseCategory.MARKETING,
        )
        
        # Matches only amount
        txn_match_partial = Transaction(
            date=date(2025, 1, 15),
            amount=50.0,
            description="Small non-marketing",
            type=TransactionType.EXPENSE,
            category=ExpenseCategory.SUPPLIES,
        )
        
        assert policy.matches(txn_match_all) is True
        assert policy.matches(txn_match_partial) is False
    
    def test_policy_matches_any_condition(self):
        """Test policy matching with require_all_conditions=False."""
        policy = SpendPolicy(
            name="Any-condition",
            description="Requires any condition",
            conditions=[
                PolicyCondition(ConditionType.AMOUNT_GREATER_THAN, 1000.0),
                PolicyCondition(ConditionType.CATEGORY_IN, ["travel"]),
            ],
            action=PolicyAction.ESCALATE,
            require_all_conditions=False,
        )
        
        # Matches category but not amount
        txn = Transaction(
            date=date(2025, 1, 15),
            amount=100.0,
            description="Small travel expense",
            type=TransactionType.EXPENSE,
            category=ExpenseCategory.TRAVEL,
        )
        
        assert policy.matches(txn) is True
    
    def test_inactive_policy_no_match(self):
        """Test that inactive policies don't match."""
        policy = SpendPolicy(
            name="Inactive",
            description="Inactive policy",
            conditions=[
                PolicyCondition(ConditionType.AMOUNT_LESS_THAN, 100.0)
            ],
            action=PolicyAction.APPROVE,
            is_active=False,
        )
        
        txn = Transaction(
            date=date(2025, 1, 15),
            amount=50.0,
            description="Test",
            type=TransactionType.EXPENSE,
        )
        
        assert policy.matches(txn) is False


class TestSpendPolicyEngine:
    """Test SpendPolicyEngine class."""
    
    def test_init_empty(self):
        """Test empty engine initialization."""
        engine = SpendPolicyEngine()
        assert len(engine.policies) == 0
    
    def test_add_policy(self):
        """Test adding policies."""
        engine = SpendPolicyEngine()
        
        policy = SpendPolicy(
            name="Test",
            description="Test policy",
            conditions=[PolicyCondition(ConditionType.AMOUNT_LESS_THAN, 100.0)],
            action=PolicyAction.APPROVE,
        )
        
        engine.add_policy(policy)
        assert len(engine.policies) == 1
    
    def test_remove_policy(self):
        """Test removing policies."""
        engine = SpendPolicyEngine()
        engine.add_policy(SpendPolicy(
            name="Test",
            description="Test",
            conditions=[],
            action=PolicyAction.APPROVE,
        ))
        
        removed = engine.remove_policy("Test")
        assert removed is True
        assert len(engine.policies) == 0
        
        removed = engine.remove_policy("NonExistent")
        assert removed is False
    
    def test_add_preset(self):
        """Test adding preset policies."""
        engine = SpendPolicyEngine()
        
        added = engine.add_preset("auto_approve_small")
        assert added is True
        assert len(engine.policies) == 1
        
        added = engine.add_preset("nonexistent_preset")
        assert added is False
    
    def test_evaluate_auto_approve(self):
        """Test auto-approve for small expenses."""
        engine = SpendPolicyEngine()
        engine.add_policy(SpendPolicy(
            name="Auto-approve small",
            description="Auto-approve under $50",
            conditions=[PolicyCondition(ConditionType.AMOUNT_LESS_THAN, 50.0)],
            action=PolicyAction.APPROVE,
        ))
        
        txn = Transaction(
            date=date(2025, 1, 15),
            amount=25.0,
            description="Small expense",
            type=TransactionType.EXPENSE,
        )
        
        result = engine.evaluate(txn)
        
        assert result.is_approved is True
        assert result.final_action == PolicyAction.APPROVE
    
    def test_evaluate_rejection(self):
        """Test rejection of blocked vendor."""
        engine = SpendPolicyEngine()
        engine.create_vendor_block_policy(
            name="Block gambling",
            vendors=["Casino Inc", "Gambling Site"],
            message="Gambling not allowed",
        )
        
        txn = Transaction(
            date=date(2025, 1, 15),
            amount=100.0,
            description="Gambling expense",
            type=TransactionType.EXPENSE,
            vendor="Casino Inc",
        )
        
        result = engine.evaluate(txn)
        
        assert result.is_rejected is True
        assert result.final_action == PolicyAction.REJECT
        assert "Gambling not allowed" in result.messages
    
    def test_evaluate_escalation(self):
        """Test escalation for large expenses."""
        engine = SpendPolicyEngine()
        engine.add_policy(SpendPolicy(
            name="Escalate large",
            description="Escalate over $1000",
            conditions=[PolicyCondition(ConditionType.AMOUNT_GREATER_THAN, 1000.0)],
            action=PolicyAction.ESCALATE,
            escalate_to="manager@company.com",
        ))
        
        txn = Transaction(
            date=date(2025, 1, 15),
            amount=5000.0,
            description="Large purchase",
            type=TransactionType.EXPENSE,
        )
        
        result = engine.evaluate(txn)
        
        assert result.needs_review is True
        assert result.final_action == PolicyAction.ESCALATE
        assert result.escalate_to == "manager@company.com"
    
    def test_evaluate_receipt_required(self):
        """Test receipt requirement flag."""
        engine = SpendPolicyEngine()
        engine.add_policy(SpendPolicy(
            name="Receipt required",
            description="Require receipt over $75",
            conditions=[PolicyCondition(ConditionType.AMOUNT_GREATER_THAN, 75.0)],
            action=PolicyAction.REQUIRE_RECEIPT,
        ))
        
        txn = Transaction(
            date=date(2025, 1, 15),
            amount=100.0,
            description="Expense",
            type=TransactionType.EXPENSE,
        )
        
        result = engine.evaluate(txn)
        assert result.requires_receipt is True
    
    def test_policy_priority_order(self):
        """Test that higher priority policies take precedence."""
        engine = SpendPolicyEngine()
        
        # Add low priority approve
        engine.add_policy(SpendPolicy(
            name="Approve small",
            description="Approve under $100",
            conditions=[PolicyCondition(ConditionType.AMOUNT_LESS_THAN, 100.0)],
            action=PolicyAction.APPROVE,
            priority=PolicyPriority.LOW,
        ))
        
        # Add high priority reject for specific category
        engine.add_policy(SpendPolicy(
            name="Block miscellaneous",
            description="Block miscellaneous",
            conditions=[PolicyCondition(ConditionType.CATEGORY_IN, ["miscellaneous"])],
            action=PolicyAction.REJECT,
            priority=PolicyPriority.HIGH,
        ))
        
        # Transaction matches both but high priority should win
        txn = Transaction(
            date=date(2025, 1, 15),
            amount=50.0,
            description="Movie tickets",
            type=TransactionType.EXPENSE,
            category=ExpenseCategory.MISCELLANEOUS,
        )
        
        result = engine.evaluate(txn)
        # High priority REJECT should override low priority APPROVE
        assert result.is_rejected is True
    
    def test_batch_evaluate(self):
        """Test batch evaluation."""
        engine = SpendPolicyEngine()
        engine.add_policy(SpendPolicy(
            name="Approve",
            description="Approve all",
            conditions=[PolicyCondition(ConditionType.AMOUNT_GREATER_THAN, 0)],
            action=PolicyAction.APPROVE,
        ))
        
        transactions = [
            Transaction(
                date=date(2025, 1, 15),
                amount=100.0,
                description="Test 1",
                type=TransactionType.EXPENSE,
            ),
            Transaction(
                date=date(2025, 1, 16),
                amount=200.0,
                description="Test 2",
                type=TransactionType.EXPENSE,
            ),
        ]
        
        results = engine.batch_evaluate(transactions)
        assert len(results) == 2
    
    def test_get_violations(self):
        """Test getting policy violations."""
        engine = SpendPolicyEngine()
        engine.add_policy(SpendPolicy(
            name="Reject large",
            description="Reject over $500",
            conditions=[PolicyCondition(ConditionType.AMOUNT_GREATER_THAN, 500.0)],
            action=PolicyAction.REJECT,
        ))
        
        transactions = [
            Transaction(
                date=date(2025, 1, 15),
                amount=100.0,
                description="Small",
                type=TransactionType.EXPENSE,
            ),
            Transaction(
                date=date(2025, 1, 16),
                amount=1000.0,
                description="Large",
                type=TransactionType.EXPENSE,
            ),
        ]
        
        violations = engine.get_violations(transactions)
        assert len(violations) == 1
        assert violations[0].is_rejected is True
    
    def test_export_policies(self):
        """Test policy export."""
        engine = SpendPolicyEngine()
        engine.create_amount_limit_policy("Limit", 1000.0)
        
        exported = engine.export_policies()
        
        assert len(exported) == 1
        assert exported[0]["name"] == "Limit"


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_evaluate_transaction(self):
        """Test evaluate_transaction function."""
        txn = Transaction(
            date=date(2025, 1, 15),
            amount=100.0,
            description="Test",
            type=TransactionType.EXPENSE,
        )
        
        result = evaluate_transaction(txn)
        assert isinstance(result, PolicyEvaluationResult)
    
    def test_create_default_policy_engine(self):
        """Test create_default_policy_engine function."""
        engine = create_default_policy_engine()
        
        assert isinstance(engine, SpendPolicyEngine)
        assert len(engine.policies) > 0
