from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
import os
from logger import app_logger
from path_utils import get_app_data_path  # type: ignore

class InvoiceGenerator:
    def __init__(self, db_manager):
        self.db_manager = db_manager

    # ── Color Extraction ──────────────────────────────────────────────
    def _extract_logo_colors(self, logo_path):
        """
        Extract the top 2 dominant DISTINCT colors from the logo independently.
        Uses PIL quantize to avoid averaging/mixing colors.
        Returns (brand_color, secondary_color) as normalized RGB tuples.
        Falls back to navy + gold on failure.
        """
        FALLBACK_BRAND     = (0.10, 0.31, 0.63)   # Navy blue
        FALLBACK_SECONDARY = (0.85, 0.65, 0.13)   # Gold

        def _norm(r, g, b, darken=0.82):
            """Normalize 0-255 RGB to 0-1 and darken slightly for print readability."""
            return (
                min(r / 255 * darken, 1.0),
                min(g / 255 * darken, 1.0),
                min(b / 255 * darken, 1.0),
            )

        def _is_valid(r, g, b):
            """Reject near-white, near-black, and near-gray pixels."""
            brightness  = (r + g + b) / 3
            saturation  = max(r, g, b) - min(r, g, b)
            return 30 < brightness < 230 and saturation > 45

        try:
            from PIL import Image
            from collections import Counter

            img = Image.open(logo_path).convert("RGB")
            img = img.resize((120, 120))

            # Quantize to 16 palette entries — real distinct colours, no averaging
            # Fallback to integer 0 (MEDIANCUT) for Pillow < 9.1.0 compatibility
            _mediancut = getattr(getattr(Image, 'Quantize', None), 'MEDIANCUT', 0)
            quantized = img.quantize(colors=16, method=_mediancut)
            palette_img = quantized.convert("RGB")

            # Count pixel frequency per palette colour (passed through filter)
            pixel_counts = Counter(
                px for px in palette_img.getdata() if _is_valid(*px)
            )

            if not pixel_counts:
                return FALLBACK_BRAND, FALLBACK_SECONDARY

            # ── BRAND: darkest + most saturated colour ─────────────────────
            # Score = saturation × (255 - brightness)²
            # This heavily favours dark, vivid corporate colours (e.g. TVS blue)
            # over bright graphic accents (e.g. orange deer) regardless of
            # how many pixels they occupy.
            def _brand_score(rgb):
                r, g, b = rgb
                brightness  = (r + g + b) / 3
                saturation  = max(r, g, b) - min(r, g, b)
                return saturation * ((255 - brightness) ** 2)

            all_colors = list(pixel_counts.keys())
            brand_rgb  = max(all_colors, key=_brand_score)
            brand      = _norm(*brand_rgb)

            # ── SECONDARY: most frequent colour visually distinct from BRAND ─
            # (the accent/graphic colour, e.g. the orange arrow in TVS logo)
            secondary = None
            for rgb, _ in pixel_counts.most_common():
                if rgb == brand_rgb:
                    continue
                dist = sum((a - b) ** 2 for a, b in zip(rgb, brand_rgb)) ** 0.5
                if dist > 55:   # Euclidean RGB distance threshold
                    secondary = _norm(*rgb, darken=0.90)
                    break

            # Fallback: no distinct second colour — derive a lighter tint of BRAND
            if secondary is None:
                secondary = tuple(min(c + 0.22, 1.0) for c in brand)

            app_logger.info(f"Logo Adaptive — BRAND={brand}  SECONDARY={secondary}")
            return brand, secondary

        except Exception as e:
            app_logger.warning(f"Could not extract logo colors: {e}")
            return FALLBACK_BRAND, FALLBACK_SECONDARY

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
        invoices_dir = get_app_data_path("invoices")  # always writable (AppData or project root)
        file_path = os.path.join(invoices_dir, f"{inv_meta['invoice_id']}.pdf")

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
            # Coerce None values to "N/A"
            current_hsn = str(item[3]).strip().upper() if item[3] is not None else "N/A"
            item[3] = current_hsn 
            if current_hsn == 'N/A' or current_hsn == 'NONE' or not current_hsn:
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
            # Extract the 2 most dominant DISTINCT colours from the logo separately
            if logo_path and os.path.exists(logo_path):
                BRAND, SECONDARY = self._extract_logo_colors(logo_path)
            else:
                BRAND     = (0.10, 0.31, 0.63)   # Fallback: Navy blue
                SECONDARY = (0.85, 0.65, 0.13)   # Fallback: Gold

        # Read new settings
        show_gst_breakdown = str(settings.get("show_gst_breakdown", "true")).lower() in ["true", "1", "yes"]
        show_hsn = str(settings.get("show_hsn_on_invoice", "false")).lower() in ["true", "1", "yes"]
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

        # ── Revised Invoice Badge ──────────────────────────────────────
        if extra_details.get("_is_edited"):
            AMBER = (0.90, 0.50, 0.00)
            badge_w = 38 * mm
            badge_h = 6 * mm
            badge_x = MARGIN_R - badge_w
            badge_y = extra_y - badge_h
            c.setFillColorRGB(*AMBER)
            c.roundRect(badge_x, badge_y, badge_w, badge_h, 1.5 * mm, fill=1, stroke=0)
            c.setFillColorRGB(1, 1, 1)
            c.setFont(HEADER_FONT, 8)
            c.drawCentredString(badge_x + badge_w / 2, badge_y + 1.5 * mm, "\u2605 REVISED INVOICE")

        # ── Custom Extra Fields (skip all internal _ keys) ─────────────
        count = 0
        for k, v in extra_details.items():
            if str(k).startswith('_'): continue   # skip internal flags
            if count > 1: break
            label_x = MARGIN_L if count == 0 else col2_x
            c.setFillColorRGB(*GRAY)
            c.setFont(BODY_FONT, 9)
            c.drawString(label_x, extra_y, f"{k}: {v}")
            count += 1

        # ━━━━━ ITEMS TABLE (Dual-Mode Auto-Switch) ━━━━━━━
        y = extra_y - 15 * mm
        
        # Determine Mode: B2B or explicitly Show HSN
        cust_gstin = inv_meta.get('customer_gstin', '').strip()
        is_b2b = bool(cust_gstin)
        
        available_width = W - (2 * MARGIN_L)
        
        if is_b2b or show_hsn:
            # 10 Columns: #  PART-CODE  DESCRIPTION  HSN  QTY  MRP  DISC%  RATE  GST%  AMOUNT
            # fixed col widths for all cols EXCEPT description:
            fixed_widths = [20, 65, 40, 30, 40, 35, 40, 35, 65]   # 9 cols (no desc)
            desc_width = available_width - sum(fixed_widths)
            col_widths_pt = [20, 65, desc_width, 40, 30, 40, 35, 40, 35, 65]
            mode_hsn = True
        else:
            # 8 Columns (B2C): #  PART-CODE  DESCRIPTION  QTY  MRP  DISC%  GST%  AMOUNT
            # fixed col widths for all cols EXCEPT description:
            fixed_widths = [20, 65, 35, 45, 40, 40, 70]   # 7 cols (no desc)
            desc_width = available_width - sum(fixed_widths)
            col_widths_pt = [20, 65, desc_width, 35, 45, 40, 40, 70]
            mode_hsn = False

        col_x = [MARGIN_L]
        for w in col_widths_pt:
            col_x.append(col_x[-1] + w)
        TABLE_W = available_width

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
            c.rect(MARGIN_L, y - 8 * mm, TABLE_W, 8 * mm, fill=1, stroke=0)
            
            c.setFillColorRGB(*WHITE)
            c.setFont(HEADER_FONT, 8)
            pad_l = 2 * mm
            pad_r = 2 * mm
            
            # Left align
            c.drawString(col_x[0] + pad_l, y - 5.5 * mm, "#")
            c.drawString(col_x[1] + pad_l, y - 5.5 * mm, "PART CODE")
            c.drawString(col_x[2] + pad_l, y - 5.5 * mm, "DESCRIPTION")
            
            # Right align
            if mode_hsn:
                c.drawRightString(col_x[4] - pad_r, y - 5.5 * mm, "HSN")
                c.drawRightString(col_x[5] - pad_r, y - 5.5 * mm, "QTY")
                c.drawRightString(col_x[6] - pad_r, y - 5.5 * mm, "MRP")
                c.drawRightString(col_x[7] - pad_r, y - 5.5 * mm, "DISC%")
                c.drawRightString(col_x[8] - pad_r, y - 5.5 * mm, "RATE")
                c.drawRightString(col_x[9] - pad_r, y - 5.5 * mm, "GST%")
                c.drawRightString(col_x[10] - pad_r, y - 5.5 * mm, "AMOUNT")
            else:
                c.drawRightString(col_x[4] - pad_r, y - 5.5 * mm, "QTY")
                c.drawRightString(col_x[5] - pad_r, y - 5.5 * mm, "MRP")
                c.drawRightString(col_x[6] - pad_r, y - 5.5 * mm, "DISC%")
                c.drawRightString(col_x[7] - pad_r, y - 5.5 * mm, "GST%")
                c.drawRightString(col_x[8] - pad_r, y - 5.5 * mm, "AMOUNT")
                
            return y - 8 * mm

        y = draw_header(c, y)
        y -= 2 * mm   # gap between header and first data row
        
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
                y -= 2 * mm   # gap after repeated header on new page
            
            # Row
            if idx % 2 == 0:
                c.setFillColorRGB(*LIGHT_GRAY)
                c.rect(MARGIN_L, y - ROW_H, TABLE_W, ROW_H, fill=1, stroke=0)
                
            c.setFillColorRGB(0.2, 0.2, 0.2)
            c.setFont(BODY_FONT, 9)
            
            # Content
            pad_l = 2 * mm
            pad_r = 2 * mm
            
            # SNo
            c.drawString(col_x[0] + pad_l, y - 6 * mm, str(item[0]))

            # PART CODE
            part_code = str(item[1])
            c.drawString(col_x[1] + pad_l, y - 6 * mm, part_code)
            
            # DESCRIPTION (Paragraph Auto-Wrap - No Bleeding)
            desc_text = str(item[2])
            desc_style = ParagraphStyle(
                name='DescStyle',
                fontName=BODY_FONT,
                fontSize=7.5,
                leading=8.5,
                alignment=0
            )
            desc_paragraph = Paragraph(desc_text, desc_style)
            
            # Width strictly constrained to its column boundary (accounting for padding)
            p_width = col_widths_pt[2] - (pad_l + pad_r)
            p_w, p_h = desc_paragraph.wrapOn(c, p_width, ROW_H)
            
            # Vertically center the wrapped paragraph inside the fixed row height
            p_y = y - ROW_H + (ROW_H - p_h) / 2
            desc_paragraph.drawOn(c, col_x[2] + pad_l, p_y)
            
            # Base Details
            qty_display = f"{float(item[6]):g}"   # string for table cells
            qty_num     = max(float(item[6]), 0.01) # float for math
            raw_mrp = clean_float(item[7])
            disc_val = clean_float(item[5])
            gst_val = clean_float(item[4])
            total_val = clean_float(item[8])
            
            if mode_hsn:
                # 10 Columns
                # HSN
                hsn_text = str(item[3])
                if not hsn_text or hsn_text == "None": hsn_text = ""
                c.drawRightString(col_x[4] - pad_r, y - 6 * mm, hsn_text)
                
                # QTY, MRP, DISC%
                c.drawRightString(col_x[5] - pad_r, y - 6 * mm, qty_display)
                c.drawRightString(col_x[6] - pad_r, y - 6 * mm, f"{raw_mrp:.2f}")
                c.drawRightString(col_x[7] - pad_r, y - 6 * mm, f"{disc_val:.0f}%")
                
                # RATE = unit taxable base (excl. GST) = (AMOUNT / qty) / (1 + GST%)
                unit_incl = total_val / qty_num   # GST-inclusive per unit
                rate_val  = unit_incl / (1 + gst_val / 100) if gst_val > 0 else unit_incl
                c.drawRightString(col_x[8] - pad_r, y - 6 * mm, f"{rate_val:.2f}")
                
                # GST%, AMOUNT
                c.drawRightString(col_x[9] - pad_r, y - 6 * mm, f"{gst_val:.0f}%")
                c.setFont(HEADER_FONT, 9)
                c.drawRightString(col_x[10] - pad_r, y - 6 * mm, f"{total_val:.2f}")
            else:
                # 8 Columns (B2C)
                # QTY, MRP, DISC%
                c.drawRightString(col_x[4] - pad_r, y - 6 * mm, qty_display)
                c.drawRightString(col_x[5] - pad_r, y - 6 * mm, f"{raw_mrp:.2f}")
                c.drawRightString(col_x[6] - pad_r, y - 6 * mm, f"{disc_val:.0f}%")
                
                # GST%, AMOUNT
                c.drawRightString(col_x[7] - pad_r, y - 6 * mm, f"{gst_val:.0f}%")
                c.setFont(HEADER_FONT, 9)
                c.drawRightString(col_x[8] - pad_r, y - 6 * mm, f"{total_val:.2f}")
            c.setFont(BODY_FONT, 9)
            
            y -= ROW_H

        # ━━━━━ SUMMARY SECTION ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        # Ensure space
        # Ensure enough space for summary + QR + signatory + footer
        if y < 90 * mm:
            c.showPage()
            y = H - 40 * mm


        # Line between Items and Summary
        c.setStrokeColorRGB(*BRAND)
        c.setLineWidth(1)
        c.line(MARGIN_L, y, MARGIN_R, y)
        
        y -= 10 * mm
        
        # --- ACCOUNTING ROUND OFF ---
        exact_total = float(inv_meta['total'])
        rounded_total = float(round(exact_total))
        round_off = rounded_total - exact_total

        # Left Side: Words & Terms
        top_summary_y = y
        c.setFont(BODY_FONT, 9)
        c.setFillColorRGB(*GRAY)
        words = self._amount_in_words(rounded_total)
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

        # GST Breakdown (Optional Split vs Single)
        total_gst_val = float(inv_meta.get('gst_included', 0.0))
        
        if show_gst_breakdown and total_gst_val > 0:
            if gst_mode == "IGST (Inter-State)":
                y -= 6 * mm
                c.setFillColorRGB(*GRAY)
                c.drawString(card_x, y, "IGST (Included):")
                c.setFillColorRGB(*BLACK)
                c.drawRightString(MARGIN_R, y, f"{total_gst_val:.2f}")
            else:
                # CGST/SGST Split
                half_gst = total_gst_val / 2
                y -= 6 * mm
                c.setFillColorRGB(*GRAY)
                c.drawString(card_x, y, "CGST (Included):")
                c.setFillColorRGB(*BLACK)
                c.drawRightString(MARGIN_R, y, f"{half_gst:.2f}")
                
                y -= 6 * mm
                c.setFillColorRGB(*GRAY)
                c.drawString(card_x, y, "SGST (Included):")
                c.setFillColorRGB(*BLACK)
                c.drawRightString(MARGIN_R, y, f"{half_gst:.2f}")
        else:
            y -= 6 * mm
            c.setFillColorRGB(*GRAY)
            c.drawString(card_x, y, "GST (Included):")
            c.setFillColorRGB(*BLACK)
            c.drawRightString(MARGIN_R, y, f"{total_gst_val:.2f}")

        # Round Off
        y -= 6 * mm
        c.setFillColorRGB(*GRAY)
        c.drawString(card_x, y, "Round Off:")
        c.setFillColorRGB(*BLACK)
        sign = "+" if round_off >= 0 else "-"
        c.drawRightString(MARGIN_R, y, f"{sign} {abs(round_off):.2f}")

        # Grand Total Bar (Retain Brand Color)
        y -= 10 * mm
        c.setFillColorRGB(*BRAND)
        c.roundRect(card_x - 2 * mm, y - 4 * mm, card_w + 2 * mm, 12 * mm, 2 * mm, fill=1, stroke=0)
        
        c.setFillColorRGB(*WHITE)
        c.setFont(HEADER_FONT, 12)
        c.drawString(card_x + 2 * mm, y, "GRAND TOTAL")
        c.setFont(HEADER_FONT, 14)
        c.drawRightString(MARGIN_R, y - 1 * mm, f"Rs. {rounded_total:.2f}")
        
        # ━━━━━ QR CODE + PAYMENT + SIGNATORY SECTION ━━━━━━━━━━━━━━
        # QR Code & Payment are aligned higher up on the Left
        # Signatory remains lower on the Right
        sig_zone_y = y - 5 * mm   # Bottom boundary for Signatory
        qr_size    = 22 * mm      # Cleaner, more compact QR scale
        qr_top_y   = top_summary_y - 9 * mm  # Tightest fit directly below Words

        # ── Read Payment QR settings (fully user-configurable from Settings page) ──
        upi_enabled = str(settings.get("payment_qr_enabled", "true")).lower() in ["true", "1", "yes"]
        UPI_ID      = settings.get("payment_upi_id", "").strip()
        pay_name    = settings.get("payment_display_name", "").strip() or shop_name

        # ── Read payment breakdown EARLY (needed for QR condition + block) ────
        pay_cash  = float(inv_meta.get("payment_cash", rounded_total))
        pay_upi   = float(inv_meta.get("payment_upi",  0.0))
        pay_due   = float(inv_meta.get("payment_due",  0.0))
        pay_mode  = str(inv_meta.get("payment_mode", "CASH"))

        # ── LEFT: UPI Payment QR ──────────────────────────────────────
        # QR is only needed when UPI money is involved:
        #   • pay_upi > 0  → customer already paid some via UPI (show amount paid)
        #   • pay_due > 0  → remaining balance to be collected via UPI
        upi_involved = (pay_upi > 0 or pay_due > 0)
        if upi_enabled and UPI_ID and upi_involved:
            # QR amount: outstanding due first, else the UPI portion already paid
            if pay_due > 0:
                qr_amount = pay_due          # collect remaining balance via UPI
            elif pay_upi > 0:
                qr_amount = pay_upi          # confirm the UPI portion already paid
            else:
                qr_amount = inv_meta.get("_qr_amount", rounded_total)
            upi_amount  = f"{qr_amount:.2f}"
            # URL-encode payee name for safety
            safe_pay_name = pay_name.replace(" ", "%20")
            upi_string  = (
                f"upi://pay?pa={UPI_ID}&pn={safe_pay_name}"
                f"&am={upi_amount}&cu=INR"
                f"&tn=Invoice%20{inv_meta['invoice_id']}"
            )
            try:
                import qrcode as _qr
                import tempfile, io
                qr_img = _qr.QRCode(
                    version=2,
                    error_correction=_qr.constants.ERROR_CORRECT_M,
                    box_size=4,
                    border=2,
                )
                qr_img.add_data(upi_string)
                qr_img.make(fit=True)
                pil_img = qr_img.make_image(fill_color="black", back_color="white")
                # Save to a temp file so ReportLab can read it
                tmp_qr = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                pil_img.save(tmp_qr.name)
                tmp_qr.close()
                qr_x = MARGIN_L
                c.drawImage(tmp_qr.name, qr_x, qr_top_y - qr_size,
                            width=qr_size, height=qr_size, mask='auto')
                # Store for deferred cleanup after c.save() — Windows keeps file locks open
                self._pending_qr_cleanup = tmp_qr.name
                c.setFillColorRGB(*GRAY)
                c.setFont(BODY_FONT, 7)
                # Label: "Scan to Pay Due" if balance, else "Scan to Pay via UPI"
                scan_label = "Scan to Pay Due" if pay_due > 0 else "Scan to Pay via UPI"
                c.drawCentredString(qr_x + qr_size / 2, qr_top_y - qr_size - 3 * mm,
                                    scan_label)
                c.setFont(HEADER_FONT, 7)
                c.drawCentredString(qr_x + qr_size / 2, qr_top_y - qr_size - 7 * mm,
                                    UPI_ID)
            except Exception as _qr_err:
                # If qrcode not installed, show UPI ID as text fallback
                c.setFillColorRGB(*GRAY)
                c.setFont(BODY_FONT, 8)
                c.drawString(MARGIN_L, qr_top_y - 8 * mm, f"Pay via UPI: {UPI_ID}")

        # ── PAYMENT BREAKDOWN BLOCK (between Grand Total and Signatory) ──────────
        pay_block_x = MARGIN_L + 25 * mm   # Fit snugly beside QR Core
        pay_block_y = qr_top_y - 1 * mm
        pay_col_w   = 35 * mm              # Narrow constraint to stop rightward bleed

        # Only render if user has saved at least one meaningful payment field
        has_pay_data = (pay_cash + pay_upi + pay_due) > 0 or pay_mode != "CASH"

        if has_pay_data:
            # Mini header
            c.setFillColorRGB(*GRAY)
            c.setFont(HEADER_FONT, 7.5)
            c.drawString(pay_block_x, pay_block_y, "PAYMENT RECEIVED")
            pay_block_y -= 5 * mm

            row_h = 4.5 * mm

            def _pay_row(label, amount, color_rgb, bold=False):
                nonlocal pay_block_y
                c.setFillColorRGB(*GRAY)
                c.setFont(BODY_FONT, 8)
                c.drawString(pay_block_x + 2 * mm, pay_block_y, label)
                c.setFillColorRGB(*color_rgb)
                c.setFont(HEADER_FONT if bold else BODY_FONT, 8)
                c.drawRightString(pay_block_x + pay_col_w, pay_block_y, f"Rs. {amount:,.2f}")
                pay_block_y -= row_h

            GREEN  = (0.0, 0.6, 0.3)
            CYAN_C = (0.0, 0.5, 0.8)
            RED_C  = (0.8, 0.1, 0.1)

            if pay_cash > 0:
                _pay_row("Cash Received :", pay_cash, GREEN)
            if pay_upi > 0:
                _pay_row("UPI Received :",  pay_upi,  CYAN_C)
                
            pay_block_y -= 1 * mm # Extra margin to prevent badge overlap

            if pay_due > 0:
                # Highlighted due row
                due_box_y = pay_block_y - 1.5 * mm
                c.setFillColorRGB(0.98, 0.9, 0.9)
                c.roundRect(pay_block_x, due_box_y, pay_col_w + 2 * mm, row_h + 2 * mm,
                            1.5 * mm, fill=1, stroke=0)
                _pay_row("BALANCE DUE :", pay_due, RED_C, bold=True)
            else:
                # Paid in full badge
                badge_h = 5.5 * mm
                badge_w = 34 * mm
                badge_y = pay_block_y - 4 * mm
                c.setFillColorRGB(0.9, 0.98, 0.9)
                c.setStrokeColorRGB(*GREEN)
                c.roundRect(pay_block_x, badge_y, badge_w, badge_h, 1.5 * mm, fill=1, stroke=1)
                
                c.setFillColorRGB(*GREEN)
                c.setFont(HEADER_FONT, 8)
                c.drawCentredString(pay_block_x + (badge_w / 2), badge_y + 1.5 * mm, "\u2713 PAID IN FULL")
                pay_block_y -= 6 * mm


        # ── RIGHT: Authorised Signatory  ──────────────────────────────
        sig_x = MARGIN_R - 55 * mm          # right-aligned block, ~55mm wide
        sig_top = sig_zone_y - 2 * mm

        # "For <ShopName>" header
        c.setFillColorRGB(*BRAND)
        c.setFont(HEADER_FONT, 9)
        c.drawRightString(MARGIN_R, sig_top, f"For  {shop_name}")

        # Blank signature area (dotted line)
        sig_line_y = sig_top - 18 * mm
        c.setStrokeColorRGB(*GRAY)
        c.setLineWidth(0.5)
        c.setDash(2, 3)
        c.line(sig_x, sig_line_y, MARGIN_R, sig_line_y)
        c.setDash()   # reset dash

        # "Authorized Signatory" label
        c.setFillColorRGB(*GRAY)
        c.setFont(BODY_FONT, 8)
        c.drawRightString(MARGIN_R, sig_line_y - 5 * mm, "Authorized Signatory")

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

        # B12: Deferred QR temp file cleanup after file handle is released by c.save()
        if hasattr(self, '_pending_qr_cleanup') and self._pending_qr_cleanup:
            import os as _os
            try:
                _os.unlink(self._pending_qr_cleanup)
            except Exception:
                pass
            self._pending_qr_cleanup = None

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
             
             # Use _final_total from stored tax_details for accurate amounts (B6 fix)
             # For legacy invoices without tax_details, fall back to item['total']
             final_total = tax_info.get('_final_total')
             if final_total and final_total > 0:
                 discounted_total = final_total
             else:
                 discounted_total = item.get('total', 0.0)

             qty = item.get('qty', 1)
             unit_discounted = discounted_total / qty if qty > 0 else 0
             
             disc_perc = 0.0
             if raw_mrp > 0:
                 disc_perc = (1 - (unit_discounted / raw_mrp)) * 100
             
             # Robust HSN Extraction
             hsn_val = tax_info.get('hsn') or item.get('hsn')
             if hsn_val is None or str(hsn_val).strip() == "":
                 hsn_val = 'N/A'
                 
             pdf_items.append([
                 idx, 
                 sys_id,
                 item.get('name', 'Item'),
                 str(hsn_val),
                 tax_info.get('gst_rate') or item.get('gst_rate', 18.0),
                 disc_perc, # Index 5: DISC%
                 qty,
                 raw_mrp, # Rate (MRP)
                 discounted_total # Amount (Final)
             ])
             
        return self.generate_invoice_pdf(details, pdf_items)
