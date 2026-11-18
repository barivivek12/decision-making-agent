"""
Decision-Making Resolution Agent  --  SQLite Database Version
=============================================================
Uses a real SQLite database (resolution_agent.db) instead of dicts.

SETUP (run once):
    python database.py        <-- creates & seeds the DB

THEN run the agent:
    python agent_db.py

Steps implemented:
  1. Functional Tools       -- four isolated, deterministic functions
  2. Tool Schemas           -- declarative contracts (documented)
  3. Tool Registry          -- whitelist + safe dispatcher
  4. Agentic ReAct Loop     -- stateful, multi-step reasoning cycle
  5. Guardrails             -- max iterations, graceful errors, arg validation
"""

import sys
import io
import json
import uuid
import datetime

# Force UTF-8 on Windows console
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from database import get_connection, DB_PATH


# =============================================================================
# STEP 1 -- FUNCTIONAL TOOLS  (now reading/writing a real SQLite database)
# =============================================================================

def lookup_order(order_id: str) -> dict:
    """
    Tool 1: Order Lookup
    Queries the 'orders' table and returns full order details.
    """
    conn = get_connection()
    row  = conn.execute(
        "SELECT * FROM orders WHERE order_id = ?", (order_id,)
    ).fetchone()
    conn.close()

    if row is None:
        return {
            "success": False,
            "error": f"Order '{order_id}' not found in database. Please verify the order ID.",
        }

    return {
        "success":              True,
        "order_id":             row["order_id"],
        "customer_name":        row["customer_name"],
        "email":                row["email"],
        "item_id":              row["item_id"],
        "item_name":            row["item_name"],
        "status":               row["status"],
        "eligible_for_exchange": bool(row["eligible_for_exchange"]),
        "amount_paid":          row["amount_paid"],
    }


def check_inventory(item_id: str) -> dict:
    """
    Tool 2: Inventory Inspection
    Queries the 'inventory' table for real-time stock count.
    """
    conn = get_connection()
    row  = conn.execute(
        "SELECT * FROM inventory WHERE item_id = ?", (item_id,)
    ).fetchone()
    conn.close()

    if row is None:
        return {
            "success": False,
            "error": f"Item '{item_id}' not found in inventory.",
        }

    return {
        "success":   True,
        "item_id":   row["item_id"],
        "item_name": row["item_name"],
        "stock":     row["stock"],
        "available": row["stock"] > 0,
    }


def process_refund(order_id: str, reason: str) -> dict:
    """
    Tool 3: Refund Processing
    Looks up the order, generates a transaction ID, and writes to 'refunds' table.
    """
    conn  = get_connection()
    order = conn.execute(
        "SELECT * FROM orders WHERE order_id = ?", (order_id,)
    ).fetchone()

    if order is None:
        conn.close()
        return {
            "success": False,
            "error": f"Cannot refund: Order '{order_id}' not found.",
        }

    txn_id    = f"TXN-{uuid.uuid4().hex[:8].upper()}"
    amount    = order["amount_paid"]
    timestamp = datetime.datetime.now().isoformat()

    # Write refund record to database
    conn.execute(
        "INSERT INTO refunds VALUES (?, ?, ?, ?, ?)",
        (txn_id, order_id, amount, reason, timestamp)
    )
    conn.commit()
    conn.close()

    return {
        "success":          True,
        "order_id":         order_id,
        "transaction_id":   txn_id,
        "refunded_amount":  amount,
        "reason":           reason,
        "timestamp":        timestamp,
        "message":          f"Refund of ${amount:.2f} issued. Reference: {txn_id}",
    }


def send_notification(email: str, message: str) -> dict:
    """
    Tool 4: Customer Notification
    Logs the email into the 'notifications' table and prints to console.
    """
    if "@" not in email:
        return {"success": False, "error": f"Invalid email: '{email}'."}

    conn      = get_connection()
    timestamp = datetime.datetime.now().isoformat()

    # Persist to database
    conn.execute(
        "INSERT INTO notifications (email, message, sent_at) VALUES (?, ?, ?)",
        (email, message, timestamp)
    )
    conn.commit()
    conn.close()

    print(f"\n  [EMAIL -> {email}]")
    print(f"  {message}")
    print(f"  {'─'*50}")

    return {"success": True, "email": email, "message": "Notification sent and saved to DB."}


# =============================================================================
# STEP 2 -- TOOL SCHEMAS  (declarative contracts — for LLM reference)
# =============================================================================

