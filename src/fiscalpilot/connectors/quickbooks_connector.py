"""
QuickBooks Online Connector — full integration with QBO Accounting API.

Pulls transactions (purchases + deposits), invoices, bill payments,
vendor credits, and account balances via the QBO REST API v3.

Authentication: OAuth2 (handled by OAuth2TokenManager).
Requires: `pip install fiscalpilot[quickbooks]`

QuickBooks API docs:
  https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

import httpx

from fiscalpilot.auth.oauth2 import OAuth2TokenManager
from fiscalpilot.connectors.base import BaseConnector
from fiscalpilot.models.company import CompanyProfile
from fiscalpilot.models.financial import (
    AccountBalance,
    ExpenseCategory,
    FinancialDataset,
    Invoice,
    LineItem,
    Transaction,
    TransactionType,
)

logger = logging.getLogger("fiscalpilot.connectors.quickbooks")

# QuickBooks API endpoints
_QBO_BASE_URL = "https://quickbooks.api.intuit.com/v3/company"
_QBO_SANDBOX_URL = "https://sandbox-quickbooks.api.intuit.com/v3/company"
_QBO_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
_QBO_AUTH_URL = "https://appcenter.intuit.com/connect/oauth2"

# Max results per API page
_PAGE_SIZE = 1000

# Map QBO account types to our categories
_QBO_CATEGORY_MAP: dict[str, ExpenseCategory] = {
    "Advertising": ExpenseCategory.MARKETING,
    "Auto": ExpenseCategory.TRAVEL,
    "Bank Charges": ExpenseCategory.OTHER,
    "Charity": ExpenseCategory.OTHER,
    "Cost of Goods Sold": ExpenseCategory.INVENTORY,
    "Dues": ExpenseCategory.SUBSCRIPTIONS,
    "Entertainment": ExpenseCategory.MEALS,
    "Equipment Rental": ExpenseCategory.EQUIPMENT,
    "Insurance": ExpenseCategory.INSURANCE,
    "Interest Paid": ExpenseCategory.INTEREST,
    "Legal & Professional Fees": ExpenseCategory.PROFESSIONAL_FEES,
    "Meals and Entertainment": ExpenseCategory.MEALS,
    "Office Expenses": ExpenseCategory.SUPPLIES,
    "Other Business Expenses": ExpenseCategory.OTHER,
    "Payroll Expenses": ExpenseCategory.PAYROLL,
    "Rent or Lease": ExpenseCategory.RENT,
    "Repair and Maintenance": ExpenseCategory.MAINTENANCE,
    "Shipping and delivery expense": ExpenseCategory.SHIPPING,
    "Stationery & Printing": ExpenseCategory.SUPPLIES,
    "Supplies": ExpenseCategory.SUPPLIES,
    "Taxes & Licenses": ExpenseCategory.TAXES,
    "Travel": ExpenseCategory.TRAVEL,
    "Travel Meals": ExpenseCategory.MEALS,
    "Utilities": ExpenseCategory.UTILITIES,
}


class QuickBooksConnector(BaseConnector):
    """Pull financial data from QuickBooks Online.

    Uses the QBO Accounting API v3 to fetch:
    - Purchase transactions (expenses, checks, credit card charges)
    - Deposit transactions (income)
    - Invoices (accounts receivable)
    - Bill payments
    - Account balances

    Authentication is handled via OAuth2. You can either:
    1. Provide a refresh_token directly (for headless / CI usage)
    2. Use the interactive auth flow via ``authorize()``

    Usage::

        connector = QuickBooksConnector(credentials={
            "client_id": "ABcDef...",
            "client_secret": "xyz123...",
            "refresh_token": "AB11...",
            "realm_id": "4620816365213515760",
        })
        dataset = await connector.pull(company_profile)

    For sandbox/development::

        connector = QuickBooksConnector(
            credentials={...},
            sandbox=True,
        )
    """

    name = "quickbooks"
    description = "Pull financial data from QuickBooks Online"

    def __init__(
        self,
        credentials: dict[str, Any] | None = None,
        *,
        sandbox: bool = False,
        start_date: date | None = None,
        end_date: date | None = None,
        **options: Any,
    ) -> None:
        super().__init__(credentials, **options)
        creds = credentials or {}

        self.client_id: str = creds.get("client_id", "")
        self.client_secret: str = creds.get("client_secret", "")
        self.refresh_token: str = creds.get("refresh_token", "")
        self.realm_id: str = creds.get("realm_id", "")
        self.sandbox = sandbox or creds.get("sandbox", False)

        self.start_date = start_date
        self.end_date = end_date or date.today()

        self._base_url = _QBO_SANDBOX_URL if self.sandbox else _QBO_BASE_URL
        self._token_manager: OAuth2TokenManager | None = None
        self._http: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _ensure_token_manager(self) -> OAuth2TokenManager:
        """Initialize the OAuth2 token manager."""
        if self._token_manager is None:
            self._token_manager = OAuth2TokenManager(
                provider="quickbooks",
                client_id=self.client_id,
                client_secret=self.client_secret,
                token_url=_QBO_TOKEN_URL,
                scopes=["com.intuit.quickbooks.accounting"],
            )
            self._token_manager.load_or_set(refresh_token=self.refresh_token)
        return self._token_manager

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create a reusable httpx client."""
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                timeout=60.0,
                headers={"Accept": "application/json"},
            )
        return self._http

    async def close(self) -> None:
        """Clean up HTTP client and token manager."""
        if self._http and not self._http.is_closed:
            await self._http.aclose()
        if self._token_manager:
            await self._token_manager.close()

    # ------------------------------------------------------------------
    # API helpers
    # ------------------------------------------------------------------

    async def _api_get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make an authenticated GET request to the QBO API."""
        mgr = self._ensure_token_manager()
        token = await mgr.get_access_token()
        client = await self._get_client()

        url = f"{self._base_url}/{self.realm_id}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

        resp = await client.get(url, headers=headers, params=params)

        # Handle 401 → force refresh and retry once
        if resp.status_code == 401:
            logger.info("QBO token expired, refreshing...")
            await mgr.refresh()
            token = await mgr.get_access_token()
            headers["Authorization"] = f"Bearer {token}"
            resp = await client.get(url, headers=headers, params=params)

        resp.raise_for_status()
        return resp.json()

    async def _query(self, query: str) -> list[dict[str, Any]]:
        """Execute a QBO query (SQL-like) and handle pagination.

        The QBO query API uses STARTPOSITION and MAXRESULTS for pagination.
        """
        all_results: list[dict[str, Any]] = []
        start_pos = 1

        while True:
            paged_query = f"{query} STARTPOSITION {start_pos} MAXRESULTS {_PAGE_SIZE}"
            data = await self._api_get("query", params={"query": paged_query})

            response = data.get("QueryResponse", {})

            # Find the entity list (it's the first key that isn't metadata)
            entities: list[dict[str, Any]] = []
            for key, value in response.items():
                if isinstance(value, list):
                    entities = value
                    break

            if not entities:
                break

            all_results.extend(entities)

            # If we got fewer than PAGE_SIZE, we've reached the end
            if len(entities) < _PAGE_SIZE:
                break

            start_pos += _PAGE_SIZE

        return all_results

    # ------------------------------------------------------------------
    # Data fetchers
    # ------------------------------------------------------------------

    async def _fetch_purchases(self) -> list[Transaction]:
        """Fetch Purchase entities (expenses, checks, credit card charges)."""
        date_filter = ""
        if self.start_date:
            date_filter = f" WHERE MetaData.CreateTime >= '{self.start_date.isoformat()}'"
            date_filter += f" AND MetaData.CreateTime <= '{self.end_date.isoformat()}'"

        query = f"SELECT * FROM Purchase{date_filter} ORDERBY MetaData.CreateTime DESC"
        purchases = await self._query(query)

        transactions: list[Transaction] = []
        for p in purchases:
            try:
                txn_date = self._parse_date(p.get("TxnDate", ""))
                total = float(p.get("TotalAmt", 0))

                # Get vendor name
                vendor_ref = p.get("EntityRef", {})
                vendor = vendor_ref.get("name", "") if vendor_ref else ""

                # Get account name for category mapping
                account_ref = p.get("AccountRef", {})
                account_name = account_ref.get("name", "") if account_ref else ""

                # Parse line items for description
                lines = p.get("Line", [])
                desc_parts = []
                for line in lines:
                    detail = line.get("AccountBasedExpenseLineDetail", {}) or line.get(
                        "ItemBasedExpenseLineDetail", {}
                    )
                    if detail:
                        acct = detail.get("AccountRef", {}).get("name", "")
                        if acct:
                            desc_parts.append(acct)
                    desc = line.get("Description", "")
                    if desc:
                        desc_parts.append(desc)

                description = "; ".join(desc_parts[:3]) if desc_parts else f"Purchase #{p.get('Id', '')}"

                # Map payment type
                pay_type = p.get("PaymentType", "")

                txn = Transaction(
                    id=f"qbo-purchase-{p.get('Id', '')}",
                    date=txn_date,
                    amount=total,
                    type=TransactionType.EXPENSE,
                    category=self._map_qbo_category(account_name),
                    description=description,
                    vendor=vendor or None,
                    account=account_name or None,
                    tags=[f"qbo:{pay_type.lower()}"] if pay_type else ["qbo:purchase"],
                    raw_data=p,
                )
                transactions.append(txn)
            except Exception as e:
                logger.debug("Skipping QBO purchase: %s", e)

        logger.info("Fetched %d purchases from QuickBooks", len(transactions))
        return transactions

    async def _fetch_deposits(self) -> list[Transaction]:
        """Fetch Deposit entities (income/revenue)."""
        date_filter = ""
        if self.start_date:
            date_filter = f" WHERE MetaData.CreateTime >= '{self.start_date.isoformat()}'"
            date_filter += f" AND MetaData.CreateTime <= '{self.end_date.isoformat()}'"

        query = f"SELECT * FROM Deposit{date_filter} ORDERBY MetaData.CreateTime DESC"
        deposits = await self._query(query)

        transactions: list[Transaction] = []
        for d in deposits:
            try:
                txn_date = self._parse_date(d.get("TxnDate", ""))
                total = float(d.get("TotalAmt", 0))

                # Parse deposit lines for description
                lines = d.get("Line", [])
                desc_parts = []
                for line in lines:
                    desc = line.get("Description", "")
                    if desc:
                        desc_parts.append(desc)
                    detail = line.get("DepositLineDetail", {})
                    if detail:
                        entity = detail.get("Entity", {})
                        if entity:
                            desc_parts.append(entity.get("name", ""))

                description = "; ".join(desc_parts[:3]) if desc_parts else f"Deposit #{d.get('Id', '')}"

                account_ref = d.get("DepositToAccountRef", {})
                account_name = account_ref.get("name", "") if account_ref else ""

                txn = Transaction(
                    id=f"qbo-deposit-{d.get('Id', '')}",
                    date=txn_date,
                    amount=total,
                    type=TransactionType.INCOME,
                    description=description,
                    account=account_name or None,
                    tags=["qbo:deposit"],
                    raw_data=d,
                )
                transactions.append(txn)
            except Exception as e:
                logger.debug("Skipping QBO deposit: %s", e)

        logger.info("Fetched %d deposits from QuickBooks", len(transactions))
        return transactions

    async def _fetch_invoices(self) -> list[Invoice]:
        """Fetch Invoice entities (accounts receivable)."""
        date_filter = ""
        if self.start_date:
            date_filter = f" WHERE MetaData.CreateTime >= '{self.start_date.isoformat()}'"
            date_filter += f" AND MetaData.CreateTime <= '{self.end_date.isoformat()}'"

        query = f"SELECT * FROM Invoice{date_filter} ORDERBY MetaData.CreateTime DESC"
        raw_invoices = await self._query(query)

        invoices: list[Invoice] = []
        for inv in raw_invoices:
            try:
                customer_ref = inv.get("CustomerRef", {})
                customer = customer_ref.get("name", "Unknown") if customer_ref else "Unknown"

                due_date = self._parse_date(inv.get("DueDate", inv.get("TxnDate", "")))
                total = float(inv.get("TotalAmt", 0))
                balance = float(inv.get("Balance", 0))

                # Determine status
                if balance == 0:
                    status = "paid"
                elif due_date < date.today():
                    status = "overdue"
                else:
                    status = "pending"

                # Parse line items
                line_items: list[LineItem] = []
                for line in inv.get("Line", []):
                    if line.get("DetailType") == "SalesItemLineDetail":
                        detail = line.get("SalesItemLineDetail", {})
                        item_ref = detail.get("ItemRef", {})
                        li = LineItem(
                            description=line.get("Description", item_ref.get("name", "Item")),
                            quantity=float(detail.get("Qty", 1)),
                            unit_price=float(detail.get("UnitPrice", 0)),
                            total=float(line.get("Amount", 0)),
                        )
                        line_items.append(li)

                invoice = Invoice(
                    id=f"qbo-invoice-{inv.get('Id', '')}",
                    invoice_number=inv.get("DocNumber"),
                    vendor=customer,  # In QBO invoices, this is the customer
                    amount=total,
                    due_date=due_date,
                    status=status,
                    line_items=line_items,
                )
                invoices.append(invoice)
            except Exception as e:
                logger.debug("Skipping QBO invoice: %s", e)

        logger.info("Fetched %d invoices from QuickBooks", len(invoices))
        return invoices

    async def _fetch_bills(self) -> list[Invoice]:
        """Fetch Bill entities (accounts payable)."""
        date_filter = ""
        if self.start_date:
            date_filter = f" WHERE MetaData.CreateTime >= '{self.start_date.isoformat()}'"
            date_filter += f" AND MetaData.CreateTime <= '{self.end_date.isoformat()}'"

        query = f"SELECT * FROM Bill{date_filter} ORDERBY MetaData.CreateTime DESC"
        raw_bills = await self._query(query)

        bills: list[Invoice] = []
        for bill in raw_bills:
            try:
                vendor_ref = bill.get("VendorRef", {})
                vendor = vendor_ref.get("name", "Unknown") if vendor_ref else "Unknown"

                due_date = self._parse_date(bill.get("DueDate", bill.get("TxnDate", "")))
                total = float(bill.get("TotalAmt", 0))
                balance = float(bill.get("Balance", 0))

                status = "paid" if balance == 0 else ("overdue" if due_date < date.today() else "pending")

                line_items: list[LineItem] = []
                for line in bill.get("Line", []):
                    if line.get("DetailType") == "AccountBasedExpenseLineDetail":
                        detail = line.get("AccountBasedExpenseLineDetail", {})
                        acct_ref = detail.get("AccountRef", {})
                        li = LineItem(
                            description=line.get("Description", acct_ref.get("name", "Expense")),
                            quantity=1.0,
                            unit_price=float(line.get("Amount", 0)),
                            total=float(line.get("Amount", 0)),
                            category=self._map_qbo_category(acct_ref.get("name", "")),
                        )
                        line_items.append(li)

                bill_obj = Invoice(
                    id=f"qbo-bill-{bill.get('Id', '')}",
                    invoice_number=bill.get("DocNumber"),
                    vendor=vendor,
                    amount=total,
                    due_date=due_date,
                    status=status,
                    line_items=line_items,
                )
                bills.append(bill_obj)
            except Exception as e:
                logger.debug("Skipping QBO bill: %s", e)

        logger.info("Fetched %d bills from QuickBooks", len(bills))
        return bills

    async def _fetch_account_balances(self) -> list[AccountBalance]:
        """Fetch current account balances."""
        query = "SELECT * FROM Account WHERE Active = true ORDERBY Name"
        accounts = await self._query(query)

        balances: list[AccountBalance] = []
        for acct in accounts:
            try:
                acct_type = acct.get("AccountType", "")
                # Only include balance sheet accounts
                if acct_type not in (
                    "Bank", "Credit Card", "Other Current Asset",
                    "Other Current Liability", "Accounts Receivable",
                    "Accounts Payable",
                ):
                    continue

                balance = AccountBalance(
                    account_name=acct.get("Name", "Unknown"),
                    account_type=self._map_account_type(acct_type),
                    balance=float(acct.get("CurrentBalance", 0)),
                    as_of=datetime.now(),
                    institution=acct.get("BankNum") or None,
                )
                balances.append(balance)
            except Exception as e:
                logger.debug("Skipping QBO account: %s", e)

        logger.info("Fetched %d account balances from QuickBooks", len(balances))
        return balances

    # ------------------------------------------------------------------
    # Main pull
    # ------------------------------------------------------------------

    async def pull(self, company: CompanyProfile) -> FinancialDataset:
        """Pull all financial data from QuickBooks Online.

        Fetches purchases, deposits, invoices, bills, and account balances
        in parallel for maximum speed.

        Args:
            company: Company profile for context.

        Returns:
            Normalized FinancialDataset with all QBO data.
        """
        import asyncio

        logger.info(
            "Pulling QuickBooks data for %s (realm: %s, sandbox: %s)",
            company.name, self.realm_id, self.sandbox,
        )

        # Fetch all entity types in parallel
        purchases_task = asyncio.create_task(self._fetch_purchases())
        deposits_task = asyncio.create_task(self._fetch_deposits())
        invoices_task = asyncio.create_task(self._fetch_invoices())
        bills_task = asyncio.create_task(self._fetch_bills())
        balances_task = asyncio.create_task(self._fetch_account_balances())

        purchases, deposits, invoices, bills, balances = await asyncio.gather(
            purchases_task, deposits_task, invoices_task, bills_task, balances_task,
        )

        all_transactions = purchases + deposits
        all_invoices = invoices + bills

        dataset = FinancialDataset(
            transactions=all_transactions,
            invoices=all_invoices,
            balances=balances,
            source="quickbooks",
            period_start=self.start_date,
            period_end=self.end_date,
            metadata={
                "realm_id": self.realm_id,
                "sandbox": self.sandbox,
                "purchase_count": len(purchases),
                "deposit_count": len(deposits),
                "invoice_count": len(invoices),
                "bill_count": len(bills),
            },
        )

        logger.info(
            "QuickBooks pull complete: %d transactions, %d invoices/bills, %d balances",
            len(all_transactions), len(all_invoices), len(balances),
        )
        return dataset

    # ------------------------------------------------------------------
    # Auth & health
    # ------------------------------------------------------------------

    async def validate_credentials(self) -> bool:
        """Validate QuickBooks OAuth2 credentials by making a test API call."""
        if not all([self.client_id, self.client_secret, self.refresh_token, self.realm_id]):
            return False

        try:
            data = await self._api_get("companyinfo/" + self.realm_id)
            return "CompanyInfo" in data
        except Exception as e:
            logger.warning("QuickBooks credential validation failed: %s", e)
            return False

    async def health_check(self) -> dict[str, Any]:
        """Check QuickBooks connectivity and API health."""
        try:
            data = await self._api_get("companyinfo/" + self.realm_id)
            info = data.get("CompanyInfo", {})
            return {
                "connector": self.name,
                "healthy": True,
                "error": None,
                "company_name": info.get("CompanyName"),
                "country": info.get("Country"),
                "sandbox": self.sandbox,
            }
        except Exception as e:
            return {
                "connector": self.name,
                "healthy": False,
                "error": str(e),
                "sandbox": self.sandbox,
            }

    def get_authorization_url(self, redirect_uri: str, state: str = "") -> str:
        """Get the QuickBooks OAuth2 authorization URL.

        Direct the user to this URL to begin the OAuth2 flow.
        """
        mgr = self._ensure_token_manager()
        return mgr.get_authorization_url(
            authorize_url=_QBO_AUTH_URL,
            redirect_uri=redirect_uri,
            state=state,
        )

    async def handle_callback(self, code: str, redirect_uri: str) -> None:
        """Handle the OAuth2 callback after the user authorizes.

        Exchanges the authorization code for tokens and stores them.
        """
        mgr = self._ensure_token_manager()
        await mgr.exchange_code(code=code, redirect_uri=redirect_uri)
        logger.info("QuickBooks authorization complete")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_date(raw: str) -> date:
        """Parse a QBO date string (YYYY-MM-DD)."""
        if not raw:
            return date.today()
        return datetime.strptime(raw[:10], "%Y-%m-%d").date()

    @staticmethod
    def _map_qbo_category(account_name: str) -> ExpenseCategory | None:
        """Map a QBO account name to a FiscalPilot expense category."""
        if not account_name:
            return None
        if account_name in _QBO_CATEGORY_MAP:
            return _QBO_CATEGORY_MAP[account_name]
        lower = account_name.lower()
        for keyword, cat in _QBO_CATEGORY_MAP.items():
            if keyword.lower() in lower:
                return cat
        return ExpenseCategory.OTHER

    @staticmethod
    def _map_account_type(qbo_type: str) -> str:
        """Map QBO account types to simplified types."""
        mapping = {
            "Bank": "checking",
            "Credit Card": "credit",
            "Other Current Asset": "savings",
            "Other Current Liability": "credit",
            "Accounts Receivable": "receivable",
            "Accounts Payable": "payable",
        }
        return mapping.get(qbo_type, "other")
