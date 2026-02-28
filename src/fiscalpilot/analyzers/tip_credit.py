"""
Tip Tax Credit Calculator — calculate FICA tip credit (Section 45B) savings.

Most restaurant owners don't know they can claim tax credits on the employer portion
of FICA taxes paid on employee tips. This is essentially "free money" that many miss.

Section 45B Credit:
- Employers can claim a credit for FICA taxes paid on tips EXCEEDING the amount needed
  to bring wages to minimum wage.
- Credit = 7.65% (Social Security + Medicare) × qualifying tips

Example:
- Employee paid $5.15/hr + $15/hr tips = $20.15/hr total
- Federal tipped minimum = $7.25/hr
- Tips counted toward wage: $7.25 - $5.15 = $2.10/hr
- Qualifying tips for credit: $15.00 - $2.10 = $12.90/hr
- Credit per hour: $12.90 × 7.65% = $0.99/hr
- For 2000 hours/year: ~$1,980 credit per employee!
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("fiscalpilot.analyzers.tip_credit")


# 2024 rates (update annually)
FICA_RATE = 0.0765  # 6.2% SS + 1.45% Medicare
FEDERAL_MINIMUM_WAGE = 7.25
FEDERAL_TIPPED_MINIMUM = 2.13  # Federal minimum for tipped employees


@dataclass
class TippedEmployee:
    """Data for a single tipped employee."""
    name: str = ""
    hourly_wage: float = 0.0  # Cash wage paid (before tips)
    hours_worked: float = 0.0  # Hours in the period (month/year)
    tips_received: float = 0.0  # Total tips received

    @property
    def tips_per_hour(self) -> float:
        """Average tips per hour."""
        if self.hours_worked > 0:
            return self.tips_received / self.hours_worked
        return 0.0

    @property
    def total_hourly_compensation(self) -> float:
        """Total hourly compensation including tips."""
        return self.hourly_wage + self.tips_per_hour


@dataclass
class EmployeeTipCreditResult:
    """Tip credit calculation for a single employee."""
    employee_name: str = ""
    hours_worked: float = 0.0
    hourly_wage: float = 0.0
    tips_received: float = 0.0
    tips_per_hour: float = 0.0

    # Calculation breakdown
    minimum_wage_used: float = FEDERAL_MINIMUM_WAGE
    tip_credit_taken: float = 0.0  # Portion of tips counting toward min wage
    qualifying_tips: float = 0.0  # Tips eligible for FICA credit
    fica_credit_amount: float = 0.0  # Actual credit earned

    # Annualized projection
    annualized_credit: float = 0.0


@dataclass
class TipCreditResult:
    """Complete tip credit analysis results."""

    # Summary totals
    total_tipped_employees: int = 0
    total_hours_worked: float = 0.0
    total_tips_reported: float = 0.0
    total_qualifying_tips: float = 0.0
    total_fica_credit: float = 0.0

    # Annualized projections
    annual_credit_projection: float = 0.0

    # Per-employee breakdown
    employee_details: list[EmployeeTipCreditResult] = field(default_factory=list)

    # Parameters used
    minimum_wage_used: float = FEDERAL_MINIMUM_WAGE
    fica_rate_used: float = FICA_RATE

    # Insights
    insights: list[str] = field(default_factory=list)

    # Compliance notes
    compliance_notes: list[str] = field(default_factory=list)

    # Period
    period_type: str = "month"  # month, quarter, year


@dataclass
class StateMinimumWage:
    """State-specific minimum wage information."""
    state: str
    tipped_minimum: float
    regular_minimum: float
    tip_credit_allowed: bool = True  # Some states don't allow tip credit


# Key state minimum wages (2024) - major restaurant states
STATE_MINIMUM_WAGES: dict[str, StateMinimumWage] = {
    "CA": StateMinimumWage("California", 16.00, 16.00, False),  # No tip credit in CA
    "NY": StateMinimumWage("New York", 15.00, 15.00, False),  # NYC - no tip credit
    "TX": StateMinimumWage("Texas", 2.13, 7.25, True),
    "FL": StateMinimumWage("Florida", 8.98, 13.00, True),
    "IL": StateMinimumWage("Illinois", 7.80, 14.00, True),
    "PA": StateMinimumWage("Pennsylvania", 2.83, 7.25, True),
    "OH": StateMinimumWage("Ohio", 5.05, 10.45, True),
    "GA": StateMinimumWage("Georgia", 2.13, 7.25, True),
    "NC": StateMinimumWage("North Carolina", 2.13, 7.25, True),
    "NJ": StateMinimumWage("New Jersey", 5.26, 15.13, True),
    "VA": StateMinimumWage("Virginia", 2.13, 12.00, True),
    "AZ": StateMinimumWage("Arizona", 11.35, 14.35, True),
    "WA": StateMinimumWage("Washington", 16.28, 16.28, False),  # No tip credit in WA
    "MA": StateMinimumWage("Massachusetts", 6.75, 15.00, True),
    "CO": StateMinimumWage("Colorado", 11.40, 14.42, True),
    "MN": StateMinimumWage("Minnesota", 10.85, 10.85, False),  # No tip credit
    "NV": StateMinimumWage("Nevada", 11.25, 12.00, True),
}


class TipCreditCalculator:
    """Calculate FICA tip credit (Section 45B) for restaurants."""

    @classmethod
    def calculate(
        cls,
        employees: list[TippedEmployee],
        *,
        state: str | None = None,
        custom_minimum_wage: float | None = None,
        period_type: str = "month",  # month, quarter, year
    ) -> TipCreditResult:
        """
        Calculate tip credit for all tipped employees.

        Args:
            employees: List of tipped employee data.
            state: Two-letter state code for state-specific minimum wage.
            custom_minimum_wage: Override minimum wage (e.g., for local minimums).
            period_type: Period of the data (month, quarter, year).

        Returns:
            TipCreditResult with credit calculations and insights.
        """
        # Determine minimum wage to use
        min_wage = cls._get_minimum_wage(state, custom_minimum_wage)
        tip_credit_allowed = cls._is_tip_credit_allowed(state)

        # Calculate for each employee
        employee_results: list[EmployeeTipCreditResult] = []
        total_hours = 0.0
        total_tips = 0.0
        total_qualifying = 0.0
        total_credit = 0.0

        for emp in employees:
            result = cls._calculate_employee_credit(emp, min_wage)
            employee_results.append(result)

            total_hours += result.hours_worked
            total_tips += result.tips_received
            total_qualifying += result.qualifying_tips
            total_credit += result.fica_credit_amount

        # Calculate annualization factor
        if period_type == "month":
            annual_factor = 12
        elif period_type == "quarter":
            annual_factor = 4
        else:
            annual_factor = 1

        annual_projection = total_credit * annual_factor

        # Generate insights
        insights = cls._generate_insights(
            total_credit=total_credit,
            annual_projection=annual_projection,
            total_tips=total_tips,
            total_qualifying=total_qualifying,
            tip_credit_allowed=tip_credit_allowed,
            state=state,
            employee_count=len(employees),
        )

        # Compliance notes
        compliance = cls._get_compliance_notes()

        return TipCreditResult(
            total_tipped_employees=len(employees),
            total_hours_worked=total_hours,
            total_tips_reported=total_tips,
            total_qualifying_tips=total_qualifying,
            total_fica_credit=total_credit,
            annual_credit_projection=annual_projection,
            employee_details=employee_results,
            minimum_wage_used=min_wage,
            fica_rate_used=FICA_RATE,
            insights=insights,
            compliance_notes=compliance,
            period_type=period_type,
        )

    @classmethod
    def quick_estimate(
        cls,
        *,
        num_tipped_employees: int,
        avg_hours_per_employee: float = 30.0,  # Per week
        avg_tips_per_hour: float = 15.0,
        avg_cash_wage: float = 2.13,
        state: str | None = None,
    ) -> TipCreditResult:
        """
        Quick estimate of annual tip credit without detailed employee data.

        Useful for "napkin math" when you don't have detailed payroll.

        Args:
            num_tipped_employees: Number of tipped employees.
            avg_hours_per_employee: Average hours per employee per WEEK.
            avg_tips_per_hour: Average tips per hour across all tipped staff.
            avg_cash_wage: Average cash wage paid (before tips).
            state: Two-letter state code.

        Returns:
            TipCreditResult with annual estimate.
        """
        # Convert to monthly
        weekly_hours = avg_hours_per_employee
        monthly_hours = weekly_hours * 4.33
        monthly_tips = monthly_hours * avg_tips_per_hour

        # Create synthetic employees
        employees = [
            TippedEmployee(
                name=f"Employee {i+1}",
                hourly_wage=avg_cash_wage,
                hours_worked=monthly_hours,
                tips_received=monthly_tips,
            )
            for i in range(num_tipped_employees)
        ]

        return cls.calculate(employees, state=state, period_type="month")

    @classmethod
    def _calculate_employee_credit(
        cls,
        employee: TippedEmployee,
        minimum_wage: float,
    ) -> EmployeeTipCreditResult:
        """Calculate credit for a single employee."""
        # Tips per hour
        tips_per_hour = employee.tips_per_hour

        # How much of tips are used to meet minimum wage?
        # tip_credit_taken = min_wage - cash_wage (but can't exceed tips_per_hour)
        wage_deficit = max(0, minimum_wage - employee.hourly_wage)
        tip_credit_taken = min(wage_deficit, tips_per_hour)

        # Qualifying tips = tips above what's used for minimum wage
        qualifying_tips_per_hour = max(0, tips_per_hour - tip_credit_taken)
        qualifying_tips_total = qualifying_tips_per_hour * employee.hours_worked

        # FICA credit = 7.65% of qualifying tips
        fica_credit = qualifying_tips_total * FICA_RATE

        # Annualize (assume monthly data by default)
        annualized = fica_credit * 12

        return EmployeeTipCreditResult(
            employee_name=employee.name,
            hours_worked=employee.hours_worked,
            hourly_wage=employee.hourly_wage,
            tips_received=employee.tips_received,
            tips_per_hour=tips_per_hour,
            minimum_wage_used=minimum_wage,
            tip_credit_taken=tip_credit_taken * employee.hours_worked,
            qualifying_tips=qualifying_tips_total,
            fica_credit_amount=fica_credit,
            annualized_credit=annualized,
        )

    @classmethod
    def _get_minimum_wage(
        cls,
        state: str | None,
        custom: float | None,
    ) -> float:
        """Get the applicable minimum wage."""
        if custom is not None:
            return custom
        if state and state.upper() in STATE_MINIMUM_WAGES:
            return STATE_MINIMUM_WAGES[state.upper()].regular_minimum
        return FEDERAL_MINIMUM_WAGE

    @classmethod
    def _is_tip_credit_allowed(cls, state: str | None) -> bool:
        """Check if state allows tip credit toward minimum wage."""
        if state and state.upper() in STATE_MINIMUM_WAGES:
            return STATE_MINIMUM_WAGES[state.upper()].tip_credit_allowed
        return True  # Default federal rules allow it

    @classmethod
    def _generate_insights(
        cls,
        total_credit: float,
        annual_projection: float,
        total_tips: float,
        total_qualifying: float,
        tip_credit_allowed: bool,
        state: str | None,
        employee_count: int,
    ) -> list[str]:
        """Generate insights about tip credit opportunity."""
        insights = []

        # Main credit insight
        if annual_projection > 0:
            insights.append(
                f"💰 ANNUAL TIP CREDIT: Estimated ${annual_projection:,.0f}/year in FICA tip credits. "
                "This is a dollar-for-dollar reduction in taxes owed."
            )

            per_employee = annual_projection / employee_count if employee_count > 0 else 0
            insights.append(
                f"📊 Per tipped employee: ~${per_employee:,.0f}/year average credit."
            )

        # State-specific notes
        if state:
            state_upper = state.upper()
            if state_upper in STATE_MINIMUM_WAGES:
                state_info = STATE_MINIMUM_WAGES[state_upper]
                if not state_info.tip_credit_allowed:
                    insights.append(
                        f"⚠️ {state_info.state}: State does not allow tip credit toward minimum wage. "
                        "You must pay full minimum wage, but this maximizes your FICA credit."
                    )

        # Optimization suggestions
        if total_qualifying > 0:
            (total_credit / total_qualifying) * 100 if total_qualifying > 0 else 0
            insights.append(
                f"📈 Qualifying tips: ${total_qualifying:,.0f} of ${total_tips:,.0f} total tips qualify "
                f"for the {FICA_RATE*100:.2f}% FICA credit."
            )

        # Call to action
        insights.append(
            "✅ ACTION: File Form 8846 with your tax return to claim this credit. "
            "Consult a CPA to ensure proper documentation."
        )

        return insights

    @classmethod
    def _get_compliance_notes(cls) -> list[str]:
        """Get compliance and documentation notes."""
        return [
            "📋 FORM 8846: Use IRS Form 8846 to claim the Credit for Employer Social Security "
            "and Medicare Taxes Paid on Certain Employee Tips.",

            "📝 DOCUMENTATION: Maintain records of tip reports (Form 4070) or equivalent POS "
            "tip tracking for all employees.",

            "⚠️ FOOD & BEVERAGE ONLY: Credit only applies to tips from food or beverage "
            "establishments where tipping is customary.",

            "🔄 ANNUAL CLAIM: Credit is claimed annually on your business tax return. "
            "Cannot be claimed on payroll tax deposits.",

            "💡 NO DOUBLE DIP: Tips credited against minimum wage don't reduce the FICA "
            "credit calculation - calculation is based on ALL tips above min wage threshold.",
        ]


def calculate_tip_credit(
    employees: list[TippedEmployee],
    **kwargs: Any,
) -> TipCreditResult:
    """Convenience function for tip credit calculation.

    See TipCreditCalculator.calculate() for full parameter documentation.
    """
    return TipCreditCalculator.calculate(employees, **kwargs)


def quick_tip_credit_estimate(**kwargs: Any) -> TipCreditResult:
    """Convenience function for quick tip credit estimate.

    See TipCreditCalculator.quick_estimate() for full parameter documentation.
    """
    return TipCreditCalculator.quick_estimate(**kwargs)
