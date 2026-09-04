"""
Decline Detector — Deep build.
Maps bank decline codes to the 5-bucket cause taxonomy and emits RiskObjects.
30+ real-world decline codes mapped.
"""

from __future__ import annotations

from typing import Any

from models import DeclineCause, RiskObject, RiskType, Urgency
from data_generator import DECLINE_CODE_MAP


def detect_decline_risks(raw_events: list[dict[str, Any]]) -> list[RiskObject]:
    """
    Process raw payment decline events and emit standardized RiskObjects.
    Filters out mandate-type instruments (handled by mandate_detector).
    """
    risks = []
    for event in raw_events:
        # Skip mandate instruments — those are handled by mandate_detector
        if event.get("instrument_type") == "upi_autopay_mandate":
            continue

        decline_code = event["decline_code"]
        cause = DECLINE_CODE_MAP.get(decline_code, DeclineCause.NETWORK_DROP)

        amount = event["amount"]
        retry_count = event.get("retry_count", 0)

        # Amount-weighted urgency calculation
        if cause == DeclineCause.RISK_BLOCK:
            urgency = Urgency.HIGH  # always high for risk blocks
        elif amount > 20000 or retry_count >= 2:
            urgency = Urgency.HIGH
        elif amount > 5000:
            urgency = Urgency.MEDIUM
        else:
            urgency = Urgency.LOW

        risk = RiskObject(
            risk_id=event["event_id"],
            customer_id=event["customer_id"],
            risk_type=RiskType.PAYMENT_DECLINE,
            cause=cause.value,
            amount_at_stake=amount,
            urgency=urgency,
            detected_at=event["timestamp"],
            context={
                "decline_code": decline_code,
                "instrument_type": event.get("instrument_type", "card"),
                "card_last4": event.get("card_last4", ""),
                "retry_count": retry_count,
                "merchant_id": event.get("merchant_id", ""),
                "is_mandate": False,
            },
        )
        risks.append(risk)

    return risks
