import os, sys, traceback
sys.path.insert(0, os.getcwd())
from database_manager import DatabaseManager

db_path = os.path.join(os.getcwd(), 'data', 'spareparts_pro.db')
db = DatabaseManager(db_path)

# Let's see what happens when we try to call receive_po_item
# We need a line_item_id that exists. Let's find one.
conn = db.get_connection()
row = conn.execute("SELECT id, po_id, part_id FROM po_items LIMIT 1").fetchone()
conn.close()

if not row:
    print("No PO items found to test with.")
else:
    line_item_id, po_id, part_id = row
    print(f"Testing receive_po_item for line_item_id={line_item_id}, part_id={part_id}")
    success, msg = db.receive_po_item(line_item_id, 1, 100.0, part_id)
    print(f"Result: success={success}, msg={msg}")
