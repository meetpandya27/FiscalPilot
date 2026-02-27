"""
Tests for Tip Tax Credit Calculator — FICA 45B credit estimation.
"""

import pytest
from fiscalpilot.analyzers.tip_credit import (
    TipCreditCalculator,
    TipCreditResult,
    TippedEmployee,
    EmployeeTipCreditResult,
    FICA_RATE,
    FEDERAL_MINIMUM_WAGE,
    STATE_MINIMUM_WAGES,
)


class TestFICATipCreditCalculation:
    """Test core FICA tip credit calculations."""
    
    def test_basic_credit_calculation(self):
        """Calculate credit for employee paid above minimum wage in tips."""
        employees = [
            TippedEmployee(
                name="Server A",
                hourly_wage=2.13,
                hours_worked=160,  # Monthly
                tips_received=2400,  # $15/hr average
            )
        ]
        
        result = TipCreditCalculator.calculate(employees)
        
        # Tips per hour = 2400 / 160 = $15
        # Tip credit toward min wage = 7.25 - 2.13 = $5.12
        # Qualifying tips = 15 - 5.12 = $9.88/hr
        # Qualifying total = 9.88 * 160 = $1580.80
        # FICA credit = 1580.80 * 0.0765 = ~$120.89
        
        assert result.total_fica_credit > 0
        assert result.total_tipped_employees == 1
    
    def test_multiple_employees(self):
        """Calculate credit for multiple tipped employees."""
        employees = [
            TippedEmployee(name="Server A", hourly_wage=2.13, hours_worked=160, tips_received=2400),
            TippedEmployee(name="Server B", hourly_wage=2.13, hours_worked=120, tips_received=1800),
            TippedEmployee(name="Bartender", hourly_wage=2.13, hours_worked=180, tips_received=3600),
        ]
        
        result = TipCreditCalculator.calculate(employees)
        
        assert result.total_tipped_employees == 3
        assert len(result.employee_details) == 3
        assert result.total_fica_credit > 0
    
    def test_annualized_projection(self):
        """Should project annual credit from monthly data."""
        employees = [
            TippedEmployee(name="Server", hourly_wage=2.13, hours_worked=160, tips_received=2400),
        ]
        
        result = TipCreditCalculator.calculate(employees, period_type="month")
        
        # Annual projection should be monthly * 12
        monthly_credit = result.total_fica_credit
        expected_annual = monthly_credit * 12
        assert result.annual_credit_projection == pytest.approx(expected_annual, rel=0.01)


class TestTipCreditWithStateLaws:
    """Test state-specific minimum wage handling."""
    
    def test_texas_federal_rates(self):
        """Texas uses federal minimum wage and allows tip credit."""
        employees = [TippedEmployee(name="Server", hourly_wage=2.13, hours_worked=160, tips_received=2400)]
        
        result = TipCreditCalculator.calculate(employees, state="TX")
        
        assert result.minimum_wage_used == STATE_MINIMUM_WAGES["TX"].regular_minimum
        assert result.total_fica_credit > 0
    
    def test_california_no_tip_credit(self):
        """California doesn't allow tip credit toward minimum wage."""
        employees = [TippedEmployee(name="Server", hourly_wage=16.00, hours_worked=160, tips_received=2400)]
        
        result = TipCreditCalculator.calculate(employees, state="CA")
        
        # CA requires full minimum wage ($16), so ALL tips qualify for FICA credit
        # Since wage = min wage, tip credit toward wage = 0
        # All $2400 in tips should be qualifying
        assert result.minimum_wage_used == 16.00
    
    def test_new_york_high_minimum(self):
        """New York has high minimum wage."""
        employees = [TippedEmployee(name="Server", hourly_wage=15.00, hours_worked=160, tips_received=2400)]
        
        result = TipCreditCalculator.calculate(employees, state="NY")
        
        assert result.minimum_wage_used == STATE_MINIMUM_WAGES["NY"].regular_minimum


class TestQuickEstimate:
    """Test quick estimate functionality."""
    
    def test_quick_estimate_basic(self):
        """Quick estimate with minimal inputs."""
        result = TipCreditCalculator.quick_estimate(
            num_tipped_employees=10,
            avg_hours_per_employee=30,  # Per week
            avg_tips_per_hour=15,
            avg_cash_wage=2.13,
        )
        
        assert result.total_tipped_employees == 10
        assert result.annual_credit_projection > 0
    
    def test_quick_estimate_with_state(self):
        """Quick estimate with state override."""
        federal_result = TipCreditCalculator.quick_estimate(
            num_tipped_employees=10,
            avg_hours_per_employee=30,
            avg_tips_per_hour=15,
        )
        
        ca_result = TipCreditCalculator.quick_estimate(
            num_tipped_employees=10,
            avg_hours_per_employee=30,
            avg_tips_per_hour=15,
            state="CA",
        )
        
        # Both should have credits, but amounts may differ
        assert federal_result.annual_credit_projection > 0
        assert ca_result.annual_credit_projection > 0


