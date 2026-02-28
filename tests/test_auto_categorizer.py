"""Tests for the Auto-Categorization module."""

import pytest
from datetime import date
from fiscalpilot.analyzers.auto_categorizer import (
    AutoCategorizer,
    CategoryRule,
    CategorizationResult,
    CategorizationStrategy,
    categorize,
    batch_categorize,
)
from fiscalpilot.models.financial import Transaction, TransactionType


class TestCategoryRule:
    """Test CategoryRule class."""
    
    def test_rule_creation(self):
        """Test basic rule creation."""
        rule = CategoryRule(
            name="test_rule",
            category="marketing",
            vendors=["Google Ads", "Facebook"],
            patterns=[r"campaign"],
        )
        assert rule.name == "test_rule"
        assert rule.category == "marketing"
        assert len(rule.vendors) == 2
    
    def test_rule_matches_vendor(self):
        """Test rule matching by vendor."""
        rule = CategoryRule(
            name="software",
            category="software",
            vendors=["AWS", "Microsoft Azure"],
        )
        
        txn = Transaction(
            date=date(2025, 1, 15),
            amount=-500.0,
            description="Cloud services",
            type=TransactionType.EXPENSE,
            vendor="AWS",
        )
        
        assert rule.matches(txn) is True
    
    def test_rule_matches_pattern(self):
        """Test rule matching by description pattern."""
        rule = CategoryRule(
            name="marketing",
            category="marketing",
            patterns=[r"advertis", r"campaign"],
        )
        
        txn = Transaction(
            date=date(2025, 1, 15),
            amount=-1000.0,
            description="Q1 Advertising Campaign",
            type=TransactionType.EXPENSE,
        )
        
        assert rule.matches(txn) is True
    
    def test_rule_no_match(self):
        """Test rule that doesn't match."""
        rule = CategoryRule(
            name="travel",
            category="travel",
            vendors=["Delta", "United"],
        )
        
        txn = Transaction(
            date=date(2025, 1, 15),
            amount=-50.0,
            description="Office supplies",
            type=TransactionType.EXPENSE,
            vendor="Staples",
        )
        
        assert rule.matches(txn) is False


class TestAutoCategorizer:
    """Test AutoCategorizer class."""
    
    def test_init_with_default_rules(self):
        """Test initialization with default rules."""
        categorizer = AutoCategorizer()
        assert len(categorizer.rules) > 0
    
    def test_init_with_custom_rules(self):
        """Test initialization with custom rules."""
        rules = [
            CategoryRule(name="custom", category="custom", vendors=["Test Vendor"])
        ]
        categorizer = AutoCategorizer(rules)
        assert len(categorizer.rules) == 1
    
    def test_categorize_known_vendor(self):
        """Test categorization of known vendor."""
        categorizer = AutoCategorizer()
        
        txn = Transaction(
            date=date(2025, 1, 15),
            amount=-100.0,
            description="Monthly subscription",
            type=TransactionType.EXPENSE,
            vendor="Gusto",
        )
        
        result = categorizer.categorize(txn)
        assert isinstance(result, CategorizationResult)
        assert result.category == "payroll"
        assert result.confidence > 0.8
    
    def test_categorize_by_pattern(self):
        """Test categorization by description pattern."""
        categorizer = AutoCategorizer()
        
        txn = Transaction(
            date=date(2025, 1, 15),
            amount=-2500.0,
            description="Monthly rent payment",
            type=TransactionType.EXPENSE,
        )
        
        result = categorizer.categorize(txn)
        # Categorizer matches based on patterns/rules
        assert result.category in ["rent", "office_supplies", "supplies"]
    
    def test_categorize_unknown(self):
        """Test categorization of unknown transaction."""
        categorizer = AutoCategorizer()
        
        txn = Transaction(
            date=date(2025, 1, 15),
            amount=-123.45,
            description="XYZZY789",  # Gibberish that won't match
            type=TransactionType.EXPENSE,
        )
        
        result = categorizer.categorize(txn)
        assert result.category == "uncategorized"
        assert result.confidence == 0.0
    
    def test_learn_from_correction(self):
        """Test learning from user corrections."""
        categorizer = AutoCategorizer()
        
        txn = Transaction(
            date=date(2025, 1, 15),
            amount=-100.0,
            description="XYZ Corp",
            type=TransactionType.EXPENSE,
            vendor="XYZ Corp",
        )
        
        # Learn that XYZ Corp is always consulting
        categorizer.learn_from_correction(txn, "professional_services")
        
        # Now categorize same vendor
        result = categorizer._match_vendor_history(txn)
        assert result is not None
        assert result.category == "professional_services"
    
    def test_batch_categorize(self):
        """Test batch categorization."""
        categorizer = AutoCategorizer()
        
        transactions = [
            Transaction(
                date=date(2025, 1, 15),
                amount=-100.0,
                description="Monthly fee",
                type=TransactionType.EXPENSE,
                vendor="ADP",
            ),
            Transaction(
                date=date(2025, 1, 16),
                amount=-500.0,
                description="Cloud hosting",
                type=TransactionType.EXPENSE,
                vendor="AWS",
            ),
        ]
        
        results = categorizer.batch_categorize(transactions)
        assert len(results) == 2
        
        # Both should be categorized
        for txn, result in results:
            assert result.category != "uncategorized"
    
    def test_add_rule(self):
        """Test adding a custom rule."""
        categorizer = AutoCategorizer()
        initial_count = len(categorizer.rules)
        
        rule = CategoryRule(
            name="custom_vendor",
            category="custom_category",
            vendors=["My Special Vendor"],
        )
        categorizer.add_rule(rule)
        
        assert len(categorizer.rules) == initial_count + 1
    
    def test_remove_rule(self):
        """Test removing a rule."""
        categorizer = AutoCategorizer()
        # Get name of first rule
        rule_name = categorizer.rules[0].name
        initial_count = len(categorizer.rules)
        
        removed = categorizer.remove_rule(rule_name)
        assert removed is True
        assert len(categorizer.rules) == initial_count - 1
    
    def test_get_uncategorized(self):
        """Test getting uncategorized transactions."""
        categorizer = AutoCategorizer()
        
        transactions = [
            Transaction(
                date=date(2025, 1, 15),
                amount=-100.0,
                description="Payroll",
                type=TransactionType.EXPENSE,
                vendor="ADP",
            ),
            Transaction(
                date=date(2025, 1, 16),
                amount=-50.0,
                description="RANDOM123",  # Won't categorize
                type=TransactionType.EXPENSE,
            ),
        ]
        
        uncategorized = categorizer.get_uncategorized(transactions)
        assert len(uncategorized) == 1


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_categorize_function(self):
        """Test the categorize() convenience function."""
        txn = Transaction(
            date=date(2025, 1, 15),
            amount=-100.0,
            description="Monthly fee",
            type=TransactionType.EXPENSE,
            vendor="Gusto",
        )
        
        result = categorize(txn)
        assert isinstance(result, CategorizationResult)
    
    def test_batch_categorize_function(self):
        """Test the batch_categorize() convenience function."""
        transactions = [
            Transaction(
                date=date(2025, 1, 15),
                amount=-100.0,
                description="Test",
                type=TransactionType.EXPENSE,
            )
        ]
        
        results = batch_categorize(transactions)
        assert len(results) == 1
