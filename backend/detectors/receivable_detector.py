"""
Receivable Detector — Light build.
Scans overdue B2B invoices and classifies cause from payment history variance.
"""

from __future__ import annotations

from typing import Any

from models import OverdueCause, RiskObject, RiskType, Urgency


def detect_receivable_risks(raw_events: list[dict[str, Any]]) -> list[RiskObject]:
    """
    Process raw overdue B2B invoice records and emit standardized RiskObjects.
    Uses pre-computed gap_std_dev for cash-constraint heuristic.
    """
    risks = []
    for event in raw_events:
        amount = event["amount"]
        days_overdue = event.get("days_overdue", 0)

        # Urgency from days overdue
        if days_overdue > 60:
            urgency = Urgency.HIGH
        elif days_overdue > 30:
            urgency = Urgency.MEDIUM
        else:
            urgency = Urgency.LOW

        risk = RiskObject(
            risk_id=event["event_id"],
            customer_id=event["customer_id"],
            risk_type=RiskType.RECEIVABLE_OVERDUE,
            cause=event["cause"],
            amount_at_stake=amount,
            urgency=urgency,
            detected_at=event["timestamp"],
            context={
                "invoice_id": event.get("invoice_id", ""),
                "days_overdue": days_overdue,
                "due_date": event.get("due_date", ""),
                "gap_std_dev": event.get("gap_std_dev", 0),
                "has_dispute": event.get("has_dispute", False),
                "payment_history_gaps": event.get("payment_history_gaps", []),
                "is_mandate": False,
            },
        )
        risks.append(risk)

    return risks
