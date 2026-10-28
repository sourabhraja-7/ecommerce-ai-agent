"""
Returns Service — SQLite-backed returns / refund engine.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from src.services.database import get_connection


@dataclass
class ReturnRequest:
    order_id: str
    reason: str
    status: str = "pending"  # pending, approved, rejected, completed
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    refund_amount: float = 0.0
    rma_number: str = ""


RETURN_REASONS = {
    "defective": "Product is defective / malfunctioning",
    "wrong_item": "Wrong item was shipped",
    "not_as_described": "Product doesn't match description",
    "changed_mind": "Changed my mind",
    "damaged": "Package arrived damaged",
    "too_late": "Delivery was too late",
}

RETURN_POLICY = """
📋 **Return Policy Summary:**
- You have **14 days** from delivery to initiate a return.
- Items must be in original packaging and unused.
- Return shipping: **Free for defective/wrong items**, buyer pays for other reasons.
- Refunds are processed within **3-5 business days** after we receive the item.
- Non-returnable items: Clearance/outlet items, hygiene products (earbud tips, etc.)
""".strip()


def _row_to_return(row) -> ReturnRequest:
    return ReturnRequest(
        order_id=row["order_id"],
        reason=row["reason"],
        status=row["status"],
        created_at=row["created_at"],
        refund_amount=row["refund_amount"],
        rma_number=row["rma_number"],
    )


class ReturnsService:
    """SQLite-backed returns engine."""

    def get_policy(self) -> str:
        return RETURN_POLICY

    def create_return(self, order_id: str, reason: str, order_total: float) -> ReturnRequest:
        conn = get_connection()
        try:
            # Numeric max, not string ordering (so RMA-10000 sorts after RMA-9999)
            last = conn.execute(
                "SELECT MAX(CAST(SUBSTR(rma_number, 5) AS INTEGER)) FROM returns"
            ).fetchone()[0]
            rma = f"RMA-{(last + 1) if last else 1000}"

            ret = ReturnRequest(
                order_id=order_id.upper(),
                reason=reason,
                refund_amount=order_total,
                rma_number=rma,
                status="approved",
            )
            conn.execute(
                """INSERT INTO returns (rma_number, order_id, reason, status, refund_amount, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (rma, ret.order_id, reason, ret.status, order_total, ret.created_at),
            )
            conn.commit()
            return ret
        finally:
            conn.close()

    def get_return(self, order_id: str) -> Optional[ReturnRequest]:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM returns WHERE order_id = ? ORDER BY created_at DESC LIMIT 1",
                (order_id.upper(),),
            ).fetchone()
            return _row_to_return(row) if row else None
        finally:
            conn.close()

    def get_all_returns(self) -> list[ReturnRequest]:
        conn = get_connection()
        try:
            rows = conn.execute("SELECT * FROM returns ORDER BY created_at DESC").fetchall()
            return [_row_to_return(r) for r in rows]
        finally:
            conn.close()
