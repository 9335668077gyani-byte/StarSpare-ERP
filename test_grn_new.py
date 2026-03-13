import os, sys, traceback
sys.path.insert(0, os.getcwd())
from database_manager import DatabaseManager
import uuid

db_path = os.path.join(os.getcwd(), 'data', 'spareparts_pro.db')
db = DatabaseManager(db_path)

# Let's see what happens when we try to call receive_po_item for a NEW part
conn = db.get_connection()
cursor = conn.cursor()

po_id = 9999
cursor.execute("INSERT OR IGNORE INTO purchase_orders (po_id, supplier_name, order_date, status) VALUES (?, ?, '2026-02-27', 'OPEN')", (str(po_id), 'TEST VENDOR'))

# 2. Add a dummy PO item with a part_id that DOES NOT exist in parts
fake_part_id = "NEW_PART_" + str(uuid.uuid4())[:8]
cursor.execute("INSERT INTO po_items (po_id, part_id, part_name, qty_ordered, qty_received, received_cost) VALUES (?, ?, ?, ?, ?, ?)",
               (po_id, fake_part_id, "Test Fake Part", 10, 0, 0.0))
conn.commit()
line_item_id = cursor.lastrowid
conn.close()

print(f"Testing receive_po_item for NEW part... line_item_id={line_item_id}, part_id={fake_part_id}")
success, msg = db.receive_po_item(line_item_id, 5, 250.0, fake_part_id)
print(f"Result: success={success}, msg={msg}")
