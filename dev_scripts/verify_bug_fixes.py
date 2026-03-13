
import os
import json
from datetime import datetime, timedelta
from database_manager import DatabaseManager

# Setup DB path
DB_PATH = "data/spareparts_pro.db"
db = DatabaseManager(DB_PATH)

def test_vendor_name_matching():
    print("\n--- Testing Vendor Name Matching ---")
    vendor_clean = "Alpha Spares"
    vendor_messy = "  ALPHA spares  "
    
    # Create a PO with clean name
    items = [{"part_id": "P1", "part_name": "Test Part", "qty_ordered": 5}]
    db.create_purchase_order(vendor_clean, items, total_amount=500.0)
    
    # Search with messy name
    start = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    end = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    results = db.search_vendor_history(vendor_messy, start, end)
    
    found = any(vendor_clean in str(r) or vendor_messy.strip().upper() in str(r).upper() for r in results)
    if results:
        print(f"SUCCESS: Found {len(results)} orders using messy name '{vendor_messy}'")
    else:
        print(f"FAILED: No orders found for '{vendor_messy}'")

def test_date_range():
    print("\n--- Testing Date Range (365 Days) ---")
    vendor = "Alpha Spares"
    # Create a PO 200 days ago
    past_date = (datetime.now() - timedelta(days=200)).strftime("%Y-%m-%d %H:%M:%S")
    po_id = f"PO-PAST-{int(datetime.now().timestamp())}"
    
    conn = db.get_connection()
    conn.execute("INSERT INTO purchase_orders (po_id, supplier_name, order_date, status) VALUES (?, ?, ?, ?)",
                 (po_id, vendor, past_date, "OPEN"))
    conn.commit()
    conn.close()
    
    # Search with 365 day range (default in UI now)
    start = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    end = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    
    results = db.search_vendor_history(vendor, start, end)
    found = any(po_id in str(r) for r in results)
    
    if found:
        print(f"SUCCESS: Found PO from 200 days ago within 365-day range.")
    else:
        print(f"FAILED: PO from 200 days ago not found.")

def test_sales_export_logic():
    print("\n--- Testing Sales Export Logic (Simulation) ---")
    
    # Mock data as returned by db.get_sales_report
    # (date, invoice_id, customer, items_count, total_amount, json_items, invoice_id)
    cart_data = {
        "cart": [
            {"name": "GENERAL SERVICE", "qty": 1, "total": 450.0},
            {"name": "Engine Oil", "qty": 1, "total": 350.0},
            {"name": "LABOUR CHARGE", "qty": 1, "total": 150.0}
        ]
    }
    
    mock_row = (
        "2026-02-14", "INV-TEST-001", "Test Customer", 
        0, 950.0, json.dumps(cart_data), "INV-TEST-001"
    )
    
    # Simulated logic from ReportsPage.export_to_excel
    r = mock_row
    json_str = r[5]
    items_cnt = r[3]
    labour_charge = 0.0
    
    try:
        items_data = json.loads(json_str)
        cart = items_data.get('cart', []) if isinstance(items_data, dict) else items_data
        
        calc_cnt = sum(item.get('qty', 0) for item in cart)
        if items_cnt == 0:
            items_cnt = calc_cnt
            
        for x in cart:
            nm = str(x.get('name', '')).upper()
            if "SERVICE" in nm or "LABOUR" in nm:
                labour_charge += x.get('total', 0.0)
    except Exception as e:
        print(f"Error in logic: {e}")

    print(f"Result -> Items Count: {items_cnt} (Expected: 3)")
    print(f"Result -> Labour Charge: {labour_charge} (Expected: 600.0)")
    
    if items_cnt == 3 and labour_charge == 600.0:
        print("SUCCESS: Export logic correctly recalculated counts and labor charges.")
    else:
        print("FAILED: Export logic mismatch.")

if __name__ == "__main__":
    test_vendor_name_matching()
    test_date_range()
    test_sales_export_logic()
