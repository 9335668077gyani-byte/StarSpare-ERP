from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QFrame, QScrollArea, QGridLayout, 
                             QGraphicsDropShadowEffect, QGraphicsOpacityEffect)
from PyQt6.QtCore import Qt, QTimer, QSize, QPoint, QRectF, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QLinearGradient, QBrush, QPen, QConicalGradient
from custom_components import ProMessageBox
from logger import app_logger
import ui_theme
from styles import (COLOR_BACKGROUND, COLOR_SURFACE, COLOR_ACCENT_CYAN, COLOR_ACCENT_GREEN,
                    COLOR_ACCENT_RED, COLOR_ACCENT_YELLOW, COLOR_TEXT_PRIMARY)
from datetime import datetime
import math

DAILY_BUDGET = 5000.0

class BudgetReactor(QWidget):
    """
    High-Tech Radial Gauge for Daily Budget Monitoring.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(250)
        self.spent = 0.0
        self.budget = DAILY_BUDGET
        self.percentage = 0.0
        self.angle_offset = 0
        
        # Animation
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(50)
        
    def update_data(self, spent):
        self.spent = spent
        self.percentage = min(1.0, self.spent / self.budget) if self.budget > 0 else 0
        self.update()
        
    def animate(self):
        self.angle_offset = (self.angle_offset + 2) % 360
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w, h = self.width(), self.height()
        center = QPoint(int(w/2), int(h/2))
        radius = min(w, h) / 2 - 20
        
        # Determine Status Color
        if self.percentage < 0.5:
            color = QColor(COLOR_ACCENT_GREEN)
        elif self.percentage < 0.9:
            color = QColor(COLOR_ACCENT_YELLOW)
        else:
            color = QColor(COLOR_ACCENT_RED)
            
        # 1. Background Orbital Rings (Rotating)
        painter.save()
        painter.translate(center)
        painter.rotate(self.angle_offset)
        pen = QPen(QColor(0, 242, 255, 30), 2)
        pen.setDashPattern([10, 20])
        painter.setPen(pen)
        painter.drawEllipse(QPoint(0,0), int(radius), int(radius))
        
        # Inner Ring (Counter-rotating)
        painter.rotate(-self.angle_offset * 2)
        pen.setColor(QColor(color.red(), color.green(), color.blue(), 50))
        pen.setDashPattern([5, 10])
        painter.setPen(pen)
        painter.drawEllipse(QPoint(0,0), int(radius - 20), int(radius - 20))
        painter.restore()
        
        # 2. Progress Arc
        start_angle = -90 * 16 # Top
        span_angle = -self.percentage * 360 * 16
        
        rect = QRectF(center.x() - (radius - 10), center.y() - (radius - 10), 
                      (radius - 10) * 2, (radius - 10) * 2)
        
        pen = QPen(color, 8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, int(start_angle), int(span_angle))
        
        # 3. Core Text
        painter.setPen(Qt.GlobalColor.white)
        painter.setFont(QFont("Consolas", 10))
        painter.drawText(QRectF(0, center.y() - 40, w, 20), Qt.AlignmentFlag.AlignCenter, "DAILY BURN")
        
        painter.setPen(color)
        painter.setFont(QFont("Consolas", 24, QFont.Weight.Bold))
        painter.drawText(QRectF(0, center.y() - 15, w, 40), Qt.AlignmentFlag.AlignCenter, f"₹{self.spent:,.0f}")
        
        painter.setPen(QColor("#888"))
        painter.setFont(QFont("Consolas", 8))
        painter.drawText(QRectF(0, center.y() + 25, w, 20), Qt.AlignmentFlag.AlignCenter, f"TARGET: ₹{self.budget:,.0f}")

class ExpenseBarChart(QWidget):
    """
    Real-time Bar Chart showing Last 7 Days Expenses.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(150)
        self.data_points = [] # List of (Label, Value)
        self.max_val = 1000
        
    def update_data(self, data):
        """data: list of (label, value) tuples"""
        self.data_points = data
        if data:
            self.max_val = max([x[1] for x in data] + [1000]) # At least 1000 scale
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        # Draw Background
        painter.fillRect(self.rect(), QColor(0, 0, 0, 50))
        
        if not self.data_points:
            painter.setPen(QColor(100, 100, 100))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No Data for Chart")
            return
            
        # Margins
        margin_bottom = 30
        margin_top = 20
        available_h = h - margin_bottom - margin_top
        
        bar_width = (w / len(self.data_points)) * 0.6
        spacing = (w / len(self.data_points)) * 0.4
        
        x = spacing / 2
        
        for label, val in self.data_points:
            # Bar Height
            ratio = val / self.max_val
            bar_h = int(available_h * ratio)
            
            # Color based on value intensity
            c = QColor(COLOR_ACCENT_CYAN)
            if ratio > 0.8: c = QColor(COLOR_ACCENT_RED)
            elif ratio > 0.4: c = QColor(COLOR_ACCENT_YELLOW)
            
            # Draw Bar
            rect = QRectF(x, h - margin_bottom - bar_h, bar_width, bar_h)
            painter.setBrush(c)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 4, 4)
            
            # Glow
            painter.setBrush(QColor(c.red(), c.green(), c.blue(), 50))
            painter.drawRoundedRect(rect.adjusted(-2, -2, 2, 2), 4, 4)
            
            # Value Label (Top of bar)
            if val > 0:
                painter.setPen(Qt.GlobalColor.white)
                painter.setFont(QFont("Consolas", 8))
                painter.drawText(QRectF(x - 10, h - margin_bottom - bar_h - 15, bar_width + 20, 15), 
                               Qt.AlignmentFlag.AlignCenter, f"{int(val/1000)}k" if val >= 1000 else str(int(val)))
            
            # X Axis Label
            painter.setPen(QColor(150, 150, 150))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(QRectF(x - 5, h - margin_bottom + 5, bar_width + 10, 20), 
                           Qt.AlignmentFlag.AlignCenter, label)
            
            x += bar_width + spacing
            
        # Title
        painter.setPen(QColor(COLOR_ACCENT_CYAN))
        painter.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
        painter.drawText(10, 15, "WEEKLY BURN RATE")

