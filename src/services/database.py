"""
SQLite Database Module — persistent storage for the e-commerce support agent.

Tables:
  - orders: customer orders with items (JSON), status, tracking
  - shipments: carrier tracking with event history (JSON)
  - returns: return requests with RMA tracking
"""
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from src.config import settings


def get_connection() -> sqlite3.Connection:
    """Get a connection to the SQLite database."""
    db_path = Path(settings.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    order_id         TEXT PRIMARY KEY,
    customer_name    TEXT NOT NULL,
    email            TEXT NOT NULL,
    items            TEXT NOT NULL,         -- JSON array of {product_name, sku, quantity, price}
    status           TEXT NOT NULL DEFAULT 'confirmed',
    total            REAL NOT NULL,
    created_at       TEXT NOT NULL,
    shipping_address TEXT NOT NULL,
    tracking_number  TEXT
);

CREATE TABLE IF NOT EXISTS shipments (
    tracking_number    TEXT PRIMARY KEY,
    carrier            TEXT NOT NULL,
    status             TEXT NOT NULL DEFAULT 'label_created',
    estimated_delivery TEXT,
    events             TEXT NOT NULL DEFAULT '[]'  -- JSON array of {timestamp, location, description}
);

CREATE TABLE IF NOT EXISTS returns (
    rma_number    TEXT PRIMARY KEY,
    order_id      TEXT NOT NULL REFERENCES orders(order_id),
    reason        TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending',
    refund_amount REAL NOT NULL,
    created_at    TEXT NOT NULL
);
"""


def init_db(reset: bool = False):
    """Create tables and seed data if empty. `reset=True` wipes and reseeds."""
    conn = get_connection()
    try:
        if reset:
            conn.executescript(
                "DROP TABLE IF EXISTS returns; DROP TABLE IF EXISTS shipments; DROP TABLE IF EXISTS orders;"
            )
        conn.executescript(SCHEMA)

        # Only seed if database is empty
        count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        if count == 0:
            _seed_data(conn)

        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Seed Data — 12 orders, diverse scenarios
# ---------------------------------------------------------------------------

def _seed_data(conn: sqlite3.Connection):
    now = datetime.now()

    def ago(**kw) -> str:
        return (now - timedelta(**kw)).isoformat()

    def day(offset: int) -> str:
        return (now + timedelta(days=offset)).strftime("%Y-%m-%d")

    # (order_id, name, email, items, status, total, created_at, address, tracking)
    orders = [
        ("ORD-1001", "James Wilson", "james@example.com",
         [{"product_name": "Wireless Headphones", "sku": "SKU-501", "quantity": 1, "price": 79.99},
          {"product_name": "USB-C Cable", "sku": "SKU-102", "quantity": 2, "price": 12.99}],
         "delivered", 105.97, ago(days=12),
         "742 Evergreen Terrace, Springfield, IL 62701", "FDX-78901234"),

        ("ORD-1002", "Sarah Chen", "sarah@example.com",
         [{"product_name": "Mechanical Keyboard", "sku": "SKU-201", "quantity": 1, "price": 149.99}],
         "shipped", 149.99, ago(days=4),
         "221B Baker Street, London, NW1 6XE", "UPS-45678901"),

        ("ORD-1003", "Marcus Rivera", "marcus@example.com",
         [{"product_name": "27\" 4K Monitor", "sku": "SKU-305", "quantity": 1, "price": 499.99}],
         "confirmed", 499.99, ago(hours=6),
         "350 Fifth Avenue, New York, NY 10118", None),

        ("ORD-1004", "Emily Foster", "emily@example.com",
         [{"product_name": "Wireless Mouse", "sku": "SKU-410", "quantity": 1, "price": 49.99},
          {"product_name": "XL Mousepad", "sku": "SKU-411", "quantity": 1, "price": 19.99}],
         "cancelled", 69.98, ago(days=3),
         "1 Infinite Loop, Cupertino, CA 95014", None),

        ("ORD-1005", "David Kim", "david@example.com",
         [{"product_name": "Wireless Charger", "sku": "SKU-601", "quantity": 1, "price": 39.99}],
         "delivered", 39.99, ago(days=5),
         "1600 Amphitheatre Pkwy, Mountain View, CA 94043", "DHL-11223344"),

        ("ORD-1006", "Olivia Brown", "olivia@example.com",
         [{"product_name": "Tablet Stand", "sku": "SKU-701", "quantity": 1, "price": 29.99},
          {"product_name": "Screen Protector", "sku": "SKU-702", "quantity": 2, "price": 9.99}],
         "shipped", 49.97, ago(days=2),
         "4059 Mt Lee Dr, Hollywood, CA 90068", "UPS-99887766"),

        ("ORD-1007", "Alex Turner", "alex@example.com",
         [{"product_name": "1TB Portable SSD", "sku": "SKU-801", "quantity": 1, "price": 129.99}],
         "confirmed", 129.99, ago(hours=2),
         "10 Downing Street, London, SW1A 2AA", None),

        ("ORD-1008", "Sophia Martinez", "sophia@example.com",
         [{"product_name": "Smartwatch Pro", "sku": "SKU-901", "quantity": 1, "price": 299.99}],
         "delivered", 299.99, ago(days=16),
         "5th Ave & 59th St, New York, NY 10022", "FDX-55667788"),

        ("ORD-1009", "Daniel Park", "daniel@example.com",
         [{"product_name": "Bluetooth Speaker", "sku": "SKU-1001", "quantity": 1, "price": 89.99}],
         "delivered", 89.99, ago(days=1),
         "100 Broadway, New York, NY 10005", "DHL-99001122"),

        ("ORD-1010", "Rachel Green", "rachel@example.com",
         [{"product_name": "Laptop Sleeve", "sku": "SKU-1101", "quantity": 1, "price": 34.99}],
         "shipped", 34.99, ago(days=6),
         "90 Bedford St, New York, NY 10014", "FDX-33445566"),

        ("ORD-1011", "James Wilson", "james@example.com",
         [{"product_name": "HD Webcam", "sku": "SKU-1201", "quantity": 1, "price": 89.99}],
         "shipped", 89.99, ago(days=1),
         "742 Evergreen Terrace, Springfield, IL 62701", "UPS-11223344"),

        ("ORD-1012", "Grace Patel", "grace@example.com",
         [{"product_name": "Wireless Earbuds", "sku": "SKU-502", "quantity": 2, "price": 79.99},
          {"product_name": "Phone Case", "sku": "SKU-1301", "quantity": 1, "price": 24.99},
          {"product_name": "Car Charger", "sku": "SKU-1302", "quantity": 1, "price": 19.99}],
         "delivered", 204.96, ago(days=7),
         "555 Market St, San Francisco, CA 94105", "DHL-77889900"),
    ]

    for o in orders:
        conn.execute(
            "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (o[0], o[1], o[2], json.dumps(o[3]), o[4], o[5], o[6], o[7], o[8]),
        )

    # --- Shipments (9 tracking records) ---
    def ev(when: str, location: str, description: str) -> dict:
        return {"timestamp": when, "location": location, "description": description}

    shipments = [
        ("FDX-78901234", "FedEx", "delivered", day(-2), [
            ev(ago(days=12), "Chicago, IL", "Package picked up"),
            ev(ago(days=10), "Memphis, TN", "Arrived at FedEx hub"),
            ev(ago(days=4), "Springfield, IL", "Out for delivery"),
            ev(ago(days=2), "Springfield, IL", "Delivered"),
        ]),
        ("UPS-45678901", "UPS", "in_transit", day(2), [
            ev(ago(days=4), "London, UK", "Package picked up"),
            ev(ago(days=1), "Stansted, UK", "Processing at UPS facility"),
        ]),
        ("DHL-11223344", "DHL", "delivered", day(-3), [
            ev(ago(days=5), "San Jose, CA", "Package picked up"),
            ev(ago(days=3), "Mountain View, CA", "Delivered"),
        ]),
        ("UPS-99887766", "UPS", "out_for_delivery", day(0), [
            ev(ago(days=2), "Burbank, CA", "Package picked up"),
            ev(ago(hours=6), "Hollywood, CA", "Out for delivery"),
        ]),
        ("FDX-55667788", "FedEx", "delivered", day(-14), [
            ev(ago(days=16), "Newark, NJ", "Package picked up"),
            ev(ago(days=14), "New York, NY", "Delivered"),
        ]),
        ("DHL-99001122", "DHL", "delivered", day(-1), [
            ev(ago(days=3), "Jersey City, NJ", "Package picked up"),
            ev(ago(days=1), "New York, NY", "Delivered"),
        ]),
        ("FDX-33445566", "FedEx", "in_transit", day(4), [
            ev(ago(days=6), "New York, NY", "Package picked up"),
            ev(ago(days=3), "Paris, FR", "International transit hub"),
        ]),
        ("UPS-11223344", "UPS", "in_transit", day(1), [
            ev(ago(days=1), "Springfield, IL", "Package picked up"),
            ev(ago(hours=3), "Chicago, IL", "Arrived at local facility"),
        ]),
        ("DHL-77889900", "DHL", "delivered", day(-5), [
            ev(ago(days=7), "Oakland, CA", "Package picked up"),
            ev(ago(days=5), "San Francisco, CA", "Delivered"),
        ]),
    ]

    for s in shipments:
        conn.execute(
            "INSERT INTO shipments VALUES (?, ?, ?, ?, ?)",
            (s[0], s[1], s[2], s[3], json.dumps(s[4])),
        )

    conn.commit()
    print(f"✅ SQLite seeded: {len(orders)} orders, {len(shipments)} shipments")
