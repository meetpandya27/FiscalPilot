"""Tests for data models."""

from datetime import date, datetime

import pytest

from fiscalpilot.models.company import CompanyProfile, CompanySize, Industry
from fiscalpilot.models.financial import (
    AccountBalance,
    ExpenseCategory,
    FinancialDataset,
    Transaction,
    TransactionType,
)
from fiscalpilot.models.report import (
    ActionItem,
    AuditReport,
    ExecutiveSummary,
    Finding,
    FindingCategory,
    Severity,
)


class TestCompanyProfile:
    def test_create_company(self) -> None:
        company = CompanyProfile(
            name="Test Corp",
            industry=Industry.SAAS,
            size=CompanySize.MEDIUM,
            annual_revenue=10_000_000,
        )
        assert company.name == "Test Corp"
        assert company.industry == Industry.SAAS
        assert company.size == CompanySize.MEDIUM
        assert company.annual_revenue == 10_000_000

    def test_company_defaults(self) -> None:
        company = CompanyProfile(name="Small Biz")
        assert company.industry == Industry.OTHER
        assert company.size == CompanySize.SMALL
        assert company.country == "US"
        assert company.currency == "USD"

    def test_size_label(self) -> None:
        company = CompanyProfile(name="Big Co", size=CompanySize.ENTERPRISE)
        assert "Fortune" in company.size_label or "Global" in company.size_label


class TestTransaction:
    def test_create_expense(self) -> None:
        txn = Transaction(
            date=date(2025, 1, 15),
            amount=500.0,
            type=TransactionType.EXPENSE,
            description="Office supplies",
            vendor="Staples",
            category=ExpenseCategory.SUPPLIES,
        )
        assert txn.is_expense
        assert not txn.is_income
        assert txn.amount == 500.0

    def test_create_income(self) -> None:
        txn = Transaction(
            date=date(2025, 1, 15),
            amount=10000.0,
            type=TransactionType.INCOME,
            description="Client payment",
        )
        assert txn.is_income
        assert not txn.is_expense


class TestFinancialDataset:
    def test_totals(self) -> None:
        dataset = FinancialDataset(
            transactions=[
                Transaction(date=date(2025, 1, 1), amount=1000, type=TransactionType.INCOME),
                Transaction(date=date(2025, 1, 2), amount=500, type=TransactionType.INCOME),
                Transaction(date=date(2025, 1, 3), amount=200, type=TransactionType.EXPENSE),
                Transaction(date=date(2025, 1, 4), amount=300, type=TransactionType.EXPENSE),
            ]
        )
        assert dataset.total_income == 1500.0
        assert dataset.total_expenses == 500.0
        assert dataset.expense_count == 2

    def test_empty_dataset(self) -> None:
        dataset = FinancialDataset()
        assert dataset.total_income == 0.0
        assert dataset.total_expenses == 0.0
        assert dataset.expense_count == 0


class TestAuditReport:
    def test_total_savings(self) -> None:
        report = AuditReport(
            company_name="Test",
            findings=[
                Finding(
                    id="f1",
                    title="Issue 1",
                    category=FindingCategory.WASTE,
                    severity=Severity.HIGH,
                    description="Wasteful spending detected",
                    potential_savings=5000,
                ),
                Finding(
                    id="f2",
                    title="Issue 2",
                    category=FindingCategory.COST_REDUCTION,
                    severity=Severity.MEDIUM,
                    description="Cost reduction opportunity",
                    potential_savings=3000,
                ),
            ],
        )
        assert report.total_potential_savings == 8000.0

    def test_critical_findings(self) -> None:
        report = AuditReport(
            company_name="Test",
            findings=[
                Finding(
                    id="f1",
                    title="Critical",
                    category=FindingCategory.FRAUD,
                    severity=Severity.CRITICAL,
                    description="Potential fraud detected",
                    potential_savings=10000,
                ),
                Finding(
                    id="f2",
                    title="Low",
                    category=FindingCategory.WASTE,
                    severity=Severity.LOW,
                    description="Minor waste",
                    potential_savings=100,
                ),
            ],
        )
        assert len(report.critical_findings) == 1
        assert len(report.high_priority_findings) == 1

    def test_to_json(self) -> None:
        report = AuditReport(company_name="Test")
        json_str = report.to_json()
        assert "Test" in json_str

    def test_to_markdown(self) -> None:
        report = AuditReport(
            company_name="Test Co",
            findings=[
                Finding(
                    id="f1",
                    title="Waste Found",
                    category=FindingCategory.WASTE,
                    severity=Severity.HIGH,
                    description="Too much waste",
                    potential_savings=5000,
                    recommendation="Fix it",
                ),
            ],
            executive_summary=ExecutiveSummary(
                total_potential_savings=5000,
                total_findings=1,
                health_score=80,
            ),
        )
        md = report.to_markdown()
        assert "Test Co" in md
        assert "Waste Found" in md
        assert "5,000" in md
