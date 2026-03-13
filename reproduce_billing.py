
import json

class MockWidget:
    def __init__(self, text="0"):
        self._text = text
    def text(self):
        return self._text
    def setText(self, t):
        self._text = t
    def strip(self):
        return self._text.strip()

def calculate_totals_logic(cart_items, discount_text):
    sub_total = sum(item['total'] for item in cart_items)
    
    try:
        txt = discount_text.strip()
        perc = float(txt) if txt else 0.0
        if perc > 100: perc = 100
    except ValueError:
        perc = 0.0
        
    savings_amt = (sub_total * perc) / 100
    grand_total = sub_total - savings_amt
    if grand_total < 0: grand_total = 0
    
    return sub_total, savings_amt, grand_total

# Test Case 1: Single item, no discount
cart = [{'total': 175.42, 'price': 175.42, 'qty': 1}]
sub, disc, grand = calculate_totals_logic(cart, "0")
print(f"Test 1: Sub={sub}, Disc={disc}, Grand={grand}")

# Test Case 2: 10% discount
sub, disc, grand = calculate_totals_logic(cart, "10")
print(f"Test 2: Sub={sub}, Disc={disc}, Grand={grand}")

# Test Case 3: Item-level discount
cart_discounted = [{'total': 157.88, 'price': 157.88, 'qty': 1}] # 10% off 175.42 approx
sub, disc, grand = calculate_totals_logic(cart_discounted, "0")
print(f"Test 3 (Item Disc): Sub={sub}, Disc={disc}, Grand={grand}")

# Simulation of PDF rendering (Mock)
def mock_pdf_render(sub_total, discount, grand_total, gst_rate=18):
    taxable = sub_total - discount
    gst = taxable * gst_rate / 100.0
    print(f"PDF Render -> SubTotal: {sub_total}, Discount: {discount}, GST: {gst}, DISPLAYED GrandTotal: {grand_total}")
    print(f"Wait... SHOULD GrandTotal be {taxable + gst}?")

print("\nPDF Simulation:")
mock_pdf_render(sub, disc, grand)
