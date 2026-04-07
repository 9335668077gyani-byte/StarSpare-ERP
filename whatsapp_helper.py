import webbrowser
import urllib.parse
import re

def send_invoice_msg(mobile, customer_name, invoice_id, amount, pdf_path, shop_name="SpareParts Pro", due_amount=0.0):
    """
    Opens WhatsApp Web DIRECTLY (bypassing landing page).
    Uses web.whatsapp.com/send
    """
    if not mobile:
        return False, "Mobile number missing"

    # 1. Sanitize Mobile
    # Remove all non-digits
    clean_mobile = re.sub(r'\D', '', str(mobile))
    
    # Remove leading '0' or '+' if present (though \D removed +, 0 might remain)
    if clean_mobile.startswith('0'):
        clean_mobile = clean_mobile.lstrip('0')
    
    # Prefix 91 if length is 10
    if len(clean_mobile) == 10:
        clean_mobile = "91" + clean_mobile
    
    # 2. Prepare Name (Title Case)
    clean_name = customer_name.strip().title() if customer_name and customer_name.strip() else "Customer"
    
    # 3. Message Template (Requested Format with Capitalized Greeting)
    amount_float = float(amount) if amount else 0.0
    due_float = float(due_amount) if due_amount else 0.0
    
    message = (
        f"NAMASTE {clean_name}! 🙏\n\n"
        f"Thank you for visiting {shop_name}! 🙏\n\n"
        f"📄 Your Invoice: {invoice_id}\n"
        f"💰 Total Amount: Rs. {amount_float:,.2f}\n"
    )
    
    if due_float > 0:
        message += (
            f"⚠️ Pending Due: Rs. {due_float:,.2f}\n\n"
            f"A gentle reminder regarding your pending balance. We kindly request you to clear the dues at your earliest convenience.\n\n"
        )
    else:
        message += "\n"

    message += (
        f"Please find the bill attached below.\n"
        f"Visit Again!"
    )
    
    # 4. Encode and Launch Direct URL
    try:
        encoded_msg = urllib.parse.quote(message)
        # Use web.whatsapp.com/send for direct chat bypass
        url = f"https://web.whatsapp.com/send?phone={clean_mobile}&text={encoded_msg}"
        webbrowser.open(url)
        return True, "WhatsApp Web Triggered"
    except Exception as e:
        return False, str(e)

def send_po_msg(mobile, vendor_name, po_id, shop_name="SpareParts Pro"):
    """
    Opens WhatsApp Web DIRECTLY (bypassing landing page) for a Purchase Order.
    Uses web.whatsapp.com/send
    """
    if not mobile:
        return False, "Mobile number missing"

    # 1. Sanitize Mobile
    clean_mobile = re.sub(r'\D', '', str(mobile))
    if clean_mobile.startswith('0'):
        clean_mobile = clean_mobile.lstrip('0')
    if len(clean_mobile) == 10:
        clean_mobile = "91" + clean_mobile
    
    # 2. Prepare Name
    clean_name = vendor_name.strip().title() if vendor_name and vendor_name.strip() else "Vendor"
    
    # 3. Message Template
    message = (
        f"NAMASTE {clean_name}! 🙏\n\n"
        f"This is an official Purchase Order from {shop_name}.\n\n"
        f"📦 PO Number: {po_id}\n\n"
        f"Please review the attached PDF for item details and quantities.\n"
        f"Thank You!"
    )
    
    # 4. Encode and Launch Direct URL
    try:
        encoded_msg = urllib.parse.quote(message)
        url = f"https://web.whatsapp.com/send?phone={clean_mobile}&text={encoded_msg}"
        webbrowser.open(url)
        return True, "WhatsApp Web Triggered"
    except Exception as e:
        return False, str(e)

def send_report_msg(report_name, shop_name="SpareParts Pro"):
    """
    Opens WhatsApp Web DIRECTLY without a predefined phone number.
    This allows the user to manually select a contact to share the report with.
    """
    message = (
        f"NAMASTE! 🙏\n\n"
        f"Here is the `{report_name}` from {shop_name}.\n\n"
        f"Please find the document attached below.\n"
        f"Thank You!"
    )
    
    try:
        encoded_msg = urllib.parse.quote(message)
        # Omit phone to let user choose!
        url = f"https://web.whatsapp.com/send?text={encoded_msg}"
        webbrowser.open(url)
        return True, "WhatsApp Web Triggered"
    except Exception as e:
        return False, str(e)