class TestTipCreditInsights:
    """Test insight generation."""
    
    def test_annual_credit_insight(self):
        """Should generate insight about annual credit amount."""
        employees = [TippedEmployee(name="Server", hourly_wage=2.13, hours_worked=160, tips_received=2400)]
        
        result = TipCreditCalculator.calculate(employees)
        
        assert len(result.insights) > 0
        # Should mention dollar amount
        has_amount = any("$" in insight for insight in result.insights)
        assert has_amount
    
    def test_form_8846_mentioned(self):
        """Should mention IRS Form 8846 for claiming credit."""
        employees = [TippedEmployee(name="Server", hourly_wage=2.13, hours_worked=160, tips_received=2400)]
        
        result = TipCreditCalculator.calculate(employees)
        
        # Check either insights or compliance notes
        all_text = " ".join(result.insights + result.compliance_notes)
        assert "8846" in all_text or "form" in all_text.lower()


class TestComplianceNotes:
    """Test compliance information."""
    
    def test_compliance_notes_generated(self):
        """Should generate compliance notes."""
        employees = [TippedEmployee(name="Server", hourly_wage=2.13, hours_worked=160, tips_received=2400)]
        
        result = TipCreditCalculator.calculate(employees)
        
        assert len(result.compliance_notes) > 0
    
    def test_food_beverage_requirement_noted(self):
        """Should note credit only applies to food/beverage establishments."""
        employees = [TippedEmployee(name="Server", hourly_wage=2.13, hours_worked=160, tips_received=2400)]
        
        result = TipCreditCalculator.calculate(employees)
        
        all_notes = " ".join(result.compliance_notes)
        assert "food" in all_notes.lower() or "beverage" in all_notes.lower()


class TestTipCreditEdgeCases:
    """Test edge cases."""
    
    def test_zero_tips(self):
        """Should handle employee with zero tips."""
        employees = [TippedEmployee(name="Server", hourly_wage=2.13, hours_worked=160, tips_received=0)]
        
        result = TipCreditCalculator.calculate(employees)
        
        assert result.total_fica_credit == 0
        assert result.total_qualifying_tips == 0
    
    def test_zero_hours(self):
        """Should handle employee with zero hours."""
        employees = [TippedEmployee(name="Server", hourly_wage=2.13, hours_worked=0, tips_received=0)]
        
        result = TipCreditCalculator.calculate(employees)
        
        assert result.total_fica_credit == 0
    
    def test_high_cash_wage_no_tip_credit_taken(self):
        """Employee paid above minimum wage uses no tips for wage."""
        employees = [
            TippedEmployee(
                name="Server",
                hourly_wage=10.00,  # Above federal minimum
                hours_worked=160,
                tips_received=2400,
            )
        ]
        
        result = TipCreditCalculator.calculate(employees)
        
        # All tips should qualify since wage >= minimum
        # Qualifying tips = all tips
        assert result.total_qualifying_tips == 2400
    
    def test_empty_employee_list(self):
        """Should handle empty employee list."""
        result = TipCreditCalculator.calculate([])
        
        assert result.total_tipped_employees == 0
        assert result.total_fica_credit == 0


class TestTippedEmployeeModel:
    """Test TippedEmployee dataclass calculations."""
    
    def test_tips_per_hour(self):
        """Tips per hour = tips / hours."""
        emp = TippedEmployee(hourly_wage=2.13, hours_worked=160, tips_received=2400)
        
        assert emp.tips_per_hour == 15.0
    
    def test_total_compensation(self):
        """Total hourly = wage + tips per hour."""
        emp = TippedEmployee(hourly_wage=2.13, hours_worked=160, tips_received=2400)
        
        assert emp.total_hourly_compensation == 17.13  # 2.13 + 15.00
    
    def test_zero_hours_tips_per_hour(self):
        """Tips per hour should be 0 when hours are 0."""
        emp = TippedEmployee(hourly_wage=2.13, hours_worked=0, tips_received=100)
        
        assert emp.tips_per_hour == 0


class TestConvenienceFunctions:
    """Test module-level convenience functions."""
    
    def test_calculate_tip_credit(self):
        """Test calculate_tip_credit convenience function."""
        from fiscalpilot.analyzers.tip_credit import calculate_tip_credit
        
        employees = [TippedEmployee(name="Server", hourly_wage=2.13, hours_worked=160, tips_received=2400)]
        result = calculate_tip_credit(employees)
        
        assert isinstance(result, TipCreditResult)
    
    def test_quick_tip_credit_estimate(self):
        """Test quick_tip_credit_estimate convenience function."""
        from fiscalpilot.analyzers.tip_credit import quick_tip_credit_estimate
        
        result = quick_tip_credit_estimate(num_tipped_employees=5)
        
        assert isinstance(result, TipCreditResult)
