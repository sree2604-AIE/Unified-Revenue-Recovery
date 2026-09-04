"""Debug: trace what happens to the cycle-deadline edge case mandates."""
from data_generator import generate_all_data
from detectors.mandate_detector import detect_mandate_risks
from mandate_budget_optimizer import predict_optimal_retry_date, pick_mandate_action
from decision_engine import decide, register_opted_out, reset_state

reset_state()
data = generate_all_data()
customers = data["customers"]
opted_out_ids = {c.customer_id for c in customers if c.opted_out}
register_opted_out(opted_out_ids)

mandates = data["mandate_failures"]
print("=== RAW MANDATE EVENTS (indices 2,3,4 = cycle-deadline edge cases) ===")
for i, m in enumerate(mandates[:6]):
    print(f"\n[{i}] {m['event_id']}")
    print(f"  customer: {m['customer_id']}")
    print(f"  cause: {m['cause']}")
    print(f"  retries: {m['retries_used']}/{m['max_retries_allowed']} (remaining: {m['retries_remaining']})")
    print(f"  cycle_end: {m['mandate_cycle_end_date']}")
    print(f"  typical_day: {m['typical_debit_day']}")
    print(f"  debit_history: {m['debit_history']}")
    predicted = predict_optimal_retry_date(m['debit_history'])
    print(f"  predicted_optimal: {predicted}")
    if predicted and m['mandate_cycle_end_date']:
        print(f"  predicted > cycle_end? {predicted > m['mandate_cycle_end_date']}")

# Now detect and decide
risks = detect_mandate_risks(mandates)
print(f"\n=== DETECTED {len(risks)} mandate risks ===")
for r in risks[:6]:
    mc = r.context.get('mandate', {})
    print(f"\n{r.risk_id}:")
    print(f"  is_mandate: {r.context.get('is_mandate')}")
    print(f"  retries_remaining: {mc.get('retries_remaining')}")
    print(f"  predicted: {mc.get('predicted_optimal_retry_date')}")
    print(f"  cycle_end: {mc.get('mandate_cycle_end_date')}")
    
    # Check if opted out first
    if r.customer_id in opted_out_ids:
        print(f"  -> OPTED OUT, decision: no_action")
    else:
        action, reasoning = pick_mandate_action(r)
        print(f"  -> action: {action}")
        print(f"  -> reasoning: {reasoning}")
