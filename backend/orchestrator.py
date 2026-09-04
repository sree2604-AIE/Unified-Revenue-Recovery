"""
Orchestrator — Ties all layers together into a single batch-processing pipeline.
Detection → Diagnosis → Decision → Execution → Audit.
"""

from __future__ import annotations

from typing import Any

from models import ActionType, RiskObject
from data_generator import generate_all_data
from detectors import (
    detect_decline_risks,
    detect_checkout_risks,
    detect_receivable_risks,
    detect_expiry_risks,
    detect_mandate_risks,
)
from decision_engine import decide, record_attempt, register_opted_out, reset_state
from execution_engine import ExecutionEngine
from audit_logger import AuditLogger


# Singleton instances (reset on each batch run)
_audit_logger = AuditLogger()
_execution_engine: ExecutionEngine | None = None


def get_audit_logger() -> AuditLogger:
    return _audit_logger


def run_batch() -> dict[str, Any]:
    """
    Execute the full pipeline:
      1. Generate synthetic data (all 5 types)
      2. Run all 5 detectors → collect RiskObject[]
      3. For each risk: decide() → select_channel() → execute_action()
      4. Log everything to audit trail
      5. Return summary metrics
    """
    global _execution_engine

    # Reset state
    reset_state()
    _audit_logger.clear()

    # 1. Generate data
    data = generate_all_data()
    customers = data["customers"]

    # 2. Initialize execution engine with customer data
    _execution_engine = ExecutionEngine(customers, seed=42)

    # 3. Register opted-out customers
    opted_out_ids = {c.customer_id for c in customers if c.opted_out}
    register_opted_out(opted_out_ids)

    # 4. Run all detectors
    all_risks: list[RiskObject] = []

    # Decline detector (non-mandate payment declines)
    decline_risks = detect_decline_risks(data["payment_declines"])
    all_risks.extend(decline_risks)

    # Checkout detector
    checkout_risks = detect_checkout_risks(data["checkout_abandonments"])
    all_risks.extend(checkout_risks)

    # Receivable detector
    receivable_risks = detect_receivable_risks(data["overdue_receivables"])
    all_risks.extend(receivable_risks)

    # Expiry detector
    expiry_risks = detect_expiry_risks(data["expiring_instruments"])
    all_risks.extend(expiry_risks)

    # Mandate detector
    mandate_risks = detect_mandate_risks(data["mandate_failures"])
    all_risks.extend(mandate_risks)

    # 5. Process each risk through the pipeline
    for risk in all_risks:
        _process_risk(risk)

    # 6. Return summary
    metrics = _audit_logger.get_summary_metrics()
    metrics["mandate_stats"] = _audit_logger.get_mandate_stats()
    metrics["detector_counts"] = {
        "payment_decline": len(decline_risks),
        "checkout_abandon": len(checkout_risks),
        "receivable_overdue": len(receivable_risks),
        "instrument_expiring": len(expiry_risks),
        "mandate_failures": len(mandate_risks),
        "total": len(all_risks),
    }

    return metrics


def _process_risk(risk: RiskObject) -> None:
    """Process a single risk through decide → execute → log."""
    # Record attempt
    attempt = record_attempt(risk.risk_id)

    # Decision
    action, reasoning = decide(risk)

    # Channel selection
    channel = _execution_engine.select_channel(risk.customer_id, action)

    # Execution
    record = _execution_engine.execute_action(
        risk=risk,
        action=action,
        channel=channel,
        attempt_number=attempt,
        reasoning=reasoning,
    )

    # If action is no_action due to opt-out, force the flag
    if "opted out" in reasoning:
        record.customer_opted_out = True
        record.amount_recovered = 0.0
        record.outcome = "no_response"

    # Log
    _audit_logger.log(record)


def run_single(risk: RiskObject) -> dict[str, Any]:
    """Process a single risk object (for API endpoint / live demo)."""
    _process_risk(risk)
    trail = _audit_logger.get_audit_trail()
    return trail[-1] if trail else {}


if __name__ == "__main__":
    result = run_batch()
    print("\n" + "=" * 60)
    print("UNIFIED REVENUE RECOVERY ORCHESTRATOR — BATCH RESULTS")
    print("=" * 60)
    print(f"\nRecords processed: {result['total_records']}")
    print(f"  Detectors: {result['detector_counts']}")
    print(f"\n₹ At Risk:    ₹{result['total_at_risk']:,.2f}")
    print(f"₹ Recovered:  ₹{result['total_recovered']:,.2f}")
    print(f"Recovery Rate: {result['recovery_rate']:.1f}%")
    print(f"\nActions taken: {result['actions_taken']}")
    print(f"Escalations:   {result['escalations']}")
    print(f"No-actions:    {result['no_actions']}")
    print("\nPer-source breakdown:")
    for src, stats in result["by_source"].items():
        print(f"  {src}: ₹{stats['at_risk']:,.2f} at risk, "
              f"₹{stats['recovered']:,.2f} recovered ({stats['recovery_rate']:.1f}%)")
    ms = result.get("mandate_stats", {})
    if ms:
        print(f"\nMandate Stats:")
        print(f"  Total mandates:          {ms['total_mandates']}")
        print(f"  At-risk (retries ≤ 1):   {ms['at_risk_mandates']}")
        print(f"  Budget exhausted:        {ms['budget_exhausted']}")
        print(f"  Optimal window holds:    {ms['optimal_window_holds']}")
        print(f"  Cycle deadline esc.:     {ms['cycle_deadline_escalations']}")
