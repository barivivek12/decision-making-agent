"""
Decision-Making Resolution Agent
=================================
Autonomous agent that reads order records, evaluates exchange eligibility,
and initiates a refund when an item cannot be exchanged.

Steps implemented:
  1. Functional Tools       – four isolated, deterministic functions
  2. Tool Schemas           – declarative JSON contracts for the LLM
  3. Tool Registry          – whitelist + safe dispatcher
  4. Agentic ReAct Loop     – stateful, multi-step reasoning cycle
  5. Guardrails             – max iterations, graceful errors, arg validation
"""

import json
import uuid
import datetime
import os
import sys

# --- Load .env file if present (simple key=value parser, no extra deps) ------
_env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ.setdefault(_k.strip(), _v.strip())

# --- Guard: require API key before importing the client ---------------------
if not os.environ.get("GEMINI_API_KEY"):
    print(
        "\n[ERROR] GEMINI_API_KEY is not set.\n"
        "  Option A: set it in your shell:\n"
        "            $env:GEMINI_API_KEY='your-key'   (PowerShell)\n"
        "  Option B: create a file named '.env' next to agent.py:\n"
        "            GEMINI_API_KEY=your-key\n"
        "  Get a free key at https://aistudio.google.com/apikey\n"
    )
    sys.exit(1)

from google import genai
from google.genai import types

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — FUNCTIONAL TOOLS
# Isolated, deterministic functions that return structured payloads.
# ─────────────────────────────────────────────────────────────────────────────

# Fake in-memory database of orders
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
        "eligible_for_exchange": False,   # ineligible order
        "amount_paid": 199.99,
    },
}

# Fake warehouse inventory
INVENTORY_DB = {
    "ITEM-A": {"item_name": "Wireless Headphones", "stock": 0},   # out of stock
    "ITEM-B": {"item_name": "Bluetooth Speaker",   "stock": 5},   # in stock
    "ITEM-C": {"item_name": "Smart Watch",         "stock": 3},   # in stock (but order ineligible)
}

# Simple notification log (in-memory)
NOTIFICATIONS_SENT = []


