"""
Toast POS Connector — import restaurant data from Toast.

Toast is the leading restaurant-specific POS system, used by 100,000+ restaurants.
This connector pulls:
- Sales and revenue data
- Menu item performance
- Labor data (hours, costs)
- Guest counts and check averages
- Payment method breakdowns
- Tips and service charges

Requires Toast API credentials:
- Client ID and Client Secret (OAuth2)
- Restaurant External ID

API Documentation: https://doc.toasttab.com/
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any

import httpx

from fiscalpilot.connectors.base import BaseConnector
from fiscalpilot.models.financial import (
    ExpenseCategory,
    FinancialDataset,
    Transaction,
    TransactionType,
)

if TYPE_CHECKING:
    from fiscalpilot.models.company import CompanyProfile

logger = logging.getLogger("fiscalpilot.connectors.toast")

# Toast API endpoints
TOAST_API_BASE = "https://ws-api.toasttab.com"
TOAST_AUTH_URL = "https://ws-api.toasttab.com/authentication/v1/authentication/login"


class ToastOrderSource(str, Enum):
    """Source of Toast orders."""
    
    IN_STORE = "In Store"
    ONLINE = "Online"
    THIRD_PARTY = "Third Party"
    CATERING = "Catering"


class ToastPaymentType(str, Enum):
    """Toast payment types."""
    
    CASH = "Cash"
    CREDIT = "Credit"
    DEBIT = "Debit"
    GIFT_CARD = "Gift Card"
    HOUSE_ACCOUNT = "House Account"
    OTHER = "Other"


@dataclass
class ToastSalesSummary:
    """Daily sales summary from Toast."""
    
    date: date
    net_sales: Decimal
    gross_sales: Decimal
    discounts: Decimal
    voids: Decimal
    refunds: Decimal
    tax_collected: Decimal
    tips: Decimal
    service_charges: Decimal
    guest_count: int
    order_count: int
    
    @property
    def check_average(self) -> Decimal:
        """Average check per order."""
        if self.order_count == 0:
            return Decimal("0")
        return self.net_sales / self.order_count
    
    @property
    def per_guest_average(self) -> Decimal:
        """Average spend per guest."""
        if self.guest_count == 0:
            return Decimal("0")
        return self.net_sales / self.guest_count


@dataclass
class ToastMenuItem:
    """Menu item sales data."""
    
    item_id: str
    name: str
    category: str
    quantity_sold: int
    gross_sales: Decimal
    net_sales: Decimal
    discounts: Decimal
    voids: Decimal
    
    @property
    def average_price(self) -> Decimal:
        """Average selling price."""
        if self.quantity_sold == 0:
            return Decimal("0")
        return self.net_sales / self.quantity_sold


@dataclass
class ToastLaborEntry:
    """Labor/timecard entry from Toast."""
    
    employee_id: str
    employee_name: str
    job_title: str
    date: date
    regular_hours: Decimal
    overtime_hours: Decimal
    hourly_rate: Decimal
    tips_declared: Decimal
    
    @property
    def total_hours(self) -> Decimal:
        """Total hours worked."""
        return self.regular_hours + self.overtime_hours
    
    @property
    def labor_cost(self) -> Decimal:
        """Total labor cost (wages only, excluding tips)."""
        regular_cost = self.regular_hours * self.hourly_rate
        overtime_cost = self.overtime_hours * self.hourly_rate * Decimal("1.5")
        return regular_cost + overtime_cost


@dataclass
class ToastPaymentBreakdown:
    """Payment method breakdown."""
    
    date: date
    cash: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    debit: Decimal = Decimal("0")
    gift_card: Decimal = Decimal("0")
    house_account: Decimal = Decimal("0")
    third_party: Decimal = Decimal("0")
    other: Decimal = Decimal("0")
    
    @property
    def total(self) -> Decimal:
        """Total payments."""
        return (
            self.cash + self.credit + self.debit + 
            self.gift_card + self.house_account + 
            self.third_party + self.other
        )
    
    @property
    def card_percentage(self) -> float:
        """Percentage of card payments."""
        if self.total == 0:
            return 0.0
        return float((self.credit + self.debit) / self.total * 100)


class ToastConnector(BaseConnector):
    """Import restaurant data from Toast POS.

    Usage::

        connector = ToastConnector(
            credentials={
                "client_id": "YOUR_CLIENT_ID",
                "client_secret": "YOUR_CLIENT_SECRET",
                "restaurant_guid": "YOUR_RESTAURANT_GUID",
            }
        )
        dataset = await connector.pull(company)

    Features:
    - Daily sales summaries
    - Menu item performance analysis
    - Labor hours and costs
    - Payment method breakdowns
    - Guest count and check averages
    - Multi-location support
    """

    name = "toast"
    description = "Import restaurant data from Toast POS"

    def __init__(
        self,
        credentials: dict[str, Any] | None = None,
        **options: Any,
    ) -> None:
        super().__init__(credentials, **options)

        creds = credentials or {}
        self.client_id = creds.get("client_id", "")
        self.client_secret = creds.get("client_secret", "")
        self.restaurant_guid = creds.get("restaurant_guid", "")
        self.management_group_guid = creds.get("management_group_guid")
        
        self._access_token: str | None = None
        self._token_expires: datetime | None = None

    def validate_credentials(self) -> list[str]:
        """Validate that required credentials are present."""
        errors = []
        if not self.client_id:
            errors.append("Toast client_id is required")
        if not self.client_secret:
            errors.append("Toast client_secret is required")
        if not self.restaurant_guid:
            errors.append("Toast restaurant_guid is required")
        return errors

    async def _authenticate(self, client: httpx.AsyncClient) -> str:
        """Authenticate with Toast API and get access token."""
        if self._access_token and self._token_expires:
            if datetime.now() < self._token_expires:
                return self._access_token

        response = await client.post(
            TOAST_AUTH_URL,
            json={
                "clientId": self.client_id,
                "clientSecret": self.client_secret,
                "userAccessType": "TOAST_MACHINE_CLIENT",
            },
        )
        response.raise_for_status()
        data = response.json()

        self._access_token = data.get("token", {}).get("accessToken")
        expires_in = data.get("token", {}).get("expiresIn", 3600)
        self._token_expires = datetime.now() + timedelta(seconds=expires_in - 60)

        return self._access_token

    def _get_headers(self) -> dict[str, str]:
        """Get headers for Toast API requests."""
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Toast-Restaurant-External-ID": self.restaurant_guid,
            "Content-Type": "application/json",
        }

    async def _fetch_orders(
        self,
        client: httpx.AsyncClient,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Fetch orders for a date range."""
        orders = []
        
        # Toast uses business dates
        current = start_date
        while current <= end_date:
            url = f"{TOAST_API_BASE}/orders/v2/orders"
            params = {
                "businessDate": current.isoformat(),
                "pageSize": 100,
            }
            
            try:
                response = await client.get(
                    url,
                    headers=self._get_headers(),
                    params=params,
                )
                response.raise_for_status()
                orders.extend(response.json())
            except httpx.HTTPError as e:
                logger.warning(f"Failed to fetch orders for {current}: {e}")
            
            current += timedelta(days=1)
        
        return orders

    async def _fetch_labor(
        self,
        client: httpx.AsyncClient,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Fetch labor/timecard data."""
        url = f"{TOAST_API_BASE}/labor/v1/timeEntries"
        params = {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
        }
        
        try:
            response = await client.get(
                url,
                headers=self._get_headers(),
                params=params,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.warning(f"Failed to fetch labor data: {e}")
            return []

    async def _fetch_menu_items(
        self,
        client: httpx.AsyncClient,
    ) -> list[dict[str, Any]]:
        """Fetch menu item catalog."""
        url = f"{TOAST_API_BASE}/menus/v2/menus"
        
        try:
            response = await client.get(
                url,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.warning(f"Failed to fetch menu items: {e}")
            return []

    def _aggregate_daily_sales(
        self,
        orders: list[dict[str, Any]],
    ) -> dict[date, ToastSalesSummary]:
        """Aggregate orders into daily sales summaries."""
        summaries: dict[date, dict] = {}
        
        for order in orders:
            business_date = date.fromisoformat(order.get("businessDate", ""))
            
            if business_date not in summaries:
                summaries[business_date] = {
                    "net_sales": Decimal("0"),
                    "gross_sales": Decimal("0"),
                    "discounts": Decimal("0"),
                    "voids": Decimal("0"),
                    "refunds": Decimal("0"),
                    "tax_collected": Decimal("0"),
                    "tips": Decimal("0"),
                    "service_charges": Decimal("0"),
                    "guest_count": 0,
                    "order_count": 0,
                }
            
            summary = summaries[business_date]
            
            # Extract amounts (Toast stores in cents)
            amount = Decimal(str(order.get("amount", 0))) / 100
            tax = Decimal(str(order.get("taxAmount", 0))) / 100
            tip = Decimal(str(order.get("tipAmount", 0))) / 100
            discount = Decimal(str(order.get("discountAmount", 0))) / 100
            
            summary["gross_sales"] += amount + discount
            summary["net_sales"] += amount
            summary["discounts"] += discount
            summary["tax_collected"] += tax
            summary["tips"] += tip
            summary["guest_count"] += order.get("guestCount", 1)
            summary["order_count"] += 1
            
            # Handle voids/refunds
            if order.get("voided"):
                summary["voids"] += amount
            if order.get("refund"):
                summary["refunds"] += Decimal(str(order.get("refundAmount", 0))) / 100
        
        return {
            d: ToastSalesSummary(
                date=d,
                net_sales=s["net_sales"],
                gross_sales=s["gross_sales"],
                discounts=s["discounts"],
                voids=s["voids"],
                refunds=s["refunds"],
                tax_collected=s["tax_collected"],
                tips=s["tips"],
                service_charges=s["service_charges"],
                guest_count=s["guest_count"],
                order_count=s["order_count"],
            )
            for d, s in summaries.items()
        }

    def _aggregate_menu_sales(
        self,
        orders: list[dict[str, Any]],
    ) -> list[ToastMenuItem]:
        """Aggregate item-level sales from orders."""
        item_sales: dict[str, dict] = {}
        
        for order in orders:
            for selection in order.get("selections", []):
                item_id = selection.get("itemGuid", "unknown")
                item_name = selection.get("displayName", "Unknown Item")
                item_category = selection.get("salesCategory", {}).get("name", "Uncategorized")
                
                if item_id not in item_sales:
                    item_sales[item_id] = {
                        "name": item_name,
                        "category": item_category,
                        "quantity_sold": 0,
                        "gross_sales": Decimal("0"),
                        "net_sales": Decimal("0"),
                        "discounts": Decimal("0"),
                        "voids": Decimal("0"),
                    }
                
                item = item_sales[item_id]
                quantity = selection.get("quantity", 1)
                price = Decimal(str(selection.get("price", 0))) / 100
                discount = Decimal(str(selection.get("discountAmount", 0))) / 100
                
                item["quantity_sold"] += quantity
                item["gross_sales"] += price + discount
                item["net_sales"] += price
                item["discounts"] += discount
                
                if selection.get("voided"):
                    item["voids"] += price
        
        return [
            ToastMenuItem(
                item_id=item_id,
                name=data["name"],
                category=data["category"],
                quantity_sold=data["quantity_sold"],
                gross_sales=data["gross_sales"],
                net_sales=data["net_sales"],
                discounts=data["discounts"],
                voids=data["voids"],
            )
            for item_id, data in item_sales.items()
        ]

    def _parse_labor_entries(
        self,
        labor_data: list[dict[str, Any]],
    ) -> list[ToastLaborEntry]:
        """Parse labor/timecard data into entries."""
        entries = []
        
        for entry in labor_data:
            employee = entry.get("employee", {})
            
            # Calculate hours from clock in/out
            clock_in = entry.get("inDate")
            clock_out = entry.get("outDate")
            
            if clock_in and clock_out:
                in_time = datetime.fromisoformat(clock_in.replace("Z", "+00:00"))
                out_time = datetime.fromisoformat(clock_out.replace("Z", "+00:00"))
                total_hours = Decimal(str((out_time - in_time).total_seconds() / 3600))
            else:
                total_hours = Decimal("0")
            
            # Overtime after 8 hours
            regular = min(total_hours, Decimal("8"))
            overtime = max(total_hours - Decimal("8"), Decimal("0"))
            
            hourly_rate = Decimal(str(entry.get("hourlyWage", 0))) / 100
            tips = Decimal(str(entry.get("declaredCashTips", 0))) / 100
            
            entries.append(ToastLaborEntry(
                employee_id=employee.get("guid", ""),
                employee_name=f"{employee.get('firstName', '')} {employee.get('lastName', '')}".strip(),
                job_title=entry.get("jobReference", {}).get("name", "Staff"),
                date=date.fromisoformat(entry.get("businessDate", date.today().isoformat())),
                regular_hours=regular,
                overtime_hours=overtime,
                hourly_rate=hourly_rate,
                tips_declared=tips,
            ))
        
        return entries

    def _aggregate_payments(
        self,
        orders: list[dict[str, Any]],
    ) -> dict[date, ToastPaymentBreakdown]:
        """Aggregate payment methods by date."""
        payments: dict[date, dict] = {}
        
        for order in orders:
            business_date = date.fromisoformat(order.get("businessDate", ""))
            
            if business_date not in payments:
                payments[business_date] = {
                    "cash": Decimal("0"),
                    "credit": Decimal("0"),
                    "debit": Decimal("0"),
                    "gift_card": Decimal("0"),
                    "house_account": Decimal("0"),
                    "third_party": Decimal("0"),
                    "other": Decimal("0"),
                }
            
            for payment in order.get("payments", []):
                amount = Decimal(str(payment.get("amount", 0))) / 100
                payment_type = payment.get("type", "").upper()
                
                if payment_type == "CASH":
                    payments[business_date]["cash"] += amount
                elif payment_type in ("CREDIT", "VISA", "MASTERCARD", "AMEX"):
                    payments[business_date]["credit"] += amount
                elif payment_type == "DEBIT":
                    payments[business_date]["debit"] += amount
                elif payment_type == "GIFT_CARD":
                    payments[business_date]["gift_card"] += amount
                elif payment_type == "HOUSE_ACCOUNT":
                    payments[business_date]["house_account"] += amount
                elif payment_type in ("DOORDASH", "UBEREATS", "GRUBHUB"):
                    payments[business_date]["third_party"] += amount
                else:
                    payments[business_date]["other"] += amount
        
        return {
            d: ToastPaymentBreakdown(date=d, **p)
            for d, p in payments.items()
        }

    def _orders_to_transactions(
        self,
        orders: list[dict[str, Any]],
    ) -> list[Transaction]:
        """Convert Toast orders to FiscalPilot transactions."""
        transactions = []
        
        daily_summaries = self._aggregate_daily_sales(orders)
        
        for business_date, summary in daily_summaries.items():
            # Net sales as income
            if summary.net_sales > 0:
                transactions.append(Transaction(
                    id=f"toast_sales_{business_date.isoformat()}",
                    date=business_date,
                    amount=float(summary.net_sales),
                    type=TransactionType.INCOME,
                    description=f"Toast POS Sales - {summary.order_count} orders",
                    vendor="Toast POS",
                    account="Sales",
                    tags=["pos", "toast", "sales"],
                    raw_data={
                        "source": "toast",
                        "guest_count": summary.guest_count,
                        "order_count": summary.order_count,
                        "check_average": float(summary.check_average),
                        "gross_sales": float(summary.gross_sales),
                        "discounts": float(summary.discounts),
                    },
                ))
            
            # Tips as separate income
            if summary.tips > 0:
                transactions.append(Transaction(
                    id=f"toast_tips_{business_date.isoformat()}",
                    date=business_date,
                    amount=float(summary.tips),
                    type=TransactionType.INCOME,
                    description=f"Toast POS Tips",
                    vendor="Toast POS",
                    account="Tips",
                    tags=["pos", "toast", "tips"],
                ))
            
            # Refunds as expense/negative
            if summary.refunds > 0:
                transactions.append(Transaction(
                    id=f"toast_refunds_{business_date.isoformat()}",
                    date=business_date,
                    amount=-float(summary.refunds),
                    type=TransactionType.EXPENSE,
                    description=f"Toast POS Refunds",
                    vendor="Toast POS",
                    category=ExpenseCategory.OTHER,
                    tags=["pos", "toast", "refunds"],
                ))
        
        return transactions

    async def pull(
        self,
        company: CompanyProfile,
        start_date: date | None = None,
        end_date: date | None = None,
        **options: Any,
    ) -> FinancialDataset:
        """Pull restaurant data from Toast POS.

        Args:
            company: Company profile.
            start_date: Start of date range (default: 30 days ago).
            end_date: End of date range (default: today).
            **options: Additional options.

        Returns:
            FinancialDataset with Toast sales data.
        """
        errors = self.validate_credentials()
        if errors:
            raise ValueError(f"Invalid credentials: {', '.join(errors)}")

        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Authenticate
            await self._authenticate(client)

            # Fetch data
            orders = await self._fetch_orders(client, start_date, end_date)
            labor_data = await self._fetch_labor(client, start_date, end_date)

            # Convert to transactions
            transactions = self._orders_to_transactions(orders)

            # Store additional data in metadata
            menu_sales = self._aggregate_menu_sales(orders)
            labor_entries = self._parse_labor_entries(labor_data)
            payment_breakdown = self._aggregate_payments(orders)
            daily_summaries = self._aggregate_daily_sales(orders)

            return FinancialDataset(
                company=company,
                transactions=transactions,
                date_range=(start_date, end_date),
                metadata={
                    "source": "toast",
                    "restaurant_guid": self.restaurant_guid,
                    "menu_sales": [
                        {
                            "item_id": item.item_id,
                            "name": item.name,
                            "category": item.category,
                            "quantity_sold": item.quantity_sold,
                            "net_sales": float(item.net_sales),
                        }
                        for item in sorted(menu_sales, key=lambda x: x.net_sales, reverse=True)
                    ],
                    "labor_summary": {
                        "total_hours": sum(float(e.total_hours) for e in labor_entries),
                        "total_labor_cost": sum(float(e.labor_cost) for e in labor_entries),
                        "total_tips_declared": sum(float(e.tips_declared) for e in labor_entries),
                    },
                    "daily_summaries": {
                        d.isoformat(): {
                            "net_sales": float(s.net_sales),
                            "guest_count": s.guest_count,
                            "order_count": s.order_count,
                            "check_average": float(s.check_average),
                        }
                        for d, s in daily_summaries.items()
                    },
                    "payment_breakdown": {
                        d.isoformat(): {
                            "cash": float(p.cash),
                            "credit": float(p.credit),
                            "debit": float(p.debit),
                            "gift_card": float(p.gift_card),
                            "card_percentage": p.card_percentage,
                        }
                        for d, p in payment_breakdown.items()
                    },
                },
            )

    async def health_check(self) -> dict[str, Any]:
        """Check Toast API connectivity."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await self._authenticate(client)
                return {
                    "status": "healthy",
                    "authenticated": True,
                    "restaurant_guid": self.restaurant_guid,
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }


# Convenience functions
def create_toast_connector(
    client_id: str,
    client_secret: str,
    restaurant_guid: str,
    **options: Any,
) -> ToastConnector:
    """Create a Toast connector with credentials."""
    return ToastConnector(
        credentials={
            "client_id": client_id,
            "client_secret": client_secret,
            "restaurant_guid": restaurant_guid,
        },
        **options,
    )
