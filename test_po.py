import os
import sqlite3
from database_manager import DatabaseManager
from report_generator import ReportGenerator

def test():
    # Setup temporary db
    print("Setting up test DB...")
    db = DatabaseManager('test_erp.db')
    
    # 1. Add some parts
    print("Adding parts...")
    db.add_part({'id': 'PART-01', 'name': 'Engine Oil', 'desc': '', 'price': 500.0, 'qty': 10, 'rack': 'A1', 'col': '1', 'reorder': 5, 'vendor': 'V1'})
    
    # 2. Create a PO
    print("Creating PO...")
    items = [{
        'part_id': 'PART-01',
        'part_name': 'Engine Oil',
        'qty_ordered': 10,
        'price': 400.0,
        'hsn_code': '2710',
        'gst_rate': 18.0
    }]
    success, po_id = db.create_purchase_order('V1', items, 4000.0)
    print(f"PO Created: {po_id}")
    
    # Check initial status
    conn = db.get_connection()
    c = conn.cursor()
    c.execute("SELECT status FROM purchase_orders WHERE po_id=?", (po_id,))
    status = c.fetchone()[0]
    print(f"Initial PO Status: {status}")
    
    # 3. Receive 2 items
    print("Receiving 2 items...")
    # Need item ID.
    c.execute("SELECT id FROM po_items WHERE po_id=?", (po_id,))
    item_id = c.fetchone()[0]
    
    success, msg = db.receive_po_item(item_id, 2, 400.0, 'PART-01')
    print(f"Receive result: {success}, {msg}")
    
    c.execute("SELECT status FROM purchase_orders WHERE po_id=?", (po_id,))
    status = c.fetchone()[0]
    print(f"PO Status after receiving 2: {status}")
    
    # 4. Generate Single PO PDF
    print("Generating PDF...")
    po_header = {
        'To': 'V1',
        'PO Number': po_id,
        'Date': '2026-03-09',
        'Status': status
    }
    # get_po_items returns (id, part_id, part_name, qty_ordered, qty_received, ordered_price, hsn_code, gst_rate)
    po_items_data = db.get_po_items(po_id)
    
    rg = ReportGenerator(db)
    success, pdf_path = rg.generate_single_po_pdf(po_header, po_items_data)
    print(f"PDF Generated: {success}, {pdf_path}")
    
    print("Done")

if __name__ == "__main__":
    test()
