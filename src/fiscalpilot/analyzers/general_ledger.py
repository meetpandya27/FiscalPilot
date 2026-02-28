"""
General Ledger and Chart of Accounts Module.

Provides:
- Chart of Accounts management
- General Ledger entries
- Journal entries
- Trial balance
- Financial statement generation
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum


class AccountType(str, Enum):
    """Account types in the chart of accounts."""
    
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    REVENUE = "revenue"
    EXPENSE = "expense"
    CONTRA_ASSET = "contra_asset"
    CONTRA_LIABILITY = "contra_liability"
    CONTRA_REVENUE = "contra_revenue"


class AccountSubtype(str, Enum):
    """Account subtypes for more granular classification."""
    
    # Assets
    CASH = "cash"
    BANK = "bank"
    ACCOUNTS_RECEIVABLE = "accounts_receivable"
    INVENTORY = "inventory"
    PREPAID = "prepaid"
    FIXED_ASSET = "fixed_asset"
    ACCUMULATED_DEPRECIATION = "accumulated_depreciation"
    OTHER_ASSET = "other_asset"
    
    # Liabilities
    ACCOUNTS_PAYABLE = "accounts_payable"
    CREDIT_CARD = "credit_card"
    ACCRUED_EXPENSE = "accrued_expense"
    SHORT_TERM_DEBT = "short_term_debt"
    LONG_TERM_DEBT = "long_term_debt"
    OTHER_LIABILITY = "other_liability"
    
    # Equity
    RETAINED_EARNINGS = "retained_earnings"
    COMMON_STOCK = "common_stock"
    OWNERS_EQUITY = "owners_equity"
    OTHER_EQUITY = "other_equity"
    
    # Revenue
    SALES = "sales"
    SERVICE_REVENUE = "service_revenue"
    OTHER_INCOME = "other_income"
    
    # Expense
    COGS = "cogs"
    PAYROLL = "payroll"
    RENT = "rent"
    UTILITIES = "utilities"
    MARKETING = "marketing"
    PROFESSIONAL_SERVICES = "professional_services"
    OTHER_EXPENSE = "other_expense"


@dataclass
class Account:
    """A chart of accounts entry."""
    
    id: str
    code: str  # e.g., "1000", "4000"
    name: str
    account_type: AccountType
    subtype: AccountSubtype | None = None
    
    # Hierarchy
    parent_id: str | None = None
    level: int = 1
    
    # Configuration
    is_active: bool = True
    is_header: bool = False  # Header accounts used for grouping only
    description: str | None = None
    
    # Balances
    balance: Decimal = Decimal("0")
    opening_balance: Decimal = Decimal("0")
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime | None = None
    
    @property
    def normal_balance(self) -> str:
        """Get the normal balance side (debit or credit) for this account type."""
        if self.account_type in (
            AccountType.ASSET,
            AccountType.EXPENSE,
            AccountType.CONTRA_LIABILITY,
            AccountType.CONTRA_REVENUE,
        ):
            return "debit"
        else:
            return "credit"


@dataclass
class JournalLine:
    """A single line in a journal entry."""
    
    account_id: str
    account_code: str
    account_name: str
    
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    
    description: str | None = None
    
    @property
    def net_amount(self) -> Decimal:
        """Net amount (debit positive, credit negative)."""
        return self.debit - self.credit


@dataclass
class JournalEntry:
    """A journal entry."""
    
    id: str
    date: datetime
    description: str
    
    lines: list[JournalLine] = field(default_factory=list)
    
    # Reference
    reference: str | None = None  # Invoice #, check #, etc.
    source: str | None = None  # AP, AR, GL, etc.
    
    # State
    is_posted: bool = False
    posted_at: datetime | None = None
    posted_by: str | None = None
    
    is_reversing: bool = False
    reversed_entry_id: str | None = None
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    created_by: str | None = None
    
    @property
    def total_debits(self) -> Decimal:
        """Total of all debit amounts."""
        return sum(line.debit for line in self.lines)
    
    @property
    def total_credits(self) -> Decimal:
        """Total of all credit amounts."""
        return sum(line.credit for line in self.lines)
    
    @property
    def is_balanced(self) -> bool:
        """Whether debits equal credits."""
        return self.total_debits == self.total_credits


@dataclass
class TrialBalanceRow:
    """A row in the trial balance."""
    
    account_id: str
    account_code: str
    account_name: str
    account_type: AccountType
    
    debit_balance: Decimal = Decimal("0")
    credit_balance: Decimal = Decimal("0")


@dataclass
class TrialBalance:
    """A trial balance report."""
    
    as_of_date: datetime
    rows: list[TrialBalanceRow] = field(default_factory=list)
    
    total_debits: Decimal = Decimal("0")
    total_credits: Decimal = Decimal("0")
    is_balanced: bool = True


@dataclass
class FinancialStatementLine:
    """A line item in a financial statement."""
    
    label: str
    amount: Decimal
    level: int = 1  # Indentation level
    is_total: bool = False
    account_ids: list[str] = field(default_factory=list)


@dataclass
class IncomeStatement:
    """Income statement (P&L)."""
    
    period_start: datetime
    period_end: datetime
    
    revenue_lines: list[FinancialStatementLine] = field(default_factory=list)
    expense_lines: list[FinancialStatementLine] = field(default_factory=list)
    
    total_revenue: Decimal = Decimal("0")
    total_expenses: Decimal = Decimal("0")
    net_income: Decimal = Decimal("0")


@dataclass
class BalanceSheet:
    """Balance sheet."""
    
    as_of_date: datetime
    
    asset_lines: list[FinancialStatementLine] = field(default_factory=list)
    liability_lines: list[FinancialStatementLine] = field(default_factory=list)
    equity_lines: list[FinancialStatementLine] = field(default_factory=list)
    
    total_assets: Decimal = Decimal("0")
    total_liabilities: Decimal = Decimal("0")
    total_equity: Decimal = Decimal("0")
    
    @property
    def is_balanced(self) -> bool:
        """Assets should equal liabilities + equity."""
        return self.total_assets == (self.total_liabilities + self.total_equity)


class GeneralLedger:
    """Manage chart of accounts and general ledger.

    Usage::

        gl = GeneralLedger()
        
        # Set up chart of accounts
        gl.add_account(Account(
            id="1000",
            code="1000",
            name="Cash",
            account_type=AccountType.ASSET,
            subtype=AccountSubtype.CASH,
        ))
        
        # Create journal entry
        entry = gl.create_journal_entry(
            date=datetime.now(),
            description="Sale payment received",
            lines=[
                JournalLine(account_id="1000", account_code="1000", account_name="Cash", debit=Decimal("1000")),
                JournalLine(account_id="4000", account_code="4000", account_name="Sales", credit=Decimal("1000")),
            ],
        )
        
        # Post entry
        gl.post_entry(entry.id)
        
        # Generate reports
        trial_balance = gl.generate_trial_balance()
        income_statement = gl.generate_income_statement()
    """

    def __init__(self) -> None:
        self.accounts: dict[str, Account] = {}
        self.entries: dict[str, JournalEntry] = {}
        
        self._entry_counter = 0

    def add_account(self, account: Account) -> None:
        """Add an account to the chart of accounts."""
        self.accounts[account.id] = account

    def get_account(self, account_id: str) -> Account | None:
        """Get an account by ID."""
        return self.accounts.get(account_id)

    def get_account_by_code(self, code: str) -> Account | None:
        """Get an account by code."""
        for account in self.accounts.values():
            if account.code == code:
                return account
        return None

    def update_account(self, account: Account) -> None:
        """Update an account."""
        account.updated_at = datetime.now()
        self.accounts[account.id] = account

    def deactivate_account(self, account_id: str) -> None:
        """Deactivate an account."""
        account = self.accounts.get(account_id)
        if account:
            account.is_active = False
            account.updated_at = datetime.now()

    def get_accounts_by_type(self, account_type: AccountType) -> list[Account]:
        """Get all accounts of a given type."""
        return [
            a for a in self.accounts.values()
            if a.account_type == account_type and a.is_active
        ]

    def get_child_accounts(self, parent_id: str) -> list[Account]:
        """Get child accounts of a parent."""
        return [
            a for a in self.accounts.values()
            if a.parent_id == parent_id
        ]

    def create_journal_entry(
        self,
        date: datetime,
        description: str,
        lines: list[JournalLine],
        reference: str | None = None,
        source: str | None = None,
        created_by: str | None = None,
    ) -> JournalEntry:
        """Create a journal entry (not yet posted).
        
        Args:
            date: Entry date.
            description: Description of entry.
            lines: Journal lines.
            reference: Reference number.
            source: Source module (AP, AR, etc.).
            created_by: User creating entry.
        
        Returns:
            The created entry.
        """
        self._entry_counter += 1
        
        entry = JournalEntry(
            id=f"je_{self._entry_counter}",
            date=date,
            description=description,
            lines=lines,
            reference=reference,
            source=source,
            created_by=created_by,
        )
        
        self.entries[entry.id] = entry
        return entry

    def validate_entry(self, entry: JournalEntry) -> tuple[bool, list[str]]:
        """Validate a journal entry before posting.
        
        Returns:
            Tuple of (is_valid, list of error messages).
        """
        errors = []
        
        # Check balance
        if not entry.is_balanced:
            errors.append(
                f"Entry is not balanced. Debits: {entry.total_debits}, "
                f"Credits: {entry.total_credits}"
            )
        
        # Check for zero entries
        if entry.total_debits == 0:
            errors.append("Entry has no amounts")
        
        # Validate accounts exist
        for line in entry.lines:
            account = self.accounts.get(line.account_id)
            if not account:
                errors.append(f"Account not found: {line.account_id}")
            elif not account.is_active:
                errors.append(f"Account is inactive: {account.name}")
            elif account.is_header:
                errors.append(f"Cannot post to header account: {account.name}")
        
        return len(errors) == 0, errors

    def post_entry(
        self,
        entry_id: str,
        posted_by: str | None = None,
    ) -> tuple[bool, list[str]]:
        """Post a journal entry to update account balances.
        
        Args:
            entry_id: Entry to post.
            posted_by: User posting entry.
        
        Returns:
            Tuple of (success, error messages).
        """
        entry = self.entries.get(entry_id)
        if not entry:
            return False, [f"Entry not found: {entry_id}"]
        
        if entry.is_posted:
            return False, ["Entry is already posted"]
        
        # Validate
        is_valid, errors = self.validate_entry(entry)
        if not is_valid:
            return False, errors
        
        # Update account balances
        for line in entry.lines:
            account = self.accounts.get(line.account_id)
            if not account:
                continue
            
            # Calculate balance change based on normal balance
            if account.normal_balance == "debit":
                account.balance += (line.debit - line.credit)
            else:
                account.balance += (line.credit - line.debit)
            
            account.updated_at = datetime.now()
        
        # Mark as posted
        entry.is_posted = True
        entry.posted_at = datetime.now()
        entry.posted_by = posted_by
        
        return True, []

    def reverse_entry(
        self,
        entry_id: str,
        reverse_date: datetime | None = None,
        created_by: str | None = None,
    ) -> JournalEntry | None:
        """Create a reversing entry for posted entry.
        
        Args:
            entry_id: Entry to reverse.
            reverse_date: Date for reversing entry.
            created_by: User creating reversal.
        
        Returns:
            The reversing entry or None if original not found/posted.
        """
        original = self.entries.get(entry_id)
        if not original or not original.is_posted:
            return None
        
        # Create reversed lines
        reversed_lines = []
        for line in original.lines:
            reversed_lines.append(JournalLine(
                account_id=line.account_id,
                account_code=line.account_code,
                account_name=line.account_name,
                debit=line.credit,  # Swap debit and credit
                credit=line.debit,
                description=f"Reversal of: {line.description or ''}",
            ))
        
        reversal = self.create_journal_entry(
            date=reverse_date or datetime.now(),
            description=f"Reversal of {original.id}: {original.description}",
            lines=reversed_lines,
            reference=original.reference,
            source=original.source,
            created_by=created_by,
        )
        
        reversal.is_reversing = True
        reversal.reversed_entry_id = entry_id
        
        return reversal

    def get_account_activity(
        self,
        account_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[tuple[JournalEntry, JournalLine]]:
        """Get all posted activity for an account.
        
        Args:
            account_id: Account to query.
            start_date: Start of period.
            end_date: End of period.
        
        Returns:
            List of (entry, line) tuples.
        """
        activity = []
        
        for entry in self.entries.values():
            if not entry.is_posted:
                continue
            if start_date and entry.date < start_date:
                continue
            if end_date and entry.date > end_date:
                continue
            
            for line in entry.lines:
                if line.account_id == account_id:
                    activity.append((entry, line))
        
        return sorted(activity, key=lambda x: x[0].date)

    def generate_trial_balance(
        self,
        as_of_date: datetime | None = None,
    ) -> TrialBalance:
        """Generate trial balance report.
        
        Args:
            as_of_date: Date for trial balance.
        
        Returns:
            Trial balance report.
        """
        as_of_date = as_of_date or datetime.now()
        
        rows = []
        total_debits = Decimal("0")
        total_credits = Decimal("0")
        
        # Sort accounts by code
        sorted_accounts = sorted(
            [a for a in self.accounts.values() if a.is_active and not a.is_header],
            key=lambda a: a.code,
        )
        
        for account in sorted_accounts:
            # Calculate balance through as_of_date
            balance = account.opening_balance
            
            for entry in self.entries.values():
                if not entry.is_posted:
                    continue
                if entry.date > as_of_date:
                    continue
                
                for line in entry.lines:
                    if line.account_id == account.id:
                        if account.normal_balance == "debit":
                            balance += (line.debit - line.credit)
                        else:
                            balance += (line.credit - line.debit)
            
            if balance == 0:
                continue  # Skip zero balances
            
            # Determine debit or credit balance
            if account.normal_balance == "debit":
                debit_balance = balance if balance >= 0 else Decimal("0")
                credit_balance = -balance if balance < 0 else Decimal("0")
            else:
                credit_balance = balance if balance >= 0 else Decimal("0")
                debit_balance = -balance if balance < 0 else Decimal("0")
            
            rows.append(TrialBalanceRow(
                account_id=account.id,
                account_code=account.code,
                account_name=account.name,
                account_type=account.account_type,
                debit_balance=debit_balance,
                credit_balance=credit_balance,
            ))
            
            total_debits += debit_balance
            total_credits += credit_balance
        
        return TrialBalance(
            as_of_date=as_of_date,
            rows=rows,
            total_debits=total_debits,
            total_credits=total_credits,
            is_balanced=(total_debits == total_credits),
        )

    def generate_income_statement(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> IncomeStatement:
        """Generate income statement for a period.
        
        Args:
            start_date: Period start.
            end_date: Period end.
        
        Returns:
            Income statement.
        """
        revenue_lines = []
        expense_lines = []
        total_revenue = Decimal("0")
        total_expenses = Decimal("0")
        
        # Process revenue accounts
        revenue_accounts = self.get_accounts_by_type(AccountType.REVENUE)
        for account in sorted(revenue_accounts, key=lambda a: a.code):
            balance = Decimal("0")
            
            for entry in self.entries.values():
                if not entry.is_posted:
                    continue
                if not (start_date <= entry.date <= end_date):
                    continue
                
                for line in entry.lines:
                    if line.account_id == account.id:
                        balance += (line.credit - line.debit)
            
            if balance != 0:
                revenue_lines.append(FinancialStatementLine(
                    label=account.name,
                    amount=balance,
                    account_ids=[account.id],
                ))
                total_revenue += balance
        
        # Process expense accounts
        expense_accounts = self.get_accounts_by_type(AccountType.EXPENSE)
        for account in sorted(expense_accounts, key=lambda a: a.code):
            balance = Decimal("0")
            
            for entry in self.entries.values():
                if not entry.is_posted:
                    continue
                if not (start_date <= entry.date <= end_date):
                    continue
                
                for line in entry.lines:
                    if line.account_id == account.id:
                        balance += (line.debit - line.credit)
            
            if balance != 0:
                expense_lines.append(FinancialStatementLine(
                    label=account.name,
                    amount=balance,
                    account_ids=[account.id],
                ))
                total_expenses += balance
        
        return IncomeStatement(
            period_start=start_date,
            period_end=end_date,
            revenue_lines=revenue_lines,
            expense_lines=expense_lines,
            total_revenue=total_revenue,
            total_expenses=total_expenses,
            net_income=total_revenue - total_expenses,
        )

    def generate_balance_sheet(
        self,
        as_of_date: datetime,
    ) -> BalanceSheet:
        """Generate balance sheet as of a date.
        
        Args:
            as_of_date: Date for balance sheet.
        
        Returns:
            Balance sheet.
        """
        asset_lines = []
        liability_lines = []
        equity_lines = []
        
        total_assets = Decimal("0")
        total_liabilities = Decimal("0")
        total_equity = Decimal("0")
        
        def get_balance(account: Account) -> Decimal:
            balance = account.opening_balance
            
            for entry in self.entries.values():
                if not entry.is_posted:
                    continue
                if entry.date > as_of_date:
                    continue
                
                for line in entry.lines:
                    if line.account_id == account.id:
                        if account.normal_balance == "debit":
                            balance += (line.debit - line.credit)
                        else:
                            balance += (line.credit - line.debit)
            
            return balance
        
        # Assets
        for account in sorted(
            self.get_accounts_by_type(AccountType.ASSET),
            key=lambda a: a.code,
        ):
            balance = get_balance(account)
            if balance != 0:
                asset_lines.append(FinancialStatementLine(
                    label=account.name,
                    amount=balance,
                    account_ids=[account.id],
                ))
                total_assets += balance
        
        # Liabilities
        for account in sorted(
            self.get_accounts_by_type(AccountType.LIABILITY),
            key=lambda a: a.code,
        ):
            balance = get_balance(account)
            if balance != 0:
                liability_lines.append(FinancialStatementLine(
                    label=account.name,
                    amount=balance,
                    account_ids=[account.id],
                ))
                total_liabilities += balance
        
        # Equity
        for account in sorted(
            self.get_accounts_by_type(AccountType.EQUITY),
            key=lambda a: a.code,
        ):
            balance = get_balance(account)
            if balance != 0:
                equity_lines.append(FinancialStatementLine(
                    label=account.name,
                    amount=balance,
                    account_ids=[account.id],
                ))
                total_equity += balance
        
        return BalanceSheet(
            as_of_date=as_of_date,
            asset_lines=asset_lines,
            liability_lines=liability_lines,
            equity_lines=equity_lines,
            total_assets=total_assets,
            total_liabilities=total_liabilities,
            total_equity=total_equity,
        )

    def setup_standard_coa(self) -> None:
        """Set up a standard chart of accounts.
        
        Creates common accounts for a small business.
        """
        accounts = [
            # Assets
            Account("1000", "1000", "Cash", AccountType.ASSET, AccountSubtype.CASH),
            Account("1010", "1010", "Checking Account", AccountType.ASSET, AccountSubtype.BANK, parent_id="1000"),
            Account("1020", "1020", "Savings Account", AccountType.ASSET, AccountSubtype.BANK, parent_id="1000"),
            Account("1100", "1100", "Accounts Receivable", AccountType.ASSET, AccountSubtype.ACCOUNTS_RECEIVABLE),
            Account("1200", "1200", "Inventory", AccountType.ASSET, AccountSubtype.INVENTORY),
            Account("1300", "1300", "Prepaid Expenses", AccountType.ASSET, AccountSubtype.PREPAID),
            Account("1500", "1500", "Fixed Assets", AccountType.ASSET, AccountSubtype.FIXED_ASSET),
            Account("1600", "1600", "Accumulated Depreciation", AccountType.CONTRA_ASSET, AccountSubtype.ACCUMULATED_DEPRECIATION),
            
            # Liabilities
            Account("2000", "2000", "Accounts Payable", AccountType.LIABILITY, AccountSubtype.ACCOUNTS_PAYABLE),
            Account("2100", "2100", "Credit Cards", AccountType.LIABILITY, AccountSubtype.CREDIT_CARD),
            Account("2200", "2200", "Accrued Expenses", AccountType.LIABILITY, AccountSubtype.ACCRUED_EXPENSE),
            Account("2300", "2300", "Sales Tax Payable", AccountType.LIABILITY, AccountSubtype.OTHER_LIABILITY),
            Account("2500", "2500", "Short-Term Debt", AccountType.LIABILITY, AccountSubtype.SHORT_TERM_DEBT),
            Account("2600", "2600", "Long-Term Debt", AccountType.LIABILITY, AccountSubtype.LONG_TERM_DEBT),
            
            # Equity
            Account("3000", "3000", "Owner's Equity", AccountType.EQUITY, AccountSubtype.OWNERS_EQUITY),
            Account("3100", "3100", "Retained Earnings", AccountType.EQUITY, AccountSubtype.RETAINED_EARNINGS),
            
            # Revenue
            Account("4000", "4000", "Sales Revenue", AccountType.REVENUE, AccountSubtype.SALES),
            Account("4100", "4100", "Service Revenue", AccountType.REVENUE, AccountSubtype.SERVICE_REVENUE),
            Account("4900", "4900", "Other Income", AccountType.REVENUE, AccountSubtype.OTHER_INCOME),
            
            # Expenses
            Account("5000", "5000", "Cost of Goods Sold", AccountType.EXPENSE, AccountSubtype.COGS),
            Account("6000", "6000", "Payroll Expense", AccountType.EXPENSE, AccountSubtype.PAYROLL),
            Account("6100", "6100", "Rent Expense", AccountType.EXPENSE, AccountSubtype.RENT),
            Account("6200", "6200", "Utilities Expense", AccountType.EXPENSE, AccountSubtype.UTILITIES),
            Account("6300", "6300", "Marketing Expense", AccountType.EXPENSE, AccountSubtype.MARKETING),
            Account("6400", "6400", "Professional Services", AccountType.EXPENSE, AccountSubtype.PROFESSIONAL_SERVICES),
            Account("6500", "6500", "Office Supplies", AccountType.EXPENSE, AccountSubtype.OTHER_EXPENSE),
            Account("6600", "6600", "Insurance Expense", AccountType.EXPENSE, AccountSubtype.OTHER_EXPENSE),
            Account("6700", "6700", "Depreciation Expense", AccountType.EXPENSE, AccountSubtype.OTHER_EXPENSE),
            Account("6900", "6900", "Other Expenses", AccountType.EXPENSE, AccountSubtype.OTHER_EXPENSE),
        ]
        
        for account in accounts:
            self.add_account(account)
