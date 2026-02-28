"""
Inventory Management — track stock levels, costs, and optimize inventory.

Provides:
- Stock level tracking and valuation
- Reorder point calculations
- ABC analysis (inventory classification)
- Turnover rate analysis
- Dead stock identification
- Par level recommendations
- FIFO/LIFO/weighted average costing
- Shrinkage and waste tracking
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class CostingMethod(str, Enum):
    """Inventory costing methods."""
    
    FIFO = "fifo"  # First In, First Out
    LIFO = "lifo"  # Last In, First Out  
    WEIGHTED_AVERAGE = "weighted_average"
    SPECIFIC_ID = "specific_id"


class StockStatus(str, Enum):
    """Stock level status."""
    
    OVERSTOCKED = "overstocked"
    OPTIMAL = "optimal"
    LOW = "low"
    CRITICAL = "critical"
    OUT_OF_STOCK = "out_of_stock"


class ABCClass(str, Enum):
    """ABC inventory classification."""
    
    A = "A"  # High value (top 80% of value, ~20% of items)
    B = "B"  # Medium value (next 15% of value, ~30% of items)
    C = "C"  # Low value (bottom 5% of value, ~50% of items)


@dataclass
class InventoryItem:
    """Represents an inventory item."""
    
    id: str
    name: str
    sku: str | None = None
    category: str = "General"
    unit: str = "each"  # each, lb, oz, case, etc.
    
    # Current stock
    quantity_on_hand: Decimal = Decimal("0")
    unit_cost: Decimal = Decimal("0")
    
    # Reorder settings
    reorder_point: Decimal | None = None
    reorder_quantity: Decimal | None = None
    par_level: Decimal | None = None
    
    # Usage tracking
    avg_daily_usage: Decimal = Decimal("0")
    lead_time_days: int = 3
    
    # Location
    location: str | None = None
    bin_number: str | None = None
    
    # Metadata
    last_received: date | None = None
    last_counted: date | None = None
    supplier: str | None = None
    
    @property
    def total_value(self) -> Decimal:
        """Total inventory value for this item."""
        return self.quantity_on_hand * self.unit_cost
    
    @property
    def days_of_stock(self) -> float | None:
        """Days of stock remaining at current usage rate."""
        if self.avg_daily_usage <= 0:
            return None
        return float(self.quantity_on_hand / self.avg_daily_usage)
    
    @property
    def status(self) -> StockStatus:
        """Current stock status."""
        if self.quantity_on_hand <= 0:
            return StockStatus.OUT_OF_STOCK
        
        if self.reorder_point is not None:
            if self.quantity_on_hand <= self.reorder_point * Decimal("0.5"):
                return StockStatus.CRITICAL
            if self.quantity_on_hand <= self.reorder_point:
                return StockStatus.LOW
        
        if self.par_level is not None:
            if self.quantity_on_hand > self.par_level * Decimal("1.5"):
                return StockStatus.OVERSTOCKED
        
        return StockStatus.OPTIMAL
    
    @property
    def suggested_order_quantity(self) -> Decimal | None:
        """Calculate suggested order quantity based on usage."""
        if self.avg_daily_usage <= 0 or self.par_level is None:
            return self.reorder_quantity
        
        # Order up to par level plus safety stock
        safety_stock = self.avg_daily_usage * self.lead_time_days
        target = self.par_level + safety_stock
        order_qty = target - self.quantity_on_hand
        
        return max(order_qty, Decimal("0"))


@dataclass
class InventoryTransaction:
    """Represents an inventory movement."""
    
    id: str
    item_id: str
    date: datetime
    transaction_type: str  # receive, issue, adjust, transfer, count, waste
    quantity: Decimal
    unit_cost: Decimal | None = None
    total_cost: Decimal | None = None
    reference: str | None = None  # PO#, invoice#, etc.
    reason: str | None = None
    location_from: str | None = None
    location_to: str | None = None
    user: str | None = None
    notes: str | None = None


@dataclass
class InventoryCount:
    """Represents a physical inventory count."""
    
    id: str
    date: datetime
    items: list[dict[str, Any]] = field(default_factory=list)
    status: str = "in_progress"  # in_progress, completed, approved
    counted_by: str | None = None
    approved_by: str | None = None
    notes: str | None = None
    
    @property
    def total_variance(self) -> Decimal:
        """Total variance value from count."""
        return sum(
            Decimal(str(item.get("variance_value", 0)))
            for item in self.items
        )
    
    @property
    def variance_percentage(self) -> float:
        """Variance as percentage of total value."""
        expected_value = sum(
            Decimal(str(item.get("expected_value", 0)))
            for item in self.items
        )
        if expected_value == 0:
            return 0.0
        return float(abs(self.total_variance) / expected_value * 100)


@dataclass
class ABCAnalysisResult:
    """Result of ABC inventory analysis."""
    
    item_id: str
    item_name: str
    annual_value: Decimal
    cumulative_percentage: float
    abc_class: ABCClass
    usage_frequency: int
    
    
@dataclass 
class TurnoverAnalysis:
    """Inventory turnover analysis result."""
    
    item_id: str
    item_name: str
    category: str
    cost_of_goods_sold: Decimal
    average_inventory: Decimal
    turnover_rate: float
    days_inventory: float
    
    @property
    def is_slow_moving(self) -> bool:
        """Item is slow moving if turnover < 4x/year."""
        return self.turnover_rate < 4.0
    
    @property
    def is_dead_stock(self) -> bool:
        """Item is dead stock if no turns in 6+ months."""
        return self.days_inventory > 180 or self.turnover_rate < 1.0


class InventoryManager:
    """Inventory management and analysis.

    Usage::

        manager = InventoryManager()
        
        # Add items
        item = InventoryItem(id="1", name="Tomatoes", unit="lb")
        manager.add_item(item)
        
        # Receive inventory
        manager.receive(item_id="1", quantity=50, unit_cost=Decimal("2.50"))
        
        # Issue/use inventory
        manager.issue(item_id="1", quantity=10, reason="Kitchen use")
        
        # Get reports
        low_stock = manager.get_low_stock_items()
        abc = manager.abc_analysis()
    """

    def __init__(
        self,
        costing_method: CostingMethod = CostingMethod.WEIGHTED_AVERAGE,
    ) -> None:
        self.costing_method = costing_method
        self.items: dict[str, InventoryItem] = {}
        self.transactions: list[InventoryTransaction] = []
        self._cost_layers: dict[str, list[dict]] = {}  # For FIFO/LIFO

    def add_item(self, item: InventoryItem) -> None:
        """Add an inventory item."""
        self.items[item.id] = item
        self._cost_layers[item.id] = []

    def get_item(self, item_id: str) -> InventoryItem | None:
        """Get an inventory item by ID."""
        return self.items.get(item_id)

    def receive(
        self,
        item_id: str,
        quantity: Decimal,
        unit_cost: Decimal,
        reference: str | None = None,
        supplier: str | None = None,
        notes: str | None = None,
    ) -> InventoryTransaction:
        """Receive inventory from a purchase."""
        item = self.items.get(item_id)
        if not item:
            raise ValueError(f"Item {item_id} not found")

        # Update item quantity and cost
        old_qty = item.quantity_on_hand
        old_cost = item.unit_cost
        new_qty = old_qty + quantity

        if self.costing_method == CostingMethod.WEIGHTED_AVERAGE:
            # Weighted average cost
            if new_qty > 0:
                total_old = old_qty * old_cost
                total_new = quantity * unit_cost
                item.unit_cost = (total_old + total_new) / new_qty
        elif self.costing_method in (CostingMethod.FIFO, CostingMethod.LIFO):
            # Add cost layer
            self._cost_layers[item_id].append({
                "quantity": quantity,
                "unit_cost": unit_cost,
                "date": datetime.now(),
            })

        item.quantity_on_hand = new_qty
        item.last_received = date.today()
        if supplier:
            item.supplier = supplier

        # Record transaction
        txn = InventoryTransaction(
            id=f"rcv_{datetime.now().timestamp()}",
            item_id=item_id,
            date=datetime.now(),
            transaction_type="receive",
            quantity=quantity,
            unit_cost=unit_cost,
            total_cost=quantity * unit_cost,
            reference=reference,
            notes=notes,
        )
        self.transactions.append(txn)
        
        return txn

    def issue(
        self,
        item_id: str,
        quantity: Decimal,
        reason: str | None = None,
        reference: str | None = None,
        notes: str | None = None,
    ) -> InventoryTransaction:
        """Issue inventory (use, sell, transfer out)."""
        item = self.items.get(item_id)
        if not item:
            raise ValueError(f"Item {item_id} not found")

        if quantity > item.quantity_on_hand:
            raise ValueError(f"Insufficient stock: {item.quantity_on_hand} available")

        # Calculate cost based on method
        if self.costing_method == CostingMethod.WEIGHTED_AVERAGE:
            issue_cost = item.unit_cost
        elif self.costing_method == CostingMethod.FIFO:
            issue_cost = self._calculate_fifo_cost(item_id, quantity)
        elif self.costing_method == CostingMethod.LIFO:
            issue_cost = self._calculate_lifo_cost(item_id, quantity)
        else:
            issue_cost = item.unit_cost

        item.quantity_on_hand -= quantity

        # Record transaction
        txn = InventoryTransaction(
            id=f"iss_{datetime.now().timestamp()}",
            item_id=item_id,
            date=datetime.now(),
            transaction_type="issue",
            quantity=-quantity,  # Negative for issues
            unit_cost=issue_cost,
            total_cost=quantity * issue_cost,
            reason=reason,
            reference=reference,
            notes=notes,
        )
        self.transactions.append(txn)
        
        return txn

    def _calculate_fifo_cost(self, item_id: str, quantity: Decimal) -> Decimal:
        """Calculate cost using FIFO method."""
        layers = self._cost_layers.get(item_id, [])
        remaining = quantity
        total_cost = Decimal("0")
        
        while remaining > 0 and layers:
            layer = layers[0]
            use_qty = min(remaining, layer["quantity"])
            total_cost += use_qty * layer["unit_cost"]
            layer["quantity"] -= use_qty
            remaining -= use_qty
            
            if layer["quantity"] <= 0:
                layers.pop(0)
        
        if quantity > 0:
            return total_cost / quantity
        return Decimal("0")

    def _calculate_lifo_cost(self, item_id: str, quantity: Decimal) -> Decimal:
        """Calculate cost using LIFO method."""
        layers = self._cost_layers.get(item_id, [])
        remaining = quantity
        total_cost = Decimal("0")
        
        while remaining > 0 and layers:
            layer = layers[-1]
            use_qty = min(remaining, layer["quantity"])
            total_cost += use_qty * layer["unit_cost"]
            layer["quantity"] -= use_qty
            remaining -= use_qty
            
            if layer["quantity"] <= 0:
                layers.pop()
        
        if quantity > 0:
            return total_cost / quantity
        return Decimal("0")

    def adjust(
        self,
        item_id: str,
        new_quantity: Decimal,
        reason: str,
        notes: str | None = None,
    ) -> InventoryTransaction:
        """Adjust inventory quantity (from count, shrinkage, etc)."""
        item = self.items.get(item_id)
        if not item:
            raise ValueError(f"Item {item_id} not found")

        variance = new_quantity - item.quantity_on_hand
        item.quantity_on_hand = new_quantity

        txn = InventoryTransaction(
            id=f"adj_{datetime.now().timestamp()}",
            item_id=item_id,
            date=datetime.now(),
            transaction_type="adjust",
            quantity=variance,
            unit_cost=item.unit_cost,
            total_cost=abs(variance) * item.unit_cost,
            reason=reason,
            notes=notes,
        )
        self.transactions.append(txn)
        
        return txn

    def waste(
        self,
        item_id: str,
        quantity: Decimal,
        reason: str,
        notes: str | None = None,
    ) -> InventoryTransaction:
        """Record waste/spoilage."""
        item = self.items.get(item_id)
        if not item:
            raise ValueError(f"Item {item_id} not found")

        item.quantity_on_hand -= quantity

        txn = InventoryTransaction(
            id=f"waste_{datetime.now().timestamp()}",
            item_id=item_id,
            date=datetime.now(),
            transaction_type="waste",
            quantity=-quantity,
            unit_cost=item.unit_cost,
            total_cost=quantity * item.unit_cost,
            reason=reason,
            notes=notes,
        )
        self.transactions.append(txn)
        
        return txn

    def get_total_value(self) -> Decimal:
        """Get total inventory value."""
        return sum(item.total_value for item in self.items.values())

    def get_low_stock_items(self) -> list[InventoryItem]:
        """Get items that are low or critical stock."""
        return [
            item for item in self.items.values()
            if item.status in (StockStatus.LOW, StockStatus.CRITICAL, StockStatus.OUT_OF_STOCK)
        ]

    def get_items_to_reorder(self) -> list[tuple[InventoryItem, Decimal]]:
        """Get items that need to be reordered with suggested quantities."""
        reorder_list = []
        
        for item in self.items.values():
            if item.reorder_point is None:
                continue
            if item.quantity_on_hand <= item.reorder_point:
                suggested_qty = item.suggested_order_quantity
                if suggested_qty and suggested_qty > 0:
                    reorder_list.append((item, suggested_qty))
        
        return sorted(reorder_list, key=lambda x: x[0].status.value)

    def abc_analysis(self) -> list[ABCAnalysisResult]:
        """Perform ABC analysis on inventory.
        
        Classifies items by annual value:
        - A: Top 80% of value (usually ~20% of items)
        - B: Next 15% of value (usually ~30% of items)
        - C: Bottom 5% of value (usually ~50% of items)
        """
        # Calculate annual value for each item
        item_values = []
        for item in self.items.values():
            # Estimate annual value from daily usage
            annual_value = item.avg_daily_usage * item.unit_cost * 365
            
            # Count usage frequency from transactions
            usage_count = sum(
                1 for txn in self.transactions
                if txn.item_id == item.id and txn.transaction_type == "issue"
            )
            
            item_values.append({
                "item": item,
                "annual_value": annual_value,
                "usage_frequency": usage_count,
            })
        
        # Sort by annual value descending
        item_values.sort(key=lambda x: x["annual_value"], reverse=True)
        
        # Calculate cumulative percentages and assign classes
        total_value = sum(iv["annual_value"] for iv in item_values)
        if total_value == 0:
            total_value = Decimal("1")  # Avoid division by zero
        
        results = []
        cumulative = Decimal("0")
        
        for iv in item_values:
            cumulative += iv["annual_value"]
            cumulative_pct = float(cumulative / total_value * 100)
            
            if cumulative_pct <= 80:
                abc_class = ABCClass.A
            elif cumulative_pct <= 95:
                abc_class = ABCClass.B
            else:
                abc_class = ABCClass.C
            
            results.append(ABCAnalysisResult(
                item_id=iv["item"].id,
                item_name=iv["item"].name,
                annual_value=iv["annual_value"],
                cumulative_percentage=cumulative_pct,
                abc_class=abc_class,
                usage_frequency=iv["usage_frequency"],
            ))
        
        return results

    def turnover_analysis(
        self,
        cost_of_goods_sold: dict[str, Decimal] | None = None,
    ) -> list[TurnoverAnalysis]:
        """Analyze inventory turnover rates.
        
        Args:
            cost_of_goods_sold: COGS by item_id. If not provided,
                               estimates from issue transactions.
        """
        results = []
        
        for item in self.items.values():
            # Calculate COGS from transactions if not provided
            if cost_of_goods_sold and item.id in cost_of_goods_sold:
                cogs = cost_of_goods_sold[item.id]
            else:
                # Sum issue transactions
                cogs = sum(
                    abs(txn.total_cost or Decimal("0"))
                    for txn in self.transactions
                    if txn.item_id == item.id and txn.transaction_type == "issue"
                )
            
            # Use current inventory as average (simplified)
            avg_inventory = item.total_value
            if avg_inventory == 0:
                avg_inventory = Decimal("1")
            
            turnover = float(cogs / avg_inventory) if avg_inventory > 0 else 0
            days_inv = 365 / turnover if turnover > 0 else 365
            
            results.append(TurnoverAnalysis(
                item_id=item.id,
                item_name=item.name,
                category=item.category,
                cost_of_goods_sold=cogs,
                average_inventory=avg_inventory,
                turnover_rate=turnover,
                days_inventory=days_inv,
            ))
        
        return sorted(results, key=lambda x: x.turnover_rate)

    def get_dead_stock(self) -> list[TurnoverAnalysis]:
        """Get items classified as dead stock."""
        turnover = self.turnover_analysis()
        return [t for t in turnover if t.is_dead_stock]

    def get_slow_moving(self) -> list[TurnoverAnalysis]:
        """Get slow-moving inventory items."""
        turnover = self.turnover_analysis()
        return [t for t in turnover if t.is_slow_moving and not t.is_dead_stock]

    def calculate_reorder_point(
        self,
        item_id: str,
        service_level: float = 0.95,
    ) -> Decimal:
        """Calculate optimal reorder point for an item.
        
        Args:
            item_id: Item to calculate for.
            service_level: Desired service level (0-1).
        
        Returns:
            Recommended reorder point quantity.
        """
        item = self.items.get(item_id)
        if not item or item.avg_daily_usage <= 0:
            return Decimal("0")
        
        # Simple formula: (Daily Usage × Lead Time) + Safety Stock
        lead_time_demand = item.avg_daily_usage * item.lead_time_days
        
        # Safety stock based on service level (simplified)
        # Higher service level = more safety stock
        safety_factor = Decimal(str({
            0.90: 1.28,
            0.95: 1.65,
            0.99: 2.33,
        }.get(service_level, 1.65)))
        
        # Assume 20% variability in demand
        safety_stock = item.avg_daily_usage * Decimal("0.2") * safety_factor * Decimal(str(item.lead_time_days ** 0.5))
        
        return lead_time_demand + safety_stock

    def calculate_par_level(
        self,
        item_id: str,
        order_frequency_days: int = 7,
    ) -> Decimal:
        """Calculate recommended par level.
        
        Args:
            item_id: Item to calculate for.
            order_frequency_days: How often orders are placed.
        
        Returns:
            Recommended par level.
        """
        item = self.items.get(item_id)
        if not item or item.avg_daily_usage <= 0:
            return Decimal("0")
        
        # Par = (Daily Usage × Order Cycle) + Reorder Point
        order_cycle_demand = item.avg_daily_usage * order_frequency_days
        reorder_point = self.calculate_reorder_point(item_id)
        
        return order_cycle_demand + reorder_point

    def get_waste_report(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        """Generate waste/shrinkage report.
        
        Returns summary of waste transactions and values.
        """
        waste_txns = [
            txn for txn in self.transactions
            if txn.transaction_type in ("waste", "adjust")
            and (start_date is None or txn.date.date() >= start_date)
            and (end_date is None or txn.date.date() <= end_date)
        ]
        
        total_waste_value = sum(
            abs(txn.total_cost or Decimal("0"))
            for txn in waste_txns
            if txn.quantity < 0
        )
        
        by_reason: dict[str, Decimal] = {}
        for txn in waste_txns:
            reason = txn.reason or "Unknown"
            by_reason[reason] = by_reason.get(reason, Decimal("0")) + abs(txn.total_cost or Decimal("0"))
        
        by_item: dict[str, Decimal] = {}
        for txn in waste_txns:
            item = self.items.get(txn.item_id)
            name = item.name if item else txn.item_id
            by_item[name] = by_item.get(name, Decimal("0")) + abs(txn.total_cost or Decimal("0"))
        
        return {
            "total_transactions": len(waste_txns),
            "total_value": float(total_waste_value),
            "by_reason": {k: float(v) for k, v in sorted(by_reason.items(), key=lambda x: x[1], reverse=True)},
            "by_item": {k: float(v) for k, v in sorted(by_item.items(), key=lambda x: x[1], reverse=True)[:10]},
            "percentage_of_inventory": float(total_waste_value / max(self.get_total_value(), Decimal("1")) * 100),
        }

    def get_valuation_report(self) -> dict[str, Any]:
        """Generate inventory valuation report."""
        by_category: dict[str, Decimal] = {}
        by_status: dict[str, tuple[int, Decimal]] = {}
        
        for item in self.items.values():
            # By category
            cat = item.category
            by_category[cat] = by_category.get(cat, Decimal("0")) + item.total_value
            
            # By status
            status = item.status.value
            count, value = by_status.get(status, (0, Decimal("0")))
            by_status[status] = (count + 1, value + item.total_value)
        
        return {
            "total_items": len(self.items),
            "total_value": float(self.get_total_value()),
            "costing_method": self.costing_method.value,
            "by_category": {k: float(v) for k, v in sorted(by_category.items(), key=lambda x: x[1], reverse=True)},
            "by_status": {
                status: {"count": count, "value": float(value)}
                for status, (count, value) in by_status.items()
            },
            "low_stock_count": len(self.get_low_stock_items()),
            "dead_stock_value": sum(
                self.items[t.item_id].total_value
                for t in self.get_dead_stock()
                if t.item_id in self.items
            ),
        }
