import os
from datetime import datetime
from logger import app_logger

try:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    REPORTLAB_AVAILABLE = True
except ImportError:
    app_logger.error("ReportLab is not installed. PDF generation will fail.")
    REPORTLAB_AVAILABLE = False


# ---------------------------------------------------------------------------
# Data Sanitization Utilities
# ---------------------------------------------------------------------------

def _clean(val):
    """
    Sanitize a single cell value for safe use in a ReportLab table:
    - Converts None / NaN to '-'
    - Strips leading/trailing whitespace, newline chars, and stray quotes
    - Replaces the Rupee symbol with 'Rs.' (default fonts don't support it)
    - Returns a plain str
    """
    if val is None:
        return "-"
    s = str(val)
    # Replace NaN / None strings
    if s.lower() in ("nan", "none", "null"):
        return "-"
    # Strip control chars and stray quotes
    s = s.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    s = s.replace('"', '').replace("'", "").strip()
    # Font-safe symbol replacement
    s = s.replace("₹", "Rs.")
    return s if s else "-"


def _safe_float(val):
    """Return float or 0.0; never raises."""
    try:
        if val is None or str(val).strip() in ("", "nan", "none"):
            return 0.0
        return float(val)
    except (ValueError, TypeError):
        return 0.0


# ---------------------------------------------------------------------------
# Shared Style Constants
# ---------------------------------------------------------------------------

HEADER_BLUE   = colors.HexColor("#1a4f9c")
HEADER_GREEN  = colors.HexColor("#2e7d32")
HEADER_ORANGE = colors.HexColor("#e65100")

_BASE_TABLE_STYLE = [
    # Header row
    ("TEXTCOLOR",   (0, 0), (-1,  0), colors.white),
    ("FONTNAME",    (0, 0), (-1,  0), "Helvetica-Bold"),
    ("FONTSIZE",    (0, 0), (-1,  0), 9),
    ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
    ("TOPPADDING",  (0, 0), (-1,  0), 8),
    # Data rows
    ("FONTNAME",    (0, 1), (-1, -1), "Helvetica"),
    ("FONTSIZE",    (0, 1), (-1, -1), 8),
    ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING",  (0, 1), (-1, -1), 4),
    ("BOTTOMPADDING",(0,1), (-1, -1), 4),
    # Alternating row colours
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
    # Grid
    ("INNERGRID",   (0, 0), (-1, -1), 0.25, colors.lightgrey),
    ("BOX",         (0, 0), (-1, -1), 0.5,  colors.darkgrey),
]


def _make_table_style(header_color, extra_styles=None):
    styles = list(_BASE_TABLE_STYLE)
    styles.insert(0, ("BACKGROUND", (0, 0), (-1, 0), header_color))
    if extra_styles:
        styles.extend(extra_styles)
    return TableStyle(styles)


# ---------------------------------------------------------------------------
# ReportGenerator Class
# ---------------------------------------------------------------------------

