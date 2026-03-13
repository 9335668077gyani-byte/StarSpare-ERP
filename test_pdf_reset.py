import sys
import os

# Ensure we are in the right directory
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from database_manager import DatabaseManager
from invoice_generator import InvoiceGenerator

db = DatabaseManager('data/spareparts_pro.db')
ig = InvoiceGenerator(db)

meta = {
    'invoice_id': 'TEST-INV-001',
    'customer_name': 'Test Customer',
    'customer_phone': '9876543210',
    'customer_address': '123 Test Street, Test City',
    'date': '2026-02-27',
    'vehicle': 'Honda City',
    'reg_no': 'KA-01-AB-1234',
    'sub_total': 1000.0,
    'discount': 50.0,
    'total': 950.0
}

items = [
    {
        'part_id': 'PART-001',
        'part_name': 'Test Part 1 with a very long description that should auto wrap properly now',
        'qty': 2,
        'price': 250.0,
        'tax_perc': 18.0,
        'hsn': '1234',
        'total': 500.0
    },
    {
        'part_id': 'PART-002',
        'part_name': 'Test Part 2',
        'qty': 1,
        'price': 500.0,
        'tax_perc': 18.0,
        'hsn': '5678',
        'total': 500.0
    }
]

print("Generating Test PDF...")
try:
    path = ig.generate_invoice_pdf(meta, items)
    print(f"Success! PDF generated at: {path}")
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"Error generating PDF: {e}")