TOOL_SCHEMAS = {
    "lookup_order": {
        "description": "Look up a customer order by order ID from the database.",
        "parameters":  {"order_id": "string"},
        "required":    ["order_id"],
    },
    "check_inventory": {
        "description": "Check warehouse stock for an item from the database.",
        "parameters":  {"item_id": "string"},
        "required":    ["item_id"],
    },
    "process_refund": {
        "description": "Issue a financial refund. Writes to the refunds table.",
        "parameters":  {"order_id": "string", "reason": "string"},
        "required":    ["order_id", "reason"],
    },
    "send_notification": {
        "description": "Send and save a confirmation email to the customer.",
        "parameters":  {"email": "string", "message": "string"},
        "required":    ["email", "message"],
    },
}


# =============================================================================
# STEP 3 -- TOOL REGISTRY + SAFE DISPATCHER
# =============================================================================

TOOL_REGISTRY = {
    "lookup_order":      lookup_order,
    "check_inventory":   check_inventory,
    "process_refund":    process_refund,
    "send_notification": send_notification,
}


def dispatch_tool(tool_name: str, args: dict) -> dict:
    """
    Safe dispatcher.
    - Rejects unregistered tool names.
    - Wraps execution in try/except for graceful error recovery.
    """
    if tool_name not in TOOL_REGISTRY:
        return {
            "success": False,
            "error": f"Unauthorized: '{tool_name}' is not a registered tool.",
        }
    try:
        return TOOL_REGISTRY[tool_name](**args)
    except TypeError as e:
        return {"success": False, "error": f"Bad arguments for '{tool_name}': {e}"}
    except Exception as e:
        return {"success": False, "error": f"Error in '{tool_name}': {e}"}


# =============================================================================
# MOCK MODEL  --  Simulates LLM tool-calling decisions (no API key needed)
# Replace decide() with a real LLM API call to upgrade to a live model.
# =============================================================================

class MockModel:
    def decide(self, history: list[dict]) -> dict:
        def last_result(tool_name):
            for entry in reversed(history):
                if entry["role"] == "tool" and entry["tool_name"] == tool_name:
                    return entry["content"]
            return None

        order_id   = self._extract_order_id(history)
        order_info = last_result("lookup_order")

        # 1. Look up the order first
        if order_info is None:
            if not order_id:
                return {"type": "final_answer", "text":
                    "I could not find an order ID in your message. "
                    "Please provide your order number (e.g. ORD-1001)."}
            return {"type": "tool_call", "tool": "lookup_order",
                    "args": {"order_id": order_id}}

        # 2. Order not found in DB
        if not order_info["success"]:
            return {"type": "final_answer", "text":
                f"Sorry, I could not locate your order. "
                f"{order_info['error']} Please double-check and try again."}

        # 3. Order ineligible -- refund immediately
        if not order_info["eligible_for_exchange"]:
            refund = last_result("process_refund")
            if refund is None:
                return {"type": "tool_call", "tool": "process_refund",
                        "args": {"order_id": order_info["order_id"],
                                 "reason": "Order not eligible for exchange per policy."}}
            notif = last_result("send_notification")
            if notif is None:
                return {"type": "tool_call", "tool": "send_notification",
                        "args": {"email": order_info["email"],
                                 "message": (
                                    f"Dear {order_info['customer_name']},\n"
                                    f"Order {order_info['order_id']} is not eligible for exchange. "
                                    f"A full refund of ${refund['refunded_amount']:.2f} has been issued. "
                                    f"Ref: {refund['transaction_id']}. We apologize for the inconvenience.")}}
            return {"type": "final_answer", "text":
                f"Hi {order_info['customer_name']}, your order {order_info['order_id']} is not "
                f"eligible for exchange. A refund of ${refund['refunded_amount']:.2f} has been "
                f"processed (Ref: {refund['transaction_id']}). "
                f"Confirmation sent to {order_info['email']}."}

        # 4. Check inventory
        inv = last_result("check_inventory")
        if inv is None:
            return {"type": "tool_call", "tool": "check_inventory",
                    "args": {"item_id": order_info["item_id"]}}

        # 5a. Stock available -- Exchange
        if inv["available"]:
            notif = last_result("send_notification")
            if notif is None:
                return {"type": "tool_call", "tool": "send_notification",
                        "args": {"email": order_info["email"],
                                 "message": (
                                    f"Dear {order_info['customer_name']},\n"
                                    f"Great news! A replacement {order_info['item_name']} is in stock. "
                                    f"Your exchange for order {order_info['order_id']} is confirmed. "
                                    f"Your new unit will be dispatched shortly!")}}
            return {"type": "final_answer", "text":
                f"Hi {order_info['customer_name']}, great news! "
                f"We have {inv['stock']} unit(s) of {order_info['item_name']} available. "
                f"Your exchange for order {order_info['order_id']} is confirmed. "
                f"Confirmation sent to {order_info['email']}."}

        # 5b. Stock = 0 -- Refund
        refund = last_result("process_refund")
        if refund is None:
            return {"type": "tool_call", "tool": "process_refund",
                    "args": {"order_id": order_info["order_id"],
                             "reason": f"{order_info['item_name']} is out of stock."}}
        notif = last_result("send_notification")
        if notif is None:
            return {"type": "tool_call", "tool": "send_notification",
                    "args": {"email": order_info["email"],
                             "message": (
                                f"Dear {order_info['customer_name']},\n"
                                f"We're sorry -- {order_info['item_name']} is out of stock. "
                                f"A full refund of ${refund['refunded_amount']:.2f} has been issued. "
                                f"Ref: {refund['transaction_id']}. We apologize for the inconvenience.")}}
        return {"type": "final_answer", "text":
            f"Hi {order_info['customer_name']}, unfortunately {order_info['item_name']} "
            f"is out of stock. A full refund of ${refund['refunded_amount']:.2f} has been issued "
            f"(Ref: {refund['transaction_id']}). Confirmation sent to {order_info['email']}."}

    @staticmethod
    def _extract_order_id(history):
        import re
        for entry in history:
            if entry["role"] == "user":
                m = re.search(r"ORD-\d+", entry["content"], re.IGNORECASE)
                if m:
                    return m.group(0).upper()
        return None


