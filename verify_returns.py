import sys
import os
import sqlite3
import json
from datetime import datetime

# Setup paths
base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(base_dir)

from database_manager import DatabaseManager

def test_returns():
    print("🚀 Starting Sales Return Verification...")
    
    # 1. Setup DB
    db_path = os.path.join(base_dir, "data", "spareparts_pro.db")
    db = DatabaseManager(db_path)
    
    # 2. Add a Test Part
    part_id = "TEST-PART-999"
    print(f"Adding test part: {part_id}")
    
    conn = db.get_connection()
    conn.execute("INSERT OR REPLACE INTO parts (part_id, part_name, qty, unit_price) VALUES (?, ?, ?, ?)", 
                 (part_id, "Test Widget", 50, 100.0))
    conn.commit()
    conn.close()
    
    # 3. Simulate a Sale -> Qty should drop to 40
    print("Simulating Sale of 10 units...")
    invoice_id = "INV-TEST-001"
    
    # Manually decrease stock and add to sales to simulate 'billing_page' logic
    # In real app, billing page does this.
    
    # a. Create Invoice
    cart = [{'id': part_id, 'name': "Test Widget", 'qty': 10, 'price': 100.0, 'total': 1000.0}]
    json_items = json.dumps(cart)
    
    conn = db.get_connection()
    conn.execute("INSERT OR REPLACE INTO invoices (invoice_id, customer_name, total_amount, date, json_items) VALUES (?, ?, ?, ?, ?)", 
                 (invoice_id, "Tester", 1000.0, datetime.now().strftime("%Y-%m-%d"), json_items))
    
    # b. Update Part Stock (50 -> 40)
    conn.execute("UPDATE parts SET qty = 40 WHERE part_id = ?", (part_id,))
    
    # c. Add to Sales
    conn.execute("INSERT INTO sales (invoice_id, part_id, quantity, price_at_sale, sale_date) VALUES (?, ?, ?, ?, ?)",
                 (invoice_id, part_id, 10, 100.0, datetime.now().strftime("%Y-%m-%d")))
    conn.commit()
    conn.close()
    
    # Verify Stock is 40
    row = db.get_part_by_id(part_id)
    print(f"Stock after sale (Should be 40): {row[4]}")
    if row[4] != 40:
        print("❌ Stock Mismatch after sale!")
        return

    # 4. Process Return of 3 units -> Stock should be 43
    print("Processing Return of 3 units...")
    success, msg = db.process_return(invoice_id, part_id, 3, 300.0, "Defective")
    
    if success:
        print("✅ Return processed successfully via DB Manager.")
    else:
        print(f"❌ Return failed: {msg}")
        return

    # 5. Verify Final Stock
    row = db.get_part_by_id(part_id)
    print(f"Final Stock (Should be 43): {row[4]}")
    
    if row[4] == 43:
        print("✅ SUCCESS: Stock restored correctly!")
    else:
        print(f"❌ FAILURE: Stock is {row[4]}, expected 43.")
        
    # 6. Verify Return Record
    conn = db.get_connection()
    cursor = conn.execute("SELECT * FROM returns WHERE invoice_id = ?", (invoice_id,))
    ret_row = cursor.fetchone()
    conn.close()
    
    if ret_row:
        print(f"✅ Return Record Found: {ret_row}")
    else:
        print("❌ Return Record NOT Found in table.")

    # Cleanup
    print("Cleaning up test data...")
    conn = db.get_connection()
    conn.execute("DELETE FROM parts WHERE part_id = ?", (part_id,))
    conn.execute("DELETE FROM invoices WHERE invoice_id = ?", (invoice_id,))
    conn.execute("DELETE FROM sales WHERE invoice_id = ?", (invoice_id,))
    conn.execute("DELETE FROM returns WHERE invoice_id = ?", (invoice_id,))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    test_returns()
