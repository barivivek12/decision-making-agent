"""
schemas.py — Step 2: Declarative Tool Contracts (Schemas)
These JSON-schema-style dicts are the only view the LLM has of each tool.
Descriptions must be unambiguous so the model knows exactly when and how
to invoke each tool.
"""

TOOL_SCHEMAS: list[dict] = [
    # ------------------------------------------------------------------
    # Schema 1 — Order Lookup
    # ------------------------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "lookup_order",
            "description": (
                "Retrieve complete order details from the customer database using "
                "an order ID. Use this tool first whenever a customer reports an "
                "issue with an order. Returns the customer name, email, purchased "
                "item ID, item name, order status, whether the order is eligible "
                "for an exchange, the amount paid, currency, and original payment "
                "method. If the order ID is not found, returns an error payload."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": (
                            "The unique order identifier to look up "
                            "(e.g. 'ORD-1001'). Case-insensitive."
                        ),
                    }
                },
                "required": ["order_id"],
            },
        },
    },

    # ------------------------------------------------------------------
    # Schema 2 — Inventory Inspection
    # ------------------------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "check_inventory",
            "description": (
                "Query the warehouse management system for real-time stock levels "
                "of a specific item SKU. Use this tool after retrieving order "
                "details to determine whether a replacement unit is available. "
                "Returns the stock count and an 'available' boolean. "
                "If stock_count is 0 or available is false, a replacement cannot "
                "be shipped and a refund must be initiated instead."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "string",
                        "description": (
                            "The unique warehouse item / SKU identifier to check "
                            "(e.g. 'ITEM-PRO-X'). Obtained from the lookup_order result."
                        ),
                    }
                },
                "required": ["item_id"],
            },
        },
    },

    # ------------------------------------------------------------------
    # Schema 3 — Refund Processing
    # ------------------------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "process_refund",
            "description": (
                "Issue a financial refund to the customer's original payment method "
                "for a given order. Use this tool ONLY when: (a) the item is out of "
                "stock and cannot be exchanged, OR (b) the order is not eligible for "
                "an exchange. Do NOT use this tool if a replacement unit is available "
                "and the order is exchange-eligible. Returns a transaction reference "
                "number, the refunded amount, and a confirmation timestamp."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The order ID for which the refund is being issued.",
                    },
                    "reason": {
                        "type": "string",
                        "description": (
                            "A brief, human-readable explanation for why the refund "
                            "is being issued (e.g. 'Item out of stock — exchange not possible')."
                        ),
                    },
                },
                "required": ["order_id", "reason"],
            },
        },
    },

    # ------------------------------------------------------------------
    # Schema 4 — Customer Notification
    # ------------------------------------------------------------------
    {
        "type": "function",
        "function": {
            "name": "send_notification",
            "description": (
                "Dispatch an official email confirmation to the customer summarising "
                "the resolution taken (exchange or refund). Always call this tool as "
                "the final action before delivering the summary response. The message "
                "should be polite, clearly state what action was taken, include any "
                "relevant reference numbers, and advise on next steps."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_email": {
                        "type": "string",
                        "description": (
                            "The recipient's email address. Obtained from the "
                            "lookup_order result."
                        ),
                    },
                    "message": {
                        "type": "string",
                        "description": (
                            "The full body of the notification email. Should be "
                            "professional, empathetic, and include all relevant "
                            "details such as order ID, resolution type, transaction "
                            "references, and expected timelines."
                        ),
                    },
                },
                "required": ["customer_email", "message"],
            },
        },
    },
]
