"""
Three-Way Matching — match POs, receipts, and invoices for AP automation.

Provides:
- Purchase order to receipt matching
- Receipt to invoice matching
- Three-way match validation
- Variance detection and tolerance handling
- Auto-approval for exact matches
- Exception routing for mismatches
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class MatchStatus(str, Enum):
    """Status of a match attempt."""
    
    MATCHED = "matched"  # All three documents match
    PARTIAL = "partial"  # Some items match
    QUANTITY_VARIANCE = "quantity_variance"
    PRICE_VARIANCE = "price_variance"
    MISSING_PO = "missing_po"
    MISSING_RECEIPT = "missing_receipt"
    MISSING_INVOICE = "missing_invoice"
    UNMATCHED = "unmatched"


class DocumentType(str, Enum):
    """Types of documents in three-way match."""
    
    PURCHASE_ORDER = "purchase_order"
    RECEIPT = "receipt"
    INVOICE = "invoice"


@dataclass
class LineItem:
    """A line item on a PO, receipt, or invoice."""
    
    id: str
    item_id: str
    item_name: str
    quantity: Decimal
    unit_price: Decimal
    unit: str = "each"
    description: str | None = None
    
    @property
    def total(self) -> Decimal:
        """Line total."""
        return self.quantity * self.unit_price


@dataclass
class PurchaseOrder:
    """A purchase order document."""
    
    id: str
    po_number: str
    vendor_id: str
    vendor_name: str
    order_date: date
    expected_date: date | None = None
    items: list[LineItem] = field(default_factory=list)
    ship_to: str | None = None
    status: str = "open"  # open, partial, received, closed, cancelled
    notes: str | None = None
    created_by: str | None = None
    approved_by: str | None = None
    
    @property
    def subtotal(self) -> Decimal:
        """Subtotal before tax."""
        return sum(item.total for item in self.items)
    
    @property
    def item_count(self) -> int:
        """Number of line items."""
        return len(self.items)


@dataclass
class Receipt:
    """A receiving document."""
    
    id: str
    receipt_number: str
    vendor_id: str
    vendor_name: str
    received_date: date
    po_id: str | None = None
    items: list[LineItem] = field(default_factory=list)
    received_by: str | None = None
    location: str | None = None
    notes: str | None = None
    
    @property
    def total_received(self) -> Decimal:
        """Total value received."""
        return sum(item.total for item in self.items)


@dataclass
class Invoice:
    """A vendor invoice document."""
    
    id: str
    invoice_number: str
    vendor_id: str
    vendor_name: str
    invoice_date: date
    due_date: date | None = None
    po_number: str | None = None
    items: list[LineItem] = field(default_factory=list)
    subtotal: Decimal = Decimal("0")
    tax: Decimal = Decimal("0")
    shipping: Decimal = Decimal("0")
    total: Decimal = Decimal("0")
    payment_terms: str | None = None
    status: str = "pending"  # pending, matched, approved, paid, disputed
    
    def calculate_totals(self) -> None:
        """Calculate invoice totals from line items."""
        self.subtotal = sum(item.total for item in self.items)
        self.total = self.subtotal + self.tax + self.shipping


@dataclass
class MatchResult:
    """Result of matching documents."""
    
    match_id: str
    status: MatchStatus
    po: PurchaseOrder | None
    receipt: Receipt | None
    invoice: Invoice | None
    
    # Variance details
    quantity_variance: Decimal = Decimal("0")
    price_variance: Decimal = Decimal("0")
    total_variance: Decimal = Decimal("0")
    
    # Line-level results
    line_results: list[dict[str, Any]] = field(default_factory=list)
    
    # Actions
    auto_approved: bool = False
    requires_review: bool = False
    exception_reason: str | None = None
    
    matched_at: datetime = field(default_factory=datetime.now)
    
    @property
    def variance_percentage(self) -> float:
        """Total variance as percentage of invoice."""
        if self.invoice and self.invoice.total > 0:
            return float(abs(self.total_variance) / self.invoice.total * 100)
        return 0.0
    
    @property
    def is_exact_match(self) -> bool:
        """Whether this is an exact match (no variances)."""
        return (
            self.status == MatchStatus.MATCHED and
            self.quantity_variance == 0 and
            self.price_variance == 0
        )


@dataclass
class MatchingTolerance:
    """Tolerance settings for matching."""
    
    quantity_variance_pct: float = 0.0  # % variance allowed
    quantity_variance_abs: Decimal = Decimal("0")  # Absolute variance allowed
    price_variance_pct: float = 0.0
    price_variance_abs: Decimal = Decimal("0")
    total_variance_pct: float = 0.0
    total_variance_abs: Decimal = Decimal("0")
    
    # Auto-approval thresholds
    auto_approve_below: Decimal = Decimal("0")  # Invoice total threshold
    auto_approve_exact_only: bool = True


class ThreeWayMatcher:
    """Three-way matching engine for AP automation.

    Usage::

        matcher = ThreeWayMatcher(
            tolerance=MatchingTolerance(
                price_variance_pct=2.0,
                total_variance_abs=Decimal("10"),
            )
        )
        
        # Add documents
        matcher.add_purchase_order(po)
        matcher.add_receipt(receipt)
        matcher.add_invoice(invoice)
        
        # Perform match
        result = matcher.match_invoice(invoice.id)
    """

    def __init__(
        self,
        tolerance: MatchingTolerance | None = None,
    ) -> None:
        self.tolerance = tolerance or MatchingTolerance()
        
        self.purchase_orders: dict[str, PurchaseOrder] = {}
        self.receipts: dict[str, Receipt] = {}
        self.invoices: dict[str, Invoice] = {}
        self.match_results: list[MatchResult] = []
        
        # Index for faster lookups
        self._po_by_number: dict[str, str] = {}  # PO number -> PO ID
        self._po_by_vendor: dict[str, list[str]] = {}  # Vendor ID -> PO IDs
        self._receipts_by_po: dict[str, list[str]] = {}  # PO ID -> Receipt IDs

    def add_purchase_order(self, po: PurchaseOrder) -> None:
        """Add a purchase order."""
        self.purchase_orders[po.id] = po
        self._po_by_number[po.po_number] = po.id
        
        if po.vendor_id not in self._po_by_vendor:
            self._po_by_vendor[po.vendor_id] = []
        self._po_by_vendor[po.vendor_id].append(po.id)

    def add_receipt(self, receipt: Receipt) -> None:
        """Add a receiving document."""
        self.receipts[receipt.id] = receipt
        
        if receipt.po_id:
            if receipt.po_id not in self._receipts_by_po:
                self._receipts_by_po[receipt.po_id] = []
            self._receipts_by_po[receipt.po_id].append(receipt.id)

    def add_invoice(self, invoice: Invoice) -> None:
        """Add a vendor invoice."""
        invoice.calculate_totals()
        self.invoices[invoice.id] = invoice

    def get_purchase_order(self, po_id: str) -> PurchaseOrder | None:
        """Get PO by ID."""
        return self.purchase_orders.get(po_id)

    def find_po_by_number(self, po_number: str) -> PurchaseOrder | None:
        """Find PO by PO number."""
        po_id = self._po_by_number.get(po_number)
        return self.purchase_orders.get(po_id) if po_id else None

    def find_matching_po(self, invoice: Invoice) -> PurchaseOrder | None:
        """Find the best matching PO for an invoice."""
        # Try by PO number first
        if invoice.po_number:
            po = self.find_po_by_number(invoice.po_number)
            if po:
                return po
        
        # Try by vendor and amount
        vendor_pos = self._po_by_vendor.get(invoice.vendor_id, [])
        for po_id in vendor_pos:
            po = self.purchase_orders[po_id]
            if po.status not in ("closed", "cancelled"):
                # Check if amounts are close
                if abs(po.subtotal - invoice.subtotal) <= self.tolerance.total_variance_abs:
                    return po
        
        return None

    def find_matching_receipts(self, po: PurchaseOrder) -> list[Receipt]:
        """Find receipts for a PO."""
        receipt_ids = self._receipts_by_po.get(po.id, [])
        return [self.receipts[rid] for rid in receipt_ids]

    def _match_line_items(
        self,
        po_items: list[LineItem],
        receipt_items: list[LineItem],
        invoice_items: list[LineItem],
    ) -> list[dict[str, Any]]:
        """Match line items across all three documents."""
        results = []
        
        # Build item lookups
        po_by_item = {item.item_id: item for item in po_items}
        receipt_by_item = {item.item_id: item for item in receipt_items}
        invoice_by_item = {item.item_id: item for item in invoice_items}
        
        # Get all unique item IDs
        all_items = set(po_by_item.keys()) | set(receipt_by_item.keys()) | set(invoice_by_item.keys())
        
        for item_id in all_items:
            po_item = po_by_item.get(item_id)
            receipt_item = receipt_by_item.get(item_id)
            invoice_item = invoice_by_item.get(item_id)
            
            result = {
                "item_id": item_id,
                "item_name": (
                    po_item.item_name if po_item else
                    receipt_item.item_name if receipt_item else
                    invoice_item.item_name if invoice_item else "Unknown"
                ),
                "po_quantity": float(po_item.quantity) if po_item else None,
                "receipt_quantity": float(receipt_item.quantity) if receipt_item else None,
                "invoice_quantity": float(invoice_item.quantity) if invoice_item else None,
                "po_price": float(po_item.unit_price) if po_item else None,
                "invoice_price": float(invoice_item.unit_price) if invoice_item else None,
                "quantity_variance": Decimal("0"),
                "price_variance": Decimal("0"),
                "status": "matched",
            }
            
            # Check quantity variance (receipt vs invoice)
            if receipt_item and invoice_item:
                qty_var = invoice_item.quantity - receipt_item.quantity
                result["quantity_variance"] = float(qty_var)
                if qty_var != 0:
                    result["status"] = "quantity_variance"
            elif invoice_item and not receipt_item:
                result["status"] = "missing_receipt"
            
            # Check price variance (PO vs invoice)
            if po_item and invoice_item:
                price_var = invoice_item.unit_price - po_item.unit_price
                result["price_variance"] = float(price_var)
                if price_var != 0 and result["status"] == "matched":
                    result["status"] = "price_variance"
            elif invoice_item and not po_item:
                result["status"] = "missing_po"
            
            results.append(result)
        
        return results

    def _is_within_tolerance(
        self,
        quantity_var: Decimal,
        price_var: Decimal,
        total_var: Decimal,
        invoice_total: Decimal,
    ) -> bool:
        """Check if variances are within tolerance."""
        tol = self.tolerance
        
        # Check quantity
        if quantity_var != 0:
            if tol.quantity_variance_abs > 0:
                if abs(quantity_var) > tol.quantity_variance_abs:
                    return False
        
        # Check price
        if price_var != 0:
            if tol.price_variance_abs > 0:
                if abs(price_var) > tol.price_variance_abs:
                    return False
            if tol.price_variance_pct > 0:
                # Would need original price for percentage check
                pass
        
        # Check total
        if total_var != 0:
            if tol.total_variance_abs > 0:
                if abs(total_var) > tol.total_variance_abs:
                    return False
            if tol.total_variance_pct > 0 and invoice_total > 0:
                if float(abs(total_var) / invoice_total * 100) > tol.total_variance_pct:
                    return False
        
        return True

    def match_invoice(self, invoice_id: str) -> MatchResult:
        """Perform three-way match for an invoice.
        
        Returns:
            MatchResult with match status and details.
        """
        invoice = self.invoices.get(invoice_id)
        if not invoice:
            return MatchResult(
                match_id=f"match_{datetime.now().timestamp()}",
                status=MatchStatus.MISSING_INVOICE,
                po=None,
                receipt=None,
                invoice=None,
                exception_reason="Invoice not found",
                requires_review=True,
            )
        
        # Find matching PO
        po = self.find_matching_po(invoice)
        if not po:
            return MatchResult(
                match_id=f"match_{datetime.now().timestamp()}",
                status=MatchStatus.MISSING_PO,
                po=None,
                receipt=None,
                invoice=invoice,
                exception_reason="No matching purchase order found",
                requires_review=True,
            )
        
        # Find receipts
        receipts = self.find_matching_receipts(po)
        
        # Combine receipt items
        all_receipt_items = []
        for receipt in receipts:
            all_receipt_items.extend(receipt.items)
        
        if not receipts:
            return MatchResult(
                match_id=f"match_{datetime.now().timestamp()}",
                status=MatchStatus.MISSING_RECEIPT,
                po=po,
                receipt=None,
                invoice=invoice,
                exception_reason="No receiving documents found for PO",
                requires_review=True,
            )
        
        # Use first receipt for the result (simplified)
        primary_receipt = receipts[0]
        
        # Match line items
        line_results = self._match_line_items(
            po.items, all_receipt_items, invoice.items
        )
        
        # Calculate total variances
        quantity_var = sum(
            Decimal(str(lr.get("quantity_variance", 0)))
            for lr in line_results
        )
        price_var = sum(
            Decimal(str(lr.get("price_variance", 0)))
            for lr in line_results
        )
        
        # Total variance between PO and invoice
        total_var = invoice.subtotal - po.subtotal
        
        # Determine status
        has_qty_var = any(lr["status"] == "quantity_variance" for lr in line_results)
        has_price_var = any(lr["status"] == "price_variance" for lr in line_results)
        has_missing = any(lr["status"] in ("missing_po", "missing_receipt") for lr in line_results)
        
        if not has_qty_var and not has_price_var and not has_missing:
            status = MatchStatus.MATCHED
        elif has_qty_var and not has_price_var:
            status = MatchStatus.QUANTITY_VARIANCE
        elif has_price_var and not has_qty_var:
            status = MatchStatus.PRICE_VARIANCE
        elif has_missing:
            status = MatchStatus.PARTIAL
        else:
            status = MatchStatus.UNMATCHED
        
        # Check tolerance
        within_tolerance = self._is_within_tolerance(
            quantity_var, price_var, total_var, invoice.total
        )
        
        # Determine if auto-approve
        auto_approved = False
        requires_review = True
        
        if status == MatchStatus.MATCHED and total_var == 0:
            if self.tolerance.auto_approve_exact_only:
                auto_approved = True
                requires_review = False
        elif within_tolerance:
            if not self.tolerance.auto_approve_exact_only:
                if invoice.total <= self.tolerance.auto_approve_below or self.tolerance.auto_approve_below == 0:
                    auto_approved = True
                    requires_review = False
        
        result = MatchResult(
            match_id=f"match_{datetime.now().timestamp()}",
            status=status,
            po=po,
            receipt=primary_receipt,
            invoice=invoice,
            quantity_variance=quantity_var,
            price_variance=price_var,
            total_variance=total_var,
            line_results=line_results,
            auto_approved=auto_approved,
            requires_review=requires_review,
            exception_reason=None if status == MatchStatus.MATCHED else f"Variance detected: {status.value}",
        )
        
        self.match_results.append(result)
        
        # Update invoice status
        if auto_approved:
            invoice.status = "approved"
        elif status == MatchStatus.MATCHED:
            invoice.status = "matched"
        
        return result

    def match_all_pending(self) -> list[MatchResult]:
        """Match all pending invoices."""
        results = []
        for invoice_id, invoice in self.invoices.items():
            if invoice.status == "pending":
                result = self.match_invoice(invoice_id)
                results.append(result)
        return results

    def get_exceptions(self) -> list[MatchResult]:
        """Get all match results that require review."""
        return [r for r in self.match_results if r.requires_review]

    def get_auto_approved(self) -> list[MatchResult]:
        """Get all auto-approved matches."""
        return [r for r in self.match_results if r.auto_approved]

    def get_matching_summary(self) -> dict[str, Any]:
        """Get summary of matching activity."""
        total = len(self.match_results)
        if total == 0:
            return {
                "total_matches": 0,
                "matched": 0,
                "exceptions": 0,
                "auto_approved": 0,
            }
        
        statuses = {}
        for result in self.match_results:
            status = result.status.value
            statuses[status] = statuses.get(status, 0) + 1
        
        total_variance = sum(
            result.total_variance for result in self.match_results
        )
        
        return {
            "total_matches": total,
            "by_status": statuses,
            "auto_approved": len([r for r in self.match_results if r.auto_approved]),
            "requiring_review": len([r for r in self.match_results if r.requires_review]),
            "total_variance": float(total_variance),
            "avg_variance": float(total_variance / total),
            "match_rate": len([r for r in self.match_results if r.status == MatchStatus.MATCHED]) / total * 100,
        }
