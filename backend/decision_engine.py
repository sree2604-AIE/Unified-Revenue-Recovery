"""
Decision Engine — Deterministic rule-based mapping from RiskObject → ActionType.
Opt-out check fires FIRST (before mandate branch) to prevent bypass.
"""

from __future__ import annotations

from typing import Any, Optional

from models import (
    ActionType,
    AbandonCause,
    DeclineCause,
    ExpiryCause,
    OverdueCause,
    RiskObject,
    RiskType,
    Urgency,
)
from mandate_budget_optimizer import pick_mandate_action

# ---------------------------------------------------------------------------
# Stopping‑rule constants
# ---------------------------------------------------------------------------
MAX_ATTEMPTS_PER_RISK = 3

# Tone escalation: friendly → firm → final (never threatening)
TONE_BY_ATTEMPT = {1: "friendly", 2: "firm", 3: "final"}

# ---------------------------------------------------------------------------
# Customer opt‑out registry (populated at runtime by the orchestrator)
# ---------------------------------------------------------------------------
_opted_out_customers: set[str] = set()
_attempt_counts: dict[str, int] = {}


def reset_state() -> None:
    """Reset engine state between batch runs."""
    _opted_out_customers.clear()
    _attempt_counts.clear()


def register_opted_out(customer_ids: set[str]) -> None:
    """Load opted-out customer IDs (called once before a batch run)."""
    _opted_out_customers.update(customer_ids)


def record_attempt(risk_id: str) -> int:
    """Increment and return the attempt number for a given risk_id."""
    _attempt_counts[risk_id] = _attempt_counts.get(risk_id, 0) + 1
    return _attempt_counts[risk_id]


def get_attempt_count(risk_id: str) -> int:
    return _attempt_counts.get(risk_id, 0)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def decide(risk: RiskObject) -> tuple[str, str]:
    """
    Pure-function decision: RiskObject → (action, reasoning).

    Execution order:
      1. OPT-OUT CHECK FIRST — before anything else, including mandate logic
      2. MAX ATTEMPTS CHECK — cap retries per risk_id
      3. MANDATE BRANCH — if is_mandate, delegate to mandate optimizer
      4. STANDARD 12-ROW TABLE — deterministic cause→action mapping
    """

    # ── 1. Opt-out hard stop ──────────────────────────────────────────────
    if risk.customer_id in _opted_out_customers:
        return (
            ActionType.NO_ACTION.value,
            "customer opted out — hard stop, no contact",
        )

    # ── 2. Max attempts per risk_id ───────────────────────────────────────
    current = get_attempt_count(risk.risk_id)
    if current >= MAX_ATTEMPTS_PER_RISK:
        return (
            ActionType.NO_ACTION.value,
            f"max attempts reached ({current}/{MAX_ATTEMPTS_PER_RISK}) — stopping rule",
        )

    # ── 3. Mandate-specific branch ────────────────────────────────────────
    if risk.context.get("is_mandate"):
        return pick_mandate_action(risk)

    # ── 4. Standard decision table ────────────────────────────────────────
    return _standard_decision(risk)


# ---------------------------------------------------------------------------
# Standard 12-row decision table
# ---------------------------------------------------------------------------

def _standard_decision(risk: RiskObject) -> tuple[str, str]:
    """Map non-mandate risks to actions using the deterministic table."""

    rt = risk.risk_type
    cause = risk.cause

    # ── Payment decline ───────────────────────────────────────────────────
    if rt == RiskType.PAYMENT_DECLINE:
        if cause == DeclineCause.INSUFFICIENT_FUNDS.value:
            return (
                ActionType.SCHEDULE_RETRY.value,
                "insufficient funds — scheduling retry for likely payday window",
            )
        if cause == DeclineCause.EXPIRED_INSTRUMENT.value:
            return (
                ActionType.PROMPT_NEW_INSTRUMENT.value,
                "expired instrument — prompting customer to add new payment method",
            )
        if cause == DeclineCause.RISK_BLOCK.value:
            # NEVER auto-retry risk blocks
            return (
                ActionType.ESCALATE_TO_HUMAN_REVIEW.value,
                "risk_block — escalated to human review (auto-retry prohibited)",
            )
        if cause in (DeclineCause.BANK_TIMEOUT.value, DeclineCause.NETWORK_DROP.value):
            return (
                ActionType.RETRY_IMMEDIATE.value,
                f"transient failure ({cause}) — retrying immediately",
            )

    # ── Checkout abandon ──────────────────────────────────────────────────
    if rt == RiskType.CHECKOUT_ABANDON:
        if cause == AbandonCause.OTP_FAILURE.value:
            return (
                ActionType.SEND_ALT_VERIFICATION_NUDGE.value,
                "OTP failure detected — sending alternative verification nudge",
            )
        if cause == AbandonCause.LATE_PRICE_REVEAL.value:
            return (
                ActionType.SEND_PRICE_TRANSPARENCY_NUDGE.value,
                "late price reveal — sending price transparency nudge",
            )
        if cause == AbandonCause.NETWORK_DROP.value:
            return (
                ActionType.SEND_RESUME_CHECKOUT_LINK.value,
                "network drop during checkout — sending resume link",
            )
        if cause == AbandonCause.INDECISION_NO_SIGNAL.value:
            # Stopping rule: don't spam indecisive users
            return (
                ActionType.NO_ACTION.value,
                "indecision with no signal — stopping rule, no spam",
            )

    # ── Receivable overdue ────────────────────────────────────────────────
    if rt == RiskType.RECEIVABLE_OVERDUE:
        if cause == OverdueCause.LIKELY_CASH_CONSTRAINED.value:
            return (
                ActionType.PROPOSE_PARTIAL_PAYMENT_PLAN.value,
                "payer likely cash-constrained — proposing structured payment plan",
            )
        if cause == OverdueCause.DISPUTED_AMOUNT.value:
            return (
                ActionType.ESCALATE_TO_HUMAN_REVIEW.value,
                "disputed amount — escalated to human review for resolution",
            )
        if cause == OverdueCause.SIMPLE_DELAY.value:
            attempt = get_attempt_count(risk.risk_id) + 1
            tone = TONE_BY_ATTEMPT.get(attempt, "final")
            return (
                ActionType.SEND_REMINDER.value,
                f"simple delay — sending {tone} reminder (attempt {attempt})",
            )

    # ── Instrument expiring ───────────────────────────────────────────────
    if rt == RiskType.INSTRUMENT_EXPIRING:
        return (
            ActionType.SEND_PROACTIVE_UPDATE_NUDGE.value,
            "instrument expiring within window — sending proactive update nudge",
        )

    # ── Fallback (should never reach here) ────────────────────────────────
    return (
        ActionType.NO_ACTION.value,
        f"unrecognized risk_type/cause combination: {rt}/{cause}",
    )
