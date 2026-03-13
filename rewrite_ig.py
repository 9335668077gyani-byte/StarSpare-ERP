import os

# Read the original file
with open("c:/Users/Admin/Desktop/spare_ERP/invoice_generator.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

output = []
# We keep everything up to `def _get_item_data`
found_target = False
for line in lines:
    if line.strip().startswith("def _get_item_data(self, ctx):"):
        found_target = True
        break
    output.append(line)

new_code = """
    def _add_footer(self, canvas, doc):
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        canvas.saveState()
        canvas.setFont('Helvetica', 7)
        canvas.setFillColorRGB(0.5, 0.5, 0.5)
        
        # Left side (Terms & Conditions)
        tc_text = "T&C: 1. Goods once sold will not be taken back. 2. Subject to local jurisdiction."
        canvas.drawString(10.5*mm, 8*mm, tc_text)
        
        # Right side (Brand + Contact)
        text = "NexTier Systems Mob-9807418534"
        text_width = canvas.stringWidth(text, 'Helvetica', 7)
        x_text = A4[0] - 10.5*mm - text_width
        canvas.drawString(x_text, 8*mm, text)
        
        # Optional Logo if provided
        import os
        logo_path = os.path.join("data", "nextier_logo.png")
        if os.path.exists(logo_path):
            try:
                canvas.drawImage(logo_path, x_text - 6*mm, 6*mm, width=5*mm, height=5*mm, preserveAspectRatio=True, anchor='s')
            except Exception:
                pass
                
        canvas.restoreState()

    def generate_invoice_pdf(self, meta, items):
        import os
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib.colors import HexColor, black, white, lightgrey
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, KeepTogether
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

        if not os.path.exists("invoices"): os.makedirs("invoices")
        filepath = os.path.join("invoices", f"{meta.get('invoice_id', 'INVOICE')}.pdf")
        
        # RULE 1: BYPASS CACHE FOR CUSTOM COLORS
        shop_settings = self.db_manager.get_shop_settings()
        theme_name = shop_settings.get("invoice_theme", "Modern Blue")
        
        if "Custom Color" in theme_name:
            theme_hex = shop_settings.get("invoice_custom_color", "#3498DB") 
            if not str(theme_hex).startswith("#"): theme_hex = f"#{theme_hex}"
            if len(str(theme_hex)) < 7: theme_hex = "#3498DB"
        elif "Logo Adaptive" in theme_name:
            logo_path = shop_settings.get("logo_path", "")
            if os.path.exists(logo_path):
                try:
                    rgb = self._extract_logo_color(logo_path)[0]
                    theme_hex = '#%02x%02x%02x' % (int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255))
                except:
                    theme_hex = "#3498DB"
            else:
                theme_hex = "#3498DB"
        elif "Executive" in theme_name: theme_hex = "#1A1A1E" 
        elif "Professional" in theme_name: theme_hex = "#E67E22"
        elif "Minimal" in theme_name: theme_hex = "#222222"
        else: theme_hex = "#3498DB"

        try:
            PRIMARY_COLOR = HexColor(theme_hex)
        except:
            PRIMARY_COLOR = HexColor("#3498DB")

        selected_format = shop_settings.get("invoice_format", "Modern")

        doc = SimpleDocTemplate(filepath, pagesize=A4, rightMargin=10*mm, leftMargin=10*mm, topMargin=15*mm, bottomMargin=15*mm)
        elements = []
        styles = getSampleStyleSheet()
        styleN = styles['Normal']
        styleN.fontName = 'Helvetica'
        styleN.fontSize = 9
        
        styleB = ParagraphStyle('bold', parent=styleN, fontName='Helvetica-Bold')
        styleR = ParagraphStyle('right', parent=styleN, alignment=TA_RIGHT)
        styleC = ParagraphStyle('center', parent=styleN, alignment=TA_CENTER)
        
        # RULE 2: THE UNIVERSAL DATA PAYLOAD
        s_name = shop_settings.get('shop_name', 'Shop Name')
        s_add = shop_settings.get('address', '')
        s_gst = shop_settings.get('gstin', '')
        
        c_name = meta.get('customer', meta.get('customer_name', ''))
        c_phone = meta.get('mobile', meta.get('customer_phone', ''))
        c_add = meta.get('address', meta.get('customer_address', ''))
        inv_no = meta.get('invoice_id', meta.get('invoice_number', ''))
        inv_date = meta.get('date', '')

        header_left = Paragraph(f"<b><font size=14>{s_name}</font></b><br/>{s_add}<br/><b>GSTIN:</b> {s_gst}", styleN)
        header_right = Paragraph(f"<b>BILL TO:</b><br/>{c_name}<br/>Ph: {c_phone}<br/>{c_add}<br/><br/><b>Invoice No:</b> {inv_no}<br/><b>Date:</b> {inv_date}", styleR)

        logo = self._get_logo(shop_settings.get('logo_path', ''))
        if logo:
            header_table = Table([[logo, header_left, header_right]], colWidths=[40*mm, 80*mm, 70*mm])
            header_table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'), ('ALIGN',(2,0),(2,0),'RIGHT')]))
        else:
            header_table = Table([[header_left, header_right]], colWidths=[110*mm, 80*mm])
            header_table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'), ('ALIGN',(1,0),(1,0),'RIGHT')]))
            
        elements.append(header_table)
        elements.append(Spacer(1, 8*mm))
        elements.append(Paragraph("<b>TAX INVOICE</b>", ParagraphStyle('ti', fontName='Helvetica-Bold', fontSize=14, alignment=TA_CENTER, textColor=PRIMARY_COLOR)))
        elements.append(Spacer(1, 4*mm))

        # RULE 3: THE "IRON GRID" A4 TABLE (190mm)
        table_data = [["S.No", "Description", "HSN", "Qty", "Rate", "GST %", "Total"]]
        
        import re as _re
        def _safe_f(val):
            if not val: return 0.0
            if isinstance(val, (int, float)): return float(val)
            match = _re.search(r'-?\d+(?:\.\d+)?', str(val).replace(',', ''))
            return float(match.group()) if match else 0.0

        hsn_data = {}
        for idx, row in enumerate(items):
            if isinstance(row, dict):
                hsn = str(row.get('hsn_code', row.get('hsn', '')))
                gr = _safe_f(row.get('gst_rate', row.get('tax_perc', 0)))
                av = _safe_f(row.get('total', 0))
                qty = str(row.get('qty', 1))
                rate = _safe_f(row.get('unit_price', row.get('price', 0)))
                desc_val = f"<b>{row.get('part_id','')}</b> - {row.get('part_name','')}"
            else:
                hsn = str(row[6]) if len(row) > 6 else ""
                gr = _safe_f(row[7]) if len(row) > 7 else 0.0
                av = _safe_f(row[5]) if len(row) > 5 else 0.0
                qty = str(row[3])
                rate = _safe_f(row[4])
                desc_val = f"<b>{row[1]}</b> - {row[2]}"
            
            # HSN data collection
            tv = (av * 100) / (100 + gr) if gr else av
            ta = av - tv
            c_s = ta / 2
            sk = hsn if hsn else "None"
            if sk not in hsn_data: hsn_data[sk] = {'taxable': 0.0, 'cgst': 0.0, 'sgst': 0.0, 'rate': gr}
            hsn_data[sk]['taxable'] += tv
            hsn_data[sk]['cgst'] += c_s
            hsn_data[sk]['sgst'] += c_s

            desc = Paragraph(desc_val, styleN)
            table_data.append([
                str(idx + 1), 
                desc, 
                hsn, 
                qty, 
                f"{rate:.2f}", 
                f"{gr:g}%", 
                f"{av:.2f}"
            ])

        col_widths = [12*mm, 75*mm, 20*mm, 15*mm, 23*mm, 15*mm, 30*mm]
        item_table = Table(table_data, colWidths=col_widths, repeatRows=1)

        # RULE 4: THE 5 DISTINCT FORMATS (TableStyles)
        t_style = [
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('ALIGN', (1,0), (1,-1), 'LEFT'),
            ('ALIGN', (4,0), (6,-1), 'RIGHT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold')
        ]

        if selected_format == "Modern":
            # Format 1: Modern (Default)
            t_style.extend([
                ('BACKGROUND', (0,0), (-1,0), PRIMARY_COLOR),
                ('TEXTCOLOR', (0,0), (-1,0), white),
                ('GRID', (0,0), (-1,-1), 0.25, lightgrey),
                ('BOX', (0,0), (-1,-1), 0.25, lightgrey)
            ])
        elif selected_format == "Classic":
            # Format 2: Classic (Tally/SAP Style)
            t_style.extend([
                ('TEXTCOLOR', (0,0), (-1,0), black),
                ('GRID', (0,0), (-1,-1), 1.0, black)
            ])
        elif selected_format == "Compact":
            # Format 3: Compact
            t_style.extend([
                ('TEXTCOLOR', (0,0), (-1,0), PRIMARY_COLOR),
                ('LINEBELOW', (0,0), (-1,0), 1.0, PRIMARY_COLOR),
                ('LINEBELOW', (0,1), (-1,-1), 0.25, lightgrey)
            ])
        elif "Elegant" in selected_format or selected_format == "Detailed":
            # Format 4: Elegant
            t_style.extend([
                ('TEXTCOLOR', (0,0), (-1,0), PRIMARY_COLOR),
                ('BOX', (0,0), (-1,-1), 0.5, black)
            ])
            for i in range(1, len(table_data)):
                if i % 2 == 0: t_style.append(('BACKGROUND', (0,i), (-1,i), HexColor("#F8F9FA")))
        else:
            # Format 5: Standard / Audit
            t_style.extend([
                ('BACKGROUND', (0,0), (-1,0), HexColor("#333333")),
                ('TEXTCOLOR', (0,0), (-1,0), white),
                ('GRID', (0,0), (-1,-1), 1.5, black)
            ])

        item_table.setStyle(TableStyle(t_style))
        elements.append(item_table)
        elements.append(Spacer(1, 5*mm))

        # Bottom section: Totals, Words, HSN
        d_tot = [
            [Paragraph("Sub Total:", styleR), Paragraph(f"{meta.get('sub_total',0):.2f}", styleR)],
            [Paragraph("Discount:", styleR), Paragraph(f"{meta.get('discount',0):.2f}", styleR)],
            [Paragraph("<b>GRAND TOTAL:</b>", ParagraphStyle('rbb', parent=styleN, fontName='Helvetica-Bold', alignment=TA_RIGHT)), 
             Paragraph(f"<b>{meta.get('total',0):.2f}</b>", ParagraphStyle('rbb2', parent=styleN, fontName='Helvetica-Bold', alignment=TA_RIGHT))]
        ]
        tt = Table(d_tot, colWidths=[40*mm, 36*mm])
        tt.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'RIGHT'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))

        ctx = {'hsn_data': hsn_data, 'fb': 'Helvetica-Bold', 'P': PRIMARY_COLOR}
        thsn = self._build_hsn_table(ctx)

        amt_p_text = "<b>Amount in Words:</b><br/>" + self._amount_in_words(meta.get('total',0))
        l_bot = [Paragraph(amt_p_text, styleN), Spacer(1, 5*mm), Paragraph("<b>HSN / SAC SUMMARY</b>", ParagraphStyle('h', fontName='Helvetica-Bold', fontSize=8, textColor=PRIMARY_COLOR)), thsn]
        
        tb = Table([[l_bot, tt]], colWidths=[114*mm, 76*mm])
        tb.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('ALIGN', (1,0), (1,0), 'RIGHT')]))
        elements.append(KeepTogether(tb))

        # Build PDF
        try:
            from logger import app_logger
            doc.build(elements, onFirstPage=self._add_footer, onLaterPages=self._add_footer)
        except Exception as e:
            try:
                from logger import app_logger
                app_logger.error(f"Failed to build Platypus doc: {e}")
            except:
                print(f"Failed to build Platypus doc: {e}")
            raise e
            
        return filepath

    def generate_preview_image(self, invoice_format, theme, custom_color):
        import os
        from logger import app_logger
        meta = {
            'invoice_id': 'PREVIEW-123', 'date': '01-Jan-2026', 'customer': 'Sample Customer Name',
            'mobile': '9876543210', 'vehicle': 'Brand Model Version', 'reg_no': 'UP14 AB 1234',
            'sub_total': 1500.0, 'discount': 50.0, 'total': 1450.0,
            'extra_details': {'KM': '15000', 'Mech': 'Tech1'}
        }
        items = [
            (1, 'P001', 'Long Example Part Description To Test The Wrapping Behavior Inside The Platypus Boundaries', 1.0, 450.0, 450.0, '8708', 18.0),
            (2, 'P002', 'Item Description 2', 1.0, 850.0, 850.0, '2710', 18.0),
            (3, 'P003', 'Labor Charges    ', 1.0, 200.0, 200.0, '9987', 18.0)
        ]
        
        old_get = getattr(self.db_manager, 'get_shop_settings', None)
        def mock_settings():
            s = old_get() if old_get else {}
            s['invoice_format'] = invoice_format
            s['invoice_theme'] = theme
            s['invoice_custom_color'] = custom_color
            return s
            
        if old_get: self.db_manager.get_shop_settings = mock_settings
        
        try:
            self.generate_invoice_pdf(meta, items)
            pdf_path = os.path.join("invoices", "PREVIEW-123.pdf")
            png_path = os.path.join("data", "format_previews", "live_preview.png")
            os.makedirs(os.path.dirname(png_path), exist_ok=True)
            converted = False
            try:
                import fitz
                doc = fitz.open(pdf_path)
                page = doc[0]
                mat = fitz.Matrix(3, 3) 
                pix = page.get_pixmap(matrix=mat, alpha=False)
                pix.save(png_path)
                doc.close()
                converted = True
            except ImportError: pass
                
            if not converted:
                try:
                    from pdf2image import convert_from_path
                    images = convert_from_path(pdf_path, dpi=150, first_page=1, last_page=1)
                    if images:
                        images[0].save(png_path, 'PNG')
                        converted = True
                except ImportError: pass
            
            try: os.remove(pdf_path)
            except: pass
            
            return png_path if converted else None
        except Exception as e:
            app_logger.error(f"Live preview generation failed for {invoice_format}: {e}")
            return None
        finally:
            if old_get: self.db_manager.get_shop_settings = old_get
"""

output.append(new_code)
with open("c:/Users/Admin/Desktop/spare_ERP/invoice_generator.py", "w", encoding="utf-8") as f:
    f.writelines(output)
print("File rewritten successfully")
