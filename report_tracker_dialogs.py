"""
Report Tracker Dialogs
======================
Two rich deep-dive dialogs for the Reports / Sales page:

  InvoiceTrackerDialog  — full invoice detail: items, payment, returns, PDF link
  CustomerHistoryDialog — customer lifetime view: stats, all invoices, visit chart

Fixes in this version:
  - CustomerHistoryDialog: All Invoices tab has totals footer + drill-down to InvoiceTracker
  - CustomerHistoryDialog: Analytics tab uses proper month labels
  - InvoiceTrackerDialog: Items tab has totals row at bottom
  - InvoiceTrackerDialog: Returns tab shows net revenue after refund
  - Improved banner/header visual across both dialogs
  - Context menu on CustomerHistoryDialog invoice table (View Invoice, Open PDF)
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTabWidget, QWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QScrollArea, QGridLayout,
    QAbstractItemView, QSizePolicy, QProgressBar, QMenu
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QAction
from PyQt6.QtCharts import (
    QChart, QChartView, QBarSeries, QBarSet,
    QValueAxis, QBarCategoryAxis
)

import json, os
import ui_theme
from styles import (
    COLOR_ACCENT_CYAN, COLOR_ACCENT_GREEN, COLOR_ACCENT_YELLOW,
    COLOR_ACCENT_RED, COLOR_TEXT_PRIMARY
)

# ─── shared stylesheet ────────────────────────────────────────────────────────

_DIALOG_SS = """
    QDialog {
        background-color: #06060f;
        color: #e0e0e0;
    }
    QTabWidget::pane {
        border: 1px solid #1a1a2e;
        background: #080812;
        top: -1px;
    }
    QTabBar::tab {
        background: #0d0d1e;
        color: #555;
        padding: 9px 22px;
        border: 1px solid #1a1a2e;
        border-bottom: none;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        margin-right: 3px;
        font-weight: bold;
        font-size: 11px;
        min-width: 100px;
    }
    QTabBar::tab:selected {
        background: #080812;
        color: #00e5ff;
        border-top: 2px solid #00e5ff;
    }
    QTabBar::tab:hover:!selected {
        background: #111128;
        color: #aaa;
    }
    QScrollArea { border: none; background: transparent; }
    QScrollBar:vertical {
        background: #0a0a18; width: 5px; border: none;
    }
    QScrollBar::handle:vertical {
        background: #2a2a4e; border-radius: 2px; min-height: 20px;
    }
    QScrollBar::handle:vertical:hover { background: #00e5ff55; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
    QTableWidget {
        gridline-color: transparent;
        outline: none;
        border: none;
    }
    QTableWidget::item:hover { background: rgba(0,229,255,0.06); }
    QTableWidget::item:selected {
        background: rgba(0,229,255,0.15);
        color: #fff;
    }
    QHeaderView::section {
        background: #0d0d1e;
        color: #555;
        border: none;
        border-bottom: 1px solid #1a1a2e;
        padding: 6px 8px;
        font-size: 10px;
        font-weight: bold;
        letter-spacing: 1px;
    }
"""


# ─── shared helper widgets ────────────────────────────────────────────────────

def _info_card(label, value, color=COLOR_ACCENT_CYAN, min_width=0):
    frame = QFrame()
    frame.setStyleSheet(f"""
        QFrame {{
            background: rgba(0,0,0,0.4);
            border: 1px solid {color}44;
            border-radius: 8px;
        }}
        QFrame:hover {{
            border: 1px solid {color}88;
            background: rgba(0,0,0,0.55);
        }}
    """)
    if min_width:
        frame.setMinimumWidth(min_width)
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(12, 8, 12, 8)
    lay.setSpacing(3)
    t = QLabel(label.upper())
    t.setStyleSheet("color:#555; font-size:9px; font-weight:bold; letter-spacing:1px; border:none; background:transparent;")
    v = QLabel(str(value))
    v.setStyleSheet(f"color:{color}; font-size:15px; font-weight:bold; border:none; background:transparent;")
    v.setWordWrap(True)
    lay.addWidget(t)
    lay.addWidget(v)
    return frame


def _section_header(text, color=COLOR_ACCENT_CYAN):
    f = QFrame()
    f.setStyleSheet(f"background:transparent; border:none; border-bottom: 1px solid {color}33;")
    lay = QHBoxLayout(f)
    lay.setContentsMargins(0, 6, 0, 6)
    l = QLabel(text)
    l.setStyleSheet(f"color:{color}; font-size:12px; font-weight:bold; letter-spacing:0.5px; border:none; background:transparent;")
    lay.addWidget(l)
    lay.addStretch()
    return f


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
    t.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    return t


def _ti(text, color=None,
        align=Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft):
    item = QTableWidgetItem(str(text))
    item.setTextAlignment(align)
    if color:
        item.setForeground(QColor(color))
    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
    return item


def _close_btn(dialog):
    btn = QPushButton("✕  Close")
    btn.setFixedHeight(34)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(ui_theme.get_cancel_button_style())
    btn.clicked.connect(dialog.accept)
    return btn


def _hex_to_rgb(hex_color):
    h = hex_color.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"{r},{g},{b}"


def _banner(title, subtitle, badge_text, badge_color, status_text, status_color):
    """Reusable premium top banner."""
    frame = QFrame()
    frame.setStyleSheet(f"""
        QFrame {{
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #0d0d22, stop:0.4 #0a1828, stop:1 #0d0d22);
            border-bottom: 2px solid {badge_color}33;
        }}
    """)
    frame.setFixedHeight(76)
    bl = QHBoxLayout(frame)
    bl.setContentsMargins(20, 12, 20, 12)
    bl.setSpacing(0)

    badge = QLabel(badge_text)
    badge.setStyleSheet(f"""
        color:{badge_color}; background:rgba({_hex_to_rgb(badge_color)},0.12);
        border:1px solid {badge_color}55; border-radius:7px;
        font-size:11px; font-weight:bold; padding:5px 12px;
    """)
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

    info_col = QVBoxLayout()
    info_col.setSpacing(2)
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet("color:white; font-size:19px; font-weight:bold; border:none; background:transparent;")
    sub_lbl = QLabel(subtitle)
    sub_lbl.setStyleSheet("color:#666; font-size:10px; font-weight:bold; border:none; background:transparent;")
    info_col.addWidget(title_lbl)
    info_col.addWidget(sub_lbl)

    status = QLabel(status_text)
    status.setStyleSheet(f"""
        color:{status_color}; background:rgba({_hex_to_rgb(status_color)},0.10);
        border:1px solid {status_color}44; border-radius:6px;
        font-size:11px; font-weight:bold; padding:5px 14px;
    """)
    status.setAlignment(Qt.AlignmentFlag.AlignCenter)

    bl.addWidget(badge)
    bl.addSpacing(14)
    bl.addLayout(info_col)
    bl.addStretch()
    bl.addWidget(status)
    return frame


def _footer(dialog, extra_widgets=None):
    footer = QFrame()
    footer.setStyleSheet("background: #07070e; border-top: 1px solid #1a1a2e;")
    fl = QHBoxLayout(footer)
    fl.setContentsMargins(16, 8, 16, 8)
    if extra_widgets:
        for w in extra_widgets:
            fl.addWidget(w)
    fl.addStretch()
    fl.addWidget(_close_btn(dialog))
    return footer


def _totals_frame(items, bg="#0a0a18"):
    """Build a slim horizontal totals strip below a table."""
    frame = QFrame()
    frame.setStyleSheet(f"""
        QFrame {{
            background: {bg};
            border-top: 1px solid #1a1a2e;
            border-radius: 0 0 6px 6px;
        }}
    """)
    lay = QHBoxLayout(frame)
    lay.setContentsMargins(16, 8, 16, 8)
    lay.setSpacing(0)
    for i, (label, value, color) in enumerate(items):
        if i > 0:
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.VLine)
            sep.setStyleSheet("color:#1a1a2e; background:#1a1a2e; max-width:1px;")
            lay.addWidget(sep)
            lay.addSpacing(16)
        lbl = QLabel(label)
        lbl.setStyleSheet("color:#444; font-size:10px; font-weight:bold; border:none; background:transparent;")
        val = QLabel(str(value))
        val.setStyleSheet(f"color:{color}; font-size:13px; font-weight:bold; border:none; background:transparent;")
        vlay = QVBoxLayout()
        vlay.setSpacing(1)
        vlay.setContentsMargins(0, 0, 0, 0)
        vlay.addWidget(lbl)
        vlay.addWidget(val)
        lay.addLayout(vlay)
        lay.addSpacing(24)
    lay.addStretch()
    return frame


# ═══════════════════════════════════════════════════════════════════════════════
#  INTERNAL helper — open a nested InvoiceTrackerDialog from any dialog
# ═══════════════════════════════════════════════════════════════════════════════

def _open_invoice_tracker_for_id(db_manager, invoice_id, parent):
    """Fetch row from DB and open InvoiceTrackerDialog."""
    try:
        conn = db_manager.get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                i.date, i.invoice_id, i.customer_name, i.items_count, i.total_amount,
                i.json_items, i.invoice_id,
                (SELECT COUNT(*) FROM returns r WHERE r.invoice_id = i.invoice_id),
                COALESCE(i.payment_cash, 0), COALESCE(i.payment_upi, 0),
                COALESCE(i.payment_due, 0), COALESCE(i.payment_mode, 'CASH'),
                (SELECT COALESCE(SUM(refund_amount), 0) FROM returns r WHERE r.invoice_id = i.invoice_id)
            FROM invoices i WHERE i.invoice_id = ?
        """, (str(invoice_id),))
        row = cur.fetchone()
        conn.close()
        if row:
            dlg = InvoiceTrackerDialog(db_manager, row, parent=parent)
            dlg.exec()
        else:
            from custom_components import ProMessageBox
            ProMessageBox.warning(parent, "Not Found", f"Invoice #{invoice_id} not found.")
    except Exception as e:
        from custom_components import ProMessageBox
        ProMessageBox.critical(parent, "Error", str(e))


