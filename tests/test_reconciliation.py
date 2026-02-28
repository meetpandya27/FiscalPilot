"""Tests for the Bank Reconciliation module."""

import pytest
from datetime import date
from fiscalpilot.analyzers.reconciliation import (
    BankReconciler,
    BankEntry,
    ReconciliationItem,
    ReconciliationMatch,
    ReconciliationStatus,
    MatchType,
    ReconciliationReport,
    reconcile_bank_statement,
)
from fiscalpilot.models.financial import Transaction, TransactionType


class TestBankEntry:
    """Test BankEntry dataclass."""
    
    def test_bank_entry_creation(self):
        """Test basic bank entry creation."""
        entry = BankEntry(
            date=date(2025, 1, 15),
            amount=-150.0,
            description="CHECKPMT 1234",
            reference="1234",
        )
        
        assert entry.date == date(2025, 1, 15)
        assert entry.amount == -150.0
        assert entry.reference == "1234"
    
    def test_bank_entry_is_credit(self):
        """Test credit detection."""
        credit = BankEntry(
            date=date(2025, 1, 15),
            amount=100.0,
            description="Deposit",
        )
        assert credit.is_credit is True
        assert credit.is_debit is False
    
    def test_bank_entry_is_debit(self):
        """Test debit detection."""
        debit = BankEntry(
            date=date(2025, 1, 15),
            amount=-100.0,
            description="Payment",
        )
        assert debit.is_debit is True
        assert debit.is_credit is False


class TestReconciliationMatch:
    """Test ReconciliationMatch class."""
    
    def test_match_creation(self):
        """Test basic match creation."""
        entry = BankEntry(
            date=date(2025, 1, 15),
            amount=-100.0,
            description="Payment",
        )
        txn = Transaction(
            date=date(2025, 1, 15),
            amount=100.0,
            description="Payment",
            type=TransactionType.EXPENSE,
        )
        
        match = ReconciliationMatch(
            bank_entry=entry,
            matched_record=txn,
            match_type=MatchType.EXACT,
            confidence=0.95,
        )
        
        assert match.match_type == MatchType.EXACT
        assert match.confidence == 0.95
    
    def test_match_is_exact(self):
        """Test is_exact property."""
        entry = BankEntry(
            date=date(2025, 1, 15),
            amount=-100.0,
            description="Payment",
        )
        
        exact_match = ReconciliationMatch(
            bank_entry=entry,
            matched_record=None,
            match_type=MatchType.EXACT,
            confidence=1.0,
            difference=0.0,
        )
        
        assert exact_match.is_exact is True
        
        fuzzy_match = ReconciliationMatch(
            bank_entry=entry,
            matched_record=None,
            match_type=MatchType.FUZZY,
            confidence=0.8,
            difference=5.0,
        )
        
        assert fuzzy_match.is_exact is False


class TestReconciliationItem:
    """Test ReconciliationItem class."""
    
    def test_item_creation(self):
        """Test basic item creation."""
        entry = BankEntry(
            date=date(2025, 1, 15),
            amount=-100.0,
            description="Payment",
        )
        
        item = ReconciliationItem(bank_entry=entry)
        
        assert item.status == ReconciliationStatus.UNMATCHED
        assert len(item.matches) == 0
    
    def test_item_best_match(self):
        """Test best_match property."""
        entry = BankEntry(
            date=date(2025, 1, 15),
            amount=-100.0,
            description="Payment",
        )
        
        item = ReconciliationItem(bank_entry=entry)
        
        # No matches => no best match
        assert item.best_match is None
        
        # Add some matches
        match1 = ReconciliationMatch(
            bank_entry=entry,
            matched_record=None,
            match_type=MatchType.FUZZY,
            confidence=0.7,
        )
        match2 = ReconciliationMatch(
            bank_entry=entry,
            matched_record=None,
            match_type=MatchType.EXACT,
            confidence=0.95,
        )
        
        item.matches = [match1, match2]
        
        # Should return highest confidence
        assert item.best_match.confidence == 0.95


