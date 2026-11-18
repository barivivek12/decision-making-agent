"""
main.py — Entry Point & Acceptance-Criteria Demonstration
Runs four test scenarios that satisfy every acceptance criterion:
  1. Out-of-stock → auto-refund path       (ORD-1001, stock=0)
  2. In-stock → exchange path              (ORD-1002, stock=7)
  3. Invalid order ID → resilience test    (non-existent ID)
  4. Ineligible order → refund path        (ORD-1003, eligible=False)
"""

import os
import sys
from agent import run_agent

DIVIDER = "\n" + "█" * 70 + "\n"


def run_scenario(title: str, request: str) -> None:
    print(DIVIDER)
    print(f"SCENARIO: {title}")
    print(DIVIDER)
    run_agent(request, verbose=True)


def main() -> None:
    # ------------------------------------------------------------------ #
    # Scenario 1: Out-of-stock replacement → automatic refund
    # ------------------------------------------------------------------ #
    run_scenario(
        title="Out-of-Stock Item → Automatic Refund",
        request=(
            "Hi, I received order ORD-1001 but the headphones arrived damaged. "
            "I'd like to get a replacement please."
        ),
    )

    # ------------------------------------------------------------------ #
    # Scenario 2: In-stock replacement → exchange confirmed
    # ------------------------------------------------------------------ #
    run_scenario(
        title="In-Stock Item → Exchange Confirmed",
        request=(
            "My smart watch from order ORD-1002 stopped working after two days. "
            "Can I get it exchanged?"
        ),
    )

    # ------------------------------------------------------------------ #
    # Scenario 3: Invalid order ID → graceful error (resilience)
    # ------------------------------------------------------------------ #
    run_scenario(
        title="Invalid Order ID → Graceful Error",
        request=(
            "I have a problem with order ORD-9999. The item is broken."
        ),
    )

    # ------------------------------------------------------------------ #
    # Scenario 4: Ineligible order → automatic refund
    # ------------------------------------------------------------------ #
    run_scenario(
        title="Exchange-Ineligible Order → Automatic Refund",
        request=(
            "My order ORD-1003 Bluetooth speaker is defective. Can I exchange it?"
        ),
    )


if __name__ == "__main__":
    main()
