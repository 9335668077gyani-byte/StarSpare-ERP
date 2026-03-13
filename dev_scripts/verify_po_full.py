import sqlite3
from database_manager import DatabaseManager
import os
import time

# Use the real DB to check against user's schema state
DB_PATH = "spareparts.db"
if not os.path.exists(DB_PATH):
    print("WARNING: spareparts.db not found, using test DB")
    DB_PATH = "test_verify_full.db"
    if os.path.exists(DB_PATH): os.remove(DB_PATH)

print(f"Using DB: {DB_PATH}")
db = DatabaseManager(DB_PATH)

# 1. Verify Vendor Schema
print("\n--- 1. Checking Vendor Schema ---")
conn = db.get_connection()
cursor = conn.execute("PRAGMA table_info(vendors)")
cols = [c[1] for c in cursor.fetchall()]
print(f"Vendor Columns: {cols}")
conn.close()

assert "rep_name" in cols, "Missing rep_name column"
assert "gstin" in cols, "Missing gstin column"
assert "notes" in cols, "Missing notes column"

# 2. Test Add Vendor
print("\n--- 2. Testing Add Vendor ---")
v_name = f"Test_Vendor_{int(time.time())}"
v_rep = "Suresh Kumar"
v_phone = "9876543210"
v_addr = "123 Indiranagar, Bangalore"
v_gstin = "29ABCDE1234F1Z5"
v_notes = "Very reliable supplier"

success, msg = db.add_vendor(v_name, v_rep, v_phone, v_addr, v_gstin, v_notes)
print(f"Add Result: {success} - {msg}")
assert success

# 3. Test Retrieve Vendor
print("\n--- 3. Testing Retrieve Vendor ---")
vendors = db.get_all_vendors()
target_v = None
for v in vendors:
    if v[1] == v_name:
        target_v = v
        break

print(f"Retrieved Vendor Row: {target_v}")
assert target_v is not None
# Indices: 0:id, 1:name, 2:rep, 3:phone, 4:addr, 5:gstin, 6:notes
# NOTE: Check indices based on schema order found in step 1 if inconsistent
# But DatabaseManager.create_tables defines the order.

# Let's verify by name since order might vary if migrated
# We can fetch as dict to be safe if we had a dict method, but we don't.
# We'll trust the indices match the create_table order if schema is correct.
print(f"Checking Rep: Expected '{v_rep}', Got '{target_v[2]}'")
assert target_v[2] == v_rep
print(f"Checking GSTIN: Expected '{v_gstin}', Got '{target_v[5]}'")
assert target_v[5] == v_gstin
print(f"Checking Notes: Expected '{v_notes}', Got '{target_v[6]}'")
assert target_v[6] == v_notes

# 4. Test PO Workflow
print("\n--- 4. Testing PO Creation ---")
# Need a part
db.add_part({'id': 'TEST-PART-FULL-1', 'name': 'Full Test Part', 'desc': '', 'price': 100, 'qty': 0, 'rack': '', 'col': '', 'vendor': v_name})
success, msg = db.create_purchase_order(v_name, [{'part_id': 'TEST-PART-FULL-1', 'part_name': 'Full Test Part', 'qty_ordered': 10}])
print(f"Create PO: {success} - {msg}")

# Get PO ID
pos = db.get_recent_pos_by_vendor(v_name, 1)
po_id = pos[0][0]
print(f"Created PO ID: {po_id}")

# 5. Test Receiving (Partial)
print("\n--- 5. Testing Receiving ---")
# Need to get line_item_id
conn = db.get_connection()
c = conn.cursor()
c.execute("SELECT id FROM po_items WHERE po_id = ? AND part_id = ?", (po_id, 'TEST-PART-FULL-1'))
line_id = c.fetchone()[0]
conn.close()

success, msg = db.receive_po_item(line_id, 5, 90.0, 'TEST-PART-FULL-1') # Receive 5 @ 90
print(f"Receive Result: {success} - {msg}")
assert success

# 6. Test Stats
print("\n--- 6. Testing Supplier Stats ---")
stats = db.get_vendor_stats(v_name)
print(f"Stats: {stats}")
# Ordered 10, Received 5. Execution Rate should be 50%
assert stats['execution_rate'] == 50.0
# Spend: 5 * 90 = 450
assert stats['total_spend'] == 450.0

print("\n✅ Full Logic Verification Successful!")