class TestBankReconciler:
    """Test BankReconciler class."""
    
    def test_init_default(self):
        """Test default initialization."""
        reconciler = BankReconciler()
        assert reconciler.date_tolerance_days == 3
        assert reconciler.amount_tolerance == 0.01
    
    def test_init_custom(self):
        """Test custom initialization."""
        reconciler = BankReconciler(
            date_tolerance_days=5,
            amount_tolerance=0.02,
            fuzzy_threshold=0.9,
        )
        
        assert reconciler.date_tolerance_days == 5
        assert reconciler.amount_tolerance == 0.02
        assert reconciler.fuzzy_threshold == 0.9
    
    def test_reconcile_empty(self):
        """Test reconciliation with empty entries."""
        reconciler = BankReconciler()
        
        report = reconciler.reconcile(
            bank_entries=[],
            transactions=[],
        )
        
        assert report.total_entries == 0
    
    def test_reconcile_with_matches(self):
        """Test reconciliation with matching entries."""
        reconciler = BankReconciler()
        
        bank_entries = [
            BankEntry(
                date=date(2025, 1, 15),
                amount=-100.0,
                description="Vendor payment",
            ),
        ]
        
        transactions = [
            Transaction(
                date=date(2025, 1, 15),
                amount=100.0,  # Matching amount (absolute)
                description="Vendor payment",
                type=TransactionType.EXPENSE,
            ),
        ]
        
        report = reconciler.reconcile(bank_entries, transactions)
        
        # Should find at least the entries
        assert report.total_entries == 1
    
    def test_reconcile_report_counts(self):
        """Test reconciliation report statistics."""
        reconciler = BankReconciler()
        
        bank_entries = [
            BankEntry(date=date(2025, 1, 15), amount=-100.0, description="Entry 1"),
            BankEntry(date=date(2025, 1, 16), amount=-200.0, description="Entry 2"),
        ]
        
        transactions = [
            Transaction(
                date=date(2025, 1, 15),
                amount=100.0,
                description="Entry 1",
                type=TransactionType.EXPENSE,
            ),
        ]
        
        report = reconciler.reconcile(bank_entries, transactions)
        
        assert report.total_entries == 2


class TestReconciliationReport:
    """Test ReconciliationReport class."""
    
    def test_report_creation(self):
        """Test report creation."""
        report = ReconciliationReport(
            account_name="Business Checking",
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31),
            opening_balance=1000.0,
            closing_balance=1500.0,
            total_entries=10,
            matched_count=8,
            unmatched_count=2,
        )
        
        assert report.account_name == "Business Checking"
        assert report.total_entries == 10
    
    def test_report_is_balanced(self):
        """Test is_balanced property."""
        balanced = ReconciliationReport(
            account_name="Test",
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31),
            opening_balance=1000.0,
            closing_balance=1000.0,
            total_entries=5,
            matched_count=5,
            unmatched_count=0,
        )
        
        assert balanced.is_balanced is True
        
        unbalanced = ReconciliationReport(
            account_name="Test",
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31),
            opening_balance=1000.0,
            closing_balance=1000.0,
            total_entries=5,
            matched_count=3,
            unmatched_count=2,
        )
        
        assert unbalanced.is_balanced is False
    
    def test_report_reconciliation_rate(self):
        """Test reconciliation_rate property."""
        report = ReconciliationReport(
            account_name="Test",
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31),
            opening_balance=1000.0,
            closing_balance=1000.0,
            total_entries=10,
            matched_count=8,
            unmatched_count=2,
        )
        
        assert report.reconciliation_rate == 0.8
    
    def test_report_reconciliation_rate_empty(self):
        """Test reconciliation_rate with no entries."""
        report = ReconciliationReport(
            account_name="Test",
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31),
            opening_balance=0.0,
            closing_balance=0.0,
            total_entries=0,
        )
        
        assert report.reconciliation_rate == 0.0


class TestMatchType:
    """Test MatchType enum."""
    
    def test_match_type_values(self):
        """Test match type enum values."""
        assert MatchType.EXACT.value == "exact"
        assert MatchType.REFERENCE.value == "reference"
        assert MatchType.FUZZY.value == "fuzzy"
        assert MatchType.MULTIPLE.value == "multiple"
        assert MatchType.SUGGESTED.value == "suggested"


class TestReconciliationStatus:
    """Test ReconciliationStatus enum."""
    
    def test_status_values(self):
        """Test status enum values."""
        assert ReconciliationStatus.MATCHED.value == "matched"
        assert ReconciliationStatus.UNMATCHED.value == "unmatched"
        assert ReconciliationStatus.PARTIAL.value == "partial"
        assert ReconciliationStatus.MANUAL_REVIEW.value == "manual_review"
        assert ReconciliationStatus.EXCLUDED.value == "excluded"


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_reconcile_bank_statement(self):
        """Test reconcile_bank_statement convenience function."""
        bank_entries = [
            BankEntry(
                date=date(2025, 1, 15),
                amount=-100.0,
                description="Test payment",
            ),
        ]
        
        transactions = [
            Transaction(
                date=date(2025, 1, 15),
                amount=100.0,
                description="Test payment",
                type=TransactionType.EXPENSE,
            ),
        ]
        
        report = reconcile_bank_statement(bank_entries, transactions)
        
        assert isinstance(report, ReconciliationReport)
        assert report.total_entries == 1