class ExpenseBlock(QFrame):
    """Visual block for an expense item with edit/delete options"""
    def __init__(self, data, parent_page=None):
        super().__init__()
        self.data = data
        self.parent_page = parent_page

        self.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(255, 255, 255, 0.05);
                border-left: 3px solid {self.get_cat_color(data[3])};
                border-radius: 4px;
            }}
            QFrame:hover {{
                background-color: rgba(255, 255, 255, 0.08);
            }}
            QLabel {{ color: white; border: none; background: transparent; }}
        """)
        self.setFixedHeight(55)
        
        l = QHBoxLayout(self)
        l.setContentsMargins(10, 5, 10, 5)
        
        # Icon/Cat
        cat_lbl = QLabel(data[3][:3].upper())
        cat_lbl.setStyleSheet(f"color: {self.get_cat_color(data[3])}; font-weight: bold; font-family: 'Consolas';")
        l.addWidget(cat_lbl)
        
        # Title
        title_lbl = QLabel(data[1])
        title_lbl.setStyleSheet("font-size: 13px; font-weight: bold;")
        l.addWidget(title_lbl)
        
        # Date (show if available)
        if len(data) > 4 and data[4]:
            date_lbl = QLabel(data[4])
            date_lbl.setStyleSheet("font-size: 10px; color: #888;")
            l.addWidget(date_lbl)
        
        l.addStretch()
        
        # Amount
        amt_lbl = QLabel(f"-₹{data[2]}")
        amt_lbl.setStyleSheet(f"color: {COLOR_ACCENT_RED}; font-weight: bold; font-size: 14px;")
        amt_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        l.addWidget(amt_lbl)
        
        # Spacing before buttons
        l.addSpacing(10)
        
        # EDIT BUTTON
        btn_edit = QPushButton("✏️")
        btn_edit.setFixedSize(32, 32)
        btn_edit.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 229, 255, 0.15);
                border: 1px solid #00e5ff;
                border-radius: 5px;
                font-size: 13px;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: rgba(0, 229, 255, 0.3);
                border: 2px solid #00e5ff;
            }
        """)
        btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_edit.setToolTip("Edit this expense")
        btn_edit.clicked.connect(lambda checked=False: self.edit_expense())
        l.addWidget(btn_edit, alignment=Qt.AlignmentFlag.AlignVCenter)
        
        # DELETE BUTTON
        btn_delete = QPushButton("🗑️")
        btn_delete.setFixedSize(32, 32)
        btn_delete.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 68, 68, 0.15);
                border: 1px solid #ff4444;
                border-radius: 5px;
                font-size: 13px;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: rgba(255, 68, 68, 0.3);
                border: 2px solid #ff4444;
            }
        """)
        btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_delete.setToolTip("Delete this expense")
        btn_delete.clicked.connect(lambda checked=False: self.delete_expense())
        l.addWidget(btn_delete, alignment=Qt.AlignmentFlag.AlignVCenter)

    def edit_expense(self):
        if self.parent_page:
            self.parent_page.open_edit_dialog(self.data)

    def delete_expense(self):
        if self.parent_page:
            self.parent_page.delete_expense_entry(self.data[0])
        
    def get_cat_color(self, cat):
        colors = {
            "Refreshment": "#ff9e00",   # Orange
            "Utility": "#00ccff",       # Blue
            "Salary": "#ff00d4",        # Pink
            "Transport": "#ffe600",     # Yellow
            "Rent/Fixed": "#ff4444",    # Red
            "Inventory": "#00ff9d"      # Green
        }
        return colors.get(cat, "#888888")

class ExpensePage(QWidget):
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        
        # Init AI
        from ai_manager import AIAssistant
        self.ai = AIAssistant(self.db_manager)
        
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # --- LEFT PANEL: Command & Pulse ---
        left_panel = QWidget()
        l_layout = QVBoxLayout(left_panel)
        l_layout.setContentsMargins(30, 30, 30, 30)
        l_layout.setSpacing(20)
        
        # Header
        header = QLabel("THE FINANCIAL ORACLE")
        header.setStyleSheet(f"font-size: 24px; font-weight: 800; color: {COLOR_ACCENT_CYAN}; letter-spacing: 2px;")
        l_layout.addWidget(header)
        
        # Expense Chart
        self.chart = ExpenseBarChart()
        l_layout.addWidget(self.chart)
        
        # Oracle Command Line
        cmd_container = QFrame()
        cmd_container.setStyleSheet(f"background-color: #080a10; border: 1px solid {COLOR_ACCENT_CYAN}; border-radius: 8px;")
        cmd_layout = QVBoxLayout(cmd_container)
        
        lbl_cmd = QLabel("> EXPENSE_LOG_PROTOCOL_V2")
        lbl_cmd.setStyleSheet("color: #00f2ff; font-family: 'Consolas'; font-size: 10px;")
        cmd_layout.addWidget(lbl_cmd)
        
        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("Type command (e.g., 'Tea 20', 'Rent 5000')...")
        self.cmd_input.setStyleSheet("background: transparent; color: white; font-size: 16px; border: none; font-family: 'Consolas';")
        self.cmd_input.returnPressed.connect(self.process_command)
        cmd_layout.addWidget(self.cmd_input)
        
        l_layout.addWidget(cmd_container)
        
        # Quick Actions Grid
        quick_grid = QGridLayout()
        quick_actions = [
            ("☕ Tea", "Tea 15"), 
            ("🍱 Lunch", "Lunch 120"), 
            ("⛽ Petrol", "Petrol 200"),
            ("🔧 Repair", "Shop Repair 500")
        ]
        
        for i, (label, cmd) in enumerate(quick_actions):
            btn = QPushButton(label)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(0, 242, 255, 0.1); color: {COLOR_ACCENT_CYAN}; border: 1px solid rgba(0, 242, 255, 0.3);
                    border-radius: 4px; padding: 10px;
                }}
                QPushButton:hover {{ background: {COLOR_ACCENT_CYAN}; color: black; }}
            """)
            btn.clicked.connect(lambda ch, c=cmd: self.process_command(c))
            quick_grid.addWidget(btn, 0, i)
            
        l_layout.addLayout(quick_grid)
        
        # Stats Summary
        self.stats_container = QWidget()
        self.stats_layout = QHBoxLayout(self.stats_container)
        # (Will be populated in load_data)
        l_layout.addWidget(self.stats_container)
        
        l_layout.addStretch()
        main_layout.addWidget(left_panel, stretch=2)
        
        # --- RIGHT PANEL: Reactor & Stream ---
        right_panel = QWidget()
        right_panel.setStyleSheet("background-color: #080a10; border-left: 1px solid #333;")
        r_layout = QVBoxLayout(right_panel)
        r_layout.setContentsMargins(20, 30, 20, 30)
        
        # Reactor
        self.reactor = BudgetReactor()
        r_layout.addWidget(self.reactor)
        r_layout.addSpacing(20)
        
        r_header = QLabel("TRANSACTION STREAM")
        r_header.setStyleSheet("color: #888; font-weight: bold; letter-spacing: 1px;")
        r_layout.addWidget(r_header)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        
        self.stream_container = QWidget()
        self.stream_layout = QVBoxLayout(self.stream_container)
        self.stream_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.stream_layout.setSpacing(10)
        
        scroll.setWidget(self.stream_container)
        r_layout.addWidget(scroll)
        
        main_layout.addWidget(right_panel, stretch=1)

    def process_command(self, text=None):
        if not text:
            text = self.cmd_input.text()
            
        if not text.strip(): return
        
        # AI Parse
        data, error = self.ai.parse_expense_command(text)
        
        if error:
            ProMessageBox.warning(self, "Oracle Error", error)
            return
            
        # Log to DB
        success, msg = self.db_manager.add_expense(data['title'], data['amount'], data['category'], data['date'])
        
        if success:
            self.cmd_input.clear()
            self.load_data() # Refresh UI
            # Flash effect could be added here
        else:
            ProMessageBox.critical(self, "System Fail", msg)

    def load_data(self):
        # 1. Get Last 30 Days of Expenses for Full Transaction History
        from datetime import timedelta
        today = datetime.now()
        thirty_days_ago = (today - timedelta(days=30)).strftime("%Y-%m-%d")
        today_str = today.strftime("%Y-%m-%d")
        
        # Get ALL expenses (disable date filter for now to ensure visibility)
        # expenses = self.db_manager.get_all_expenses(thirty_days_ago, today_str)
        expenses = self.db_manager.get_all_expenses(None, None)
        
        app_logger.info(f"Querying ALL expenses")
        app_logger.info(f"Found {len(expenses) if expenses else 0} expense entries")
        
        # Clear Stream
        for i in reversed(range(self.stream_layout.count())): 
            self.stream_layout.itemAt(i).widget().setParent(None)
            
        total_today = 0
        
        if not expenses or len(expenses) == 0:
            # Show empty state message
            empty_label = QLabel("No expense transactions in last 30 days.\nAdd expenses using the form on the left.")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_label.setStyleSheet("color: #666; font-size: 13px; padding: 40px;")
            self.stream_layout.addWidget(empty_label)
            app_logger.info("No expenses found in last 30 days")
        else:
            app_logger.info(f"Loading {len(expenses)} expenses")
            
        for exp in expenses:
            # exp: (id, title, amount, cat, date)
            block = ExpenseBlock(exp, parent_page=self)  # Pass parent reference
            self.stream_layout.insertWidget(0, block) # Add to top
            total_today += exp[2]
            
        # Update Reactor
        self.reactor.update_data(total_today)
            
        # 2. Update Pulse & Stats
        summary = self.db_manager.get_financial_summary()
        # self.pulse.update_data(summary['revenue'], summary['expenses'])
        
        # Update Chart
        daily_data = self.db_manager.get_daily_expenses(7)
        self.chart.update_data(daily_data)
        
        # Update Stats Text
        # Clear old stats
        for i in reversed(range(self.stats_layout.count())): 
            item = self.stats_layout.itemAt(i)
            if item.widget():
                item.widget().setParent(None)
            else:
                self.stats_layout.removeItem(item)
            
        lbl_rev = QLabel(f"REV: ₹{summary['revenue']:,.0f}")
        lbl_rev.setStyleSheet(f"color: {COLOR_ACCENT_GREEN}; font-size: 18px; font-weight: bold;")
        
        lbl_exp = QLabel(f"EXP: ₹{summary['expenses']:,.0f}")
        lbl_exp.setStyleSheet(f"color: {COLOR_ACCENT_RED}; font-size: 18px; font-weight: bold;")
        
        self.stats_layout.addWidget(lbl_rev)
        self.stats_layout.addStretch()
        self.stats_layout.addWidget(lbl_exp)
    
    def delete_expense_entry(self, expense_id):
        """Delete an expense entry with smooth fade animation"""
        if ProMessageBox.question(self, "Delete Expense?", "Are you sure you want to delete this expense entry?"):
            # Find the widget to animate
            target_widget = None
            for i in range(self.stream_layout.count()):
                widget = self.stream_layout.itemAt(i).widget()
                if hasattr(widget, 'data') and widget.data[0] == expense_id:
                    target_widget = widget
                    break
            
            if target_widget:
                # Create fade-out animation
                opacity_effect = QGraphicsOpacityEffect(target_widget)
                target_widget.setGraphicsEffect(opacity_effect)
                
                self.fade_anim = QPropertyAnimation(opacity_effect, b"opacity")
                self.fade_anim.setDuration(300)  # 300ms fade
                self.fade_anim.setStartValue(1.0)
                self.fade_anim.setEndValue(0.0)
                self.fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                
                # Delete from DB and refresh after animation
                def on_animation_finished():
                    success = self.db_manager.delete_expense(expense_id)
                    if success:
                        self.load_data()  # Refresh display
                    else:
                        # Restore opacity if delete failed
                        opacity_effect.setOpacity(1.0)
                        ProMessageBox.critical(self, "Error", "Failed to delete expense.")
                
                self.fade_anim.finished.connect(on_animation_finished)
                self.fade_anim.start()
            else:
                # Fallback: direct delete if widget not found
                success = self.db_manager.delete_expense(expense_id)
                if success:
                    self.load_data()
                else:
                    ProMessageBox.critical(self, "Error", "Failed to delete expense.")
    
    def open_edit_dialog(self, expense_data):
        app_logger.info(f"Opening edit dialog for: {expense_data}")
        """Open dialog to edit expense entry"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QComboBox, QDateEdit
        from PyQt6.QtCore import QDate
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Expense")
        dialog.setMinimumWidth(400)
        dialog.setStyleSheet(f"background-color: {COLOR_SURFACE}; color: white;")
        
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        
        # Title input
        edit_title = QLineEdit(expense_data[1])
        edit_title.setStyleSheet(ui_theme.get_lineedit_style())
        form.addRow("Title:", edit_title)
        
        # Amount input
        edit_amount = QLineEdit(str(expense_data[2]))
        edit_amount.setStyleSheet(ui_theme.get_lineedit_style())
        form.addRow("Amount (₹):", edit_amount)
        
        # Category dropdown
        edit_category = QComboBox()
        edit_category.addItems(["Refreshment", "Utility", "Salary", "Transport", "Rent/Fixed", "Inventory"])
        edit_category.setCurrentText(expense_data[3])
        edit_category.setStyleSheet(ui_theme.get_lineedit_style())
        form.addRow("Category:", edit_category)
        
        # Date picker
        edit_date = QDateEdit()
        if len(expense_data) > 4 and expense_data[4]:
            qdate = QDate.fromString(expense_data[4], "yyyy-MM-dd")
            edit_date.setDate(qdate)
        else:
            edit_date.setDate(QDate.currentDate())
        edit_date.setStyleSheet(ui_theme.get_lineedit_style())
        edit_date.setCalendarPopup(True)
        form.addRow("Date:", edit_date)
        
        layout.addLayout(form)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("Save Changes")
        btn_save.setStyleSheet(ui_theme.get_primary_button_style())
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setStyleSheet("background-color: #555; color: white; border-radius: 5px; padding: 8px;")
        
        btn_save.clicked.connect(dialog.accept)
        btn_cancel.clicked.connect(dialog.reject)
        
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)
        
        if dialog.exec():
            # Save changes with animation
            new_title = edit_title.text().strip()
            new_amount = float(edit_amount.text()) if edit_amount.text() else 0
            new_category = edit_category.currentText()
            new_date = edit_date.date().toString("yyyy-MM-dd")
            
            if new_title and new_amount > 0:
                # Find widget to animate
                target_widget = None
                for i in range(self.stream_layout.count()):
                    widget = self.stream_layout.itemAt(i).widget()
                    if hasattr(widget, 'data') and widget.data[0] == expense_data[0]:
                        target_widget = widget
                        break
                
                # Flash animation before update
                if target_widget:
                    opacity_effect = QGraphicsOpacityEffect(target_widget)
                    target_widget.setGraphicsEffect(opacity_effect)
                    
                    # Quick flash: fade out and in
                    self.flash_anim = QPropertyAnimation(opacity_effect, b"opacity")
                    self.flash_anim.setDuration(200)
                    self.flash_anim.setStartValue(1.0)
                    self.flash_anim.setEndValue(0.3)
                    self.flash_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
                    
                    def on_flash_done():
                        # Update in database
                        success = self.db_manager.update_expense(expense_data[0], new_title, new_amount, new_category, new_date)
                        if success:
                            self.load_data()  # Refresh to show changes
                        else:
                            opacity_effect.setOpacity(1.0)
                            ProMessageBox.critical(self, "Error", "Failed to update expense.")
                    
                    self.flash_anim.finished.connect(on_flash_done)
                    self.flash_anim.start()
                else:
                    # Fallback: direct update
                    success = self.db_manager.update_expense(expense_data[0], new_title, new_amount, new_category, new_date)
                    if success:
                        self.load_data()
                    else:
                        ProMessageBox.critical(self, "Error", "Failed to update expense.")
            else:
                ProMessageBox.warning(self, "Invalid Input", "Please enter valid title and amount.")
