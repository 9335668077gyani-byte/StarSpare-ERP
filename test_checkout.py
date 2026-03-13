import os
from database_manager import DatabaseManager
from invoice_generator import InvoiceGenerator

db_path = os.path.join("data", "spareparts_pro.db")
db = DatabaseManager(db_path)
pdf_generator = InvoiceGenerator(db)

# Create accurate mock items with dictionaries instead of tuples
pdf_items = [
    # idx, sys_id, name, HSN, GST%, Disc%, Qty, Rate, Total
    [1, 'P001', 'Test Filter', '8714', 18.0, 0.0, 1.0, 359.00, 359.00]
]

inv_meta = {
    "invoice_id": "TEST-1043",
    "date": "2026-02-26 14:43",
    "customer": "Walk-in",
    "mobile": "",
    "vehicle": "",
    "reg_no": "",
    "sub_total": 359.0,
    "discount": 0.0,
    "total": 359.0,
    "extra_details": {}
}

pdf_path = pdf_generator.generate_invoice_pdf(inv_meta, pdf_items)
print(f"Generated test invoice: {pdf_path}")
