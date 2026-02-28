"""
Plaid Connector — full integration with Plaid API for bank data.

Pulls bank transactions, account balances, and institution metadata
via the Plaid API. Supports both Link flow (browser-based) and
direct access_token usage.

Authentication: Plaid API keys + access_token per institution link.
Requires: `pip install fiscalpilot[plaid]`

Plaid API docs:
  https://plaid.com/docs/
"""

from __future__ import annotations

import contextlib
import logging
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any

import httpx

from fiscalpilot.connectors.base import BaseConnector
from fiscalpilot.models.financial import (
    AccountBalance,
    ExpenseCategory,
    FinancialDataset,
    Transaction,
    TransactionType,
)

if TYPE_CHECKING:
    from fiscalpilot.models.company import CompanyProfile

logger = logging.getLogger("fiscalpilot.connectors.plaid")

# Plaid environments
_PLAID_ENVS = {
    "sandbox": "https://sandbox.plaid.com",
    "development": "https://development.plaid.com",
    "production": "https://production.plaid.com",
}

# Map Plaid personal_finance_category to FiscalPilot categories
_PLAID_CATEGORY_MAP: dict[str, ExpenseCategory] = {
    # Plaid primary categories
    "INCOME": ExpenseCategory.OTHER,
    "TRANSFER_IN": ExpenseCategory.OTHER,
    "TRANSFER_OUT": ExpenseCategory.OTHER,
    "LOAN_PAYMENTS": ExpenseCategory.INTEREST,
    "BANK_FEES": ExpenseCategory.OTHER,
    "ENTERTAINMENT": ExpenseCategory.MEALS,
    "FOOD_AND_DRINK": ExpenseCategory.MEALS,
    "GENERAL_MERCHANDISE": ExpenseCategory.SUPPLIES,
    "HOME_IMPROVEMENT": ExpenseCategory.MAINTENANCE,
    "MEDICAL": ExpenseCategory.INSURANCE,
    "PERSONAL_CARE": ExpenseCategory.OTHER,
    "GENERAL_SERVICES": ExpenseCategory.PROFESSIONAL_FEES,
    "GOVERNMENT_AND_NON_PROFIT": ExpenseCategory.TAXES,
    "TRANSPORTATION": ExpenseCategory.TRAVEL,
    "TRAVEL": ExpenseCategory.TRAVEL,
    "RENT_AND_UTILITIES": ExpenseCategory.RENT,
    # Detailed categories
    "RENT_AND_UTILITIES_GAS_AND_ELECTRICITY": ExpenseCategory.UTILITIES,
    "RENT_AND_UTILITIES_INTERNET_AND_CABLE": ExpenseCategory.UTILITIES,
    "RENT_AND_UTILITIES_RENT": ExpenseCategory.RENT,
    "RENT_AND_UTILITIES_SEWAGE_AND_WASTE_MANAGEMENT": ExpenseCategory.UTILITIES,
    "RENT_AND_UTILITIES_TELEPHONE": ExpenseCategory.UTILITIES,
    "RENT_AND_UTILITIES_WATER": ExpenseCategory.UTILITIES,
    "FOOD_AND_DRINK_GROCERIES": ExpenseCategory.SUPPLIES,
    "FOOD_AND_DRINK_RESTAURANTS": ExpenseCategory.MEALS,
    "TRANSPORTATION_GAS": ExpenseCategory.TRAVEL,
    "TRANSPORTATION_PARKING": ExpenseCategory.TRAVEL,
    "TRANSPORTATION_PUBLIC_TRANSIT": ExpenseCategory.TRAVEL,
    "TRANSPORTATION_TAXIS_AND_RIDE_SHARES": ExpenseCategory.TRAVEL,
    "GENERAL_MERCHANDISE_OFFICE_SUPPLIES": ExpenseCategory.SUPPLIES,
    "GENERAL_MERCHANDISE_SOFTWARE": ExpenseCategory.SOFTWARE,
    "GENERAL_MERCHANDISE_SUBSCRIPTIONS": ExpenseCategory.SUBSCRIPTIONS,
    "GENERAL_SERVICES_ACCOUNTING_AND_FINANCIAL_PLANNING": ExpenseCategory.PROFESSIONAL_FEES,
    "GENERAL_SERVICES_INSURANCE": ExpenseCategory.INSURANCE,
    "GENERAL_SERVICES_LEGAL": ExpenseCategory.PROFESSIONAL_FEES,
    "GENERAL_SERVICES_POSTAGE_AND_SHIPPING": ExpenseCategory.SHIPPING,
}


