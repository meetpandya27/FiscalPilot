"""
Xero Connector — full integration with Xero Accounting API.

Pulls bank transactions, invoices (receivable + payable), payments,
contacts, and account balances via the Xero API v2.

Authentication: OAuth2 (handled by OAuth2TokenManager).
Requires: `pip install fiscalpilot[xero]`

Xero API docs:
  https://developer.xero.com/documentation/api/accounting/overview
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

logger = logging.getLogger("fiscalpilot.connectors.xero")

# Xero API endpoints
_XERO_API_URL = "https://api.xero.com/api.xro/2.0"
_XERO_TOKEN_URL = "https://identity.xero.com/connect/token"
_XERO_AUTH_URL = "https://login.xero.com/identity/connect/authorize"
_XERO_CONNECTIONS_URL = "https://api.xero.com/connections"

# Xero pagination
_PAGE_SIZE = 100  # Xero uses page numbers, 100 records per page

# Map Xero account codes/types to our categories
_XERO_CATEGORY_MAP: dict[str, ExpenseCategory] = {
    "DIRECTCOSTS": ExpenseCategory.INVENTORY,
    "OVERHEADS": ExpenseCategory.OTHER,
    "DEPRECIATN": ExpenseCategory.DEPRECIATION,
    "OTHERINCOME": ExpenseCategory.OTHER,
    "advertising": ExpenseCategory.MARKETING,
    "bank fees": ExpenseCategory.OTHER,
    "cleaning": ExpenseCategory.MAINTENANCE,
    "consulting": ExpenseCategory.PROFESSIONAL_FEES,
    "entertainment": ExpenseCategory.MEALS,
    "freight": ExpenseCategory.SHIPPING,
    "general expenses": ExpenseCategory.MISCELLANEOUS,
    "insurance": ExpenseCategory.INSURANCE,
    "interest": ExpenseCategory.INTEREST,
    "legal": ExpenseCategory.PROFESSIONAL_FEES,
    "light, power, heating": ExpenseCategory.UTILITIES,
    "motor vehicle": ExpenseCategory.TRAVEL,
    "office expenses": ExpenseCategory.SUPPLIES,
    "postage": ExpenseCategory.SHIPPING,
    "printing": ExpenseCategory.SUPPLIES,
    "rent": ExpenseCategory.RENT,
    "repairs": ExpenseCategory.MAINTENANCE,
    "salaries": ExpenseCategory.PAYROLL,
    "wages": ExpenseCategory.PAYROLL,
    "subscriptions": ExpenseCategory.SUBSCRIPTIONS,
    "superannuation": ExpenseCategory.PAYROLL,
    "telephone": ExpenseCategory.UTILITIES,
    "training": ExpenseCategory.OTHER,
    "travel": ExpenseCategory.TRAVEL,
    "utilities": ExpenseCategory.UTILITIES,
}


class XeroConnector(BaseConnector):
    """Pull financial data from Xero.

    Uses the Xero Accounting API to fetch:
    - Bank transactions (spend + receive money)
    - Invoices (accounts receivable)
    - Bills (accounts payable)
    - Payments
    - Account balances (via Trial Balance report)
    - Contacts (vendor information)

    Authentication is handled via OAuth2. Provide credentials or use the
    interactive flow.

    Usage::

        connector = XeroConnector(credentials={
            "client_id": "...",
            "client_secret": "...",
            "refresh_token": "...",
            "tenant_id": "...",  # Xero organisation ID
        })
        dataset = await connector.pull(company_profile)
    """

    name = "xero"
    description = "Pull financial data from Xero accounting"

    def __init__(
        self,
        credentials: dict[str, Any] | None = None,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        **options: Any,
    ) -> None:
        super().__init__(credentials, **options)
        creds = credentials or {}

        self.client_id: str = creds.get("client_id", "")
        self.client_secret: str = creds.get("client_secret", "")
        self.refresh_token: str = creds.get("refresh_token", "")
        self.tenant_id: str = creds.get("tenant_id", "")

        self.start_date = start_date
        self.end_date = end_date or date.today()

        self._token_manager: OAuth2TokenManager | None = None
        self._http: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _ensure_token_manager(self) -> OAuth2TokenManager:
        """Initialize the OAuth2 token manager."""
        if self._token_manager is None:
            self._token_manager = OAuth2TokenManager(
                provider="xero",
                client_id=self.client_id,
                client_secret=self.client_secret,
                token_url=_XERO_TOKEN_URL,
                scopes=["openid", "profile", "email", "accounting.transactions",
                        "accounting.reports.read", "accounting.contacts",
                        "accounting.settings", "offline_access"],
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

    async def _api_get(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Make an authenticated GET request to the Xero API."""
        mgr = self._ensure_token_manager()
        token = await mgr.get_access_token()
        client = await self._get_client()

        url = f"{_XERO_API_URL}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Xero-Tenant-Id": self.tenant_id,
            "Accept": "application/json",
        }

        resp = await client.get(url, headers=headers, params=params)

        # Handle 401 → refresh and retry
        if resp.status_code == 401:
            logger.info("Xero token expired, refreshing...")
            await mgr.refresh()
            token = await mgr.get_access_token()
            headers["Authorization"] = f"Bearer {token}"
            resp = await client.get(url, headers=headers, params=params)

        # Handle 429 rate limiting
        if resp.status_code == 429:
            import asyncio
            retry_after = int(resp.headers.get("Retry-After", "5"))
            logger.warning("Xero rate limited, waiting %ds", retry_after)
            await asyncio.sleep(retry_after)
            resp = await client.get(url, headers=headers, params=params)

        resp.raise_for_status()
        return resp.json()

    async def _paginated_get(
        self, endpoint: str, key: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Fetch all pages of a paginated Xero endpoint.

        Xero uses ?page=N with 100 records per page.
        """
        all_results: list[dict[str, Any]] = []
        page = 1
        base_params = dict(params or {})

        while True:
            base_params["page"] = page
            data = await self._api_get(endpoint, params=base_params)
            items = data.get(key, [])

            if not items:
                break

            all_results.extend(items)

            # If fewer than page size, it's the last page
            if len(items) < _PAGE_SIZE:
                break

            page += 1

        return all_results

    # ------------------------------------------------------------------
    # Data fetchers
    # ------------------------------------------------------------------

    async def _fetch_bank_transactions(self) -> list[Transaction]:
        """Fetch bank transactions (spend/receive money)."""
        params: dict[str, Any] = {}
        if self.start_date:
            # Xero date filter using "where" parameter
            params["where"] = (
                f'Date >= DateTime({self.start_date.year},{self.start_date.month},{self.start_date.day}) '
                f'AND Date <= DateTime({self.end_date.year},{self.end_date.month},{self.end_date.day})'
            )

        raw = await self._paginated_get("BankTransactions", "BankTransactions", params)

        transactions: list[Transaction] = []
        for bt in raw:
            try:
                status = bt.get("Status", "")
                if status == "DELETED":
                    continue

                txn_date = self._parse_xero_date(bt.get("Date", ""))
                bt_type = bt.get("Type", "")  # SPEND or RECEIVE
                total = float(bt.get("Total", 0))

                # Type mapping
                if bt_type == "SPEND":
                    txn_type = TransactionType.EXPENSE
                elif bt_type == "RECEIVE":
                    txn_type = TransactionType.INCOME
                else:
                    txn_type = TransactionType.OTHER

                # Contact (vendor/customer) info
                contact = bt.get("Contact", {})
                vendor_name = contact.get("Name", "") if contact else ""

                # Line items for description and category
                line_items = bt.get("LineItems", [])
                desc_parts = []
                category = None
                for li in line_items:
                    desc = li.get("Description", "")
                    if desc:
                        desc_parts.append(desc)
                    acct_code = li.get("AccountCode", "")
                    if acct_code and not category:
                        category = self._map_xero_category(acct_code)

                description = "; ".join(desc_parts[:3]) if desc_parts else bt.get("Reference", f"Bank Txn #{bt.get('BankTransactionID', '')[:8]}")

                # Bank account
                bank_account = bt.get("BankAccount", {})
                account_name = bank_account.get("Name", "") if bank_account else ""

                txn = Transaction(
                    id=f"xero-bt-{bt.get('BankTransactionID', '')}",
                    date=txn_date,
                    amount=abs(total),
                    type=txn_type,
                    category=category,
                    description=description,
                    vendor=vendor_name or None,
                    account=account_name or None,
                    tags=[f"xero:{bt_type.lower()}", f"xero:status:{status.lower()}"],
                    raw_data=bt,
                )
                transactions.append(txn)
            except Exception as e:
                logger.debug("Skipping Xero bank transaction: %s", e)

        logger.info("Fetched %d bank transactions from Xero", len(transactions))
        return transactions

    async def _fetch_invoices(self) -> list[Invoice]:
        """Fetch invoices (accounts receivable)."""
        params: dict[str, Any] = {}
        if self.start_date:
            params["where"] = (
                f'Date >= DateTime({self.start_date.year},{self.start_date.month},{self.start_date.day}) '
                f'AND Date <= DateTime({self.end_date.year},{self.end_date.month},{self.end_date.day})'
            )

        raw = await self._paginated_get("Invoices", "Invoices", params)

        invoices: list[Invoice] = []
        for inv in raw:
            try:
                inv_type = inv.get("Type", "")
                if inv_type not in ("ACCREC", "ACCPAY"):
                    continue

                status = inv.get("Status", "")
                if status == "DELETED" or status == "VOIDED":
                    continue

                contact = inv.get("Contact", {})
                contact_name = contact.get("Name", "Unknown") if contact else "Unknown"

                due_date_str = inv.get("DueDate", inv.get("Date", ""))
                due_date = self._parse_xero_date(due_date_str)
                total = float(inv.get("Total", 0))
                amount_paid = float(inv.get("AmountPaid", 0))

                # Xero statuses: DRAFT, SUBMITTED, AUTHORISED, PAID, VOIDED, DELETED
                if status == "PAID":
                    fp_status = "paid"
                elif status in ("AUTHORISED", "SUBMITTED") and due_date < date.today():
                    fp_status = "overdue"
                elif status == "DRAFT":
                    fp_status = "draft"
                else:
                    fp_status = "pending"

                # Determine paid_date from payments
                payments = inv.get("Payments", [])
                paid_date = None
                if payments:
                    last_payment = payments[-1]
                    paid_date = self._parse_xero_date(last_payment.get("Date", ""))

                # Parse line items
                line_items: list[LineItem] = []
                for li in inv.get("LineItems", []):
                    line = LineItem(
                        description=li.get("Description", "Item"),
                        quantity=float(li.get("Quantity", 1)),
                        unit_price=float(li.get("UnitAmount", 0)),
                        total=float(li.get("LineAmount", 0)),
                        category=self._map_xero_category(li.get("AccountCode", "")),
                    )
                    line_items.append(line)

                invoice = Invoice(
                    id=f"xero-inv-{inv.get('InvoiceID', '')}",
                    invoice_number=inv.get("InvoiceNumber"),
                    vendor=contact_name,
                    amount=total,
                    due_date=due_date,
                    paid_date=paid_date,
                    status=fp_status,
                    line_items=line_items,
                )
                invoices.append(invoice)
            except Exception as e:
                logger.debug("Skipping Xero invoice: %s", e)

        logger.info("Fetched %d invoices from Xero", len(invoices))
        return invoices

    async def _fetch_account_balances(self) -> list[AccountBalance]:
        """Fetch account balances via Xero's Trial Balance report."""
        # Use Balance Sheet report for a snapshot of account balances
        params = {
            "date": self.end_date.isoformat(),
        }

        try:
            data = await self._api_get("Reports/TrialBalance", params=params)
        except Exception as e:
            logger.warning("Could not fetch Xero trial balance: %s", e)
            return []

        balances: list[AccountBalance] = []
        reports = data.get("Reports", [])
        if not reports:
            return balances

        report = reports[0]
        rows = report.get("Rows", [])

        for section in rows:
            if section.get("RowType") != "Section":
                continue

            for row in section.get("Rows", []):
                if row.get("RowType") != "Row":
                    continue

                cells = row.get("Cells", [])
                if len(cells) < 3:
                    continue

                try:
                    account_name = cells[0].get("Value", "")
                    debit = float(cells[1].get("Value", "0") or "0")
                    credit = float(cells[2].get("Value", "0") or "0")
                    balance_val = debit - credit

                    # Determine account type from the section title
                    section_title = section.get("Title", "").lower()
                    if "bank" in section_title or "cash" in section_title:
                        acct_type = "checking"
                    elif "receivable" in section_title:
                        acct_type = "receivable"
                    elif "payable" in section_title:
                        acct_type = "payable"
                    elif "liability" in section_title:
                        acct_type = "credit"
                    else:
                        acct_type = "other"

                    balance = AccountBalance(
                        account_name=account_name,
                        account_type=acct_type,
                        balance=balance_val,
                        as_of=datetime.now(),
                    )
                    balances.append(balance)
                except (ValueError, IndexError) as e:
                    logger.debug("Skipping Xero balance row: %s", e)

        logger.info("Fetched %d account balances from Xero", len(balances))
        return balances

    # ------------------------------------------------------------------
    # Main pull
    # ------------------------------------------------------------------

    async def pull(self, company: CompanyProfile) -> FinancialDataset:
        """Pull all financial data from Xero.

        Fetches bank transactions, invoices, and account balances
        in parallel.

        Args:
            company: Company profile for context.

        Returns:
            Normalized FinancialDataset with all Xero data.
        """
        import asyncio

        logger.info(
            "Pulling Xero data for %s (tenant: %s)",
            company.name, self.tenant_id,
        )

        # Auto-detect tenant if not provided
        if not self.tenant_id:
            await self._auto_detect_tenant()

        # Fetch all entity types in parallel
        txns_task = asyncio.create_task(self._fetch_bank_transactions())
        invoices_task = asyncio.create_task(self._fetch_invoices())
        balances_task = asyncio.create_task(self._fetch_account_balances())

        transactions, invoices, balances = await asyncio.gather(
            txns_task, invoices_task, balances_task,
        )

        # Separate AR and AP invoices
        ar_invoices = [i for i in invoices if not i.id or "inv" in (i.id or "")]
        ap_invoices = [i for i in invoices if i.id and "bill" in i.id]

        dataset = FinancialDataset(
            transactions=transactions,
            invoices=invoices,
            balances=balances,
            source="xero",
            period_start=self.start_date,
            period_end=self.end_date,
            metadata={
                "tenant_id": self.tenant_id,
                "bank_transaction_count": len(transactions),
                "ar_invoice_count": len(ar_invoices),
                "ap_invoice_count": len(ap_invoices),
            },
        )

        logger.info(
            "Xero pull complete: %d transactions, %d invoices, %d balances",
            len(transactions), len(invoices), len(balances),
        )
        return dataset

    # ------------------------------------------------------------------
    # Auth & health
    # ------------------------------------------------------------------

    async def _auto_detect_tenant(self) -> None:
        """Auto-detect the Xero tenant (organisation) ID."""
        mgr = self._ensure_token_manager()
        token = await mgr.get_access_token()
        client = await self._get_client()

        resp = await client.get(
            _XERO_CONNECTIONS_URL,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
        resp.raise_for_status()

        connections = resp.json()
        if not connections:
            raise ValueError("No Xero organisations found. Please check your credentials.")

        # Use the first connected organisation
        self.tenant_id = connections[0]["tenantId"]
        logger.info(
            "Auto-detected Xero tenant: %s (%s)",
            connections[0].get("tenantName", "Unknown"),
            self.tenant_id,
        )

    async def validate_credentials(self) -> bool:
        """Validate Xero OAuth2 credentials."""
        if not all([self.client_id, self.client_secret, self.refresh_token]):
            return False

        try:
            mgr = self._ensure_token_manager()
            token = await mgr.get_access_token()
            client = await self._get_client()

            resp = await client.get(
                _XERO_CONNECTIONS_URL,
                headers={"Authorization": f"Bearer {token}"},
            )
            return resp.status_code == 200
        except Exception as e:
            logger.warning("Xero credential validation failed: %s", e)
            return False

    async def health_check(self) -> dict[str, Any]:
        """Check Xero connectivity and API health."""
        try:
            mgr = self._ensure_token_manager()
            token = await mgr.get_access_token()
            client = await self._get_client()

            resp = await client.get(
                _XERO_CONNECTIONS_URL,
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            )
            resp.raise_for_status()
            connections = resp.json()

            org_name = connections[0].get("tenantName", "Unknown") if connections else None
            return {
                "connector": self.name,
                "healthy": True,
                "error": None,
                "organisation": org_name,
                "tenant_id": self.tenant_id or (connections[0]["tenantId"] if connections else None),
                "connection_count": len(connections),
            }
        except Exception as e:
            return {
                "connector": self.name,
                "healthy": False,
                "error": str(e),
            }

    def get_authorization_url(self, redirect_uri: str, state: str = "") -> str:
        """Get the Xero OAuth2 authorization URL."""
        mgr = self._ensure_token_manager()
        return mgr.get_authorization_url(
            authorize_url=_XERO_AUTH_URL,
            redirect_uri=redirect_uri,
            state=state,
        )

    async def handle_callback(self, code: str, redirect_uri: str) -> None:
        """Handle the OAuth2 callback after user authorizes."""
        mgr = self._ensure_token_manager()
        await mgr.exchange_code(code=code, redirect_uri=redirect_uri)
        logger.info("Xero authorization complete")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_xero_date(raw: str) -> date:
        """Parse a Xero date string.

        Xero returns dates in two formats:
        - ISO: "2024-01-15"
        - .NET JSON: "/Date(1705276800000+0000)/"
        """
        if not raw:
            return date.today()

        # Handle .NET JSON date format
        if raw.startswith("/Date("):
            import re
            match = re.search(r"/Date\((\d+)", raw)
            if match:
                timestamp_ms = int(match.group(1))
                return datetime.fromtimestamp(timestamp_ms / 1000).date()

        # Handle ISO format
        try:
            return datetime.strptime(raw[:10], "%Y-%m-%d").date()
        except ValueError:
            return date.today()

    @staticmethod
    def _map_xero_category(account_code: str) -> ExpenseCategory | None:
        """Map a Xero account code/name to a FiscalPilot expense category."""
        if not account_code:
            return None

        lower = account_code.lower()
        for keyword, cat in _XERO_CATEGORY_MAP.items():
            if keyword.lower() in lower:
                return cat

        return ExpenseCategory.OTHER
