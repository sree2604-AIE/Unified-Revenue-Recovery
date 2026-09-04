"""
Execution Engine — Channel optimizer + action executor.
Picks SMS/WhatsApp/email/voice per customer segment,
simulates outreach + probabilistic outcome, calculates recovery.
"""

from __future__ import annotations

import random
from typing import Any, Optional

from models import (
    ActionRecord,
    ActionType,
    ChannelType,
    Customer,
    CustomerSegment,
    OutcomeType,
    RecoveryResult,
    RiskObject,
)

# ---------------------------------------------------------------------------
# Channel response rates by customer segment (simulated historical data)
# ---------------------------------------------------------------------------
CHANNEL_RESPONSE_RATES: dict[str, dict[str, float]] = {
    CustomerSegment.A.value: {
        ChannelType.WHATSAPP.value: 0.72,
        ChannelType.SMS.value: 0.45,
        ChannelType.EMAIL.value: 0.30,
        ChannelType.VOICE.value: 0.20,
    },
    CustomerSegment.B.value: {
        ChannelType.EMAIL.value: 0.65,
        ChannelType.WHATSAPP.value: 0.40,
        ChannelType.SMS.value: 0.35,
        ChannelType.VOICE.value: 0.15,
    },
    CustomerSegment.C.value: {
        ChannelType.SMS.value: 0.55,
        ChannelType.VOICE.value: 0.50,
        ChannelType.WHATSAPP.value: 0.30,
        ChannelType.EMAIL.value: 0.20,
    },
}

# Actions that don't involve outreach (no channel selection needed)
NO_OUTREACH_ACTIONS = {
    ActionType.NO_ACTION.value,
    ActionType.RETRY_IMMEDIATE.value,
    ActionType.SCHEDULE_RETRY.value,
    ActionType.SCHEDULE_RETRY_OPTIMAL_WINDOW.value,
}

# Recovery probability by action type (given the action was executed)
ACTION_RECOVERY_PROBS: dict[str, float] = {
    ActionType.RETRY_IMMEDIATE.value: 0.65,
    ActionType.SCHEDULE_RETRY.value: 0.55,
    ActionType.SCHEDULE_RETRY_OPTIMAL_WINDOW.value: 0.75,  # higher: timed to payday
    ActionType.PROMPT_NEW_INSTRUMENT.value: 0.40,
    ActionType.SEND_ALT_VERIFICATION_NUDGE.value: 0.50,
    ActionType.SEND_PRICE_TRANSPARENCY_NUDGE.value: 0.35,
    ActionType.SEND_RESUME_CHECKOUT_LINK.value: 0.45,
    ActionType.PROPOSE_PARTIAL_PAYMENT_PLAN.value: 0.60,
    ActionType.SEND_REMINDER.value: 0.55,
    ActionType.SEND_PROACTIVE_UPDATE_NUDGE.value: 0.50,
    ActionType.ESCALATE_TO_HUMAN_REVIEW.value: 0.30,
    ActionType.NO_ACTION.value: 0.0,
}


class ExecutionEngine:
    """Simulates outreach execution with channel selection and outcome tracking."""

    def __init__(self, customers: list[Customer], seed: int = 42):
        self._customer_map: dict[str, Customer] = {c.customer_id: c for c in customers}
        self._rng = random.Random(seed)

    def select_channel(self, customer_id: str, action: str) -> Optional[str]:
        """Pick the best channel for this customer segment's historical response rate."""
        if action in NO_OUTREACH_ACTIONS:
            return None

        customer = self._customer_map.get(customer_id)
        if not customer:
            return ChannelType.SMS.value  # fallback

        segment_rates = CHANNEL_RESPONSE_RATES.get(
            customer.segment.value, CHANNEL_RESPONSE_RATES[CustomerSegment.A.value]
        )
        # Pick the channel with highest response rate
        best_channel = max(segment_rates, key=segment_rates.get)
        return best_channel

    def execute_action(
        self,
        risk: RiskObject,
        action: str,
        channel: Optional[str],
        attempt_number: int,
        reasoning: str,
    ) -> ActionRecord:
        """Simulate executing an action and determine the outcome."""
        from datetime import datetime

        # Determine outcome probabilistically
        outcome = self._simulate_outcome(action, channel, risk.customer_id)
        amount_recovered = self._calculate_recovery(risk, action, outcome)

        customer = self._customer_map.get(risk.customer_id)
        is_mandate = risk.context.get("is_mandate", False)

        record = ActionRecord(
            risk_id=risk.risk_id,
            customer_id=risk.customer_id,
            risk_type=risk.risk_type.value if hasattr(risk.risk_type, "value") else risk.risk_type,
            cause=risk.cause,
            action=action,
            channel=channel,
            timestamp=datetime.utcnow().isoformat() + "Z",
            outcome=outcome,
            attempt_number=attempt_number,
            amount_at_stake=risk.amount_at_stake,
            amount_recovered=amount_recovered,
            reasoning=reasoning,
            customer_opted_out=customer.opted_out if customer else False,
            is_mandate=is_mandate,
            mandate_context=risk.context.get("mandate") if is_mandate else None,
        )
        return record

    def _simulate_outcome(
        self, action: str, channel: Optional[str], customer_id: str
    ) -> str:
        """Probabilistic outcome simulation."""
        if action == ActionType.NO_ACTION.value:
            return OutcomeType.NO_RESPONSE.value

        if action == ActionType.ESCALATE_TO_HUMAN_REVIEW.value:
            # Human review has its own outcome distribution
            roll = self._rng.random()
            if roll < 0.30:
                return OutcomeType.PAID.value
            elif roll < 0.55:
                return OutcomeType.RESPONDED.value
            else:
                return OutcomeType.PENDING.value

        # For retry actions (no outreach), outcome is based on recovery prob
        base_prob = ACTION_RECOVERY_PROBS.get(action, 0.3)

        # Channel bonus: if outreach, multiply by channel response rate
        if channel:
            customer = self._customer_map.get(customer_id)
            if customer:
                seg_rates = CHANNEL_RESPONSE_RATES.get(
                    customer.segment.value, {}
                )
                channel_rate = seg_rates.get(channel, 0.3)
                # Blend: base_prob * 0.6 + channel_rate * 0.4
                effective_prob = base_prob * 0.6 + channel_rate * 0.4
            else:
                effective_prob = base_prob
        else:
            effective_prob = base_prob

        roll = self._rng.random()
        if roll < effective_prob * 0.6:
            return OutcomeType.PAID.value
        elif roll < effective_prob:
            return OutcomeType.RESPONDED.value
        elif roll < effective_prob + 0.1:
            return OutcomeType.FAILED.value
        else:
            return OutcomeType.NO_RESPONSE.value

    def _calculate_recovery(
        self, risk: RiskObject, action: str, outcome: str
    ) -> float:
        """Calculate recovered ₹ based on action + outcome."""
        amount = risk.amount_at_stake

        if outcome == OutcomeType.PAID.value:
            return round(amount, 2)
        elif outcome == OutcomeType.RESPONDED.value:
            # Partial recovery depends on action type
            if action == ActionType.PROPOSE_PARTIAL_PAYMENT_PLAN.value:
                return round(amount * 0.70, 2)  # 70% for payment plans
            else:
                return round(amount * 0.90, 2)  # 90% for retries/nudges
        else:
            return 0.0
