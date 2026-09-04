"""Full batch re-run checking all mandate stats."""
from orchestrator import run_batch, get_audit_logger
import json

result = run_batch()
logger = get_audit_logger()

print("MANDATE STATS:")
print(json.dumps(result["mandate_stats"], indent=2))

trail = logger.get_audit_trail()
print("\n=== ALL MANDATE AUDIT ENTRIES ===")
mandate_entries = [r for r in trail if r.get("is_mandate")]
for r in mandate_entries:
    print(f"  {r['risk_id']}: action={r['action']}, reasoning={r['reasoning'][:80]}")

print("\n=== CYCLE DEADLINE IN REASONING ===")
cycle = [r for r in trail if "cycle ends" in r.get("reasoning", "")]
print(f"Found {len(cycle)}")
for c in cycle:
    print(f"  {c['risk_id']}: {c['reasoning']}")
