from PyQt6.QtWidgets import (QWidget, QGridLayout, QVBoxLayout, QLabel, QFrame, QHBoxLayout,
                             QScrollArea, QPushButton, QSizePolicy)
from PyQt6.QtCore import Qt, QTimer, QPointF
from PyQt6.QtGui import QColor, QFont, QPainter, QLinearGradient, QRadialGradient, QPen, QBrush
import ui_theme
from styles import (COLOR_ACCENT_CYAN, COLOR_ACCENT_AMBER, COLOR_ACCENT_GREEN, COLOR_ACCENT_RED,
                    DIM_MARGIN_STD, DIM_SPACING_STD, COLOR_BACKGROUND)
from custom_components import ReactorStatCard, TechCard, TopPerformerWidget
import datetime
import math

try:
    from PyQt6.QtCharts import (QChart, QChartView, QLineSeries, QAreaSeries,
                                QCategoryAxis, QValueAxis)
    CHARTS_AVAILABLE = True
except ImportError:
    CHARTS_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# Live Dues Monitor Panel
# ─────────────────────────────────────────────────────────────────────────────
class DuesMonitorWidget(QFrame):
    """Premium dark-teal dues panel with per-invoice WhatsApp reminders."""

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self._shop_name = "SpareParts Pro"
        self._setup_ui()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start(60_000)

    # ── frame style ────────────────────────────────────────────────────────────
    def _setup_ui(self):
        self.setObjectName("DuesMonitor")
        self.setStyleSheet("""
            QFrame#DuesMonitor {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 rgba(5,18,30,0.97),
                    stop:1 rgba(8,25,40,0.93));
                border: 1px solid rgba(0,188,212,0.40);
                border-radius: 14px;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        # ── Header ─────────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        hdr.setSpacing(8)

        self._dot = QLabel("●")
        self._dot.setStyleSheet(ui_theme.get_page_title_style())
        self._dot_state = True
        self._dot_timer = QTimer(self)
        self._dot_timer.timeout.connect(self._blink)
        self._dot_timer.start(800)

        title = QLabel("OUTSTANDING DUES")
        title.setStyleSheet(
            "color:#00bcd4; font-size:13px; font-weight:900;"
            " letter-spacing:2.5px; font-family:'Segoe UI';"
            " border:none; background:transparent;"
        )

        self.lbl_summary = QLabel("—")
        self.lbl_summary.setStyleSheet(
            "color:rgba(255,180,0,0.85); font-size:11px;"
            " border:none; background:transparent;"
        )

        btn_refresh = QPushButton("↻  Refresh")
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.setStyleSheet("""
            QPushButton {
                background: rgba(0,188,212,0.10);
                color: #00bcd4;
                border: 1px solid rgba(0,188,212,0.35);
                border-radius: 6px;
                font-size: 11px;
                font-weight: bold;
                padding: 0 10px;
            }
            QPushButton:hover { background: rgba(0,188,212,0.25); }
        """)
        btn_refresh.clicked.connect(self.refresh)

        hdr.addWidget(self._dot)
        hdr.addWidget(title)
        hdr.addStretch()
        hdr.addWidget(self.lbl_summary)
        hdr.addSpacing(10)
        hdr.addWidget(btn_refresh)
        root.addLayout(hdr)

        # thin separator
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: rgba(0,188,212,0.20); border:none;")
        root.addWidget(sep)

        # ── Column label row ───────────────────────────────────────────────────
        col_hdr = QHBoxLayout()
        col_hdr.setContentsMargins(8, 0, 8, 0)
        col_hdr.setSpacing(0)
        _CH = ("color:#00bcd4; font-size:9px; font-weight:bold;"
               " letter-spacing:1px; border:none; background:transparent;")
        for txt, stretch in [("INVOICE", 1), ("CUSTOMER", 2), ("MOBILE", 1),
                              ("TOTAL", 1), ("DUE", 1), ("DATE", 1), ("", 1)]:
            lbl = QLabel(txt)
            lbl.setStyleSheet(_CH)
            lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            col_hdr.addWidget(lbl, stretch)
        root.addLayout(col_hdr)

        # ── Scrollable card list ────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: rgba(0,188,212,0.05);
                width: 5px; border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: rgba(0,188,212,0.35);
                border-radius: 3px; min-height: 20px;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical { height: 0; }
        """)
        scroll.setMaximumHeight(200)

        self._cards_container = QWidget()
        self._cards_container.setStyleSheet("background:transparent;")
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(4)
        self._cards_layout.addStretch()
        scroll.setWidget(self._cards_container)
        root.addWidget(scroll)

        # ── Footer ─────────────────────────────────────────────────────────────
        foot_sep = QFrame()
        foot_sep.setFixedHeight(1)
        foot_sep.setStyleSheet("background: rgba(0,188,212,0.12); border:none;")
        root.addWidget(foot_sep)

        foot = QHBoxLayout()
        self.lbl_total_due = QLabel("TOTAL DUE  ₹ 0.00")
        self.lbl_total_due.setStyleSheet(
            "color:#ff6b6b; font-size:14px; font-weight:bold;"
            " border:none; background:transparent;"
        )
        self.lbl_count = QLabel("")
        self.lbl_count.setStyleSheet(
            "color:rgba(0,188,212,0.70); font-size:11px;"
            " border:none; background:transparent;"
        )
        self.lbl_oldest = QLabel("")
        self.lbl_oldest.setStyleSheet(
            "color:rgba(255,180,0,0.75); font-size:10px;"
            " border:none; background:transparent;"
        )
        foot.addWidget(self.lbl_total_due)
        foot.addStretch()
        foot.addWidget(self.lbl_oldest)
        foot.addSpacing(16)
        foot.addWidget(self.lbl_count)
        root.addLayout(foot)

    def _blink(self):
        self._dot_state = not self._dot_state
        self._dot.setVisible(self._dot_state)

    # ── per-row card ───────────────────────────────────────────────────────────
    def _make_card(self, inv_id, customer, mobile, total, due, raw_date):
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: rgba(0,188,212,0.06);
                border: 1px solid rgba(0,188,212,0.18);
                border-radius: 8px;
            }
            QFrame:hover {
                background: rgba(0,188,212,0.12);
                border: 1px solid rgba(0,188,212,0.38);
            }
        """)
        row = QHBoxLayout(card)
        row.setContentsMargins(8, 6, 8, 6)
        row.setSpacing(0)

        _V = "color:#e0f7fa; font-size:11px; border:none; background:transparent;"
        _R = "color:#ff6b6b; font-size:12px; font-weight:bold; border:none; background:transparent;"
        _D = "color:rgba(255,180,0,0.80); font-size:10px; border:none; background:transparent;"

        def _lbl(txt, style=_V, align=Qt.AlignmentFlag.AlignLeft, stretch=1):
            l = QLabel(txt)
            l.setStyleSheet(style)
            l.setAlignment(align | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(l, stretch)

        _lbl(inv_id.replace("INV-", ""), stretch=1)
        _lbl(customer[:18], stretch=2)
        _lbl(mobile, stretch=1)
        _lbl(f"Rs.{total:,.0f}", align=Qt.AlignmentFlag.AlignRight, stretch=1)
        _lbl(f"Rs.{due:,.2f}", style=_R, align=Qt.AlignmentFlag.AlignRight, stretch=1)
        _lbl(raw_date, style=_D, stretch=1)

        wa_btn = QPushButton("📲 Remind")
        wa_btn.setFixedHeight(26)
        wa_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        wa_btn.setToolTip(f"Send WhatsApp due reminder to {customer}")
        wa_btn.setStyleSheet("""
            QPushButton {
                background: rgba(37,211,102,0.15);
                color: #25d366;
                border: 1px solid rgba(37,211,102,0.40);
                border-radius: 6px;
                font-size: 10px;
                font-weight: bold;
                padding: 0 8px;
            }
            QPushButton:hover {
                background: rgba(37,211,102,0.30);
                border-color: rgba(37,211,102,0.70);
            }
            QPushButton:pressed { background: rgba(37,211,102,0.50); }
        """)
        wa_btn.clicked.connect(
            lambda _, m=mobile, c=customer, i=inv_id, t=total, d=due:
            self._send_reminder(m, c, i, t, d)
        )
        row.addWidget(wa_btn, 1)
        return card

    # ── WhatsApp reminder ─────────────────────────────────────────────────────
    def _send_reminder(self, mobile, customer, inv_id, total, due):
        from whatsapp_helper import send_invoice_msg
        from custom_components import ProMessageBox
        try:
            settings = self.db_manager.get_shop_settings()
            shop_name = settings.get("shop_name", self._shop_name)
        except Exception:
            shop_name = self._shop_name

        ok, msg = send_invoice_msg(
            mobile=mobile, customer_name=customer,
            invoice_id=inv_id, amount=total,
            pdf_path=None, shop_name=shop_name,
            due_amount=due,
        )
        if ok:
            ProMessageBox.information(
                self, "WhatsApp",
                f"Reminder opened for {customer}.\nPlease press Send in WhatsApp Web."
            )
        else:
            ProMessageBox.warning(self, "WhatsApp Error", msg or "Mobile number missing.")

    # ── refresh ────────────────────────────────────────────────────────────────
    def refresh(self):
        while self._cards_layout.count() > 1:
            item = self._cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        rows = self.db_manager.get_dues_detail(limit=50)
        total_due = 0.0
        oldest_date = None

        for r in rows:
            inv_id   = str(r[0])
            customer = str(r[1]) if r[1] else "Unknown"
            mobile   = str(r[2]) if r[2] else ""
            total    = float(r[3] or 0)
            due      = float(r[6] or 0)
            raw_date = str(r[8])[:10]

            total_due += due
            if oldest_date is None or raw_date < oldest_date:
                oldest_date = raw_date

            card = self._make_card(inv_id, customer, mobile, total, due, raw_date)
            self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)

        count = len(rows)
        self.lbl_total_due.setText(f"TOTAL DUE  Rs. {total_due:,.2f}")
        self.lbl_count.setText(f"{count} invoice{'s' if count != 1 else ''} pending")

        if oldest_date:
            self.lbl_oldest.setText(f"⏰ Oldest: {oldest_date}")
            self.lbl_summary.setText(
                f"Rs. {total_due:,.0f} across {count} customer{'s' if count != 1 else ''}"
            )
        else:
            self.lbl_summary.setText("✅ All clear — no dues!")
            self.lbl_oldest.setText("")


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard Page
# ─────────────────────────────────────────────────────────────────────────────
class DashboardPage(QWidget):
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self.ai_assistant = None
        self.bg_pulse = 0
        self.setup_ui()
        QTimer.singleShot(50, self._deferred_init)

    def _deferred_init(self):
        from ai_manager import AIAssistant
        self.ai_assistant = AIAssistant(self.db_manager)
        self.refresh_stats()
        self.dues_monitor.refresh()
        self.bg_timer = QTimer(self)
        self.bg_timer.timeout.connect(self._update_bg)
        self.bg_timer.start(100)

    def _update_bg(self):
        self.bg_pulse = (self.bg_pulse + 0.05) % (math.pi * 2)
        self.update()

    def load_data(self):
        self.refresh_stats()
        self.dues_monitor.refresh()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        grad = QRadialGradient(QPointF(rect.center()), float(rect.width()))
        grad.setColorAt(0, QColor("#050a14"))
        grad.setColorAt(1, QColor(COLOR_BACKGROUND))
        painter.setBrush(grad)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(rect)

        for i in range(3):
            cloud_c = QColor("#1e0032") if i % 2 == 0 else QColor("#000a32")
            cloud_c.setAlpha(int(20 + 10 * math.sin(self.bg_pulse + i)))
            x = rect.width() * (0.3 + 0.4 * math.sin(self.bg_pulse * 0.2 + i))
            y = rect.height() * (0.4 + 0.3 * math.cos(self.bg_pulse * 0.3 + i))
            gc = QRadialGradient(QPointF(x, y), rect.width() * 0.4)
            gc.setColorAt(0, cloud_c)
            gc.setColorAt(1, Qt.GlobalColor.transparent)
            painter.setBrush(gc)
            painter.drawRect(rect)

        painter.setOpacity(0.15)
        pen = QPen(QColor(COLOR_ACCENT_CYAN))
        pen.setWidth(1)
        painter.setPen(pen)
        step = 150
        for x in range(0, rect.width(), step):
            for y in range(0, rect.height(), step):
                if (x // step + y // step) % 3 == 0:
                    painter.drawEllipse(QPointF(x, y), 2, 2)
                    if x + step < rect.width():
                        painter.drawLine(x, y, x + step, y + step // 2)
                    if y + step < rect.height():
                        painter.drawLine(x, y, x - step // 2, y + step)
        painter.setOpacity(1.0)

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(DIM_MARGIN_STD, DIM_MARGIN_STD, DIM_MARGIN_STD, DIM_MARGIN_STD)
        self.main_layout.setSpacing(DIM_SPACING_STD)

        header = QLabel("DASHBOARD COMMAND CENTER")
        header.setStyleSheet(
            f"font-size:22px; font-weight:900; color:{COLOR_ACCENT_CYAN};"
            " letter-spacing:3px; font-family:'Segoe UI'; background:transparent;"
        )
        self.main_layout.addWidget(header)

        self.grid = QGridLayout()
        self.grid.setSpacing(10)
        self.main_layout.addLayout(self.grid)

        # Row 0 — stat cards
        self.card_parts = ReactorStatCard("Unique Parts",      "0",    COLOR_ACCENT_CYAN)
        self.card_stock = ReactorStatCard("Total Stock",       "0",    COLOR_ACCENT_GREEN)
        self.card_low   = ReactorStatCard("Critical Alerts",   "0",    COLOR_ACCENT_RED)
        
        # Make card_low clickable
        self.card_low.setCursor(Qt.CursorShape.PointingHandCursor)
        self.card_low.mousePressEvent = self.open_low_stock_dialog
        
        self.card_value = ReactorStatCard("Inventory Value",   "Rs. 0", COLOR_ACCENT_AMBER)
        self.card_today = ReactorStatCard("Today's Net Sales", "Rs. 0", COLOR_ACCENT_CYAN)
        self.grid.addWidget(self.card_parts, 0, 0)
        self.grid.addWidget(self.card_stock, 0, 1)
        self.grid.addWidget(self.card_low,   0, 2)
        self.grid.addWidget(self.card_value, 0, 3)
        self.grid.addWidget(self.card_today, 0, 4)

        # Row 1 left — top parts
        self.top_parts_widget = TopPerformerWidget("TOP SELLING PARTS", "🚀")
        self.grid.addWidget(self.top_parts_widget, 1, 0, 1, 1)

        # Row 1 center — financial cards stacked
        self.lbl_rev  = QLabel("Rs. 0.00")
        self.lbl_exp  = QLabel("Rs. 0.00")
        self.lbl_prof = QLabel("Rs. 0.00")
        self.card_revenue = TechCard("REVENUE",    self.lbl_rev,  COLOR_ACCENT_GREEN)
        self.card_expense = TechCard("EXPENSES",   self.lbl_exp,  COLOR_ACCENT_RED)
        self.card_profit  = TechCard("NET PROFIT", self.lbl_prof, COLOR_ACCENT_CYAN)
        fin_container = QWidget()
        fin_vbox = QVBoxLayout(fin_container)
        fin_vbox.setContentsMargins(0, 0, 0, 0)
        fin_vbox.setSpacing(5)
        fin_vbox.addWidget(self.card_revenue)
        fin_vbox.addWidget(self.card_expense)
        fin_vbox.addWidget(self.card_profit)
        fin_vbox.addStretch()
        self.grid.addWidget(fin_container, 1, 1, 1, 1)

        # Row 1 right — chart (3 cols)
        if CHARTS_AVAILABLE:
            chart_container = QFrame()
            chart_container.setStyleSheet(
                "background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
                " stop:0 rgba(5,8,15,0.8),stop:1 rgba(2,4,8,0.6));"
                " border-radius:12px; border:1px solid rgba(0,242,255,0.15);"
            )
            cl = QVBoxLayout(chart_container)
            self.chart_view = QChartView()
            self.chart_view.setRenderHint(self.chart_view.renderHints().Antialiasing)
            self.chart_view.setBackgroundBrush(QColor("#121212"))
            self.chart_view.setStyleSheet("background-color:transparent;")
            tl = QLabel("SALES TREND — NET REVENUE (7 DAYS)")
            tl.setStyleSheet(
                f"color:{COLOR_ACCENT_CYAN}; font-family:'Orbitron';"
                " font-weight:bold; letter-spacing:1px; border:none; background:transparent;"
            )
            cl.addWidget(tl)
            cl.addWidget(self.chart_view)
            self.grid.addWidget(chart_container, 1, 2, 1, 3)

        # Row 2 — Dues Monitor (full width)
        self.dues_monitor = DuesMonitorWidget(self.db_manager, self)
        self.grid.addWidget(self.dues_monitor, 2, 0, 1, 5)

    def refresh_stats(self):
        inv = self.db_manager.get_dashboard_stats()
        self.card_parts.set_value(str(inv['total_parts']))
        self.card_stock.set_value(f"{float(inv['total_stock_qty']):.2f}")
        self.card_low.set_value(str(inv['low_stock_count']))
        self.card_value.set_value(f"Rs. {inv['total_inventory_value']:,.0f}")

        fin = self.db_manager.get_financial_summary()
        self.lbl_rev.setText(f"Rs. {fin['revenue']:,.2f}")
        self.lbl_exp.setText(f"Rs. {fin['expenses']:,.2f}")
        self.lbl_prof.setText(f"Rs. {fin['net_profit']:,.2f}")

        try:
            today_str = datetime.date.today().strftime("%Y-%m-%d")
            td = self.db_manager.get_sales_by_date_range(today_str, today_str)
            self.card_today.set_value(f"Rs. {td[0][1]:,.0f}" if td else "Rs. 0")
        except Exception:
            self.card_today.set_value("Rs. 0")

        today = datetime.date.today()
        start = today - datetime.timedelta(days=30)
        top_parts = self.db_manager.get_top_selling_parts(
            start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")
        )
        self.top_parts_widget.set_items([(p[1], f"{p[2]} sold") for p in top_parts])

        if CHARTS_AVAILABLE:
            ts = today - datetime.timedelta(days=6)
            trend = self.db_manager.get_sales_by_date_range(
                ts.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")
            )
            self.update_chart(trend)

    def update_chart(self, trend_data):
        series = QLineSeries()
        max_val = 0
        for i, row in enumerate(trend_data):
            v = max(float(row[1]), 0)
            series.append(i, v)
            if v > max_val:
                max_val = v

        area = QAreaSeries(series)
        gradient = QLinearGradient(0, 0, 0, 400)
        c = QColor(COLOR_ACCENT_CYAN)
        c.setAlpha(150)
        gradient.setColorAt(0.0, c)
        gradient.setColorAt(1.0, Qt.GlobalColor.transparent)
        area.setBrush(QBrush(gradient))
        area.setPen(QPen(QColor(COLOR_ACCENT_CYAN), 2))

        chart = QChart()
        chart.addSeries(area)
        chart.setBackgroundVisible(False)
        chart.setPlotAreaBackgroundVisible(False)
        chart.legend().setVisible(False)

        axisX = QCategoryAxis()
        for i, row in enumerate(trend_data):
            d = datetime.datetime.strptime(row[0], "%Y-%m-%d")
            axisX.append(d.strftime("%d %b"), i)
        axisX.setLabelsColor(QColor("white"))
        axisX.setGridLineVisible(False)
        chart.addAxis(axisX, Qt.AlignmentFlag.AlignBottom)
        area.attachAxis(axisX)

        top_val = max(max_val * 1.2, 1000)
        axisY = QCategoryAxis()
        step = max(int(top_val / 5), 1)
        for tick in range(0, int(top_val) + step, step):
            axisY.append(f"{tick//1000}K" if tick >= 1000 else str(tick), tick)
        axisY.setRange(0, top_val)
        axisY.setLabelsColor(QColor("white"))
        axisY.setGridLineColor(QColor(255, 255, 255, 30))
        chart.addAxis(axisY, Qt.AlignmentFlag.AlignLeft)
        area.attachAxis(axisY)

        self.chart_view.setChart(chart)

    def open_low_stock_dialog(self, event):
        from low_stock_dialog import LowStockDialog
        dlg = LowStockDialog(self.db_manager)
        dlg.exec()
