import sqlite3
from database_manager import DatabaseManager
import os

# Setup a temporary DB for testing or use existing if safe
DB_PATH = "spareparts.db"
if not os.path.exists(DB_PATH):
    print(f"DB not found at {DB_PATH}, creating dummy...")
    DB_PATH = "test_verify_supplier_v2.db"

db = DatabaseManager(DB_PATH)

print("\n--- Testing get_vendor_stats (Execution Rate) ---")
# Ensure we have some PO items with ordered/received
# Just using whatever is there
stats = db.get_vendor_stats("TestVendor_X")
print(f"Stats: {stats}")
assert 'execution_rate' in stats
print(f"Execution Rate: {stats['execution_rate']}%")

print("\n--- Testing get_part_price_history ---")
# Need a part ID that exists. 
# Let's try to find one from the vendor
parts = db.get_parts_by_vendor("TestVendor_X")
if parts:
    pid = parts[0][0]
    print(f"Checking history for Part {pid}")
    history = db.get_part_price_history(pid, "TestVendor_X")
    print(f"Price History: {history}")
else:
    print("No parts found for TestVendor_X to test history.")

print("\n--- Testing search_vendor_history ---")
# Test date filter
res = db.search_vendor_history("TestVendor_X", start_date="2020-01-01", end_date="2030-01-01")
print(f"Found {len(res)} POs in date range")

# Test PO Search
if res:
    target_po = res[0][0]
    print(f"Searching for PO ID: {target_po}")
    res_po = db.search_vendor_history("TestVendor_X", po_id_search=target_po)
    print(f"Found {len(res_po)} matches")
    assert len(res_po) > 0
    assert res_po[0][0] == target_po

print("\n✅ Verification v2 Successful!")
