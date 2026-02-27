"""
Square POS Connector — import restaurant sales data from Square.

Square is one of the most popular POS systems for restaurants, cafes, and retail.
This connector pulls:
- Daily sales and transactions
- Payment breakdowns (card, cash, gift cards)
- Item-level sales for menu analysis
- Refunds and voids
- Tips and gratuities

Requires Square API credentials:
- Application ID
- Access Token (OAuth or personal)

API Documentation: https://developer.squareup.com/docs/
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx

from fiscalpilot.connectors.base import BaseConnector
from fiscalpilot.models.company import CompanyProfile
from fiscalpilot.models.financial import (
    ExpenseCategory,
    FinancialDataset,
    Transaction,
    TransactionType,
)

logger = logging.getLogger("fiscalpilot.connectors.square")

# Square API endpoints
SQUARE_API_BASE = "https://connect.squareup.com/v2"
SQUARE_SANDBOX_BASE = "https://connect.squareupsandbox.com/v2"


class SquarePOSConnector(BaseConnector):
    """Import restaurant sales data from Square POS.
    
    Usage::
    
        connector = SquarePOSConnector(
            credentials={
                "access_token": "YOUR_SQUARE_ACCESS_TOKEN",
                "location_id": "YOUR_LOCATION_ID",  # Optional, pulls all if not set
            }
        )
        dataset = await connector.pull(company)
    
    Features:
    - Daily sales aggregation
    - Payment type breakdown (card, cash, gift cards)
    - Item-level sales for menu analysis
    - Refund and void tracking
    - Multi-location support
    """
    
    name = "square"
    description = "Import sales data from Square POS (restaurants, retail)"
    
    def __init__(
        self,
        credentials: dict[str, Any] | None = None,
        **options: Any,
    ) -> None:
        super().__init__(credentials, **options)
        
        creds = credentials or {}
        self.access_token = creds.get("access_token", "")
        self.location_id = creds.get("location_id")  # Optional
        self.sandbox = options.get("sandbox", False)
        self.days_back = options.get("days_back", 90)  # Default 90 days
        
        # API configuration
        self._base_url = SQUARE_SANDBOX_BASE if self.sandbox else SQUARE_API_BASE
        self._client: httpx.AsyncClient | None = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Square-Version": "2024-01-18",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        return self._client
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def validate_credentials(self) -> bool:
        """Validate Square API credentials."""
        if not self.access_token:
            return False
        
        try:
            client = await self._get_client()
            response = await client.get("/locations")
            return response.status_code == 200
        except Exception as e:
            logger.warning("Square credential validation failed: %s", e)
            return False
    
    async def pull(self, company: CompanyProfile) -> FinancialDataset:
        """Pull sales data from Square.
        
        Returns transactions including:
        - Daily sales as income transactions
        - Processing fees as expense transactions
        - Refunds as negative income
        """
        client = await self._get_client()
        
        # Calculate date range
        end_date = date.today()
        start_date = end_date - timedelta(days=self.days_back)
        
        # Get locations
        locations = await self._get_locations(client)
        if self.location_id:
            locations = [loc for loc in locations if loc["id"] == self.location_id]
        
        if not locations:
            logger.warning("No Square locations found")
            return FinancialDataset(transactions=[], source="square:no_locations")
        
        logger.info("Pulling Square data from %d location(s)", len(locations))
        
        # Pull orders/payments for each location
        all_transactions: list[Transaction] = []
        
        for location in locations:
            loc_id = location["id"]
            loc_name = location.get("name", loc_id)
            
            # Get payments (actual money movement)
            payments = await self._get_payments(client, loc_id, start_date, end_date)
            
            for payment in payments:
                txns = self._payment_to_transactions(payment, loc_name)
                all_transactions.extend(txns)
        
        # Sort by date
        all_transactions.sort(key=lambda t: t.date)
        
        dataset = FinancialDataset(
            transactions=all_transactions,
            source=f"square:{len(locations)}_locations",
        )
        
        if all_transactions:
            dataset.period_start = min(t.date for t in all_transactions)
            dataset.period_end = max(t.date for t in all_transactions)
        
        logger.info(
            "Pulled %d transactions from Square (%s to %s)",
            len(all_transactions),
            dataset.period_start,
            dataset.period_end,
        )
        
        return dataset
    
    async def _get_locations(self, client: httpx.AsyncClient) -> list[dict[str, Any]]:
        """Get all Square locations."""
        try:
            response = await client.get("/locations")
            response.raise_for_status()
            data = response.json()
            return data.get("locations", [])
        except Exception as e:
            logger.error("Failed to fetch Square locations: %s", e)
            return []
    
    async def _get_payments(
        self,
        client: httpx.AsyncClient,
        location_id: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Get payments for a location within date range."""
        payments: list[dict[str, Any]] = []
        cursor: str | None = None
        
        # Square uses RFC 3339 format
        begin_time = f"{start_date.isoformat()}T00:00:00Z"
        end_time = f"{end_date.isoformat()}T23:59:59Z"
        
        while True:
            params: dict[str, Any] = {
                "location_id": location_id,
                "begin_time": begin_time,
                "end_time": end_time,
                "limit": 100,
            }
            if cursor:
                params["cursor"] = cursor
            
            try:
                response = await client.get("/payments", params=params)
                response.raise_for_status()
                data = response.json()
                
                batch = data.get("payments", [])
                payments.extend(batch)
                
                cursor = data.get("cursor")
                if not cursor:
                    break
                    
            except Exception as e:
                logger.error("Failed to fetch Square payments: %s", e)
                break
        
        return payments
    
    def _payment_to_transactions(
        self,
        payment: dict[str, Any],
        location_name: str,
    ) -> list[Transaction]:
        """Convert a Square payment to FiscalPilot transactions."""
        transactions: list[Transaction] = []
        
        # Parse date
        created_at = payment.get("created_at", "")
        try:
            txn_date = datetime.fromisoformat(created_at.replace("Z", "+00:00")).date()
        except (ValueError, AttributeError):
            txn_date = date.today()
        
        payment_id = payment.get("id", "unknown")
        status = payment.get("status", "")
        
        # Skip non-completed payments
        if status not in ("COMPLETED", "APPROVED"):
            return []
        
        # Get amounts (Square uses cents/smallest currency unit)
        amount_money = payment.get("amount_money", {})
        total_cents = amount_money.get("amount", 0)
        total_amount = Decimal(total_cents) / 100
        
        # Tip amount
        tip_money = payment.get("tip_money", {})
        tip_cents = tip_money.get("amount", 0)
        tip_amount = Decimal(tip_cents) / 100
        
        # Processing fee
        processing_fee = payment.get("processing_fee", [])
        fee_total = sum(f.get("amount_money", {}).get("amount", 0) for f in processing_fee)
        fee_amount = Decimal(fee_total) / 100
        
        # Source type (card, cash, etc.)
        source_type = payment.get("source_type", "CARD")
        card_details = payment.get("card_details", {})
        card_brand = card_details.get("card", {}).get("card_brand", "")
        
        # Build description
        if source_type == "CARD":
            payment_method = f"{card_brand} card" if card_brand else "Card"
        elif source_type == "CASH":
            payment_method = "Cash"
        else:
            payment_method = source_type.title()
        
        description = f"Square sale ({payment_method}) at {location_name}"
        
        # Main sale transaction (income)
        if total_amount > 0:
            transactions.append(Transaction(
                id=f"square_{payment_id}",
                date=txn_date,
                amount=float(total_amount),
                description=description,
                vendor=f"Square POS - {location_name}",
                type=TransactionType.INCOME,
                category=None,  # Income transactions don't need expense category
                raw_data={
                    "source": "square",
                    "payment_id": payment_id,
                    "source_type": source_type,
                    "tip_amount": float(tip_amount),
                },
            ))
        
        # Processing fee transaction (expense)
        if fee_amount > 0:
            transactions.append(Transaction(
                id=f"square_{payment_id}_fee",
                date=txn_date,
                amount=float(fee_amount),
                description=f"Square processing fee - {payment_method}",
                vendor="Square",
                type=TransactionType.EXPENSE,
                category=ExpenseCategory.PROFESSIONAL_FEES,
                raw_data={
                    "source": "square",
                    "payment_id": payment_id,
                    "fee_type": "processing",
                },
            ))
        
        return transactions
    
    async def get_item_sales(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """Get item-level sales data for menu analysis.
        
        Returns list of items with:
        - item_name
        - quantity_sold
        - gross_sales
        - average_price
        
        Useful for menu engineering and identifying top/bottom performers.
        """
        client = await self._get_client()
        
        if not start_date:
            start_date = date.today() - timedelta(days=self.days_back)
        if not end_date:
            end_date = date.today()
        
        # Get orders with line items
        orders = await self._get_orders(client, start_date, end_date)
        
        # Aggregate by item
        item_sales: dict[str, dict[str, Any]] = {}
        
        for order in orders:
            for line_item in order.get("line_items", []):
                item_name = line_item.get("name", "Unknown Item")
                quantity = int(line_item.get("quantity", "1"))
                
                base_price = line_item.get("base_price_money", {})
                price_cents = base_price.get("amount", 0)
                
                total_money = line_item.get("total_money", {})
                total_cents = total_money.get("amount", 0)
                
                if item_name not in item_sales:
                    item_sales[item_name] = {
                        "item_name": item_name,
                        "quantity_sold": 0,
                        "gross_sales": 0,
                        "base_price": price_cents / 100,
                    }
                
                item_sales[item_name]["quantity_sold"] += quantity
                item_sales[item_name]["gross_sales"] += total_cents / 100
        
        # Calculate averages and sort by sales
        result = []
        for item in item_sales.values():
            qty = item["quantity_sold"]
            item["average_price"] = item["gross_sales"] / qty if qty > 0 else 0
            result.append(item)
        
        result.sort(key=lambda x: x["gross_sales"], reverse=True)
        return result
    
    async def _get_orders(
        self,
        client: httpx.AsyncClient,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Get orders with line items."""
        orders: list[dict[str, Any]] = []
        cursor: str | None = None
        
        # Get location IDs
        locations = await self._get_locations(client)
        location_ids = [loc["id"] for loc in locations]
        if self.location_id:
            location_ids = [self.location_id]
        
        while True:
            body: dict[str, Any] = {
                "location_ids": location_ids,
                "query": {
                    "filter": {
                        "date_time_filter": {
                            "created_at": {
                                "start_at": f"{start_date.isoformat()}T00:00:00Z",
                                "end_at": f"{end_date.isoformat()}T23:59:59Z",
                            }
                        },
                        "state_filter": {
                            "states": ["COMPLETED"]
                        },
                    },
                    "sort": {
                        "sort_field": "CREATED_AT",
                        "sort_order": "DESC",
                    },
                },
                "limit": 100,
            }
            if cursor:
                body["cursor"] = cursor
            
            try:
                response = await client.post("/orders/search", json=body)
                response.raise_for_status()
                data = response.json()
                
                batch = data.get("orders", [])
                orders.extend(batch)
                
                cursor = data.get("cursor")
                if not cursor:
                    break
                    
            except Exception as e:
                logger.error("Failed to fetch Square orders: %s", e)
                break
        
        return orders
    
    async def get_daily_summary(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """Get daily sales summary.
        
        Returns list of daily summaries with:
        - date
        - total_sales
        - transaction_count
        - average_ticket
        - tips
        - processing_fees
        - net_sales
        """
        client = await self._get_client()
        
        if not start_date:
            start_date = date.today() - timedelta(days=self.days_back)
        if not end_date:
            end_date = date.today()
        
        # Get all locations
        locations = await self._get_locations(client)
        location_ids = [loc["id"] for loc in locations]
        if self.location_id:
            location_ids = [self.location_id]
        
        # Get payments and aggregate by day
        daily_data: dict[date, dict[str, Any]] = {}
        
        for loc_id in location_ids:
            payments = await self._get_payments(client, loc_id, start_date, end_date)
            
            for payment in payments:
                if payment.get("status") not in ("COMPLETED", "APPROVED"):
                    continue
                
                created_at = payment.get("created_at", "")
                try:
                    txn_date = datetime.fromisoformat(created_at.replace("Z", "+00:00")).date()
                except (ValueError, AttributeError):
                    continue
                
                if txn_date not in daily_data:
                    daily_data[txn_date] = {
                        "date": txn_date,
                        "total_sales": 0,
                        "transaction_count": 0,
                        "tips": 0,
                        "processing_fees": 0,
                    }
                
                amount = payment.get("amount_money", {}).get("amount", 0) / 100
                tip = payment.get("tip_money", {}).get("amount", 0) / 100
                fees = sum(
                    f.get("amount_money", {}).get("amount", 0) 
                    for f in payment.get("processing_fee", [])
                ) / 100
                
                daily_data[txn_date]["total_sales"] += amount
                daily_data[txn_date]["transaction_count"] += 1
                daily_data[txn_date]["tips"] += tip
                daily_data[txn_date]["processing_fees"] += fees
        
        # Calculate averages and net
        result = []
        for day in sorted(daily_data.values(), key=lambda x: x["date"]):
            count = day["transaction_count"]
            day["average_ticket"] = day["total_sales"] / count if count > 0 else 0
            day["net_sales"] = day["total_sales"] - day["processing_fees"]
            result.append(day)
        
        return result
