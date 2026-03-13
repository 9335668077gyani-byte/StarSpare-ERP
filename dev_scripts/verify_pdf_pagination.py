import os
import datetime
from invoice_generator import InvoiceGenerator

# Mock Database Manager
class MockDB:
    def __init__(self, theme_name):
        self.theme_name = theme_name

    def get_shop_settings(self):
        return {
            "shop_name": "TEST MOTORS PAGINATION",
            "shop_address": "123 Test St, Sector 5\nIndustrial Area, Delhi",
            "shop_mobile": "9999999999",
            "shop_gstin": "07AAAAA0000A1Z5",
            "logo_path": "", 
            "invoice_theme": self.theme_name 
        }

def generate_theme_test():
    themes = ["Modern (Blue)", "Executive (Black/Gold)", "Minimal (B&W)"]
    
    # 50 Items to force multiple pages
    items = []
    sub_total = 0
    for i in range(1, 55):
        qty = 2
        rate = 1500.00
        total = qty * rate
        items.append([
            i, 
            f"PART-{1000+i}", 
            f"Test Part Description for Item {i}", 
            qty, 
            rate, 
            total
        ])
        sub_total += total

    for theme in themes:
        print(f"Generating for Theme: {theme}...")
        db = MockDB(theme)
        gen = InvoiceGenerator(db)
        
        safe_theme = theme.split(" ")[0].upper()
        inv_meta = {
            "invoice_id": f"TEST-{safe_theme}-PAGES",
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "customer": f"Mr. {safe_theme} Test",
            "mobile": "9876543210",
            "vehicle": "Test Vehicle X",
            "reg_no": "DL-01-TEST",
            "sub_total": sub_total,
            "discount": 0,
            "total": sub_total,
            "extra_details": {}
        }
        
        path = gen.generate_invoice_pdf(inv_meta, items)
        print(f"Generated: {path}")

    # Open the folder
    os.startfile(os.path.join(os.getcwd(), "invoices"))

if __name__ == "__main__":
    generate_theme_test()
