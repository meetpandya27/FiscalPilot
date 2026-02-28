"""
Duplicate Detection — find duplicate payments and invoices.

Inspired by Vic.ai's duplicate detection system that catches 
duplicate payments before they happen. Uses multiple matching
strategies to identify potential duplicates.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from difflib import SequenceMatcher
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable
from collections import defaultdict

if TYPE_CHECKING:
    from fiscalpilot.models.financial import Transaction, Invoice

logger = logging.getLogger("fiscalpilot.analyzers.duplicate_detector")


class DuplicateType(str, Enum):
    """Type of duplicate detected."""
    
    EXACT = "exact"              # Identical transactions
    AMOUNT_MATCH = "amount"      # Same amount, close dates
    VENDOR_AMOUNT = "vendor"     # Same vendor + amount
    INVOICE_NUMBER = "invoice"   # Same invoice number
    SIMILAR = "similar"          # Fuzzy match
    SPLIT = "split"              # Split payments to avoid limits


class DuplicateRisk(str, Enum):
    """Risk level of the potential duplicate."""
    
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class DuplicateMatch:
    """A potential duplicate match."""
    
    duplicate_type: DuplicateType
    risk: DuplicateRisk
    confidence: float
    transactions: list[Any] = field(default_factory=list)  # Transaction or Invoice
    match_reason: str = ""
    potential_savings: float = 0.0
    
    @property
    def is_high_risk(self) -> bool:
        return self.risk == DuplicateRisk.HIGH


@dataclass
class DuplicateReport:
    """Summary report of duplicate detection."""
    
    total_analyzed: int
    duplicates_found: int
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
    potential_savings: float
    matches: list[DuplicateMatch] = field(default_factory=list)
    
    @property
    def has_duplicates(self) -> bool:
        return self.duplicates_found > 0


class DuplicateDetector:
    """
    Detect duplicate payments, invoices, and suspicious patterns.
    
    Features inspired by Vic.ai:
    - Exact duplicate detection (same amount, date, vendor)
    - Fuzzy matching for similar transactions
    - Invoice number duplicate checking
    - Split payment detection (avoiding approval limits)
    - Configurable matching thresholds
    
    Example usage:
        detector = DuplicateDetector()
        report = detector.scan_transactions(transactions)
        print(f"Found {report.duplicates_found} potential duplicates")
        print(f"Potential savings: ${report.potential_savings:,.2f}")
    """
    
    def __init__(
        self,
        date_window_days: int = 30,
        amount_tolerance: float = 0.01,
        fuzzy_threshold: float = 0.85,
    ):
        """
        Initialize duplicate detector.
        
        Args:
            date_window_days: Days to look back for duplicates.
            amount_tolerance: Tolerance for amount matching (0.01 = 1%).
            fuzzy_threshold: Minimum similarity for fuzzy matching (0-1).
        """
        self.date_window_days = date_window_days
        self.amount_tolerance = amount_tolerance
        self.fuzzy_threshold = fuzzy_threshold
        
    def scan_transactions(
        self,
        transactions: list[Transaction],
        check_splits: bool = True,
    ) -> DuplicateReport:
        """
        Scan transactions for duplicates.
        
        Args:
            transactions: List of transactions to scan.
            check_splits: Whether to check for split payment patterns.
            
        Returns:
            DuplicateReport with all findings.
        """
        matches: list[DuplicateMatch] = []
        
        # Group transactions by amount for faster matching
        by_amount = defaultdict(list)
        for txn in transactions:
            # Round to 2 decimals for grouping
            amt_key = round(txn.amount, 2)
            by_amount[amt_key].append(txn)
        
        # Check exact duplicates (same amount, similar date)
        matches.extend(self._find_exact_duplicates(transactions, by_amount))
        
        # Check vendor + amount duplicates
        matches.extend(self._find_vendor_amount_duplicates(transactions))
        
        # Check for similar descriptions (fuzzy matching)
        matches.extend(self._find_fuzzy_duplicates(transactions))
        
        # Check for split payments
        if check_splits:
            matches.extend(self._find_split_payments(transactions))
        
        # Calculate report statistics
        total_savings = sum(m.potential_savings for m in matches)
        high_risk = sum(1 for m in matches if m.risk == DuplicateRisk.HIGH)
        medium_risk = sum(1 for m in matches if m.risk == DuplicateRisk.MEDIUM)
        low_risk = sum(1 for m in matches if m.risk == DuplicateRisk.LOW)
        
        return DuplicateReport(
            total_analyzed=len(transactions),
            duplicates_found=len(matches),
            high_risk_count=high_risk,
            medium_risk_count=medium_risk,
            low_risk_count=low_risk,
            potential_savings=total_savings,
            matches=matches,
        )
    
    def scan_invoices(self, invoices: list[Invoice]) -> DuplicateReport:
        """
        Scan invoices for duplicates.
        
        Args:
            invoices: List of invoices to scan.
            
        Returns:
            DuplicateReport with all findings.
        """
        matches: list[DuplicateMatch] = []
        
        # Check for duplicate invoice numbers
        matches.extend(self._find_invoice_number_duplicates(invoices))
        
        # Check for same vendor + same amount
        matches.extend(self._find_invoice_vendor_duplicates(invoices))
        
        # Calculate statistics
        total_savings = sum(m.potential_savings for m in matches)
        high_risk = sum(1 for m in matches if m.risk == DuplicateRisk.HIGH)
        medium_risk = sum(1 for m in matches if m.risk == DuplicateRisk.MEDIUM)
        low_risk = sum(1 for m in matches if m.risk == DuplicateRisk.LOW)
        
        return DuplicateReport(
            total_analyzed=len(invoices),
            duplicates_found=len(matches),
            high_risk_count=high_risk,
            medium_risk_count=medium_risk,
            low_risk_count=low_risk,
            potential_savings=total_savings,
            matches=matches,
        )
    
    def _find_exact_duplicates(
        self,
        transactions: list[Transaction],
        by_amount: dict[float, list[Transaction]],
    ) -> list[DuplicateMatch]:
        """Find exact duplicate transactions."""
        matches = []
        seen_pairs = set()
        
        for amt, txns in by_amount.items():
            if len(txns) < 2:
                continue
            
            for i, t1 in enumerate(txns):
                for t2 in txns[i + 1:]:
                    # Skip if already seen this pair
                    pair_key = tuple(sorted([id(t1), id(t2)]))
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)
                    
                    # Check if dates are within window
                    if not self._dates_within_window(t1.date, t2.date):
                        continue
                    
                    # Check vendor match
                    vendor_match = (
                        t1.vendor and t2.vendor and 
                        t1.vendor.lower() == t2.vendor.lower()
                    )
                    
                    if vendor_match:
                        matches.append(DuplicateMatch(
                            duplicate_type=DuplicateType.EXACT,
                            risk=DuplicateRisk.HIGH,
                            confidence=0.95,
                            transactions=[t1, t2],
                            match_reason=f"Same vendor ({t1.vendor}) and amount (${amt:,.2f}) within {self.date_window_days} days",
                            potential_savings=amt,
                        ))
                    else:
                        matches.append(DuplicateMatch(
                            duplicate_type=DuplicateType.AMOUNT_MATCH,
                            risk=DuplicateRisk.MEDIUM,
                            confidence=0.75,
                            transactions=[t1, t2],
                            match_reason=f"Same amount (${amt:,.2f}) within {self.date_window_days} days",
                            potential_savings=amt,
                        ))
        
        return matches
    
    def _find_vendor_amount_duplicates(
        self,
        transactions: list[Transaction],
    ) -> list[DuplicateMatch]:
        """Find duplicates with same vendor and amount."""
        matches = []
        
        # Group by vendor + amount
        vendor_amount = defaultdict(list)
        for txn in transactions:
            if txn.vendor:
                key = (txn.vendor.lower(), round(txn.amount, 2))
                vendor_amount[key].append(txn)
        
        seen_pairs = set()
        for (vendor, amt), txns in vendor_amount.items():
            if len(txns) < 2:
                continue
            
            # Check all pairs within date window
            for i, t1 in enumerate(txns):
                for t2 in txns[i + 1:]:
                    pair_key = tuple(sorted([id(t1), id(t2)]))
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)
                    
                    if self._dates_within_window(t1.date, t2.date):
                        matches.append(DuplicateMatch(
                            duplicate_type=DuplicateType.VENDOR_AMOUNT,
                            risk=DuplicateRisk.HIGH,
                            confidence=0.9,
                            transactions=[t1, t2],
                            match_reason=f"Vendor '{vendor}' with same amount ${amt:,.2f}",
                            potential_savings=amt,
                        ))
        
        return matches
    
    def _find_fuzzy_duplicates(
        self,
        transactions: list[Transaction],
    ) -> list[DuplicateMatch]:
        """Find similar transactions using fuzzy matching."""
        matches = []
        seen_pairs = set()
        
        # Only check transactions with descriptions
        with_desc = [t for t in transactions if t.description]
        
        for i, t1 in enumerate(with_desc):
            for t2 in with_desc[i + 1:]:
                pair_key = tuple(sorted([id(t1), id(t2)]))
                if pair_key in seen_pairs:
                    continue
                
                # Check date window first (faster)
                if not self._dates_within_window(t1.date, t2.date):
                    continue
                
                # Check amount similarity
                amt_similar = self._amounts_similar(t1.amount, t2.amount)
                if not amt_similar:
                    continue
                
                # Fuzzy match descriptions
                similarity = SequenceMatcher(
                    None,
                    t1.description.lower(),
                    t2.description.lower()
                ).ratio()
                
                if similarity >= self.fuzzy_threshold:
                    seen_pairs.add(pair_key)
                    matches.append(DuplicateMatch(
                        duplicate_type=DuplicateType.SIMILAR,
                        risk=DuplicateRisk.MEDIUM if similarity > 0.9 else DuplicateRisk.LOW,
                        confidence=similarity,
                        transactions=[t1, t2],
                        match_reason=f"Similar descriptions ({similarity:.0%} match)",
                        potential_savings=min(t1.amount, t2.amount),
                    ))
        
        return matches
    
    def _find_split_payments(
        self,
        transactions: list[Transaction],
        threshold: float = 5000,
    ) -> list[DuplicateMatch]:
        """
        Find potential split payments (fraud pattern).
        
        Split payments are when someone breaks a large payment into
        smaller ones to avoid approval thresholds.
        """
        matches = []
        
        # Group by vendor and date
        vendor_date = defaultdict(list)
        for txn in transactions:
            if txn.vendor and txn.amount < threshold:
                key = (txn.vendor.lower(), txn.date)
                vendor_date[key].append(txn)
        
        for (vendor, d), txns in vendor_date.items():
            if len(txns) < 2:
                continue
            
            total = sum(t.amount for t in txns)
            
            # If combined total exceeds threshold, flag as potential split
            if total > threshold:
                matches.append(DuplicateMatch(
                    duplicate_type=DuplicateType.SPLIT,
                    risk=DuplicateRisk.HIGH,
                    confidence=0.85,
                    transactions=txns,
                    match_reason=f"{len(txns)} payments to '{vendor}' on same day totaling ${total:,.2f} (threshold: ${threshold:,.2f})",
                    potential_savings=total - max(t.amount for t in txns),
                ))
        
        return matches
    
    def _find_invoice_number_duplicates(
        self,
        invoices: list[Invoice],
    ) -> list[DuplicateMatch]:
        """Find duplicate invoice numbers."""
        matches = []
        
        # Group by invoice number
        by_number = defaultdict(list)
        for inv in invoices:
            if inv.invoice_number:
                by_number[inv.invoice_number.upper()].append(inv)
        
        for number, invs in by_number.items():
            if len(invs) > 1:
                matches.append(DuplicateMatch(
                    duplicate_type=DuplicateType.INVOICE_NUMBER,
                    risk=DuplicateRisk.HIGH,
                    confidence=0.99,
                    transactions=invs,
                    match_reason=f"Duplicate invoice number: {number}",
                    potential_savings=sum(i.total_amount or 0 for i in invs[1:]),
                ))
        
        return matches
    
    def _find_invoice_vendor_duplicates(
        self,
        invoices: list[Invoice],
    ) -> list[DuplicateMatch]:
        """Find invoices with same vendor and amount."""
        matches = []
        seen_pairs = set()
        
        # Group by vendor + amount
        vendor_amount = defaultdict(list)
        for inv in invoices:
            if inv.vendor_name and inv.total_amount:
                key = (inv.vendor_name.lower(), round(inv.total_amount, 2))
                vendor_amount[key].append(inv)
        
        for (vendor, amt), invs in vendor_amount.items():
            if len(invs) < 2:
                continue
            
            for i, inv1 in enumerate(invs):
                for inv2 in invs[i + 1:]:
                    pair_key = tuple(sorted([id(inv1), id(inv2)]))
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)
                    
                    # Check date proximity
                    if inv1.invoice_date and inv2.invoice_date:
                        if self._dates_within_window(inv1.invoice_date, inv2.invoice_date):
                            matches.append(DuplicateMatch(
                                duplicate_type=DuplicateType.VENDOR_AMOUNT,
                                risk=DuplicateRisk.MEDIUM,
                                confidence=0.85,
                                transactions=[inv1, inv2],
                                match_reason=f"Same vendor and amount: {vendor} - ${amt:,.2f}",
                                potential_savings=amt,
                            ))
        
        return matches
    
    def _dates_within_window(
        self,
        date1: date | None,
        date2: date | None,
    ) -> bool:
        """Check if two dates are within the configured window."""
        if not date1 or not date2:
            return True  # If no date, consider it a potential match
        
        delta = abs((date1 - date2).days)
        return delta <= self.date_window_days
    
    def _amounts_similar(self, amt1: float, amt2: float) -> bool:
        """Check if two amounts are similar within tolerance."""
        if amt1 == 0 and amt2 == 0:
            return True
        avg = (abs(amt1) + abs(amt2)) / 2
        diff = abs(amt1 - amt2)
        return diff <= avg * self.amount_tolerance


# Convenience functions
def find_duplicates(
    transactions: list[Transaction],
    date_window: int = 30,
) -> DuplicateReport:
    """Quick duplicate scan for transactions."""
    detector = DuplicateDetector(date_window_days=date_window)
    return detector.scan_transactions(transactions)


def find_invoice_duplicates(invoices: list[Invoice]) -> DuplicateReport:
    """Quick duplicate scan for invoices."""
    detector = DuplicateDetector()
    return detector.scan_invoices(invoices)
