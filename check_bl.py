import sqlite3
import shutil
import sys
import time

def check():
    try:
        shutil.copy2('data/spareparts_pro.db', 'data/spareparts_pro_copy.db')
    except Exception as e:
        print("Copy failed:", e)
        sys.exit(1)
        
    conn = sqlite3.connect('data/spareparts_pro_copy.db')
    c = conn.cursor()
    c.execute("""
        SELECT i.id, p.po_id, i.qty_ordered, i.qty_received, 
               (i.qty_ordered - i.qty_received) as pending, p.status, p.order_date
        FROM purchase_orders p
        JOIN po_items i ON p.po_id = i.po_id
    """)
    rows = c.fetchall()
    print("Total items:", len(rows))
    
    pending = [r for r in rows if r[5] in ('OPEN', 'PARTIAL') and r[4] > 0]
    print("Pending logic match in python:", len(pending), pending)
    
    c.execute("""
        SELECT i.id, p.po_id, p.supplier_name, i.part_name, i.qty_ordered, i.qty_received, 
               (i.qty_ordered - i.qty_received) as pending, i.part_id, i.hsn_code, i.gst_rate,
               p.order_date
        FROM purchase_orders p
        JOIN po_items i ON p.po_id = i.po_id
        WHERE p.status IN ('OPEN', 'PARTIAL') AND (i.qty_ordered - i.qty_received) > 0
        ORDER BY p.order_date ASC
    """)
    sql_pending = c.fetchall()
    print("Pending logic match in SQL:", len(sql_pending))
    for r in sql_pending:
        print(f"Row length: {len(r)}")
        print(f"Row: {r}")
        
if __name__ == '__main__':
    check()
