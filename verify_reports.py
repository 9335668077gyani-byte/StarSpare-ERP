import sqlite3
import json
import os
from datetime import datetime
from database_manager import DatabaseManager
from report_generator import ReportGenerator

def test_flow():
    print("Setting up test database...")
    db = DatabaseManager('test_spare.db')
    
    # Clean up
    conn = db.get_connection()
    c = conn.cursor()
    c.executescript('''
        DELETE FROM sales;
        DELETE FROM invoices;
        DELETE FROM returns;
        DELETE FROM parts;
    ''')
    conn.commit()
    conn.close()

    print("Adding dummy part...")
    db.add_part('P01', 'Test Part', 'Test Cat', 100, 100, 150, 10, 'A1', 'R1', '1001')

    print("Simulating a sale (SPLIT Mode)...")
    # Simulate saving an invoice that mimics what BillingPage does
    cart_json = json.dumps({'cart': [{'sys_id': 'P01', 'name': 'Test Part', 'qty': 2, 'price': 150, 'total': 300}]})
    conn = db.get_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO invoices (invoice_id, customer_name, mobile, total_amount, json_items, date, 
                              payment_cash, payment_upi, payment_due, payment_mode)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', ('INV-TEST-01', 'John Doe', '12345', 300.0, cart_json, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
          100.0, 200.0, 0.0, 'SPLIT'))
    
    c.execute('''
        INSERT INTO sales (invoice_id, part_id, quantity, price_at_sale, sale_date, cogs)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', ('INV-TEST-01', 'P01', 2, 150.0, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 200.0))
    conn.commit()
    conn.close()

    print("Checking sales report...")
    sales = db.get_sales_report(datetime.now().strftime('%Y-%m-%d'), datetime.now().strftime('%Y-%m-%d'))
    print(f"Sales found: {len(sales)}")
    assert len(sales) == 1, "Should find 1 sale"
    s = sales[0]
    print(f"Invoice details: Mode={s[11]}, Cash={s[8]}, UPI={s[9]}")
    
    print("Simulating a partial return...")
    db.process_return('INV-TEST-01', [{'part_id': 'P01', 'qty': 1, 'refund_amount': 150.0}])

    print("Checking sales report after return...")
    sales_after = db.get_sales_report(datetime.now().strftime('%Y-%m-%d'), datetime.now().strftime('%Y-%m-%d'))
    s_after = sales_after[0]
    print(f"Returns count: {s_after[7]}, Refund total: {s_after[12]}, Original Amt: {s_after[4]}")
    assert s_after[12] == 150.0, "Refund should be 150.0"

    print("Generating comprehensive PDF report...")
    gen = ReportGenerator(db)
    # create dummy totals
    total_rev = s_after[4] - s_after[12]
    total_exp = 0.0
    total_cogs = 100.0
    total_net = total_rev - total_cogs
    d_from = datetime.now().strftime('%Y-%m-%d')
    success, path = gen.generate_comprehensive_report_pdf(sales_after, [], total_rev, total_exp, total_net, total_cogs, d_from, d_from)
    print(f"PDF generated: {success}, Path: {path}")

    print("ALL LOGICS AND DATA FLOWS OK!")

if __name__ == "__main__":
    try:
        test_flow()
    except Exception as e:
        import traceback
        traceback.print_exc()
