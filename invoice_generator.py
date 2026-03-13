from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
import os
from logger import app_logger

class InvoiceGenerator:
    def __init__(self, db_manager):
        self.db_manager = db_manager

    # ── Color Extraction ──────────────────────────────────────────────
    def _extract_logo_color(self, logo_path):
        """
        Extract the dominant non-white/non-black color from the logo image.
        Returns an (r, g, b) tuple normalized to 0-1 range for reportlab.
        Falls back to navy blue if extraction fails.
        """
        FALLBACK = (0.10, 0.31, 0.63)  # Navy blue
        try:
            from PIL import Image
            img = Image.open(logo_path).convert("RGB")
            # Resize for speed
            img = img.resize((80, 80))
            pixels = list(img.getdata())

            # Filter out near-white, near-black, and very gray pixels
            filtered = []
            for r, g, b in pixels:
                brightness = (r + g + b) / 3
                saturation = max(r, g, b) - min(r, g, b)
                if brightness < 240 and brightness > 30 and saturation > 40:
                    filtered.append((r, g, b))

            if not filtered:
                return FALLBACK

            # Average the remaining pixels to get dominant color
            avg_r = sum(p[0] for p in filtered) / len(filtered)
            avg_g = sum(p[1] for p in filtered) / len(filtered)
            avg_b = sum(p[2] for p in filtered) / len(filtered)

            # Make it slightly darker for readability on white paper
            darken = 0.8
            return (
                min(avg_r / 255 * darken, 1.0),
                min(avg_g / 255 * darken, 1.0),
                min(avg_b / 255 * darken, 1.0),
            )
        except Exception as e:
            app_logger.warning(f"Could not extract logo color: {e}")
            return FALLBACK

    # ── Amount in Words ───────────────────────────────────────────────
    @staticmethod
    def _amount_in_words(amount):
        """Convert a number to Indian English words (e.g., 1250 -> 'One Thousand Two Hundred Fifty')."""
        ones = [
            "", "One", "Two", "Three", "Four", "Five", "Six", "Seven",
            "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen",
            "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen",
        ]
        tens = [
            "", "", "Twenty", "Thirty", "Forty", "Fifty",
            "Sixty", "Seventy", "Eighty", "Ninety",
        ]

        def _two_digits(n):
            if n < 20:
                return ones[n]
            return (tens[n // 10] + " " + ones[n % 10]).strip()

        def _three_digits(n):
            if n >= 100:
                return ones[n // 100] + " Hundred " + _two_digits(n % 100)
            return _two_digits(n)

        num = int(round(amount))
        if num == 0:
            return "Zero"

        # Indian numbering: Crore, Lakh, Thousand, Hundred
        parts = []
        if num >= 10000000:
            parts.append(_two_digits(num // 10000000) + " Crore")
            num %= 10000000
        if num >= 100000:
            parts.append(_two_digits(num // 100000) + " Lakh")
            num %= 100000
        if num >= 1000:
            parts.append(_two_digits(num // 1000) + " Thousand")
            num %= 1000
        if num > 0:
            parts.append(_three_digits(num))

        return " ".join(parts).strip()

    # ── Main Generator ────────────────────────────────────────────────
    def generate_invoice_pdf(self, inv_meta, items):
        if not os.path.exists("invoices"):
            os.makedirs("invoices")

        file_path = os.path.join("invoices", f"{inv_meta['invoice_id']}.pdf")

        c = canvas.Canvas(file_path, pagesize=A4)
        W, H = A4

        # ── Load Settings ──
        settings = self.db_manager.get_shop_settings()
        shop_name = settings.get("shop_name", "N.A. MOTORS")
        shop_addr = settings.get("address", "")
        shop_mob = settings.get("mobile", "")
        shop_gst = settings.get("gstin", "")
        logo_path = settings.get("logo_path", "")
        theme = settings.get("invoice_theme", "Modern (Blue)")
        app_logger.info(f"Generating PDF with Theme: '{theme}' for Invoice: {inv_meta['invoice_id']}")

        # ── Item Data Post-Processing (Hybrid HSN Fallback) ──
        for item in items:
            # item: [idx, sys_id, name, HSN, GST%, Disc%, Qty, Rate, Total]
            if not item[3] or str(item[3]).strip().upper() == 'N/A':
                rule = self.db_manager.search_hsn_rule(item[2])
                if rule:
                    item[3] = rule['hsn_code']
                    item[4] = rule.get('gst_rate', item[4])

        # ── Theme Logic ──
        # Default: Modern (Blue)
        BRAND = (0.10, 0.31, 0.63) # Navy Blue
        SECONDARY = (0.2, 0.2, 0.2)
        HEADER_FONT = "Helvetica-Bold"
        BODY_FONT = "Helvetica"
        ACCENT_LINE = True

        if theme == "Executive (Black/Gold)":
            BRAND = (0.10, 0.10, 0.12)   # Almost Black
            SECONDARY = (0.85, 0.65, 0.13)  # Gold
            HEADER_FONT = "Times-Bold"
            BODY_FONT = "Times-Roman"

        elif theme == "Minimal (B&W)":
            BRAND = (0.15, 0.15, 0.15)   # Dark Gray
            SECONDARY = (0.0, 0.0, 0.0)   # Black
            ACCENT_LINE = False

        elif theme == "Saffron (Indian)":
            BRAND = (0.88, 0.38, 0.00)    # Saffron/Deep Orange
            SECONDARY = (0.55, 0.20, 0.00) # Dark burnt orange
            HEADER_FONT = "Helvetica-Bold"
            BODY_FONT = "Helvetica"

        elif theme == "Green (Eco)":
            BRAND = (0.09, 0.40, 0.20)    # Forest Green
            SECONDARY = (0.13, 0.55, 0.27) # Lighter green
            HEADER_FONT = "Helvetica-Bold"
            BODY_FONT = "Helvetica"

        elif theme == "Logo Adaptive":
            # Extract from logo
            if logo_path and os.path.exists(logo_path):
                BRAND = self._extract_logo_color(logo_path)
            else:
                BRAND = (0.10, 0.31, 0.63) # Fallback
            SECONDARY = BRAND

        # Read new settings
        show_gst_breakdown = settings.get("show_gst_breakdown", "true") == "true"
        gst_mode = settings.get("gst_mode", "CGST+SGST")
        default_gst_rate = float(settings.get("default_gst_rate", "18"))
        footer_text = settings.get("invoice_footer_text", "Thank you for your business! | E. & O.E.")


        # Derived Colors
        BRAND_LIGHT = (BRAND[0] * 0.1, BRAND[1] * 0.1 + 0.9, BRAND[2] * 0.1 + 0.9)  # Ultra light tint
        if theme == "Minimal (B&W)": BRAND_LIGHT = (0.95, 0.95, 0.95)
        
        WHITE = (1, 1, 1)
        BLACK = (0, 0, 0)
        GRAY = (0.45, 0.45, 0.45)
        RED = (0.85, 0.15, 0.15)
        LIGHT_GRAY = (0.97, 0.97, 0.99)
        if theme == "Executive (Black/Gold)": LIGHT_GRAY = (0.98, 0.98, 0.95) 

        # ── Layout Constants ──
        MARGIN_L = 15 * mm
        MARGIN_R = W - 15 * mm
        CONTENT_W = MARGIN_R - MARGIN_L
        ROW_H = 10 * mm

        # ━━━━━ HEADER SECTION ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        header_y = H - 20 * mm
        
        # Theme Accent Color (For Shop Name & "Total Due" text)
        THEME_COLOR = BRAND
        if theme == "Executive (Black/Gold)":
            THEME_COLOR = SECONDARY # Use Gold for Shop Name in Executive
            
        # --- LEFT SIDE: LOGO & INVOICE META ---
        # Logo
        logo_h = 25 * mm
        if logo_path and os.path.exists(logo_path):
            try:
                c.drawImage(logo_path, MARGIN_L, header_y - 12 * mm, width=25 * mm, height=25 * mm, mask='auto', preserveAspectRatio=True)
            except: pass
        
        # Invoice Meta (Below Logo)
        meta_y = header_y - 20 * mm
        c.setFillColorRGB(*THEME_COLOR) # Updated to THEME_COLOR
        c.setFont(HEADER_FONT, 18)
        c.drawString(MARGIN_L, meta_y, "INVOICE")
        
        c.setFillColorRGB(*GRAY)
        c.setFont(BODY_FONT, 10)
        c.drawString(MARGIN_L, meta_y - 6 * mm, f"#{inv_meta['invoice_id']}")
        c.drawString(MARGIN_L, meta_y - 11 * mm, f"Date: {inv_meta['date']}")

        # --- RIGHT SIDE: SHOP DETAILS ---
        c.setFillColorRGB(*THEME_COLOR) # Updated to THEME_COLOR
        c.setFont(HEADER_FONT, 16)
        c.drawRightString(MARGIN_R, header_y, shop_name)
        
        c.setFillColorRGB(*GRAY)
        c.setFont(BODY_FONT, 9)
        y_metrics = header_y - 6 * mm
        for line in shop_addr.split("\n"):
            c.drawRightString(MARGIN_R, y_metrics, line.strip())
            y_metrics -= 4 * mm
        
        if shop_mob: 
            c.drawRightString(MARGIN_R, y_metrics, f"Ph: {shop_mob}")
            y_metrics -= 4 * mm
        if shop_gst:
            c.drawRightString(MARGIN_R, y_metrics, f"GSTIN: {shop_gst}")

        # Divider (Moved down slightly)
        div_y = meta_y - 20 * mm
        c.setStrokeColorRGB(*BRAND)
        c.setLineWidth(1 if ACCENT_LINE else 0.5)
        c.line(MARGIN_L, div_y, MARGIN_R, div_y)

        # ━━━━━ BILL TO & VEHICLE INFO (Text Only - Clean) ━━━━━━━━
        y = div_y - 10 * mm
        
        # Column 1: Bill To
        c.setFillColorRGB(*SECONDARY)
        c.setFont(HEADER_FONT, 10)
        c.drawString(MARGIN_L, y, "BILL TO")
        
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.setFont(BODY_FONT, 11)
        c.drawString(MARGIN_L, y - 6 * mm, inv_meta['customer'])
        
        c.setFont(BODY_FONT, 9)
        c.setFillColorRGB(*GRAY)
        c.drawString(MARGIN_L, y - 11 * mm, f"Mobile: {inv_meta['mobile']}")
        
        # Customer GSTIN display (v2.1)
        if inv_meta.get('customer_gstin'):
            c.setFont(BODY_FONT, 8)
            c.drawString(MARGIN_L, y - 15 * mm, f"GSTIN: {inv_meta['customer_gstin']}")
        
        # Column 2: Vehicle Details
        col2_x = W / 2 + 10 * mm
        c.setFillColorRGB(*SECONDARY)
        c.setFont(HEADER_FONT, 10)
        c.drawString(col2_x, y, "VEHICLE DETAILS")
        
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.setFont(BODY_FONT, 11)
        c.drawString(col2_x, y - 6 * mm, inv_meta['vehicle'])
        
        c.setFont(BODY_FONT, 9)
        c.setFillColorRGB(*GRAY)
        c.drawString(col2_x, y - 11 * mm, f"Reg No: {inv_meta['reg_no']}")
        
        # Extra Fields
        extra_y = y - 18 * mm
        extra_details = inv_meta.get("extra_details", {})
        count = 0
        for k, v in extra_details.items():
            if count > 1: break 
            label_x = MARGIN_L if count == 0 else col2_x
            c.drawString(label_x, extra_y, f"{k}: {v}")
            count += 1

        # ━━━━━ ITEMS TABLE (Modern Clean) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        y = extra_y - 15 * mm
        
        # Columns (Adjusted for Disc % column and spacing)
        col_sno = MARGIN_L + 2 * mm
        col_desc = MARGIN_L + 11 * mm
        col_hsn = MARGIN_R - 95 * mm
        col_gst = MARGIN_R - 76 * mm
        col_disc = MARGIN_R - 62 * mm  # New Column
        col_qty = MARGIN_R - 48 * mm
        col_rate = MARGIN_R - 33 * mm
        col_amt = MARGIN_R - 2 * mm

        def clean_float(val):
            try:
                if isinstance(val, (int, float)): return float(val)
                # Strip symbols like Rs. or commas
                s = str(val).replace("Rs.", "").replace("₹", "").replace(",", "").strip()
                return float(s)
            except:
                return 0.0

        def draw_header(c, y):
            # Header Bar - Retain Brand Color
            c.setFillColorRGB(*BRAND)
            c.rect(MARGIN_L, y - 8 * mm, CONTENT_W, 8 * mm, fill=1, stroke=0)
            
            c.setFillColorRGB(*WHITE)
            c.setFont(HEADER_FONT, 8)
            c.drawString(col_sno, y - 5.5 * mm, "#")
            c.drawString(col_desc, y - 5.5 * mm, "DESCRIPTION")
            c.drawString(col_hsn, y - 5.5 * mm, "HSN")
            c.drawRightString(col_gst, y - 5.5 * mm, "GST%")
            c.drawRightString(col_disc, y - 5.5 * mm, "DISC%")
            c.drawRightString(col_qty, y - 5.5 * mm, "QTY")
            c.drawRightString(col_rate, y - 5.5 * mm, "RATE")
            c.drawRightString(col_amt, y - 5.5 * mm, "AMOUNT")
            return y - 8 * mm

        y = draw_header(c, y)
        
        page_num = 1
        
        for idx, item in enumerate(items):
            # Page Break
            if y < 60 * mm:
                c.setFont(BODY_FONT, 8)
                c.drawCentredString(W/2, 10*mm, f"Page {page_num}")
                c.showPage()
                page_num += 1
                y = H - 20 * mm
                y = draw_header(c, y)
            
            # Row
            if idx % 2 == 0:
                c.setFillColorRGB(*LIGHT_GRAY)
                c.rect(MARGIN_L, y - ROW_H, CONTENT_W, ROW_H, fill=1, stroke=0)
                
            c.setFillColorRGB(0.2, 0.2, 0.2)
            c.setFont(BODY_FONT, 9)
            
            # Content
            # SNo
            c.drawString(col_sno, y - 6 * mm, str(item[0]))
            
            # Desc
            desc_text = str(item[2])
            if len(desc_text) > 30: desc_text = desc_text[:30] + "..."
            c.drawString(col_desc, y - 6 * mm, desc_text)
            
            # HSN
            hsn_text = str(item[3])
            c.drawString(col_hsn - 2 * mm, y - 6 * mm, hsn_text)
            
            # GST%
            gst_val = clean_float(item[4])
            c.drawRightString(col_gst, y - 6 * mm, f"{gst_val:.0f}%")

            # DISC%
            disc_val = clean_float(item[5])
            c.drawRightString(col_disc, y - 6 * mm, f"{disc_val:.0f}%")
            
            # Qty
            qty_val = str(item[6])
            c.drawRightString(col_qty, y - 6 * mm, qty_val)
            
            # Rate (MRP)
            rate_val = clean_float(item[7])
            c.drawRightString(col_rate, y - 6 * mm, f"{rate_val:.2f}")
            
            # Amount (Final)
            amt_val = clean_float(item[8])
            c.setFont(HEADER_FONT, 9)
            c.drawRightString(col_amt, y - 6 * mm, f"{amt_val:.2f}")
            c.setFont(BODY_FONT, 9)
            
            y -= ROW_H

        # ━━━━━ SUMMARY SECTION ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # Ensure space
        if y < 60 * mm:
            c.showPage()
            y = H - 40 * mm

        # Line between Items and Summary
        c.setStrokeColorRGB(*BRAND)
        c.setLineWidth(1)
        c.line(MARGIN_L, y, MARGIN_R, y)
        
        y -= 10 * mm
        
        # Left Side: Words & Terms
        c.setFont(BODY_FONT, 9)
        c.setFillColorRGB(*GRAY)
        words = self._amount_in_words(inv_meta['total'])
        c.drawString(MARGIN_L, y, "Amount in Words:")
        c.setFillColorRGB(*SECONDARY)
        c.setFont(HEADER_FONT, 9)
        c.drawString(MARGIN_L, y - 5 * mm, f"{words} Only")
        
        # Right Side: Summary Card
        card_w = 70 * mm
        card_x = MARGIN_R - card_w
        
          # Total MRP
        c.setFillColorRGB(*GRAY)
        c.setFont(BODY_FONT, 10)
        c.drawString(card_x, y, "Total MRP:")
        c.setFillColorRGB(*BLACK)
        c.drawRightString(MARGIN_R, y, f"{inv_meta.get('original_mrp', 0.0):.2f}")
        
        # Total Savings
        y -= 6 * mm
        c.setFillColorRGB(*GRAY)
        c.drawString(card_x, y, "Total Savings:")
        savings = inv_meta.get('total_savings', 0.0)
        if savings > 0:
            c.setFillColorRGB(*RED)
            c.drawRightString(MARGIN_R, y, f"- {savings:.2f}")
        else:
            c.setFillColorRGB(*BLACK)
            c.drawRightString(MARGIN_R, y, "0.00")

        # Taxable Value
        y -= 6 * mm
        c.setFillColorRGB(*GRAY)
        c.drawString(card_x, y, "Taxable Value:")
        c.setFillColorRGB(*BLACK)
        c.drawRightString(MARGIN_R, y, f"{inv_meta.get('taxable_value', 0.0):.2f}")

        # GST Included
        y -= 6 * mm
        c.setFillColorRGB(*GRAY)
        c.drawString(card_x, y, "GST (Included):")
        c.setFillColorRGB(*BLACK)
        c.drawRightString(MARGIN_R, y, f"{inv_meta.get('gst_included', 0.0):.2f}")

        # Grand Total Bar (Retain Brand Color)
        y -= 10 * mm
        c.setFillColorRGB(*BRAND)
        c.roundRect(card_x - 2 * mm, y - 4 * mm, card_w + 2 * mm, 12 * mm, 2 * mm, fill=1, stroke=0)
        
        c.setFillColorRGB(*WHITE)
        c.setFont(HEADER_FONT, 12)
        c.drawString(card_x + 2 * mm, y, "GRAND TOTAL")
        c.setFont(HEADER_FONT, 14)
        c.drawRightString(MARGIN_R, y - 1 * mm, f"Rs. {inv_meta['total']:.2f}")
        
        # ━━━━━ FOOTER (Minimal - No Band) ━━━━━━━━━━━━━━━━━━━━━━━━
        footer_y = 10 * mm
        
        # Simple Separator
        c.setStrokeColorRGB(*GRAY)
        c.setLineWidth(0.5)
        c.line(MARGIN_L, footer_y + 8 * mm, MARGIN_R, footer_y + 8 * mm)
        
        c.setFillColorRGB(*GRAY)
        c.setFont(BODY_FONT, 8)
        c.drawCentredString(W / 2, footer_y + 4 * mm, footer_text)
        
        # Developer Credit
        c.setFont(HEADER_FONT, 7)
        c.setFillColorRGB(*SECONDARY)
        c.drawCentredString(W / 2, footer_y, "SOFTWARE BY:- G.K.SHARMA Mob:- 9807418534")

        # ━━━━━ WATERMARK (If Status Exists) ━━━━━━━━━━━━━━━━━━━━━━
        if inv_meta.get('status'):
            from reportlab.lib.colors import Color
            c.saveState()
            c.translate(W/2, H/2)
            c.rotate(45)
            c.setFont("Helvetica-Bold", 60)
            c.setFillColor(Color(1, 0, 0, alpha=0.3))  # Fixed: use Color object for alpha support
            c.drawCentredString(0, 0, inv_meta['status'])
            c.restoreState()

        c.save()
        return file_path

    def regenerate_invoice(self, invoice_id):
        """
        Regenerate PDF for an existing invoice, checking for return status.
        """
        details = self.db_manager.get_invoice_details(invoice_id)
        if not details:
            app_logger.error(f"Cannot regenerate invoice {invoice_id}: Not found")
            return None
            
        # Check for returns
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM returns WHERE invoice_id = ?", (invoice_id,))
            if cursor.fetchone()[0] > 0:
                details['status'] = "RETAINED" # User requested "RETAINED" (or RETURNED)
            else:
                details['status'] = ""
        except:
            details['status'] = ""
        finally:
            conn.close()
            
        # Transform items for PDF generator (needs list of list/tuple)
        # Current items: [{'name':..., 'qty':..., 'price':..., 'total':...}]
        # Target: [SNo, Name, Desc, Qty, Rate, Amount]
        # Transform items for PDF generator (needs list of list/tuple)
        # Current items: [{'name':..., 'qty':..., 'price':..., 'total':...}]
        # Target: [idx, sys_id, name, HSN, GST%, Disc%, Qty, Rate, Total]
        pdf_items = []
        tax_details = details.get('tax_details', [])
        
        for idx, item in enumerate(details['items'], 1):
             sys_id = item.get('part_id', item.get('sys_id', ''))
             # Try to find tax info in saved tax_details
             tax_info = next((t for t in tax_details if t.get('id') == sys_id), {})
             
             # Calculate effective discount % (Legacy or New)
             raw_mrp = item.get('base_price', item.get('price', 0.0))
             discounted_total = item.get('total', 0.0)
             qty = item.get('qty', 1)
             unit_discounted = discounted_total / qty if qty > 0 else 0
             
             disc_perc = 0.0
             if raw_mrp > 0:
                 disc_perc = (1 - (unit_discounted / raw_mrp)) * 100
             
             pdf_items.append([
                 idx, 
                 sys_id,
                 item.get('name', 'Item'),
                 tax_info.get('hsn', item.get('hsn', 'N/A')),
                 tax_info.get('gst_rate', item.get('gst_rate', 18.0)),
                 disc_perc, # Index 5: DISC%
                 qty,
                 raw_mrp, # Rate (MRP)
                 discounted_total # Amount (Final)
             ])
             
        return self.generate_invoice_pdf(details, pdf_items)
