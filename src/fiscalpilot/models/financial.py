"""
Financial data models — transactions, accounts, line items.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TransactionType(str, Enum):
    """Core transaction types."""

    EXPENSE = "expense"
    INCOME = "income"
    TRANSFER = "transfer"
    REFUND = "refund"
    PAYROLL = "payroll"
    TAX = "tax"
    DEPRECIATION = "depreciation"
    OTHER = "other"


class ExpenseCategory(str, Enum):
    """Standardized expense categories for cross-business comparison."""

    PAYROLL = "payroll"
    RENT = "rent"
    UTILITIES = "utilities"
    INSURANCE = "insurance"
    SUPPLIES = "supplies"
    INVENTORY = "inventory"
    MARKETING = "marketing"
    SOFTWARE = "software"
    SUBSCRIPTIONS = "subscriptions"
    TRAVEL = "travel"
    MEALS = "meals"
    PROFESSIONAL_FEES = "professional_fees"
    EQUIPMENT = "equipment"
    MAINTENANCE = "maintenance"
    SHIPPING = "shipping"
    TAXES = "taxes"
    INTEREST = "interest"
    DEPRECIATION = "depreciation"
    MISCELLANEOUS = "miscellaneous"
    OTHER = "other"


class Transaction(BaseModel):
    """A single financial transaction."""

    id: str | None = None
    date: date
    amount: float
    type: TransactionType
    category: ExpenseCategory | None = None
    description: str = ""
    vendor: str | None = None
    account: str | None = None
    department: str | None = None
    tags: list[str] = Field(default_factory=list)
    raw_data: dict[str, Any] = Field(default_factory=dict, exclude=True)

    @property
    def is_expense(self) -> bool:
        return self.type == TransactionType.EXPENSE

    @property
    def is_income(self) -> bool:
        return self.type == TransactionType.INCOME


class LineItem(BaseModel):
    """A single line item on an invoice or receipt."""

    description: str
    quantity: float = 1.0
    unit_price: float
    total: float
    category: ExpenseCategory | None = None


class Invoice(BaseModel):
    """An invoice (payable or receivable)."""

    id: str | None = None
    invoice_number: str | None = None
    vendor: str
    amount: float
    due_date: date
    paid_date: date | None = None
    status: str = "pending"  # pending, paid, overdue, disputed
    line_items: list[LineItem] = Field(default_factory=list)


class AccountBalance(BaseModel):
    """Point-in-time account balance."""

    account_name: str
    account_type: str  # checking, savings, credit, loan
    balance: float
    as_of: datetime
    institution: str | None = None


class FinancialDataset(BaseModel):
    """Complete financial dataset for analysis.

    This is what connectors produce and analyzers consume.
    """

    transactions: list[Transaction] = Field(default_factory=list)
    invoices: list[Invoice] = Field(default_factory=list)
    balances: list[AccountBalance] = Field(default_factory=list)
    period_start: date | None = None
    period_end: date | None = None
    source: str = "unknown"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def total_expenses(self) -> float:
        return sum(t.amount for t in self.transactions if t.is_expense)

    @property
    def total_income(self) -> float:
        return sum(t.amount for t in self.transactions if t.is_income)

    @property
    def expense_count(self) -> int:
        return sum(1 for t in self.transactions if t.is_expense)
