from PyQt6.QtWidgets import (QWidget, QGridLayout, QVBoxLayout, QLabel, QFrame, QHBoxLayout)
from PyQt6.QtCore import Qt, QTimer, QPointF
from PyQt6.QtGui import QColor, QFont, QPainter, QLinearGradient, QRadialGradient, QPen, QBrush
from styles import (COLOR_ACCENT_CYAN, COLOR_ACCENT_AMBER, COLOR_ACCENT_GREEN, COLOR_ACCENT_RED, COLOR_SURFACE,
                    DIM_MARGIN_STD, DIM_SPACING_STD, COLOR_BACKGROUND)
from custom_components import ReactorStatCard, LiveTerminal, TechCard, TopPerformerWidget
import datetime
import math

# Try importing Charts, if unavailable, fallback gracefully
try:
    from PyQt6.QtCharts import QChart, QChartView, QPieSeries, QPieSlice, QLineSeries, QAreaSeries, QCategoryAxis, QValueAxis
    CHARTS_AVAILABLE = True
except ImportError:
    CHARTS_AVAILABLE = False
    print("Warning: PyQt6 Charts module not found. Charts will be disabled.")

class DashboardPage(QWidget):
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self.ai_assistant = None  # Will be loaded after UI renders
        self.bg_pulse = 0 # Initialize here for paintEvent
        
        self.setup_ui()
        
        # Defer heavy operations so the page renders instantly
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(50, self._deferred_init)

    def _deferred_init(self):
        """Load AI engine and stats after the UI has rendered."""
        from ai_manager import AIAssistant
        self.ai_assistant = AIAssistant(self.db_manager)
        if hasattr(self, 'terminal'):
            self.terminal.ai_assistant = self.ai_assistant
        self.refresh_stats()
        
        # Ambient update for background
        self.bg_timer = QTimer(self)
        self.bg_timer.timeout.connect(self._update_bg)
        self.bg_timer.start(100)

    def _update_bg(self):
        self.bg_pulse = (self.bg_pulse + 0.05) % (math.pi * 2)
        self.update()

    def paintEvent(self, event):
        """Draw the Nebulous Void with Neural Pathways."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 1. Base Gradient (Deep Void)
        rect = self.rect()
        grad = QRadialGradient(QPointF(rect.center()), float(rect.width()))
        grad.setColorAt(0, QColor("#050a14"))
        grad.setColorAt(1, QColor(COLOR_BACKGROUND))
        painter.setBrush(grad)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(rect)
        
        # 2. Subtle Nebula Clouds
        for i in range(3):
            cloud_c = QColor("#1e0032") if i % 2 == 0 else QColor("#000a32")
            alpha = int(20 + 10 * math.sin(self.bg_pulse + i))
            cloud_c.setAlpha(alpha)
            
            x = rect.width() * (0.3 + 0.4 * math.sin(self.bg_pulse * 0.2 + i))
            y = rect.height() * (0.4 + 0.3 * math.cos(self.bg_pulse * 0.3 + i))
            
            grad_cloud = QRadialGradient(QPointF(x, y), rect.width() * 0.4)
            grad_cloud.setColorAt(0, cloud_c)
            grad_cloud.setColorAt(1, Qt.GlobalColor.transparent)
            painter.setBrush(grad_cloud)
            painter.drawRect(rect)

        # 3. Neural Network Pathways (Faint lines)
        painter.setOpacity(0.15)
        pen = QPen(QColor(COLOR_ACCENT_CYAN))
        pen.setWidth(1)
        painter.setPen(pen)
        
        # Draw some geometric connections
        step = 150
        for x in range(0, rect.width(), step):
            for y in range(0, rect.height(), step):
                # Only draw if near a grid point
                if (x // step + y // step) % 3 == 0:
                     painter.drawEllipse(QPointF(x, y), 2, 2)
                     if x + step < rect.width():
                         painter.drawLine(x, y, x + step, y + step // 2)
                     if y + step < rect.height():
                         painter.drawLine(x, y, x - step // 2, y + step)
        painter.setOpacity(1.0)

    def load_data(self):
        """Called by Main Window refresh"""
        self.refresh_stats()

    def setup_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(DIM_MARGIN_STD, DIM_MARGIN_STD, DIM_MARGIN_STD, DIM_MARGIN_STD)
        self.main_layout.setSpacing(DIM_SPACING_STD)

        # Header
        header = QLabel("DASHBOARD COMMAND CENTER")
        header.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {COLOR_ACCENT_CYAN}; letter-spacing: 2px;")
        self.main_layout.addWidget(header)

        # 1. ARC REACTOR STATS (Grid)
        self.grid = QGridLayout()
        self.main_layout.addLayout(self.grid)
        
        # Row 0: Key Inventory Stats (Reactors) - STRICT SPEC VALUES
        self.card_parts = ReactorStatCard("Unique Parts", "619", COLOR_ACCENT_CYAN)
        self.card_stock = ReactorStatCard("Total Stock", "14451.5", COLOR_ACCENT_GREEN)
        self.card_low = ReactorStatCard("Critical Alerts", "150", COLOR_ACCENT_RED)
        self.card_value = ReactorStatCard("Total Value", "₹ 3,120,017", COLOR_ACCENT_AMBER)
        
        self.grid.addWidget(self.card_parts, 0, 0)
        self.grid.addWidget(self.card_stock, 0, 1)
        self.grid.addWidget(self.card_low, 0, 2)
        self.grid.addWidget(self.card_value, 0, 3)

        # Row 1: Top Movers & Sales Trend
        # Left: Top Selling Parts
        self.top_parts_widget = TopPerformerWidget("TOP SELLING PARTS", "🚀")
        self.grid.addWidget(self.top_parts_widget, 1, 0, 1, 1) # Span 1 col
        
        # Center: Financial Cards (Vertical Stack or smaller grid?)
        # Let's put financials in a column
        self.fin_layout = QVBoxLayout()
        self.lbl_rev = QLabel("₹ 9,633.20")
        self.lbl_exp = QLabel("₹ 455.00")
        self.lbl_prof = QLabel("₹ 9,178.20")
        
        self.card_revenue = TechCard("REVENUE", self.lbl_rev, COLOR_ACCENT_GREEN)
        self.card_expense = TechCard("EXPENSES", self.lbl_exp, COLOR_ACCENT_RED)
        self.card_profit = TechCard("NET PROFIT", self.lbl_prof, COLOR_ACCENT_CYAN)
        
        # We can stack these 3 tech cards in column 1
        fin_container = QWidget()
        fin_vbox = QVBoxLayout(fin_container)
        fin_vbox.setContentsMargins(0,0,0,0)
        fin_vbox.setSpacing(5)
        fin_vbox.addWidget(self.card_revenue)
        fin_vbox.addWidget(self.card_expense)
        fin_vbox.addWidget(self.card_profit)
        fin_vbox.addStretch()
        
        self.grid.addWidget(fin_container, 1, 1, 1, 1)

        # Right: Sales Trend Chart (Spanning 2 cols)
        if CHARTS_AVAILABLE:
            chart_container = QFrame()
            chart_container.setStyleSheet(f"background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(5, 8, 15, 0.8), stop:1 rgba(2, 4, 8, 0.6)); border-radius: 12px; border: 1px solid rgba(0, 242, 255, 0.15);")
            chart_layout = QVBoxLayout(chart_container)
            
            self.chart_view = QChartView()
            self.chart_view.setRenderHint(self.chart_view.renderHints().Antialiasing)
            self.chart_view.setBackgroundBrush(QColor("#121212")) 
            self.chart_view.setStyleSheet("background-color: transparent;")
            
            title_lbl = QLabel("SALES TREND (7 DAYS)")
            title_lbl.setStyleSheet(f"color: {COLOR_ACCENT_CYAN}; font-family: 'Orbitron'; font-weight: bold; letter-spacing: 1px; border: none; background: transparent;")
            chart_layout.addWidget(title_lbl)
            chart_layout.addWidget(self.chart_view)
            
            self.grid.addWidget(chart_container, 1, 2, 1, 2) # Span 2 cols
        
        # 2. LIVE TERMINAL (Spanning bottom)
        self.terminal = LiveTerminal(ai_assistant=self.ai_assistant)
        self.grid.addWidget(self.terminal, 2, 0, 1, 4) # Spans all 4 columns
        
        # Stretch
        self.main_layout.addStretch()

    def refresh_stats(self):
        # 1. Inventory Stats
        inv_stats = self.db_manager.get_dashboard_stats()
        self.card_parts.set_value(str(inv_stats['total_parts']))
        self.card_stock.set_value(f"{int(round(float(inv_stats['total_stock_qty']))):,d}")
        self.card_low.set_value(str(inv_stats['low_stock_count']))
        self.card_value.set_value(f"₹ {inv_stats['total_inventory_value']:,.0f}")
        
        # 2. Financial Stats
        fin_stats = self.db_manager.get_financial_summary()
        self.lbl_rev.setText(f"₹ {fin_stats['revenue']:,.2f}")
        self.lbl_exp.setText(f"₹ {fin_stats['expenses']:,.2f}")
        self.lbl_prof.setText(f"₹ {fin_stats['net_profit']:,.2f}")

        # 3. Top Parts
        # Get date range (last 30 days for relevance)
        today = datetime.date.today()
        start = today - datetime.timedelta(days=30)
        top_parts = self.db_manager.get_top_selling_parts(start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))
        
        # Format for widget: (Name, Qty + Price info)
        widget_items = []
        for p in top_parts:
            # p = (part_id, part_name, total_qty, total_revenue)
            widget_items.append((p[1], f"{p[2]} sold"))
            
        self.top_parts_widget.set_items(widget_items)

        # 4. Update Chart (Sales Trend)
        if CHARTS_AVAILABLE:
            # Get last 7 days sales
            trend_start = today - datetime.timedelta(days=6)
            trend_data = self.db_manager.get_sales_by_date_range(trend_start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))
            self.update_chart(trend_data)

    def update_chart(self, trend_data):
        # trend_data: list of (day, total_amount, count)
        
        series = QLineSeries()
        series.setName("Revenue")
        
        max_val = 0
        for i, row in enumerate(trend_data):
            series.append(i, row[1])
            if row[1] > max_val: max_val = row[1]
            
        area_series = QAreaSeries(series)
        area_series.setName("Revenue Area")
        
        # Gradient Fill
        gradient = QLinearGradient(0, 0, 0, 400)
        c_cyan = QColor(COLOR_ACCENT_CYAN)
        c_cyan.setAlpha(150)
        gradient.setColorAt(0.0, c_cyan)
        gradient.setColorAt(1.0, Qt.GlobalColor.transparent)
        area_series.setBrush(QBrush(gradient))
        area_series.setPen(QPen(QColor(COLOR_ACCENT_CYAN), 2))
        
        chart = QChart()
        chart.addSeries(area_series)
        chart.setBackgroundVisible(False)
        chart.setPlotAreaBackgroundVisible(False)
        chart.legend().setVisible(False)
        
        # Axis X
        axisX = QCategoryAxis()
        for i, row in enumerate(trend_data):
            d_obj = datetime.datetime.strptime(row[0], "%Y-%m-%d")
            axisX.append(d_obj.strftime("%d %b"), i)
        axisX.setLabelsColor(QColor("white"))
        axisX.setGridLineVisible(False)
        chart.addAxis(axisX, Qt.AlignmentFlag.AlignBottom)
        area_series.attachAxis(axisX)
        
        # Axis Y
        # Axis Y (Must be exactly '0', '2K', '4K', '6K', '8K', '10K' per spec)
        axisY = QCategoryAxis()
        axisY.append("0", 0)
        axisY.append("2K", 2000)
        axisY.append("4K", 4000)
        axisY.append("6K", 6000)
        axisY.append("8K", 8000)
        axisY.append("10K", 10000)
        axisY.setRange(0, 10000)
        axisY.setLabelsColor(QColor("white"))
        axisY.setGridLineColor(QColor(255, 255, 255, 30))
        chart.addAxis(axisY, Qt.AlignmentFlag.AlignLeft)
        area_series.attachAxis(axisY)
        
        self.chart_view.setChart(chart)
