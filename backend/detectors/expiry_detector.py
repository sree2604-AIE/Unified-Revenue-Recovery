"""
Expiry Detector — Light build.
Pure date arithmetic: flags instruments expiring before the next expected charge.
"""

from __future__ import annotations

from typing import Any

from models import ExpiryCause, RiskObject, RiskType, Urgency


def detect_expiry_risks(raw_events: list[dict[str, Any]]) -> list[RiskObject]:
    """
    Process raw expiring instrument records and emit standardized RiskObjects.
    Urgency based on days remaining to expiry.
    """
    risks = []
    for event in raw_events:
        days_to_expiry = event.get("days_to_expiry", 30)
        amount = event.get("expected_amount", 0)

        if days_to_expiry < 7:
            urgency = Urgency.HIGH
        elif days_to_expiry < 30:
            urgency = Urgency.MEDIUM
        else:
            urgency = Urgency.LOW

        risk = RiskObject(
            risk_id=event["event_id"],
            customer_id=event["customer_id"],
            risk_type=RiskType.INSTRUMENT_EXPIRING,
            cause=ExpiryCause.EXPIRY_WITHIN_WINDOW.value,
            amount_at_stake=amount,
            urgency=urgency,
            detected_at=event["timestamp"],
            context={
                "card_last4": event.get("card_last4", ""),
                "instrument_type": event.get("instrument_type", ""),
                "expiry_date": event.get("expiry_date", ""),
                "next_charge_date": event.get("next_charge_date", ""),
                "days_to_expiry": days_to_expiry,
                "is_mandate": False,
            },
        )
        risks.append(risk)

    return risks