class ReportGenerator:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        # Ensure output directories exist relative to working directory
        for folder in ["reports", "invoices"]:
            if not os.path.exists(folder):
                try:
                    os.makedirs(folder)
                except OSError:
                    pass

    # -----------------------------------------------------------------------
    # Shared: Professional shop header
    # -----------------------------------------------------------------------
    def _get_shop_header_elements(self, title):
        """Builds a standardised shop header (logo + shop info + report title)."""
        settings = self.db_manager.get_shop_settings()
        shop_name = _clean(settings.get("shop_name", "SPARE ERP"))
        shop_addr = _clean(settings.get("address", ""))
        shop_mob  = _clean(settings.get("mobile", ""))
        shop_gst  = _clean(settings.get("gstin", ""))
        logo_path = settings.get("logo_path", "")

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "HeaderTitle",
            parent=styles["Heading1"],
            fontSize=16,
            textColor=HEADER_BLUE,
            spaceAfter=4,
        )
        info_style = ParagraphStyle(
            "HeaderInfo",
            parent=styles["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#555555"),
            leading=12,
        )
        report_title_style = ParagraphStyle(
            "ReportTitle",
            parent=styles["Heading2"],
            fontSize=13,
            textColor=colors.black,
            alignment=1,
            spaceBefore=12,
            spaceAfter=10,
        )

        elements = []

        # --- Logo + shop info side-by-side ---
        logo_cell = ""
        if logo_path and os.path.exists(str(logo_path)):
            try:
                logo_cell = Image(logo_path, width=28 * mm, height=28 * mm)
                logo_cell.hAlign = "LEFT"
            except Exception:
                logo_cell = ""

        address_html = shop_addr.replace("\n", "<br/>")
        info_html = f"<b>{shop_name}</b><br/>{address_html}"
        if shop_mob and shop_mob != "-":
            info_html += f"<br/>Ph: {shop_mob}"
        if shop_gst and shop_gst != "-":
            info_html += f"<br/>GSTIN: {shop_gst}"

        info_para = Paragraph(info_html, info_style)

        hdr_table = Table([[logo_cell, info_para]], colWidths=[35 * mm, None])
        hdr_table.setStyle(TableStyle([
            ("VALIGN",  (0, 0), (-1, -1), "TOP"),
            ("ALIGN",   (1, 0), (1,  0),  "LEFT"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        elements.append(hdr_table)
        elements.append(Spacer(1, 6))

        # --- Report title & timestamp ---
        elements.append(Paragraph(f"<b>{_clean(title)}</b>", report_title_style))
        gen_time = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
        elements.append(Paragraph(
            f"Generated: {gen_time}",
            ParagraphStyle("GenTime", parent=styles["Normal"],
                           fontSize=8, textColor=colors.grey, alignment=1),
        ))
        elements.append(Spacer(1, 12))
        return elements

    # -----------------------------------------------------------------------
    # 1. Inventory Report  —  Enterprise Layout
    # -----------------------------------------------------------------------
    def generate_inventory_report_pdf(self, inventory_data):
        """
        inventory_data: rows from DatabaseManager.get_all_parts()

        VERIFIED column indices (from the SELECT statement):
          0 = part_id
          1 = part_name
          2 = description
          3 = unit_price   <-- MRP
          4 = qty          <-- Stock
          5 = rack_number  <-- Location / Rack
          6 = col_number
          7 = reorder_level
          8 = vendor_name
          (indices 9-16 are compatibility, category, dates, hsn, gst)
        """
        if not REPORTLAB_AVAILABLE:
            return False, "ReportLab not installed"

        file_path = os.path.join(
            "reports",
            f"Inventory_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        )

        doc = SimpleDocTemplate(
            file_path,
            pagesize=landscape(A4),
            rightMargin=12 * mm, leftMargin=12 * mm,
            topMargin=12 * mm, bottomMargin=12 * mm,
        )
        elements = self._get_shop_header_elements("INVENTORY STATUS REPORT")
        styles = getSampleStyleSheet()

        # ===================================================================
        # PASS 1: Calculate dashboard metrics AND build clean table rows
        # ===================================================================
        total_qty    = 0
        total_val    = 0.0
        critical_count = 0
        serial_no    = 0  # S.No. counter

        TABLE_HEADERS = ["S.No.", "Part ID", "Part Name", "Rack/Location", "Stock", "MRP (Rs.)", "Total Value (Rs.)"]
        clean_table_data = [TABLE_HEADERS]

        for row in inventory_data:
            # ---- Safe string extraction ----
            def s(val):
                """Clean a single cell: strip whitespace, remove \n \r and stray quotes."""
                if val is None:
                    return "-"
                cleaned = str(val).replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
                cleaned = cleaned.replace('"', '').replace("'", '').strip()
                return cleaned if cleaned else "-"

            try:
                part_id   = s(row[0])[:20]   # index 0: part_id
                part_name = s(row[1])[:45]    # index 1: part_name

                # index 5: rack_number  (location)
                location  = s(row[5]) if len(row) > 5 and row[5] not in (None, '') else "-"

                # index 4: qty (stock)
                try:
                    stock = float(row[4]) if row[4] is not None and str(row[4]).strip() != '' else 0.0
                except (ValueError, TypeError):
                    stock = 0

                # index 3: unit_price (MRP)
                try:
                    mrp = float(row[3]) if row[3] is not None and str(row[3]).strip() != '' else 0.0
                except (ValueError, TypeError):
                    mrp = 0.0

                # index 7: reorder_level  → determines "critical"
                try:
                    reorder = int(row[7]) if len(row) > 7 and row[7] is not None else 5
                except (ValueError, TypeError):
                    reorder = 5

                row_total = stock * mrp

                # Dashboard accumulators
                total_qty      += stock
                total_val      += row_total
                if stock <= reorder:
                    critical_count += 1

                serial_no += 1
                clean_table_data.append([
                    str(serial_no),    # S.No.
                    part_id,
                    part_name,
                    location,
                    str(stock),
                    f"{mrp:.2f}",
                    f"{row_total:.2f}",
                ])

            except Exception as e:
                app_logger.warning(f"Inventory PDF: skipped row due to error: {e}")
                continue

        total_parts = len(clean_table_data) - 1  # exclude header row
        if total_parts <= 0:
            clean_table_data.append(["-", "-", "No inventory data found", "-", "0", "0.00", "0.00"])
            total_parts = 0

        # Grand Total footer
        clean_table_data.append(["", "", "GRAND TOTAL", "", f"{float(total_qty):g}", "", f"{total_val:,.2f}"])

        # ===================================================================
        # PASS 2: Executive Dashboard Block
        # ===================================================================
        dash_style = ParagraphStyle(
            "DashLabel",
            parent=styles["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#555555"),
            leading=13,
        )
        dash_val_style = ParagraphStyle(
            "DashValue",
            parent=styles["Normal"],
            fontSize=13,
            fontName="Helvetica-Bold",
            textColor=HEADER_BLUE,
            leading=16,
        )

        def metric_cell(label, value):
            return [Paragraph(label, dash_style), Paragraph(str(value), dash_val_style)]

        dash_data = [[
            metric_cell("Total Unique Parts",          f"{total_parts}"),
            metric_cell("Total Stock Qty",             f"{total_qty:,}"),
            metric_cell("Total Portfolio Value (Rs.)", f"{total_val:,.2f}"),
            metric_cell("Critical Parts (Stock <= Reorder)", f"{critical_count}"),
        ]]

        dash_table = Table(dash_data, colWidths=[60 * mm, 60 * mm, 70 * mm, 70 * mm])
        dash_table.setStyle(TableStyle([
            ("BOX",         (0, 0), (-1, -1), 0.5,  colors.HexColor("#cccccc")),
            ("INNERGRID",   (0, 0), (-1, -1), 0.5,  colors.HexColor("#eeeeee")),
            ("BACKGROUND",  (0, 0), (-1, -1), colors.HexColor("#f0f4ff")),
            ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING",  (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING",(0, 0),(-1, -1), 8),
            # Highlight Critical cell in amber if there are critical parts
            ("BACKGROUND",  (3, 0), (3, 0),
             colors.HexColor("#fff3cd") if critical_count > 0 else colors.HexColor("#f0f4ff")),
        ]))

        elements.append(dash_table)
        elements.append(Spacer(1, 14))

        # ===================================================================
        # PASS 3: Main Inventory Table
        # ===================================================================
        # A4 Landscape usable: ~267 mm.  7 cols: 12+20+85+28+18+30+38 = 231mm
        col_widths = [12 * mm, 20 * mm, 85 * mm, 28 * mm, 18 * mm, 30 * mm, 38 * mm]

        inv_extra = [
            # Center S.No., right-align numeric columns (Stock, MRP, Total Value)
            ("ALIGN", (0, 0), (0, -1), "CENTER"),   # S.No. centered
            ("ALIGN", (4, 0), (6, -1), "RIGHT"),    # Stock, MRP, Total: right-aligned
            # Bold + tinted grand-total footer
            ("FONTNAME",    (0, -1), (-1, -1), "Helvetica-Bold"),
            ("LINEABOVE",   (0, -1), (-1, -1), 0.8, colors.HexColor("#1a4f9c")),
            ("BACKGROUND",  (0, -1), (-1, -1), colors.HexColor("#dce8fb")),
        ]
        inv_table = Table(clean_table_data, colWidths=col_widths, repeatRows=1)
        inv_table.setStyle(_make_table_style(HEADER_BLUE, inv_extra))

        elements.append(inv_table)

        try:
            doc.build(elements)
            app_logger.info(f"Inventory PDF saved: {file_path}")
            return True, file_path
        except Exception as e:
            app_logger.error(f"Failed to generate Inventory PDF: {e}")
            return False, str(e)


    # -----------------------------------------------------------------------
    # 2. Sales / Billing Report

    # -----------------------------------------------------------------------
    def generate_sales_report_pdf(self, sales_data, total_revenue, total_expenses, total_net, total_cogs, d_from, d_to):
        """
        Generates a professional sales report with expense and profit summary.
        sales_data: list of tuples
          (date, invoice_id, customer_name, items_count, total_amount, ...)
        """
        if not REPORTLAB_AVAILABLE:
            return False, "ReportLab not installed"

        file_path = os.path.join(
            "reports",
            f"Sales_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        )

        doc = SimpleDocTemplate(
            file_path,
            pagesize=A4,
            rightMargin=15 * mm, leftMargin=15 * mm,
            topMargin=15 * mm, bottomMargin=15 * mm,
        )
        title_text = f"SALES REPORT  ({_clean(d_from)} to {_clean(d_to)})"
        elements = self._get_shop_header_elements(title_text)

        styles = getSampleStyleSheet()
        
        # 1. TOP NOTCH SUMMARY BOX
        # Create a tiny table for the summary box to make it stand out
        summary_title_style = ParagraphStyle(
            "SummaryTitle",
            parent=styles["Normal"],
            fontSize=10,
            textColor=colors.white,
            alignment=1, # Center
            fontName="Helvetica-Bold",
        )
        summary_value_style = ParagraphStyle(
            "SummaryValue",
            parent=styles["Normal"],
            fontSize=14,
            textColor=colors.white,
            alignment=1, # Center
            fontName="Helvetica-Bold",
        )

        summary_data = [
            [Paragraph("TOTAL REVENUE", summary_title_style), 
             Paragraph("TOTAL COGS", summary_title_style),
             Paragraph("TOTAL EXPENSES", summary_title_style), 
             Paragraph("NET PROFIT", summary_title_style)],
            [Paragraph(f"Rs. {total_revenue:,.2f}", summary_value_style), 
             Paragraph(f"Rs. {total_cogs:,.2f}", summary_value_style), 
             Paragraph(f"Rs. {total_expenses:,.2f}", summary_value_style), 
             Paragraph(f"Rs. {total_net:,.2f}", summary_value_style)]
        ]
        
        # Color profit based on value
        profit_color = HEADER_GREEN if total_net >= 0 else colors.red
        
        summary_table = Table(summary_data, colWidths=[45*mm, 45*mm, 45*mm, 45*mm])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor("#007bff")), # Blue for Revenue
            ('BACKGROUND', (1, 0), (1, -1), colors.HexColor("#fd7e14")), # Orange for COGS
            ('BACKGROUND', (2, 0), (2, -1), colors.HexColor("#dc3545")), # Red for Expenses
            ('BACKGROUND', (3, 0), (3, -1), profit_color),              # Green/Red for Profit
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.white),
        ]))
        
        elements.append(summary_table)
        elements.append(Spacer(1, 10 * mm))

        # Secondary info
        elements.append(Paragraph(
            f"Total Invoices: {len(sales_data)}    |    Date Range: {_clean(d_from)} to {_clean(d_to)}",
            ParagraphStyle("SubInfo", parent=styles["Normal"], fontSize=9, textColor=colors.grey, alignment=1)
        ))
        elements.append(Spacer(1, 5 * mm))

        headers = ["Date", "Invoice ID", "Customer Name", "Items", "Mode", "Amount (Rs.)"]
        data = [headers]

        for row in sales_data:
            try:
                amt = _safe_float(row[4])
                refund_amt = _safe_float(row[12]) if len(row) > 12 and row[12] else 0.0
                actual_revenue = amt - refund_amt
                
                has_return = int(row[7]) > 0 if len(row) > 7 and row[7] else False
                inv_id_clean = _clean(row[1])
                if has_return:
                    inv_id_clean += "\n[REFUND]" if actual_revenue <= 0 else "\n[P.RET]"
                    
                pay_mode_raw = str(row[11]) if len(row) > 11 else "CASH"
                pay_mode = pay_mode_raw
                if pay_mode_raw == "SPLIT":
                    p_upi = float(row[9]) if len(row) > 9 and row[9] else 0.0
                    p_cash = float(row[8]) if len(row) > 8 and row[8] else 0.0
                    pay_mode = f"SPLIT\n(C:{p_cash:g}|U:{p_upi:g})"

                amt_str = f"{actual_revenue:,.2f}"
                if refund_amt > 0:
                    amt_str += f"\n(-{refund_amt:g})"

                data.append([
                    _clean(row[0]),
                    inv_id_clean,
                    _clean(row[2])[:38],
                    _clean(row[3]),
                    pay_mode,
                    amt_str,
                ])
            except Exception as e:
                app_logger.warning(f"Sales PDF row error: {e}")
                continue

        if len(data) == 1:
            data.append(["-"] * len(headers))

        col_widths = [26 * mm, 28 * mm, 52 * mm, 16 * mm, 28 * mm, 30 * mm]
        extra = [
            ("ALIGN", (3, 0), (4, -1), "CENTER"),
            ("ALIGN", (5, 0), (5, -1), "RIGHT"),
        ]
        t = Table(data, colWidths=col_widths, repeatRows=1)
        t.setStyle(_make_table_style(HEADER_GREEN, extra))

        elements.append(t)

        try:
            doc.build(elements)
            app_logger.info(f"Sales PDF saved: {file_path}")
            return True, file_path
        except Exception as e:
            app_logger.error(f"Failed to generate Sales PDF: {e}")
            return False, str(e)

    def generate_daily_sales_report_pdf(self, sales_data, expense_data, total_revenue, total_cogs, d_from, d_to):
        """
        Groups sales by date and shows a daily summary with expenses.
        sales_data: list of tuples (date, invoice_id, customer_name, items_count, total_amount, ...)
        expense_data: dict of {date_str: total_amount}
        """
        if not REPORTLAB_AVAILABLE:
            return False, "ReportLab not installed"

        file_path = os.path.join(
            "reports",
            f"Daily_Sales_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        )

        doc = SimpleDocTemplate(
            file_path,
            pagesize=A4,
            rightMargin=15 * mm, leftMargin=15 * mm,
            topMargin=15 * mm, bottomMargin=15 * mm,
        )
        title_text = f"DAILY SALES SUMMARY  ({_clean(d_from)} to {_clean(d_to)})"
        elements = self._get_shop_header_elements(title_text)

        # 1. AGGREGATE DATA BY DATE
        # Map: Date -> {'count': X, 'amount': Y}
        daily_map = {}
        for row in sales_data:
            try:
                # Extract date only (YYYY-MM-DD)
                raw_date = str(row[0]).split(' ')[0]
                amount = _safe_float(row[4])
                refund_amt = _safe_float(row[12]) if len(row) > 12 and row[12] else 0.0
                actual_rev = amount - refund_amt
                
                if raw_date not in daily_map:
                    daily_map[raw_date] = {'count': 0, 'amount': 0.0}
                
                daily_map[raw_date]['count'] += 1
                daily_map[raw_date]['amount'] += actual_rev
            except:
                continue
        
        # Sort by date descending
        sorted_dates = sorted(daily_map.keys(), reverse=True)

        styles = getSampleStyleSheet()
        total_exp = sum(expense_data.values()) if expense_data else 0.0
        net_profit = total_revenue - total_exp - total_cogs
        
        # TOP NOTCH SUMMARY BOX
        summary_title_style = ParagraphStyle(
            "SummaryTitle",
            parent=styles["Normal"],
            fontSize=10,
            textColor=colors.white,
            alignment=1,
            fontName="Helvetica-Bold",
        )
        summary_value_style = ParagraphStyle(
            "SummaryValue",
            parent=styles["Normal"],
            fontSize=14,
            textColor=colors.white,
            alignment=1,
            fontName="Helvetica-Bold",
        )

        summary_data = [
            [Paragraph("TOTAL REVENUE", summary_title_style), 
             Paragraph("TOTAL COGS", summary_title_style),
             Paragraph("TOTAL EXPENSES", summary_title_style), 
             Paragraph("NET PROFIT", summary_title_style)],
            [Paragraph(f"Rs. {total_revenue:,.2f}", summary_value_style), 
             Paragraph(f"Rs. {total_cogs:,.2f}", summary_value_style),
             Paragraph(f"Rs. {total_exp:,.2f}", summary_value_style), 
             Paragraph(f"Rs. {net_profit:,.2f}", summary_value_style)]
        ]
        
        profit_color = HEADER_GREEN if net_profit >= 0 else colors.red
        
        summary_table = Table(summary_data, colWidths=[45*mm, 45*mm, 45*mm, 45*mm])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor("#007bff")), 
            ('BACKGROUND', (1, 0), (1, -1), colors.HexColor("#fd7e14")), 
            ('BACKGROUND', (2, 0), (2, -1), colors.HexColor("#dc3545")), 
            ('BACKGROUND', (3, 0), (3, -1), profit_color),              
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.white),
        ]))
        
        elements.append(summary_table)
        elements.append(Spacer(1, 10 * mm))

        headers = ["Date", "Invoices", "Sales (Rs.)", "Expenses (Rs.)", "Net ex-COGS (Rs.)"]
        data = [headers]

        # Combine dates from both sales and expenses
        all_dates = set(daily_map.keys()) | set(expense_data.keys() if expense_data else [])
        sorted_all_dates = sorted(list(all_dates), reverse=True)

        for dt in sorted_all_dates:
            s_info = daily_map.get(dt, {'count': 0, 'amount': 0.0})
            e_amt = expense_data.get(dt, 0.0) if expense_data else 0.0
            net = s_info['amount'] - e_amt
            
            data.append([
                dt,
                str(s_info['count']),
                f"{s_info['amount']:,.2f}",
                f"{e_amt:,.2f}",
                f"{net:,.2f}"
            ])

        if len(data) == 1:
            data.append(["-", "0", "0.00", "0.00", "0.00"])

        col_widths = [45 * mm, 25 * mm, 35 * mm, 35 * mm, 40 * mm]
        extra = [
            ("ALIGN", (1, 0), (2, -1), "RIGHT"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
        ]
        t = Table(data, colWidths=col_widths, repeatRows=1)
        t.setStyle(_make_table_style(HEADER_GREEN, extra))

        elements.append(t)

        try:
            doc.build(elements)
            app_logger.info(f"Daily Sales PDF saved: {file_path}")
            return True, file_path
        except Exception as e:
            app_logger.error(f"Failed to generate Daily Sales PDF: {e}")
            return False, str(e)

    # -----------------------------------------------------------------------
    # 3. Purchase Order Backlog / History Report
    # -----------------------------------------------------------------------
    def generate_po_report_pdf(self, po_data):
        """
        po_data: list of tuples
          Expected (from export_backlog_pdf / export_history_pdf):
            index 0 = unused, 1 = unused, 2 = PO Date, 3 = PO ID,
            4 = Supplier, 5 = Part Name, 6 = Ordered, 7 = Received, 8 = Pending
        """
        if not REPORTLAB_AVAILABLE:
            return False, "ReportLab not installed"

        file_path = os.path.join(
            "reports",
            f"PO_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        )

        doc = SimpleDocTemplate(
            file_path,
            pagesize=landscape(A4),
            rightMargin=12 * mm, leftMargin=12 * mm,
            topMargin=12 * mm, bottomMargin=12 * mm,
        )
        elements = self._get_shop_header_elements("PURCHASE ORDER REPORT")

        headers = ["PO Date", "PO ID", "Supplier", "Part Name", "Ordered", "Received", "Pending"]
        data = [headers]

        for row in po_data:
            try:
                data.append([
                    _clean(row[2])[:12],   # PO Date
                    _clean(row[3]),        # PO ID
                    _clean(row[4])[:22],   # Supplier
                    _clean(row[5])[:45],   # Part Name
                    _clean(row[6]),        # Ordered
                    _clean(row[7]),        # Received
                    _clean(row[8]),        # Pending
                ])
            except Exception as e:
                app_logger.warning(f"PO PDF row error: {e}")
                continue

        if len(data) == 1:
            data.append(["-"] * len(headers))

        # A4 Landscape ~267 mm usable
        col_widths = [25 * mm, 28 * mm, 45 * mm, 105 * mm, 18 * mm, 22 * mm, 22 * mm]
        extra = [
            ("ALIGN", (4, 0), (6, -1), "CENTER"),
        ]
        t = Table(data, colWidths=col_widths, repeatRows=1)
        t.setStyle(_make_table_style(HEADER_ORANGE, extra))

        elements.append(t)

        try:
            doc.build(elements)
            app_logger.info(f"PO PDF saved: {file_path}")
            return True, file_path
        except Exception as e:
            app_logger.error(f"Failed to generate PO PDF: {e}")
            return False, str(e)

    # -----------------------------------------------------------------------
    # 4. SINGLE Purchase Order PDF (Invoice Format)
    # -----------------------------------------------------------------------
    def generate_single_po_pdf(self, po_header, po_items):
        """
        Generates a professional single purchase order invoice.
        po_header: dict with 'To', 'PO Number', 'Date', 'Status'
        po_items: list of tuples from db_manager.get_po_items
        """
        if not REPORTLAB_AVAILABLE:
            return False, "ReportLab not installed"

        file_path = os.path.join(
            "reports",
            f"PO_Invoice_{_clean(po_header.get('PO Number', ''))}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        )

        doc = SimpleDocTemplate(
            file_path,
            pagesize=A4, # A4 Portrait
            rightMargin=15 * mm, leftMargin=15 * mm,
            topMargin=15 * mm, bottomMargin=15 * mm,
        )
        elements = self._get_shop_header_elements("PURCHASE ORDER")
        
        styles = getSampleStyleSheet()
        
        # 1. METADATA BOX
        meta_data = [
            ["To:", _clean(po_header.get("To", ""))],
            ["PO Number:", _clean(po_header.get("PO Number", ""))],
            ["Date:", _clean(po_header.get("Date", ""))],
            ["Status:", _clean(po_header.get("Status", ""))]
        ]
        if "Global Discount" in po_header:
            meta_data.append(["Global Disc:", _clean(po_header.get("Global Discount", ""))])
        
        t_meta = Table(meta_data, colWidths=[30 * mm, 100 * mm])
        t_meta.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(t_meta)
        elements.append(Spacer(1, 15))
        
        # 2. ITEM TABLE
        headers = ['S.No', 'Part ID', 'Part Name', 'HSN', 'GST %', 'Qty', 'Rcvd', 'Pend', 'Disc %', 'Price', 'Total(Rs)']
        data = [headers]
        
        grand_total = 0.0
        taxable_total = 0.0  # Total after all discounts, before GST
        gst_total = 0.0      # Total GST added
        base_total = 0.0     # Total before any discount (raw price × qty), for savings calc
        serial_no = 0
        global_disc_pct = _safe_float(po_header.get("global_disc_raw", 0.0))
        
        # Cell style for wrapping part names
        cell_style = ParagraphStyle(
            "CellWrap",
            parent=styles["Normal"],
            fontSize=7,
            leading=9,
        )
        
        for row in po_items:
            # db_manager.get_po_items returns:
            # (id, part_id, part_name, qty_ordered, qty_received, ordered_price, hsn_code, gst_rate, vendor_disc_percent)
            try:
                serial_no += 1
                part_id = _clean(row[1])
                part_name = _clean(row[2])
                qty_ordered = float(row[3]) if row[3] is not None else 0.0
                qty_received = float(row[4]) if row[4] is not None else 0.0
                pending = max(0, qty_ordered - qty_received)
                ordered_price = _safe_float(row[5])
                hsn_code = _clean(row[6])
                gst_rate = _safe_float(row[7])
                v_disc = _safe_float(row[8]) if len(row) > 8 else 0.0
                
                # Apply V. DISC % then Global Discount, then GST (matches PO Create math)
                # global_disc_pct declared before loop
                after_v_disc = ordered_price * (1.0 - (v_disc / 100.0))
                after_global = after_v_disc * (1.0 - (global_disc_pct / 100.0))
                row_taxable = after_global * qty_ordered
                row_gst = row_taxable * (gst_rate / 100.0)
                row_total = row_taxable + row_gst
                
                # Accumulate totals for summary rows
                base_total += ordered_price * qty_ordered
                taxable_total += row_taxable
                gst_total += row_gst
                grand_total += row_total
                
                # Combined disc display
                total_disc = v_disc + global_disc_pct - (v_disc * global_disc_pct / 100.0)  # Effective combined
                disc_display = f"{total_disc:.1f}%" if total_disc > 0 else "-"
                
                data.append([
                    str(serial_no),
                    part_id,
                    Paragraph(part_name, cell_style),
                    hsn_code if hsn_code else "N/A",
                    f"{gst_rate:.1f}",
                    f"{float(qty_ordered):g}",
                    f"{float(qty_received):g}",
                    str(pending),
                    disc_display,
                    f"{ordered_price:.2f}" if ordered_price > 0 else "N/A",
                    f"{row_total:.2f}" if ordered_price > 0 else "N/A"
                ])
            except Exception as e:
                app_logger.warning(f"Single PO PDF row error: {e}")
                continue
                
        if len(data) == 1:
            data.append(["-"] * len(headers))
            
        # Calculate how much money was saved through discounts
        savings_total = base_total - taxable_total  # base - discounted taxable = savings
            
        # Add summary rows at bottom of table
        data.append(["", "", "GRAND TOTAL", "", "", "", "", "", "", "", f"{grand_total:,.2f}"])
        
        # Show savings breakdown if any discount was applied
        if savings_total > 0.01:
            data.append(["", "", "  Taxable (Net)", "", "", "", "", "", "", "", f"{taxable_total:,.2f}"])
            data.append(["", "", "  GST Amount", "", "", "", "", "", "", "", f"+{gst_total:,.2f}"])
            data.append(["", "", "🏷 YOU SAVED", "", "", "", "", "", "", "", f"₹{savings_total:,.2f}"])
        
        # A4 Portrait usable width ~ 210mm - 30mm = 180mm
        col_widths = [8 * mm, 18 * mm, 45 * mm, 15 * mm, 11 * mm, 11 * mm, 11 * mm, 11 * mm, 13 * mm, 15 * mm, 22 * mm]
        
        extra = [
            ("ALIGN", (0, 0), (0, -1), "CENTER"), # S.No
            ("ALIGN", (3, 0), (8, -1), "CENTER"), # HSN to Disc % -> CENTER
            ("ALIGN", (9, 0), (10, -1), "RIGHT"), # Price and Total -> RIGHT
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"), # Grand total bold
            ("LINEABOVE", (0, -1), (-1, -1), 0.8, HEADER_ORANGE),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#fff3cd"))
        ]
        
        t_items = Table(data, colWidths=col_widths, repeatRows=1)
        t_items.setStyle(_make_table_style(HEADER_ORANGE, extra))
        elements.append(t_items)
        
        # 4. FOOTER & SIGNATURE
        elements.append(Spacer(1, 30))
        sig_style = ParagraphStyle(
            "Signature",
            parent=styles["Normal"],
            fontSize=10,
            alignment=2, # Right aligned
        )
        elements.append(Paragraph("Authorized Signatory: ___________________", sig_style))
        
        try:
            doc.build(elements)
            app_logger.info(f"Single PO PDF saved: {file_path}")
            return True, file_path
        except Exception as e:
            app_logger.error(f"Failed to generate single PO PDF: {e}")
            return False, str(e)

    # -----------------------------------------------------------------------
    # 5. MERGED Multi-PO PDF (All orders in one file, page by page)
    # -----------------------------------------------------------------------
    def generate_multi_po_pdf(self, po_list):
        """
        Generates a single merged PDF with each PO on its own page.
        po_list: list of (po_header_dict, po_items_list) tuples
        """
        if not REPORTLAB_AVAILABLE:
            return False, "ReportLab not installed"

        file_path = os.path.join(
            "reports",
            f"PO_Merged_{len(po_list)}_Orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        )

        doc = SimpleDocTemplate(
            file_path,
            pagesize=A4,
            rightMargin=15 * mm, leftMargin=15 * mm,
            topMargin=15 * mm, bottomMargin=15 * mm,
        )

        all_elements = []
        styles = getSampleStyleSheet()
        sig_style = ParagraphStyle(
            "Signature",
            parent=styles["Normal"],
            fontSize=10,
            alignment=2,
        )

        for idx, (po_header, po_items) in enumerate(po_list):
            # Page break before each PO (except the first)
            if idx > 0:
                all_elements.append(PageBreak())

            # Shop header
            all_elements.extend(self._get_shop_header_elements("PURCHASE ORDER"))

            # Metadata box
            meta_data = [
                ["To:", _clean(po_header.get("To", ""))],
                ["PO Number:", _clean(po_header.get("PO Number", ""))],
                ["Date:", _clean(po_header.get("Date", ""))],
                ["Status:", _clean(po_header.get("Status", ""))]
            ]
            if "Global Discount" in po_header:
                meta_data.append(["Global Disc:", _clean(po_header.get("Global Discount", ""))])
            t_meta = Table(meta_data, colWidths=[30 * mm, 100 * mm])
            t_meta.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]))
            all_elements.append(t_meta)
            all_elements.append(Spacer(1, 15))

            # Item table
            headers = ['S.No', 'Part ID', 'Part Name', 'HSN', 'GST %', 'Qty', 'Rcvd', 'Pend', 'Disc %', 'Price', 'Total(Rs)']
            data = [headers]
            grand_total = 0.0
            serial_no = 0

            # Cell style for wrapping part names
            cell_style = ParagraphStyle(
                "CellWrapMulti",
                parent=styles["Normal"],
                fontSize=7,
                leading=9,
            )

            # global_disc_pct from PO header (same key used by single PO PDF)
            global_disc_pct = _safe_float(po_header.get("global_disc_raw", 0.0))

            for row in po_items:
                try:
                    serial_no += 1
                    part_id = _clean(row[1])
                    part_name = _clean(row[2])
                    qty_ordered = float(row[3]) if row[3] is not None else 0.0
                    qty_received = float(row[4]) if row[4] is not None else 0.0
                    pending = max(0, qty_ordered - qty_received)
                    ordered_price = _safe_float(row[5])
                    hsn_code = _clean(row[6])
                    gst_rate = _safe_float(row[7])
                    v_disc = _safe_float(row[8]) if len(row) > 8 else 0.0

                    # Apply vendor disc → global disc → GST  (mirrors single-PO PDF)
                    after_v_disc   = ordered_price * (1.0 - (v_disc / 100.0))
                    after_global   = after_v_disc  * (1.0 - (global_disc_pct / 100.0))
                    row_taxable    = after_global  * qty_ordered
                    row_gst        = row_taxable   * (gst_rate / 100.0)
                    row_total      = row_taxable   + row_gst
                    grand_total   += row_total

                    # Combined display disc %
                    total_disc = v_disc + global_disc_pct - (v_disc * global_disc_pct / 100.0)
                    disc_display = f"{total_disc:.1f}%" if total_disc > 0 else "-"

                    data.append([
                        str(serial_no), part_id, Paragraph(part_name, cell_style), hsn_code if hsn_code else "N/A",
                        f"{gst_rate:.1f}", f"{float(qty_ordered):g}", f"{float(qty_received):g}", str(pending),
                        disc_display,
                        f"{ordered_price:.2f}" if ordered_price > 0 else "N/A",
                        f"{row_total:.2f}"   if ordered_price > 0 else "N/A"
                    ])
                except Exception as e:
                    app_logger.warning(f"Multi PO PDF row error: {e}")
                    continue
        
            # Grand total row
            data.append(["", "", "GRAND TOTAL", "", "", "", "", "", "", "", f"{grand_total:,.2f}"])
            col_widths = [8 * mm, 18 * mm, 45 * mm, 15 * mm, 11 * mm, 11 * mm, 11 * mm, 11 * mm, 13 * mm, 15 * mm, 22 * mm]
            
            extra = [
                ("ALIGN", (0, 0), (0, -1), "CENTER"), # S.No
                ("ALIGN", (3, 0), (8, -1), "CENTER"), # HSN to Disc % -> CENTER
                ("ALIGN", (9, 0), (10, -1), "RIGHT"), # Price and Total -> RIGHT
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"), # Grand total bold
                ("LINEABOVE", (0, -1), (-1, -1), 0.8, HEADER_ORANGE),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#fff3cd"))
            ]
            
            t_items = Table(data, colWidths=col_widths, repeatRows=1)
            t_items.setStyle(_make_table_style(HEADER_ORANGE, extra))
            all_elements.append(t_items)
            
            all_elements.append(Spacer(1, 30))
            all_elements.append(Paragraph("Authorized Signatory: ___________________", sig_style))

        try:
            doc.build(all_elements)
            app_logger.info(f"Multi PO PDF saved: {file_path}")
            return True, file_path
        except Exception as e:
            app_logger.error(f"Failed to generate multi PO PDF: {e}")
            return False, str(e)

    # -----------------------------------------------------------------------
    # 6. SINGLE GRN PDF (Inward Bill Format)
    # -----------------------------------------------------------------------
    def generate_single_grn_pdf(self, po_header, po_items):
        """
        Generates a professional Goods Receipt Note (GRN) invoice.
        Calculates totals based ONLY on received quantities.
        po_header: dict with 'To', 'PO Number', 'Date', 'Status'
        po_items: list of tuples from db_manager.get_po_items
        """
        if not REPORTLAB_AVAILABLE:
            return False, "ReportLab not installed"

        file_path = os.path.join(
            "reports",
            f"GRN_Bill_{_clean(po_header.get('PO Number', ''))}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        )

        doc = SimpleDocTemplate(
            file_path,
            pagesize=A4, # A4 Portrait
            rightMargin=15 * mm, leftMargin=15 * mm,
            topMargin=15 * mm, bottomMargin=15 * mm,
        )
        elements = self._get_shop_header_elements("GOODS RECEIPT NOTE (GRN) / INWARD BILL")
        
        styles = getSampleStyleSheet()
        
        # 1. METADATA BOX
        meta_data = [
            ["To:", _clean(po_header.get("To", ""))],
            ["PO Number:", _clean(po_header.get("PO Number", ""))],
            ["Date:", _clean(po_header.get("Date", ""))],
            ["Status:", _clean(po_header.get("Status", ""))]
        ]
        if "Global Discount" in po_header:
            meta_data.append(["Global Disc:", _clean(po_header.get("Global Discount", ""))])
        
        t_meta = Table(meta_data, colWidths=[30 * mm, 100 * mm])
        t_meta.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(t_meta)
        elements.append(Spacer(1, 15))
        
        # 2. ITEM TABLE
        headers = ['S.No', 'Part ID', 'Part Name', 'HSN', 'GST %', 'Qty', 'Rcvd', 'Pend', 'Disc %', 'Price', 'Total(Rs)']
        data = [headers]
        
        grand_total = 0.0
        taxable_total = 0.0  
        gst_total = 0.0      
        base_total = 0.0     
        serial_no = 0
        global_disc_pct = _safe_float(po_header.get("global_disc_raw", 0.0))
        
        cell_style = ParagraphStyle(
            "CellWrap",
            parent=styles["Normal"],
            fontSize=7,
            leading=9,
        )
        
        for row in po_items:
            try:
                qty_received = float(row[4]) if row[4] is not None else 0.0
                if qty_received <= 0:
                    continue # Skip items that haven't been received
                    
                serial_no += 1
                part_id = _clean(row[1])
                part_name = _clean(row[2])
                qty_ordered = float(row[3]) if row[3] is not None else 0.0
                pending = max(0, qty_ordered - qty_received)
                ordered_price = _safe_float(row[5])
                hsn_code = _clean(row[6])
                gst_rate = _safe_float(row[7])
                v_disc = _safe_float(row[8]) if len(row) > 8 else 0.0
                
                # Apply V. DISC % then Global Discount, then GST
                after_v_disc = ordered_price * (1.0 - (v_disc / 100.0))
                after_global = after_v_disc * (1.0 - (global_disc_pct / 100.0))
                
                # GRN specific: Multiply by RECEIVED quantity
                row_taxable = after_global * qty_received
                row_gst = row_taxable * (gst_rate / 100.0)
                row_total = row_taxable + row_gst
                
                base_total += ordered_price * qty_received
                taxable_total += row_taxable
                gst_total += row_gst
                grand_total += row_total
                
                total_disc = v_disc + global_disc_pct - (v_disc * global_disc_pct / 100.0)
                disc_display = f"{total_disc:.1f}%" if total_disc > 0 else "-"
                
                data.append([
                    str(serial_no),
                    part_id,
                    Paragraph(part_name, cell_style),
                    hsn_code if hsn_code else "N/A",
                    f"{gst_rate:.1f}",
                    f"{float(qty_ordered):g}",
                    f"{float(qty_received):g}",
                    str(pending),
                    disc_display,
                    f"{ordered_price:.2f}" if ordered_price > 0 else "N/A",
                    f"{row_total:.2f}" if ordered_price > 0 else "N/A"
                ])
            except Exception as e:
                app_logger.warning(f"Single GRN PDF row error: {e}")
                continue
                
        if len(data) == 1:
            data.append(["-"] * len(headers))
            
        savings_total = base_total - taxable_total
            
        data.append(["", "", "GRAND TOTAL", "", "", "", "", "", "", "", f"{grand_total:,.2f}"])
        
        if savings_total > 0.01:
            data.append(["", "", "  Taxable (Net)", "", "", "", "", "", "", "", f"{taxable_total:,.2f}"])
            data.append(["", "", "  GST Amount", "", "", "", "", "", "", "", f"+{gst_total:,.2f}"])
            data.append(["", "", "🏷 YOU SAVED", "", "", "", "", "", "", "", f"₹{savings_total:,.2f}"])
        
        col_widths = [8 * mm, 18 * mm, 45 * mm, 15 * mm, 11 * mm, 11 * mm, 11 * mm, 11 * mm, 13 * mm, 15 * mm, 22 * mm]
        
        extra = [
            ("ALIGN", (0, 0), (0, -1), "CENTER"), 
            ("ALIGN", (3, 0), (8, -1), "CENTER"), 
            ("ALIGN", (9, 0), (10, -1), "RIGHT"), 
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"), 
            ("LINEABOVE", (0, -1), (-1, -1), 0.8, HEADER_ORANGE),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#fff3cd"))
        ]
        
        t_items = Table(data, colWidths=col_widths, repeatRows=1)
        t_items.setStyle(_make_table_style(HEADER_ORANGE, extra))
        elements.append(t_items)
        
        elements.append(Spacer(1, 30))
        sig_style = ParagraphStyle(
            "Signature",
            parent=styles["Normal"],
            fontSize=10,
            alignment=2,
        )
        elements.append(Paragraph("Authorized Signatory: ___________________", sig_style))
        
        try:
            doc.build(elements)
            app_logger.info(f"Single GRN PDF saved: {file_path}")
            return True, file_path
        except Exception as e:
            app_logger.error(f"Failed to generate single GRN PDF: {e}")
            return False, str(e)

    # -----------------------------------------------------------------------
    # 7. MERGED Multi-GRN PDF (All orders in one file, page by page)
    # -----------------------------------------------------------------------
    def generate_multi_grn_pdf(self, po_list):
        """
        Generates a single merged PDF with each GRN on its own page.
        po_list: list of (po_header_dict, po_items_list) tuples
        """
        if not REPORTLAB_AVAILABLE:
            return False, "ReportLab not installed"

        file_path = os.path.join(
            "reports",
            f"GRN_Merged_{len(po_list)}_Orders_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        )

        doc = SimpleDocTemplate(
            file_path,
            pagesize=A4,
            rightMargin=15 * mm, leftMargin=15 * mm,
            topMargin=15 * mm, bottomMargin=15 * mm,
        )

        all_elements = []
        styles = getSampleStyleSheet()
        sig_style = ParagraphStyle(
            "Signature",
            parent=styles["Normal"],
            fontSize=10,
            alignment=2,
        )

        for idx, (po_header, po_items) in enumerate(po_list):
            if idx > 0:
                all_elements.append(PageBreak())

            all_elements.extend(self._get_shop_header_elements("GOODS RECEIPT NOTE (GRN) / INWARD BILL"))

            meta_data = [
                ["To:", _clean(po_header.get("To", ""))],
                ["PO Number:", _clean(po_header.get("PO Number", ""))],
                ["Date:", _clean(po_header.get("Date", ""))],
                ["Status:", _clean(po_header.get("Status", ""))]
            ]
            if "Global Discount" in po_header:
                meta_data.append(["Global Disc:", _clean(po_header.get("Global Discount", ""))])
            t_meta = Table(meta_data, colWidths=[30 * mm, 100 * mm])
            t_meta.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]))
            all_elements.append(t_meta)
            all_elements.append(Spacer(1, 15))

            headers = ['S.No', 'Part ID', 'Part Name', 'HSN', 'GST %', 'Qty', 'Rcvd', 'Pend', 'Disc %', 'Price', 'Total(Rs)']
            data = [headers]
            grand_total = 0.0
            serial_no = 0

            cell_style = ParagraphStyle(
                "CellWrapMulti",
                parent=styles["Normal"],
                fontSize=7,
                leading=9,
            )

            global_disc_pct = _safe_float(po_header.get("global_disc_raw", 0.0))

            for row in po_items:
                try:
                    qty_received = float(row[4]) if row[4] is not None else 0.0
                    if qty_received <= 0:
                        continue # Skip items not received
                        
                    serial_no += 1
                    part_id = _clean(row[1])
                    part_name = _clean(row[2])
                    qty_ordered = float(row[3]) if row[3] is not None else 0.0
                    pending = max(0, qty_ordered - qty_received)
                    ordered_price = _safe_float(row[5])
                    hsn_code = _clean(row[6])
                    gst_rate = _safe_float(row[7])
                    v_disc = _safe_float(row[8]) if len(row) > 8 else 0.0

                    after_v_disc   = ordered_price * (1.0 - (v_disc / 100.0))
                    after_global   = after_v_disc  * (1.0 - (global_disc_pct / 100.0))
                    
                    # GRN Specific: Use qty_received
                    row_taxable    = after_global  * qty_received
                    row_gst        = row_taxable   * (gst_rate / 100.0)
                    row_total      = row_taxable   + row_gst
                    grand_total   += row_total

                    total_disc = v_disc + global_disc_pct - (v_disc * global_disc_pct / 100.0)
                    disc_display = f"{total_disc:.1f}%" if total_disc > 0 else "-"

                    data.append([
                        str(serial_no), part_id, Paragraph(part_name, cell_style), hsn_code if hsn_code else "N/A",
                        f"{gst_rate:.1f}", f"{float(qty_ordered):g}", f"{float(qty_received):g}", str(pending),
                        disc_display,
                        f"{ordered_price:.2f}" if ordered_price > 0 else "N/A",
                        f"{row_total:.2f}"   if ordered_price > 0 else "N/A"
                    ])
                except Exception as e:
                    app_logger.warning(f"Multi GRN PDF row error: {e}")
                    continue
        
            data.append(["", "", "GRAND TOTAL", "", "", "", "", "", "", "", f"{grand_total:,.2f}"])
            col_widths = [8 * mm, 18 * mm, 45 * mm, 15 * mm, 11 * mm, 11 * mm, 11 * mm, 11 * mm, 13 * mm, 15 * mm, 22 * mm]
            
            extra = [
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (3, 0), (8, -1), "CENTER"),
                ("ALIGN", (9, 0), (10, -1), "RIGHT"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("LINEABOVE", (0, -1), (-1, -1), 0.8, HEADER_ORANGE),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#fff3cd"))
            ]
            
            t_items = Table(data, colWidths=col_widths, repeatRows=1)
            t_items.setStyle(_make_table_style(HEADER_ORANGE, extra))
            all_elements.append(t_items)
            
            all_elements.append(Spacer(1, 30))
            all_elements.append(Paragraph("Authorized Signatory: ___________________", sig_style))

        try:
            doc.build(all_elements)
            app_logger.info(f"Multi GRN PDF saved: {file_path}")
            return True, file_path
        except Exception as e:
            app_logger.error(f"Failed to generate multi GRN PDF: {e}")
            return False, str(e)

    def generate_comprehensive_report_pdf(self, sales_data, expense_data, total_revenue, total_expenses, total_net, total_cogs, d_from, d_to):
        """
        Creates a deeply detailed report grouping sales (with items) and expenses by date.
        """
        if not REPORTLAB_AVAILABLE:
            return False, "ReportLab not installed"

        file_path = os.path.join(
            "reports",
            f"Comprehensive_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        )

        doc = SimpleDocTemplate(
            file_path,
            pagesize=A4,
            rightMargin=12 * mm, leftMargin=12 * mm,
            topMargin=15 * mm, bottomMargin=15 * mm,
        )
        
        elements = self._get_shop_header_elements(f"COMPREHENSIVE HISTORY  ({_clean(d_from)} to {_clean(d_to)})")
        styles = getSampleStyleSheet()
        
        # 1. SUMMARY BOX (The "Top Notch" part)
        summary_title_style = ParagraphStyle("S1", parent=styles["Normal"], fontSize=11, textColor=colors.white, alignment=1, fontName="Helvetica-Bold")
        summary_val_style = ParagraphStyle("S2", parent=styles["Normal"], fontSize=16, textColor=colors.white, alignment=1, fontName="Helvetica-Bold")

        sum_table = Table([
            [Paragraph("REVENUE", summary_title_style), Paragraph("COGS", summary_title_style), Paragraph("EXPENSES", summary_title_style), Paragraph("NET PROFIT", summary_title_style)],
            [Paragraph(f"Rs. {total_revenue:,.2f}", summary_val_style), Paragraph(f"Rs. {total_cogs:,.2f}", summary_val_style), Paragraph(f"Rs. {total_expenses:,.2f}", summary_val_style), Paragraph(f"Rs. {total_net:,.2f}", summary_val_style)]
        ], colWidths=[45*mm, 45*mm, 45*mm, 45*mm])
        
        p_color = HEADER_GREEN if total_net >= 0 else colors.red
        sum_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#007bff")), # Blue
            ('BACKGROUND', (1,0), (1,-1), colors.HexColor("#fd7e14")), # Orange
            ('BACKGROUND', (2,0), (2,-1), colors.HexColor("#dc3545")), # Red
            ('BACKGROUND', (3,0), (3,-1), p_color),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 12),
            ('TOPPADDING', (0,0), (-1,-1), 12),
            ('GRID', (0,0), (-1,-1), 1, colors.white),
        ]))
        elements.append(sum_table)
        elements.append(Spacer(1, 10 * mm))

        # 2. DATA GROUPING
        date_groups = {}
        for r in sales_data:
            dt = str(r[0]).split(' ')[0]
            if dt not in date_groups: date_groups[dt] = {'sales': [], 'exps': []}
            date_groups[dt]['sales'].append(r)
        
        for e in expense_data:
            dt = str(e[4]).split(' ')[0] # Index 4 is date
            if dt not in date_groups: date_groups[dt] = {'sales': [], 'exps': []}
            date_groups[dt]['exps'].append(e)

        sorted_dates = sorted(date_groups.keys(), reverse=True)

        date_hdr_style = ParagraphStyle("DateHdr", parent=styles["Heading2"], fontSize=14, textColor=colors.HexColor("#2c3e50"), spaceBefore=10, spaceAfter=5, borderPadding=5, backColor=colors.HexColor("#f8f9fa"))
        item_style = ParagraphStyle("ItemS", parent=styles["Normal"], fontSize=8, leading=10)

        for dt in sorted_dates:
            data = date_groups[dt]
            elements.append(Paragraph(f"🗓️ Date: {dt}", date_hdr_style))
            
            # --- Sales Section ---
            if data['sales']:
                elements.append(Paragraph("🛒 Invoices", ParagraphStyle("SubH", parent=styles["Normal"], fontSize=10, fontName="Helvetica-Bold", textColor=HEADER_GREEN)))
                s_headers = ["Inv", "Customer", "Code", "Item Name", "Qty", "MRP", "Disc", "ItemTot", "InvTot", "Mode"]
                s_table_data = [s_headers]
                
                for s in data['sales']:
                    has_return = int(s[7]) > 0 if len(s) > 7 and s[7] else False
                    inv_id_clean = _clean(s[1]).replace("INV-", "") # short
                    
                    amt = _safe_float(s[4])
                    refund_amt = _safe_float(s[12]) if len(s) > 12 and s[12] else 0.0
                    actual_revenue = amt - refund_amt
                    
                    if has_return:
                        inv_id_clean += "\n[REFUND]" if actual_revenue <= 0 else "\n[P.RET]"
                        
                    cust_clean = _clean(s[2])[:20]
                    
                    if refund_amt > 0:
                        inv_total = f"{actual_revenue:,.2f}\n(-{refund_amt:g})"
                    else:
                        inv_total = f"{actual_revenue:,.2f}"
                    
                    try:
                        import json
                        parsed = json.loads(s[5]) if s[5] else []
                        if isinstance(parsed, dict):
                            parts_list = parsed.get('cart', [])
                        else:
                            parts_list = parsed if isinstance(parsed, list) else []
                            
                        # Keep only valid parts
                        parts_list = [p for p in parts_list if isinstance(p, dict)]
                        
                        if not parts_list:
                            pay_mode_raw = str(s[11]) if len(s) > 11 else "CASH"
                            pay_mode = pay_mode_raw
                            if pay_mode_raw == "SPLIT":
                                p_upi = float(s[9]) if len(s) > 9 and s[9] else 0.0
                                p_cash = float(s[8]) if len(s) > 8 and s[8] else 0.0
                                pay_mode = f"SPLIT\n(C:{p_cash:g}|U:{p_upi:g})"
                                
                            s_table_data.append([inv_id_clean, cust_clean, "-", "-", "-", "-", "-", "-", inv_total, pay_mode])
                            continue
                            
                        # Add a row for EACH part!
                        for i, p in enumerate(parts_list):
                            part_code = p.get('sys_id', p.get('part_id', '?'))
                            part_name = p.get('name', p.get('part_name', '?'))
                            qty = str(p.get('qty', p.get('quantity', 1)))
                            try:
                                mrp = float(p.get('base_price', p.get('price', 0)))
                                price = float(p.get('price', 0))
                            except:
                                mrp, price = 0.0, 0.0
                            
                            disc_perc = ((mrp - price) / mrp * 100) if (mrp > 0 and price < mrp) else 0.0
                            disc_str = f"{disc_perc:.1f}%" if disc_perc > 0 else "-"
                            mrp_str = f"{mrp:.1f}" if mrp > 0 else "-"
                            
                            try:
                                item_total = float(p.get('total', price * float(qty)))
                            except:
                                item_total = 0.0
                            item_tot_str = f"{item_total:.2f}" if item_total > 0 else "-"
                            
                            # Only show Invoice details on the first row of that invoice group
                            row_inv = inv_id_clean if i == 0 else ""
                            row_cust = cust_clean if i == 0 else ""
                            row_tot = inv_total if i == 0 else ""
                            
                            pay_mode_raw = str(s[11]) if len(s) > 11 else "CASH"
                            pay_mode = pay_mode_raw
                            if pay_mode_raw == "SPLIT":
                                p_upi = float(s[9]) if len(s) > 9 and s[9] else 0.0
                                p_cash = float(s[8]) if len(s) > 8 and s[8] else 0.0
                                pay_mode = f"SPLIT\n(C:{p_cash:g}|U:{p_upi:g})"
                            
                            row_mode = pay_mode if i == 0 else ""
                            
                            s_table_data.append([
                                row_inv, 
                                row_cust, 
                                Paragraph(part_code, item_style), 
                                Paragraph(part_name, item_style), 
                                qty, mrp_str, disc_str, item_tot_str, row_tot, row_mode
                            ])
                            
                    except Exception as e:
                        pay_mode_raw = str(s[11]) if len(s) > 11 else "CASH"
                        pay_mode = pay_mode_raw
                        if pay_mode_raw == "SPLIT":
                            p_upi = float(s[9]) if len(s) > 9 and s[9] else 0.0
                            p_cash = float(s[8]) if len(s) > 8 and s[8] else 0.0
                            pay_mode = f"SPLIT\n(C:{p_cash:g}|U:{p_upi:g})"
                                
                        s_table_data.append([inv_id_clean, cust_clean, "-", "Error parsing items", "-", "-", "-", "-", inv_total, pay_mode])
                
                st = Table(s_table_data, colWidths=[12*mm, 20*mm, 18*mm, 36*mm, 8*mm, 12*mm, 10*mm, 16*mm, 16*mm, 32*mm])
                st.setStyle(_make_table_style(HEADER_GREEN, [
                    ('ALIGN', (4, 0), (9, -1), 'CENTER'), # Qty to Mode centered
                    ('ALIGN', (7, 0), (8, -1), 'RIGHT'),  # Item Tot and Inv Tot aligned right
                    ('FONTSIZE', (0, 0), (-1, -1), 8)
                ]))
                elements.append(st)
                elements.append(Spacer(1, 4 * mm))

            # --- Expense Section ---
            if data['exps']:
                elements.append(Paragraph("💸 Expenses", ParagraphStyle("SubH2", parent=styles["Normal"], fontSize=10, fontName="Helvetica-Bold", textColor=colors.red)))
                e_headers = ["Title", "Category", "Amount (Rs.)"]
                e_table_data = [e_headers]
                
                for ex in data['exps']:
                    e_table_data.append([
                        _clean(ex[1]),
                        _clean(ex[3]),
                        f"{_safe_float(ex[2]):,.2f}"
                    ])
                
                et = Table(e_table_data, colWidths=[80*mm, 55*mm, 50*mm])
                et.setStyle(_make_table_style(colors.red, [('ALIGN',(2,0),(2,-1),'RIGHT'), ('FONTSIZE',(0,0),(-1,-1),8)]))
                elements.append(et)
                elements.append(Spacer(1, 4 * mm))

            elements.append(Spacer(1, 5 * mm))

        try:
            doc.build(elements)
            return True, file_path
        except Exception as e:
            app_logger.error(f"Comprehensive PDF Error: {e}")
            return False, str(e)

    # -----------------------------------------------------------------------
    # 6. Vendor Purchase Statement
    # -----------------------------------------------------------------------
    def generate_vendor_statement_pdf(self, vendor_name, d_from, d_to, po_data, total_amount, total_items):
        """
        Generates a professional purchase statement for a specific vendor.
        po_data: list of tuples (po_id, date, status, items_count, total_amount)
        """
        if not REPORTLAB_AVAILABLE:
            return False, "ReportLab not installed"

        file_path = os.path.join(
            "reports",
            f"Vendor_Statement_{_clean(vendor_name)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        )

        doc = SimpleDocTemplate(
            file_path,
            pagesize=A4,
            rightMargin=15 * mm, leftMargin=15 * mm,
            topMargin=15 * mm, bottomMargin=15 * mm,
        )
        title_text = f"VENDOR PURCHASE STATEMENT"
        elements = self._get_shop_header_elements(title_text)

        styles = getSampleStyleSheet()
        
        # Secondary info
        date_str = f"Date Range: {_clean(d_from)} to {_clean(d_to)}"
        elements.append(Paragraph(
            f"<b>Supplier:</b> {_clean(vendor_name)}    |    {date_str}",
            ParagraphStyle("SubInfo", parent=styles["Normal"], fontSize=11, textColor=colors.HexColor("#333333"), alignment=1)
        ))
        elements.append(Spacer(1, 8 * mm))

        # 1. SUMMARY BOX
        summary_title_style = ParagraphStyle(
            "SummaryTitle",
            parent=styles["Normal"],
            fontSize=10,
            textColor=colors.white,
            alignment=1,
            fontName="Helvetica-Bold",
        )
        summary_value_style = ParagraphStyle(
            "SummaryValue",
            parent=styles["Normal"],
            fontSize=16,
            textColor=colors.white,
            alignment=1,
            fontName="Helvetica-Bold",
        )

        summary_data = [
            [Paragraph("TOTAL SPEND", summary_title_style), 
             Paragraph("TOTAL ORDERS", summary_title_style),
             Paragraph("ITEMS PROCURED", summary_title_style)],
            [Paragraph(f"Rs. {total_amount:,.2f}", summary_value_style), 
             Paragraph(str(len(po_data)), summary_value_style), 
             Paragraph(str(total_items), summary_value_style)]
        ]
        
        summary_table = Table(summary_data, colWidths=[60*mm, 60*mm, 60*mm])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor("#17a2b8")), # Cyan/Teal for Spend
            ('BACKGROUND', (1, 0), (1, -1), colors.HexColor("#6c757d")), # Grey for Orders
            ('BACKGROUND', (2, 0), (2, -1), colors.HexColor("#fd7e14")), # Orange for Items
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.white),
        ]))
        
        elements.append(summary_table)
        elements.append(Spacer(1, 10 * mm))

        # 2. DATA TABLE
        headers = ["Date", "PO ID", "Status", "Items", "Amount (Rs.)"]
        data = [headers]

        for row in po_data:
            try:
                # row: (id, date, status, item_count, total)
                data.append([
                    _clean(row[1])[:10], # Date
                    _clean(row[0]),      # PO ID
                    _clean(row[2]),      # Status
                    str(row[3]),         # Items
                    f"{_safe_float(row[4]):,.2f}" if len(row) > 4 else "0.00",
                ])
            except Exception as e:
                app_logger.warning(f"Vendor Statement PDF row error: {e}")
                continue

        if len(data) == 1:
            data.append(["-"] * len(headers))

        col_widths = [35 * mm, 45 * mm, 30 * mm, 25 * mm, 45 * mm]
        extra = [
            ("ALIGN", (3, 0), (4, -1), "RIGHT"),
        ]
        t = Table(data, colWidths=col_widths, repeatRows=1)
        t.setStyle(_make_table_style(colors.HexColor("#17a2b8"), extra))

        elements.append(t)

        try:
            doc.build(elements)
            app_logger.info(f"Vendor Statement PDF saved: {file_path}")
            return True, file_path
        except Exception as e:
            app_logger.error(f"Failed to generate Vendor Statement PDF: {e}")
            return False, str(e)
