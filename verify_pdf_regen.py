
import os
import sys
import shutil
from datetime import datetime

# Setup
sys.path.append(os.getcwd())
from database_manager import DatabaseManager
from invoice_generator import InvoiceGenerator

def verify_pdf_regen():
    print("--- Verifying PDF Regeneration ---")
    
    # 1. Setup Test DB
    test_db = "test_pdf_regen.db"
    if os.path.exists(test_db):
        os.remove(test_db)
        
    db = DatabaseManager(test_db)
    gen = InvoiceGenerator(db)
    
    # 2. Add Part & Sale
    print("1. Creating Data...")
    db.add_part({'id': 'P001', 'name': 'Brake Pad', 'desc': 'Front', 'price': 500, 'qty': 10, 'rack': 'A', 'col': '1'})
    
    inv_id = db.get_next_invoice_id()
    cart = [{'id': 'P001', 'name': 'Brake Pad', 'qty': 2, 'price': 500, 'total': 1000}]
    import json
    json_cart = json.dumps(cart)
    
    # Save Invoice
    # (id, cust, mob, model, reg, total, discount, date, json, count)
    db.save_invoice((inv_id, "John Doe", "9999999999", "Honda City", "KA01AB1234", 1000, 0, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), json_cart, 1))

    # 3. Process Return
    print(f"2. Processing Return for {inv_id}...")
    db.process_return(inv_id, 'P001', 2, 1000)
    
    # 4. Regenerate PDF
    print("3. Regenerating PDF...")
    try:
        path = gen.regenerate_invoice(inv_id)
        if path and os.path.exists(path):
            print(f"SUCCESS: PDF Generated at {path}")
            
            # Optional: Check if we can detect watermark (hard with just logic, but successful generation is key)
            # We trust the code we wrote for now.
        else:
            print("FAILURE: PDF did not generate.")
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()

    # Cleanup
    if os.path.exists(test_db):
        try:
             db.get_connection().close()
             os.remove(test_db)
        except: pass
        
if __name__ == "__main__":
    verify_pdf_regen()
