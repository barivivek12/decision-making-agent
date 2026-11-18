"""
dispatcher.py — Step 3: Tool Registration & Safe Dispatch
Implements a whitelist registry and an execution gatekeeper that rejects
any tool call not explicitly registered.
"""

import json
from typing import Any, Callable

from tools import lookup_order, check_inventory, process_refund, send_notification

# ---------------------------------------------------------------------------
# Step 3a — Registry Whitelist
# Maps canonical tool names → their callable implementations.
# Only functions listed here can ever be executed.
# ---------------------------------------------------------------------------

TOOL_REGISTRY: dict[str, Callable] = {
    "lookup_order":     lookup_order,
    "check_inventory":  check_inventory,
    "process_refund":   process_refund,
    "send_notification": send_notification,
}


# ---------------------------------------------------------------------------
# Step 3b — Execution Gatekeeper
# ---------------------------------------------------------------------------

def dispatch_tool(tool_name: str, raw_arguments: str | dict) -> dict[str, Any]:
    """
    Authorised entry-point for all tool executions.

    1. Verifies the tool name is whitelisted.
    2. Safely parses the argument payload.
    3. Calls the registered function and returns its structured result.

    Args:
        tool_name:     The name of the tool the model wants to call.
        raw_arguments: JSON string or dict of arguments from the model.

    Returns:
        The tool's result dict, or a controlled error payload.
    """
    # --- Authorization Check -------------------------------------------
    if tool_name not in TOOL_REGISTRY:
        return {
            "success": False,
            "error": (
                f"[DISPATCHER] Tool '{tool_name}' is not registered in the "
                "whitelist and cannot be executed. "
                f"Permitted tools: {list(TOOL_REGISTRY.keys())}."
            ),
        }

    # --- Argument Validation / Safe Parsing ----------------------------
    try:
        if isinstance(raw_arguments, str):
            arguments: dict = json.loads(raw_arguments)
        elif isinstance(raw_arguments, dict):
            arguments = raw_arguments
        else:
            raise TypeError(f"Unexpected arguments type: {type(raw_arguments)}")
    except (json.JSONDecodeError, TypeError) as exc:
        return {
            "success": False,
            "error": (
                f"[DISPATCHER] Failed to parse arguments for tool '{tool_name}': "
                f"{exc}. Please supply valid JSON arguments."
            ),
        }

    # --- Safe Execution ------------------------------------------------
    try:
        fn = TOOL_REGISTRY[tool_name]
        result = fn(**arguments)
        return result
    except TypeError as exc:
        # Catches missing/unexpected keyword arguments
        return {
            "success": False,
            "error": (
                f"[DISPATCHER] Argument mismatch when calling '{tool_name}': "
                f"{exc}. Check that all required parameters are provided."
            ),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "success": False,
            "error": f"[DISPATCHER] Unexpected error in '{tool_name}': {exc}.",
        }
