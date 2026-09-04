"""
Mandate Detector — Light-medium build.
Specialization of payment_decline for UPI Autopay mandates.
Filters decline events to mandate instruments and attaches MandateContext.
"""

from __future__ import annotations

from typing import Any

from models import DeclineCause, RiskObject, RiskType, Urgency
from mandate_budget_optimizer import predict_optimal_retry_date


def detect_mandate_risks(raw_events: list[dict[str, Any]]) -> list[RiskObject]:
    """
    Process raw mandate failure events and emit RiskObjects with MandateContext.
    Only processes events where instrument_type == 'upi_autopay_mandate'.
    """
    risks = []
    for event in raw_events:
        if event.get("instrument_type") != "upi_autopay_mandate":
            continue

        amount = event["amount"]
        retries_remaining = event.get("retries_remaining", 0)
        debit_history = event.get("debit_history", [])

        # Predict optimal retry date from customer's debit history
        predicted_date = predict_optimal_retry_date(debit_history)

        # Override urgency: retries_remaining <= 1 → HIGH (last chance)
        if retries_remaining <= 1:
            urgency = Urgency.HIGH
        elif amount > 15000:
            urgency = Urgency.MEDIUM
        else:
            urgency = Urgency.LOW

        mandate_context = {
            "mandate_id": event.get("mandate_id", ""),
            "retries_used": event.get("retries_used", 0),
            "max_retries_allowed": event.get("max_retries_allowed", 3),
            "retries_remaining": retries_remaining,
            "predicted_optimal_retry_date": predicted_date,
            "mandate_cycle_end_date": event.get("mandate_cycle_end_date", ""),
        }

        risk = RiskObject(
            risk_id=event["event_id"],
            customer_id=event["customer_id"],
            risk_type=RiskType.PAYMENT_DECLINE,
            cause=event.get("cause", DeclineCause.INSUFFICIENT_FUNDS.value),
            amount_at_stake=amount,
            urgency=urgency,
            detected_at=event["timestamp"],
            context={
                "decline_code": event.get("decline_code", "UPI_MANDATE_DEBIT_FAILED"),
                "instrument_type": "upi_autopay_mandate",
                "retry_count": event.get("retry_count", 0),
                "merchant_id": event.get("merchant_id", ""),
                "is_mandate": True,
                "mandate": mandate_context,
                "debit_history": debit_history,
                "typical_debit_day": event.get("typical_debit_day"),
            },
        )
        risks.append(risk)

    return risks
