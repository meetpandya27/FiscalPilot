"""
Transaction Splitting Module — split transactions across categories/cost centers.

Provides:
- Split by percentage or amount
- Multi-category allocation
- Cost center splits
- Project-based splits
- Split templates
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum


class SplitMethod(str, Enum):
    """How to split amounts."""
    
    PERCENTAGE = "percentage"
    FIXED_AMOUNT = "fixed_amount"
    EQUAL = "equal"


@dataclass
class SplitAllocation:
    """A single split allocation."""
    
    # Target
    category: str | None = None
    cost_center: str | None = None
    project: str | None = None
    department: str | None = None
    account_code: str | None = None
    
    # Allocation
    percentage: Decimal | None = None  # When using percentage method
    amount: Decimal | None = None  # Fixed or calculated amount
    
    # Metadata
    description: str | None = None


@dataclass
class SplitTemplate:
    """A reusable split template."""
    
    id: str
    name: str
    description: str | None = None
    
    method: SplitMethod = SplitMethod.PERCENTAGE
    allocations: list[SplitAllocation] = field(default_factory=list)
    
    # Applicability
    applies_to_category: str | None = None  # Auto-apply to this category
    applies_to_vendor: str | None = None  # Auto-apply to this vendor
    
    # State
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    created_by: str | None = None


@dataclass
class TransactionSplit:
    """A split transaction record."""
    
    id: str
    original_transaction_id: str
    original_amount: Decimal
    
    split_date: datetime = field(default_factory=datetime.now)
    split_by: str | None = None
    template_id: str | None = None
    
    allocations: list[SplitAllocation] = field(default_factory=list)
    
    # Validation
    is_balanced: bool = True
    balance_difference: Decimal = Decimal("0")
    
    notes: str | None = None


@dataclass
class SplitResult:
    """Result of a split operation."""
    
    success: bool
    split: TransactionSplit | None = None
    error: str | None = None
    
    # Validation details
    total_allocated: Decimal = Decimal("0")
    original_amount: Decimal = Decimal("0")
    difference: Decimal = Decimal("0")


class TransactionSplitter:
    """Split transactions across categories and cost centers.

    Usage::

        splitter = TransactionSplitter()
        
        # Create a split template
        template = SplitTemplate(
            id="office_supplies",
            name="Office Supplies Split",
            method=SplitMethod.PERCENTAGE,
            allocations=[
                SplitAllocation(department="Marketing", percentage=Decimal("40")),
                SplitAllocation(department="Engineering", percentage=Decimal("40")),
                SplitAllocation(department="Sales", percentage=Decimal("20")),
            ],
        )
        splitter.add_template(template)
        
        # Split a transaction
        result = splitter.split_transaction(
            transaction_id="txn_001",
            amount=Decimal("500.00"),
            template_id="office_supplies",
        )
        
        # Or split manually
        result = splitter.split_transaction(
            transaction_id="txn_002",
            amount=Decimal("1000.00"),
            allocations=[
                SplitAllocation(category="Software", percentage=Decimal("60")),
                SplitAllocation(category="Services", percentage=Decimal("40")),
            ],
        )
    """

    def __init__(self) -> None:
        self.templates: dict[str, SplitTemplate] = {}
        self.splits: dict[str, TransactionSplit] = {}
        
        self._split_counter = 0

    def add_template(self, template: SplitTemplate) -> None:
        """Add a split template."""
        self.templates[template.id] = template

    def get_template(self, template_id: str) -> SplitTemplate | None:
        """Get a template by ID."""
        return self.templates.get(template_id)

    def find_matching_template(
        self,
        category: str | None = None,
        vendor: str | None = None,
    ) -> SplitTemplate | None:
        """Find a template that auto-applies to the given criteria.
        
        Args:
            category: Transaction category.
            vendor: Vendor name.
        
        Returns:
            Matching template or None.
        """
        for template in self.templates.values():
            if not template.is_active:
                continue
            
            if template.applies_to_category and category:
                if template.applies_to_category.lower() == category.lower():
                    return template
            
            if template.applies_to_vendor and vendor:
                if template.applies_to_vendor.lower() == vendor.lower():
                    return template
        
        return None

    def _calculate_allocations(
        self,
        amount: Decimal,
        allocations: list[SplitAllocation],
        method: SplitMethod,
    ) -> list[SplitAllocation]:
        """Calculate actual amounts for allocations.
        
        Args:
            amount: Total amount to split.
            allocations: List of allocations.
            method: Split method.
        
        Returns:
            Allocations with calculated amounts.
        """
        result = []
        
        if method == SplitMethod.EQUAL:
            # Split equally
            count = len(allocations)
            if count == 0:
                return []
            
            per_allocation = (amount / count).quantize(Decimal("0.01"), ROUND_HALF_UP)
            
            # Handle rounding difference
            total = per_allocation * count
            diff = amount - total
            
            for i, alloc in enumerate(allocations):
                alloc_amount = per_allocation
                if i == 0:  # Add rounding difference to first allocation
                    alloc_amount += diff
                
                result.append(SplitAllocation(
                    category=alloc.category,
                    cost_center=alloc.cost_center,
                    project=alloc.project,
                    department=alloc.department,
                    account_code=alloc.account_code,
                    percentage=Decimal("100") / count,
                    amount=alloc_amount,
                    description=alloc.description,
                ))
        
        elif method == SplitMethod.PERCENTAGE:
            # Split by percentage
            running_total = Decimal("0")
            
            for i, alloc in enumerate(allocations):
                if alloc.percentage is None:
                    continue
                
                if i == len(allocations) - 1:
                    # Last allocation gets remainder to ensure balance
                    alloc_amount = amount - running_total
                else:
                    alloc_amount = (amount * alloc.percentage / 100).quantize(
                        Decimal("0.01"), ROUND_HALF_UP
                    )
                
                running_total += alloc_amount
                
                result.append(SplitAllocation(
                    category=alloc.category,
                    cost_center=alloc.cost_center,
                    project=alloc.project,
                    department=alloc.department,
                    account_code=alloc.account_code,
                    percentage=alloc.percentage,
                    amount=alloc_amount,
                    description=alloc.description,
                ))
        
        elif method == SplitMethod.FIXED_AMOUNT:
            # Use fixed amounts
            for alloc in allocations:
                if alloc.amount is None:
                    continue
                
                # Calculate percentage for reference
                pct = (alloc.amount / amount * 100).quantize(
                    Decimal("0.01"), ROUND_HALF_UP
                ) if amount > 0 else Decimal("0")
                
                result.append(SplitAllocation(
                    category=alloc.category,
                    cost_center=alloc.cost_center,
                    project=alloc.project,
                    department=alloc.department,
                    account_code=alloc.account_code,
                    percentage=pct,
                    amount=alloc.amount,
                    description=alloc.description,
                ))
        
        return result

    def validate_allocations(
        self,
        amount: Decimal,
        allocations: list[SplitAllocation],
    ) -> tuple[bool, Decimal]:
        """Validate that allocations balance.
        
        Args:
            amount: Original amount.
            allocations: Calculated allocations.
        
        Returns:
            Tuple of (is_balanced, difference).
        """
        total_allocated = sum(a.amount or Decimal("0") for a in allocations)
        difference = amount - total_allocated
        
        # Allow small rounding differences (< $0.01)
        is_balanced = abs(difference) < Decimal("0.01")
        
        return is_balanced, difference

    def split_transaction(
        self,
        transaction_id: str,
        amount: Decimal,
        allocations: list[SplitAllocation] | None = None,
        template_id: str | None = None,
        split_by: str | None = None,
        notes: str | None = None,
    ) -> SplitResult:
        """Split a transaction.
        
        Args:
            transaction_id: ID of transaction to split.
            amount: Total amount.
            allocations: Manual allocations.
            template_id: Template to use.
            split_by: User performing the split.
            notes: Optional notes.
        
        Returns:
            Split result.
        """
        # Get allocations from template or use provided
        method = SplitMethod.PERCENTAGE
        
        if template_id:
            template = self.templates.get(template_id)
            if not template:
                return SplitResult(
                    success=False,
                    error=f"Template not found: {template_id}",
                    original_amount=amount,
                )
            allocations = template.allocations
            method = template.method
        
        if not allocations:
            return SplitResult(
                success=False,
                error="No allocations provided",
                original_amount=amount,
            )
        
        # Calculate amounts
        calculated = self._calculate_allocations(amount, allocations, method)
        
        # Validate
        is_balanced, difference = self.validate_allocations(amount, calculated)
        
        # Create split record
        self._split_counter += 1
        split = TransactionSplit(
            id=f"split_{self._split_counter}",
            original_transaction_id=transaction_id,
            original_amount=amount,
            split_by=split_by,
            template_id=template_id,
            allocations=calculated,
            is_balanced=is_balanced,
            balance_difference=difference,
            notes=notes,
        )
        
        self.splits[split.id] = split
        
        total_allocated = sum(a.amount or Decimal("0") for a in calculated)
        
        return SplitResult(
            success=is_balanced,
            split=split,
            total_allocated=total_allocated,
            original_amount=amount,
            difference=difference,
            error=None if is_balanced else f"Split does not balance. Difference: {difference}",
        )

    def get_split(self, split_id: str) -> TransactionSplit | None:
        """Get a split by ID."""
        return self.splits.get(split_id)

    def get_splits_for_transaction(self, transaction_id: str) -> list[TransactionSplit]:
        """Get all splits for a transaction."""
        return [
            s for s in self.splits.values()
            if s.original_transaction_id == transaction_id
        ]

    def get_allocations_by_category(
        self,
        category: str,
    ) -> list[tuple[TransactionSplit, SplitAllocation]]:
        """Get all allocations to a category.
        
        Args:
            category: Category name.
        
        Returns:
            List of (split, allocation) tuples.
        """
        results = []
        
        for split in self.splits.values():
            for alloc in split.allocations:
                if alloc.category and alloc.category.lower() == category.lower():
                    results.append((split, alloc))
        
        return results

    def get_allocations_by_cost_center(
        self,
        cost_center: str,
    ) -> list[tuple[TransactionSplit, SplitAllocation]]:
        """Get all allocations to a cost center.
        
        Args:
            cost_center: Cost center name.
        
        Returns:
            List of (split, allocation) tuples.
        """
        results = []
        
        for split in self.splits.values():
            for alloc in split.allocations:
                if alloc.cost_center and alloc.cost_center.lower() == cost_center.lower():
                    results.append((split, alloc))
        
        return results

    def get_allocations_by_department(
        self,
        department: str,
    ) -> list[tuple[TransactionSplit, SplitAllocation]]:
        """Get all allocations to a department.
        
        Args:
            department: Department name.
        
        Returns:
            List of (split, allocation) tuples.
        """
        results = []
        
        for split in self.splits.values():
            for alloc in split.allocations:
                if alloc.department and alloc.department.lower() == department.lower():
                    results.append((split, alloc))
        
        return results

    def summarize_by_dimension(
        self,
        dimension: str = "category",
    ) -> dict[str, Decimal]:
        """Summarize allocated amounts by dimension.
        
        Args:
            dimension: Dimension to summarize by (category, cost_center, department, project).
        
        Returns:
            Dict of dimension value -> total amount.
        """
        summary: dict[str, Decimal] = {}
        
        for split in self.splits.values():
            for alloc in split.allocations:
                key = None
                
                if dimension == "category":
                    key = alloc.category
                elif dimension == "cost_center":
                    key = alloc.cost_center
                elif dimension == "department":
                    key = alloc.department
                elif dimension == "project":
                    key = alloc.project
                
                if key and alloc.amount:
                    summary[key] = summary.get(key, Decimal("0")) + alloc.amount
        
        return dict(sorted(summary.items(), key=lambda x: -x[1]))

    def unsplit_transaction(self, split_id: str) -> bool:
        """Remove a split (restore original transaction).
        
        Args:
            split_id: ID of split to remove.
        
        Returns:
            True if removed, False if not found.
        """
        if split_id in self.splits:
            del self.splits[split_id]
            return True
        return False

    def create_template_from_split(
        self,
        split_id: str,
        template_name: str,
        template_id: str | None = None,
    ) -> SplitTemplate | None:
        """Create a reusable template from an existing split.
        
        Args:
            split_id: Split to base template on.
            template_name: Name for new template.
            template_id: Optional ID (auto-generated if not provided).
        
        Returns:
            Created template or None if split not found.
        """
        split = self.splits.get(split_id)
        if not split:
            return None
        
        # Create allocations with just percentages (not amounts)
        template_allocations = []
        for alloc in split.allocations:
            template_allocations.append(SplitAllocation(
                category=alloc.category,
                cost_center=alloc.cost_center,
                project=alloc.project,
                department=alloc.department,
                account_code=alloc.account_code,
                percentage=alloc.percentage,
                description=alloc.description,
            ))
        
        template = SplitTemplate(
            id=template_id or f"template_{len(self.templates) + 1}",
            name=template_name,
            method=SplitMethod.PERCENTAGE,
            allocations=template_allocations,
        )
        
        self.templates[template.id] = template
        return template
