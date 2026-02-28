"""Tests for the Budget Management module."""

import pytest
from datetime import date, datetime, timedelta
from fiscalpilot.analyzers.budget import (
    BudgetManager,
    Budget,
    BudgetProgress,
    BudgetReport,
    BudgetPeriod,
    BudgetStatus,
    BudgetAlert,
    create_monthly_budget,
    check_budgets,
)
from fiscalpilot.models.financial import Transaction, TransactionType, ExpenseCategory


class TestBudget:
    """Test Budget class."""
    
    def test_budget_creation(self):
        """Test basic budget creation."""
        budget = Budget(
            name="Marketing",
            amount=5000.0,
            period=BudgetPeriod.MONTHLY,
            categories=["marketing"],
        )
        assert budget.name == "Marketing"
        assert budget.amount == 5000.0
        assert budget.period == BudgetPeriod.MONTHLY
        assert budget.is_active is True
    
    def test_monthly_period_dates(self):
        """Test monthly period date calculation."""
        budget = Budget(
            name="Test",
            amount=1000.0,
            period=BudgetPeriod.MONTHLY,
        )
        
        ref_date = date(2025, 1, 15)
        start, end = budget.get_period_dates(ref_date)
        
        assert start == date(2025, 1, 1)
        assert end == date(2025, 1, 31)
    
    def test_weekly_period_dates(self):
        """Test weekly period date calculation."""
        budget = Budget(
            name="Test",
            amount=1000.0,
            period=BudgetPeriod.WEEKLY,
        )
        
        # Pick a Wednesday
        ref_date = date(2025, 1, 15)  # This is a Wednesday
        start, end = budget.get_period_dates(ref_date)
        
        # Week should start on Monday
        assert start.weekday() == 0  # Monday
        assert end.weekday() == 6    # Sunday
        assert (end - start).days == 6
    
    def test_yearly_period_dates(self):
        """Test yearly period date calculation."""
        budget = Budget(
            name="Test",
            amount=100000.0,
            period=BudgetPeriod.YEARLY,
        )
        
        ref_date = date(2025, 6, 15)
        start, end = budget.get_period_dates(ref_date)
        
        assert start == date(2025, 1, 1)
        assert end == date(2025, 12, 31)
    
    def test_matches_transaction_category(self):
        """Test transaction matching by category."""
        budget = Budget(
            name="Marketing Budget",
            amount=5000.0,
            period=BudgetPeriod.MONTHLY,
            categories=["marketing"],
        )
        
        matching_txn = Transaction(
            date=date(2025, 1, 15),
            amount=-500.0,
            description="Ad spend",
            type=TransactionType.EXPENSE,
            category=ExpenseCategory.MARKETING,
        )
        
        non_matching_txn = Transaction(
            date=date(2025, 1, 15),
            amount=-100.0,
            description="Office supplies",
            type=TransactionType.EXPENSE,
            category=ExpenseCategory.SUPPLIES,
        )
        
        assert budget.matches_transaction(matching_txn) is True
        assert budget.matches_transaction(non_matching_txn) is False
    
    def test_matches_transaction_vendor(self):
        """Test transaction matching by vendor."""
        budget = Budget(
            name="AWS Budget",
            amount=2000.0,
            period=BudgetPeriod.MONTHLY,
            vendors=["AWS", "Amazon Web Services"],
        )
        
        matching_txn = Transaction(
            date=date(2025, 1, 15),
            amount=-500.0,
            description="Cloud services",
            type=TransactionType.EXPENSE,
            vendor="AWS",
        )
        
        non_matching_txn = Transaction(
            date=date(2025, 1, 15),
            amount=-500.0,
            description="Cloud services",
            type=TransactionType.EXPENSE,
            vendor="Google Cloud",
        )
        
        assert budget.matches_transaction(matching_txn) is True
        assert budget.matches_transaction(non_matching_txn) is False


