"""
FastAPI Backend — REST API serving data to the dashboard.
"""

from __future__ import annotations

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from models import ActionType, RiskType
from orchestrator import get_audit_logger, run_batch

app = FastAPI(
    title="Revenue Recovery Orchestrator API",
    description="API for the Unified Revenue Recovery Orchestrator dashboard",
    version="1.0.0",
)

# CORS for local dev (Vite runs on 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/run-batch")
def api_run_batch():
    """Trigger the full recovery pipeline and return summary metrics."""
    result = run_batch()
    return {"status": "ok", "metrics": result}


@app.get("/api/metrics")
def api_metrics():
    """Return aggregated metrics (₹ at risk, ₹ recovered, per-source)."""
    logger = get_audit_logger()
    return logger.get_summary_metrics()


@app.get("/api/audit-trail")
def api_audit_trail(
    risk_type: str | None = Query(None, description="Filter by risk_type"),
    search: str | None = Query(None, description="Search by risk_id"),
    limit: int = Query(500, description="Max records to return"),
    offset: int = Query(0, description="Offset for pagination"),
):
    """Return the full audit log, optionally filtered."""
    try:
        logger = get_audit_logger()
        trail = logger.get_audit_trail()

        # Apply filters
        if risk_type:
            trail = [r for r in trail if r["risk_type"] == risk_type]
        if search:
            trail = [r for r in trail if search.lower() in r["risk_id"].lower()]

        total = len(trail)
        trail = trail[offset: offset + limit]

        return {"total": total, "records": trail}
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}


@app.get("/api/risk-breakdown")
def api_risk_breakdown():
    """Per risk_type breakdown for charts."""
    logger = get_audit_logger()
    metrics = logger.get_summary_metrics()
    return metrics.get("by_source", {})


@app.get("/api/channel-stats")
def api_channel_stats():
    """Channel effectiveness data."""
    logger = get_audit_logger()
    return logger.get_channel_stats()


@app.get("/api/failure-cases")
def api_failure_cases():
    """Highlighted stopping-rule activations."""
    logger = get_audit_logger()
    return logger.get_failure_cases()


@app.get("/api/mandate-stats")
def api_mandate_stats():
    """Mandate retry budget stats."""
    logger = get_audit_logger()
    return logger.get_mandate_stats()


@app.get("/api/decision-table")
def api_decision_table():
    """Return the decision engine rules for the explainability panel."""
    return {
        "standard_rules": [
            {"risk_type": "payment_decline", "cause": "insufficient_funds", "action": "schedule_retry", "description": "Delay retry to likely payday window"},
            {"risk_type": "payment_decline", "cause": "expired_instrument", "action": "prompt_new_instrument", "description": "Prompt customer to add new payment method"},
            {"risk_type": "payment_decline", "cause": "risk_block", "action": "escalate_to_human_review", "description": "NEVER auto-retry — escalate to human"},
            {"risk_type": "payment_decline", "cause": "bank_timeout", "action": "retry_immediate", "description": "Transient failure — retry immediately"},
            {"risk_type": "payment_decline", "cause": "network_drop", "action": "retry_immediate", "description": "Transient failure — retry immediately"},
            {"risk_type": "checkout_abandon", "cause": "otp_failure", "action": "send_alt_verification_nudge", "description": "Send alternative verification method"},
            {"risk_type": "checkout_abandon", "cause": "late_price_reveal", "action": "send_price_transparency_nudge", "description": "Send price transparency nudge"},
            {"risk_type": "checkout_abandon", "cause": "network_drop", "action": "send_resume_checkout_link", "description": "Send resume checkout link"},
            {"risk_type": "checkout_abandon", "cause": "indecision_no_signal", "action": "no_action", "description": "Stopping rule — don't spam"},
            {"risk_type": "receivable_overdue", "cause": "likely_cash_constrained", "action": "propose_partial_payment_plan", "description": "Propose structured payment plan"},
            {"risk_type": "receivable_overdue", "cause": "disputed_amount", "action": "escalate_to_human_review", "description": "Escalate dispute to human review"},
            {"risk_type": "receivable_overdue", "cause": "simple_delay", "action": "send_reminder", "description": "Send reminder with escalating tone"},
            {"risk_type": "instrument_expiring", "cause": "expiry_within_window", "action": "send_proactive_update_nudge", "description": "Proactive instrument update nudge"},
        ],
        "mandate_rules": [
            {"condition": "retries_remaining == 0", "action": "escalate_to_human_review", "description": "Budget exhausted — re-authorization required"},
            {"condition": "retries >= 2 & transient cause", "action": "retry_immediate", "description": "Transient failure with budget to spare"},
            {"condition": "retries <= 1 & insufficient_funds", "action": "schedule_retry_optimal_window", "description": "Hold final retry for predicted optimal window"},
            {"condition": "predicted_date > cycle_end", "action": "escalate_to_human_review", "description": "Cycle ends before optimal window — escalate"},
        ],
        "stopping_rules": [
            {"name": "opt_out_hard_stop", "description": "Customer opted out → no_action (checked FIRST, before mandate logic)", "priority": 1},
            {"name": "max_attempts_per_risk", "description": "Max 3 attempts per risk_id", "priority": 2},
            {"name": "mandate_budget_exhausted", "description": "Mandate retries depleted → escalate", "priority": 3},
            {"name": "risk_block_never_auto_retry", "description": "Risk blocks always escalated to human", "priority": 4},
            {"name": "indecision_no_spam", "description": "No distinguishing signal → don't contact", "priority": 5},
            {"name": "tone_escalation_cap", "description": "Reminders: friendly → firm → final (never threatening)", "priority": 6},
        ],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