def lookup_order(order_id: str) -> dict:
    """
    Step 1 – Tool 1: Order Lookup
    Retrieves customer name, item details, status, and eligibility from DB.
    """
    order = ORDER_DB.get(order_id)
    if not order:
        return {
            "success": False,
            "error": f"Order '{order_id}' not found in the system. Please verify the order ID.",
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
    """
    Step 1 – Tool 2: Inventory Inspection
    Returns real-time warehouse stock count and availability flag.
    """
    item = INVENTORY_DB.get(item_id)
    if not item:
        return {
            "success": False,
            "error": f"Item '{item_id}' not found in inventory system.",
        }
    return {
        "success": True,
        "item_id": item_id,
        "item_name": item["item_name"],
        "stock": item["stock"],
        "available": item["stock"] > 0,
    }


def process_refund(order_id: str, reason: str) -> dict:
    """
    Step 1 – Tool 3: Refund Processing
    Issues a refund transaction and returns the transaction reference.
    """
    order = ORDER_DB.get(order_id)
    if not order:
        return {
            "success": False,
            "error": f"Cannot refund: Order '{order_id}' not found.",
        }
    transaction_id = f"TXN-{uuid.uuid4().hex[:8].upper()}"
    return {
        "success": True,
        "order_id": order_id,
        "transaction_id": transaction_id,
        "refunded_amount": order["amount_paid"],
        "reason": reason,
        "timestamp": datetime.datetime.now().isoformat(),
        "message": (
            f"Refund of ${order['amount_paid']:.2f} successfully processed. "
            f"Reference: {transaction_id}"
        ),
    }


def send_notification(email: str, message: str) -> dict:
    """
    Step 1 – Tool 4: Customer Notification
    Dispatches a confirmation email and logs it.
    """
    if "@" not in email:
        return {"success": False, "error": f"Invalid email address: '{email}'."}

    record = {
        "to": email,
        "message": message,
        "sent_at": datetime.datetime.now().isoformat(),
    }
    NOTIFICATIONS_SENT.append(record)
    print(f"\n[EMAIL SENT -> {email}]\n{message}\n{'─'*50}")
    return {
        "success": True,
        "email": email,
        "message": "Notification dispatched successfully.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — TOOL SCHEMAS (Declarative JSON contracts for the model)
# ─────────────────────────────────────────────────────────────────────────────

TOOL_SCHEMAS = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="lookup_order",
                description=(
                    "Look up a customer order from the database using an order ID. "
                    "Returns the customer's name, email, purchased item, payment amount, "
                    "order status, and whether the order is eligible for an exchange."
                ),
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "order_id": types.Schema(
                            type=types.Type.STRING,
                            description="The unique order identifier (e.g., 'ORD-1001').",
                        )
                    },
                    required=["order_id"],
                ),
            ),
            types.FunctionDeclaration(
                name="check_inventory",
                description=(
                    "Check the real-time warehouse inventory for a specific item. "
                    "Returns the current stock count and an availability flag. "
                    "Use this after looking up an order to determine whether a "
                    "replacement unit is available for exchange."
                ),
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "item_id": types.Schema(
                            type=types.Type.STRING,
                            description="The item identifier to check in the warehouse (e.g., 'ITEM-A').",
                        )
                    },
                    required=["item_id"],
                ),
            ),
            types.FunctionDeclaration(
                name="process_refund",
                description=(
                    "Issue a financial refund to the customer's original payment method. "
                    "Use this ONLY when the item cannot be exchanged — either because "
                    "the replacement is out of stock or the order is not eligible for exchange. "
                    "Returns a transaction reference ID and the refunded amount."
                ),
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "order_id": types.Schema(
                            type=types.Type.STRING,
                            description="The order ID for which the refund is being issued.",
                        ),
                        "reason": types.Schema(
                            type=types.Type.STRING,
                            description="A brief reason for the refund (e.g., 'Replacement out of stock').",
                        ),
                    },
                    required=["order_id", "reason"],
                ),
            ),
            types.FunctionDeclaration(
                name="send_notification",
                description=(
                    "Send an email notification to the customer confirming the resolution. "
                    "Always call this as the final step after a resolution (exchange or refund) "
                    "has been decided, to inform the customer of the outcome."
                ),
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "email": types.Schema(
                            type=types.Type.STRING,
                            description="The customer's email address.",
                        ),
                        "message": types.Schema(
                            type=types.Type.STRING,
                            description="The full notification message body to send to the customer.",
                        ),
                    },
                    required=["email", "message"],
                ),
            ),
        ]
    )
]


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — TOOL REGISTRY + SAFE DISPATCHER
# ─────────────────────────────────────────────────────────────────────────────

# Whitelist registry: only these tool names may be called
TOOL_REGISTRY = {
    "lookup_order": lookup_order,
    "check_inventory": check_inventory,
    "process_refund": process_refund,
    "send_notification": send_notification,
}


def dispatch_tool(tool_name: str, raw_args: dict) -> str:
    """
    Safe dispatcher.
    - Rejects any tool not in the whitelist registry.
    - Catches argument/runtime errors and returns them as JSON error payloads.
    """
    # Authorization check
    if tool_name not in TOOL_REGISTRY:
        return json.dumps({
            "success": False,
            "error": f"Unauthorized tool call: '{tool_name}' is not registered.",
        })

    # Argument validation + execution
    try:
        args = {k: v for k, v in raw_args.items()}  # copy / light validation
        result = TOOL_REGISTRY[tool_name](**args)
        return json.dumps(result)
    except TypeError as e:
        return json.dumps({
            "success": False,
            "error": f"Argument error calling '{tool_name}': {str(e)}",
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Unexpected error in '{tool_name}': {str(e)}",
        })


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 + 5 — AGENTIC ReAct LOOP WITH GUARDRAILS
# ─────────────────────────────────────────────────────────────────────────────

MAX_ITERATIONS = 10   # execution ceiling (guardrail)


