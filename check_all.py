import sqlite3

def check_all():
    conn = sqlite3.connect('data/spareparts_pro_copy.db')
    c = conn.cursor()
    c.execute("""
        SELECT i.id, p.po_id, i.qty_ordered, i.qty_received, 
               (i.qty_ordered - i.qty_received) as pending, p.status, p.order_date
        FROM purchase_orders p
        JOIN po_items i ON p.po_id = i.po_id
    """)
    rows = c.fetchall()
    for row in rows:
        print(row)
        
if __name__ == '__main__':
    check_all()
