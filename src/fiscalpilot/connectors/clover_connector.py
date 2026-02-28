"""
Clover POS Connector — import merchant data from Clover.

Clover is a popular POS system serving 1M+ merchants, particularly
in retail and quick-service restaurants.

This connector pulls:
- Sales and revenue data
- Order history
- Payment transactions
- Inventory/item data
- Employee time tracking
- Refunds and discounts

Requires Clover API credentials:
- API Token (OAuth2)
- Merchant ID

API Documentation: https://docs.clover.com/
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
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

logger = logging.getLogger("fiscalpilot.connectors.clover")

# Clover API endpoints
CLOVER_API_BASE = "https://api.clover.com/v3"
CLOVER_SANDBOX_BASE = "https://sandbox.dev.clover.com/v3"


class CloverPaymentResult(str, Enum):
    """Clover payment results."""
    
    SUCCESS = "SUCCESS"
    DECLINED = "DECLINED"
    VOIDED = "VOIDED"
    REFUNDED = "REFUNDED"


class CloverTenderType(str, Enum):
    """Clover tender/payment types."""
    
    CASH = "com.clover.tender.cash"
    CREDIT_CARD = "com.clover.tender.credit_card"
    DEBIT_CARD = "com.clover.tender.debit_card"
    GIFT_CARD = "com.clover.tender.gift_card"
    EXTERNAL = "com.clover.tender.external"


@dataclass
class CloverOrderSummary:
    """Daily order summary from Clover."""
    
    date: date
    total_sales: Decimal
    total_tax: Decimal
    total_tips: Decimal
    total_discounts: Decimal
    total_refunds: Decimal
    order_count: int
    item_count: int
    
    @property
    def net_sales(self) -> Decimal:
        """Net sales after discounts and refunds."""
        return self.total_sales - self.total_discounts - self.total_refunds
    
    @property
    def average_order(self) -> Decimal:
        """Average order value."""
        if self.order_count == 0:
            return Decimal("0")
        return self.net_sales / self.order_count


@dataclass
class CloverItem:
    """Item from Clover inventory."""
    
    id: str
    name: str
    sku: str | None
    price: Decimal
    cost: Decimal | None
    quantity_sold: int = 0
    total_revenue: Decimal = Decimal("0")
    
    @property
    def margin(self) -> float | None:
        """Item margin if cost is known."""
        if self.cost is None or self.price == 0:
            return None
        return float((self.price - self.cost) / self.price * 100)


@dataclass
class CloverEmployee:
    """Employee data from Clover."""
    
    id: str
    name: str
    role: str
    email: str | None
    hours_worked: Decimal = Decimal("0")
    sales_amount: Decimal = Decimal("0")
    tips_received: Decimal = Decimal("0")


@dataclass
class CloverPaymentSummary:
    """Payment method summary."""
    
    date: date
    cash: Decimal = Decimal("0")
    credit_card: Decimal = Decimal("0")
    debit_card: Decimal = Decimal("0")
    gift_card: Decimal = Decimal("0")
    external: Decimal = Decimal("0")
    
    @property
    def total(self) -> Decimal:
        """Total payments."""
        return self.cash + self.credit_card + self.debit_card + self.gift_card + self.external
    
    @property
    def card_percentage(self) -> float:
        """Percentage of card payments."""
        if self.total == 0:
            return 0.0
        return float((self.credit_card + self.debit_card) / self.total * 100)


class CloverConnector(BaseConnector):
    """Import merchant data from Clover POS.

    Usage::

        connector = CloverConnector(
            credentials={
                "api_token": "YOUR_API_TOKEN",
                "merchant_id": "YOUR_MERCHANT_ID",
            }
        )
        dataset = await connector.pull(company)

    Features:
    - Sales and order history
    - Payment method breakdowns
    - Item-level sales analysis
    - Employee performance tracking
    - Refund and discount tracking
    - Multi-location support
    """

    name = "clover"
    description = "Import merchant data from Clover POS"

    def __init__(
        self,
        credentials: dict[str, Any] | None = None,
        *,
        sandbox: bool = False,
        **options: Any,
    ) -> None:
        super().__init__(credentials, **options)

        creds = credentials or {}
        self.api_token = creds.get("api_token", "")
        self.merchant_id = creds.get("merchant_id", "")
        self.sandbox = sandbox
        
        self._base_url = CLOVER_SANDBOX_BASE if sandbox else CLOVER_API_BASE

    def validate_credentials(self) -> list[str]:
        """Validate that required credentials are present."""
        errors = []
        if not self.api_token:
            errors.append("Clover api_token is required")
        if not self.merchant_id:
            errors.append("Clover merchant_id is required")
        return errors

    def _get_headers(self) -> dict[str, str]:
        """Get headers for Clover API requests."""
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    def _merchant_url(self, endpoint: str) -> str:
        """Build URL for merchant-specific endpoint."""
        return f"{self._base_url}/merchants/{self.merchant_id}/{endpoint}"

    async def _fetch_orders(
        self,
        client: httpx.AsyncClient,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Fetch orders for a date range."""
        orders = []
        
        # Convert to milliseconds timestamp
        start_ts = int(datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc).timestamp() * 1000)
        end_ts = int(datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc).timestamp() * 1000)
        
        url = self._merchant_url("orders")
        offset = 0
        limit = 100
        
        while True:
            params = {
                "filter": f"createdTime>={start_ts}&createdTime<={end_ts}",
                "expand": "lineItems,payments,refunds,discounts",
                "limit": limit,
                "offset": offset,
            }
            
            try:
                response = await client.get(
                    url,
                    headers=self._get_headers(),
                    params=params,
                )
                response.raise_for_status()
                data = response.json()
                
                elements = data.get("elements", [])
                orders.extend(elements)
                
                if len(elements) < limit:
                    break
                offset += limit
                
            except httpx.HTTPError as e:
                logger.warning(f"Failed to fetch orders: {e}")
                break
        
        return orders

    async def _fetch_payments(
        self,
        client: httpx.AsyncClient,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Fetch payment transactions."""
        payments = []
        
        start_ts = int(datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc).timestamp() * 1000)
        end_ts = int(datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc).timestamp() * 1000)
        
        url = self._merchant_url("payments")
        offset = 0
        limit = 100
        
        while True:
            params = {
                "filter": f"createdTime>={start_ts}&createdTime<={end_ts}",
                "expand": "tender,refunds",
                "limit": limit,
                "offset": offset,
            }
            
            try:
                response = await client.get(
                    url,
                    headers=self._get_headers(),
                    params=params,
                )
                response.raise_for_status()
                data = response.json()
                
                elements = data.get("elements", [])
                payments.extend(elements)
                
                if len(elements) < limit:
                    break
                offset += limit
                
            except httpx.HTTPError as e:
                logger.warning(f"Failed to fetch payments: {e}")
                break
        
        return payments

    async def _fetch_items(
        self,
        client: httpx.AsyncClient,
    ) -> list[dict[str, Any]]:
        """Fetch inventory items."""
        url = self._merchant_url("items")
        
        try:
            response = await client.get(
                url,
                headers=self._get_headers(),
                params={"expand": "categories", "limit": 1000},
            )
            response.raise_for_status()
            return response.json().get("elements", [])
        except httpx.HTTPError as e:
            logger.warning(f"Failed to fetch items: {e}")
            return []

    async def _fetch_employees(
        self,
        client: httpx.AsyncClient,
    ) -> list[dict[str, Any]]:
        """Fetch employee list."""
        url = self._merchant_url("employees")
        
        try:
            response = await client.get(
                url,
                headers=self._get_headers(),
                params={"expand": "roles", "limit": 500},
            )
            response.raise_for_status()
            return response.json().get("elements", [])
        except httpx.HTTPError as e:
            logger.warning(f"Failed to fetch employees: {e}")
            return []

    async def _fetch_shifts(
        self,
        client: httpx.AsyncClient,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Fetch employee shifts/time entries."""
        shifts = []
        
        start_ts = int(datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc).timestamp() * 1000)
        end_ts = int(datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc).timestamp() * 1000)
        
        url = self._merchant_url("shifts")
        
        try:
            response = await client.get(
                url,
                headers=self._get_headers(),
                params={
                    "filter": f"inTime>={start_ts}&inTime<={end_ts}",
                    "expand": "employee",
                    "limit": 1000,
                },
            )
            response.raise_for_status()
            shifts = response.json().get("elements", [])
        except httpx.HTTPError as e:
            logger.warning(f"Failed to fetch shifts: {e}")
        
        return shifts

    def _aggregate_daily_summary(
        self,
        orders: list[dict[str, Any]],
    ) -> dict[date, CloverOrderSummary]:
        """Aggregate orders into daily summaries."""
        summaries: dict[date, dict] = {}
        
        for order in orders:
            created_time = order.get("createdTime", 0) / 1000
            order_date = datetime.fromtimestamp(created_time, tz=timezone.utc).date()
            
            if order_date not in summaries:
                summaries[order_date] = {
                    "total_sales": Decimal("0"),
                    "total_tax": Decimal("0"),
                    "total_tips": Decimal("0"),
                    "total_discounts": Decimal("0"),
                    "total_refunds": Decimal("0"),
                    "order_count": 0,
                    "item_count": 0,
                }
            
            summary = summaries[order_date]
            
            # Clover stores amounts in cents
            total = Decimal(str(order.get("total", 0))) / 100
            tax = Decimal(str(order.get("taxAmount", 0))) / 100
            
            summary["total_sales"] += total
            summary["total_tax"] += tax
            summary["order_count"] += 1
            
            # Line items
            for item in order.get("lineItems", {}).get("elements", []):
                summary["item_count"] += 1
            
            # Discounts
            for discount in order.get("discounts", {}).get("elements", []):
                summary["total_discounts"] += Decimal(str(discount.get("amount", 0))) / 100
            
            # Payments (for tips)
            for payment in order.get("payments", {}).get("elements", []):
                tip = Decimal(str(payment.get("tipAmount", 0))) / 100
                summary["total_tips"] += tip
            
            # Refunds
            for refund in order.get("refunds", {}).get("elements", []):
                summary["total_refunds"] += Decimal(str(refund.get("amount", 0))) / 100
        
        return {
            d: CloverOrderSummary(
                date=d,
                total_sales=s["total_sales"],
                total_tax=s["total_tax"],
                total_tips=s["total_tips"],
                total_discounts=s["total_discounts"],
                total_refunds=s["total_refunds"],
                order_count=s["order_count"],
                item_count=s["item_count"],
            )
            for d, s in summaries.items()
        }

    def _aggregate_item_sales(
        self,
        orders: list[dict[str, Any]],
        items: list[dict[str, Any]],
    ) -> list[CloverItem]:
        """Aggregate item-level sales."""
        # Build item lookup
        item_lookup = {
            item["id"]: CloverItem(
                id=item["id"],
                name=item.get("name", "Unknown"),
                sku=item.get("sku"),
                price=Decimal(str(item.get("price", 0))) / 100,
                cost=Decimal(str(item.get("cost", 0))) / 100 if item.get("cost") else None,
            )
            for item in items
        }
        
        # Aggregate sales from orders
        for order in orders:
            for line_item in order.get("lineItems", {}).get("elements", []):
                item_id = line_item.get("item", {}).get("id")
                if item_id and item_id in item_lookup:
                    item = item_lookup[item_id]
                    quantity = 1  # Clover doesn't always have quantity
                    amount = Decimal(str(line_item.get("price", 0))) / 100
                    
                    # Update in place (dataclass fields)
                    object.__setattr__(item, "quantity_sold", item.quantity_sold + quantity)
                    object.__setattr__(item, "total_revenue", item.total_revenue + amount)
        
        return list(item_lookup.values())

    def _aggregate_payments(
        self,
        payments: list[dict[str, Any]],
    ) -> dict[date, CloverPaymentSummary]:
        """Aggregate payment methods by date."""
        summaries: dict[date, dict] = {}
        
        for payment in payments:
            created_time = payment.get("createdTime", 0) / 1000
            payment_date = datetime.fromtimestamp(created_time, tz=timezone.utc).date()
            
            if payment_date not in summaries:
                summaries[payment_date] = {
                    "cash": Decimal("0"),
                    "credit_card": Decimal("0"),
                    "debit_card": Decimal("0"),
                    "gift_card": Decimal("0"),
                    "external": Decimal("0"),
                }
            
            # Skip failed/voided payments
            result = payment.get("result")
            if result not in ("SUCCESS", None):
                continue
            
            amount = Decimal(str(payment.get("amount", 0))) / 100
            tender_type = payment.get("tender", {}).get("labelKey", "")
            
            if tender_type == CloverTenderType.CASH.value:
                summaries[payment_date]["cash"] += amount
            elif tender_type == CloverTenderType.CREDIT_CARD.value:
                summaries[payment_date]["credit_card"] += amount
            elif tender_type == CloverTenderType.DEBIT_CARD.value:
                summaries[payment_date]["debit_card"] += amount
            elif tender_type == CloverTenderType.GIFT_CARD.value:
                summaries[payment_date]["gift_card"] += amount
            else:
                summaries[payment_date]["external"] += amount
        
        return {
            d: CloverPaymentSummary(date=d, **s)
            for d, s in summaries.items()
        }

    def _calculate_employee_hours(
        self,
        shifts: list[dict[str, Any]],
        employees: list[dict[str, Any]],
    ) -> list[CloverEmployee]:
        """Calculate employee hours from shifts."""
        employee_lookup = {
            emp["id"]: CloverEmployee(
                id=emp["id"],
                name=emp.get("name", "Unknown"),
                role=emp.get("role", {}).get("name", "Staff") if emp.get("role") else "Staff",
                email=emp.get("email"),
            )
            for emp in employees
        }
        
        for shift in shifts:
            emp_id = shift.get("employee", {}).get("id")
            if emp_id and emp_id in employee_lookup:
                emp = employee_lookup[emp_id]
                
                in_time = shift.get("inTime", 0) / 1000
                out_time = shift.get("outTime") or datetime.now(tz=timezone.utc).timestamp()
                if isinstance(out_time, int):
                    out_time = out_time / 1000
                
                hours = Decimal(str((out_time - in_time) / 3600))
                object.__setattr__(emp, "hours_worked", emp.hours_worked + hours)
        
        return list(employee_lookup.values())

    def _orders_to_transactions(
        self,
        orders: list[dict[str, Any]],
    ) -> list[Transaction]:
        """Convert Clover orders to FiscalPilot transactions."""
        transactions = []
        
        daily_summaries = self._aggregate_daily_summary(orders)
        
        for order_date, summary in daily_summaries.items():
            # Net sales as income
            if summary.net_sales > 0:
                transactions.append(Transaction(
                    id=f"clover_sales_{order_date.isoformat()}",
                    date=order_date,
                    amount=float(summary.net_sales),
                    type=TransactionType.INCOME,
                    description=f"Clover POS Sales - {summary.order_count} orders",
                    vendor="Clover POS",
                    account="Sales",
                    tags=["pos", "clover", "sales"],
                    raw_data={
                        "source": "clover",
                        "order_count": summary.order_count,
                        "item_count": summary.item_count,
                        "average_order": float(summary.average_order),
                        "total_tax": float(summary.total_tax),
                        "discounts": float(summary.total_discounts),
                    },
                ))
            
            # Tips as separate income
            if summary.total_tips > 0:
                transactions.append(Transaction(
                    id=f"clover_tips_{order_date.isoformat()}",
                    date=order_date,
                    amount=float(summary.total_tips),
                    type=TransactionType.INCOME,
                    description=f"Clover POS Tips",
                    vendor="Clover POS",
                    account="Tips",
                    tags=["pos", "clover", "tips"],
                ))
            
            # Tax collected
            if summary.total_tax > 0:
                transactions.append(Transaction(
                    id=f"clover_tax_{order_date.isoformat()}",
                    date=order_date,
                    amount=float(summary.total_tax),
                    type=TransactionType.INCOME,
                    description=f"Clover POS Tax Collected",
                    vendor="Clover POS",
                    account="Sales Tax Payable",
                    tags=["pos", "clover", "tax"],
                ))
            
            # Refunds as negative/expense
            if summary.total_refunds > 0:
                transactions.append(Transaction(
                    id=f"clover_refunds_{order_date.isoformat()}",
                    date=order_date,
                    amount=-float(summary.total_refunds),
                    type=TransactionType.EXPENSE,
                    description=f"Clover POS Refunds",
                    vendor="Clover POS",
                    category=ExpenseCategory.OTHER,
                    tags=["pos", "clover", "refunds"],
                ))
        
        return transactions

    async def pull(
        self,
        company: CompanyProfile,
        start_date: date | None = None,
        end_date: date | None = None,
        **options: Any,
    ) -> FinancialDataset:
        """Pull merchant data from Clover POS.

        Args:
            company: Company profile.
            start_date: Start of date range (default: 30 days ago).
            end_date: End of date range (default: today).
            **options: Additional options.

        Returns:
            FinancialDataset with Clover sales data.
        """
        errors = self.validate_credentials()
        if errors:
            raise ValueError(f"Invalid credentials: {', '.join(errors)}")

        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Fetch all data
            orders = await self._fetch_orders(client, start_date, end_date)
            payments = await self._fetch_payments(client, start_date, end_date)
            items = await self._fetch_items(client)
            employees = await self._fetch_employees(client)
            shifts = await self._fetch_shifts(client, start_date, end_date)

            # Process data
            transactions = self._orders_to_transactions(orders)
            daily_summaries = self._aggregate_daily_summary(orders)
            item_sales = self._aggregate_item_sales(orders, items)
            payment_breakdown = self._aggregate_payments(payments)
            employee_hours = self._calculate_employee_hours(shifts, employees)

            return FinancialDataset(
                company=company,
                transactions=transactions,
                date_range=(start_date, end_date),
                metadata={
                    "source": "clover",
                    "merchant_id": self.merchant_id,
                    "sandbox": self.sandbox,
                    "daily_summaries": {
                        d.isoformat(): {
                            "total_sales": float(s.total_sales),
                            "net_sales": float(s.net_sales),
                            "order_count": s.order_count,
                            "average_order": float(s.average_order),
                        }
                        for d, s in daily_summaries.items()
                    },
                    "top_items": [
                        {
                            "id": item.id,
                            "name": item.name,
                            "quantity_sold": item.quantity_sold,
                            "total_revenue": float(item.total_revenue),
                            "margin": item.margin,
                        }
                        for item in sorted(item_sales, key=lambda x: x.total_revenue, reverse=True)[:20]
                    ],
                    "payment_methods": {
                        d.isoformat(): {
                            "cash": float(p.cash),
                            "credit_card": float(p.credit_card),
                            "debit_card": float(p.debit_card),
                            "card_percentage": p.card_percentage,
                        }
                        for d, p in payment_breakdown.items()
                    },
                    "labor_summary": {
                        "total_hours": sum(float(e.hours_worked) for e in employee_hours),
                        "employee_count": len([e for e in employee_hours if e.hours_worked > 0]),
                    },
                },
            )

    async def health_check(self) -> dict[str, Any]:
        """Check Clover API connectivity."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = f"{self._base_url}/merchants/{self.merchant_id}"
                response = await client.get(
                    url,
                    headers=self._get_headers(),
                )
                response.raise_for_status()
                merchant = response.json()
                
                return {
                    "status": "healthy",
                    "merchant_id": self.merchant_id,
                    "merchant_name": merchant.get("name"),
                    "sandbox": self.sandbox,
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }


# Convenience functions
def create_clover_connector(
    api_token: str,
    merchant_id: str,
    *,
    sandbox: bool = False,
    **options: Any,
) -> CloverConnector:
    """Create a Clover connector with credentials."""
    return CloverConnector(
        credentials={
            "api_token": api_token,
            "merchant_id": merchant_id,
        },
        sandbox=sandbox,
        **options,
    )
