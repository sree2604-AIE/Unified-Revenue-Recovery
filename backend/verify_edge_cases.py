"""Verification script for edge cases."""
from orchestrator import run_batch, get_audit_logger

result = run_batch()
logger = get_audit_logger()
trail = logger.get_audit_trail()

print("=== CYCLE DEADLINE CASES ===")
cycle_cases = [r for r in trail if "cycle ends before" in r.get("reasoning", "")]
print(f"Found {len(cycle_cases)} cycle-deadline escalation(s)")
for c in cycle_cases:
    print(f"  {c['risk_id']}: {c['reasoning']}")

print("\n=== OPTED-OUT MANDATE CASES ===")
opted_mandate = [r for r in trail if r.get("is_mandate") and r.get("customer_opted_out")]
print(f"Found {len(opted_mandate)} opted-out mandate case(s)")
for c in opted_mandate:
    print(f"  {c['risk_id']}: action={c['action']}, reasoning={c['reasoning']}")

# Also check all opted-out cases
print("\n=== ALL OPTED-OUT CASES ===")
opted_all = [r for r in trail if r.get("customer_opted_out")]
print(f"Found {len(opted_all)} opted-out case(s) total")
for c in opted_all:
    print(f"  {c['risk_id']} (mandate={c.get('is_mandate')}): action={c['action']}, reasoning={c['reasoning']}")

print("\n=== OPTIMAL WINDOW HOLDS ===")
optimal = [r for r in trail if r.get("action") == "schedule_retry_optimal_window"]
print(f"Found {len(optimal)} optimal-window hold(s)")
for c in optimal:
    print(f"  {c['risk_id']}: {c['reasoning']}")

print("\n=== BUDGET EXHAUSTED ===")
exhausted = [r for r in trail if "mandate_budget_exhausted" in r.get("reasoning", "")]
print(f"Found {len(exhausted)} budget-exhausted case(s)")
for c in exhausted:
    print(f"  {c['risk_id']}: {c['reasoning']}")

print("\n=== FAILURE CASES (stopping rules) ===")
failures = logger.get_failure_cases()
rules_seen = set()
for f in failures:
    rules_seen.add(f.get("stopping_rule", "unknown"))
print(f"Stopping rules triggered: {rules_seen}")
print(f"Total failure cases: {len(failures)}")
