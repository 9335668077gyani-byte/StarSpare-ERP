import sqlite3
from database_manager import DatabaseManager
import os
import time

DB_PATH = "spareparts.db"
# Use main DB to verify against real data structure if possible, or test db
if not os.path.exists(DB_PATH):
    DB_PATH = "test_verify_partial.db"

print(f"Using DB: {DB_PATH}")
db = DatabaseManager(DB_PATH)

# Clean slate if test db
if "test_" in DB_PATH:
    if os.path.exists(DB_PATH): os.remove(DB_PATH)
    db = DatabaseManager(DB_PATH)
    db.create_tables()

# 1. Setup Data
ts = int(time.time())
v_name = f"Partial_Vendor_{ts}"
db.add_vendor(v_name, "Rep", "Phone", "Addr", "GST", "Notes")

p1 = f"P1_{ts}"
p2 = f"P2_{ts}"
db.add_part({'id': p1, 'name': 'Part 1', 'desc':'', 'price':100, 'qty':0, 'rack':'', 'col':'', 'vendor':v_name})
db.add_part({'id': p2, 'name': 'Part 2', 'desc':'', 'price':200, 'qty':0, 'rack':'', 'col':'', 'vendor':v_name})

# 2. Create PO
items = [
    {'part_id': p1, 'part_name': 'Part 1', 'qty_ordered': 10},
    {'part_id': p2, 'part_name': 'Part 2', 'qty_ordered': 5}
]
res, po_id = db.create_purchase_order(v_name, items)
print(f"Created PO: {po_id}")

# 3. Partial Receive P1 (5/10)
print("Receiving P1 (5/10)...")
conn = db.get_connection()
c = conn.cursor()
c.execute("SELECT id FROM po_items WHERE po_id=? AND part_id=?", (po_id, p1))
line_id_1 = c.fetchone()[0]
conn.close()
db.receive_po_item(line_id_1, 5, 100.0, p1)

# 4. Check Status (Should be OPEN or PARTIAL? Logic says PARTIAL once a receive happens?)
# The receive_po_item logic updates to PARTIAL if pending > 0.
# It checks: SELECT COUNT(*) FROM po_items WHERE po_id = ? AND qty_received < qty_ordered
# P1: 5 < 10 (True)
# P2: 0 < 5 (True)
# Count = 2. So Status -> PARTIAL.

# 5. Fetch History Master
print("Fetching History Master...")
orders = db.get_all_purchase_orders()
my_po = next((o for o in orders if o[0] == po_id), None)
print(f"Master Row: {my_po}")
# Row: po_id, supplier, date, status, item_count, total_qty
assert my_po[3] == 'PARTIAL', f"Expected PARTIAL, got {my_po[3]}"

# 6. Fetch History Details
print("Fetching History Details...")
details = db.get_po_items(po_id)
# Row: part_id, part_name, qty_ordered, qty_received, pending, received_cost, total_cost
for row in details:
    print(f"Detail: {row}")
    if row[0] == p1:
        # Check P1
        assert row[3] == 5, "P1 Received incorrect"
        assert row[4] == 5, "P1 Pending incorrect"
        assert row[6] == 500.0, "P1 Total Cost incorrect"
    elif row[0] == p2:
        # Check P2
        assert row[3] == 0, "P2 Received incorrect"
        assert row[4] == 5, "P2 Pending incorrect"
        assert row[6] == 0.0, "P2 Total Cost incorrect"

print("✅ Logic Correct")