class TestBudgetManager:
    """Test BudgetManager class."""
    
    def test_init_empty(self):
        """Test empty initialization."""
        manager = BudgetManager()
        assert len(manager.budgets) == 0
    
    def test_create_budget(self):
        """Test budget creation."""
        manager = BudgetManager()
        budget = manager.create_budget(
            name="Marketing",
            amount=5000.0,
            period=BudgetPeriod.MONTHLY,
            categories=["marketing"],
        )
        
        assert len(manager.budgets) == 1
        assert budget.name == "Marketing"
        assert budget.amount == 5000.0
    
    def test_remove_budget(self):
        """Test budget removal."""
        manager = BudgetManager()
        manager.create_budget("Test", 1000.0)
        
        assert len(manager.budgets) == 1
        
        removed = manager.remove_budget("Test")
        assert removed is True
        assert len(manager.budgets) == 0
        
        # Try to remove non-existent
        removed = manager.remove_budget("NonExistent")
        assert removed is False
    
    def test_get_budget(self):
        """Test getting budget by name."""
        manager = BudgetManager()
        manager.create_budget("Marketing", 5000.0)
        manager.create_budget("Travel", 2000.0)
        
        budget = manager.get_budget("Marketing")
        assert budget is not None
        assert budget.amount == 5000.0
        
        budget = manager.get_budget("NonExistent")
        assert budget is None
    
    def test_calculate_progress(self):
        """Test budget progress calculation."""
        manager = BudgetManager()
        budget = manager.create_budget(
            name="Marketing",
            amount=1000.0,
            period=BudgetPeriod.MONTHLY,
            categories=["marketing"],
        )
        
        # Create transactions for current month
        today = date.today()
        transactions = [
            Transaction(
                date=today,
                amount=-300.0,
                description="Ad spend",
                type=TransactionType.EXPENSE,
                category=ExpenseCategory.MARKETING,
            ),
            Transaction(
                date=today,
                amount=-200.0,
                description="More ads",
                type=TransactionType.EXPENSE,
                category=ExpenseCategory.MARKETING,
            ),
        ]
        
        progress = manager.calculate_progress(budget, transactions, today)
        
        assert progress.spent == 500.0
        assert progress.remaining == 500.0
        assert progress.percentage_used == 50.0
        assert progress.status == BudgetStatus.ON_TRACK
    
    def test_exceeded_budget(self):
        """Test detection of exceeded budget."""
        manager = BudgetManager()
        budget = manager.create_budget(
            name="Small Budget",
            amount=100.0,
            period=BudgetPeriod.MONTHLY,
        )
        
        today = date.today()
        transactions = [
            Transaction(
                date=today,
                amount=-150.0,
                description="Over budget",
                type=TransactionType.EXPENSE,
            ),
        ]
        
        progress = manager.calculate_progress(budget, transactions, today)
        
        assert progress.spent == 150.0
        assert progress.remaining == -50.0
        assert progress.percentage_used == 150.0
        assert progress.status == BudgetStatus.EXCEEDED
    
    def test_warning_threshold(self):
        """Test warning threshold detection."""
        manager = BudgetManager()
        budget = manager.create_budget(
            name="Test",
            amount=100.0,
            period=BudgetPeriod.MONTHLY,
            warning_threshold=0.75,
        )
        
        today = date.today()
        transactions = [
            Transaction(
                date=today,
                amount=-80.0,
                description="Almost over",
                type=TransactionType.EXPENSE,
            ),
        ]
        
        progress = manager.calculate_progress(budget, transactions, today)
        assert progress.status == BudgetStatus.WARNING
    
    def test_get_report(self):
        """Test full budget report generation."""
        manager = BudgetManager()
        manager.create_budget("Marketing", 5000.0, categories=["marketing"])
        manager.create_budget("Travel", 2000.0, categories=["travel"])
        
        today = date.today()
        transactions = [
            Transaction(
                date=today,
                amount=-1000.0,
                description="Ads",
                type=TransactionType.EXPENSE,
                category=ExpenseCategory.MARKETING,
            ),
            Transaction(
                date=today,
                amount=-500.0,
                description="Flight",
                type=TransactionType.EXPENSE,
                category=ExpenseCategory.TRAVEL,
            ),
        ]
        
        report = manager.get_report(transactions, today)
        
        assert report.total_budgeted == 7000.0
        assert report.total_spent == 1500.0
        assert report.total_remaining == 5500.0
        assert len(report.budgets) == 2
    
    def test_alerts_generation(self):
        """Test that alerts are generated for budget issues."""
        manager = BudgetManager()
        manager.create_budget("Test", 100.0)
        
        today = date.today()
        transactions = [
            Transaction(
                date=today,
                amount=-150.0,
                description="Over",
                type=TransactionType.EXPENSE,
            ),
        ]
        
        report = manager.get_report(transactions, today)
        
        # Should have alert for exceeded budget
        assert len(report.alerts) > 0
        exceeded_alerts = [a for a in report.alerts if a.alert_type == "exceeded"]
        assert len(exceeded_alerts) > 0
    
    def test_export_budgets(self):
        """Test budget export."""
        manager = BudgetManager()
        manager.create_budget("Marketing", 5000.0, categories=["marketing"])
        
        exported = manager.export_budgets()
        
        assert len(exported) == 1
        assert exported[0]["name"] == "Marketing"
        assert exported[0]["amount"] == 5000.0


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_create_monthly_budget(self):
        """Test create_monthly_budget function."""
        budget = create_monthly_budget("Test", 1000.0, ["marketing"])
        
        assert budget.name == "Test"
        assert budget.amount == 1000.0
        assert budget.period == BudgetPeriod.MONTHLY
    
    def test_check_budgets(self):
        """Test check_budgets function."""
        budgets = [
            Budget(name="Test", amount=1000.0, period=BudgetPeriod.MONTHLY)
        ]
        transactions = [
            Transaction(
                date=date.today(),
                amount=-500.0,
                description="Test",
                type=TransactionType.EXPENSE,
            )
        ]
        
        report = check_budgets(transactions, budgets)
        assert isinstance(report, BudgetReport)
