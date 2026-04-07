"""
Dev script: Inspect raw TVS API response for painted models (MOTORCYCLE).
Run from the spare_ERP directory: python dev_scripts/inspect_painted_models.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api_sync_engine import TVSApiClient, _force_dict, _safe_str

DEALER_ID = "63735"
VEHICLE_TYPE = "MOTORCYCLE"

client = TVSApiClient(DEALER_ID)
client.connect()

result = client.get_painted_models_with_colors(vehicle_type=VEHICLE_TYPE)

model_entries = result.get("models", [])
color_entries = result.get("colors", [])

print(f"\n=== innerDate (model_entries): {len(model_entries)} items ===")
for i, m in enumerate(model_entries[:5]):
    print(f"  [{i}] keys: {list(m.keys())}")
    print(f"       raw: {json.dumps(m, indent=10)[:300]}")

print(f"\n=== imageData (color_entries): {len(color_entries)} items ===")
for i, c in enumerate(color_entries[:5]):
    print(f"  [{i}] keys: {list(c.keys())}")
    print(f"       raw: {json.dumps(c, indent=10)[:300]}")

# Show unique ModelIDs in color_entries vs model_entries
color_model_ids = set(_safe_str(e.get("ModelID") or "") for e in color_entries)
inner_model_ids = set(_safe_str(m.get("ModelID") or "") for m in model_entries)

print(f"\n=== ModelID overlap ===")
print(f"  Color entries ModelIDs (sample): {list(color_model_ids)[:10]}")
print(f"  Inner entries ModelIDs (sample): {list(inner_model_ids)[:10]}")
print(f"  Matching IDs: {color_model_ids & inner_model_ids}")
