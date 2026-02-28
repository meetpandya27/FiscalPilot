"""
Budget Management — track budgets vs actual spending.

Inspired by xtraCHEF's restaurant budgeting and Firefly III's
personal finance budgeting. Track spending against budgets,
get alerts when approaching limits, and forecast budget usage.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any
from collections import defaultdict

if TYPE_CHECKING:
    from fiscalpilot.models.financial import Transaction, ExpenseCategory

logger = logging.getLogger("fiscalpilot.analyzers.budget")


class BudgetPeriod(str, Enum):
    """Time period for a budget."""
    
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class BudgetStatus(str, Enum):
    """Current status of a budget."""
    
    ON_TRACK = "on_track"
    WARNING = "warning"       # 75-99% used
    EXCEEDED = "exceeded"     # > 100%
    UNUSED = "unused"         # < 25% used in period
    NOT_STARTED = "not_started"


@dataclass
class BudgetAlert:
    """An alert about a budget status."""
    
    budget_name: str
    alert_type: str
    message: str
    severity: str  # "info", "warning", "critical"
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class Budget:
    """A budget for tracking spending."""
    
    name: str
    amount: float
    period: BudgetPeriod
    categories: list[str] = field(default_factory=list)  # Empty = all
    vendors: list[str] = field(default_factory=list)     # Empty = all
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool = True
    rollover: bool = False  # Roll unused budget to next period
    warning_threshold: float = 0.75  # Alert at 75%
    created_at: datetime = field(default_factory=datetime.now)
    
    def get_period_dates(self, reference_date: date | None = None) -> tuple[date, date]:
        """Get start and end dates for current period."""
        ref = reference_date or date.today()
        
        if self.period == BudgetPeriod.DAILY:
            return ref, ref
        
        elif self.period == BudgetPeriod.WEEKLY:
            start = ref - timedelta(days=ref.weekday())
            end = start + timedelta(days=6)
            return start, end
        
        elif self.period == BudgetPeriod.BIWEEKLY:
            # Assume budget starts on start_date, cycle every 2 weeks
            if self.start_date:
                days_since = (ref - self.start_date).days
                period_start = days_since - (days_since % 14)
                start = self.start_date + timedelta(days=period_start)
            else:
                start = ref - timedelta(days=ref.weekday())
            end = start + timedelta(days=13)
            return start, end
        
        elif self.period == BudgetPeriod.MONTHLY:
            start = ref.replace(day=1)
            # End is last day of month
            if ref.month == 12:
                end = ref.replace(year=ref.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end = ref.replace(month=ref.month + 1, day=1) - timedelta(days=1)
            return start, end
        
        elif self.period == BudgetPeriod.QUARTERLY:
            quarter = (ref.month - 1) // 3
            start = date(ref.year, quarter * 3 + 1, 1)
            if quarter == 3:
                end = date(ref.year + 1, 1, 1) - timedelta(days=1)
            else:
                end = date(ref.year, (quarter + 1) * 3 + 1, 1) - timedelta(days=1)
            return start, end
        
        elif self.period == BudgetPeriod.YEARLY:
            start = date(ref.year, 1, 1)
            end = date(ref.year, 12, 31)
            return start, end
        
        return ref, ref
    
    def matches_transaction(self, transaction: Transaction) -> bool:
        """Check if a transaction falls under this budget."""
        # Check categories
        if self.categories:
            if transaction.category:
                if transaction.category.value not in self.categories:
                    return False
            else:
                return False
        
        # Check vendors
        if self.vendors:
            if transaction.vendor:
                if transaction.vendor.lower() not in [v.lower() for v in self.vendors]:
                    return False
            else:
                return False
        
        # Check date range
        period_start, period_end = self.get_period_dates(transaction.date)
        if transaction.date:
            if transaction.date < period_start or transaction.date > period_end:
                return False
        
        return True


@dataclass
class BudgetProgress:
    """Progress tracking for a budget."""
    
    budget: Budget
    spent: float = 0.0
    remaining: float = 0.0
    percentage_used: float = 0.0
    status: BudgetStatus = BudgetStatus.NOT_STARTED
    transactions: list[Any] = field(default_factory=list)
    period_start: date | None = None
    period_end: date | None = None
    days_remaining: int = 0
    projected_total: float = 0.0
    daily_average: float = 0.0
    
    @property
    def is_over_budget(self) -> bool:
        return self.status == BudgetStatus.EXCEEDED
    
    @property
    def budget_per_day(self) -> float:
        """Calculate daily budget allowance."""
        if self.period_start and self.period_end:
            days = (self.period_end - self.period_start).days + 1
            return self.budget.amount / days
        return 0.0


@dataclass
class BudgetReport:
    """Summary report of all budgets."""
    
    report_date: date
    total_budgeted: float
    total_spent: float
    total_remaining: float
    budgets: list[BudgetProgress] = field(default_factory=list)
    alerts: list[BudgetAlert] = field(default_factory=list)
    
    @property
    def overall_percentage(self) -> float:
        if self.total_budgeted == 0:
            return 0.0
        return self.total_spent / self.total_budgeted * 100
    
    @property
    def over_budget_count(self) -> int:
        return sum(1 for b in self.budgets if b.is_over_budget)


class BudgetManager:
    """
    Manage budgets and track spending.
    
    Features inspired by xtraCHEF and Firefly III:
    - Multiple budget periods (daily, weekly, monthly, etc.)
    - Category and vendor-specific budgets
    - Real-time progress tracking
    - Alerts at configurable thresholds
    - Projections based on current spending rate
    - Budget rollover support
    
    Example usage:
        manager = BudgetManager()
        
        # Create monthly marketing budget
        manager.create_budget(
            name="Marketing",
            amount=5000,
            period=BudgetPeriod.MONTHLY,
            categories=["marketing", "advertising"],
        )
        
        # Check budget progress
        report = manager.get_report(transactions)
        for budget in report.budgets:
            print(f"{budget.budget.name}: {budget.percentage_used:.0%} used")
    """
    
    def __init__(self, budgets: list[Budget] | None = None):
        """Initialize budget manager."""
        self.budgets = budgets or []
        
    def create_budget(
        self,
        name: str,
        amount: float,
        period: BudgetPeriod = BudgetPeriod.MONTHLY,
        categories: list[str] | None = None,
        vendors: list[str] | None = None,
        warning_threshold: float = 0.75,
        rollover: bool = False,
    ) -> Budget:
        """
        Create a new budget.
        
        Args:
            name: Budget name.
            amount: Budget amount.
            period: Budget period (monthly, weekly, etc.).
            categories: Categories this budget applies to.
            vendors: Vendors this budget applies to.
            warning_threshold: Percentage to trigger warning (0-1).
            rollover: Carry unused budget to next period.
            
        Returns:
            Created Budget.
        """
        budget = Budget(
            name=name,
            amount=amount,
            period=period,
            categories=categories or [],
            vendors=vendors or [],
            warning_threshold=warning_threshold,
            rollover=rollover,
            start_date=date.today(),
        )
        self.budgets.append(budget)
        logger.info(f"Created budget: {name} (${amount:,.2f}/{period.value})")
        return budget
    
    def add_budget(self, budget: Budget):
        """Add an existing budget."""
        self.budgets.append(budget)
    
    def remove_budget(self, name: str) -> bool:
        """Remove a budget by name."""
        before = len(self.budgets)
        self.budgets = [b for b in self.budgets if b.name != name]
        return len(self.budgets) < before
    
    def get_budget(self, name: str) -> Budget | None:
        """Get a budget by name."""
        for budget in self.budgets:
            if budget.name == name:
                return budget
        return None
    
    def calculate_progress(
        self,
        budget: Budget,
        transactions: list[Transaction],
        reference_date: date | None = None,
    ) -> BudgetProgress:
        """
        Calculate progress for a single budget.
        
        Args:
            budget: Budget to check.
            transactions: Transactions to analyze.
            reference_date: Date to calculate period from.
            
        Returns:
            BudgetProgress with spending details.
        """
        ref = reference_date or date.today()
        period_start, period_end = budget.get_period_dates(ref)
        
        # Filter transactions for this budget's period
        matching_txns = []
        total_spent = 0.0
        
        for txn in transactions:
            if not txn.date:
                continue
            
            # Check if in current period
            if txn.date < period_start or txn.date > period_end:
                continue
            
            # Check if matches budget criteria
            if budget.matches_transaction(txn):
                matching_txns.append(txn)
                total_spent += abs(txn.amount)
        
        # Calculate metrics
        remaining = budget.amount - total_spent
        pct_used = (total_spent / budget.amount * 100) if budget.amount > 0 else 0
        days_passed = (ref - period_start).days + 1
        total_days = (period_end - period_start).days + 1
        days_remaining = total_days - days_passed
        
        daily_avg = total_spent / days_passed if days_passed > 0 else 0
        projected = daily_avg * total_days if daily_avg > 0 else total_spent
        
        # Determine status
        if total_spent == 0:
            status = BudgetStatus.NOT_STARTED
        elif pct_used >= 100:
            status = BudgetStatus.EXCEEDED
        elif pct_used >= budget.warning_threshold * 100:
            status = BudgetStatus.WARNING
        elif pct_used < 25 and days_passed > total_days * 0.5:
            status = BudgetStatus.UNUSED
        else:
            status = BudgetStatus.ON_TRACK
        
        return BudgetProgress(
            budget=budget,
            spent=total_spent,
            remaining=remaining,
            percentage_used=pct_used,
            status=status,
            transactions=matching_txns,
            period_start=period_start,
            period_end=period_end,
            days_remaining=days_remaining,
            projected_total=projected,
            daily_average=daily_avg,
        )
    
    def get_report(
        self,
        transactions: list[Transaction],
        reference_date: date | None = None,
    ) -> BudgetReport:
        """
        Generate a comprehensive budget report.
        
        Args:
            transactions: Transactions to analyze.
            reference_date: Date for period calculations.
            
        Returns:
            BudgetReport with all budget progress and alerts.
        """
        ref = reference_date or date.today()
        
        budget_progress = []
        alerts = []
        total_budgeted = 0.0
        total_spent = 0.0
        
        for budget in self.budgets:
            if not budget.is_active:
                continue
            
            progress = self.calculate_progress(budget, transactions, ref)
            budget_progress.append(progress)
            
            total_budgeted += budget.amount
            total_spent += progress.spent
            
            # Generate alerts
            alerts.extend(self._generate_alerts(progress))
        
        return BudgetReport(
            report_date=ref,
            total_budgeted=total_budgeted,
            total_spent=total_spent,
            total_remaining=total_budgeted - total_spent,
            budgets=budget_progress,
            alerts=alerts,
        )
    
    def _generate_alerts(self, progress: BudgetProgress) -> list[BudgetAlert]:
        """Generate alerts for a budget progress."""
        alerts = []
        
        if progress.status == BudgetStatus.EXCEEDED:
            alerts.append(BudgetAlert(
                budget_name=progress.budget.name,
                alert_type="exceeded",
                message=f"Budget exceeded by ${abs(progress.remaining):,.2f} ({progress.percentage_used:.0f}% used)",
                severity="critical",
            ))
        
        elif progress.status == BudgetStatus.WARNING:
            alerts.append(BudgetAlert(
                budget_name=progress.budget.name,
                alert_type="warning",
                message=f"Budget at {progress.percentage_used:.0f}% with ${progress.remaining:,.2f} remaining",
                severity="warning",
            ))
        
        # Alert if projected to exceed
        if progress.projected_total > progress.budget.amount and progress.status != BudgetStatus.EXCEEDED:
            overage = progress.projected_total - progress.budget.amount
            alerts.append(BudgetAlert(
                budget_name=progress.budget.name,
                alert_type="projection",
                message=f"Projected to exceed budget by ${overage:,.2f} at current rate",
                severity="warning",
            ))
        
        return alerts
    
    def check_transaction(
        self,
        transaction: Transaction,
    ) -> list[tuple[Budget, bool, str]]:
        """
        Check if a transaction would exceed any budgets.
        
        Args:
            transaction: Transaction to check.
            
        Returns:
            List of (budget, would_exceed, message) tuples.
        """
        results = []
        
        for budget in self.budgets:
            if not budget.is_active:
                continue
            
            if budget.matches_transaction(transaction):
                # Would need actual progress to check
                results.append((
                    budget,
                    False,  # Would need current progress
                    f"Transaction applies to {budget.name} budget"
                ))
        
        return results
    
    def get_category_budgets(self) -> dict[str, list[Budget]]:
        """Get budgets organized by category."""
        by_category: dict[str, list[Budget]] = defaultdict(list)
        
        for budget in self.budgets:
            if budget.categories:
                for cat in budget.categories:
                    by_category[cat].append(budget)
            else:
                by_category["_all"].append(budget)
        
        return dict(by_category)
    
    def export_budgets(self) -> list[dict[str, Any]]:
        """Export budgets as serializable dicts."""
        return [
            {
                "name": b.name,
                "amount": b.amount,
                "period": b.period.value,
                "categories": b.categories,
                "vendors": b.vendors,
                "warning_threshold": b.warning_threshold,
                "rollover": b.rollover,
                "is_active": b.is_active,
            }
            for b in self.budgets
        ]


# Convenience functions
def create_monthly_budget(
    name: str,
    amount: float,
    categories: list[str] | None = None,
) -> Budget:
    """Quick creation of a monthly budget."""
    return Budget(
        name=name,
        amount=amount,
        period=BudgetPeriod.MONTHLY,
        categories=categories or [],
        start_date=date.today(),
    )


def check_budgets(
    transactions: list[Transaction],
    budgets: list[Budget],
) -> BudgetReport:
    """Quick budget check."""
    manager = BudgetManager(budgets)
    return manager.get_report(transactions)
