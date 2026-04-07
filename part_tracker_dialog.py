"""
Part Tracker Dialog  —  Individual Part Deep-Dive
Shows all info for one part: profile, full sale history, purchase orders,
and financial summary with a mini revenue chart.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTabWidget, QWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QProgressBar, QScrollArea, QGridLayout,
    QAbstractItemView, QSizePolicy
)
from PyQt6.QtCore import Qt, QDate, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis, QBarCategoryAxis, QBarSeries, QBarSet

import ui_theme
from styles import (
    COLOR_ACCENT_CYAN, COLOR_ACCENT_GREEN, COLOR_ACCENT_YELLOW,
    COLOR_ACCENT_RED, COLOR_TEXT_PRIMARY
)


# ─────────────────── tiny helpers ───────────────────────────────────────────

def _lbl(text, color="#cccccc", size=10, bold=False):
    l = QLabel(str(text))
    weight = "bold" if bold else "normal"
    l.setStyleSheet(
        f"color:{color}; font-size:{size}px; font-weight:{weight};"
        " border:none; background:transparent;"
    )
    l.setWordWrap(True)
    return l


def _section_header(text, color=COLOR_ACCENT_CYAN):
    f = QFrame()
    f.setStyleSheet(f"background:transparent; border:none; border-bottom: 1px solid {color}44;")
    lay = QHBoxLayout(f)
    lay.setContentsMargins(0, 4, 0, 4)
    l = QLabel(text)
    l.setStyleSheet(f"color:{color}; font-size:12px; font-weight:bold; border:none; background:transparent;")
    lay.addWidget(l)
    lay.addStretch()
    return f


def _info_card(label, value, color=COLOR_ACCENT_CYAN):
    """A small labelled value card."""
    frame = QFrame()
    frame.setStyleSheet(f"""
        QFrame {{
            background: rgba(0,0,0,0.35);
            border: 1px solid {color}33;
            border-radius: 6px;
        }}
    """)
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(10, 6, 10, 6)
    lay.setSpacing(2)
    lbl_title = QLabel(label.upper())
    lbl_title.setStyleSheet("color:#666; font-size:9px; font-weight:bold; border:none; background:transparent;")
    lbl_val = QLabel(str(value))
    lbl_val.setStyleSheet(f"color:{color}; font-size:14px; font-weight:bold; border:none; background:transparent;")
    lay.addWidget(lbl_title)
    lay.addWidget(lbl_val)
    return frame


def _styled_table(cols):
    t = QTableWidget()
    t.setColumnCount(len(cols))
    t.setHorizontalHeaderLabels(cols)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.verticalHeader().setVisible(False)
    t.setStyleSheet(ui_theme.get_table_style())
    t.setShowGrid(False)
    t.setAlternatingRowColors(False)
    return t


def _table_item(text, color=None, align=Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft):
    item = QTableWidgetItem(str(text))
    item.setTextAlignment(align)
    if color:
        item.setForeground(QColor(color))
    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
    return item


# ─────────────────── main dialog ────────────────────────────────────────────

class PartTrackerDialog(QDialog):
    """
    Full part tracking dialog.

    row_data layout (matching get_all_parts):
      0:part_id  1:part_name  2:description  3:unit_price  4:qty
      5:rack     6:col        7:reorder      8:vendor      9:compat
      10:category 11:added_date 12:last_ordered 13:added_by 14:last_edited_date
      15:hsn_code 16:gst_rate  17:last_cost
    """

    def __init__(self, db_manager, row_data, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.rd = row_data
        self.part_id   = str(row_data[0])
        self.part_name = str(row_data[1])

        self.setWindowTitle(f"🔍 Part Tracker  —  {self.part_name}")
        self.setMinimumSize(900, 640)
        self.setStyleSheet("""
            QDialog {
                background-color: #080812;
                color: #e0e0e0;
            }
            QTabWidget::pane {
                border: 1px solid #1a1a2e;
                background: #0a0a18;
                top: -1px;
            }
            QTabBar::tab {
                background: #0f0f1e;
                color: #666;
                padding: 8px 20px;
                border: 1px solid #1a1a2e;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
                font-weight: bold;
                font-size: 11px;
            }
            QTabBar::tab:selected {
                background: #0a0a18;
                color: #00e5ff;
                border-top: 2px solid #00e5ff;
            }
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                background: #0a0a18; width: 6px; border: none;
            }
            QScrollBar::handle:vertical {
                background: #1a1a2e; border-radius: 3px;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Banner ───────────────────────────────────────────────────────────
        banner = QFrame()
        banner.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #0d0d20, stop:0.5 #0a1a2a, stop:1 #0d0d20);
                border-bottom: 2px solid #00e5ff33;
            }
        """)
        banner.setFixedHeight(72)
        bl = QHBoxLayout(banner)
        bl.setContentsMargins(20, 10, 20, 10)

        id_badge = QLabel(self.part_id)
        id_badge.setStyleSheet("""
            color: #00e5ff; background: rgba(0,229,255,0.1);
            border: 1px solid #00e5ff44; border-radius: 6px;
            font-size: 11px; font-weight: bold; padding: 4px 10px;
        """)

        name_lbl = QLabel(self.part_name)
        name_lbl.setStyleSheet("color: white; font-size: 18px; font-weight: bold; border:none; background:transparent;")

        cat_lbl = QLabel(str(row_data[10] or "Uncategorized").upper())
        cat_lbl.setStyleSheet("""
            color: #888; background: rgba(255,255,255,0.05);
            border: 1px solid #333; border-radius: 4px;
            font-size: 9px; font-weight:bold; padding: 3px 8px;
        """)

        rd = row_data
        qty = int(rd[4] or 0)
        reorder = int(rd[7] or 5)
        stock_color = COLOR_ACCENT_RED if qty <= reorder else COLOR_ACCENT_GREEN
        stock_lbl = QLabel(f"{'⚠ LOW' if qty<=reorder else '✅ OK'}  Qty: {qty}")
        stock_lbl.setStyleSheet(f"""
            color: {stock_color}; background: {stock_color}18;
            border: 1px solid {stock_color}44; border-radius: 5px;
            font-size: 11px; font-weight: bold; padding: 4px 12px;
        """)

        bl.addWidget(id_badge)
        bl.addSpacing(12)
        bl.addWidget(name_lbl)
        bl.addSpacing(10)
        bl.addWidget(cat_lbl)
        bl.addStretch()
        bl.addWidget(stock_lbl)

        root.addWidget(banner)

        # ── Tabs ─────────────────────────────────────────────────────────────
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)

        self.tabs.addTab(self._build_profile_tab(),   "📋 PROFILE")
        self.tabs.addTab(self._build_sales_tab(),     "🧾 SALE HISTORY")
        self.tabs.addTab(self._build_purchase_tab(),  "📦 PURCHASE HISTORY")
        self.tabs.addTab(self._build_finance_tab(),   "💹 FINANCIALS")

        # ── Footer ───────────────────────────────────────────────────────────
        footer = QFrame()
        footer.setStyleSheet("background: #08080f; border-top: 1px solid #1a1a2e;")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(16, 8, 16, 8)
        fl.addStretch()
        btn_close = QPushButton("✕  Close")
        btn_close.setFixedHeight(32)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(ui_theme.get_cancel_button_style())
        btn_close.clicked.connect(self.accept)
        fl.addWidget(btn_close)
        root.addWidget(footer)

    # ── Tab 1: Profile ───────────────────────────────────────────────────────
    def _build_profile_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        w = QWidget()
        scroll.setWidget(w)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        rd = self.rd
        qty     = int(rd[4] or 0)
        reorder = int(rd[7] or 5)
        mrp     = float(rd[3] or 0)
        cost    = float(rd[17] or 0) if len(rd) > 17 else 0.0
        margin  = ((mrp - cost) / mrp * 100) if mrp > 0 and cost > 0 else 0.0

        # ── Top info cards ────────────────────────────────────────────────
        cards_row = QHBoxLayout()
        cards_row.setSpacing(10)
        cards_row.addWidget(_info_card("MRP / Sale Price",  f"₹ {mrp:,.2f}",   COLOR_ACCENT_YELLOW))
        cards_row.addWidget(_info_card("Last Cost Price",   f"₹ {cost:,.2f}" if cost else "N/A",  "#a78bfa"))
        cards_row.addWidget(_info_card("Gross Margin",      f"{margin:.1f}%" if margin else "N/A",  COLOR_ACCENT_GREEN))
        cards_row.addWidget(_info_card("Current Stock",     qty,               COLOR_ACCENT_CYAN))
        cards_row.addWidget(_info_card("Reorder Level",     reorder,           COLOR_ACCENT_RED if qty<=reorder else "#555"))
        layout.addLayout(cards_row)

        # ── Stock progress bar ────────────────────────────────────────────
        layout.addWidget(_section_header("📊 STOCK LEVEL"))
        prog_frame = QFrame()
        prog_frame.setStyleSheet("background:transparent; border:none;")
        prog_l = QVBoxLayout(prog_frame)
        prog_l.setContentsMargins(0, 0, 0, 0)
        prog_l.setSpacing(4)

        max_stock = max(qty, reorder) * 2 or 20
        pct = int(min(qty / max_stock, 1.0) * 100)
        bar_color = COLOR_ACCENT_RED if qty <= reorder else (COLOR_ACCENT_YELLOW if qty <= reorder * 2 else COLOR_ACCENT_GREEN)

        prog = QProgressBar()
        prog.setRange(0, 100)
        prog.setValue(pct)
        prog.setTextVisible(False)
        prog.setFixedHeight(12)
        prog.setStyleSheet(f"""
            QProgressBar {{ background: #1a1a2e; border: none; border-radius: 6px; }}
            QProgressBar::chunk {{ background: {bar_color}; border-radius: 6px; }}
        """)
        hint = QLabel(f"  {qty} in stock  /  Reorder at {reorder}")
        hint.setStyleSheet(f"color:{bar_color}; font-size:10px; border:none; background:transparent;")
        prog_l.addWidget(prog)
        prog_l.addWidget(hint)
        layout.addWidget(prog_frame)

        # ── Identity details ──────────────────────────────────────────────
        layout.addWidget(_section_header("🪪 PART IDENTITY"))
        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(8)

        def gv(value, fallback="N/A"):
            v = str(value or "").strip()
            return v if v and v not in ("None", "") else fallback

        fields = [
            ("Part ID",        gv(rd[0])),
            ("Part Name",      gv(rd[1])),
            ("Description",    gv(rd[2])),
            ("Category",       gv(rd[10])),
            ("Compatibility",  gv(rd[9])),
            ("Vendor",         gv(rd[8])),
            ("Location",       f"Rack {gv(rd[5])}, Col {gv(rd[6])}"),
            ("HSN Code",       gv(rd[15] if len(rd)>15 else "")),
            ("GST Rate",       f"{gv(rd[16] if len(rd)>16 else '')}%" if rd[16] else "N/A"),
            ("Added Date",     gv(rd[11], "Old Stock")),
            ("Added By",       gv(rd[13] if len(rd)>13 else "", "System")),
            ("Last Ordered",   gv(rd[12], "Never")),
            ("Last Edited",    gv(rd[14] if len(rd)>14 else "", "Never")),
        ]

        for i, (label, value) in enumerate(fields):
            row, col = divmod(i, 2)
            lbl = QLabel(f"{label}:")
            lbl.setStyleSheet("color:#555; font-size:10px; font-weight:bold; border:none; background:transparent;")
            val = QLabel(value)
            val.setStyleSheet("color:#ccc; font-size:10px; border:none; background:transparent;")
            val.setWordWrap(True)
            grid.addWidget(lbl, row, col * 2)
            grid.addWidget(val, row, col * 2 + 1)

        layout.addLayout(grid)
        layout.addStretch()
        return scroll

    # ── Tab 2: Sale History ──────────────────────────────────────────────────
    def _build_sales_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # Summary mini-cards
        try:
            conn = self.db.get_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT COUNT(*), SUM(quantity), SUM(quantity * price_at_sale),
                       MIN(sale_date), MAX(sale_date)
                FROM sales
                WHERE part_id = ?
            """, (self.part_id,))
            s = cur.fetchone()
            conn.close()
            total_txns  = int(s[0] or 0)
            total_qty   = float(s[1] or 0)
            total_rev   = float(s[2] or 0)
            first_sale  = str(s[3] or "—")[:10]
            last_sale   = str(s[4] or "—")[:10]
        except Exception:
            total_txns = total_qty = total_rev = 0
            first_sale = last_sale = "—"

        cards_row = QHBoxLayout()
        cards_row.setSpacing(10)
        cards_row.addWidget(_info_card("Total Transactions",   total_txns,           COLOR_ACCENT_CYAN))
        cards_row.addWidget(_info_card("Total Units Sold",     f"{int(total_qty)}",  COLOR_ACCENT_YELLOW))
        cards_row.addWidget(_info_card("Total Revenue",        f"₹ {total_rev:,.0f}", COLOR_ACCENT_GREEN))
        cards_row.addWidget(_info_card("First Sale",           first_sale,           "#a78bfa"))
        cards_row.addWidget(_info_card("Last Sale",            last_sale,            "#a78bfa"))
        layout.addLayout(cards_row)

        # Sales table
        t = _styled_table(["DATE", "INVOICE ID", "CUSTOMER", "QTY", "PRICE / UNIT", "TOTAL"])
        t.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        t.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        t.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        try:
            conn = self.db.get_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT s.sale_date, s.invoice_id, i.customer_name,
                       s.quantity, s.price_at_sale,
                       s.quantity * s.price_at_sale AS line_total
                FROM sales s
                LEFT JOIN invoices i ON s.invoice_id = i.invoice_id
                WHERE s.part_id = ?
                ORDER BY s.sale_date DESC
            """, (self.part_id,))
            rows = cur.fetchall()
            conn.close()
        except Exception:
            rows = []

        t.setRowCount(len(rows))
        for i, (dt, inv_id, cust, qty, price, total) in enumerate(rows):
            t.setItem(i, 0, _table_item(str(dt or "")[:16],           "#aaa"))
            t.setItem(i, 1, _table_item(str(inv_id or ""),            COLOR_ACCENT_CYAN))
            t.setItem(i, 2, _table_item(str(cust or "Walk-in")))
            t.setItem(i, 3, _table_item(str(int(qty or 0)),           COLOR_ACCENT_YELLOW,
                                        Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter))
            t.setItem(i, 4, _table_item(f"₹ {float(price or 0):,.2f}",  "#ccc",
                                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
            t.setItem(i, 5, _table_item(f"₹ {float(total or 0):,.2f}", COLOR_ACCENT_GREEN,
                                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))

        if not rows:
            t.setRowCount(1)
            placeholder = QTableWidgetItem("No sale records found for this part")
            placeholder.setForeground(QColor("#444"))
            placeholder.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            t.setItem(0, 0, placeholder)
            t.setSpan(0, 0, 1, 6)

        layout.addWidget(t)
        return w

    # ── Tab 3: Purchase History ──────────────────────────────────────────────
    def _build_purchase_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        try:
            conn = self.db.get_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT po.order_date, po.po_id, po.supplier_name, po.status,
                       pi.qty_ordered, pi.qty_received,
                       COALESCE(pi.landing_cost, pi.received_cost, pi.ordered_price, 0) AS unit_cost,
                       COALESCE(pi.landing_cost, pi.received_cost, pi.ordered_price, 0) * pi.qty_received AS line_total
                FROM po_items pi
                JOIN purchase_orders po ON pi.po_id = po.po_id
                WHERE pi.part_id = ?
                ORDER BY po.order_date DESC
            """, (self.part_id,))
            rows = cur.fetchall()

            # Summary
            cur.execute("""
                SELECT SUM(pi.qty_ordered), SUM(pi.qty_received),
                       SUM(COALESCE(pi.landing_cost, pi.received_cost, pi.ordered_price, 0) * pi.qty_received),
                       COUNT(DISTINCT po.po_id)
                FROM po_items pi
                JOIN purchase_orders po ON pi.po_id = po.po_id
                WHERE pi.part_id = ?
            """, (self.part_id,))
            sm = cur.fetchone()
            conn.close()
        except Exception:
            rows = []
            sm = (0, 0, 0, 0)

        total_ord, total_rcvd, total_cost, total_pos = (sm or (0,0,0,0))

        cards_row = QHBoxLayout()
        cards_row.setSpacing(10)
        cards_row.addWidget(_info_card("Purchase Orders",   int(total_pos or 0),               COLOR_ACCENT_CYAN))
        cards_row.addWidget(_info_card("Total Ordered",     int(total_ord or 0),               COLOR_ACCENT_YELLOW))
        cards_row.addWidget(_info_card("Total Received",    int(total_rcvd or 0),              COLOR_ACCENT_GREEN))
        cards_row.addWidget(_info_card("Total Spend",       f"₹ {float(total_cost or 0):,.0f}", "#a78bfa"))
        layout.addLayout(cards_row)

        t = _styled_table(["DATE", "PO ID", "SUPPLIER", "STATUS", "QTY ORD", "QTY RCV", "UNIT COST", "TOTAL"])
        t.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        t.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        t.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        t.setRowCount(len(rows) if rows else 1)

        if rows:
            status_colors = {
                "PENDING": "#ff9800", "PARTIAL": "#f1c40f",
                "RECEIVED": "#00ff88", "CANCELLED": "#ff4444"
            }
            for i, (dt, po_id, supplier, status, qty_o, qty_r, unit_cost, line_total) in enumerate(rows):
                sc = status_colors.get(str(status or "").upper(), "#aaa")
                t.setItem(i, 0, _table_item(str(dt or "")[:10],              "#aaa"))
                t.setItem(i, 1, _table_item(str(po_id or ""),                COLOR_ACCENT_CYAN))
                t.setItem(i, 2, _table_item(str(supplier or "")))
                t.setItem(i, 3, _table_item(str(status or "").upper(),       sc,
                                            Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter))
                t.setItem(i, 4, _table_item(str(int(qty_o or 0)),            COLOR_ACCENT_YELLOW,
                                            Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter))
                t.setItem(i, 5, _table_item(str(int(qty_r or 0)),            COLOR_ACCENT_GREEN,
                                            Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter))
                t.setItem(i, 6, _table_item(f"₹ {float(unit_cost or 0):,.2f}",  "#ccc",
                                            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
                t.setItem(i, 7, _table_item(f"₹ {float(line_total or 0):,.2f}", "#a78bfa",
                                            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
        else:
            ph = QTableWidgetItem("No purchase records found for this part")
            ph.setForeground(QColor("#444"))
            ph.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            t.setItem(0, 0, ph)
            t.setSpan(0, 0, 1, 8)

        layout.addWidget(t)
        return w

    # ── Tab 4: Financials ────────────────────────────────────────────────────
    def _build_finance_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # ── Fetch data ────────────────────────────────────────────────────
        try:
            conn = self.db.get_connection()
            cur = conn.cursor()

            # Monthly revenue
            cur.execute("""
                SELECT strftime('%Y-%m', sale_date) as month,
                       SUM(quantity) as units,
                       SUM(quantity * price_at_sale) as revenue
                FROM sales
                WHERE part_id = ?
                GROUP BY month
                ORDER BY month ASC
                LIMIT 12
            """, (self.part_id,))
            monthly = cur.fetchall()

            # Returns
            cur.execute("""
                SELECT COUNT(*), COALESCE(SUM(refund_amount),0), COALESCE(SUM(quantity),0)
                FROM returns WHERE part_id = ?
            """, (self.part_id,))
            ret = cur.fetchone()
            conn.close()
        except Exception:
            monthly = []
            ret = (0, 0, 0)

        ret_count = int(ret[0] or 0)
        ret_amount = float(ret[1] or 0)
        ret_qty = int(ret[2] or 0)

        mrp  = float(self.rd[3] or 0)
        cost = float(self.rd[17] or 0) if len(self.rd) > 17 else 0.0

        total_rev  = sum(float(r[2] or 0) for r in monthly)
        total_units = sum(int(r[1] or 0) for r in monthly)
        est_profit = (mrp - cost) * total_units if cost > 0 else 0.0
        net_rev    = total_rev - ret_amount

        # Summary cards
        cards_row = QHBoxLayout()
        cards_row.setSpacing(10)
        cards_row.addWidget(_info_card("Gross Revenue",   f"₹ {total_rev:,.0f}",    COLOR_ACCENT_GREEN))
        cards_row.addWidget(_info_card("Net Revenue",     f"₹ {net_rev:,.0f}",      COLOR_ACCENT_CYAN))
        cards_row.addWidget(_info_card("Est. Gross Profit", f"₹ {est_profit:,.0f}" if cost > 0 else "N/A",  "#a78bfa"))
        cards_row.addWidget(_info_card("Returns Value",   f"₹ {ret_amount:,.0f}",   COLOR_ACCENT_RED if ret_amount > 0 else "#444"))
        cards_row.addWidget(_info_card("Return Events",   f"{ret_count} ({ret_qty} units)", COLOR_ACCENT_RED if ret_count > 0 else "#444"))
        layout.addLayout(cards_row)

        # Monthly revenue bar chart
        layout.addWidget(_section_header("📅 MONTHLY REVENUE (Last 12 Months)"))
        chart = QChart()
        chart.setBackgroundBrush(QColor("#0a0a18"))
        chart.setPlotAreaBackgroundBrush(QColor("#0d0d1e"))
        chart.setPlotAreaBackgroundVisible(True)
        chart.legend().setVisible(False)
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        chart.layout().setContentsMargins(0, 0, 0, 0)

        if monthly:
            bar_set = QBarSet("Revenue")
            bar_set.setColor(QColor("#a78bfa"))
            bar_set.setBorderColor(QColor("#a78bfa"))
            cats = []
            max_v = 0.0
            for (month, units, revenue) in monthly:
                v = float(revenue or 0)
                bar_set.append(v)
                cats.append(str(month or "")[-7:])
                if v > max_v:
                    max_v = v

            series = QBarSeries()
            series.append(bar_set)
            chart.addSeries(series)

            ax = QBarCategoryAxis()
            ax.append(cats)
            ax.setLabelsColor(QColor("#666"))
            ax.setGridLineColor(QColor("#1a1a2e"))
            chart.addAxis(ax, Qt.AlignmentFlag.AlignBottom)
            series.attachAxis(ax)

            ay = QValueAxis()
            ay.setRange(0, max_v * 1.2 or 100)
            ay.setLabelsColor(QColor("#666"))
            ay.setGridLineColor(QColor("#1a1a2e"))
            ay.setTickCount(5)
            chart.addAxis(ay, Qt.AlignmentFlag.AlignLeft)
            series.attachAxis(ay)
        else:
            empty = QBarSet("No Data")
            empty.append(0)
            empty.setColor(QColor("#1a1a2e"))
            es = QBarSeries()
            es.append(empty)
            chart.addSeries(es)

        cv = QChartView(chart)
        cv.setRenderHint(QPainter.RenderHint.Antialiasing)
        cv.setMinimumHeight(200)
        cv.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(cv)

        return w
