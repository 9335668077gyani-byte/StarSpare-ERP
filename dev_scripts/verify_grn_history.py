import sqlite3
from database_manager import DatabaseManager
import os
import time

DB_PATH = "spareparts.db"
if not os.path.exists(DB_PATH):
    print("WARNING: spareparts.db not found, using test DB")
    DB_PATH = "test_verify_grn.db"
    
print(f"Using DB: {DB_PATH}")
db = DatabaseManager(DB_PATH)

# 1. Create Part & PO
ts = int(time.time())
v_name = f"Vendor_{ts}"
db.add_vendor(v_name, "Rep", "Phone", "Addr", "GST", "Notes")

part_id = f"GRN_TEST_{ts}"
db.add_part({'id': part_id, 'name': 'GRN Test Part', 'desc':'', 'price':100, 'qty':0, 'rack':'', 'col':'', 'vendor':v_name})

print(f"Creating PO for {part_id}...")
res, po_id = db.create_purchase_order(v_name, [{'part_id': part_id, 'part_name': 'GRN Test Part', 'qty_ordered': 10}])
print(f"PO Created: {po_id}")

# 2. Receive Partial
print("Receiving 5 items...")
# Get line item id
conn = db.get_connection()
c = conn.cursor()
c.execute("SELECT id FROM po_items WHERE po_id=?", (po_id,))
line_id = c.fetchone()[0]
conn.close()

success, msg = db.receive_po_item(line_id, 5, 105.0, part_id) # 5 @ 105
print(f"Receive Result: {success} - {msg}")
assert success

# 3. VERIFY HISTORY DATA
# This uses the EXACT query from get_po_items which feeds the History Detail table
print("Fetching PO Items (History View)...")
items = db.get_po_items(po_id)
# Row: part_id, part_name, qty_ordered, qty_received, pending, received_cost, total_cost
row = items[0]
print(f"History Row: {row}")

# Checks
# Received should be 5
if row[3] != 5:
    print(f"❌ FAIL: Received Qty mismatch. Expected 5, Got {row[3]}")
else:
    print("✅ Received Qty Verified")

# Pending should be 5
if row[4] != 5:
    print(f"❌ FAIL: Pending Qty mismatch. Expected 5, Got {row[4]}")
else:
    print("✅ Pending Qty Verified")

# Cost should be 105.0
if row[5] != 105.0:
    print(f"❌ FAIL: Unit Cost mismatch. Expected 105.0, Got {row[5]}")
else:
    print("✅ Unit Cost Verified")

# Total Cost should be 5 * 105 = 525.0
expected_total = 5 * 105.0
if abs(row[6] - expected_total) > 0.01:
    print(f"❌ FAIL: Total Cost mismatch. Expected {expected_total}, Got {row[6]}")
else:
    print("✅ Total Cost Verified")

# 4. Verify Master List Status
print("Fetching Master List...")
orders = db.get_all_purchase_orders()
my_order = next((o for o in orders if o[0] == po_id), None)
print(f"Master Row: {my_order}")
# Status should be PARTIAL
if my_order[3] != 'PARTIAL':
     print(f"❌ FAIL: PO Status mismatch. Expected PARTIAL, Got {my_order[3]}")
else:
    print("✅ PO Status Verified")
