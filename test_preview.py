import os
from database_manager import DatabaseManager
from invoice_generator import InvoiceGenerator

db_path = os.path.join("data", "spareparts_pro.db")
db = DatabaseManager(db_path)

gen = InvoiceGenerator(db)

theme = "Custom Color"
custom_color = "#00ff00"

formats = [
    "Modern", 
    "Classic", 
    "Compact", 
    "Detailed", 
    "TVS Standard"
]

for fmt in formats:
    print(f"\n--- Testing Format: {fmt} ---")
    try:
        pdf_path = gen.generate_preview_image(fmt, theme, custom_color)
        print("SUCCESS. Output:", pdf_path)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print("FAILED:", e)
