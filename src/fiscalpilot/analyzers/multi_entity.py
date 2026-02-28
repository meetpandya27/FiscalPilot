"""
Multi-Entity Consolidation — consolidate financials across multiple entities.

Provides:
- Multi-location consolidation
- Intercompany elimination
- Currency conversion
- Segment reporting
- Minority interest handling
- Consolidation adjustments
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any


class ConsolidationType(str, Enum):
    """Types of consolidation."""
    
    FULL = "full"  # 100% consolidation
    PROPORTIONAL = "proportional"  # Ownership % consolidation
    EQUITY_METHOD = "equity"  # Just record share of earnings
    COST_METHOD = "cost"  # Just record at cost


class EntityType(str, Enum):
    """Types of entities."""
    
    PARENT = "parent"
    SUBSIDIARY = "subsidiary"
    BRANCH = "branch"
    DIVISION = "division"
    JOINT_VENTURE = "joint_venture"


@dataclass
class Entity:
    """A legal entity or operating unit."""
    
    id: str
    name: str
    entity_type: EntityType
    parent_id: str | None = None  # Parent entity ID
    ownership_pct: float = 100.0  # Ownership percentage
    functional_currency: str = "USD"
    consolidation_type: ConsolidationType = ConsolidationType.FULL
    
    # Location info
    country: str = "US"
    region: str | None = None
    
    # Settings
    is_active: bool = True
    use_different_fiscal_year: bool = False
    fiscal_year_end_month: int = 12


@dataclass
class EntityFinancials:
    """Financial data for an entity."""
    
    entity_id: str
    period_start: date
    period_end: date
    currency: str = "USD"
    
    # Income statement
    revenue: Decimal = Decimal("0")
    cost_of_goods_sold: Decimal = Decimal("0")
    gross_profit: Decimal = Decimal("0")
    operating_expenses: Decimal = Decimal("0")
    operating_income: Decimal = Decimal("0")
    other_income: Decimal = Decimal("0")
    other_expense: Decimal = Decimal("0")
    interest_expense: Decimal = Decimal("0")
    income_before_tax: Decimal = Decimal("0")
    income_tax: Decimal = Decimal("0")
    net_income: Decimal = Decimal("0")
    
    # Balance sheet
    cash: Decimal = Decimal("0")
    accounts_receivable: Decimal = Decimal("0")
    inventory: Decimal = Decimal("0")
    other_current_assets: Decimal = Decimal("0")
    fixed_assets: Decimal = Decimal("0")
    accumulated_depreciation: Decimal = Decimal("0")
    other_assets: Decimal = Decimal("0")
    total_assets: Decimal = Decimal("0")
    
    accounts_payable: Decimal = Decimal("0")
    accrued_liabilities: Decimal = Decimal("0")
    current_portion_debt: Decimal = Decimal("0")
    other_current_liabilities: Decimal = Decimal("0")
    long_term_debt: Decimal = Decimal("0")
    other_liabilities: Decimal = Decimal("0")
    total_liabilities: Decimal = Decimal("0")
    
    common_stock: Decimal = Decimal("0")
    retained_earnings: Decimal = Decimal("0")
    other_equity: Decimal = Decimal("0")
    total_equity: Decimal = Decimal("0")
    
    # Intercompany balances
    intercompany_receivables: dict[str, Decimal] = field(default_factory=dict)
    intercompany_payables: dict[str, Decimal] = field(default_factory=dict)
    intercompany_revenue: dict[str, Decimal] = field(default_factory=dict)
    intercompany_expense: dict[str, Decimal] = field(default_factory=dict)
    
    def calculate_totals(self) -> None:
        """Calculate derived totals."""
        self.gross_profit = self.revenue - self.cost_of_goods_sold
        self.operating_income = self.gross_profit - self.operating_expenses
        self.income_before_tax = (
            self.operating_income + self.other_income - 
            self.other_expense - self.interest_expense
        )
        self.net_income = self.income_before_tax - self.income_tax
        
        self.total_assets = (
            self.cash + self.accounts_receivable + self.inventory +
            self.other_current_assets + self.fixed_assets -
            self.accumulated_depreciation + self.other_assets
        )
        
        self.total_liabilities = (
            self.accounts_payable + self.accrued_liabilities +
            self.current_portion_debt + self.other_current_liabilities +
            self.long_term_debt + self.other_liabilities
        )
        
        self.total_equity = (
            self.common_stock + self.retained_earnings + self.other_equity
        )


@dataclass
class EliminationEntry:
    """An intercompany elimination entry."""
    
    description: str
    debit_account: str
    debit_amount: Decimal
    credit_account: str
    credit_amount: Decimal
    entity1_id: str
    entity2_id: str
    entry_type: str  # revenue, ar_ap, investment, etc.


@dataclass
class ConsolidationAdjustment:
    """A consolidation adjustment entry."""
    
    description: str
    adjustments: dict[str, Decimal] = field(default_factory=dict)  # account -> amount
    adjustment_type: str = "manual"  # manual, currency, minority, etc.


@dataclass
class ConsolidatedResult:
    """Result of consolidation."""
    
    period_start: date
    period_end: date
    reporting_currency: str
    
    # Consolidated financials
    financials: EntityFinancials
    
    # Components
    entity_contributions: dict[str, dict[str, Any]] = field(default_factory=dict)
    eliminations: list[EliminationEntry] = field(default_factory=list)
    adjustments: list[ConsolidationAdjustment] = field(default_factory=list)
    
    # Minority interest
    minority_interest_income: Decimal = Decimal("0")
    minority_interest_equity: Decimal = Decimal("0")
    
    # Currency translation
    translation_adjustments: Decimal = Decimal("0")
    
    @property
    def total_eliminations(self) -> Decimal:
        """Total amount of eliminations."""
        return sum(e.debit_amount for e in self.eliminations)


class MultiEntityConsolidator:
    """Multi-entity financial consolidation.

    Usage::

        consolidator = MultiEntityConsolidator(reporting_currency="USD")
        
        # Add entities
        consolidator.add_entity(Entity(
            id="parent",
            name="Parent Corp",
            entity_type=EntityType.PARENT,
        ))
        consolidator.add_entity(Entity(
            id="sub1",
            name="Subsidiary 1",
            entity_type=EntityType.SUBSIDIARY,
            parent_id="parent",
            ownership_pct=80.0,
        ))
        
        # Add financials
        consolidator.add_financials(parent_financials)
        consolidator.add_financials(sub1_financials)
        
        # Consolidate
        result = consolidator.consolidate(
            period_start=date(2024, 1, 1),
            period_end=date(2024, 12, 31),
        )
    """

    def __init__(
        self,
        reporting_currency: str = "USD",
    ) -> None:
        self.reporting_currency = reporting_currency
        
        self.entities: dict[str, Entity] = {}
        self.financials: dict[str, list[EntityFinancials]] = {}  # entity_id -> financials list
        
        # Currency exchange rates
        self.exchange_rates: dict[str, Decimal] = {}  # currency -> rate to reporting currency
        
        # Elimination rules
        self.auto_eliminate_intercompany = True

    def add_entity(self, entity: Entity) -> None:
        """Add an entity to the consolidation."""
        self.entities[entity.id] = entity
        if entity.id not in self.financials:
            self.financials[entity.id] = []

    def get_entity(self, entity_id: str) -> Entity | None:
        """Get an entity by ID."""
        return self.entities.get(entity_id)

    def add_financials(self, financials: EntityFinancials) -> None:
        """Add financial data for an entity."""
        if financials.entity_id not in self.financials:
            self.financials[financials.entity_id] = []
        self.financials[financials.entity_id].append(financials)

    def set_exchange_rate(self, currency: str, rate: Decimal) -> None:
        """Set exchange rate to reporting currency."""
        self.exchange_rates[currency] = rate

    def _get_financials_for_period(
        self,
        entity_id: str,
        period_start: date,
        period_end: date,
    ) -> EntityFinancials | None:
        """Get financials for an entity and period."""
        for fin in self.financials.get(entity_id, []):
            if fin.period_start == period_start and fin.period_end == period_end:
                return fin
        return None

    def _convert_currency(
        self,
        amount: Decimal,
        from_currency: str,
    ) -> Decimal:
        """Convert amount to reporting currency."""
        if from_currency == self.reporting_currency:
            return amount
        
        rate = self.exchange_rates.get(from_currency, Decimal("1"))
        return amount * rate

    def _apply_ownership(
        self,
        financials: EntityFinancials,
        ownership_pct: float,
        consolidation_type: ConsolidationType,
    ) -> EntityFinancials:
        """Apply ownership percentage to financials."""
        if consolidation_type == ConsolidationType.FULL:
            # Full consolidation - 100% of all amounts
            return financials
        
        if consolidation_type == ConsolidationType.PROPORTIONAL:
            # Proportional - ownership % of all amounts
            factor = Decimal(str(ownership_pct / 100))
            result = EntityFinancials(
                entity_id=financials.entity_id,
                period_start=financials.period_start,
                period_end=financials.period_end,
            )
            
            # Apply factor to all numeric fields
            for field_name in [
                "revenue", "cost_of_goods_sold", "gross_profit",
                "operating_expenses", "operating_income", "net_income",
                "cash", "accounts_receivable", "inventory",
                "fixed_assets", "total_assets", "accounts_payable",
                "total_liabilities", "total_equity",
            ]:
                original = getattr(financials, field_name, Decimal("0"))
                setattr(result, field_name, original * factor)
            
            return result
        
        # Cost/equity method - not consolidated, just tracked
        return EntityFinancials(
            entity_id=financials.entity_id,
            period_start=financials.period_start,
            period_end=financials.period_end,
        )

    def _generate_eliminations(
        self,
        financials_list: list[EntityFinancials],
    ) -> list[EliminationEntry]:
        """Generate intercompany elimination entries."""
        eliminations = []
        
        for fin in financials_list:
            # Eliminate intercompany receivables/payables
            for other_entity, amount in fin.intercompany_receivables.items():
                eliminations.append(EliminationEntry(
                    description=f"Eliminate IC receivable {fin.entity_id} from {other_entity}",
                    debit_account="intercompany_payable",
                    debit_amount=amount,
                    credit_account="intercompany_receivable",
                    credit_amount=amount,
                    entity1_id=fin.entity_id,
                    entity2_id=other_entity,
                    entry_type="ar_ap",
                ))
            
            # Eliminate intercompany revenue
            for other_entity, amount in fin.intercompany_revenue.items():
                eliminations.append(EliminationEntry(
                    description=f"Eliminate IC revenue {fin.entity_id} to {other_entity}",
                    debit_account="revenue",
                    debit_amount=amount,
                    credit_account="cost_of_goods_sold",
                    credit_amount=amount,
                    entity1_id=fin.entity_id,
                    entity2_id=other_entity,
                    entry_type="revenue",
                ))
        
        return eliminations

    def _calculate_minority_interest(
        self,
        entity: Entity,
        financials: EntityFinancials,
    ) -> tuple[Decimal, Decimal]:
        """Calculate minority interest for less than 100% owned subsidiary.
        
        Returns (minority_interest_income, minority_interest_equity).
        """
        if entity.ownership_pct >= 100:
            return Decimal("0"), Decimal("0")
        
        minority_pct = Decimal(str((100 - entity.ownership_pct) / 100))
        
        minority_income = financials.net_income * minority_pct
        minority_equity = financials.total_equity * minority_pct
        
        return minority_income, minority_equity

    def consolidate(
        self,
        period_start: date,
        period_end: date,
        include_inactive: bool = False,
    ) -> ConsolidatedResult:
        """Perform consolidation for a period.
        
        Args:
            period_start: Start of period.
            period_end: End of period.
            include_inactive: Include inactive entities.
        
        Returns:
            ConsolidatedResult with consolidated financials.
        """
        # Initialize consolidated financials
        consolidated = EntityFinancials(
            entity_id="consolidated",
            period_start=period_start,
            period_end=period_end,
            currency=self.reporting_currency,
        )
        
        entity_contributions = {}
        all_financials = []
        total_minority_income = Decimal("0")
        total_minority_equity = Decimal("0")
        
        # Process each entity
        for entity_id, entity in self.entities.items():
            if not entity.is_active and not include_inactive:
                continue
            
            # Get financials for period
            fin = self._get_financials_for_period(entity_id, period_start, period_end)
            if not fin:
                continue
            
            # Convert currency
            if fin.currency != self.reporting_currency:
                rate = self.exchange_rates.get(fin.currency, Decimal("1"))
                # Apply rate to all amounts (simplified)
                for field_name in [
                    "revenue", "cost_of_goods_sold", "operating_expenses",
                    "net_income", "cash", "accounts_receivable", "inventory",
                    "fixed_assets", "total_assets", "accounts_payable",
                    "total_liabilities", "total_equity",
                ]:
                    original = getattr(fin, field_name, Decimal("0"))
                    setattr(fin, field_name, original * rate)
                fin.currency = self.reporting_currency
            
            # Apply ownership/consolidation type
            adjusted_fin = self._apply_ownership(
                fin, entity.ownership_pct, entity.consolidation_type
            )
            
            # Calculate minority interest
            minority_income, minority_equity = self._calculate_minority_interest(
                entity, fin
            )
            total_minority_income += minority_income
            total_minority_equity += minority_equity
            
            # Add to consolidated
            consolidated.revenue += adjusted_fin.revenue
            consolidated.cost_of_goods_sold += adjusted_fin.cost_of_goods_sold
            consolidated.operating_expenses += adjusted_fin.operating_expenses
            consolidated.other_income += adjusted_fin.other_income
            consolidated.other_expense += adjusted_fin.other_expense
            consolidated.interest_expense += adjusted_fin.interest_expense
            consolidated.income_tax += adjusted_fin.income_tax
            
            consolidated.cash += adjusted_fin.cash
            consolidated.accounts_receivable += adjusted_fin.accounts_receivable
            consolidated.inventory += adjusted_fin.inventory
            consolidated.other_current_assets += adjusted_fin.other_current_assets
            consolidated.fixed_assets += adjusted_fin.fixed_assets
            consolidated.accumulated_depreciation += adjusted_fin.accumulated_depreciation
            consolidated.other_assets += adjusted_fin.other_assets
            
            consolidated.accounts_payable += adjusted_fin.accounts_payable
            consolidated.accrued_liabilities += adjusted_fin.accrued_liabilities
            consolidated.current_portion_debt += adjusted_fin.current_portion_debt
            consolidated.long_term_debt += adjusted_fin.long_term_debt
            consolidated.other_liabilities += adjusted_fin.other_liabilities
            
            consolidated.common_stock += adjusted_fin.common_stock
            consolidated.retained_earnings += adjusted_fin.retained_earnings
            
            # Track contributions
            entity_contributions[entity_id] = {
                "name": entity.name,
                "revenue": float(fin.revenue),
                "net_income": float(fin.net_income),
                "total_assets": float(fin.total_assets),
                "ownership_pct": entity.ownership_pct,
                "consolidation_type": entity.consolidation_type.value,
            }
            
            all_financials.append(fin)
        
        # Generate eliminations
        eliminations = []
        if self.auto_eliminate_intercompany:
            eliminations = self._generate_eliminations(all_financials)
            
            # Apply eliminations to consolidated
            for elim in eliminations:
                if elim.entry_type == "revenue":
                    consolidated.revenue -= elim.debit_amount
                    consolidated.cost_of_goods_sold -= elim.credit_amount
                elif elim.entry_type == "ar_ap":
                    consolidated.accounts_receivable -= elim.credit_amount
                    consolidated.accounts_payable -= elim.debit_amount
        
        # Calculate totals
        consolidated.calculate_totals()
        
        # Adjust for minority interest
        consolidated.net_income -= total_minority_income
        
        return ConsolidatedResult(
            period_start=period_start,
            period_end=period_end,
            reporting_currency=self.reporting_currency,
            financials=consolidated,
            entity_contributions=entity_contributions,
            eliminations=eliminations,
            minority_interest_income=total_minority_income,
            minority_interest_equity=total_minority_equity,
        )

    def get_segment_report(
        self,
        period_start: date,
        period_end: date,
        segment_by: str = "entity",  # entity, region, country
    ) -> dict[str, Any]:
        """Generate segment report.
        
        Args:
            period_start: Start of period.
            period_end: End of period.
            segment_by: Segmentation field.
        
        Returns:
            Dict with segment performance.
        """
        segments: dict[str, dict] = {}
        
        for entity_id, entity in self.entities.items():
            if not entity.is_active:
                continue
            
            fin = self._get_financials_for_period(entity_id, period_start, period_end)
            if not fin:
                continue
            
            # Determine segment key
            if segment_by == "entity":
                key = entity.name
            elif segment_by == "region":
                key = entity.region or "Unassigned"
            elif segment_by == "country":
                key = entity.country
            else:
                key = entity.name
            
            if key not in segments:
                segments[key] = {
                    "revenue": Decimal("0"),
                    "operating_income": Decimal("0"),
                    "net_income": Decimal("0"),
                    "total_assets": Decimal("0"),
                    "entity_count": 0,
                }
            
            segments[key]["revenue"] += fin.revenue
            segments[key]["operating_income"] += fin.operating_income
            segments[key]["net_income"] += fin.net_income
            segments[key]["total_assets"] += fin.total_assets
            segments[key]["entity_count"] += 1
        
        # Calculate totals and percentages
        total_revenue = sum(s["revenue"] for s in segments.values())
        
        return {
            "period": f"{period_start} to {period_end}",
            "segment_by": segment_by,
            "segments": {
                key: {
                    "revenue": float(data["revenue"]),
                    "revenue_pct": float(data["revenue"] / total_revenue * 100) if total_revenue > 0 else 0,
                    "operating_income": float(data["operating_income"]),
                    "margin_pct": float(data["operating_income"] / data["revenue"] * 100) if data["revenue"] > 0 else 0,
                    "net_income": float(data["net_income"]),
                    "total_assets": float(data["total_assets"]),
                    "entity_count": data["entity_count"],
                }
                for key, data in sorted(segments.items(), key=lambda x: x[1]["revenue"], reverse=True)
            },
            "total_revenue": float(total_revenue),
        }

    def get_entity_comparison(
        self,
        period_start: date,
        period_end: date,
    ) -> list[dict[str, Any]]:
        """Compare performance across entities."""
        comparisons = []
        
        for entity_id, entity in self.entities.items():
            fin = self._get_financials_for_period(entity_id, period_start, period_end)
            if not fin:
                continue
            
            comparisons.append({
                "entity_id": entity_id,
                "entity_name": entity.name,
                "entity_type": entity.entity_type.value,
                "revenue": float(fin.revenue),
                "gross_margin": float(fin.gross_profit / fin.revenue * 100) if fin.revenue > 0 else 0,
                "operating_margin": float(fin.operating_income / fin.revenue * 100) if fin.revenue > 0 else 0,
                "net_margin": float(fin.net_income / fin.revenue * 100) if fin.revenue > 0 else 0,
                "total_assets": float(fin.total_assets),
                "roa": float(fin.net_income / fin.total_assets * 100) if fin.total_assets > 0 else 0,
            })
        
        return sorted(comparisons, key=lambda x: x["revenue"], reverse=True)
