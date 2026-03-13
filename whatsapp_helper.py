import webbrowser
import urllib.parse
import re

def send_invoice_msg(mobile, customer_name, invoice_id, amount, pdf_path, shop_name="SpareParts Pro"):
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
    message = (
        f"NAMASTE {clean_name}! 🙏\n\n"
        f"Thank you for visiting {shop_name}! 🙏\n\n"
        f"📄 Your Invoice: {invoice_id}\n"
        f"💰 Total Amount: Rs. {amount}\n\n"
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
