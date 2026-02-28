"""
Bank Reconciliation — match bank transactions with accounting records.

Inspired by Akaunting's bank reconciliation feature. Helps match
imported bank transactions with invoices, expenses, and other records
to ensure accurate bookkeeping.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from difflib import SequenceMatcher
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fiscalpilot.models.financial import Transaction, Invoice

logger = logging.getLogger("fiscalpilot.analyzers.reconciliation")


class ReconciliationStatus(str, Enum):
    """Status of a reconciliation item."""
    
    MATCHED = "matched"
    UNMATCHED = "unmatched"
    PARTIAL = "partial"
    MANUAL_REVIEW = "manual_review"
    EXCLUDED = "excluded"


class MatchType(str, Enum):
    """How a match was made."""
    
    EXACT = "exact"           # Exact amount and date
    REFERENCE = "reference"   # Matched by reference number
    FUZZY = "fuzzy"          # Close match
    MULTIPLE = "multiple"    # Multiple records match one bank entry
    SUGGESTED = "suggested"  # AI suggested match


@dataclass
class BankEntry:
    """A single bank statement entry."""
    
    date: date
    description: str
    amount: float
    reference: str | None = None
    balance: float | None = None
    entry_id: str | None = None
    
    @property
    def is_credit(self) -> bool:
        return self.amount > 0
    
    @property
    def is_debit(self) -> bool:
        return self.amount < 0


@dataclass
class ReconciliationMatch:
    """A match between bank entry and accounting record."""
    
    bank_entry: BankEntry
    matched_record: Any  # Transaction, Invoice, or other record
    match_type: MatchType
    confidence: float
    difference: float = 0.0
    match_reason: str = ""
    
    @property
    def is_exact(self) -> bool:
        return abs(self.difference) < 0.01


@dataclass
class ReconciliationItem:
    """An item in the reconciliation process."""
    
    bank_entry: BankEntry
    status: ReconciliationStatus = ReconciliationStatus.UNMATCHED
    matches: list[ReconciliationMatch] = field(default_factory=list)
    selected_match: ReconciliationMatch | None = None
    notes: str = ""
    
    @property
    def best_match(self) -> ReconciliationMatch | None:
        if self.selected_match:
            return self.selected_match
        if self.matches:
            return max(self.matches, key=lambda m: m.confidence)
        return None


@dataclass
class ReconciliationReport:
    """Summary of a reconciliation session."""
    
    account_name: str
    period_start: date
    period_end: date
    opening_balance: float
    closing_balance: float
    
    # Bank statement summary
    total_credits: float = 0.0
    total_debits: float = 0.0
    total_entries: int = 0
    
    # Reconciliation results
    matched_count: int = 0
    unmatched_count: int = 0
    partial_count: int = 0
    review_count: int = 0
    
    items: list[ReconciliationItem] = field(default_factory=list)
    differences: list[dict[str, Any]] = field(default_factory=list)
    
    @property
    def is_balanced(self) -> bool:
        """Check if reconciliation is balanced."""
        return len(self.differences) == 0 and self.unmatched_count == 0
    
    @property
    def reconciliation_rate(self) -> float:
        """Percentage of items successfully reconciled."""
        if self.total_entries == 0:
            return 0.0
        return self.matched_count / self.total_entries


class BankReconciler:
    """
    Reconcile bank statements with accounting records.
    
    Features inspired by Akaunting:
    - Match bank entries to invoices, expenses, transfers
    - Auto-match by reference number or exact amount
    - Fuzzy matching for close matches
    - Handle partial payments and multiple matches
    - Track unreconciled items for review
    
    Example usage:
        reconciler = BankReconciler()
        report = reconciler.reconcile(
            bank_entries=bank_statement,
            transactions=accounting_records,
            account_name="Business Checking",
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 31),
        )
        print(f"Matched: {report.matched_count}/{report.total_entries}")
    """
    
    def __init__(
        self,
        date_tolerance_days: int = 3,
        amount_tolerance: float = 0.01,
        fuzzy_threshold: float = 0.8,
    ):
        """
        Initialize reconciler.
        
        Args:
            date_tolerance_days: Days before/after to look for matches.
            amount_tolerance: Percentage tolerance for amounts (0.01 = 1%).
            fuzzy_threshold: Minimum similarity score for fuzzy matching.
        """
        self.date_tolerance_days = date_tolerance_days
        self.amount_tolerance = amount_tolerance
        self.fuzzy_threshold = fuzzy_threshold
    
    def reconcile(
        self,
        bank_entries: list[BankEntry],
        transactions: list[Transaction],
        account_name: str = "Default Account",
        period_start: date | None = None,
        period_end: date | None = None,
        invoices: list[Invoice] | None = None,
    ) -> ReconciliationReport:
        """
        Reconcile bank entries with accounting records.
        
        Args:
            bank_entries: Bank statement entries.
            transactions: Accounting transactions to match against.
            account_name: Name of the bank account.
            period_start: Start of reconciliation period.
            period_end: End of reconciliation period.
            invoices: Optional invoices to match against.
            
        Returns:
            ReconciliationReport with all matches and discrepancies.
        """
        if not bank_entries:
            return ReconciliationReport(
                account_name=account_name,
                period_start=period_start or date.today(),
                period_end=period_end or date.today(),
                opening_balance=0.0,
                closing_balance=0.0,
            )
        
        # Default period from bank entries
        if not period_start:
            period_start = min(e.date for e in bank_entries)
        if not period_end:
            period_end = max(e.date for e in bank_entries)
        
        # Calculate totals
        credits = sum(e.amount for e in bank_entries if e.is_credit)
        debits = sum(e.amount for e in bank_entries if e.is_debit)
        
        # Find opening/closing balance
        sorted_entries = sorted(bank_entries, key=lambda e: e.date)
        opening = sorted_entries[0].balance or 0.0
        closing = sorted_entries[-1].balance or 0.0
        
        # Create reconciliation items
        items = []
        for entry in bank_entries:
            item = ReconciliationItem(bank_entry=entry)
            
            # Find matches in transactions
            txn_matches = self._find_transaction_matches(entry, transactions)
            item.matches.extend(txn_matches)
            
            # Find matches in invoices if provided
            if invoices:
                inv_matches = self._find_invoice_matches(entry, invoices)
                item.matches.extend(inv_matches)
            
            # Determine status
            if item.matches:
                best = max(item.matches, key=lambda m: m.confidence)
                if best.confidence > 0.9 and best.is_exact:
                    item.status = ReconciliationStatus.MATCHED
                    item.selected_match = best
                elif best.confidence > 0.7:
                    item.status = ReconciliationStatus.MANUAL_REVIEW
                else:
                    item.status = ReconciliationStatus.PARTIAL
            else:
                item.status = ReconciliationStatus.UNMATCHED
            
            items.append(item)
        
        # Count statuses
        matched = sum(1 for i in items if i.status == ReconciliationStatus.MATCHED)
        unmatched = sum(1 for i in items if i.status == ReconciliationStatus.UNMATCHED)
        partial = sum(1 for i in items if i.status == ReconciliationStatus.PARTIAL)
        review = sum(1 for i in items if i.status == ReconciliationStatus.MANUAL_REVIEW)
        
        # Find differences
        differences = self._find_differences(items, transactions)
        
        return ReconciliationReport(
            account_name=account_name,
            period_start=period_start,
            period_end=period_end,
            opening_balance=opening,
            closing_balance=closing,
            total_credits=credits,
            total_debits=debits,
            total_entries=len(bank_entries),
            matched_count=matched,
            unmatched_count=unmatched,
            partial_count=partial,
            review_count=review,
            items=items,
            differences=differences,
        )
    
    def _find_transaction_matches(
        self,
        entry: BankEntry,
        transactions: list[Transaction],
    ) -> list[ReconciliationMatch]:
        """Find transaction matches for a bank entry."""
        matches = []
        
        for txn in transactions:
            confidence = 0.0
            match_type = None
            match_reason = ""
            
            # Check by reference
            if entry.reference and txn.reference:
                if entry.reference == txn.reference:
                    confidence = 0.99
                    match_type = MatchType.REFERENCE
                    match_reason = f"Reference match: {entry.reference}"
            
            # Check by exact amount
            if self._amounts_match_exact(entry.amount, txn.amount):
                if self._dates_close(entry.date, txn.date):
                    confidence = max(confidence, 0.9)
                    match_type = match_type or MatchType.EXACT
                    match_reason = match_reason or f"Exact amount ${entry.amount:,.2f}"
            
            # Check by similar amount (within tolerance)
            elif self._amounts_match_fuzzy(entry.amount, txn.amount):
                if self._dates_close(entry.date, txn.date):
                    confidence = max(confidence, 0.7)
                    match_type = match_type or MatchType.FUZZY
                    diff = abs(entry.amount - txn.amount)
                    match_reason = match_reason or f"Close amount (diff: ${diff:.2f})"
            
            # Check description similarity
            if entry.description and txn.description:
                similarity = SequenceMatcher(
                    None,
                    entry.description.lower(),
                    txn.description.lower()
                ).ratio()
                
                if similarity >= self.fuzzy_threshold:
                    confidence = max(confidence, similarity * 0.8)
                    if not match_type:
                        match_type = MatchType.FUZZY
                        match_reason = f"Description similarity: {similarity:.0%}"
            
            if confidence > 0.5:
                matches.append(ReconciliationMatch(
                    bank_entry=entry,
                    matched_record=txn,
                    match_type=match_type or MatchType.FUZZY,
                    confidence=confidence,
                    difference=abs(entry.amount) - abs(txn.amount),
                    match_reason=match_reason,
                ))
        
        return sorted(matches, key=lambda m: m.confidence, reverse=True)
    
    def _find_invoice_matches(
        self,
        entry: BankEntry,
        invoices: list[Invoice],
    ) -> list[ReconciliationMatch]:
        """Find invoice matches for a bank entry (typically credits)."""
        matches = []
        
        if not entry.is_credit:
            return matches  # Invoices typically match to credits (payments received)
        
        for inv in invoices:
            confidence = 0.0
            match_type = None
            match_reason = ""
            
            # Check by invoice reference
            if entry.reference and inv.invoice_number:
                if inv.invoice_number in entry.reference or entry.reference in inv.invoice_number:
                    confidence = 0.95
                    match_type = MatchType.REFERENCE
                    match_reason = f"Invoice number match: {inv.invoice_number}"
            
            # Check by amount
            total = inv.total_amount or 0
            if self._amounts_match_exact(entry.amount, total):
                confidence = max(confidence, 0.85)
                match_type = match_type or MatchType.EXACT
                match_reason = match_reason or f"Amount match: ${total:,.2f}"
            
            if confidence > 0.5:
                matches.append(ReconciliationMatch(
                    bank_entry=entry,
                    matched_record=inv,
                    match_type=match_type or MatchType.FUZZY,
                    confidence=confidence,
                    difference=entry.amount - total,
                    match_reason=match_reason,
                ))
        
        return matches
    
    def _find_differences(
        self,
        items: list[ReconciliationItem],
        transactions: list[Transaction],
    ) -> list[dict[str, Any]]:
        """Find accounting differences."""
        differences = []
        
        # Unmatched bank entries
        for item in items:
            if item.status == ReconciliationStatus.UNMATCHED:
                differences.append({
                    "type": "unmatched_bank_entry",
                    "date": item.bank_entry.date,
                    "amount": item.bank_entry.amount,
                    "description": item.bank_entry.description,
                    "action_needed": "Find or create matching record",
                })
        
        # Find unreconciled transactions (in accounting but not in bank)
        matched_txns = set()
        for item in items:
            if item.selected_match and hasattr(item.selected_match.matched_record, 'id'):
                matched_txns.add(id(item.selected_match.matched_record))
        
        for txn in transactions:
            if id(txn) not in matched_txns:
                differences.append({
                    "type": "unmatched_transaction",
                    "date": txn.date,
                    "amount": txn.amount,
                    "description": txn.description,
                    "vendor": txn.vendor,
                    "action_needed": "Verify if cleared or remove",
                })
        
        return differences
    
    def _amounts_match_exact(self, amt1: float, amt2: float) -> bool:
        """Check for exact amount match (within penny)."""
        return abs(abs(amt1) - abs(amt2)) < 0.01
    
    def _amounts_match_fuzzy(self, amt1: float, amt2: float) -> bool:
        """Check for fuzzy amount match (within tolerance)."""
        if amt1 == 0 and amt2 == 0:
            return True
        max_amt = max(abs(amt1), abs(amt2))
        diff = abs(abs(amt1) - abs(amt2))
        return diff <= max_amt * self.amount_tolerance
    
    def _dates_close(self, date1: date | None, date2: date | None) -> bool:
        """Check if dates are within tolerance."""
        if not date1 or not date2:
            return True
        delta = abs((date1 - date2).days)
        return delta <= self.date_tolerance_days
    
    def auto_reconcile(
        self,
        bank_entries: list[BankEntry],
        transactions: list[Transaction],
        confidence_threshold: float = 0.9,
    ) -> tuple[list[ReconciliationItem], list[ReconciliationItem]]:
        """
        Automatically reconcile high-confidence matches.
        
        Args:
            bank_entries: Bank statement entries.
            transactions: Accounting transactions.
            confidence_threshold: Minimum confidence for auto-reconcile.
            
        Returns:
            Tuple of (reconciled_items, needs_review_items).
        """
        reconciled = []
        needs_review = []
        
        for entry in bank_entries:
            item = ReconciliationItem(bank_entry=entry)
            matches = self._find_transaction_matches(entry, transactions)
            
            if matches:
                best = matches[0]
                if best.confidence >= confidence_threshold and best.is_exact:
                    item.status = ReconciliationStatus.MATCHED
                    item.selected_match = best
                    reconciled.append(item)
                else:
                    item.status = ReconciliationStatus.MANUAL_REVIEW
                    item.matches = matches
                    needs_review.append(item)
            else:
                item.status = ReconciliationStatus.UNMATCHED
                needs_review.append(item)
        
        return reconciled, needs_review


# Convenience function
def reconcile_bank_statement(
    bank_entries: list[BankEntry],
    transactions: list[Transaction],
    account_name: str = "Bank Account",
) -> ReconciliationReport:
    """Quick bank reconciliation."""
    reconciler = BankReconciler()
    return reconciler.reconcile(bank_entries, transactions, account_name)
