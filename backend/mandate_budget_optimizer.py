"""
Mandate Budget Optimizer — UPI Autopay.
Treats NPCI mandate retries as a depletable budget.
Decides *when* to spend each retry instead of firing blindly.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Optional

from models import ActionType, DeclineCause


def predict_optimal_retry_date(debit_history: list[str]) -> Optional[str]:
    """
    Predict the optimal retry date from a customer's past successful debit dates.
    Finds the most common day-of-month (mode) across history, returns the next
    occurrence of that day as the predicted best retry window.

    This is a proxy for "salary credit date" without ever storing salary data —
    it's just a pattern in past successful debit timestamps.
    """
    if not debit_history:
        return None

    # Extract day-of-month from each historical debit date
    days = []
    for date_str in debit_history:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            days.append(dt.day)
        except (ValueError, TypeError):
            continue

    if not days:
        return None

    # Find the mode (most common day)
    counter = Counter(days)
    typical_day = counter.most_common(1)[0][0]

    # Find next occurrence of that day
    today = datetime.utcnow()
    try:
        next_date = today.replace(day=typical_day)
        if next_date <= today:
            # Move to next month
            if today.month == 12:
                next_date = today.replace(year=today.year + 1, month=1, day=typical_day)
            else:
                next_date = today.replace(month=today.month + 1, day=min(typical_day, 28))
    except ValueError:
        # Day doesn't exist in current month (e.g., 31st)
        next_date = today.replace(day=min(typical_day, 28))
        if next_date <= today:
            if today.month == 12:
                next_date = today.replace(year=today.year + 1, month=1, day=min(typical_day, 28))
            else:
                next_date = today.replace(month=today.month + 1, day=min(typical_day, 28))

    return next_date.strftime("%Y-%m-%d")


def pick_mandate_action(risk) -> tuple[str, str]:
    """
    Mandate-specific decision logic.
    Checked BEFORE falling through to the normal decision table for mandate-flagged risks.

    Decision table:
    | Condition                                           | Action                          |
    |-----------------------------------------------------|---------------------------------|
    | retries_remaining == 0                               | escalate_to_human_review        |
    | retries >= 2 and cause is transient                  | retry_immediate                 |
    | retries <= 1 and insufficient_funds                  | schedule_retry_optimal_window   |
    | predicted_date > cycle_end                           | escalate_to_human_review        |
    """
    mandate = risk.context.get("mandate", {})
    retries_remaining = mandate.get("retries_remaining", 0)
    max_retries = mandate.get("max_retries_allowed", 3)
    predicted_date = mandate.get("predicted_optimal_retry_date")
    cycle_end = mandate.get("mandate_cycle_end_date")
    cause = risk.cause

    # Rule 1: Budget exhausted
    if retries_remaining == 0:
        return (
            ActionType.ESCALATE_TO_HUMAN_REVIEW.value,
            f"mandate_budget_exhausted_no_further_retry — "
            f"used {max_retries}/{max_retries} retries, re-authorization required"
        )

    # Rule 2: Transient failures with budget to spare
    transient_causes = {DeclineCause.BANK_TIMEOUT.value, DeclineCause.NETWORK_DROP.value}
    if retries_remaining >= 2 and cause in transient_causes:
        return (
            ActionType.RETRY_IMMEDIATE.value,
            f"transient failure ({cause}) with budget to spare "
            f"({retries_remaining}/{max_retries} retries left)"
        )

    # Rule 3 & 4: Last retry(s) with insufficient_funds — hold for optimal window
    if retries_remaining <= 1 and cause == DeclineCause.INSUFFICIENT_FUNDS.value:
        # Check if cycle ends before predicted optimal window
        if predicted_date and cycle_end:
            try:
                pred_dt = datetime.strptime(predicted_date, "%Y-%m-%d")
                cycle_dt = datetime.strptime(cycle_end, "%Y-%m-%d")
                if pred_dt > cycle_dt:
                    return (
                        ActionType.ESCALATE_TO_HUMAN_REVIEW.value,
                        f"cycle ends ({cycle_end}) before predicted optimal window ({predicted_date}) "
                        f"— escalating rather than risking the last retry"
                    )
            except (ValueError, TypeError):
                pass

        return (
            ActionType.SCHEDULE_RETRY_OPTIMAL_WINDOW.value,
            f"held final retry ({retries_remaining} of {max_retries}) "
            f"for predicted optimal window on {predicted_date or 'unknown'} "
            f"instead of firing immediately"
        )

    # Fallback for mandate risks: use the budget wisely
    if retries_remaining >= 2:
        return (
            ActionType.SCHEDULE_RETRY.value,
            f"mandate retry scheduled with {retries_remaining}/{max_retries} retries remaining"
        )

    # Last resort: hold and optimize
    return (
        ActionType.SCHEDULE_RETRY_OPTIMAL_WINDOW.value,
        f"held retry ({retries_remaining} of {max_retries}) "
        f"for optimal window on {predicted_date or 'next best day'}"
    )
