"""
Synthetic data generator for the Unified Revenue Recovery Orchestrator.
Generates realistic Indian payment ecosystem data across all 5 risk types.
Deterministic seed for reproducibility.
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta
from typing import Any

from models import (
    AbandonCause,
    ChannelType,
    Customer,
    CustomerSegment,
    DeclineCause,
    ExpiryCause,
    OverdueCause,
    RiskType,
    Urgency,
)

SEED = 42
_rng = random.Random(SEED)


def _uid() -> str:
    return uuid.UUID(int=_rng.getrandbits(128), version=4).hex[:12]


def _iso_now(offset_hours: float = 0) -> str:
    return (datetime.utcnow() + timedelta(hours=offset_hours)).isoformat() + "Z"


def _iso_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------

_FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh",
    "Ayaan", "Krishna", "Ishaan", "Ananya", "Diya", "Priya", "Meera",
    "Riya", "Kavya", "Saanvi", "Isha", "Neha", "Pooja", "Rahul", "Amit",
    "Deepak", "Suresh", "Vikram", "Rohan", "Karan", "Nikhil", "Sneha", "Divya",
]
_LAST_NAMES = [
    "Sharma", "Patel", "Singh", "Kumar", "Gupta", "Reddy", "Nair",
    "Joshi", "Verma", "Mehta", "Iyer", "Rao", "Das", "Chatterjee", "Banerjee",
]


def generate_customers(n: int = 100) -> list[Customer]:
    """Generate n synthetic customer profiles with segments, channels, opt-out flags."""
    customers = []
    for i in range(n):
        cid = f"CUST_{_uid()}"
        seg = _rng.choice(list(CustomerSegment))
        # ~5% opted out
        opted_out = _rng.random() < 0.05
        customers.append(
            Customer(
                customer_id=cid,
                name=f"{_rng.choice(_FIRST_NAMES)} {_rng.choice(_LAST_NAMES)}",
                segment=seg,
                preferred_channel=_rng.choice(list(ChannelType)),
                opted_out=opted_out,
                phone=f"+91{_rng.randint(7000000000, 9999999999)}",
                email=f"user{i}@example.com",
            )
        )
    return customers


# ---------------------------------------------------------------------------
# Decline code → cause mapping (30+ real-world codes)
# ---------------------------------------------------------------------------

DECLINE_CODE_MAP: dict[str, DeclineCause] = {
    # Insufficient funds
    "DO_NOT_HONOR": DeclineCause.INSUFFICIENT_FUNDS,
    "INSUFFICIENT_FUNDS": DeclineCause.INSUFFICIENT_FUNDS,
    "EXCEEDS_WITHDRAWAL_LIMIT": DeclineCause.INSUFFICIENT_FUNDS,
    "CARD_NOT_ACTIVATED": DeclineCause.INSUFFICIENT_FUNDS,
    "ALLOWABLE_PIN_TRIES_EXCEEDED": DeclineCause.INSUFFICIENT_FUNDS,
    "ACTIVITY_LIMIT_EXCEEDED": DeclineCause.INSUFFICIENT_FUNDS,
    "WITHDRAWAL_LIMIT": DeclineCause.INSUFFICIENT_FUNDS,
    # Expired instrument
    "EXPIRED_CARD": DeclineCause.EXPIRED_INSTRUMENT,
    "EXPIRED_ACCOUNT": DeclineCause.EXPIRED_INSTRUMENT,
    "INVALID_CARD_NUMBER": DeclineCause.EXPIRED_INSTRUMENT,
    "CLOSED_ACCOUNT": DeclineCause.EXPIRED_INSTRUMENT,
    "CARD_EXPIRED": DeclineCause.EXPIRED_INSTRUMENT,
    "INVALID_EXPIRY": DeclineCause.EXPIRED_INSTRUMENT,
    # Risk block
    "SUSPECTED_FRAUD": DeclineCause.RISK_BLOCK,
    "STOLEN_CARD": DeclineCause.RISK_BLOCK,
    "LOST_CARD": DeclineCause.RISK_BLOCK,
    "RESTRICTED_CARD": DeclineCause.RISK_BLOCK,
    "SECURITY_VIOLATION": DeclineCause.RISK_BLOCK,
    "PICKUP_CARD": DeclineCause.RISK_BLOCK,
    "FRAUD_SUSPECTED": DeclineCause.RISK_BLOCK,
    "RISK_THRESHOLD_EXCEEDED": DeclineCause.RISK_BLOCK,
    # Bank timeout
    "ISSUER_UNAVAILABLE": DeclineCause.BANK_TIMEOUT,
    "SYSTEM_ERROR": DeclineCause.BANK_TIMEOUT,
    "PROCESSING_ERROR": DeclineCause.BANK_TIMEOUT,
    "TIMEOUT": DeclineCause.BANK_TIMEOUT,
    "ISSUER_NOT_AVAILABLE": DeclineCause.BANK_TIMEOUT,
    "BANK_NOT_SUPPORTED": DeclineCause.BANK_TIMEOUT,
    # Network drop
    "NETWORK_ERROR": DeclineCause.NETWORK_DROP,
    "CONNECTION_TIMEOUT": DeclineCause.NETWORK_DROP,
    "GATEWAY_ERROR": DeclineCause.NETWORK_DROP,
    "COMMUNICATION_ERROR": DeclineCause.NETWORK_DROP,
    "DNS_FAILURE": DeclineCause.NETWORK_DROP,
}

# Weighted distribution for realistic decline patterns
_DECLINE_WEIGHTS = {
    DeclineCause.INSUFFICIENT_FUNDS: 0.40,
    DeclineCause.EXPIRED_INSTRUMENT: 0.15,
    DeclineCause.RISK_BLOCK: 0.10,
    DeclineCause.BANK_TIMEOUT: 0.20,
    DeclineCause.NETWORK_DROP: 0.15,
}


def generate_payment_declines(customers: list[Customer], n: int = 60) -> list[dict[str, Any]]:
    """Generate n synthetic payment decline events with realistic decline codes."""
    events = []
    decline_codes_by_cause = {}
    for code, cause in DECLINE_CODE_MAP.items():
        decline_codes_by_cause.setdefault(cause, []).append(code)

    causes = list(_DECLINE_WEIGHTS.keys())
    weights = list(_DECLINE_WEIGHTS.values())

    for _ in range(n):
        cause = _rng.choices(causes, weights=weights, k=1)[0]
        code = _rng.choice(decline_codes_by_cause[cause])
        cust = _rng.choice(customers)
        amount = round(_rng.uniform(500, 50000), 2)
        retry_count = _rng.choices([0, 1, 2, 3], weights=[0.4, 0.3, 0.2, 0.1], k=1)[0]

        # Urgency based on amount + retry count
        if amount > 20000 or retry_count >= 2:
            urgency = Urgency.HIGH
        elif amount > 5000:
            urgency = Urgency.MEDIUM
        else:
            urgency = Urgency.LOW

        events.append({
            "event_id": f"EVT_DECL_{_uid()}",
            "customer_id": cust.customer_id,
            "decline_code": code,
            "cause": cause.value,
            "amount": amount,
            "urgency": urgency.value,
            "instrument_type": "card",
            "card_last4": f"{_rng.randint(1000, 9999)}",
            "retry_count": retry_count,
            "timestamp": _iso_now(offset_hours=_rng.uniform(-48, 0)),
            "merchant_id": f"MERCH_{_rng.randint(1000, 9999)}",
        })
    return events


# ---------------------------------------------------------------------------
# Checkout abandonments
# ---------------------------------------------------------------------------

def generate_checkout_abandonments(customers: list[Customer], n: int = 50) -> list[dict[str, Any]]:
    """Generate n synthetic checkout session abandonment events with event streams."""
    events = []
    cause_weights = {
        AbandonCause.OTP_FAILURE: 0.30,
        AbandonCause.LATE_PRICE_REVEAL: 0.25,
        AbandonCause.NETWORK_DROP: 0.20,
        AbandonCause.INDECISION_NO_SIGNAL: 0.25,
    }
    causes = list(cause_weights.keys())
    weights = list(cause_weights.values())

    for _ in range(n):
        cause = _rng.choices(causes, weights=weights, k=1)[0]
        cust = _rng.choice(customers)
        cart_value = round(_rng.uniform(800, 75000), 2)

        # Build event stream
        session_start = datetime.utcnow() - timedelta(hours=_rng.uniform(1, 72))
        stream = []
        t = session_start

        # Page view events
        for page in ["product_page", "cart", "checkout"]:
            t += timedelta(seconds=_rng.randint(5, 60))
            stream.append({"type": "page_view", "page": page, "ts": t.isoformat() + "Z"})

        # Cause-specific events
        otp_attempts = 0
        price_reveal_gap_seconds = None
        network_errors = 0

        if cause == AbandonCause.OTP_FAILURE:
            for _ in range(_rng.randint(1, 3)):
                t += timedelta(seconds=_rng.randint(10, 30))
                otp_attempts += 1
                stream.append({"type": "otp_attempt", "success": False, "ts": t.isoformat() + "Z"})
        elif cause == AbandonCause.LATE_PRICE_REVEAL:
            t += timedelta(seconds=_rng.randint(1, 3))
            stream.append({"type": "price_reveal", "ts": t.isoformat() + "Z"})
            price_reveal_gap_seconds = _rng.uniform(0.5, 2.5)  # <3s before drop
        elif cause == AbandonCause.NETWORK_DROP:
            t += timedelta(seconds=_rng.randint(5, 20))
            network_errors = _rng.randint(1, 3)
            for _ in range(network_errors):
                stream.append({"type": "network_error", "ts": t.isoformat() + "Z"})
                t += timedelta(seconds=_rng.randint(2, 10))

        # Drop event
        t += timedelta(seconds=_rng.randint(2, 15))
        stream.append({"type": "session_drop", "ts": t.isoformat() + "Z"})

        urgency = Urgency.HIGH if cart_value > 30000 else (Urgency.MEDIUM if cart_value > 5000 else Urgency.LOW)

        events.append({
            "event_id": f"EVT_ABAN_{_uid()}",
            "customer_id": cust.customer_id,
            "session_id": f"SESS_{_uid()}",
            "cause": cause.value,
            "cart_value": cart_value,
            "urgency": urgency.value,
            "otp_attempts": otp_attempts,
            "price_reveal_gap_seconds": price_reveal_gap_seconds,
            "network_errors": network_errors,
            "event_stream": stream,
            "timestamp": stream[-1]["ts"],
        })
    return events


# ---------------------------------------------------------------------------
# Overdue receivables (B2B)
# ---------------------------------------------------------------------------

def generate_overdue_receivables(customers: list[Customer], n: int = 40) -> list[dict[str, Any]]:
    """Generate n synthetic overdue B2B invoice records with payment history."""
    events = []
    for _ in range(n):
        cust = _rng.choice(customers)
        amount = round(_rng.uniform(25000, 500000), 2)
        days_overdue = _rng.randint(5, 120)

        # Payment history: list of past payment gaps (days between invoice date and payment)
        history_len = _rng.randint(3, 8)
        payment_gaps = [_rng.randint(15, 60) for _ in range(history_len)]

        # Cash constraint heuristic: high variance = likely constrained
        import statistics
        gap_std = statistics.stdev(payment_gaps) if len(payment_gaps) > 1 else 0
        has_dispute = _rng.random() < 0.10  # 10% disputes

        if has_dispute:
            cause = OverdueCause.DISPUTED_AMOUNT.value
        elif gap_std > 15:
            cause = OverdueCause.LIKELY_CASH_CONSTRAINED.value
        else:
            cause = OverdueCause.SIMPLE_DELAY.value

        if days_overdue > 60:
            urgency = Urgency.HIGH
        elif days_overdue > 30:
            urgency = Urgency.MEDIUM
        else:
            urgency = Urgency.LOW

        due_date = datetime.utcnow() - timedelta(days=days_overdue)

        events.append({
            "event_id": f"EVT_RECV_{_uid()}",
            "customer_id": cust.customer_id,
            "invoice_id": f"INV_{_uid()}",
            "amount": amount,
            "cause": cause,
            "urgency": urgency.value,
            "days_overdue": days_overdue,
            "due_date": _iso_date(due_date),
            "payment_history_gaps": payment_gaps,
            "gap_std_dev": round(gap_std, 2),
            "has_dispute": has_dispute,
            "timestamp": _iso_now(),
        })
    return events


# ---------------------------------------------------------------------------
# Expiring instruments
# ---------------------------------------------------------------------------

def generate_expiring_instruments(customers: list[Customer], n: int = 50) -> list[dict[str, Any]]:
    """Generate n synthetic records of cards/mandates about to expire."""
    events = []
    for _ in range(n):
        cust = _rng.choice(customers)
        days_to_expiry = _rng.randint(1, 45)
        days_to_next_charge = _rng.randint(1, 30)
        amount = round(_rng.uniform(500, 25000), 2)

        expiry_date = datetime.utcnow() + timedelta(days=days_to_expiry)
        next_charge_date = datetime.utcnow() + timedelta(days=days_to_next_charge)

        # Only flag if expiry is before or close to next charge
        buffer_days = 5
        at_risk = days_to_expiry < (days_to_next_charge + buffer_days)

        if not at_risk:
            continue  # skip, not actually at risk

        if days_to_expiry < 7:
            urgency = Urgency.HIGH
        elif days_to_expiry < 30:
            urgency = Urgency.MEDIUM
        else:
            urgency = Urgency.LOW

        events.append({
            "event_id": f"EVT_EXPR_{_uid()}",
            "customer_id": cust.customer_id,
            "card_last4": f"{_rng.randint(1000, 9999)}",
            "instrument_type": _rng.choice(["credit_card", "debit_card"]),
            "expiry_date": _iso_date(expiry_date),
            "next_charge_date": _iso_date(next_charge_date),
            "expected_amount": amount,
            "days_to_expiry": days_to_expiry,
            "urgency": urgency.value,
            "cause": ExpiryCause.EXPIRY_WITHIN_WINDOW.value,
            "timestamp": _iso_now(),
        })

    # Ensure we have enough records — generate more if filtering removed too many
    while len(events) < n:
        cust = _rng.choice(customers)
        days_to_expiry = _rng.randint(1, 20)
        days_to_next_charge = _rng.randint(5, 25)
        amount = round(_rng.uniform(500, 25000), 2)
        expiry_date = datetime.utcnow() + timedelta(days=days_to_expiry)

        if days_to_expiry < 7:
            urgency = Urgency.HIGH
        elif days_to_expiry < 30:
            urgency = Urgency.MEDIUM
        else:
            urgency = Urgency.LOW

        events.append({
            "event_id": f"EVT_EXPR_{_uid()}",
            "customer_id": cust.customer_id,
            "card_last4": f"{_rng.randint(1000, 9999)}",
            "instrument_type": _rng.choice(["credit_card", "debit_card"]),
            "expiry_date": _iso_date(expiry_date),
            "next_charge_date": _iso_date(datetime.utcnow() + timedelta(days=days_to_next_charge)),
            "expected_amount": amount,
            "days_to_expiry": days_to_expiry,
            "urgency": urgency.value,
            "cause": ExpiryCause.EXPIRY_WITHIN_WINDOW.value,
            "timestamp": _iso_now(),
        })
    return events[:n]


# ---------------------------------------------------------------------------
# Mandate failures (UPI Autopay)
# ---------------------------------------------------------------------------

def generate_mandate_failures(customers: list[Customer], n: int = 20) -> list[dict[str, Any]]:
    """
    Generate n synthetic UPI Autopay mandate failure events.
    Each customer gets a past debit history clustered around a specific day-of-month
    (proxy for salary credit date).
    """
    events = []
    today = datetime.utcnow()

    # Reserve indices for guaranteed edge cases
    # indices 0,1 → retries_remaining == 0 (budget exhausted)
    # indices 2,3,4 → cycle ends before predicted optimal window
    # index 5 → assigned to an opted-out customer (for verification)
    opted_out_customers = [c for c in customers if c.opted_out]
    non_opted_out = [c for c in customers if not c.opted_out]

    for i in range(n):
        # Pick customer
        if i == 5 and opted_out_customers:
            cust = _rng.choice(opted_out_customers)
        else:
            cust = _rng.choice(non_opted_out) if non_opted_out else _rng.choice(customers)

        # Customer's typical debit day (clustered)
        typical_day = _rng.randint(1, 28)

        # Generate past successful debit history (3-6 cycles)
        history_len = _rng.randint(3, 6)
        debit_history = []
        for month_offset in range(history_len, 0, -1):
            # Cluster around typical_day with ±2 days noise
            actual_day = max(1, min(28, typical_day + _rng.randint(-2, 2)))
            past_date = today - timedelta(days=30 * month_offset)
            past_date = past_date.replace(day=actual_day)
            debit_history.append(_iso_date(past_date))

        max_retries = 3
        amount = round(_rng.uniform(1000, 30000), 2)

        # Edge case control
        if i in (0, 1):
            # Budget exhausted
            retries_used = max_retries
            cycle_end = today + timedelta(days=_rng.randint(3, 10))
            cause = DeclineCause.INSUFFICIENT_FUNDS.value
        elif i in (2, 3, 4):
            # Cycle ends before predicted optimal window
            retries_used = 2  # 1 retry remaining
            # Force typical_day to be far enough out that predicted date > cycle_end
            # Set typical_day to ~25-28 and cycle_end to just 1-2 days from today
            typical_day = _rng.randint(25, 28)
            cycle_end = today + timedelta(days=_rng.randint(1, 2))
            cause = DeclineCause.INSUFFICIENT_FUNDS.value
        else:
            retries_used = _rng.choices([0, 1, 2], weights=[0.4, 0.35, 0.25], k=1)[0]
            cycle_end = today + timedelta(days=_rng.randint(5, 14))
            # Mix of causes
            cause = _rng.choices(
                [DeclineCause.INSUFFICIENT_FUNDS.value, DeclineCause.BANK_TIMEOUT.value,
                 DeclineCause.NETWORK_DROP.value],
                weights=[0.6, 0.25, 0.15],
                k=1,
            )[0]

        retries_remaining = max_retries - retries_used

        if retries_remaining <= 1:
            urgency = Urgency.HIGH
        elif amount > 15000:
            urgency = Urgency.MEDIUM
        else:
            urgency = Urgency.LOW

        events.append({
            "event_id": f"EVT_MAND_{_uid()}",
            "customer_id": cust.customer_id,
            "decline_code": "UPI_MANDATE_DEBIT_FAILED",
            "cause": cause,
            "amount": amount,
            "urgency": urgency.value,
            "instrument_type": "upi_autopay_mandate",
            "mandate_id": f"MAND_{_uid()}",
            "max_retries_allowed": max_retries,
            "retries_used": retries_used,
            "retries_remaining": retries_remaining,
            "mandate_cycle_end_date": _iso_date(cycle_end),
            "debit_history": debit_history,
            "typical_debit_day": typical_day,
            "retry_count": retries_used,
            "timestamp": _iso_now(offset_hours=_rng.uniform(-24, 0)),
            "merchant_id": f"MERCH_{_rng.randint(1000, 9999)}",
        })
    return events


# ---------------------------------------------------------------------------
# Master generator
# ---------------------------------------------------------------------------

def generate_all_data() -> dict[str, Any]:
    """Generate the complete synthetic dataset for the orchestrator."""
    customers = generate_customers(100)
    return {
        "customers": customers,
        "payment_declines": generate_payment_declines(customers, 60),
        "checkout_abandonments": generate_checkout_abandonments(customers, 50),
        "overdue_receivables": generate_overdue_receivables(customers, 40),
        "expiring_instruments": generate_expiring_instruments(customers, 50),
        "mandate_failures": generate_mandate_failures(customers, 20),
    }


if __name__ == "__main__":
    data = generate_all_data()
    total = sum(len(v) for k, v in data.items() if k != "customers")
    print(f"Generated {total} total risk events across 5 types:")
    for key, val in data.items():
        print(f"  {key}: {len(val)} records")
