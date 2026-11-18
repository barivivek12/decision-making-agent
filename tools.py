"""
tools.py — Step 1: Functional Tool Implementations
Each function is an isolated, deterministic action the agent can invoke.
All functions return structured dicts with a 'success' status indicator.
"""

import uuid
import datetime
from typing import Any

# ---------------------------------------------------------------------------
# Simulated In-Memory Data Stores
# ---------------------------------------------------------------------------

ORDERS_DB: dict[str, dict] = {
    "ORD-1001": {
        "order_id": "ORD-1001",
        "customer_name": "Alice Johnson",
        "customer_email": "alice@example.com",
        "item_id": "ITEM-PRO-X",
        "item_name": "ProX Wireless Headphones",
        "order_status": "delivered",
        "eligible_for_exchange": True,
        "amount_paid": 149.99,
        "currency": "USD",
        "payment_method": "Visa ending in 4242",
    },
    "ORD-1002": {
        "order_id": "ORD-1002",
        "customer_name": "Bob Martinez",
        "customer_email": "bob@example.com",
        "item_id": "ITEM-ULTRA-Y",
        "item_name": "UltraY Smart Watch",
        "order_status": "delivered",
        "eligible_for_exchange": True,
        "amount_paid": 299.00,
        "currency": "USD",
        "payment_method": "Mastercard ending in 8891",
    },
    "ORD-1003": {
        "order_id": "ORD-1003",
        "customer_name": "Clara Singh",
        "customer_email": "clara@example.com",
        "item_id": "ITEM-ECHO-Z",
        "item_name": "EchoZ Bluetooth Speaker",
        "order_status": "delivered",
        "eligible_for_exchange": False,  # past return window
        "amount_paid": 89.50,
        "currency": "USD",
        "payment_method": "PayPal",
    },
}

WAREHOUSE_DB: dict[str, dict] = {
    "ITEM-PRO-X":   {"item_id": "ITEM-PRO-X",   "item_name": "ProX Wireless Headphones", "stock": 0},   # out of stock → triggers refund
    "ITEM-ULTRA-Y": {"item_id": "ITEM-ULTRA-Y",  "item_name": "UltraY Smart Watch",       "stock": 7},   # in stock → exchange
    "ITEM-ECHO-Z":  {"item_id": "ITEM-ECHO-Z",   "item_name": "EchoZ Bluetooth Speaker",  "stock": 3},
}

REFUND_LEDGER: list[dict] = []
NOTIFICATION_LOG: list[dict] = []


# ---------------------------------------------------------------------------
# Tool 1 — Order Lookup
# ---------------------------------------------------------------------------

def lookup_order(order_id: str) -> dict[str, Any]:
    """
    Retrieve full order details from the database by order ID.

    Args:
        order_id: The unique order identifier (e.g. 'ORD-1001').

    Returns:
        Structured dict with order details or an error payload.
    """
    order_id = str(order_id).strip().upper()
    if order_id not in ORDERS_DB:
        return {
            "success": False,
            "error": f"Order '{order_id}' was not found in the database. "
                     "Please verify the order ID and try again.",
        }
    record = ORDERS_DB[order_id]
    return {
        "success": True,
        "order_id": record["order_id"],
        "customer_name": record["customer_name"],
        "customer_email": record["customer_email"],
        "item_id": record["item_id"],
        "item_name": record["item_name"],
        "order_status": record["order_status"],
        "eligible_for_exchange": record["eligible_for_exchange"],
        "amount_paid": record["amount_paid"],
        "currency": record["currency"],
        "payment_method": record["payment_method"],
    }


# ---------------------------------------------------------------------------
# Tool 2 — Inventory Inspection
# ---------------------------------------------------------------------------

def check_inventory(item_id: str) -> dict[str, Any]:
    """
    Query the warehouse for real-time stock levels of a given item.

    Args:
        item_id: The unique item/SKU identifier (e.g. 'ITEM-PRO-X').

    Returns:
        Structured dict with stock count and availability flag or an error payload.
    """
    item_id = str(item_id).strip().upper()
    if item_id not in WAREHOUSE_DB:
        return {
            "success": False,
            "error": f"Item '{item_id}' was not found in the warehouse catalogue.",
        }
    record = WAREHOUSE_DB[item_id]
    stock = record["stock"]
    return {
        "success": True,
        "item_id": record["item_id"],
        "item_name": record["item_name"],
        "stock_count": stock,
        "available": stock > 0,
    }


# ---------------------------------------------------------------------------
# Tool 3 — Refund Processing
# ---------------------------------------------------------------------------

def process_refund(order_id: str, reason: str) -> dict[str, Any]:
    """
    Issue a financial refund to the customer's original payment method.

    Args:
        order_id: The order identifier to refund.
        reason:   A brief description of why the refund is being issued.

    Returns:
        Structured dict with the refund transaction reference and amount,
        or an error payload.
    """
    order_id = str(order_id).strip().upper()
    if order_id not in ORDERS_DB:
        return {
            "success": False,
            "error": f"Cannot process refund — order '{order_id}' not found.",
        }
    order = ORDERS_DB[order_id]
    transaction_ref = f"REF-{uuid.uuid4().hex[:10].upper()}"
    timestamp = datetime.datetime.utcnow().isoformat() + "Z"
    ledger_entry = {
        "transaction_ref": transaction_ref,
        "order_id": order_id,
        "customer_email": order["customer_email"],
        "amount_refunded": order["amount_paid"],
        "currency": order["currency"],
        "payment_method": order["payment_method"],
        "reason": reason,
        "timestamp": timestamp,
    }
    REFUND_LEDGER.append(ledger_entry)
    return {
        "success": True,
        "transaction_ref": transaction_ref,
        "order_id": order_id,
        "amount_refunded": order["amount_paid"],
        "currency": order["currency"],
        "payment_method": order["payment_method"],
        "timestamp": timestamp,
        "message": f"Refund of {order['currency']} {order['amount_paid']:.2f} "
                   f"successfully initiated to {order['payment_method']}.",
    }


# ---------------------------------------------------------------------------
# Tool 4 — Customer Notification
# ---------------------------------------------------------------------------

def send_notification(customer_email: str, message: str) -> dict[str, Any]:
    """
    Send a confirmation email notification to the customer.

    Args:
        customer_email: The recipient's email address.
        message:        The body of the notification message.

    Returns:
        Structured dict confirming dispatch, or an error payload.
    """
    customer_email = str(customer_email).strip()
    message = str(message).strip()

    if "@" not in customer_email:
        return {
            "success": False,
            "error": f"'{customer_email}' does not appear to be a valid email address.",
        }
    if not message:
        return {
            "success": False,
            "error": "Notification message body cannot be empty.",
        }

    notification_id = f"NOTIF-{uuid.uuid4().hex[:8].upper()}"
    timestamp = datetime.datetime.utcnow().isoformat() + "Z"
    log_entry = {
        "notification_id": notification_id,
        "recipient": customer_email,
        "message": message,
        "timestamp": timestamp,
        "status": "sent",
    }
    NOTIFICATION_LOG.append(log_entry)

    return {
        "success": True,
        "notification_id": notification_id,
        "recipient": customer_email,
        "timestamp": timestamp,
        "message": f"Notification successfully dispatched to {customer_email}.",
    }
