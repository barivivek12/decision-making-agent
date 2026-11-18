import sys
import io

# Force UTF-8 on Windows console
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

"""
Decision-Making Resolution Agent  --  NO API KEY VERSION
=========================================================
This version replaces the real LLM with a MockModel -- a simple
rule-based function that simulates the model's tool-calling decisions.

The ENTIRE agentic architecture is preserved:
  Step 1: Functional Tools       – four isolated, deterministic functions
  Step 2: Tool Schemas           – declarative contracts (kept for documentation)
  Step 3: Tool Registry          – whitelist + safe dispatcher
  Step 4: Agentic ReAct Loop     – stateful, multi-step reasoning cycle
  Step 5: Guardrails             – max iterations, graceful errors, arg validation

Swap MockModel.decide() with a real LLM call later and nothing else changes.
"""

import json
import uuid
import datetime

# =============================================================================
# STEP 1 -- FUNCTIONAL TOOLS
# Isolated, deterministic functions that return structured payloads.
# =============================================================================

# In-memory order database
ORDER_DB = {
    "ORD-1001": {
        "customer_name": "Alice Johnson",
        "email": "alice@example.com",
        "item_id": "ITEM-A",
        "item_name": "Wireless Headphones",
        "status": "delivered",
        "eligible_for_exchange": True,
        "amount_paid": 89.99,
    },
    "ORD-1002": {
        "customer_name": "Bob Smith",
        "email": "bob@example.com",
        "item_id": "ITEM-B",
        "item_name": "Bluetooth Speaker",
        "status": "delivered",
        "eligible_for_exchange": True,
        "amount_paid": 49.99,
    },
    "ORD-1003": {
        "customer_name": "Carol White",
        "email": "carol@example.com",
        "item_id": "ITEM-C",
        "item_name": "Smart Watch",
        "status": "delivered",
        "eligible_for_exchange": False,       # ineligible order
        "amount_paid": 199.99,
    },
}

# In-memory warehouse inventory
INVENTORY_DB = {
    "ITEM-A": {"item_name": "Wireless Headphones", "stock": 0},   # out of stock
    "ITEM-B": {"item_name": "Bluetooth Speaker",   "stock": 5},   # in stock
    "ITEM-C": {"item_name": "Smart Watch",         "stock": 3},   # in stock, but order ineligible
}

NOTIFICATIONS_SENT = []   # simple in-memory log


def lookup_order(order_id: str) -> dict:
    """Tool 1 – Fetch order details from the database."""
    order = ORDER_DB.get(order_id)
    if not order:
        return {
            "success": False,
            "error": f"Order '{order_id}' not found. Please verify the order ID.",
        }
    return {
        "success": True,
        "order_id": order_id,
        "customer_name": order["customer_name"],
        "email": order["email"],
        "item_id": order["item_id"],
        "item_name": order["item_name"],
        "status": order["status"],
        "eligible_for_exchange": order["eligible_for_exchange"],
        "amount_paid": order["amount_paid"],
    }


def check_inventory(item_id: str) -> dict:
    """Tool 2 – Check real-time warehouse stock for an item."""
    item = INVENTORY_DB.get(item_id)
    if not item:
        return {
            "success": False,
            "error": f"Item '{item_id}' not found in inventory.",
        }
    return {
        "success": True,
        "item_id": item_id,
        "item_name": item["item_name"],
        "stock": item["stock"],
        "available": item["stock"] > 0,
    }


def process_refund(order_id: str, reason: str) -> dict:
    """Tool 3 – Issue a financial refund for an order."""
    order = ORDER_DB.get(order_id)
    if not order:
        return {
            "success": False,
            "error": f"Cannot refund: Order '{order_id}' not found.",
        }
    txn_id = f"TXN-{uuid.uuid4().hex[:8].upper()}"
    return {
        "success": True,
        "order_id": order_id,
        "transaction_id": txn_id,
        "refunded_amount": order["amount_paid"],
        "reason": reason,
        "timestamp": datetime.datetime.now().isoformat(),
        "message": (
            f"Refund of ${order['amount_paid']:.2f} issued. "
            f"Reference: {txn_id}"
        ),
    }