# =============================================================================
# STEP 4 + 5 -- AGENTIC ReAct LOOP WITH GUARDRAILS
# =============================================================================

MAX_ITERATIONS = 10


def run_agent(user_request: str) -> str:
    model   = MockModel()
    history = [{"role": "user", "content": user_request}]

    print(f"\n{'='*60}")
    print("AGENT STARTED")
    print(f"{'='*60}")
    print(f"User: {user_request}\n")

    for iteration in range(1, MAX_ITERATIONS + 1):
        print(f"-- Iteration {iteration}/{MAX_ITERATIONS} -------------------------")

        decision = model.decide(history)

        # Final answer -- exit loop
        if decision["type"] == "final_answer":
            answer = decision["text"]
            print(f"\n[AGENT RESPONSE]\n{answer}")
            print(f"{'='*60}\n")
            return answer

        # Tool call -- dispatch and record
        tool_name = decision["tool"]
        args      = decision.get("args", {})
        print(f"  [TOOL CALL] {tool_name}({json.dumps(args)})")

        result = dispatch_tool(tool_name, args)
        print(f"  [RESULT]    {json.dumps(result)}")

        history.append({"role": "model", "content": f"Calling: {tool_name}"})
        history.append({"role": "tool",  "tool_name": tool_name, "content": result})

    # Guardrail: escalate
    msg = "[WARNING] Max iterations reached. Flagged for human escalation."
    print(f"\n{msg}\n{'='*60}\n")
    return msg


# =============================================================================
# DEMO
# =============================================================================

if __name__ == "__main__":

    print(f"\n[DB] Using database: {DB_PATH}\n")

    print("#"*60)
    print("  SCENARIO 1: Stock = 0 --> REFUND")
    print("#"*60)
    run_agent("My order ORD-1001 arrived damaged. Please help.")

    print("#"*60)
    print("  SCENARIO 2: Stock > 0 --> EXCHANGE")
    print("#"*60)
    run_agent("I got a faulty Bluetooth Speaker. Order ORD-1002.")

    print("#"*60)
    print("  SCENARIO 3: Ineligible order --> REFUND (policy)")
    print("#"*60)
    run_agent("My Smart Watch is broken. Order ORD-1003.")

    print("#"*60)
    print("  SCENARIO 4: Invalid order ID --> graceful error")
    print("#"*60)
    run_agent("My order ORD-9999 has an issue.")

    # Show what was written to the database
    print("\n" + "="*60)
    print("DATABASE AUDIT LOGS")
    print("="*60)
    conn = get_connection()
    print("\n--- REFUNDS TABLE ---")
    for row in conn.execute("SELECT * FROM refunds"):
        print(dict(row))
    print("\n--- NOTIFICATIONS TABLE ---")
    for row in conn.execute("SELECT * FROM notifications"):
        r = dict(row)
        r["message"] = r["message"][:60] + "..."   # truncate for display
        print(r)
    conn.close()