class PlaidConnector(BaseConnector):
    """Pull bank transaction data via the Plaid API.

    Supports multiple linked bank accounts. Each bank connection requires
    a Plaid access_token obtained through the Plaid Link flow.

    Usage::

        connector = PlaidConnector(credentials={
            "client_id": "...",
            "secret": "...",
            "access_tokens": ["access-sandbox-..."],  # One per linked bank
        })
        dataset = await connector.pull(company_profile)

    For single bank account::

        connector = PlaidConnector(credentials={
            "client_id": "...",
            "secret": "...",
            "access_token": "access-sandbox-...",
        })

    Environments: "sandbox" (default), "development", "production"
    """

    name = "plaid"
    description = "Pull bank transaction data via Plaid API"

    def __init__(
        self,
        credentials: dict[str, Any] | None = None,
        *,
        environment: str = "sandbox",
        start_date: date | None = None,
        end_date: date | None = None,
        days_back: int = 90,
        **options: Any,
    ) -> None:
        super().__init__(credentials, **options)
        creds = credentials or {}

        self.client_id: str = creds.get("client_id", "")
        self.secret: str = creds.get("secret", "")
        self.environment = environment or creds.get("environment", "sandbox")

        # Support single or multiple access tokens
        if "access_tokens" in creds:
            self.access_tokens: list[str] = creds["access_tokens"]
        elif "access_token" in creds:
            self.access_tokens = [creds["access_token"]]
        else:
            self.access_tokens = []

        self.start_date = start_date or (date.today() - timedelta(days=days_back))
        self.end_date = end_date or date.today()

        self._base_url = _PLAID_ENVS.get(self.environment, _PLAID_ENVS["sandbox"])
        self._http: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create a reusable httpx client."""
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                timeout=60.0,
                headers={"Content-Type": "application/json"},
            )
        return self._http

    async def close(self) -> None:
        """Clean up HTTP client."""
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    # ------------------------------------------------------------------
    # Plaid Link flow
    # ------------------------------------------------------------------

    async def create_link_token(
        self,
        user_id: str = "fiscalpilot_user",
        *,
        products: list[str] | None = None,
        country_codes: list[str] | None = None,
        language: str = "en",
        redirect_uri: str | None = None,
    ) -> str:
        """Create a Link token to initialize Plaid Link.

        This is step 1 of the Plaid integration flow.

        Args:
            user_id: Unique identifier for the end user.
            products: Plaid products to enable (default: transactions).
            country_codes: Countries to show institutions for (default: US).
            language: Language for Link interface.
            redirect_uri: OAuth redirect URI (for OAuth institutions).

        Returns:
            link_token to use with Plaid Link.
        """
        payload: dict[str, Any] = {
            "user": {"client_user_id": user_id},
            "client_name": "FiscalPilot",
            "products": products or ["transactions"],
            "country_codes": country_codes or ["US"],
            "language": language,
        }

        if redirect_uri:
            payload["redirect_uri"] = redirect_uri

        data = await self._api_post("link/token/create", payload)
        return data["link_token"]

    async def exchange_public_token(self, public_token: str) -> str:
        """Exchange a public_token for an access_token.

        This is step 3 of the Plaid integration flow, after user
        completes authorization in Plaid Link.

        Args:
            public_token: The public_token from Plaid Link callback.

        Returns:
            access_token to use for API calls.
        """
        data = await self._api_post(
            "item/public_token/exchange",
            {
                "public_token": public_token,
            },
        )

        access_token = data["access_token"]

        # Add to our list of tokens
        if access_token not in self.access_tokens:
            self.access_tokens.append(access_token)

        # Store the token for future use
        self._save_access_tokens()

        logger.info("Plaid: Exchanged public_token for access_token")
        return access_token

    def _save_access_tokens(self) -> None:
        """Save access tokens to disk for persistence."""
        import json
        from pathlib import Path

        token_dir = Path.home() / ".fiscalpilot" / "tokens"
        token_dir.mkdir(parents=True, exist_ok=True)

        token_file = token_dir / "plaid.json"
        data = {
            "client_id": self.client_id,
            "environment": self.environment,
            "access_tokens": self.access_tokens,
        }

        token_file.write_text(json.dumps(data, indent=2))
        token_file.chmod(0o600)
        logger.debug("Saved Plaid tokens to %s", token_file)

    def _load_access_tokens(self) -> None:
        """Load access tokens from disk."""
        import json
        from pathlib import Path

        token_file = Path.home() / ".fiscalpilot" / "tokens" / "plaid.json"

        if token_file.exists():
            try:
                data = json.loads(token_file.read_text())
                stored_tokens = data.get("access_tokens", [])
                # Merge with any tokens from credentials
                for token in stored_tokens:
                    if token not in self.access_tokens:
                        self.access_tokens.append(token)
                logger.debug("Loaded %d Plaid tokens from disk", len(stored_tokens))
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Failed to load Plaid tokens: %s", e)

    async def authorize(
        self,
        *,
        port: int = 8080,
        timeout: float = 300,
        user_id: str = "fiscalpilot_user",
        open_browser: bool = True,
    ) -> str:
        """Complete interactive Plaid Link flow via browser.

        Opens browser with Plaid Link, waits for user to connect bank,
        then exchanges the public_token for an access_token.

        Args:
            port: Local port for callback server.
            timeout: Seconds to wait for user to complete auth.
            user_id: Unique identifier for the user.
            open_browser: Automatically open browser.

        Returns:
            The new access_token.

        Raises:
            TimeoutError: If user doesn't complete auth in time.
            ValueError: If authorization fails.
        """
        import asyncio
        import threading
        import webbrowser
        from http.server import BaseHTTPRequestHandler, HTTPServer

        if not self.client_id or not self.secret:
            raise ValueError(
                "client_id and secret are required. Get them from https://dashboard.plaid.com/developers/keys"
            )

        # Create link token
        link_token = await self.create_link_token(user_id=user_id)

        # State for callback
        public_token: str | None = None
        error: str | None = None

        # HTML page that loads Plaid Link
        html_page = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>FiscalPilot - Connect Bank</title>
            <script src="https://cdn.plaid.com/link/v2/stable/link-initialize.js"></script>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif;
                       display: flex; justify-content: center; align-items: center;
                       height: 100vh; margin: 0; background: #f0f4f8; }}
                .card {{ background: white; padding: 40px; border-radius: 12px;
                        box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; }}
                h1 {{ color: #333; margin-bottom: 20px; }}
                #status {{ color: #666; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="card">
                <h1>🏦 Connect Your Bank</h1>
                <p>Plaid Link will open automatically...</p>
                <p id="status"></p>
            </div>
            <script>
                const handler = Plaid.create({{
                    token: '{link_token}',
                    onSuccess: (public_token, metadata) => {{
                        document.getElementById('status').innerText = 'Connected! Closing...';
                        fetch('/callback?public_token=' + public_token)
                            .then(() => window.close());
                    }},
                    onExit: (err, metadata) => {{
                        if (err) {{
                            fetch('/callback?error=' + encodeURIComponent(err.display_message || err.error_message));
                        }}
                        document.getElementById('status').innerText = 'You can close this window.';
                    }},
                }});
                handler.open();
            </script>
        </body>
        </html>
        """

        class PlaidCallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                nonlocal public_token, error
                from urllib.parse import parse_qs, urlparse

                parsed = urlparse(self.path)
                params = parse_qs(parsed.query)

                if parsed.path == "/":
                    # Serve the HTML page
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.end_headers()
                    self.wfile.write(html_page.encode())
                elif parsed.path == "/callback":
                    if "public_token" in params:
                        public_token = params["public_token"][0]
                    if "error" in params:
                        error = params["error"][0]
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"OK")
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, format: str, *args) -> None:  # noqa: A002
                pass

        # Start server
        server = HTTPServer(("localhost", port), PlaidCallbackHandler)
        thread = threading.Thread(target=lambda: server.handle_request() or server.handle_request(), daemon=True)
        thread.start()

        # Open browser
        url = f"http://localhost:{port}/"
        logger.info("Opening browser for Plaid Link")

        if open_browser:
            webbrowser.open(url)

        # Wait for callback
        start_time = asyncio.get_event_loop().time()
        while not public_token and not error:
            if asyncio.get_event_loop().time() - start_time > timeout:
                server.server_close()
                raise TimeoutError(f"Plaid authorization timed out after {timeout}s")
            await asyncio.sleep(0.5)

        server.server_close()

        if error:
            raise ValueError(f"Plaid authorization failed: {error}")

        # Exchange public token for access token
        access_token = await self.exchange_public_token(public_token)  # type: ignore

        logger.info("Plaid bank connected successfully")
        return access_token

    def is_connected(self) -> bool:
        """Check if any bank accounts are connected."""
        self._load_access_tokens()
        return len(self.access_tokens) > 0

    async def disconnect(self, access_token: str | None = None) -> bool:
        """Remove a bank connection.

        Args:
            access_token: Specific token to remove. If None, removes all.

        Returns:
            True if any connections were removed.
        """
        if access_token:
            if access_token in self.access_tokens:
                # Also call Plaid to invalidate
                with contextlib.suppress(Exception):
                    await self._api_post("item/remove", {"access_token": access_token})
                self.access_tokens.remove(access_token)
                self._save_access_tokens()
                return True
            return False
        else:
            # Remove all
            for token in self.access_tokens[:]:
                with contextlib.suppress(Exception):
                    await self._api_post("item/remove", {"access_token": token})
            removed = len(self.access_tokens) > 0
            self.access_tokens.clear()
            self._save_access_tokens()
            return removed

    async def get_institutions(self) -> list[dict[str, Any]]:
        """Get info about connected bank institutions.

        Returns:
            List of institution info for each connected bank.
        """
        self._load_access_tokens()
        institutions = []

        for access_token in self.access_tokens:
            try:
                data = await self._api_post("item/get", {"access_token": access_token})
                item = data.get("item", {})

                inst_id = item.get("institution_id")
                if inst_id:
                    inst_data = await self._api_post(
                        "institutions/get_by_id",
                        {
                            "institution_id": inst_id,
                            "country_codes": ["US"],
                        },
                    )
                    institution = inst_data.get("institution", {})
                    institutions.append(
                        {
                            "id": inst_id,
                            "name": institution.get("name", "Unknown"),
                            "products": item.get("available_products", []),
                        }
                    )
            except Exception as e:
                logger.warning("Failed to get institution info: %s", e)

        return institutions

    # ------------------------------------------------------------------
    # API helpers
    # ------------------------------------------------------------------

    async def _api_post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Make an authenticated POST request to the Plaid API."""
        client = await self._get_client()

        url = f"{self._base_url}/{endpoint}"

        # Plaid uses client_id + secret in the body, not headers
        payload = {
            "client_id": self.client_id,
            "secret": self.secret,
            **payload,
        }

        resp = await client.post(url, json=payload)

        # Plaid returns errors as 400 with JSON body
        if resp.status_code >= 400:
            error_data = resp.json()
            error_code = error_data.get("error_code", "UNKNOWN")
            error_msg = error_data.get("error_message", resp.text)

            # Handle specific Plaid errors
            if error_code == "ITEM_LOGIN_REQUIRED":
                raise PermissionError(
                    f"Plaid: Bank connection needs re-authentication. Please re-link through Plaid Link. ({error_msg})"
                )
            elif error_code == "RATE_LIMIT_EXCEEDED":
                import asyncio

                logger.warning("Plaid rate limited, waiting 60s")
                await asyncio.sleep(60)
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
            else:
                raise httpx.HTTPStatusError(
                    f"Plaid API error [{error_code}]: {error_msg}",
                    request=resp.request,
                    response=resp,
                )

        return resp.json()

    # ------------------------------------------------------------------
    # Data fetchers
    # ------------------------------------------------------------------

    async def _fetch_transactions_for_token(self, access_token: str) -> list[Transaction]:
        """Fetch all transactions for a single access token."""
        all_transactions: list[Transaction] = []
        has_more = True
        cursor: str | None = None

        while has_more:
            payload: dict[str, Any] = {
                "access_token": access_token,
                "options": {
                    "include_personal_finance_category": True,
                },
            }

            # Use the sync endpoint with cursor-based pagination
            if cursor:
                payload["cursor"] = cursor
            else:
                # First call: specify date range
                payload["start_date"] = self.start_date.isoformat()
                payload["end_date"] = self.end_date.isoformat()

            data = await self._api_post("transactions/sync", payload)

            # Process added transactions
            added = data.get("added", [])
            for txn in added:
                try:
                    parsed = self._parse_plaid_transaction(txn)
                    if parsed:
                        all_transactions.append(parsed)
                except Exception as e:
                    logger.debug("Skipping Plaid transaction: %s", e)

            # Process modified transactions (update existing)
            modified = data.get("modified", [])
            modified_ids = {f"plaid-{t.get('transaction_id')}" for t in modified}
            all_transactions = [t for t in all_transactions if t.id not in modified_ids]
            for txn in modified:
                try:
                    parsed = self._parse_plaid_transaction(txn)
                    if parsed:
                        all_transactions.append(parsed)
                except Exception as e:
                    logger.debug("Skipping modified Plaid transaction: %s", e)

            # Remove deleted transactions
            removed = data.get("removed", [])
            removed_ids = {f"plaid-{r.get('transaction_id')}" for r in removed}
            all_transactions = [t for t in all_transactions if t.id not in removed_ids]

            has_more = data.get("has_more", False)
            cursor = data.get("next_cursor")

        return all_transactions

    async def _fetch_balances_for_token(self, access_token: str) -> list[AccountBalance]:
        """Fetch account balances for a single access token."""
        data = await self._api_post(
            "accounts/balance/get",
            {
                "access_token": access_token,
            },
        )

        balances: list[AccountBalance] = []
        for acct in data.get("accounts", []):
            try:
                balance_data = acct.get("balances", {})
                current = balance_data.get("current")
                if current is None:
                    continue

                # Map Plaid account types
                acct_type = acct.get("type", "")
                acct_subtype = acct.get("subtype", "")
                fp_type = self._map_plaid_account_type(acct_type, acct_subtype)

                # Institution info
                institution = data.get("item", {}).get("institution_id", "")

                balance = AccountBalance(
                    account_name=acct.get("name", acct.get("official_name", "Unknown")),
                    account_type=fp_type,
                    balance=float(current),
                    as_of=datetime.now(),
                    institution=institution or None,
                )
                balances.append(balance)
            except Exception as e:
                logger.debug("Skipping Plaid account: %s", e)

        return balances

    # ------------------------------------------------------------------
    # Main pull
    # ------------------------------------------------------------------

    async def pull(self, company: CompanyProfile) -> FinancialDataset:
        """Pull all bank data from Plaid across all linked accounts.

        Fetches transactions and balances for each access_token in parallel.

        Args:
            company: Company profile for context.

        Returns:
            Normalized FinancialDataset with all Plaid data.
        """
        import asyncio

        if not self.access_tokens:
            raise ValueError("No Plaid access tokens configured. Please link a bank account through Plaid Link first.")

        logger.info(
            "Pulling Plaid data for %s (%d linked accounts, %s to %s)",
            company.name,
            len(self.access_tokens),
            self.start_date,
            self.end_date,
        )

        # Fetch transactions and balances for all tokens in parallel
        txn_tasks = [asyncio.create_task(self._fetch_transactions_for_token(token)) for token in self.access_tokens]
        bal_tasks = [asyncio.create_task(self._fetch_balances_for_token(token)) for token in self.access_tokens]

        txn_results = await asyncio.gather(*txn_tasks, return_exceptions=True)
        bal_results = await asyncio.gather(*bal_tasks, return_exceptions=True)

        # Aggregate results, log errors for failed tokens
        all_transactions: list[Transaction] = []
        all_balances: list[AccountBalance] = []

        for i, result in enumerate(txn_results):
            if isinstance(result, Exception):
                logger.error("Failed to fetch transactions for token %d: %s", i, result)
            else:
                all_transactions.extend(result)

        for i, result in enumerate(bal_results):
            if isinstance(result, Exception):
                logger.error("Failed to fetch balances for token %d: %s", i, result)
            else:
                all_balances.extend(result)

        dataset = FinancialDataset(
            transactions=all_transactions,
            balances=all_balances,
            source="plaid",
            period_start=self.start_date,
            period_end=self.end_date,
            metadata={
                "environment": self.environment,
                "linked_accounts": len(self.access_tokens),
                "transaction_count": len(all_transactions),
                "balance_count": len(all_balances),
            },
        )

        logger.info(
            "Plaid pull complete: %d transactions, %d balances from %d accounts",
            len(all_transactions),
            len(all_balances),
            len(self.access_tokens),
        )
        return dataset

    # ------------------------------------------------------------------
    # Auth & health
    # ------------------------------------------------------------------

    async def validate_credentials(self) -> bool:
        """Validate Plaid API credentials."""
        if not all([self.client_id, self.secret]):
            return False

        if not self.access_tokens:
            # Can still validate API keys without access tokens
            try:
                await self._api_post(
                    "institutions/get",
                    {
                        "count": 1,
                        "offset": 0,
                        "country_codes": ["US"],
                    },
                )
                return True
            except Exception:
                return False

        # Validate by fetching account info for the first token
        try:
            await self._api_post(
                "accounts/get",
                {
                    "access_token": self.access_tokens[0],
                },
            )
            return True
        except Exception as e:
            logger.warning("Plaid credential validation failed: %s", e)
            return False

    async def health_check(self) -> dict[str, Any]:
        """Check Plaid connectivity and account health."""
        results: dict[str, Any] = {
            "connector": self.name,
            "environment": self.environment,
            "linked_accounts": len(self.access_tokens),
        }

        if not self.access_tokens:
            results["healthy"] = False
            results["error"] = "No bank accounts linked"
            return results

        # Check each linked account
        account_statuses = []
        for i, token in enumerate(self.access_tokens):
            try:
                data = await self._api_post("accounts/get", {"access_token": token})
                item = data.get("item", {})
                accounts = data.get("accounts", [])
                account_statuses.append(
                    {
                        "index": i,
                        "institution_id": item.get("institution_id"),
                        "accounts": len(accounts),
                        "healthy": True,
                    }
                )
            except Exception as e:
                account_statuses.append(
                    {
                        "index": i,
                        "healthy": False,
                        "error": str(e),
                    }
                )

        all_healthy = all(s["healthy"] for s in account_statuses)
        results["healthy"] = all_healthy
        results["error"] = None if all_healthy else "Some accounts have issues"
        results["accounts"] = account_statuses

        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_plaid_transaction(self, txn: dict[str, Any]) -> Transaction | None:
        """Parse a Plaid transaction into a FiscalPilot Transaction."""
        txn_date_str = txn.get("date", txn.get("authorized_date", ""))
        if not txn_date_str:
            return None

        txn_date = datetime.strptime(txn_date_str, "%Y-%m-%d").date()
        amount = float(txn.get("amount", 0))

        # Plaid: positive amounts = spending, negative = income
        # (opposite of our convention)
        if amount > 0:
            txn_type = TransactionType.EXPENSE
        elif amount < 0:
            txn_type = TransactionType.INCOME
            amount = abs(amount)
        else:
            return None  # Skip zero-amount transactions

        # Category from personal_finance_category (Plaid's newer, better system)
        pfc = txn.get("personal_finance_category", {})
        primary = pfc.get("primary", "")
        detailed = pfc.get("detailed", "")
        category = self._map_plaid_category(primary, detailed)

        # Merchant / vendor
        merchant = txn.get("merchant_name") or txn.get("name", "")

        # Additional context
        account_id = txn.get("account_id", "")
        payment_channel = txn.get("payment_channel", "")  # online, in store, other

        return Transaction(
            id=f"plaid-{txn.get('transaction_id', '')}",
            date=txn_date,
            amount=amount,
            type=txn_type,
            category=category,
            description=txn.get("name", ""),
            vendor=merchant or None,
            account=account_id or None,
            tags=[
                f"plaid:{payment_channel}" if payment_channel else "plaid:txn",
                "plaid:pending" if txn.get("pending") else "plaid:posted",
            ],
            raw_data=txn,
        )

    @staticmethod
    def _map_plaid_category(primary: str, detailed: str) -> ExpenseCategory | None:
        """Map Plaid personal_finance_category to FiscalPilot category."""
        if not primary:
            return None

        # Try detailed category first (more specific)
        if detailed and detailed in _PLAID_CATEGORY_MAP:
            return _PLAID_CATEGORY_MAP[detailed]

        # Fall back to primary
        if primary in _PLAID_CATEGORY_MAP:
            return _PLAID_CATEGORY_MAP[primary]

        return ExpenseCategory.OTHER

    @staticmethod
    def _map_plaid_account_type(acct_type: str, subtype: str) -> str:
        """Map Plaid account types to simplified types."""
        type_map = {
            "depository": {
                "checking": "checking",
                "savings": "savings",
                "money market": "savings",
                "cd": "savings",
            },
            "credit": {
                "credit card": "credit",
            },
            "loan": {
                "mortgage": "loan",
                "student": "loan",
                "auto": "loan",
            },
            "investment": {
                "": "investment",
            },
        }

        subtype_map = type_map.get(acct_type, {})
        if subtype_map:
            for key, value in subtype_map.items():
                if key in subtype.lower():
                    return value
        return "other"
