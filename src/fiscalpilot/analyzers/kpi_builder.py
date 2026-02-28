"""
Custom KPI Builder — user-defined metrics and dashboards.

Provides:
- Custom metric definitions
- Formula-based calculations
- KPI dashboards
- Benchmark comparisons
- Goal tracking
- Trend analysis
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Callable


class KPICategory(str, Enum):
    """KPI categories."""
    
    FINANCIAL = "financial"
    OPERATIONAL = "operational"
    CUSTOMER = "customer"
    EMPLOYEE = "employee"
    CUSTOM = "custom"


class AggregationType(str, Enum):
    """How to aggregate values."""
    
    SUM = "sum"
    AVERAGE = "average"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    LAST = "last"
    FIRST = "first"


class ComparisonPeriod(str, Enum):
    """Comparison period types."""
    
    PREVIOUS_PERIOD = "previous_period"
    PREVIOUS_YEAR = "previous_year"
    YEAR_TO_DATE = "ytd"
    MONTHLY_AVERAGE = "monthly_avg"


class GoalStatus(str, Enum):
    """Goal achievement status."""
    
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    BEHIND = "behind"
    ACHIEVED = "achieved"
    NOT_STARTED = "not_started"


@dataclass
class DataSource:
    """A data source for KPIs."""
    
    id: str
    name: str
    type: str  # transactions, invoices, custom, etc.
    
    # Data provider function
    query: str | None = None  # SQL-like query or filter
    fields: list[str] = field(default_factory=list)


@dataclass
class KPIDefinition:
    """Definition of a KPI."""
    
    id: str
    name: str
    description: str
    category: KPICategory
    
    # Formula and calculation
    formula: str  # e.g., "revenue - expenses" or "{gross_profit}/{revenue}*100"
    unit: str = ""  # "$", "%", "days", etc.
    decimals: int = 2
    
    # Data sources
    source_ids: list[str] = field(default_factory=list)
    
    # Aggregation
    aggregation: AggregationType = AggregationType.SUM
    
    # Display
    display_format: str = "{value}"  # e.g., "${value:,.2f}" or "{value:.1f}%"
    higher_is_better: bool = True
    
    # Thresholds for status
    warning_threshold: Decimal | None = None
    critical_threshold: Decimal | None = None
    
    # Goal
    goal_value: Decimal | None = None
    goal_period: str | None = None  # "monthly", "quarterly", "yearly"


@dataclass
class KPIValue:
    """A calculated KPI value."""
    
    kpi_id: str
    kpi_name: str
    
    # Value
    value: Decimal
    formatted_value: str
    unit: str
    
    # Period
    period_start: datetime
    period_end: datetime
    
    # Comparison
    comparison_value: Decimal | None = None
    comparison_period: str | None = None
    change_value: Decimal | None = None
    change_percent: float | None = None
    
    # Status
    status: str = "normal"  # normal, warning, critical
    goal_status: GoalStatus | None = None
    goal_progress_pct: float | None = None
    
    # Trend
    trend: str | None = None  # up, down, flat
    
    calculated_at: datetime = field(default_factory=datetime.now)


@dataclass
class KPIDashboard:
    """A dashboard of KPIs."""
    
    id: str
    name: str
    description: str
    
    # KPIs to display
    kpi_ids: list[str] = field(default_factory=list)
    
    # Layout
    layout: list[dict[str, Any]] = field(default_factory=list)  # Grid positions
    
    # Filters
    default_period: str = "month"  # day, week, month, quarter, year
    
    # Sharing
    is_public: bool = False
    owner_id: str | None = None


@dataclass
class KPIGoal:
    """A goal for a KPI."""
    
    id: str
    kpi_id: str
    
    target_value: Decimal
    period_type: str  # monthly, quarterly, yearly
    start_date: datetime
    end_date: datetime
    
    # Progress
    current_value: Decimal | None = None
    progress_pct: float = 0.0
    status: GoalStatus = GoalStatus.NOT_STARTED
    
    # Updates
    last_updated: datetime | None = None


class KPIBuilder:
    """Build and calculate custom KPIs.

    Usage::

        builder = KPIBuilder()
        
        # Register data sources
        builder.register_source(DataSource(
            id="transactions",
            name="Transactions",
            type="transactions",
            fields=["amount", "category", "date"],
        ))
        
        # Define a KPI
        builder.add_kpi(KPIDefinition(
            id="gross_margin",
            name="Gross Margin",
            description="Gross profit as % of revenue",
            category=KPICategory.FINANCIAL,
            formula="(revenue - cogs) / revenue * 100",
            unit="%",
            display_format="{value:.1f}%",
            higher_is_better=True,
            goal_value=Decimal("35"),
        ))
        
        # Calculate KPIs
        values = builder.calculate_kpi(
            "gross_margin",
            variables={"revenue": 100000, "cogs": 65000},
        )
    """

    def __init__(self) -> None:
        self.kpis: dict[str, KPIDefinition] = {}
        self.sources: dict[str, DataSource] = {}
        self.dashboards: dict[str, KPIDashboard] = {}
        self.goals: dict[str, KPIGoal] = {}
        
        # Built-in variable providers
        self._variable_providers: dict[str, Callable[[], Decimal]] = {}
        
        # Historical values for trend analysis
        self._historical_values: dict[str, list[tuple[datetime, Decimal]]] = {}

    def register_source(self, source: DataSource) -> None:
        """Register a data source."""
        self.sources[source.id] = source

    def add_kpi(self, kpi: KPIDefinition) -> None:
        """Add a KPI definition."""
        self.kpis[kpi.id] = kpi

    def remove_kpi(self, kpi_id: str) -> None:
        """Remove a KPI."""
        if kpi_id in self.kpis:
            del self.kpis[kpi_id]

    def register_variable_provider(
        self,
        name: str,
        provider: Callable[[], Decimal],
    ) -> None:
        """Register a function that provides variable values."""
        self._variable_providers[name] = provider

    def _parse_formula(self, formula: str) -> list[str]:
        """Extract variable names from formula."""
        # Match variables like {revenue} or plain revenue
        pattern = r'\{?([a-zA-Z_][a-zA-Z0-9_]*)\}?'
        matches = re.findall(pattern, formula)
        
        # Filter out math operators
        operators = {'sum', 'avg', 'min', 'max', 'abs', 'round'}
        return [m for m in matches if m.lower() not in operators]

    def _evaluate_formula(
        self,
        formula: str,
        variables: dict[str, Any],
    ) -> Decimal:
        """Evaluate a formula with given variables.
        
        Args:
            formula: The formula string.
            variables: Variable values.
        
        Returns:
            Calculated result.
        """
        # Replace variable placeholders
        expr = formula
        
        # Replace {var} syntax
        for name, value in variables.items():
            expr = expr.replace(f"{{{name}}}", str(value))
            # Also replace plain variable names (word boundaries)
            expr = re.sub(rf'\b{name}\b', str(value), expr)
        
        # Safe evaluation (only allow basic math)
        try:
            # Only allow numbers, operators, and math functions
            allowed = re.compile(r'^[\d\.\+\-\*\/\(\)\s,]+$')
            if not allowed.match(expr):
                raise ValueError(f"Invalid formula: {expr}")
            
            result = eval(expr)  # noqa: S307
            return Decimal(str(result))
        except Exception as e:
            raise ValueError(f"Failed to evaluate formula '{formula}': {e}")

    def calculate_kpi(
        self,
        kpi_id: str,
        variables: dict[str, Any] | None = None,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
        compare_with: ComparisonPeriod | None = None,
    ) -> KPIValue:
        """Calculate a KPI value.
        
        Args:
            kpi_id: The KPI to calculate.
            variables: Variable values for the formula.
            period_start: Start of period.
            period_end: End of period.
            compare_with: Comparison period type.
        
        Returns:
            Calculated KPI value.
        """
        kpi = self.kpis.get(kpi_id)
        if not kpi:
            raise ValueError(f"KPI not found: {kpi_id}")
        
        period_end = period_end or datetime.now()
        period_start = period_start or (period_end - timedelta(days=30))
        
        # Gather variables
        all_variables = variables or {}
        
        # Add from registered providers
        for name, provider in self._variable_providers.items():
            if name not in all_variables:
                try:
                    all_variables[name] = provider()
                except Exception:
                    pass
        
        # Calculate current value
        value = self._evaluate_formula(kpi.formula, all_variables)
        
        # Format value
        try:
            fmt = kpi.display_format.replace("{value", "{0")
            formatted_value = fmt.format(float(value))
        except (ValueError, KeyError):
            formatted_value = f"{value:.{kpi.decimals}f}{kpi.unit}"
        
        # Determine status
        status = "normal"
        if kpi.critical_threshold is not None:
            if kpi.higher_is_better:
                if value <= kpi.critical_threshold:
                    status = "critical"
                elif kpi.warning_threshold and value <= kpi.warning_threshold:
                    status = "warning"
            else:
                if value >= kpi.critical_threshold:
                    status = "critical"
                elif kpi.warning_threshold and value >= kpi.warning_threshold:
                    status = "warning"
        
        # Calculate comparison if requested
        comparison_value = None
        change_value = None
        change_percent = None
        
        if compare_with:
            comparison_value = self._get_comparison_value(
                kpi_id,
                period_start,
                period_end,
                compare_with,
            )
            if comparison_value is not None and comparison_value != 0:
                change_value = value - comparison_value
                change_percent = float((change_value / comparison_value) * 100)
        
        # Calculate goal progress
        goal_status = None
        goal_progress_pct = None
        
        if kpi.goal_value is not None:
            goal_progress_pct = float((value / kpi.goal_value) * 100)
            
            if goal_progress_pct >= 100:
                goal_status = GoalStatus.ACHIEVED
            elif goal_progress_pct >= 80:
                goal_status = GoalStatus.ON_TRACK
            elif goal_progress_pct >= 50:
                goal_status = GoalStatus.AT_RISK
            else:
                goal_status = GoalStatus.BEHIND
        
        # Determine trend
        trend = self._calculate_trend(kpi_id, value)
        
        # Store for history
        self._record_value(kpi_id, value)
        
        return KPIValue(
            kpi_id=kpi_id,
            kpi_name=kpi.name,
            value=value,
            formatted_value=formatted_value,
            unit=kpi.unit,
            period_start=period_start,
            period_end=period_end,
            comparison_value=comparison_value,
            comparison_period=compare_with.value if compare_with else None,
            change_value=change_value,
            change_percent=change_percent,
            status=status,
            goal_status=goal_status,
            goal_progress_pct=goal_progress_pct,
            trend=trend,
        )

    def _record_value(self, kpi_id: str, value: Decimal) -> None:
        """Record a KPI value for trend analysis."""
        if kpi_id not in self._historical_values:
            self._historical_values[kpi_id] = []
        
        self._historical_values[kpi_id].append((datetime.now(), value))
        
        # Keep only last 90 days
        cutoff = datetime.now() - timedelta(days=90)
        self._historical_values[kpi_id] = [
            (ts, v) for ts, v in self._historical_values[kpi_id]
            if ts > cutoff
        ]

    def _get_comparison_value(
        self,
        kpi_id: str,
        period_start: datetime,
        period_end: datetime,
        comparison: ComparisonPeriod,
    ) -> Decimal | None:
        """Get comparison value for a KPI."""
        history = self._historical_values.get(kpi_id, [])
        if not history:
            return None
        
        if comparison == ComparisonPeriod.PREVIOUS_PERIOD:
            # Get value from equivalent previous period
            period_days = (period_end - period_start).days
            target_date = period_end - timedelta(days=period_days)
            
            # Find closest value
            closest = None
            closest_diff = float('inf')
            for ts, val in history:
                diff = abs((ts - target_date).total_seconds())
                if diff < closest_diff:
                    closest_diff = diff
                    closest = val
            return closest
        
        elif comparison == ComparisonPeriod.PREVIOUS_YEAR:
            target_date = period_end - timedelta(days=365)
            closest = None
            closest_diff = float('inf')
            for ts, val in history:
                diff = abs((ts - target_date).total_seconds())
                if diff < closest_diff:
                    closest_diff = diff
                    closest = val
            return closest
        
        elif comparison == ComparisonPeriod.MONTHLY_AVERAGE:
            if history:
                return sum(v for _, v in history) / len(history)
        
        return None

    def _calculate_trend(self, kpi_id: str, current_value: Decimal) -> str | None:
        """Calculate trend direction."""
        history = self._historical_values.get(kpi_id, [])
        if len(history) < 3:
            return None
        
        # Get values from last 7 days
        cutoff = datetime.now() - timedelta(days=7)
        recent = [v for ts, v in history if ts > cutoff]
        
        if len(recent) < 2:
            return None
        
        # Simple trend: compare current to average of recent
        avg = sum(recent) / len(recent)
        
        if current_value > avg * Decimal("1.05"):
            return "up"
        elif current_value < avg * Decimal("0.95"):
            return "down"
        else:
            return "flat"

    def create_dashboard(self, dashboard: KPIDashboard) -> None:
        """Create a new dashboard."""
        self.dashboards[dashboard.id] = dashboard

    def get_dashboard_values(
        self,
        dashboard_id: str,
        variables: dict[str, Any] | None = None,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
    ) -> list[KPIValue]:
        """Calculate all KPIs for a dashboard.
        
        Args:
            dashboard_id: Dashboard to calculate.
            variables: Variable values.
            period_start: Start of period.
            period_end: End of period.
        
        Returns:
            List of KPI values.
        """
        dashboard = self.dashboards.get(dashboard_id)
        if not dashboard:
            raise ValueError(f"Dashboard not found: {dashboard_id}")
        
        values = []
        for kpi_id in dashboard.kpi_ids:
            try:
                value = self.calculate_kpi(
                    kpi_id,
                    variables=variables,
                    period_start=period_start,
                    period_end=period_end,
                )
                values.append(value)
            except Exception:
                # Skip KPIs that fail to calculate
                pass
        
        return values

    def set_goal(
        self,
        kpi_id: str,
        target_value: Decimal,
        period_type: str,
        start_date: datetime,
        end_date: datetime,
    ) -> KPIGoal:
        """Set a goal for a KPI.
        
        Args:
            kpi_id: The KPI.
            target_value: Goal target.
            period_type: monthly, quarterly, yearly.
            start_date: Goal period start.
            end_date: Goal period end.
        
        Returns:
            The created goal.
        """
        goal_id = f"goal_{kpi_id}_{start_date.year}_{start_date.month}"
        
        goal = KPIGoal(
            id=goal_id,
            kpi_id=kpi_id,
            target_value=target_value,
            period_type=period_type,
            start_date=start_date,
            end_date=end_date,
        )
        
        self.goals[goal_id] = goal
        return goal

    def update_goal_progress(
        self,
        goal_id: str,
        current_value: Decimal,
    ) -> KPIGoal | None:
        """Update progress toward a goal."""
        goal = self.goals.get(goal_id)
        if not goal:
            return None
        
        goal.current_value = current_value
        goal.last_updated = datetime.now()
        
        if goal.target_value > 0:
            goal.progress_pct = float((current_value / goal.target_value) * 100)
        
        # Update status
        now = datetime.now()
        time_elapsed_pct = (
            (now - goal.start_date).days /
            (goal.end_date - goal.start_date).days * 100
        )
        
        if goal.progress_pct >= 100:
            goal.status = GoalStatus.ACHIEVED
        elif goal.progress_pct >= time_elapsed_pct * 0.9:
            goal.status = GoalStatus.ON_TRACK
        elif goal.progress_pct >= time_elapsed_pct * 0.7:
            goal.status = GoalStatus.AT_RISK
        else:
            goal.status = GoalStatus.BEHIND
        
        return goal

    def get_standard_kpis(self) -> list[KPIDefinition]:
        """Get standard KPI definitions for common metrics."""
        return [
            KPIDefinition(
                id="gross_margin",
                name="Gross Margin",
                description="Gross profit as percentage of revenue",
                category=KPICategory.FINANCIAL,
                formula="(revenue - cogs) / revenue * 100",
                unit="%",
                display_format="{value:.1f}%",
                higher_is_better=True,
                warning_threshold=Decimal("25"),
                critical_threshold=Decimal("15"),
            ),
            KPIDefinition(
                id="net_margin",
                name="Net Profit Margin",
                description="Net profit as percentage of revenue",
                category=KPICategory.FINANCIAL,
                formula="net_profit / revenue * 100",
                unit="%",
                display_format="{value:.1f}%",
                higher_is_better=True,
            ),
            KPIDefinition(
                id="current_ratio",
                name="Current Ratio",
                description="Current assets / Current liabilities",
                category=KPICategory.FINANCIAL,
                formula="current_assets / current_liabilities",
                unit="",
                display_format="{value:.2f}",
                higher_is_better=True,
                warning_threshold=Decimal("1.5"),
                critical_threshold=Decimal("1.0"),
            ),
            KPIDefinition(
                id="quick_ratio",
                name="Quick Ratio",
                description="(Current assets - Inventory) / Current liabilities",
                category=KPICategory.FINANCIAL,
                formula="(current_assets - inventory) / current_liabilities",
                unit="",
                display_format="{value:.2f}",
                higher_is_better=True,
            ),
            KPIDefinition(
                id="days_sales_outstanding",
                name="Days Sales Outstanding",
                description="Average collection period for receivables",
                category=KPICategory.OPERATIONAL,
                formula="accounts_receivable / daily_sales",
                unit=" days",
                display_format="{value:.0f} days",
                higher_is_better=False,
            ),
            KPIDefinition(
                id="inventory_turnover",
                name="Inventory Turnover",
                description="How many times inventory is sold per year",
                category=KPICategory.OPERATIONAL,
                formula="cogs / average_inventory",
                unit="x",
                display_format="{value:.1f}x",
                higher_is_better=True,
            ),
            KPIDefinition(
                id="revenue_growth",
                name="Revenue Growth",
                description="Year-over-year revenue growth",
                category=KPICategory.FINANCIAL,
                formula="(current_revenue - previous_revenue) / previous_revenue * 100",
                unit="%",
                display_format="{value:+.1f}%",
                higher_is_better=True,
            ),
            KPIDefinition(
                id="operating_expense_ratio",
                name="Operating Expense Ratio",
                description="Operating expenses as % of revenue",
                category=KPICategory.FINANCIAL,
                formula="operating_expenses / revenue * 100",
                unit="%",
                display_format="{value:.1f}%",
                higher_is_better=False,
            ),
        ]