def send_notification(email: str, message: str) -> dict:
    """Tool 4 – Dispatch a confirmation email to the customer."""
    if "@" not in email:
        return {"success": False, "error": f"Invalid email: '{email}'."}

    NOTIFICATIONS_SENT.append({
        "to": email,
        "message": message,
        "sent_at": datetime.datetime.now().isoformat(),
    })
    print(f"\n  [EMAIL -> {email}]")
    # encode to ASCII for Windows console compatibility
    safe_msg = message.encode("ascii", errors="replace").decode("ascii")
    print(f"  {safe_msg}")
    print(f"  {'─'*50}")
    return {"success": True, "email": email, "message": "Notification sent."}


# =============================================================================
# STEP 2 -- TOOL SCHEMAS  (declarative contracts -- kept for documentation/reference)
# In a real agent these are sent to the LLM so it knows how to call each tool.
# =============================================================================

TOOL_SCHEMAS = {
    "lookup_order": {
        "description": "Look up a customer order by order ID.",
        "parameters": {"order_id": "string -- the order identifier (e.g. 'ORD-1001')"},
        "required": ["order_id"],
    },
    "check_inventory": {
        "description": "Check warehouse stock for a given item.",
        "parameters": {"item_id": "string -- the item identifier (e.g. 'ITEM-A')"},
        "required": ["item_id"],
    },
    "process_refund": {
        "description": "Issue a financial refund. Use when exchange is impossible.",
        "parameters": {
            "order_id": "string -- the order to refund",
            "reason":   "string -- reason for the refund",
        },
        "required": ["order_id", "reason"],
    },
    "send_notification": {
        "description": "Send confirmation email to the customer.",
        "parameters": {
            "email":   "string -- customer email address",
            "message": "string -- full message body",
        },
        "required": ["email", "message"],
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
    - Rejects tools not in the whitelist registry.
    - Catches argument/runtime errors, returns structured error payloads.
    """
    # Authorization check
    if tool_name not in TOOL_REGISTRY:
        return {
            "success": False,
            "error": f"Unauthorized: '{tool_name}' is not a registered tool.",
        }

    # Argument validation + execution
    try:
        return TOOL_REGISTRY[tool_name](**args)
    except TypeError as e:
        return {"success": False, "error": f"Bad arguments for '{tool_name}': {e}"}
    except Exception as e:
        return {"success": False, "error": f"Error in '{tool_name}': {e}"}


# =============================================================================
# MOCK MODEL  --  Simulates LLM tool-calling decisions
# =============================================================================
# This replaces the Gemini/OpenAI API call.
# It reads the conversation history and decides what to do next.
# To use a real LLM: replace MockModel.decide() with an API call.
# =============================================================================

class MockModel:
    """
    Rule-based simulator of a tool-using LLM.

    decide(history) returns either:
      {"type": "tool_call", "tool": "<name>", "args": {...}}
      {"type": "final_answer", "text": "<message>"}
    """

    def decide(self, history: list[dict]) -> dict:
        """
        Read the conversation history and decide the next action.
        Each entry in history is: {"role": ..., "content": ...}
        """

        # ── Helper: search history for a previous tool result ────────────
        def last_result(tool_name: str) -> dict | None:
            for entry in reversed(history):
                if entry["role"] == "tool" and entry["tool_name"] == tool_name:
                    return entry["content"]
            return None

        # ── Extract the user's order ID from the first user message ─────
        order_id = self._extract_order_id(history)

        # ─────────────────────────────────────────────────────────────────
        # DECISION 1: If we have no order info yet, look it up
        # ─────────────────────────────────────────────────────────────────
        order_info = last_result("lookup_order")
        if order_info is None:
            if not order_id:
                return {
                    "type": "final_answer",
                    "text": (
                        "I'm sorry, I couldn't find an order ID in your message. "
                        "Could you please provide your order number (e.g. ORD-1001)?"
                    ),
                }
            return {"type": "tool_call", "tool": "lookup_order", "args": {"order_id": order_id}}

        # ─────────────────────────────────────────────────────────────────
        # DECISION 2: If order lookup failed, report it and stop
        # ─────────────────────────────────────────────────────────────────
        if not order_info["success"]:
            return {
                "type": "final_answer",
                "text": (
                    f"I'm sorry, I was unable to locate your order. "
                    f"Details: {order_info['error']} "
                    f"Please double-check your order ID and try again."
                ),
            }

        # ─────────────────────────────────────────────────────────────────
        # DECISION 3: If the order is ineligible for exchange, refund immediately
        # ─────────────────────────────────────────────────────────────────
        if not order_info["eligible_for_exchange"]:
            refund_info = last_result("process_refund")
            if refund_info is None:
                return {
                    "type": "tool_call",
                    "tool": "process_refund",
                    "args": {
                        "order_id": order_info["order_id"],
                        "reason":   "Order is not eligible for exchange per policy.",
                    },
                }
            # Refund done -- now notify
            notif = last_result("send_notification")
            if notif is None:
                return {
                    "type": "tool_call",
                    "tool": "send_notification",
                    "args": {
                        "email": order_info["email"],
                        "message": (
                            f"Dear {order_info['customer_name']},\n"
                            f"Your order {order_info['order_id']} is not eligible for an exchange "
                            f"per our return policy. We have issued a full refund of "
                            f"${refund_info['refunded_amount']:.2f}. "
                            f"Transaction ID: {refund_info['transaction_id']}.\n"
                            f"We apologize for the inconvenience."
                        ),
                    },
                }
            # All done
            return {
                "type": "final_answer",
                "text": (
                    f"Hi {order_info['customer_name']}, your order {order_info['order_id']} "
                    f"is not eligible for an exchange. A full refund of "
                    f"${refund_info['refunded_amount']:.2f} has been processed "
                    f"(Ref: {refund_info['transaction_id']}). "
                    f"A confirmation email has been sent to {order_info['email']}. "
                    f"We apologize for the inconvenience!"
                ),
            }

        # ─────────────────────────────────────────────────────────────────
        # DECISION 4: Order is eligible -- check inventory
        # ─────────────────────────────────────────────────────────────────
        inventory_info = last_result("check_inventory")
        if inventory_info is None:
            return {
                "type": "tool_call",
                "tool": "check_inventory",
                "args": {"item_id": order_info["item_id"]},
            }

        # ─────────────────────────────────────────────────────────────────
        # DECISION 5a: Stock available → Exchange
        # ─────────────────────────────────────────────────────────────────
        if inventory_info["available"]:
            notif = last_result("send_notification")
            if notif is None:
                return {
                    "type": "tool_call",
                    "tool": "send_notification",
                    "args": {
                        "email": order_info["email"],
                        "message": (
                            f"Dear {order_info['customer_name']},\n"
                            f"Great news! A replacement {order_info['item_name']} is in stock. "
                            f"Your exchange for order {order_info['order_id']} has been confirmed. "
                            f"Your new unit will be dispatched shortly. Thank you for your patience!"
                        ),
                    },
                }
            return {
                "type": "final_answer",
                "text": (
                    f"Hi {order_info['customer_name']}, good news! "
                    f"We have {inventory_info['stock']} unit(s) of {order_info['item_name']} in stock. "
                    f"Your exchange for order {order_info['order_id']} has been confirmed "
                    f"and your replacement will be dispatched shortly. "
                    f"A confirmation email has been sent to {order_info['email']}."
                ),
            }

        # ─────────────────────────────────────────────────────────────────
        # DECISION 5b: Stock = 0 → Refund
        # ─────────────────────────────────────────────────────────────────
        refund_info = last_result("process_refund")
        if refund_info is None:
            return {
                "type": "tool_call",
                "tool": "process_refund",
                "args": {
                    "order_id": order_info["order_id"],
                    "reason":   f"{order_info['item_name']} is out of stock -- exchange not possible.",
                },
            }

        notif = last_result("send_notification")
        if notif is None:
            return {
                "type": "tool_call",
                "tool": "send_notification",
                "args": {
                    "email": order_info["email"],
                    "message": (
                        f"Dear {order_info['customer_name']},\n"
                        f"We're sorry -- the {order_info['item_name']} is currently out of stock, "
                        f"so we're unable to process an exchange for order {order_info['order_id']}. "
                        f"Instead, a full refund of ${refund_info['refunded_amount']:.2f} has been issued. "
                        f"Transaction ID: {refund_info['transaction_id']}. "
                        f"We apologize for the inconvenience!"
                    ),
                },
            }

        return {
            "type": "final_answer",
            "text": (
                f"Hi {order_info['customer_name']}, unfortunately the "
                f"{order_info['item_name']} is out of stock so we could not process an exchange. "
                f"We've issued a full refund of ${refund_info['refunded_amount']:.2f} "
                f"(Ref: {refund_info['transaction_id']}). "
                f"A confirmation email has been sent to {order_info['email']}. "
                f"Sorry for the trouble!"
            ),
        }

    # ── Utility: extract order ID from user message ───────────────────────────
    @staticmethod
    def _extract_order_id(history: list[dict]) -> str | None:
        """Find an 'ORD-XXXX' pattern in the first user message."""
        import re
        for entry in history:
            if entry["role"] == "user":
                match = re.search(r"ORD-\d+", entry["content"], re.IGNORECASE)
                if match:
                    return match.group(0).upper()
        return None


# =============================================================================
# STEP 4 + 5 -- AGENTIC ReAct LOOP WITH GUARDRAILS
# =============================================================================

MAX_ITERATIONS = 10   # hard execution ceiling


def run_agent(user_request: str) -> str:
    """
    Main agentic loop -- Reason, Act, Observe, Repeat.

    history entries have the shape:
      {"role": "user"|"model"|"tool", "content": str|dict, "tool_name": str (tool only)}
    """
    model = MockModel()

    # Stateful conversation history
    history: list[dict] = [{"role": "user", "content": user_request}]

    print(f"\n{'='*60}")
    print(f"AGENT STARTED")
    print(f"{'='*60}")
    print(f"User: {user_request}\n")

    for iteration in range(1, MAX_ITERATIONS + 1):
        print(f"-- Iteration {iteration}/{MAX_ITERATIONS} -------------------------")

        # ── Model decision (replace this call with a real LLM API here) ──
        decision = model.decide(history)

        # ── FINAL ANSWER ──────────────────────────────────────────────────
        if decision["type"] == "final_answer":
            answer = decision["text"]
            print(f"\n[AGENT RESPONSE]\n{answer}")
            print(f"{'='*60}\n")
            return answer

        # ── TOOL CALL DETECTED ────────────────────────────────────────────
        tool_name = decision["tool"]
        args      = decision.get("args", {})

        print(f"  [TOOL CALL] {tool_name}({json.dumps(args)})")

        # Safe dispatch via registry
        result = dispatch_tool(tool_name, args)

        print(f"  [RESULT]    {json.dumps(result)}")

        # Append model thought and tool result into history
        history.append({
            "role":    "model",
            "content": f"Calling tool: {tool_name}",
        })
        history.append({
            "role":      "tool",
            "tool_name": tool_name,
            "content":   result,
        })

    # ── GUARDRAIL: max iterations exceeded ───────────────────────────────────
    msg = (
        "[WARNING] Agent could not resolve the request within the allowed steps. "
        "This session has been flagged for human escalation."
    )
    print(f"\n{msg}\n{'='*60}\n")
    return msg


# =============================================================================
# DEMO -- Three scenarios covering all acceptance criteria
# =============================================================================

if __name__ == "__main__":

    print("\n" + "#"*60)
    print("  SCENARIO 1: Stock = 0 --> should REFUND")
    print("#"*60)
    run_agent(
        "Hi, I received a damaged product. My order is ORD-1001. "
        "Can you please sort this out?"
    )

    print("\n" + "#"*60)
    print("  SCENARIO 2: Stock > 0 --> should EXCHANGE")
    print("#"*60)
    run_agent(
        "Hello! I got a faulty Bluetooth Speaker. Order number ORD-1002. "
        "Please help me resolve this."
    )

    print("\n" + "#"*60)
    print("  SCENARIO 3: Ineligible order --> REFUND (policy)")
    print("#"*60)
    run_agent(
        "My Smart Watch arrived broken. Order ORD-1003. "
        "Can I get an exchange?"
    )

    print("\n" + "#"*60)
    print("  SCENARIO 4: Invalid order ID --> graceful error")
    print("#"*60)
    run_agent(
        "My order ORD-9999 has a defective item. What can you do?"
    )
