"""
Core data models for the Unified Revenue Recovery Orchestrator.
All shared contracts: risk objects, cause taxonomies, action enums, audit log schema.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RiskType(str, Enum):
    PAYMENT_DECLINE = "payment_decline"
    CHECKOUT_ABANDON = "checkout_abandon"
    RECEIVABLE_OVERDUE = "receivable_overdue"
    INSTRUMENT_EXPIRING = "instrument_expiring"


class Urgency(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# -- Cause enums per risk type -----------------------------------------------

class DeclineCause(str, Enum):
    INSUFFICIENT_FUNDS = "insufficient_funds"
    EXPIRED_INSTRUMENT = "expired_instrument"
    RISK_BLOCK = "risk_block"
    BANK_TIMEOUT = "bank_timeout"
    NETWORK_DROP = "network_drop"


class AbandonCause(str, Enum):
    OTP_FAILURE = "otp_failure"
    LATE_PRICE_REVEAL = "late_price_reveal"
    NETWORK_DROP = "network_drop"
    INDECISION_NO_SIGNAL = "indecision_no_signal"


class OverdueCause(str, Enum):
    LIKELY_CASH_CONSTRAINED = "likely_cash_constrained"
    DISPUTED_AMOUNT = "disputed_amount"
    SIMPLE_DELAY = "simple_delay"


class ExpiryCause(str, Enum):
    EXPIRY_WITHIN_WINDOW = "expiry_within_window"


# -- Action types (bounded action set) --------------------------------------

class ActionType(str, Enum):
    # Payment decline actions
    SCHEDULE_RETRY = "schedule_retry"
    PROMPT_NEW_INSTRUMENT = "prompt_new_instrument"
    RETRY_IMMEDIATE = "retry_immediate"

    # Checkout abandon actions
    SEND_ALT_VERIFICATION_NUDGE = "send_alt_verification_nudge"
    SEND_PRICE_TRANSPARENCY_NUDGE = "send_price_transparency_nudge"
    SEND_RESUME_CHECKOUT_LINK = "send_resume_checkout_link"

    # Receivable overdue actions
    PROPOSE_PARTIAL_PAYMENT_PLAN = "propose_partial_payment_plan"
    SEND_REMINDER = "send_reminder"

    # Instrument expiring actions
    SEND_PROACTIVE_UPDATE_NUDGE = "send_proactive_update_nudge"

    # Mandate-specific action
    SCHEDULE_RETRY_OPTIMAL_WINDOW = "schedule_retry_optimal_window"

    # Shared actions
    ESCALATE_TO_HUMAN_REVIEW = "escalate_to_human_review"
    NO_ACTION = "no_action"


class ChannelType(str, Enum):
    SMS = "sms"
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    VOICE = "voice"


class OutcomeType(str, Enum):
    RESPONDED = "responded"
    NO_RESPONSE = "no_response"
    PAID = "paid"
    FAILED = "failed"
    PENDING = "pending"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class MandateContext(BaseModel):
    """Extra context present only when instrument_type == 'upi_autopay_mandate'."""
    mandate_id: str
    retries_used: int
    max_retries_allowed: int  # NPCI/bank cap, e.g. 3 per billing cycle
    retries_remaining: int    # derived: max_retries_allowed - retries_used
    predicted_optimal_retry_date: Optional[str] = None  # ISO date
    mandate_cycle_end_date: str  # hard deadline — no retries after this


class RiskObject(BaseModel):
    """
    The shared risk object — core data contract.
    Every detector emits this exact shape so the decision engine stays source-agnostic.
    """
    risk_id: str
    customer_id: str
    risk_type: RiskType
    cause: str  # enum value specific to risk_type
    amount_at_stake: float
    urgency: Urgency
    detected_at: str  # ISO timestamp
    context: dict[str, Any] = Field(default_factory=dict)
    # context holds risk_type-specific fields:
    #   - decline_code, instrument_type, retry_count (payment_decline)
    #   - session_id, events, cart_value (checkout_abandon)
    #   - invoice_id, days_overdue, payment_history (receivable_overdue)
    #   - card_last4, expiry_date, next_charge_date (instrument_expiring)
    #   - is_mandate, mandate (MandateContext dict) (mandate failures)


class ActionRecord(BaseModel):
    """Audit record for every action taken."""
    risk_id: str
    customer_id: str
    risk_type: str
    cause: str
    action: str
    channel: Optional[str] = None
    timestamp: str
    outcome: str
    attempt_number: int
    amount_at_stake: float
    amount_recovered: float = 0.0
    reasoning: str
    customer_opted_out: bool = False
    is_mandate: bool = False
    mandate_context: Optional[dict] = None


class RecoveryResult(BaseModel):
    """Per-risk recovery outcome."""
    risk_id: str
    amount_at_stake: float
    amount_recovered: float
    recovery_rate: float  # amount_recovered / amount_at_stake


# ---------------------------------------------------------------------------
# Customer model (for channel selection & opt-out tracking)
# ---------------------------------------------------------------------------

class CustomerSegment(str, Enum):
    A = "A"
    B = "B"
    C = "C"


class Customer(BaseModel):
    """Synthetic customer profile."""
    customer_id: str
    name: str
    segment: CustomerSegment
    preferred_channel: ChannelType
    opted_out: bool = False
    phone: str = ""
    email: str = ""
