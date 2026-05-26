"""
Update Firestore platform_reports documents: redirect bq_destiny to canonical RAW table names.
Run ONCE, coordinated with Shiro. ETL will write to new tables on next execution.
"""
import firebase_admin
from firebase_admin import credentials, firestore

RENAMES = {
    "raw.mediasmart_daily":           "raw.mediasmart_delivery",
    "raw.mediasmart_revenue_daily":   "raw.mediasmart_revenue",
    "raw.mediasmart_bid_supply_daily":"raw.mediasmart_bid_supply",
    "raw.mgid_daily":                 "raw.mgid_delivery",
    "raw.siprocal_daily_materialized":"raw.siprocal_delivery",
}

app = firebase_admin.initialize_app(options={"projectId": "adframework"})
db = firestore.client()

docs = db.collection("platform_reports").stream()

updated = []
skipped = []

for doc in docs:
    data = doc.to_dict()
    old_dest = data.get("bq_destiny", "")
    if old_dest in RENAMES:
        new_dest = RENAMES[old_dest]
        doc.reference.update({"bq_destiny": new_dest})
        updated.append(f"  {doc.id}: {old_dest} -> {new_dest}")
    else:
        skipped.append(f"  {doc.id}: bq_destiny={old_dest!r} (unchanged)")

print("=== UPDATED ===")
print("\n".join(updated) if updated else "  (none)")
print(f"\n=== SKIPPED / NO CHANGE ({len(skipped)}) ===")
print("\n".join(skipped) if skipped else "  (none)")
print(f"\nDone. {len(updated)} docs updated.")
