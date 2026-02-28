"""
Vendor Management Module — supplier tracking and scoring.

Provides:
- Vendor database and profiles
- Performance scoring
- Payment term tracking
- Contract management
- Spend analysis by vendor
- Risk assessment
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum


class VendorStatus(str, Enum):
    """Vendor status."""
    
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    BLOCKED = "blocked"
    PREFERRED = "preferred"


class PaymentTerms(str, Enum):
    """Standard payment terms."""
    
    NET_15 = "net_15"
    NET_30 = "net_30"
    NET_45 = "net_45"
    NET_60 = "net_60"
    NET_90 = "net_90"
    DUE_ON_RECEIPT = "due_on_receipt"
    PREPAID = "prepaid"


class RiskLevel(str, Enum):
    """Vendor risk level."""
    
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class VendorContact:
    """A vendor contact person."""
    
    name: str
    email: str | None = None
    phone: str | None = None
    title: str | None = None
    is_primary: bool = False


@dataclass
class VendorContract:
    """A vendor contract."""
    
    id: str
    vendor_id: str
    
    title: str
    start_date: datetime
    end_date: datetime | None = None
    
    # Terms
    value: Decimal | None = None
    payment_terms: PaymentTerms = PaymentTerms.NET_30
    auto_renew: bool = False
    
    # Documents
    document_url: str | None = None
    
    # Status
    is_active: bool = True
    
    @property
    def days_until_expiry(self) -> int | None:
        """Days until contract expires."""
        if not self.end_date:
            return None
        return (self.end_date - datetime.now()).days

    @property
    def is_expiring_soon(self) -> bool:
        """Whether contract expires within 60 days."""
        days = self.days_until_expiry
        return days is not None and 0 < days <= 60


@dataclass
class VendorPaymentHistory:
    """Payment history for a vendor."""
    
    total_paid: Decimal = Decimal("0")
    total_invoices: int = 0
    
    avg_days_to_pay: float = 0.0
    on_time_pct: float = 100.0
    early_payment_pct: float = 0.0
    
    last_payment_date: datetime | None = None
    last_payment_amount: Decimal | None = None


@dataclass
class VendorPerformance:
    """Vendor performance metrics."""
    
    overall_score: float = 0.0  # 0-100
    
    # Component scores (0-100)
    quality_score: float = 0.0
    delivery_score: float = 0.0
    pricing_score: float = 0.0
    responsiveness_score: float = 0.0
    
    # Issues
    total_issues: int = 0
    resolved_issues: int = 0
    open_issues: int = 0
    
    # Returns
    return_rate: float = 0.0
    
    # Calculations
    last_evaluated: datetime | None = None


@dataclass
class Vendor:
    """A vendor profile."""
    
    id: str
    name: str
    status: VendorStatus = VendorStatus.ACTIVE
    
    # Basic info
    legal_name: str | None = None
    tax_id: str | None = None
    duns_number: str | None = None
    
    # Categories
    category: str | None = None
    tags: list[str] = field(default_factory=list)
    
    # Contact
    contacts: list[VendorContact] = field(default_factory=list)
    website: str | None = None
    address: str | None = None
    
    # Payment
    payment_terms: PaymentTerms = PaymentTerms.NET_30
    bank_account: str | None = None  # Last 4 digits only
    payment_method: str = "ach"  # ach, check, wire, card
    
    # Performance
    performance: VendorPerformance | None = None
    payment_history: VendorPaymentHistory | None = None
    risk_level: RiskLevel = RiskLevel.LOW
    
    # Contracts
    contracts: list[VendorContract] = field(default_factory=list)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime | None = None
    notes: str | None = None

    @property
    def primary_contact(self) -> VendorContact | None:
        """Get primary contact."""
        for contact in self.contacts:
            if contact.is_primary:
                return contact
        return self.contacts[0] if self.contacts else None

    @property
    def active_contracts(self) -> list[VendorContract]:
        """Get active contracts."""
        return [c for c in self.contracts if c.is_active]


@dataclass
class VendorSpendSummary:
    """Spend summary for a vendor."""
    
    vendor_id: str
    vendor_name: str
    
    # Totals
    total_spend: Decimal = Decimal("0")
    ytd_spend: Decimal = Decimal("0")
    prior_year_spend: Decimal = Decimal("0")
    
    # Breakdown
    spend_by_category: dict[str, Decimal] = field(default_factory=dict)
    spend_by_month: dict[str, Decimal] = field(default_factory=dict)
    
    # Trend
    yoy_change: float = 0.0  # Year over year change %
    mom_change: float = 0.0  # Month over month change %
    
    # Share
    pct_of_total_spend: float = 0.0


@dataclass
class VendorAnalysisSummary:
    """Summary of vendor analysis."""
    
    total_vendors: int = 0
    active_vendors: int = 0
    preferred_vendors: int = 0
    blocked_vendors: int = 0
    
    total_spend: Decimal = Decimal("0")
    top_vendors_by_spend: list[tuple[str, Decimal]] = field(default_factory=list)
    
    avg_performance_score: float = 0.0
    
    expiring_contracts: list[VendorContract] = field(default_factory=list)
    high_risk_vendors: list[str] = field(default_factory=list)
    
    concentration_warning: str | None = None


class VendorManager:
    """Manage vendors and supplier relationships.

    Usage::

        manager = VendorManager()
        
        # Add vendor
        vendor = Vendor(
            id="v001",
            name="ACME Supplies",
            category="Office Supplies",
            payment_terms=PaymentTerms.NET_30,
        )
        manager.add_vendor(vendor)
        
        # Record spend
        manager.record_spend("v001", Decimal("1500"), "Office Supplies", datetime.now())
        
        # Score vendor
        manager.score_vendor("v001", quality=85, delivery=90, pricing=75)
        
        # Analyze vendors
        summary = manager.get_analysis_summary()
    """

    def __init__(self) -> None:
        self.vendors: dict[str, Vendor] = {}
        
        # Spend records: vendor_id -> list of (amount, category, date)
        self._spend_records: dict[str, list[tuple[Decimal, str, datetime]]] = {}

    def add_vendor(self, vendor: Vendor) -> None:
        """Add a vendor."""
        self.vendors[vendor.id] = vendor
        self._spend_records[vendor.id] = []

    def update_vendor(self, vendor: Vendor) -> None:
        """Update a vendor."""
        vendor.updated_at = datetime.now()
        self.vendors[vendor.id] = vendor

    def get_vendor(self, vendor_id: str) -> Vendor | None:
        """Get a vendor by ID."""
        return self.vendors.get(vendor_id)

    def search_vendors(
        self,
        query: str | None = None,
        status: VendorStatus | None = None,
        category: str | None = None,
        risk_level: RiskLevel | None = None,
    ) -> list[Vendor]:
        """Search vendors with filters.
        
        Args:
            query: Text search in name/legal_name.
            status: Filter by status.
            category: Filter by category.
            risk_level: Filter by risk level.
        
        Returns:
            Matching vendors.
        """
        results = list(self.vendors.values())
        
        if status:
            results = [v for v in results if v.status == status]
        if category:
            results = [v for v in results if v.category == category]
        if risk_level:
            results = [v for v in results if v.risk_level == risk_level]
        
        if query:
            query_lower = query.lower()
            results = [
                v for v in results
                if query_lower in v.name.lower() or
                (v.legal_name and query_lower in v.legal_name.lower())
            ]
        
        return results

    def block_vendor(self, vendor_id: str, reason: str | None = None) -> None:
        """Block a vendor."""
        vendor = self.vendors.get(vendor_id)
        if vendor:
            vendor.status = VendorStatus.BLOCKED
            vendor.updated_at = datetime.now()
            if reason:
                vendor.notes = f"Blocked: {reason}"

    def set_preferred(self, vendor_id: str) -> None:
        """Set vendor as preferred."""
        vendor = self.vendors.get(vendor_id)
        if vendor:
            vendor.status = VendorStatus.PREFERRED
            vendor.updated_at = datetime.now()

    def add_contract(self, vendor_id: str, contract: VendorContract) -> None:
        """Add a contract to a vendor."""
        vendor = self.vendors.get(vendor_id)
        if vendor:
            contract.vendor_id = vendor_id
            vendor.contracts.append(contract)
            vendor.updated_at = datetime.now()

    def record_spend(
        self,
        vendor_id: str,
        amount: Decimal,
        category: str,
        date: datetime,
    ) -> None:
        """Record a spend transaction."""
        if vendor_id not in self._spend_records:
            self._spend_records[vendor_id] = []
        
        self._spend_records[vendor_id].append((amount, category, date))

    def get_vendor_spend(
        self,
        vendor_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> VendorSpendSummary:
        """Get spend summary for a vendor.
        
        Args:
            vendor_id: The vendor.
            start_date: Start of period.
            end_date: End of period.
        
        Returns:
            Spend summary.
        """
        vendor = self.vendors.get(vendor_id)
        if not vendor:
            raise ValueError(f"Vendor not found: {vendor_id}")
        
        records = self._spend_records.get(vendor_id, [])
        
        now = datetime.now()
        ytd_start = datetime(now.year, 1, 1)
        prior_year_start = datetime(now.year - 1, 1, 1)
        prior_year_end = datetime(now.year - 1, 12, 31)
        
        total_spend = Decimal("0")
        ytd_spend = Decimal("0")
        prior_year_spend = Decimal("0")
        spend_by_category: dict[str, Decimal] = {}
        spend_by_month: dict[str, Decimal] = {}
        
        for amount, category, date in records:
            # Filter by date range if provided
            if start_date and date < start_date:
                continue
            if end_date and date > end_date:
                continue
            
            total_spend += amount
            
            # YTD
            if date >= ytd_start:
                ytd_spend += amount
            
            # Prior year
            if prior_year_start <= date <= prior_year_end:
                prior_year_spend += amount
            
            # By category
            spend_by_category[category] = spend_by_category.get(category, Decimal("0")) + amount
            
            # By month
            month_key = date.strftime("%Y-%m")
            spend_by_month[month_key] = spend_by_month.get(month_key, Decimal("0")) + amount
        
        # Calculate YoY change
        yoy_change = 0.0
        if prior_year_spend > 0:
            yoy_change = float((ytd_spend - prior_year_spend) / prior_year_spend * 100)
        
        # Calculate percent of total spend
        all_spend = sum(
            sum(amt for amt, _, _ in recs)
            for recs in self._spend_records.values()
        )
        pct_of_total = float(total_spend / all_spend * 100) if all_spend > 0 else 0
        
        return VendorSpendSummary(
            vendor_id=vendor_id,
            vendor_name=vendor.name,
            total_spend=total_spend,
            ytd_spend=ytd_spend,
            prior_year_spend=prior_year_spend,
            spend_by_category=spend_by_category,
            spend_by_month=spend_by_month,
            yoy_change=yoy_change,
            pct_of_total_spend=pct_of_total,
        )

    def score_vendor(
        self,
        vendor_id: str,
        quality: float = 0.0,
        delivery: float = 0.0,
        pricing: float = 0.0,
        responsiveness: float = 0.0,
    ) -> VendorPerformance:
        """Score a vendor's performance.
        
        Args:
            vendor_id: The vendor.
            quality: Quality score (0-100).
            delivery: Delivery score (0-100).
            pricing: Pricing score (0-100).
            responsiveness: Responsiveness score (0-100).
        
        Returns:
            Updated performance.
        """
        vendor = self.vendors.get(vendor_id)
        if not vendor:
            raise ValueError(f"Vendor not found: {vendor_id}")
        
        # Weighted average
        weights = {
            "quality": 0.30,
            "delivery": 0.30,
            "pricing": 0.25,
            "responsiveness": 0.15,
        }
        
        overall = (
            quality * weights["quality"] +
            delivery * weights["delivery"] +
            pricing * weights["pricing"] +
            responsiveness * weights["responsiveness"]
        )
        
        performance = VendorPerformance(
            overall_score=overall,
            quality_score=quality,
            delivery_score=delivery,
            pricing_score=pricing,
            responsiveness_score=responsiveness,
            last_evaluated=datetime.now(),
        )
        
        vendor.performance = performance
        
        # Update risk level based on score
        if overall >= 80:
            vendor.risk_level = RiskLevel.LOW
        elif overall >= 60:
            vendor.risk_level = RiskLevel.MEDIUM
        elif overall >= 40:
            vendor.risk_level = RiskLevel.HIGH
        else:
            vendor.risk_level = RiskLevel.CRITICAL
        
        vendor.updated_at = datetime.now()
        return performance

    def record_payment(
        self,
        vendor_id: str,
        amount: Decimal,
        invoice_date: datetime,
        payment_date: datetime,
    ) -> None:
        """Record a payment to update payment history.
        
        Args:
            vendor_id: The vendor.
            amount: Payment amount.
            invoice_date: Date of invoice.
            payment_date: Date payment was made.
        """
        vendor = self.vendors.get(vendor_id)
        if not vendor:
            return
        
        if not vendor.payment_history:
            vendor.payment_history = VendorPaymentHistory()
        
        history = vendor.payment_history
        
        # Calculate days to pay
        days_to_pay = (payment_date - invoice_date).days
        
        # Get expected days from payment terms
        terms_days = {
            PaymentTerms.DUE_ON_RECEIPT: 0,
            PaymentTerms.PREPAID: 0,
            PaymentTerms.NET_15: 15,
            PaymentTerms.NET_30: 30,
            PaymentTerms.NET_45: 45,
            PaymentTerms.NET_60: 60,
            PaymentTerms.NET_90: 90,
        }
        expected_days = terms_days.get(vendor.payment_terms, 30)
        
        # Update running average
        if history.total_invoices == 0:
            history.avg_days_to_pay = float(days_to_pay)
        else:
            history.avg_days_to_pay = (
                (history.avg_days_to_pay * history.total_invoices + days_to_pay) /
                (history.total_invoices + 1)
            )
        
        # Update on-time percentage
        on_time = days_to_pay <= expected_days
        early = days_to_pay < expected_days
        
        old_on_time_count = int(history.on_time_pct / 100 * history.total_invoices)
        new_on_time_count = old_on_time_count + (1 if on_time else 0)
        history.on_time_pct = new_on_time_count / (history.total_invoices + 1) * 100
        
        old_early_count = int(history.early_payment_pct / 100 * history.total_invoices)
        new_early_count = old_early_count + (1 if early else 0)
        history.early_payment_pct = new_early_count / (history.total_invoices + 1) * 100
        
        # Update totals
        history.total_paid += amount
        history.total_invoices += 1
        history.last_payment_date = payment_date
        history.last_payment_amount = amount
        
        vendor.updated_at = datetime.now()

    def get_expiring_contracts(
        self,
        days_ahead: int = 60,
    ) -> list[VendorContract]:
        """Get contracts expiring soon.
        
        Args:
            days_ahead: Look-ahead period in days.
        
        Returns:
            List of expiring contracts.
        """
        expiring = []
        cutoff = datetime.now() + timedelta(days=days_ahead)
        
        for vendor in self.vendors.values():
            for contract in vendor.active_contracts:
                if contract.end_date and contract.end_date <= cutoff:
                    expiring.append(contract)
        
        return sorted(expiring, key=lambda c: c.end_date or datetime.max)

    def check_concentration_risk(
        self,
        threshold_pct: float = 25.0,
    ) -> list[tuple[str, float]]:
        """Check for vendor concentration risk.
        
        Args:
            threshold_pct: Threshold for concentration warning.
        
        Returns:
            List of (vendor_name, pct_of_spend) for concentrated vendors.
        """
        # Calculate total spend per vendor
        vendor_totals: dict[str, Decimal] = {}
        
        for vendor_id, records in self._spend_records.items():
            total = sum(amt for amt, _, _ in records)
            if total > 0:
                vendor_totals[vendor_id] = total
        
        if not vendor_totals:
            return []
        
        total_spend = sum(vendor_totals.values())
        if total_spend == 0:
            return []
        
        concentrated = []
        for vendor_id, vendor_spend in vendor_totals.items():
            pct = float(vendor_spend / total_spend * 100)
            if pct >= threshold_pct:
                vendor = self.vendors.get(vendor_id)
                name = vendor.name if vendor else vendor_id
                concentrated.append((name, pct))
        
        return sorted(concentrated, key=lambda x: -x[1])

    def get_analysis_summary(self) -> VendorAnalysisSummary:
        """Get overall vendor analysis summary.
        
        Returns:
            Analysis summary.
        """
        vendors = list(self.vendors.values())
        
        # Status counts
        active = len([v for v in vendors if v.status == VendorStatus.ACTIVE])
        preferred = len([v for v in vendors if v.status == VendorStatus.PREFERRED])
        blocked = len([v for v in vendors if v.status == VendorStatus.BLOCKED])
        
        # Total spend
        total_spend = sum(
            sum(amt for amt, _, _ in records)
            for records in self._spend_records.values()
        )
        
        # Top vendors by spend
        vendor_spends = []
        for vendor_id, records in self._spend_records.items():
            vendor = self.vendors.get(vendor_id)
            if vendor:
                spend = sum(amt for amt, _, _ in records)
                vendor_spends.append((vendor.name, spend))
        
        top_vendors = sorted(vendor_spends, key=lambda x: -x[1])[:10]
        
        # Average performance
        scores = [v.performance.overall_score for v in vendors if v.performance]
        avg_score = sum(scores) / len(scores) if scores else 0
        
        # Expiring contracts
        expiring = self.get_expiring_contracts(60)
        
        # High risk vendors
        high_risk = [
            v.name for v in vendors
            if v.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        ]
        
        # Concentration warning
        concentrated = self.check_concentration_risk(25)
        concentration_warning = None
        if concentrated:
            names = ", ".join(f"{name} ({pct:.1f}%)" for name, pct in concentrated[:3])
            concentration_warning = f"High spend concentration: {names}"
        
        return VendorAnalysisSummary(
            total_vendors=len(vendors),
            active_vendors=active,
            preferred_vendors=preferred,
            blocked_vendors=blocked,
            total_spend=total_spend,
            top_vendors_by_spend=top_vendors,
            avg_performance_score=avg_score,
            expiring_contracts=expiring,
            high_risk_vendors=high_risk,
            concentration_warning=concentration_warning,
        )
