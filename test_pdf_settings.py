import os
from database_manager import DatabaseManager
from invoice_generator import InvoiceGenerator

db_path = os.path.join("data", "spareparts_pro.db")
db = DatabaseManager(db_path)

gen = InvoiceGenerator(db)
settings = db.get_shop_settings()
print(f"Current DB Settings:")
print(f"Format: {settings.get('invoice_format')}")
print(f"Theme: {settings.get('invoice_theme')}")
print(f"Custom Color: {settings.get('invoice_custom_color')}")
print(f"App Theme: {settings.get('app_theme')}")

meta = {
    'invoice_id': 'TEST-001', 'date': '01-Jan-2026', 'customer': 'Sample Customer',
    'mobile': '9876543210', 'vehicle': 'Brand Model', 'reg_no': 'UP14 1234',
    'sub_total': 1500.0, 'discount': 50.0, 'total': 1450.0,
    'extra_details': {}
}
items = [(1, 'P001', 'Test Item', 1.0, 450.0, 450.0, '8708', 18.0)]

try:
    pdf_path = gen.generate_invoice_pdf(meta, items)
    print("SUCCESS! PDF created at:", pdf_path)
except Exception as e:
    print("ERROR generating PDF:", e)
    import traceback
    traceback.print_exc()
