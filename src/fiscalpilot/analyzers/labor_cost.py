"""
Labor Cost Analyzer — analyze payroll, scheduling, and labor efficiency.

Provides:
- Labor cost percentage analysis
- Sales per labor hour (SPLH)
- Overtime tracking and alerts
- Schedule optimization recommendations
- Tip credit compliance
- Labor law compliance checks
- Shift productivity analysis
- Forecasting labor needs
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any


class EmployeeType(str, Enum):
    """Types of employees."""
    
    HOURLY = "hourly"
    SALARIED = "salaried"
    TIPPED = "tipped"
    CONTRACTOR = "contractor"


class ShiftType(str, Enum):
    """Types of shifts."""
    
    OPENING = "opening"
    MID = "mid"
    CLOSING = "closing"
    SPLIT = "split"
    ON_CALL = "on_call"


@dataclass
class Employee:
    """Employee information."""
    
    id: str
    name: str
    position: str
    department: str
    employee_type: EmployeeType
    hourly_rate: Decimal
    hire_date: date
    
    # For tipped employees
    tipped: bool = False
    tip_credit_rate: Decimal | None = None  # Rate when tip credit applied
    
    # For overtime calculations
    overtime_exempt: bool = False
    weekly_hours_threshold: Decimal = Decimal("40")
    daily_hours_threshold: Decimal | None = None  # Some states have daily OT
    
    # Benefits/burden
    benefit_rate_pct: float = 0.0  # Benefits as % of wages
    
    @property
    def fully_loaded_rate(self) -> Decimal:
        """Hourly rate including benefits burden."""
        burden = Decimal(str(1 + self.benefit_rate_pct / 100))
        return self.hourly_rate * burden


@dataclass
class Shift:
    """A scheduled or worked shift."""
    
    id: str
    employee_id: str
    date: date
    start_time: time
    end_time: time
    break_minutes: int = 0
    shift_type: ShiftType = ShiftType.MID
    department: str | None = None
    position: str | None = None
    
    # Actuals (vs scheduled)
    actual_start: time | None = None
    actual_end: time | None = None
    actual_break_minutes: int | None = None
    
    # Tips
    tips_earned: Decimal = Decimal("0")
    
    @property
    def scheduled_hours(self) -> Decimal:
        """Scheduled hours for this shift."""
        start = datetime.combine(self.date, self.start_time)
        end = datetime.combine(self.date, self.end_time)
        
        # Handle overnight shifts
        if end < start:
            end += timedelta(days=1)
        
        total_minutes = (end - start).total_seconds() / 60
        net_minutes = total_minutes - self.break_minutes
        return Decimal(str(net_minutes / 60))
    
    @property
    def actual_hours(self) -> Decimal | None:
        """Actual worked hours if available."""
        if not self.actual_start or not self.actual_end:
            return None
        
        start = datetime.combine(self.date, self.actual_start)
        end = datetime.combine(self.date, self.actual_end)
        
        if end < start:
            end += timedelta(days=1)
        
        breaks = self.actual_break_minutes if self.actual_break_minutes else self.break_minutes
        total_minutes = (end - start).total_seconds() / 60
        net_minutes = total_minutes - breaks
        return Decimal(str(net_minutes / 60))
    
    @property
    def hours(self) -> Decimal:
        """Worked hours (actual if available, else scheduled)."""
        return self.actual_hours or self.scheduled_hours


@dataclass  
class DayPartMetrics:
    """Metrics for a daypart (breakfast, lunch, dinner, etc)."""
    
    daypart: str
    start_time: time
    end_time: time
    total_hours: Decimal
    labor_cost: Decimal
    sales: Decimal
    guest_count: int
    
    @property
    def splh(self) -> Decimal:
        """Sales per labor hour."""
        if self.total_hours <= 0:
            return Decimal("0")
        return self.sales / self.total_hours
    
    @property
    def labor_cost_pct(self) -> float:
        """Labor cost as percentage of sales."""
        if self.sales <= 0:
            return 0.0
        return float(self.labor_cost / self.sales * 100)
    
    @property
    def guests_per_labor_hour(self) -> float:
        """Guests served per labor hour."""
        if self.total_hours <= 0:
            return 0.0
        return float(Decimal(str(self.guest_count)) / self.total_hours)


@dataclass
class LaborAnalysisResult:
    """Result of labor cost analysis for a period."""
    
    start_date: date
    end_date: date
    
    # Hours
    total_scheduled_hours: Decimal
    total_actual_hours: Decimal
    regular_hours: Decimal
    overtime_hours: Decimal
    
    # Costs
    regular_wages: Decimal
    overtime_wages: Decimal
    total_wages: Decimal
    total_tips: Decimal
    benefit_costs: Decimal
    total_labor_cost: Decimal
    
    # Efficiency
    sales: Decimal
    labor_cost_pct: float
    splh: Decimal
    target_labor_pct: float
    
    # By category
    by_department: dict[str, dict[str, Any]] = field(default_factory=dict)
    by_position: dict[str, dict[str, Any]] = field(default_factory=dict)
    by_daypart: list[DayPartMetrics] = field(default_factory=list)
    
    @property
    def overtime_percentage(self) -> float:
        """Overtime hours as percentage of total."""
        if self.total_actual_hours <= 0:
            return 0.0
        return float(self.overtime_hours / self.total_actual_hours * 100)
    
    @property
    def variance_from_target(self) -> float:
        """Variance from target labor percentage."""
        return self.labor_cost_pct - self.target_labor_pct
    
    @property
    def is_over_target(self) -> bool:
        """Whether labor cost exceeds target."""
        return self.labor_cost_pct > self.target_labor_pct
    
    @property
    def variance_dollars(self) -> Decimal:
        """Dollar variance from target."""
        target_cost = self.sales * Decimal(str(self.target_labor_pct / 100))
        return self.total_labor_cost - target_cost


@dataclass
class OvertimeAlert:
    """Alert for overtime situation."""
    
    employee_id: str
    employee_name: str
    week_start: date
    hours_worked: Decimal
    hours_threshold: Decimal
    overtime_hours: Decimal
    overtime_cost: Decimal
    projected_weekly_hours: Decimal | None = None


@dataclass
class ScheduleOptimization:
    """Recommendation for schedule optimization."""
    
    recommendation: str
    category: str  # understaffed, overstaffed, overtime_risk, etc.
    impact_hours: Decimal
    impact_dollars: Decimal
    affected_shifts: list[str]
    priority: str  # high, medium, low


class LaborCostAnalyzer:
    """Analyze labor costs and optimize scheduling.

    Usage::

        analyzer = LaborCostAnalyzer(target_labor_pct=25.0)
        
        # Add employees
        emp = Employee(
            id="1",
            name="John Smith",
            position="Server",
            department="FOH",
            employee_type=EmployeeType.TIPPED,
            hourly_rate=Decimal("2.13"),
            hire_date=date(2023, 1, 1),
            tipped=True,
        )
        analyzer.add_employee(emp)
        
        # Add shifts
        shift = Shift(
            id="s1",
            employee_id="1",
            date=date(2024, 1, 15),
            start_time=time(11, 0),
            end_time=time(19, 0),
            break_minutes=30,
        )
        analyzer.add_shift(shift)
        
        # Analyze
        result = analyzer.analyze_period(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            sales=Decimal("100000"),
        )
    """

    def __init__(
        self,
        target_labor_pct: float = 25.0,
        overtime_multiplier: Decimal = Decimal("1.5"),
        default_benefit_rate: float = 0.0,
    ) -> None:
        self.target_labor_pct = target_labor_pct
        self.overtime_multiplier = overtime_multiplier
        self.default_benefit_rate = default_benefit_rate
        
        self.employees: dict[str, Employee] = {}
        self.shifts: list[Shift] = []
        
        # Daypart definitions (can be customized)
        self.dayparts = [
            ("breakfast", time(6, 0), time(11, 0)),
            ("lunch", time(11, 0), time(15, 0)),
            ("afternoon", time(15, 0), time(17, 0)),
            ("dinner", time(17, 0), time(22, 0)),
            ("late_night", time(22, 0), time(2, 0)),
        ]

    def add_employee(self, employee: Employee) -> None:
        """Add or update an employee."""
        if employee.benefit_rate_pct == 0.0:
            employee.benefit_rate_pct = self.default_benefit_rate
        self.employees[employee.id] = employee

    def get_employee(self, employee_id: str) -> Employee | None:
        """Get an employee by ID."""
        return self.employees.get(employee_id)

    def add_shift(self, shift: Shift) -> None:
        """Add a shift."""
        self.shifts.append(shift)

    def add_shifts(self, shifts: list[Shift]) -> None:
        """Add multiple shifts."""
        self.shifts.extend(shifts)

    def _get_shifts_in_period(
        self,
        start_date: date,
        end_date: date,
    ) -> list[Shift]:
        """Get shifts within a date range."""
        return [
            s for s in self.shifts
            if start_date <= s.date <= end_date
        ]

    def _calculate_weekly_hours(
        self,
        employee_id: str,
        week_start: date,
    ) -> tuple[Decimal, Decimal]:
        """Calculate regular and overtime hours for a week.
        
        Returns (regular_hours, overtime_hours).
        """
        employee = self.employees.get(employee_id)
        if not employee or employee.overtime_exempt:
            # Return all hours as regular for exempt employees
            week_end = week_start + timedelta(days=6)
            total = sum(
                s.hours for s in self.shifts
                if s.employee_id == employee_id and week_start <= s.date <= week_end
            )
            return (total, Decimal("0"))
        
        week_end = week_start + timedelta(days=6)
        week_shifts = [
            s for s in self.shifts
            if s.employee_id == employee_id and week_start <= s.date <= week_end
        ]
        
        total_hours = sum(s.hours for s in week_shifts)
        threshold = employee.weekly_hours_threshold
        
        if total_hours <= threshold:
            return (total_hours, Decimal("0"))
        
        return (threshold, total_hours - threshold)

    def _calculate_shift_cost(
        self,
        shift: Shift,
        is_overtime: bool = False,
    ) -> Decimal:
        """Calculate cost for a shift."""
        employee = self.employees.get(shift.employee_id)
        if not employee:
            return Decimal("0")
        
        rate = employee.fully_loaded_rate
        if is_overtime and not employee.overtime_exempt:
            rate = rate * self.overtime_multiplier
        
        return shift.hours * rate

    def analyze_period(
        self,
        start_date: date,
        end_date: date,
        sales: Decimal,
        guest_count: int = 0,
        sales_by_daypart: dict[str, Decimal] | None = None,
    ) -> LaborAnalysisResult:
        """Analyze labor costs for a period.
        
        Args:
            start_date: Start of analysis period.
            end_date: End of analysis period.
            sales: Total sales for the period.
            guest_count: Total guests served.
            sales_by_daypart: Optional sales breakdown by daypart.
        
        Returns:
            LaborAnalysisResult with comprehensive analysis.
        """
        period_shifts = self._get_shifts_in_period(start_date, end_date)
        
        # Calculate hours and costs
        total_scheduled = Decimal("0")
        total_actual = Decimal("0")
        total_regular = Decimal("0")
        total_overtime = Decimal("0")
        regular_wages = Decimal("0")
        overtime_wages = Decimal("0")
        total_tips = Decimal("0")
        benefit_costs = Decimal("0")
        
        by_department: dict[str, dict] = {}
        by_position: dict[str, dict] = {}
        
        # Process by week for overtime calculations
        current_date = start_date
        while current_date <= end_date:
            # Find week start (Monday)
            week_start = current_date - timedelta(days=current_date.weekday())
            week_end = week_start + timedelta(days=6)
            
            for emp_id in self.employees:
                reg_hours, ot_hours = self._calculate_weekly_hours(emp_id, week_start)
                
                # Get employee's shifts this week within our period
                emp_week_shifts = [
                    s for s in period_shifts
                    if s.employee_id == emp_id and week_start <= s.date <= week_end
                ]
                
                for shift in emp_week_shifts:
                    employee = self.employees[emp_id]
                    
                    total_scheduled += shift.scheduled_hours
                    total_actual += shift.hours
                    total_tips += shift.tips_earned
                    
                    # Allocate to regular or overtime
                    shift_hours = shift.hours
                    if ot_hours > 0:
                        # Some hours are overtime
                        ot_for_shift = min(ot_hours, shift_hours)
                        reg_for_shift = shift_hours - ot_for_shift
                        ot_hours -= ot_for_shift
                    else:
                        reg_for_shift = shift_hours
                        ot_for_shift = Decimal("0")
                    
                    total_regular += reg_for_shift
                    total_overtime += ot_for_shift
                    
                    reg_cost = reg_for_shift * employee.hourly_rate
                    ot_cost = ot_for_shift * employee.hourly_rate * self.overtime_multiplier
                    regular_wages += reg_cost
                    overtime_wages += ot_cost
                    
                    # Benefits
                    benefit_costs += (reg_cost + ot_cost) * Decimal(str(employee.benefit_rate_pct / 100))
                    
                    # By department
                    dept = shift.department or employee.department
                    if dept not in by_department:
                        by_department[dept] = {"hours": Decimal("0"), "cost": Decimal("0")}
                    by_department[dept]["hours"] += shift_hours
                    by_department[dept]["cost"] += reg_cost + ot_cost
                    
                    # By position
                    pos = shift.position or employee.position
                    if pos not in by_position:
                        by_position[pos] = {"hours": Decimal("0"), "cost": Decimal("0")}
                    by_position[pos]["hours"] += shift_hours
                    by_position[pos]["cost"] += reg_cost + ot_cost
            
            # Move to next week
            current_date = week_end + timedelta(days=1)
        
        total_wages = regular_wages + overtime_wages
        total_labor_cost = total_wages + benefit_costs
        
        labor_cost_pct = float(total_labor_cost / sales * 100) if sales > 0 else 0
        splh = sales / total_actual if total_actual > 0 else Decimal("0")
        
        # Analyze by daypart
        daypart_metrics = self._analyze_dayparts(
            period_shifts, sales_by_daypart or {}
        )
        
        return LaborAnalysisResult(
            start_date=start_date,
            end_date=end_date,
            total_scheduled_hours=total_scheduled,
            total_actual_hours=total_actual,
            regular_hours=total_regular,
            overtime_hours=total_overtime,
            regular_wages=regular_wages,
            overtime_wages=overtime_wages,
            total_wages=total_wages,
            total_tips=total_tips,
            benefit_costs=benefit_costs,
            total_labor_cost=total_labor_cost,
            sales=sales,
            labor_cost_pct=labor_cost_pct,
            splh=splh,
            target_labor_pct=self.target_labor_pct,
            by_department={
                k: {"hours": float(v["hours"]), "cost": float(v["cost"])}
                for k, v in by_department.items()
            },
            by_position={
                k: {"hours": float(v["hours"]), "cost": float(v["cost"])}
                for k, v in by_position.items()
            },
            by_daypart=daypart_metrics,
        )

    def _analyze_dayparts(
        self,
        shifts: list[Shift],
        sales_by_daypart: dict[str, Decimal],
    ) -> list[DayPartMetrics]:
        """Analyze labor by daypart."""
        metrics = []
        
        for name, start, end in self.dayparts:
            # Find shifts overlapping this daypart
            daypart_hours = Decimal("0")
            daypart_cost = Decimal("0")
            
            for shift in shifts:
                overlap = self._calculate_overlap(
                    shift.start_time, shift.end_time, start, end
                )
                if overlap > 0:
                    employee = self.employees.get(shift.employee_id)
                    if employee:
                        hours = Decimal(str(overlap / 60))  # Convert minutes to hours
                        daypart_hours += hours
                        daypart_cost += hours * employee.fully_loaded_rate
            
            sales = sales_by_daypart.get(name, Decimal("0"))
            
            metrics.append(DayPartMetrics(
                daypart=name,
                start_time=start,
                end_time=end,
                total_hours=daypart_hours,
                labor_cost=daypart_cost,
                sales=sales,
                guest_count=0,  # Would need guest data by daypart
            ))
        
        return metrics

    def _calculate_overlap(
        self,
        shift_start: time,
        shift_end: time,
        daypart_start: time,
        daypart_end: time,
    ) -> float:
        """Calculate overlap in minutes between shift and daypart."""
        # Convert to minutes since midnight
        def to_minutes(t: time) -> int:
            return t.hour * 60 + t.minute
        
        ss = to_minutes(shift_start)
        se = to_minutes(shift_end)
        ds = to_minutes(daypart_start)
        de = to_minutes(daypart_end)
        
        # Handle overnight
        if se < ss:
            se += 24 * 60
        if de < ds:
            de += 24 * 60
        
        # Calculate overlap
        overlap_start = max(ss, ds)
        overlap_end = min(se, de)
        
        return max(0, overlap_end - overlap_start)

    def get_overtime_alerts(
        self,
        week_start: date,
        projected_shifts: list[Shift] | None = None,
    ) -> list[OvertimeAlert]:
        """Get alerts for employees approaching or exceeding overtime.
        
        Args:
            week_start: Start of week to analyze.
            projected_shifts: Additional planned shifts to include.
        
        Returns:
            List of overtime alerts.
        """
        alerts = []
        all_shifts = self.shifts + (projected_shifts or [])
        week_end = week_start + timedelta(days=6)
        
        for emp_id, employee in self.employees.items():
            if employee.overtime_exempt:
                continue
            
            # Current hours
            current_hours = sum(
                s.hours for s in self.shifts
                if s.employee_id == emp_id and week_start <= s.date <= week_end
            )
            
            # Projected hours
            projected_hours = sum(
                s.scheduled_hours for s in (projected_shifts or [])
                if s.employee_id == emp_id and week_start <= s.date <= week_end
            )
            
            total_projected = current_hours + projected_hours
            threshold = employee.weekly_hours_threshold
            
            # Alert if at or over threshold
            if current_hours >= threshold or total_projected >= threshold:
                overtime = max(Decimal("0"), current_hours - threshold)
                overtime_cost = overtime * employee.hourly_rate * (self.overtime_multiplier - 1)
                
                alerts.append(OvertimeAlert(
                    employee_id=emp_id,
                    employee_name=employee.name,
                    week_start=week_start,
                    hours_worked=current_hours,
                    hours_threshold=threshold,
                    overtime_hours=overtime,
                    overtime_cost=overtime_cost,
                    projected_weekly_hours=total_projected if projected_hours > 0 else None,
                ))
        
        return sorted(alerts, key=lambda x: x.overtime_hours, reverse=True)

    def get_schedule_recommendations(
        self,
        target_date: date,
        expected_sales: Decimal,
    ) -> list[ScheduleOptimization]:
        """Get recommendations for schedule optimization.
        
        Args:
            target_date: Date to analyze/optimize.
            expected_sales: Expected sales for the day.
        
        Returns:
            List of optimization recommendations.
        """
        recommendations = []
        
        day_shifts = [s for s in self.shifts if s.date == target_date]
        
        # Calculate current labor cost and SPLH
        total_hours = sum(s.scheduled_hours for s in day_shifts)
        total_cost = Decimal("0")
        for shift in day_shifts:
            employee = self.employees.get(shift.employee_id)
            if employee:
                total_cost += shift.scheduled_hours * employee.fully_loaded_rate
        
        # Target labor cost
        target_cost = expected_sales * Decimal(str(self.target_labor_pct / 100))
        target_hours = target_cost / Decimal("15")  # Assume avg $15/hr
        
        # Variance
        hours_variance = total_hours - target_hours
        cost_variance = total_cost - target_cost
        
        if cost_variance > target_cost * Decimal("0.1"):
            # More than 10% over target
            recommendations.append(ScheduleOptimization(
                recommendation=f"Reduce scheduled hours by {float(hours_variance):.1f} hrs to hit target labor %",
                category="overstaffed",
                impact_hours=hours_variance,
                impact_dollars=cost_variance,
                affected_shifts=[s.id for s in day_shifts],
                priority="high",
            ))
        elif cost_variance < -target_cost * Decimal("0.1"):
            # More than 10% under target
            recommendations.append(ScheduleOptimization(
                recommendation=f"Add {float(-hours_variance):.1f} hrs for better coverage",
                category="understaffed",
                impact_hours=-hours_variance,
                impact_dollars=-cost_variance,
                affected_shifts=[],
                priority="medium",
            ))
        
        # Check for overtime risks
        # This is simplified - would need week context
        for shift in day_shifts:
            employee = self.employees.get(shift.employee_id)
            if employee and shift.scheduled_hours > Decimal("10"):
                recommendations.append(ScheduleOptimization(
                    recommendation=f"Long shift ({shift.scheduled_hours}h) for {employee.name} - consider splitting",
                    category="long_shift",
                    impact_hours=shift.scheduled_hours - Decimal("8"),
                    impact_dollars=Decimal("0"),
                    affected_shifts=[shift.id],
                    priority="low",
                ))
        
        return sorted(recommendations, key=lambda x: x.priority)

    def calculate_labor_forecast(
        self,
        target_date: date,
        expected_sales: Decimal,
        by_daypart: dict[str, Decimal] | None = None,
    ) -> dict[str, Any]:
        """Forecast labor needs based on expected sales.
        
        Returns recommended hours by position/daypart.
        """
        # Calculate target hours
        target_cost = expected_sales * Decimal(str(self.target_labor_pct / 100))
        
        # Get average wage from existing employees
        if self.employees:
            avg_wage = sum(e.fully_loaded_rate for e in self.employees.values()) / len(self.employees)
        else:
            avg_wage = Decimal("15")
        
        total_hours_needed = target_cost / avg_wage
        
        forecast = {
            "target_date": target_date.isoformat(),
            "expected_sales": float(expected_sales),
            "target_labor_cost": float(target_cost),
            "target_labor_pct": self.target_labor_pct,
            "total_hours_needed": float(total_hours_needed),
            "avg_wage_used": float(avg_wage),
        }
        
        # Break down by daypart if sales provided
        if by_daypart:
            daypart_hours = {}
            for daypart, sales in by_daypart.items():
                daypart_target = sales * Decimal(str(self.target_labor_pct / 100))
                daypart_hours[daypart] = {
                    "sales": float(sales),
                    "target_cost": float(daypart_target),
                    "hours_needed": float(daypart_target / avg_wage),
                }
            forecast["by_daypart"] = daypart_hours
        
        return forecast