def _open_pdf_for_id(invoice_id, parent):
    """Open the PDF for a given invoice ID."""
    try:
        from path_utils import get_app_data_path  # type: ignore
        pdf_path = os.path.join(get_app_data_path("invoices"), f"{invoice_id}.pdf")
        if os.path.exists(pdf_path):
            os.startfile(pdf_path)
        else:
            from custom_components import ProMessageBox
            ProMessageBox.warning(parent, "Not Found", f"PDF not found:\n{pdf_path}")
    except Exception as e:
        from custom_components import ProMessageBox
        ProMessageBox.critical(parent, "Error", str(e))


# ═══════════════════════════════════════════════════════════════════════════════
#  1.  INVOICE TRACKER DIALOG
# ═══════════════════════════════════════════════════════════════════════════════

class InvoiceTrackerDialog(QDialog):
    """
    Full invoice deep-dive.
    invoice_row (tuple from get_sales_report):
      [0]  date          [1]  invoice_id   [2]  customer_name
      [3]  items_count   [4]  total_amount [5]  json_items
      [6]  invoice_id    [7]  return_count [8]  payment_cash
      [9]  payment_upi   [10] payment_due  [11] payment_mode
      [12] total_refund
    """

    def __init__(self, db_manager, invoice_row, parent=None):
        super().__init__(parent)
        self.db  = db_manager
        self.row = invoice_row
        self.inv_id = str(invoice_row[1])
        self.cust   = str(invoice_row[2] or "Walk-in")

        # fetch extra invoice fields
        try:
            conn = self.db.get_connection()
            cur  = conn.cursor()
            cur.execute(
                "SELECT mobile, vehicle_model, reg_no, customer_gstin, discount "
                "FROM invoices WHERE invoice_id=?", (self.inv_id,)
            )
            full = cur.fetchone() or (None, None, None, None, 0)
            conn.close()
        except Exception:
            full = (None, None, None, None, 0)

        self.mobile   = str(full[0] or "—")
        self.vehicle  = str(full[1] or "—")
        self.reg_no   = str(full[2] or "—")
        self.gstin    = str(full[3] or "—")
        self.discount = float(full[4] or 0)

        self.pay_cash = float(invoice_row[8] or 0)
        self.pay_upi  = float(invoice_row[9] or 0)
        self.pay_due  = float(invoice_row[10] or 0)
        self.pay_mode = str(invoice_row[11] or "CASH")
        self.total    = float(invoice_row[4] or 0)
        self.refund   = float(invoice_row[12] or 0) if len(invoice_row) > 12 else 0.0

        mode_colors = {
            "CASH": COLOR_ACCENT_CYAN, "UPI": COLOR_ACCENT_GREEN,
            "SPLIT": "#f1c40f", "PARTIAL": "#ff9800", "DUE": COLOR_ACCENT_RED
        }
        self._mc = mode_colors.get(self.pay_mode.upper(), "#aaa")

        self.setWindowTitle(f"🧾 Invoice Tracker  —  #{self.inv_id}")
        self.setMinimumSize(920, 640)
        self.setStyleSheet(_DIALOG_SS)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Status badge
        if self.pay_due > 0.01:
            status_txt = f"⚠ DUE  ₹ {self.pay_due:,.2f}"
            status_col = COLOR_ACCENT_RED
        else:
            status_txt = "✅  FULLY PAID"
            status_col = COLOR_ACCENT_GREEN

        root.addWidget(_banner(
            self.cust,
            f"Invoice #{self.inv_id}  •  {str(invoice_row[0])[:16]}",
            self.pay_mode,
            self._mc,
            status_txt, status_col
        ))

        tabs = QTabWidget()
        tabs.setDocumentMode(False)
        root.addWidget(tabs)
        tabs.addTab(self._build_overview(),  "📋  OVERVIEW")
        tabs.addTab(self._build_items(),     "🛒  ITEMS")
        tabs.addTab(self._build_returns(),   "↩️  RETURNS")

        # Footer with PDF button
        btn_pdf = QPushButton("📄  Open Invoice PDF")
        btn_pdf.setFixedHeight(32)
        btn_pdf.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_pdf.setStyleSheet(ui_theme.get_neon_action_button())
        btn_pdf.clicked.connect(lambda: _open_pdf_for_id(self.inv_id, self))
        root.addWidget(_footer(self, [btn_pdf]))

    # ── Overview tab ──────────────────────────────────────────────────────────
    def _build_overview(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        w = QWidget()
        scroll.setWidget(w)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        # Payment summary cards
        cards = QHBoxLayout()
        cards.setSpacing(10)
        cards.addWidget(_info_card("Total Amount",  f"₹ {self.total:,.2f}",   COLOR_ACCENT_YELLOW))
        cards.addWidget(_info_card("Discount",       f"₹ {self.discount:,.2f}",
                                   "#666" if self.discount == 0 else "#f1c40f"))
        cards.addWidget(_info_card("Cash Paid",      f"₹ {self.pay_cash:,.2f}", COLOR_ACCENT_CYAN))
        cards.addWidget(_info_card("UPI Paid",       f"₹ {self.pay_upi:,.2f}",  COLOR_ACCENT_GREEN))
        cards.addWidget(_info_card("Due",            f"₹ {self.pay_due:,.2f}",
                                   COLOR_ACCENT_RED if self.pay_due > 0.01 else "#333"))
        cards.addWidget(_info_card("Refunded",       f"₹ {self.refund:,.2f}",
                                   COLOR_ACCENT_RED if self.refund > 0 else "#333"))
        layout.addLayout(cards)

        # Payment progress bar
        if self.total > 0:
            collected = self.pay_cash + self.pay_upi
            pct = min(collected / self.total, 1.0)
            bar_color = COLOR_ACCENT_GREEN if self.pay_due <= 0.01 else "#ff9800"

            prog = QProgressBar()
            prog.setRange(0, 1000)
            prog.setValue(int(pct * 1000))
            prog.setTextVisible(False)
            prog.setFixedHeight(10)
            prog.setStyleSheet(f"""
                QProgressBar {{ background: #1a1a2e; border: none; border-radius: 5px; }}
                QProgressBar::chunk {{ background: {bar_color}; border-radius: 5px; }}
            """)

            if pct >= 1.0:
                hint_text = f"  ✅ Fully collected  ₹ {collected:,.2f}"
            else:
                hint_text = f"  ₹ {collected:,.2f} collected of ₹ {self.total:,.2f}  ({int(pct*100)}%)"
            hint = QLabel(hint_text)
            hint.setStyleSheet(f"color:{bar_color}; font-size:10px; font-weight:bold; border:none; background:transparent;")
            layout.addWidget(prog)
            layout.addWidget(hint)

        # Invoice details grid
        layout.addWidget(_section_header("🪪  INVOICE DETAILS"))
        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(8)

        def gv(v, fb="—"):
            s = str(v or "").strip()
            return s if s and s not in ("None", "") else fb

        fields = [
            ("Invoice ID",     gv(self.inv_id)),
            ("Date / Time",    gv(self.row[0])),
            ("Customer",       gv(self.cust)),
            ("Mobile",         gv(self.mobile)),
            ("Vehicle",        gv(self.vehicle)),
            ("Reg No.",        gv(self.reg_no)),
            ("Customer GSTIN", gv(self.gstin)),
            ("Payment Mode",   self.pay_mode),
            ("Items Count",    str(self.row[3] or 0)),
            ("Returns",        str(self.row[7] or 0)),
        ]

        for i, (lbl, val) in enumerate(fields):
            r, c = divmod(i, 2)
            l = QLabel(f"{lbl}:")
            l.setStyleSheet("color:#444; font-size:10px; font-weight:bold; border:none; background:transparent;")
            v = QLabel(val)
            v.setStyleSheet("color:#bbb; font-size:10px; border:none; background:transparent;")
            grid.addWidget(l, r, c * 2)
            grid.addWidget(v, r, c * 2 + 1)

        layout.addLayout(grid)
        layout.addStretch()
        return scroll

    # ── Items tab ─────────────────────────────────────────────────────────────
    def _build_items(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # Parse cart from json_items
        cart = []
        try:
            raw = self.row[5]
            data = json.loads(raw) if raw else {}
            if isinstance(data, str):
                data = json.loads(data)
            if isinstance(data, list):
                cart = data
            elif isinstance(data, dict):
                cart = data.get("cart", [])
        except Exception:
            cart = []

        total_qty    = sum(float(item.get("qty", 0)) for item in cart)
        total_amt    = sum(float(item.get("total", 0)) for item in cart)
        labour_total = sum(float(item.get("total", 0)) for item in cart
                           if any(k in str(item.get("name", "")).upper()
                                  for k in ("SERVICE", "LABOUR")))
        parts_total  = total_amt - labour_total

        # Summary cards
        cards = QHBoxLayout()
        cards.setSpacing(10)
        cards.addWidget(_info_card("Line Items",  str(len(cart)),             COLOR_ACCENT_CYAN))
        cards.addWidget(_info_card("Total Qty",   f"{int(total_qty)}",        COLOR_ACCENT_YELLOW))
        cards.addWidget(_info_card("Parts Total", f"₹ {parts_total:,.2f}",   COLOR_ACCENT_GREEN))
        cards.addWidget(_info_card("Labour / Svc",f"₹ {labour_total:,.2f}",  "#a78bfa"))
        cards.addWidget(_info_card("Grand Total", f"₹ {total_amt:,.2f}",     COLOR_ACCENT_YELLOW))
        layout.addLayout(cards)

        # Table
        t = _styled_table(["SL", "PART ID", "PART NAME", "QTY", "MRP/UNIT", "DISC %", "FINAL TOTAL"])
        t.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        t.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        t.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        t.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        t.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        if cart:
            t.setRowCount(len(cart))
            for i, item in enumerate(cart):
                nm = str(item.get("name", "")).upper()
                is_labour = "SERVICE" in nm or "LABOUR" in nm
                row_color = "#a78bfa" if is_labour else None

                part_id  = item.get("sys_id", item.get("id", "—"))
                part_name = item.get("name", "—")
                qty       = float(item.get("qty", 0))
                mrp_unit  = float(item.get("base_price", item.get("price", 0)))
                total     = float(item.get("total", 0))
                eff_disc  = ((1 - (total / (mrp_unit * qty))) * 100
                             if mrp_unit > 0 and qty > 0 else 0.0)
                eff_disc  = max(0.0, round(eff_disc, 1))

                t.setItem(i, 0, _ti(str(i + 1), "#555",
                                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter))
                t.setItem(i, 1, _ti(str(part_id), row_color or COLOR_ACCENT_CYAN,
                                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter))
                t.setItem(i, 2, _ti(str(part_name), row_color))
                t.setItem(i, 3, _ti(str(int(qty)) if qty == int(qty) else f"{qty:g}",
                                    COLOR_ACCENT_YELLOW,
                                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter))
                t.setItem(i, 4, _ti(f"₹ {mrp_unit:,.2f}", "#ccc",
                                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight))
                t.setItem(i, 5, _ti(f"{eff_disc:.1f}%" if eff_disc > 0 else "—",
                                    "#f1c40f" if eff_disc > 0 else "#333",
                                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter))
                t.setItem(i, 6, _ti(f"₹ {total:,.2f}", COLOR_ACCENT_GREEN,
                                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight))
        else:
            t.setRowCount(1)
            ph = QTableWidgetItem("No item data available for this invoice")
            ph.setForeground(QColor("#444"))
            ph.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            t.setItem(0, 0, ph)
            t.setSpan(0, 0, 1, 7)

        layout.addWidget(t)

        # Totals footer strip
        if cart:
            layout.addWidget(_totals_frame([
                ("TOTAL ITEMS",  str(len(cart)),              "#888"),
                ("TOTAL QTY",    str(int(total_qty)),          COLOR_ACCENT_YELLOW),
                ("PARTS",        f"₹ {parts_total:,.2f}",     COLOR_ACCENT_GREEN),
                ("LABOUR / SVC", f"₹ {labour_total:,.2f}",    "#a78bfa"),
                ("GRAND TOTAL",  f"₹ {total_amt:,.2f}",       COLOR_ACCENT_YELLOW),
            ]))
        return w

    # ── Returns tab ───────────────────────────────────────────────────────────
    def _build_returns(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        try:
            conn = self.db.get_connection()
            cur  = conn.cursor()
            cur.execute("""
                SELECT r.return_id, r.part_id, p.part_name, r.quantity,
                       r.refund_amount, r.return_date, r.reason
                FROM returns r
                LEFT JOIN parts p ON r.part_id = p.part_id
                WHERE r.invoice_id = ?
                ORDER BY r.return_date DESC
            """, (self.inv_id,))
            rows = cur.fetchall()
            conn.close()
        except Exception:
            rows = []

        total_refund = sum(float(r[4] or 0) for r in rows)
        total_qty    = sum(int(r[3] or 0) for r in rows)
        net_revenue  = self.total - total_refund

        # Summary cards
        cards = QHBoxLayout()
        cards.setSpacing(10)
        cards.addWidget(_info_card("Invoice Total",   f"₹ {self.total:,.2f}",
                                   COLOR_ACCENT_YELLOW))
        cards.addWidget(_info_card("Return Events",   str(len(rows)),
                                   COLOR_ACCENT_RED if rows else "#333"))
        cards.addWidget(_info_card("Units Returned",  str(total_qty),
                                   COLOR_ACCENT_YELLOW if rows else "#333"))
        cards.addWidget(_info_card("Total Refunded",  f"₹ {total_refund:,.2f}",
                                   COLOR_ACCENT_RED if total_refund > 0 else "#333"))
        cards.addWidget(_info_card("Net Revenue",     f"₹ {net_revenue:,.2f}",
                                   COLOR_ACCENT_GREEN if net_revenue >= 0 else COLOR_ACCENT_RED))
        layout.addLayout(cards)

        t = _styled_table(["RETURN ID", "PART", "PART NAME", "QTY", "REFUND", "DATE", "REASON"])
        t.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        t.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        if rows:
            t.setRowCount(len(rows))
            for i, (rid, pid, pname, qty, refund, rdate, reason) in enumerate(rows):
                t.setItem(i, 0, _ti(str(rid or ""),    COLOR_ACCENT_CYAN,
                                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter))
                t.setItem(i, 1, _ti(str(pid or ""),    "#aaa"))
                t.setItem(i, 2, _ti(str(pname or "Unknown")))
                t.setItem(i, 3, _ti(str(int(qty or 0)), COLOR_ACCENT_YELLOW,
                                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter))
                t.setItem(i, 4, _ti(f"₹ {float(refund or 0):,.2f}", COLOR_ACCENT_RED,
                                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight))
                t.setItem(i, 5, _ti(str(rdate or "")[:10], "#aaa"))
                t.setItem(i, 6, _ti(str(reason or "—")))
        else:
            t.setRowCount(1)
            ph = QTableWidgetItem("No returns for this invoice  ✅")
            ph.setForeground(QColor("#00ff88"))
            ph.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            t.setItem(0, 0, ph)
            t.setSpan(0, 0, 1, 7)

        layout.addWidget(t)

        if rows:
            layout.addWidget(_totals_frame([
                ("UNITS RETURNED",  str(total_qty),            COLOR_ACCENT_YELLOW),
                ("TOTAL REFUNDED",  f"₹ {total_refund:,.2f}",  COLOR_ACCENT_RED),
                ("NET REVENUE",     f"₹ {net_revenue:,.2f}",
                 COLOR_ACCENT_GREEN if net_revenue >= 0 else COLOR_ACCENT_RED),
            ]))
        return w


# ═══════════════════════════════════════════════════════════════════════════════
#  2.  CUSTOMER HISTORY DIALOG
# ═══════════════════════════════════════════════════════════════════════════════

class CustomerHistoryDialog(QDialog):
    """
    Full customer deep-dive.
    customer_name: str — looked up from the table row.
    """

    def __init__(self, db_manager, customer_name, parent=None):
        super().__init__(parent)
        self.db   = db_manager
        self.cust = str(customer_name or "Walk-in")

        self.setWindowTitle(f"💎 Customer Profile  —  {self.cust}")
        self.setMinimumSize(980, 680)
        self.setStyleSheet(_DIALOG_SS)

        # ── Fetch all data ───────────────────────────────────────────────────
        try:
            conn = self.db.get_connection()
            cur  = conn.cursor()
            cur.execute("""
                SELECT i.invoice_id, i.date, i.total_amount, i.items_count,
                       COALESCE(i.payment_cash,0), COALESCE(i.payment_upi,0),
                       COALESCE(i.payment_due,0),  COALESCE(i.payment_mode,'CASH'),
                       i.vehicle_model, i.reg_no, i.mobile,
                       (SELECT COALESCE(SUM(refund_amount),0) FROM returns r WHERE r.invoice_id=i.invoice_id)
                FROM invoices i
                WHERE LOWER(TRIM(i.customer_name)) = LOWER(TRIM(?))
                ORDER BY i.date DESC
            """, (self.cust,))
            self.invoices = cur.fetchall()

            cur.execute("""
                SELECT COUNT(*), COALESCE(SUM(r.refund_amount),0)
                FROM returns r
                JOIN invoices i ON r.invoice_id=i.invoice_id
                WHERE LOWER(TRIM(i.customer_name)) = LOWER(TRIM(?))
            """, (self.cust,))
            ret_row = cur.fetchone() or (0, 0)

            cur.execute("""
                SELECT s.part_id, p.part_name, SUM(s.quantity) as tot
                FROM sales s
                JOIN invoices i ON s.invoice_id=i.invoice_id
                LEFT JOIN parts p ON s.part_id=p.part_id
                WHERE LOWER(TRIM(i.customer_name)) = LOWER(TRIM(?))
                GROUP BY s.part_id
                ORDER BY tot DESC
                LIMIT 1
            """, (self.cust,))
            fav = cur.fetchone()
            conn.close()
        except Exception:
            self.invoices = []
            ret_row = (0, 0)
            fav = None

        self.ret_count  = int(ret_row[0] or 0)
        self.ret_amount = float(ret_row[1] or 0)
        self.fav_part   = str(fav[1] or fav[0]) if fav else "—"

        self.total_spent   = sum(float(r[2] or 0) for r in self.invoices)
        self.total_due     = sum(float(r[6] or 0) for r in self.invoices)
        self.net_rev       = self.total_spent - self.ret_amount
        self.invoice_count = len(self.invoices)
        self.avg_order     = self.total_spent / self.invoice_count if self.invoice_count else 0
        self.total_cash    = sum(float(r[4] or 0) for r in self.invoices)
        self.total_upi     = sum(float(r[5] or 0) for r in self.invoices)

        latest = self.invoices[0] if self.invoices else None
        self.mobile  = str(latest[10] or "—") if latest else "—"
        self.vehicle = str(latest[8] or "—")  if latest else "—"

        status_txt = "⚠  HAS DUES" if self.total_due > 0.01 else "✅  NO DUES"
        status_col = COLOR_ACCENT_RED if self.total_due > 0.01 else COLOR_ACCENT_GREEN

        # ── Build layout ─────────────────────────────────────────────────────
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(_banner(
            self.cust,
            f"Mobile: {self.mobile}  •  {self.invoice_count} Invoice{'s' if self.invoice_count != 1 else ''}",
            "CUSTOMER",
            COLOR_ACCENT_GREEN,
            status_txt, status_col
        ))

        tabs = QTabWidget()
        tabs.setDocumentMode(False)
        root.addWidget(tabs)
        tabs.addTab(self._build_profile(),   "👤  PROFILE")
        tabs.addTab(self._build_invoices(),  "🧾  ALL INVOICES")
        tabs.addTab(self._build_analytics(), "📊  ANALYTICS")
        root.addWidget(_footer(self))

    # ── Profile tab ───────────────────────────────────────────────────────────
    def _build_profile(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        w = QWidget()
        scroll.setWidget(w)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        # Row 1 — financials
        cards1 = QHBoxLayout()
        cards1.setSpacing(10)
        cards1.addWidget(_info_card("Total Invoices",  str(self.invoice_count),       COLOR_ACCENT_CYAN))
        cards1.addWidget(_info_card("Total Spent",     f"₹ {self.total_spent:,.0f}", COLOR_ACCENT_YELLOW))
        cards1.addWidget(_info_card("Net Revenue",     f"₹ {self.net_rev:,.0f}",     COLOR_ACCENT_GREEN))
        cards1.addWidget(_info_card("Avg Order Value", f"₹ {self.avg_order:,.0f}",   "#a78bfa"))
        layout.addLayout(cards1)

        # Row 2 — dues / returns / fav
        cards2 = QHBoxLayout()
        cards2.setSpacing(10)
        cards2.addWidget(_info_card("Cash Collected",  f"₹ {self.total_cash:,.0f}",  COLOR_ACCENT_CYAN))
        cards2.addWidget(_info_card("UPI Collected",   f"₹ {self.total_upi:,.0f}",   COLOR_ACCENT_GREEN))
        cards2.addWidget(_info_card("Pending Dues",    f"₹ {self.total_due:,.0f}",
                                    COLOR_ACCENT_RED if self.total_due > 0.01 else "#333"))
        cards2.addWidget(_info_card("Returns",
                                    f"{self.ret_count}  (₹ {self.ret_amount:,.0f})",
                                    COLOR_ACCENT_RED if self.ret_count > 0 else "#333"))
        layout.addLayout(cards2)

        # Row 3 — fav part + vehicle
        cards3 = QHBoxLayout()
        cards3.setSpacing(10)
        cards3.addWidget(_info_card("Favourite Part", self.fav_part[:28], "#f1c40f"))
        cards3.addWidget(_info_card("Vehicle",        self.vehicle,        "#a78bfa"))
        layout.addLayout(cards3)

        # Identity grid
        layout.addWidget(_section_header("🪪  CONTACT DETAILS"))
        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(8)

        vehicles = list(dict.fromkeys(
            str(r[8]) for r in self.invoices if r[8] and str(r[8]).strip() not in ("None", "—", "")
        ))
        reg_nos = list(dict.fromkeys(
            str(r[9]) for r in self.invoices if r[9] and str(r[9]).strip() not in ("None", "—", "")
        ))

        fields = [
            ("Name",        self.cust),
            ("Mobile",      self.mobile),
            ("Vehicles",    ", ".join(vehicles) if vehicles else "—"),
            ("Reg Numbers", ", ".join(reg_nos)  if reg_nos  else "—"),
            ("First Visit", str(self.invoices[-1][1] if self.invoices else "—")[:10]),
            ("Last Visit",  str(self.invoices[0][1]  if self.invoices else "—")[:10]),
        ]
        for i, (lbl, val) in enumerate(fields):
            r, c = divmod(i, 2)
            l = QLabel(f"{lbl}:")
            l.setStyleSheet("color:#444; font-size:10px; font-weight:bold; border:none; background:transparent;")
            v = QLabel(val)
            v.setStyleSheet("color:#bbb; font-size:10px; border:none; background:transparent;")
            v.setWordWrap(True)
            grid.addWidget(l, r, c * 2)
            grid.addWidget(v, r, c * 2 + 1)

        layout.addLayout(grid)
        layout.addStretch()
        return scroll

    # ── All Invoices tab ──────────────────────────────────────────────────────
    def _build_invoices(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 4)
        layout.setSpacing(0)

        # Instruction hint
        hint = QLabel("💡  Double-click any row to view full invoice details  •  Right-click for more actions")
        hint.setStyleSheet("color:#444; font-size:10px; font-style:italic; padding: 0 4px 6px 4px; border:none; background:transparent;")
        layout.addWidget(hint)

        t = _styled_table(["DATE", "INVOICE ID", "ITEMS", "AMOUNT", "CASH", "UPI", "DUE", "MODE"])
        t.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        t.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        t.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        t.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        self._inv_table = t  # keep ref for context menu

        mode_colors = {
            "CASH": COLOR_ACCENT_CYAN,  "UPI": COLOR_ACCENT_GREEN,
            "SPLIT": "#f1c40f",          "PARTIAL": "#ff9800",
            "DUE": COLOR_ACCENT_RED
        }

        if self.invoices:
            t.setRowCount(len(self.invoices))
            for i, inv in enumerate(self.invoices):
                inv_id, date_, total, items, cash, upi, due, mode = (
                    inv[0], inv[1], inv[2], inv[3], inv[4], inv[5], inv[6], inv[7])
                mc = mode_colors.get(str(mode).upper(), "#aaa")
                if float(due or 0) > 0.01:
                    mc = mode_colors["PARTIAL"] if (cash or upi) else mode_colors["DUE"]

                t.setItem(i, 0, _ti(str(date_ or "")[:16], "#888"))
                t.setItem(i, 1, _ti(str(inv_id or ""), COLOR_ACCENT_CYAN))
                t.setItem(i, 2, _ti(str(items or 0), "#888",
                                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter))
                t.setItem(i, 3, _ti(f"₹ {float(total or 0):,.2f}", COLOR_ACCENT_YELLOW,
                                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight))
                t.setItem(i, 4, _ti(f"₹ {float(cash or 0):,.2f}", COLOR_ACCENT_CYAN,
                                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight))
                t.setItem(i, 5, _ti(f"₹ {float(upi or 0):,.2f}", COLOR_ACCENT_GREEN,
                                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight))
                t.setItem(i, 6, _ti(f"₹ {float(due or 0):,.2f}",
                                    COLOR_ACCENT_RED if float(due or 0) > 0.01 else "#333",
                                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight))
                t.setItem(i, 7, _ti(str(mode or "CASH").upper(), mc,
                                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter))
        else:
            t.setRowCount(1)
            ph = QTableWidgetItem("No invoices found for this customer")
            ph.setForeground(QColor("#444"))
            ph.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            t.setItem(0, 0, ph)
            t.setSpan(0, 0, 1, 8)

        # ── Wire interactions ────────────────────────────────────────────────
        t.doubleClicked.connect(self._on_inv_table_double_click)
        t.customContextMenuRequested.connect(self._on_inv_table_context_menu)

        layout.addWidget(t)

        # ── Totals footer ────────────────────────────────────────────────────
        if self.invoices:
            layout.addWidget(_totals_frame([
                ("INVOICES",      str(self.invoice_count),           "#888"),
                ("TOTAL SPENT",   f"₹ {self.total_spent:,.2f}",     COLOR_ACCENT_YELLOW),
                ("CASH",          f"₹ {self.total_cash:,.2f}",       COLOR_ACCENT_CYAN),
                ("UPI",           f"₹ {self.total_upi:,.2f}",        COLOR_ACCENT_GREEN),
                ("PENDING DUES",  f"₹ {self.total_due:,.2f}",
                 COLOR_ACCENT_RED if self.total_due > 0.01 else "#333"),
                ("NET REVENUE",   f"₹ {self.net_rev:,.2f}",          COLOR_ACCENT_GREEN),
            ]))
        return w

    def _on_inv_table_double_click(self, index):
        """Open InvoiceTrackerDialog for the double-clicked row."""
        row = index.row()
        item = self._inv_table.item(row, 1)   # col 1 = INVOICE ID
        if item:
            inv_id = item.text().strip()
            _open_invoice_tracker_for_id(self.db, inv_id, self)

    def _on_inv_table_context_menu(self, pos):
        index = self._inv_table.indexAt(pos)
        if not index.isValid():
            return
        row = index.row()
        item = self._inv_table.item(row, 1)
        if not item:
            return
        inv_id = item.text().strip()

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #0d0d1e;
                color: #00e5ff;
                border: 1px solid #00e5ff44;
                border-radius: 6px;
            }
            QMenu::item { padding: 8px 24px 8px 12px; font-size: 12px; font-weight: bold; }
            QMenu::item:selected { background: rgba(0,229,255,0.15); }
            QMenu::separator { background: #1a1a2e; height: 1px; margin: 4px 0; }
        """)

        act_view = QAction(f"🔍  View Full Invoice  #{inv_id}", self)
        act_view.triggered.connect(lambda: _open_invoice_tracker_for_id(self.db, inv_id, self))
        menu.addAction(act_view)

        menu.addSeparator()

        act_pdf = QAction("📄  Open Invoice PDF", self)
        act_pdf.triggered.connect(lambda: _open_pdf_for_id(inv_id, self))
        menu.addAction(act_pdf)

        menu.exec(self._inv_table.viewport().mapToGlobal(pos))

    # ── Analytics tab ─────────────────────────────────────────────────────────
    def _build_analytics(self):
        # Wrap in a scroll area so chart + table are never hidden
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        w = QWidget()
        scroll.setWidget(w)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        layout.addWidget(_section_header("📅  MONTHLY SPEND HISTORY"))

        # Build monthly data — last 12 months
        monthly: dict = {}
        for inv in self.invoices:
            month = str(inv[1] or "")[:7]   # YYYY-MM
            if month:
                monthly[month] = monthly.get(month, 0.0) + float(inv[2] or 0)

        sorted_months = sorted(monthly.keys())[-12:]

        chart = QChart()
        chart.setBackgroundBrush(QColor("#080812"))
        chart.setPlotAreaBackgroundBrush(QColor("#0a0a1a"))
        chart.setPlotAreaBackgroundVisible(True)
        chart.legend().setVisible(False)
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        chart.layout().setContentsMargins(0, 0, 0, 0)
        chart.setTitle("")

        if sorted_months:
            bar_set = QBarSet("Spend")
            bar_set.setColor(QColor(COLOR_ACCENT_GREEN))
            bar_set.setBorderColor(QColor(COLOR_ACCENT_GREEN))
            cats = []
            max_v = 0.0
            for m in sorted_months:
                v = monthly[m]
                bar_set.append(v)
                # Human readable label: Apr'04 → Apr 04 or just Mon-YY
                try:
                    from datetime import datetime as _dt
                    cats.append(_dt.strptime(m, "%Y-%m").strftime("%b '%y"))
                except Exception:
                    cats.append(m[-5:])
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
            ay.setRange(0, max_v * 1.2 or 1000)
            ay.setLabelsColor(QColor("#666"))
            ay.setGridLineColor(QColor("#1a1a2e"))
            ay.setTickCount(5)
            ay.setLabelFormat("₹%.0f")
            chart.addAxis(ay, Qt.AlignmentFlag.AlignLeft)
            series.attachAxis(ay)
        else:
            e = QBarSet("No Data")
            e.append(0)
            e.setColor(QColor("#1a1a2e"))
            es = QBarSeries()
            es.append(e)
            chart.addSeries(es)
            no_data = QLabel("No purchase history to display")
            no_data.setStyleSheet("color:#444; font-style:italic; border:none; background:transparent;")
            no_data.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(no_data)

        cv = QChartView(chart)
        cv.setRenderHint(QPainter.RenderHint.Antialiasing)
        # KEY FIX: fixed height so chart cannot push the parts table off-screen
        cv.setFixedHeight(185)
        cv.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        cv.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(cv)

        # Parts purchased table
        layout.addWidget(_section_header("🛒  PARTS PURCHASED (All Time)"))
        try:
            conn = self.db.get_connection()
            cur  = conn.cursor()
            cur.execute("""
                SELECT s.part_id, COALESCE(p.part_name, s.part_id),
                       SUM(s.quantity) as total_qty,
                       SUM(s.quantity * s.price_at_sale) as total_revenue,
                       COUNT(DISTINCT s.invoice_id) as times
                FROM sales s
                JOIN invoices i ON s.invoice_id=i.invoice_id
                LEFT JOIN parts p ON s.part_id=p.part_id
                WHERE LOWER(TRIM(i.customer_name)) = LOWER(TRIM(?))
                GROUP BY s.part_id
                ORDER BY total_revenue DESC
                LIMIT 20
            """, (self.cust,))
            part_rows = cur.fetchall()
            conn.close()
        except Exception:
            part_rows = []

        t = _styled_table(["PART ID", "PART NAME", "TOTAL QTY", "TOTAL SPEND", "ORDERS"])
        t.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        t.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        t.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        t.setMinimumHeight(120)

        if part_rows:
            row_h = 28
            header_h = 30
            ideal_h = min(len(part_rows) * row_h + header_h + 4, 320)
            t.setFixedHeight(ideal_h)
            t.setRowCount(len(part_rows))
            for i, (pid, pname, qty, rev, times) in enumerate(part_rows):
                t.setRowHeight(i, row_h)
                t.setItem(i, 0, _ti(str(pid or ""),               COLOR_ACCENT_CYAN))
                t.setItem(i, 1, _ti(str(pname or "—")))
                t.setItem(i, 2, _ti(str(int(qty or 0)),            COLOR_ACCENT_YELLOW,
                                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter))
                t.setItem(i, 3, _ti(f"Rs. {float(rev or 0):,.2f}", COLOR_ACCENT_GREEN,
                                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight))
                t.setItem(i, 4, _ti(str(int(times or 0)),          "#888",
                                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter))
        else:
            t.setFixedHeight(56)
            t.setRowCount(1)
            ph = QTableWidgetItem("No detailed parts data available")
            ph.setForeground(QColor("#444"))
            ph.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            t.setItem(0, 0, ph)
            t.setSpan(0, 0, 1, 5)

        layout.addWidget(t)

        # Analytics totals footer
        if part_rows:
            total_parts_spend = sum(float(r[3] or 0) for r in part_rows)
            total_parts_qty   = sum(int(r[2] or 0) for r in part_rows)
            layout.addWidget(_totals_frame([
                ("UNIQUE PARTS",   str(len(part_rows)),               "#888"),
                ("TOTAL QTY",      str(total_parts_qty),              COLOR_ACCENT_YELLOW),
                ("TOTAL SPEND",    f"Rs. {total_parts_spend:,.2f}",   COLOR_ACCENT_GREEN),
            ]))

        layout.addStretch(1)
        return scroll
