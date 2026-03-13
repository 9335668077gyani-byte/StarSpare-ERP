import sqlite3
import sys
import os

# Ensure we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database_manager import DatabaseManager

def test_po_vendor():
    db = DatabaseManager('data/spareparts_pro.db')
    conn = sqlite3.connect('data/spareparts_pro.db')
    cursor = conn.cursor()

    # Get a PO to test with
    cursor.execute("SELECT po_id, supplier_name FROM purchase_orders LIMIT 1")
    po = cursor.fetchone()
    if not po:
        print("No POs found.")
        return

    po_id, supplier_name = po

    # Create a dummy po_item
    cursor.execute("INSERT INTO po_items (po_id, part_id, part_name, qty_ordered, qty_received, ordered_price, hsn_code, gst_rate) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                   (po_id, 'TEST_VEND_01', 'Test Vendor Part', 10, 0, 100.0, '1234', 18.0))
    item_id = cursor.lastrowid
    conn.commit()

    # Call the receive function
    success, msg = db.receive_po_item(item_id, 10, 100.0, 'TEST_VEND_01')
    if not success:
        print(f"Failed to receive: {msg}")
        return

    # Verify the parts table
    cursor.execute("SELECT vendor_name, added_by FROM parts WHERE part_id = 'TEST_VEND_01'")
    part = cursor.fetchone()
    if not part:
        print("Part not created!")
        return

    vendor_name, added_by = part
    
    # Assertions
    if vendor_name != supplier_name:
        print(f"❌ FAIL: Vendor Name mismatch: expected {supplier_name}, got '{vendor_name}'")
    else:
        print(f"✅ PASS: Vendor Name correctly propagated: '{vendor_name}'")

    if added_by != "PO_SYSTEM":
        print(f"❌ FAIL: Added_By mismatch: got '{added_by}'")
    else:
        print(f"✅ PASS: Added_By correctly set: '{added_by}'")

    # Cleanup
    cursor.execute("DELETE FROM po_items WHERE id = ?", (item_id,))
    cursor.execute("DELETE FROM parts WHERE part_id = 'TEST_VEND_01'")
    conn.commit()
    conn.close()

if __name__ == '__main__':
    test_po_vendor()
