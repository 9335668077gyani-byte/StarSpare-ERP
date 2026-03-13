import sqlite3
import os

DB_PATH = 'data/spareparts_pro.db'

def fix_vendors():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all parts with empty or null vendor_name
    cursor.execute("SELECT part_id, vendor_name FROM parts WHERE vendor_name IS NULL OR TRIM(vendor_name) = ''")
    parts = cursor.fetchall()
    
    updates = 0
    for part in parts:
        part_id = part[0]
        
        # Try to find a PO item for this part
        cursor.execute('''
            SELECT po_id FROM po_items 
            WHERE part_id = ? OR part_name = ?
            ORDER BY id DESC LIMIT 1
        ''', (part_id, part_id))
        po_item = cursor.fetchone()
        
        if po_item:
            po_id = po_item[0]
            # Get supplier for this PO
            cursor.execute("SELECT supplier_name FROM purchase_orders WHERE po_id = ?", (po_id,))
            po = cursor.fetchone()
            
            if po and po[0]:
                supplier_name = po[0]
                # Update part's vendor_name
                cursor.execute("UPDATE parts SET vendor_name = ? WHERE part_id = ?", (supplier_name, part_id))
                updates += 1
                print(f"Updated part {part_id} with vendor {supplier_name}")
                
    conn.commit()
    conn.close()
    print(f"Fixed {updates} parts with missing vendors.")

if __name__ == '__main__':
    fix_vendors()