def run_agent(user_request: str) -> str:
    """
    Main agentic loop (ReAct: Reason → Act → Observe → Repeat).

    Maintains an ordered conversation history.
    Calls the model, detects tool requests, dispatches them safely,
    feeds results back into state, and repeats until a final answer
    is produced or the iteration ceiling is hit.
    """
    # Initialize Gemini client (reads GEMINI_API_KEY from environment)
    client = genai.Client()

    system_instruction = (
        "You are an autonomous customer resolution agent. "
        "Your job is to resolve order issues by: "
        "(1) looking up the order, "
        "(2) checking inventory for a replacement, "
        "(3) if stock > 0 AND the order is eligible, confirm the exchange; "
        "    otherwise initiate a refund, "
        "(4) always notify the customer by email, "
        "(5) provide a clear, polite summary to the customer. "
        "Use the provided tools — do not guess or fabricate data."
    )

    # Conversation history (stateful)
    history: list[types.Content] = []

    # Seed with the user request
    history.append(types.Content(
        role="user",
        parts=[types.Part(text=user_request)],
    ))

    print(f"\n{'='*60}")
    print(f"[AGENT STARTED]")
    print(f"{'='*60}")
    print(f"User: {user_request}\n")

    for iteration in range(1, MAX_ITERATIONS + 1):
        print(f"-- Iteration {iteration}/{MAX_ITERATIONS} -------------------------")

        # Model invocation with tools and full history
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=history,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=TOOL_SCHEMAS,
            ),
        )

        candidate = response.candidates[0]
        content = candidate.content          # types.Content (role=model)
        history.append(content)              # append model turn to history

        # Inspect parts for tool calls vs. final text answer
        tool_calls_found = []
        text_parts = []

        for part in content.parts:
            if part.function_call:
                tool_calls_found.append(part.function_call)
            elif part.text:
                text_parts.append(part.text)

        # ── FINAL ANSWER ──────────────────────────────────────────────────
        if not tool_calls_found:
            final_answer = "\n".join(text_parts).strip()
            print(f"\n[AGENT FINAL RESPONSE]\n{final_answer}")
            print(f"{'='*60}\n")
            return final_answer

        # ── TOOL CALLS DETECTED ───────────────────────────────────────────
        tool_response_parts = []

        for fc in tool_calls_found:
            tool_name = fc.name
            raw_args  = dict(fc.args) if fc.args else {}

            print(f"[TOOL CALL] {tool_name}({json.dumps(raw_args)})")

            # Safe dispatch
            result_json = dispatch_tool(tool_name, raw_args)
            result_data = json.loads(result_json)

            print(f"[RESULT]    {result_json}")

            # Build a function response part
            tool_response_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=tool_name,
                        response=result_data,
                    )
                )
            )

        # Append tool results to history as a "tool" role turn
        history.append(types.Content(
            role="tool",
            parts=tool_response_parts,
        ))

    # ── GUARDRAIL: max iterations exceeded ───────────────────────────────────
    escalation_msg = (
        "[WARNING] Agent could not resolve the request within the allowed steps. "
        "This session has been flagged for human escalation."
    )
    print(f"\n{escalation_msg}\n{'='*60}\n")
    return escalation_msg


# ─────────────────────────────────────────────────────────────────────────────
# DEMO — Run three scenarios to satisfy all acceptance criteria
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "#"*60)
    print("  SCENARIO 1: Item out of stock -> should REFUND")
    print("#"*60)
    run_agent(
        "Hi, I received a damaged product. My order ID is ORD-1001. "
        "Can you please sort this out for me?"
    )

    print("\n" + "#"*60)
    print("  SCENARIO 2: Replacement in stock -> should EXCHANGE")
    print("#"*60)
    run_agent(
        "Hello! I got a faulty Bluetooth Speaker. Order number ORD-1002. "
        "Please help me resolve this."
    )

    print("\n" + "#"*60)
    print("  SCENARIO 3: Invalid order ID -> should REPORT gracefully")
    print("#"*60)
    run_agent(
        "My order ORD-9999 has a defective item. What can you do for me?"
    )
