"""
Checkout Detector — Deep build.
Reconstructs checkout event streams and classifies abandonment cause via
rule-based analysis of event sequence features.
"""

from __future__ import annotations

from typing import Any

from models import AbandonCause, RiskObject, RiskType, Urgency


def _classify_abandonment_cause(event: dict[str, Any]) -> str:
    """
    Classify checkout abandonment cause from event stream features.
    Priority order:
      1. OTP failure — any OTP attempt without success
      2. Network drop — network error events in stream
      3. Late price reveal — price shown <3s before drop
      4. Indecision — no distinguishing signal (stopping rule: don't spam)
    """
    otp_attempts = event.get("otp_attempts", 0)
    network_errors = event.get("network_errors", 0)
    price_gap = event.get("price_reveal_gap_seconds")

    # Check OTP failures
    if otp_attempts > 0:
        # Verify no successful OTP in the stream
        stream = event.get("event_stream", [])
        otp_success = any(
            e.get("type") == "otp_attempt" and e.get("success") is True
            for e in stream
        )
        if not otp_success:
            return AbandonCause.OTP_FAILURE.value

    # Check network errors
    if network_errors > 0:
        return AbandonCause.NETWORK_DROP.value

    # Check late price reveal (price shown <3s before session drop)
    if price_gap is not None and price_gap < 3.0:
        return AbandonCause.LATE_PRICE_REVEAL.value

    # No distinguishing signal — indecision
    return AbandonCause.INDECISION_NO_SIGNAL.value


def detect_checkout_risks(raw_events: list[dict[str, Any]]) -> list[RiskObject]:
    """
    Process raw checkout abandonment events and emit standardized RiskObjects.
    Re-classifies cause from event stream features for robustness.
    """
    risks = []
    for event in raw_events:
        # Re-classify cause from event stream (don't just trust the pre-assigned cause)
        classified_cause = _classify_abandonment_cause(event)
        cart_value = event.get("cart_value", 0)

        if cart_value > 30000:
            urgency = Urgency.HIGH
        elif cart_value > 5000:
            urgency = Urgency.MEDIUM
        else:
            urgency = Urgency.LOW

        risk = RiskObject(
            risk_id=event["event_id"],
            customer_id=event["customer_id"],
            risk_type=RiskType.CHECKOUT_ABANDON,
            cause=classified_cause,
            amount_at_stake=cart_value,
            urgency=urgency,
            detected_at=event["timestamp"],
            context={
                "session_id": event.get("session_id", ""),
                "otp_attempts": event.get("otp_attempts", 0),
                "network_errors": event.get("network_errors", 0),
                "price_reveal_gap_seconds": event.get("price_reveal_gap_seconds"),
                "event_stream_length": len(event.get("event_stream", [])),
                "is_mandate": False,
            },
        )
        risks.append(risk)

    return risks
