"""
Order Service — SQLite-backed order management.
"""
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from src.services.database import get_connection

RETURN_WINDOW_DAYS = 14


@dataclass
class OrderItem:
    product_name: str
    sku: str
    quantity: int
    price: float


@dataclass
class Order:
    order_id: str
    customer_name: str
    email: str
    items: list[OrderItem]
    status: str  # confirmed, shipped, delivered, cancelled
    total: float
    created_at: str
    shipping_address: str
    tracking_number: Optional[str] = None


def _row_to_order(row) -> Order:
    return Order(
        order_id=row["order_id"],
        customer_name=row["customer_name"],
        email=row["email"],
        items=[OrderItem(**i) for i in json.loads(row["items"])],
        status=row["status"],
        total=row["total"],
        created_at=row["created_at"],
        shipping_address=row["shipping_address"],
        tracking_number=row["tracking_number"],
    )


class OrderService:
    """SQLite-backed order management."""

    def get_order(self, order_id: str) -> Optional[Order]:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM orders WHERE order_id = ?", (order_id.strip().upper(),)
            ).fetchone()
            return _row_to_order(row) if row else None
        finally:
            conn.close()

    def get_orders_by_email(self, email: str) -> list[Order]:
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM orders WHERE email = ? ORDER BY created_at DESC",
                (email.strip().lower(),),
            ).fetchall()
            return [_row_to_order(r) for r in rows]
        finally:
            conn.close()

    def get_all_orders(self) -> list[Order]:
        conn = get_connection()
        try:
            rows = conn.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
            return [_row_to_order(r) for r in rows]
        finally:
            conn.close()

    def search_orders(self, query: str) -> list[Order]:
        """Search by order ID, customer name, or product name."""
        conn = get_connection()
        try:
            pattern = f"%{query.strip()}%"
            rows = conn.execute(
                """SELECT * FROM orders
                   WHERE order_id LIKE ? OR customer_name LIKE ? OR items LIKE ?
                   ORDER BY created_at DESC""",
                (pattern, pattern, pattern),
            ).fetchall()
            return [_row_to_order(r) for r in rows]
        finally:
            conn.close()

    def can_return(self, order_id: str) -> tuple[bool, str]:
        """Check if an order is eligible for return (delivered, within window, not already returned)."""
        order = self.get_order(order_id)
        if not order:
            return False, f"Order {order_id} not found."
        if order.status == "cancelled":
            return False, "Cancelled orders cannot be returned."
        if order.status != "delivered":
            return False, f"Order has not been delivered yet (status: {order.status})."
        if datetime.now() - datetime.fromisoformat(order.created_at) > timedelta(days=RETURN_WINDOW_DAYS):
            return False, f"The {RETURN_WINDOW_DAYS}-day return window has expired."

        conn = get_connection()
        try:
            existing = conn.execute(
                "SELECT rma_number FROM returns WHERE order_id = ?", (order.order_id,)
            ).fetchone()
        finally:
            conn.close()
        if existing:
            return False, f"A return already exists for this order ({existing['rma_number']})."

        return True, "Order is eligible for return."
