"""
database.py  —  SQLite setup for the Resolution Agent
======================================================
Run this ONCE to create and seed the database:
    python database.py

Creates:  resolution_agent.db
Tables:   orders, inventory, refunds, notifications
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "resolution_agent.db")


def get_connection():
    """Return a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row   # rows behave like dicts
    return conn


def init_db():
    """Create tables and seed sample data."""
    conn = get_connection()
    cur  = conn.cursor()

    # ── ORDERS table ──────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id              TEXT PRIMARY KEY,
            customer_name         TEXT NOT NULL,
            email                 TEXT NOT NULL,
            item_id               TEXT NOT NULL,
            item_name             TEXT NOT NULL,
            status                TEXT NOT NULL,
            eligible_for_exchange INTEGER NOT NULL,   -- 1=yes, 0=no
            amount_paid           REAL NOT NULL
        )
    """)

    # ── INVENTORY table ───────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            item_id   TEXT PRIMARY KEY,
            item_name TEXT NOT NULL,
            stock     INTEGER NOT NULL
        )
    """)

    # ── REFUNDS table (audit log) ─────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS refunds (
            transaction_id TEXT PRIMARY KEY,
            order_id       TEXT NOT NULL,
            refunded_amount REAL NOT NULL,
            reason         TEXT NOT NULL,
            created_at     TEXT NOT NULL
        )
    """)

    # ── NOTIFICATIONS table (audit log) ───────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            email      TEXT NOT NULL,
            message    TEXT NOT NULL,
            sent_at    TEXT NOT NULL
        )
    """)

    # ── Seed Orders ───────────────────────────────────────────────────────────
    orders = [
        ("ORD-1001", "Alice Johnson", "alice@example.com",
         "ITEM-A", "Wireless Headphones", "delivered", 1, 89.99),
        ("ORD-1002", "Bob Smith",     "bob@example.com",
         "ITEM-B", "Bluetooth Speaker",  "delivered", 1, 49.99),
        ("ORD-1003", "Carol White",   "carol@example.com",
         "ITEM-C", "Smart Watch",        "delivered", 0, 199.99),
    ]
    cur.executemany("""
        INSERT OR IGNORE INTO orders
        VALUES (?,?,?,?,?,?,?,?)
    """, orders)

    # ── Seed Inventory ────────────────────────────────────────────────────────
    inventory = [
        ("ITEM-A", "Wireless Headphones", 0),   # out of stock
        ("ITEM-B", "Bluetooth Speaker",   5),   # in stock
        ("ITEM-C", "Smart Watch",         3),   # in stock (but order ineligible)
    ]
    cur.executemany("""
        INSERT OR IGNORE INTO inventory
        VALUES (?,?,?)
    """, inventory)

    conn.commit()
    conn.close()
    print(f"[DB] Database ready at: {DB_PATH}")


if __name__ == "__main__":
    init_db()

    # Quick verification — print table contents
    conn = get_connection()
    print("\n--- ORDERS ---")
    for row in conn.execute("SELECT * FROM orders"):
        print(dict(row))
    print("\n--- INVENTORY ---")
    for row in conn.execute("SELECT * FROM inventory"):
        print(dict(row))
    conn.close()
