from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QFrame, 
                             QCompleter, QDialog, QScrollArea, QAbstractItemView, QFormLayout, QInputDialog,
                             QGraphicsDropShadowEffect)
from PyQt6.QtCore import Qt, QStringListModel, QTimer
from PyQt6.QtGui import QColor, QBrush, QStandardItemModel, QStandardItem, QDoubleValidator
from billing_animations import AnimatedLabel, PulseEffect, FlashEffect, ScalePulse
from styles import (COLOR_SURFACE, COLOR_ACCENT_CYAN, COLOR_ACCENT_GREEN, COLOR_ACCENT_YELLOW, COLOR_TEXT_PRIMARY,
                   STYLE_GLASS_PANEL, STYLE_LCD_DISPLAY, STYLE_DIGITAL_LABEL, STYLE_GLASS_SIDEBAR, STYLE_HEADER_ACCENT,
                   DIM_BUTTON_HEIGHT, DIM_INPUT_HEIGHT, DIM_MARGIN_STD, DIM_SPACING_STD, DIM_ICON_SIZE)
from invoice_generator import InvoiceGenerator
from datetime import datetime
from whatsapp_helper import send_invoice_msg
from custom_components import ProMessageBox, ProDialog, ProTableDelegate
from logger import app_logger

MAX_FREE_DISCOUNT = 9.0

import ui_theme
import json
import os


# ═══════════════════════════════════════════════════════════════════════════════
# PAYMENT COLLECTION DIALOG
# ═══════════════════════════════════════════════════════════════════════════════
class PaymentDialog(QDialog):
    """Collect Cash / UPI payment with live due auto-calculation."""

    def __init__(self, grand_total: float, invoice_id: str, parent=None, previously_paid: float = 0.0):
        super().__init__(parent)
        self.grand_total = grand_total
        self.previously_paid = previously_paid
        self.target_amount = max(0.0, grand_total - previously_paid)
        self.invoice_id  = invoice_id
        self._result     = None   # (cash, upi, due, mode)

        self.setWindowTitle("💳 COLLECT PAYMENT")
        self.setModal(True)
        self.setFixedSize(440, 440)
        self.setStyleSheet("""
            QDialog { background-color: #07090f; color: white; }
            QLabel  { color: #aaa; font-size: 12px; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # ── Header ──────────────────────────────────────────────────
        hdr = QLabel(f"Invoice  #{invoice_id}")
        hdr.setStyleSheet(ui_theme.get_page_title_style())
        layout.addWidget(hdr)

        if self.previously_paid > 0:
            total_lbl = QLabel(f"Invoice Total: ₹ {grand_total:,.2f}\nPaid Earlier: ₹ {self.previously_paid:,.2f}\n\nRemaining: ₹ {self.target_amount:,.2f}")
            total_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            total_lbl.setStyleSheet(
                "color: #00ff88; font-size: 20px; font-weight: 900;"
                " font-family: 'Segoe UI'; border: none; background: transparent;"
            )
        else:
            total_lbl = QLabel(f"₹ {grand_total:,.2f}")
            total_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            total_lbl.setStyleSheet(
                "color: #00ff88; font-size: 34px; font-weight: 900;"
                " font-family: 'Segoe UI'; border: none; background: transparent;"
            )
            
        layout.addWidget(total_lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #1a1a2e;")
        layout.addWidget(sep)

        # ── Entry Fields ─────────────────────────────────────────────
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setVerticalSpacing(12)

        from PyQt6.QtWidgets import QDoubleSpinBox
        
        class SelectableDoubleSpinBox(QDoubleSpinBox):
            def focusInEvent(self, event):
                super().focusInEvent(event)
                QTimer.singleShot(0, self.selectAll)

        def make_spin(color):
            s = SelectableDoubleSpinBox()
            s.setRange(0.0, self.target_amount)
            s.setDecimals(2)
            s.setPrefix("₹ ")
            s.setFixedHeight(42)
            s.setStyleSheet(f"""
                QDoubleSpinBox {{
                    background: #0d1018; color: {color};
                    border: 2px solid {color}40; border-radius: 7px;
                    padding: 4px 10px; font-size: 15px; font-weight: bold;
                }}
                QDoubleSpinBox:focus {{ border-color: {color}; }}
                QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 22px; }}
            """)
            return s

        self.spin_cash = make_spin("#00e5ff")
        self.spin_upi  = make_spin("#00ff88")
        self.spin_cash.valueChanged.connect(self._on_cash_changed)
        self.spin_upi.valueChanged.connect(self._recalculate)

        lbl_cash = QLabel("💵  Cash Received:")
        lbl_cash.setStyleSheet(ui_theme.get_page_title_style())
        lbl_upi  = QLabel("📱  UPI Received:")
        lbl_upi.setStyleSheet(ui_theme.get_page_title_style())

        form.addRow(lbl_cash, self.spin_cash)
        form.addRow(lbl_upi,  self.spin_upi)
        layout.addLayout(form)

        # ── Due Label ────────────────────────────────────────────────
        self.lbl_due = QLabel("Balance Due:  ₹ 0.00")
        self.lbl_due.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_due.setStyleSheet(
            "color: #888; font-size: 13px; font-weight: bold;"
            " padding: 8px; border-radius: 6px; background: #0a0a10;"
        )
        layout.addWidget(self.lbl_due)

        # ── Quick Buttons ────────────────────────────────────────────
        quick_row = QHBoxLayout()
        quick_row.setSpacing(10)
        for label, cash, upi in [
            ("💵 Full Cash",  self.target_amount, 0.0),
            ("📱 Full UPI",   0.0, self.target_amount),
            ("⚡ Split 50/50", self.target_amount / 2, self.target_amount / 2),
        ]:
            btn = QPushButton(label)
            btn.setFixedHeight(34)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(0,229,255,0.08); color: #00e5ff;
                    border: 1px solid rgba(0,229,255,0.3); border-radius: 7px;
                    font-weight: bold; font-size: 11px;
                }
                QPushButton:hover { background: rgba(0,229,255,0.18); }
            """)
            _c, _u = cash, upi
            btn.clicked.connect(lambda _, c=_c, u=_u: self._quick_set(c, u))
            quick_row.addWidget(btn)
        layout.addLayout(quick_row)

        # ── Confirm Button ───────────────────────────────────────────
        self.btn_confirm = QPushButton("✅  CONFIRM & SAVE PAYMENT")
        self.btn_confirm.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_confirm.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            " stop:0 #003344, stop:1 #005522); color: #00ff88;"
            " border: 2px solid #00ff88; border-radius: 8px;"
            " font-size: 14px; font-weight: bold; }"
            "QPushButton:hover { background: #00ff88; color: black; }"
        )
        self.btn_confirm.clicked.connect(self._confirm)
        layout.addWidget(self.btn_confirm)

        # Initialise with full cash
        self._quick_set(self.target_amount, 0.0)

    # ── helpers ─────────────────────────────────────────────────────
    def _quick_set(self, cash, upi):
        self.spin_cash.blockSignals(True)
        self.spin_upi.blockSignals(True)
        self.spin_cash.setValue(cash)
        self.spin_upi.setValue(upi)
        self.spin_cash.blockSignals(False)
        self.spin_upi.blockSignals(False)
        self._recalculate()

    def _on_cash_changed(self, val):
        self.spin_upi.blockSignals(True)
        self.spin_upi.setValue(max(0.0, self.target_amount - val))
        self.spin_upi.blockSignals(False)
        self._recalculate()

    def _recalculate(self):
        c = self.spin_cash.value()
        u = self.spin_upi.value()
        due = max(0.0, self.target_amount - c - u)
        
        if due > 0:
            self.lbl_due.setStyleSheet("color: #ff4444; font-size: 13px; font-weight: bold; padding: 8px; border-radius: 6px; background: rgba(255,68,68,0.1);")
            self.lbl_due.setText(f"Balance Due:  ₹ {due:,.2f}")
        else:
            self.lbl_due.setStyleSheet("color: #00ff88; font-size: 13px; font-weight: bold; padding: 8px; border-radius: 6px; background: rgba(0,255,136,0.1);")
            self.lbl_due.setText("✅ Target Paid")

    def _confirm(self):
        c = self.spin_cash.value()
        u = self.spin_upi.value()
        due = max(0.0, self.target_amount - c - u)
        
        if c > 0 and u > 0: mode = "SPLIT"
        elif u > 0: mode = "UPI"
        elif c > 0: mode = "CASH"
        else: mode = "DUE"
        
        if due > 0:
            mode = "PARTIAL" if (c + u) > 0 else "DUE"

        self._result = (c, u, due, mode)
        self.accept()

    def get_result(self):
        """Returns (cash, upi, due, mode) or None if cancelled."""
        return self._result


class BillingPage(QWidget):
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self.pdf_generator = InvoiceGenerator(db_manager)
        self.cart_items = []
        self.editing_invoice_id = None
        self.editing_date_str = None
        self._recall_done = False   # True after a customer is recalled; stops live re-lookup
        self.setup_ui()
        self.load_saved_fields()  # Restore persistent custom fields
        
    def showEvent(self, event):
        self.update_completer()
        self.search_bar.setFocus()  # Auto-focus for instant scanning
        super().showEvent(event)

    def resizeEvent(self, event):
        # Dynamic Font Scaling for Grand Total - Optimized to prevent overlap
        if hasattr(self, 'lbl_grand_total'):
             if self.width() < 1200:
                self.lbl_grand_total.setStyleSheet(ui_theme.get_page_title_style())
             else:
                self.lbl_grand_total.setStyleSheet(ui_theme.get_page_title_style())
        super().resizeEvent(event)

    def setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(DIM_SPACING_STD + 10)
        main_layout.setContentsMargins(DIM_MARGIN_STD, DIM_MARGIN_STD, DIM_MARGIN_STD, DIM_MARGIN_STD)

        # --- LEFT PANEL (Glassmorphism) ---
        # --- LEFT PANEL (Glassmorphism) ---
        left_panel = QFrame()
        left_panel.setStyleSheet(STYLE_GLASS_SIDEBAR)
        left_panel.setMinimumWidth(280) # Responsive Sidebar
        
        # Main Layout for Left Panel (contains ScrollArea)
        left_main_layout = QVBoxLayout(left_panel)
        left_main_layout.setContentsMargins(0, 0, 0, 0)
        left_main_layout.setSpacing(0)

        # Scroll Area Setup
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("background: transparent; border: none;") # Transparent ScrollArea
        
        # Scroll Content Widget (The actual container for widgets)
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        
        # Layout for Scroll Content
        left_layout = QVBoxLayout(scroll_content)
        left_layout.setSpacing(20)
        left_layout.setContentsMargins(25, 25, 25, 25)
        
        # --- Add Widgets to scroll_content (left_layout) ---
        
        # Part Search Header
        lbl_search = QLabel("🔍 PART SEARCH")
        lbl_search.setStyleSheet(ui_theme.get_page_title_style())
        left_layout.addWidget(lbl_search)
        
        # Scanned Accent Line
        line_search = QFrame()
        line_search.setStyleSheet(STYLE_HEADER_ACCENT)
        left_layout.addWidget(line_search)
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔍 Scan/Type + ENTER to add instantly...")
        self.search_bar.setFixedHeight(DIM_INPUT_HEIGHT)
        self.search_bar.setStyleSheet(ui_theme.get_lineedit_style())
        self.search_bar.returnPressed.connect(self.add_to_cart_from_search)  # Auto-add on Enter
        left_layout.addWidget(self.search_bar)
        
        self.btn_add_manual = QPushButton("➕ ADD TO COCKPIT")
        self.btn_add_manual.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add_manual.setStyleSheet(ui_theme.get_primary_button_style())
        self.btn_add_manual.clicked.connect(self.add_to_cart_from_search)
        left_layout.addWidget(self.btn_add_manual)
        
        # Customer Info Header
        lbl_cust = QLabel("👤 CUSTOMER INFO")
        lbl_cust.setStyleSheet(ui_theme.get_page_title_style())
        left_layout.addWidget(lbl_cust)
        
        # Scanned Accent Line
        line_cust = QFrame()
        line_cust.setStyleSheet(STYLE_HEADER_ACCENT)
        left_layout.addWidget(line_cust)
        
        self.in_cust_name = QLineEdit()
        self.in_cust_name.setPlaceholderText("Customer Name")
        self.in_cust_name.setFixedHeight(DIM_INPUT_HEIGHT)
        self.in_cust_name.setStyleSheet(ui_theme.get_lineedit_style())
        left_layout.addWidget(self.in_cust_name)
        
        self.in_mobile = QLineEdit()
        self.in_mobile.setPlaceholderText("Mobile Number")
        self.in_mobile.setFixedHeight(DIM_INPUT_HEIGHT)
        self.in_mobile.setStyleSheet(ui_theme.get_lineedit_style())
        self.in_mobile.textChanged.connect(self.check_customer_history)
        self.in_mobile.returnPressed.connect(self.recall_customer)
        left_layout.addWidget(self.in_mobile)

        # Dynamic HUD (Hidden by default)
        self.hud_container = QWidget()
        self.hud_layout = QVBoxLayout(self.hud_container)
        self.hud_layout.setContentsMargins(0, 0, 0, 0)
        self.hud_layout.setSpacing(5)
        
        self.lbl_last_visit = QLabel("")
        self.lbl_last_visit.setStyleSheet(ui_theme.get_page_title_style())
        self.hud_layout.addWidget(self.lbl_last_visit)
        
        self.lbl_fav_part = QLabel("")
        self.lbl_fav_part.setStyleSheet(ui_theme.get_page_title_style())
        self.hud_layout.addWidget(self.lbl_fav_part)
        
        self.hud_container.setVisible(False)
        left_layout.addWidget(self.hud_container)

        self.in_vehicle = QLineEdit()
        self.in_vehicle.setPlaceholderText("Vehicle Model")
        self.in_vehicle.setFixedHeight(DIM_INPUT_HEIGHT)
        self.in_vehicle.setStyleSheet(ui_theme.get_lineedit_style())
        left_layout.addWidget(self.in_vehicle)

        self.in_reg_no = QLineEdit()
        self.in_reg_no.setPlaceholderText("Reg No  (press Enter or type to recall)")
        self.in_reg_no.setFixedHeight(DIM_INPUT_HEIGHT)
        self.in_reg_no.setStyleSheet(ui_theme.get_lineedit_style())
        self.in_reg_no.textChanged.connect(self.check_customer_history)   # live lookup
        self.in_reg_no.returnPressed.connect(self.recall_customer)
        left_layout.addWidget(self.in_reg_no)

        self.in_customer_gstin = QLineEdit()
        self.in_customer_gstin.setPlaceholderText("Customer GSTIN (Optional)")
        self.in_customer_gstin.setFixedHeight(DIM_INPUT_HEIGHT)
        self.in_customer_gstin.setStyleSheet(ui_theme.get_lineedit_style())
        self.in_customer_gstin.returnPressed.connect(self.recall_customer)
        left_layout.addWidget(self.in_customer_gstin)
        
        # Dynamic Fields Container
        self.dynamic_fields = [] # List of (field_name, input_widget, row_widget)
        self.dynamic_container = QVBoxLayout()
        left_layout.addLayout(self.dynamic_container)
        
        # Add Detail Button
        btn_add_detail = QPushButton("➕ ADD EXTRA DETAIL")
        btn_add_detail.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add_detail.setStyleSheet(ui_theme.get_ghost_button_style())
        btn_add_detail.clicked.connect(self.add_dynamic_field)
        left_layout.addWidget(btn_add_detail)
        
        left_layout.addStretch()
        
        # Finalize Scroll Area
        scroll_area.setWidget(scroll_content)
        left_main_layout.addWidget(scroll_area)
        
        main_layout.addWidget(left_panel, 25) 

        # --- RIGHT PANEL ---
        right_panel = QFrame()
        right_panel.setStyleSheet(STYLE_GLASS_PANEL)
        right_panel_layout = QVBoxLayout(right_panel)
        right_panel_layout.setContentsMargins(0, 0, 0, 0)
        right_panel_layout.setSpacing(0)
        
        content_widget = QWidget()
        # Ensure inner widget has transparent background to show glass effect
        content_widget.setStyleSheet("background: transparent; border: none;") 
        right_layout = QVBoxLayout(content_widget)
        right_layout.setContentsMargins(25, 25, 25, 25)
        right_layout.setSpacing(20)
        
        # Table
        self.cart_table = QTableWidget()
        self.cart_table.setColumnCount(8)
        self.cart_table.setHorizontalHeaderLabels(["ID", "NAME", "REMAINING", "MRP", "DISC%", "PRICE", "QTY", "TOTAL"])
        self.cart_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.cart_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.cart_table.horizontalHeader().setMinimumSectionSize(80) # Prevent collapse
        
        # Context Menu for Row Options
        self.cart_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.cart_table.viewport().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.cart_table.customContextMenuRequested.connect(self.show_context_menu)
        self.cart_table.viewport().customContextMenuRequested.connect(self.show_context_menu)
        
        # Alternating Rows and Solid Dark Background
        self.cart_table.setAlternatingRowColors(True)
        self.cart_table.cellChanged.connect(self.handle_cart_cell_edit)
        table_style = ui_theme.get_table_style() + """
            QTableWidget {
                background-color: #010206;
                alternate-background-color: #0a0f18;
            }
            QTableWidget::item {
                border-bottom: 1px solid #1a1a2e;
            }
        """
        self.cart_table.setStyleSheet(table_style)
        self.cart_table.verticalHeader().setVisible(False)
        self.cart_table.setShowGrid(False) # Clean grid
        
        self.delegate = ProTableDelegate(self.cart_table)
        for c in range(self.cart_table.columnCount()): 
             self.cart_table.setItemDelegateForColumn(c, self.delegate)
             
        # Empty State
        self.lbl_empty_state = QLabel("Awaiting System Input...", self.cart_table)
        self.lbl_empty_state.setStyleSheet(ui_theme.get_page_title_style())
        self.lbl_empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_empty_state.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        # Override resizeEvent to center the label
        original_resize = self.cart_table.resizeEvent
        def custom_resize(event):
            original_resize(event)
            self.lbl_empty_state.setGeometry(0, 0, self.cart_table.width(), self.cart_table.height())
        self.cart_table.resizeEvent = custom_resize
             
        right_layout.addWidget(self.cart_table)
        
        # --- SUMMARY SECTION (Unified Telemetry Panel) ---
        summary_container = QWidget()
        summary_layout = QVBoxLayout(summary_container)
        summary_layout.setContentsMargins(0, 5, 0, 0)
        summary_layout.setSpacing(10)
        
        panel_metrics = QFrame()
        panel_metrics.setStyleSheet("""
            QFrame {
                background-color: #0b0b14;
                border: 1px solid rgba(0, 229, 255, 0.2);
                border-radius: 8px;
            }
        """)
        metrics_layout = QHBoxLayout(panel_metrics)
        metrics_layout.setContentsMargins(15, 10, 15, 10)
        metrics_layout.setSpacing(25)
        
        def create_metric(title, value_widget):
            vbox = QVBoxLayout()
            lbl = QLabel(title)
            lbl.setStyleSheet(ui_theme.get_page_title_style())
            lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
            vbox.addWidget(lbl)
            
            value_widget.setStyleSheet("""
                color: #fff; 
                font-size: 18pt;  
                font-family: 'Segoe UI', sans-serif; 
                font-weight: bold; 
                border: none; 
                background: transparent;
            """)
            value_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vbox.addWidget(value_widget)
            return vbox

        self.lbl_parts_count = AnimatedLabel("0")
        metrics_layout.addLayout(create_metric("PARTS", self.lbl_parts_count))
        
        self.lbl_items_count = AnimatedLabel("0")
        metrics_layout.addLayout(create_metric("ITEMS", self.lbl_items_count))

        self.lbl_subtotal = AnimatedLabel("0.00")
        metrics_layout.addLayout(create_metric("SUB-TOTAL (₹)", self.lbl_subtotal))
        
        self.in_discount_pct = QLineEdit("0")
        self.in_discount_pct.setValidator(QDoubleValidator(0.0, 100.0, 2))
        self.in_discount_pct.editingFinished.connect(self.handle_global_discount_change)
        self.in_discount_pct.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.in_discount_pct.setStyleSheet(ui_theme.get_page_title_style())
        self.in_discount_pct.setFixedSize(70, 35)
        metrics_layout.addLayout(create_metric("DISCOUNT (%)", self.in_discount_pct))
        
        self.lbl_savings = AnimatedLabel("0.00")
        metrics_layout.addLayout(create_metric("SAVINGS (₹)", self.lbl_savings))
        self.lbl_savings.setStyleSheet(ui_theme.get_page_title_style())
        
        metrics_layout.addStretch(1)
        
        # Grand Total Section
        gt_layout = QVBoxLayout()
        gt_layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        lbl_gt_title = QLabel("TOTAL TO PAY")
        lbl_gt_title.setStyleSheet(ui_theme.get_page_title_style())
        lbl_gt_title.setAlignment(Qt.AlignmentFlag.AlignRight)
        gt_layout.addWidget(lbl_gt_title)
        
        self.lbl_grand_total = QLabel("₹ 0.00")
        self.lbl_grand_total.setStyleSheet(ui_theme.get_page_title_style())
        self.lbl_grand_total.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        gt_glow = QGraphicsDropShadowEffect()
        gt_glow.setBlurRadius(20)
        gt_glow.setColor(QColor("#00ff00"))
        gt_glow.setOffset(0, 0)
        self.lbl_grand_total.setGraphicsEffect(gt_glow)
        gt_layout.addWidget(self.lbl_grand_total)
        
        metrics_layout.addLayout(gt_layout)
        summary_layout.addWidget(panel_metrics)

        # ── GST Breakdown Badge (live, shown/hidden by Settings toggle) ──
        self.gst_badge = QFrame()
        self.gst_badge.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(0, 229, 255, 0.08), stop:1 rgba(0, 255, 65, 0.06));
                border: 1px solid rgba(0, 229, 255, 0.25);
                border-radius: 8px;
            }
        """)
        gst_badge_layout = QHBoxLayout(self.gst_badge)
        gst_badge_layout.setContentsMargins(18, 8, 18, 8)
        gst_badge_layout.setSpacing(30)

        gst_icon = QLabel("💰 GST BREAKDOWN")
        gst_icon.setStyleSheet(ui_theme.get_page_title_style())
        gst_badge_layout.addWidget(gst_icon)

        self.lbl_gst_taxable = QLabel("Taxable: ₹ 0.00")
        self.lbl_gst_taxable.setStyleSheet(ui_theme.get_page_title_style())
        gst_badge_layout.addWidget(self.lbl_gst_taxable)

        self.lbl_gst_cgst = QLabel("CGST: ₹ 0.00")
        self.lbl_gst_cgst.setStyleSheet(ui_theme.get_page_title_style())
        gst_badge_layout.addWidget(self.lbl_gst_cgst)

        self.lbl_gst_sgst = QLabel("SGST: ₹ 0.00")
        self.lbl_gst_sgst.setStyleSheet(ui_theme.get_page_title_style())
        gst_badge_layout.addWidget(self.lbl_gst_sgst)

        self.lbl_gst_total = QLabel("Total GST: ₹ 0.00")
        self.lbl_gst_total.setStyleSheet(ui_theme.get_page_title_style())
        gst_badge_layout.addWidget(self.lbl_gst_total)

        gst_badge_layout.addStretch()
        summary_layout.addWidget(self.gst_badge)

        # Load GST visibility from settings (default visible)
        try:
            s = self.db_manager.get_shop_settings()
            self._gst_visible = (s.get("show_gst_breakdown", "true") == "true")
        except Exception:
            self._gst_visible = True
        self.gst_badge.setVisible(self._gst_visible)
        
        # ROW 2: Actions
        actions_row = QHBoxLayout()
        actions_row.setSpacing(15)
        # actions_row.setAlignment(Qt.AlignmentFlag.AlignRight) # Standardize stretch?
        
        # Generate Invoice (Cyan)
        self.btn_checkout = QPushButton("GENERATE INVOICE [F12]")
        self.btn_checkout.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_checkout.setStyleSheet(ui_theme.get_neon_action_button())
        self.btn_checkout.clicked.connect(lambda: self.generate_invoice(silent=False))
        
        # drop shadow effects cannot be shared, create new ones
        glow_c = QGraphicsDropShadowEffect()
        glow_c.setBlurRadius(25)
        glow_c.setColor(QColor(COLOR_ACCENT_CYAN))
        glow_c.setOffset(0,0)
        self.btn_checkout.setGraphicsEffect(glow_c)
        actions_row.addWidget(self.btn_checkout)
        
        # WhatsApp (Green)
        self.btn_whatsapp = QPushButton("WHATSAPP INVOICE")
        self.btn_whatsapp.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_whatsapp.setStyleSheet(ui_theme.get_primary_button_style())
        self.btn_whatsapp.clicked.connect(self.send_whatsapp)
        
        glow_g = QGraphicsDropShadowEffect()
        glow_g.setBlurRadius(25)
        glow_g.setColor(QColor(COLOR_ACCENT_GREEN))
        glow_g.setOffset(0,0)
        self.btn_whatsapp.setGraphicsEffect(glow_g)
        actions_row.addWidget(self.btn_whatsapp)
        
        summary_layout.addLayout(actions_row)

        # ── PAYMENT ROW REMOVED ──\n        # Payment collection is now automatically initiated when generating an invoice.

        right_layout.addWidget(summary_container)
        right_panel_layout.addWidget(content_widget)
        main_layout.addWidget(right_panel, 70)

        self.setup_completer()

    def setup_completer(self):
        self.completer = QCompleter()
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        
        popup = self.completer.popup()
        popup.setStyleSheet(f"""
            QAbstractItemView {{
                background-color: #121212;
                color: {COLOR_ACCENT_CYAN};
                border: 1px solid #444;
            }}
        """)
        self.search_bar.setCompleter(self.completer)
        # When user selects a suggestion (arrow + Enter or click), add to cart immediately
        self.completer.activated.connect(self._on_completer_activated)

    def update_completer(self):
        try:
            parts = self.db_manager.get_all_parts()
            model = QStandardItemModel()
            
            for p in parts:
                # p[0]=id, p[1]=name, p[4]=stock
                display_text = f"{p[1]} ({p[0]})"
                item = QStandardItem(display_text)
                
                # Stock Check for Red Color
                if p[4] < 1:
                   item.setForeground(QBrush(QColor("#ff4444")))
                
                model.appendRow(item)
                
            self.completer.setModel(model)
        except Exception as e:
            app_logger.error(f"Error updating completer: {e}")

    def add_to_cart_from_search(self):
        # Guard: skip if completer already handled this Enter press
        if getattr(self, '_completer_handled', False):
            self._completer_handled = False
            return

        text = self.search_bar.text().strip()
        if not text: return
        
        # Fast parsing - extract Part ID
        if "(" in text and text.endswith(")"):
            part_id = text.split("(")[-1].strip(")")
        else:
            part_id = text
            
        # REAL-TIME STOCK FETCH
        try:
            part = self.db_manager.get_part_by_id(part_id)
            if part:
                self.add_item_to_cart(part)
                self.search_bar.clear()
                self.search_bar.setFocus()  # Keep focus for rapid entry
            else:
                ProMessageBox.warning(self, "Not Found", f"Part ID '{part_id}' not found!")
                self.search_bar.selectAll()  # Select all for easy re-entry
        except Exception as e:
            app_logger.error(f"Error adding to cart from search: {e}")
            self.search_bar.selectAll()

    def _on_completer_activated(self, text):
        """Called when user selects a suggestion from the dropdown (arrow+Enter or click).
        Sets guard flag to prevent returnPressed from double-adding."""
        self._completer_handled = True
        # Parse and add directly from the activated text
        if "(" in text and text.endswith(")"):
            part_id = text.split("(")[-1].strip(")")
        else:
            part_id = text
        try:
            part = self.db_manager.get_part_by_id(part_id)
            if part:
                self.add_item_to_cart(part)
                # Defer clear — QCompleter re-fills the bar AFTER this signal returns
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, self._clear_search_bar)
        except Exception as e:
            app_logger.error(f"Error in completer activation: {e}")

    def _clear_search_bar(self):
        """Deferred clear for search bar after completer insertion."""
        self.search_bar.clear()
        self.search_bar.setFocus()

    def add_item_to_cart(self, part):
        db_stock = part[4]
        
        found_item = None
        for item in self.cart_items:
            if item['sys_id'] == part[0]:
                found_item = item
                break
        
        current_cart_qty = found_item['qty'] if found_item else 0
        
        if db_stock <= current_cart_qty:
             ProMessageBox.warning(self, "Out of Stock", f"Only {db_stock} items available!")
             return

        # Prompt for Quantity
        dialog = ProDialog(self, title="ENTER QUANTITY", width=300, height=180)
        lbl = QLabel(f"Quantity to Add for:\n{part[1]}")
        lbl.setStyleSheet(ui_theme.get_page_title_style())
        lbl.setWordWrap(True)
        dialog.set_content(lbl)
        
        qty_in = QLineEdit("1")
        qty_in.setStyleSheet(ui_theme.get_lineedit_style())
        qty_in.setValidator(QDoubleValidator(0.01, float(db_stock), 3))
        qty_in.setFocus()
        # auto select text to allow quick overwrite
        QTimer.singleShot(10, qty_in.selectAll)
        dialog.set_content(qty_in)
        
        qty_in.returnPressed.connect(dialog.accept)
        
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("ADD")
        btn_save.setStyleSheet(ui_theme.get_primary_button_style())
        btn_save.clicked.connect(dialog.accept)
        btn_layout.addWidget(btn_save)
        
        dialog.add_buttons(btn_layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                entered_qty = float(qty_in.text())
            except ValueError:
                return
                
            if entered_qty <= 0:
                return
                
            if current_cart_qty + entered_qty > db_stock:
                ProMessageBox.warning(self, "Invalid", f"Max total stock available is {db_stock}")
                return
                
            if found_item:
                found_item['qty'] += entered_qty
                found_item['total'] = found_item['qty'] * found_item['price']
                found_item['db_stock'] = db_stock
                self.refresh_cart()
            else:
                hsn_code = str(part[15]).strip() if len(part) > 15 and part[15] else 'N/A'
                gst_rate = float(part[16]) if len(part) > 16 and part[16] else 18.0
                
                # Hybrid HSN Engine Fallback (v2.1)
                if not hsn_code or hsn_code == 'N/A':
                    rule = self.db_manager.search_hsn_rule(part[1])
                    if rule:
                        hsn_code = rule['hsn_code']
                        gst_rate = rule['gst_rate']

                self.cart_items.append({
                    'sys_id': part[0],
                    'name': part[1],
                    'price': part[3],
                    'db_stock': db_stock,
                    'qty': entered_qty,
                    'total': part[3] * entered_qty,
                    'hsn_code': hsn_code,
                    'gst_rate': gst_rate
                })
                # FLASH EFFECT for new item added! (Fast cyan flash for high-speed feedback)
                FlashEffect.flash(self.cart_table, "#00e5ff", 1)
                self.refresh_cart()
        
    def remove_cart_item(self, index):
        if 0 <= index < len(self.cart_items):
            item_name = self.cart_items[index]['name']
            
            if ProMessageBox.question(self, "CONFIRM DELETE", f"Remove '{item_name}'?"):
                self.cart_items.pop(index)
                self.refresh_cart()

    def edit_cart_item(self, index):
        if not (0 <= index < len(self.cart_items)): return
        
        item = self.cart_items[index]
        current_qty = item['qty']
        max_stock = item['db_stock']
        
        # ProDialog for Editing
        dialog = ProDialog(self, title="EDIT QUANTITY", width=300, height=180)
        
        lbl = QLabel(f"Set Quantity for: {item['name']}")
        lbl.setStyleSheet(ui_theme.get_page_title_style())
        dialog.set_content(lbl)
        
        qty_in = QLineEdit(f"{float(current_qty):g}")
        qty_in.setStyleSheet(ui_theme.get_lineedit_style())
        qty_in.setValidator(QDoubleValidator(0.01, max_stock, 3))
        dialog.set_content(qty_in)
        
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("UPDATE")
        btn_save.setStyleSheet(ui_theme.get_primary_button_style())
        btn_save.clicked.connect(dialog.accept)
        btn_layout.addWidget(btn_save)
        
        dialog.add_buttons(btn_layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
             try:
                 new_qty = float(qty_in.text())
                 if 0.01 <= new_qty <= max_stock:
                     item['qty'] = new_qty
                     item['total'] = item['price'] * new_qty
                     self.refresh_cart()
                 else:
                     ProMessageBox.warning(self, "Invalid", f"Qty must be between 0.01 and {max_stock}")
             except ValueError:
                 pass

    def refresh_cart(self):
        self.populate_cart_table()
        self.calculate_totals()
        
    def populate_cart_table(self):
        self.cart_table.blockSignals(True)
        self.cart_table.setRowCount(0)
        self.lbl_empty_state.setVisible(len(self.cart_items) == 0)
        
        # Read global discount for live display blending
        try:
            global_disc = float(self.in_discount_pct.text().strip() or 0)
        except ValueError:
            global_disc = 0.0
        
        for i, item in enumerate(self.cart_items):
            self.cart_table.insertRow(i)
            
            def create_item(text, align=Qt.AlignmentFlag.AlignCenter, col_type='generic'):
                it = QTableWidgetItem(str(text))
                it.setTextAlignment(align)
                it.setData(Qt.ItemDataRole.UserRole, {'type': col_type})
                return it

            self.cart_table.setItem(i, 0, create_item(item['sys_id'], col_type='id'))
            self.cart_table.setItem(i, 1, create_item(item['name'], Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, col_type='name'))
            
            # REMAINING STOCK Cell — shows how many more can be added (db_stock - in_cart)
            db_stock = item.get('db_stock', 0)
            remaining = max(0, db_stock - item['qty'])
            remaining_str = f"{round(remaining, 3):g}"
            stock_item = create_item(remaining_str)
            if remaining == 0:
                stock_item.setForeground(QBrush(QColor("#ff2222")))
                stock_item.setText("SOLD OUT")
            elif remaining <= 3:
                stock_item.setForeground(QBrush(QColor("#ff9800")))
            else:
                stock_item.setForeground(QBrush(QColor("#00ff41")))
            self.cart_table.setItem(i, 2, stock_item)
            
            # MATH — always compute from base MRP, blending both item & global discounts
            original_mrp = item.get('base_price', item['price'])
            item_price = item['price']   # reflects item-level discount already
            
            # Blend global discount on top for visual display only
            effective_price = item_price * (1 - global_disc / 100) if global_disc > 0 else item_price
            
            disc_perc = 0.0
            if original_mrp > 0 and effective_price < original_mrp:
                disc_perc = (1 - (effective_price / original_mrp)) * 100
            
            # MRP Cell (Strikethrough if any discount active)
            mrp_item = create_item(f"{original_mrp:.2f}")
            if disc_perc > 0:
                font = mrp_item.font()
                font.setStrikeOut(True)
                mrp_item.setFont(font)
                mrp_item.setForeground(QBrush(QColor("#888888")))
            self.cart_table.setItem(i, 3, mrp_item)
            
            # DISC% Cell (Neon Green if any discount active)
            disc_item = create_item(f"{disc_perc:.1f}%")
            if disc_perc > 0:
                font = disc_item.font()
                font.setBold(True)
                disc_item.setFont(font)
                disc_item.setForeground(QBrush(QColor("#00FF00")))
            self.cart_table.setItem(i, 4, disc_item)
            
            # PRICE Cell — show effective (globally discounted) price (Bold if discounted)
            price_item = create_item(f"{effective_price:.2f}", col_type='price')
            if disc_perc > 0:
                font = price_item.font()
                font.setBold(True)
                price_item.setFont(font)
            self.cart_table.setItem(i, 5, price_item)
            
            # QTY
            self.cart_table.setItem(i, 6, create_item(f"{float(item['qty']):g}"))
            
            # TOTAL — show effective total per row
            effective_total = effective_price * item['qty']
            self.cart_table.setItem(i, 7, create_item(f"{effective_total:.2f}"))
            
        self.cart_table.blockSignals(False)

    def handle_cart_cell_edit(self, row, col):
        if not (0 <= row < len(self.cart_items)): return
        item = self.cart_items[row]
        table_item = self.cart_table.item(row, col)
        if not table_item: return
        
        text = table_item.text().strip().replace('%', '')
        
        if col == 4: # DISC%
            try:
                pct = float(text)
                if pct < 0: pct = 0
                if pct > 100: pct = 100
                self.apply_item_discount(row, pct)
            except ValueError:
                self.refresh_cart() # Revert to actual valid data
                
        elif col == 6: # QTY
            try:
                new_qty = float(text)
                delta = new_qty - item['qty']
                if delta != 0:
                    self.adjust_item_qty(row, delta)
            except ValueError:
                self.refresh_cart() # Revert to actual valid data
                
    def show_context_menu(self, pos):
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtGui import QAction, QCursor
        
        # Using global position mapped to viewport is most reliable for QTableWidget
        viewport_pos = self.cart_table.viewport().mapFromGlobal(QCursor.pos())
        index = self.cart_table.indexAt(viewport_pos)
        
        if not index.isValid():
             # Right click on empty area?
             menu = QMenu(self)
             menu.setStyleSheet(self._get_menu_style())
             clear_all = QAction("🧹 Clear Entire Cart", self)
             # Fix: triggered signal passes a bool, use lambda to avoid TypeError
             clear_all.triggered.connect(lambda: self.reset_form())
             menu.addAction(clear_all)
             menu.exec(self.cart_table.viewport().mapToGlobal(pos))
             return
            
        row = index.row()
        item_data = self.cart_items[row]
        
        menu = QMenu(self)
        menu.setStyleSheet(self._get_menu_style())
        
        # 1. Primary Actions
        intel_action = QAction("📋 Part Intel / Info", self)
        intel_action.triggered.connect(lambda: self.show_part_intel(row))
        menu.addAction(intel_action)
        
        menu.addSeparator()
        
        edit_action = QAction("✏️ Edit Quantity (Manual)", self)
        edit_action.triggered.connect(lambda: self.edit_cart_item(row))
        menu.addAction(edit_action)
        
        # 2. Quick Sets Sub-menu
        quick_menu = menu.addMenu("⚡ Quick Quantity")
        for val in [+1, +5, +10, -1]:
            label = f"+{val}" if val > 0 else f"{val}"
            act = QAction(label, self)
            act.triggered.connect(lambda _, r=row, v=val: self.adjust_item_qty(r, v))
            quick_menu.addAction(act)
            
        # 3. Discount Sub-menu
        disc_menu = menu.addMenu("🏷️ Item Discount")
        for pct in [0, 2, 5, 10, 15, 20]:
            act = QAction("0% Off (Remove)" if pct == 0 else f"{pct}% Off", self)
            act.triggered.connect(lambda _, r=row, p=pct: self.apply_item_discount(r, p))
            disc_menu.addAction(act)
        
        menu.addSeparator()
        
        del_action = QAction("🗑️ Remove Item", self)
        del_action.triggered.connect(lambda: self.remove_cart_item(row))
        menu.addAction(del_action)
        
        menu.exec(self.cart_table.viewport().mapToGlobal(pos))

    def _get_menu_style(self):
        return """
            QMenu {
                background-color: #0b0b14;
                color: #00e5ff;
                border: 1px solid rgba(0, 229, 255, 0.4);
                padding: 5px;
            }
            QMenu::item {
                padding: 8px 25px 8px 10px;
                font-family: 'Segoe UI';
                font-size: 13px;
                font-weight: bold;
            }
            QMenu::item:selected {
                background-color: rgba(0, 229, 255, 0.2);
            }
            QMenu::separator {
                height: 1px;
                background: rgba(0, 229, 255, 0.1);
                margin: 5px 0px;
            }
        """

    def adjust_item_qty(self, row, delta):
        if not (0 <= row < len(self.cart_items)): return
        item = self.cart_items[row]
        new_qty = item['qty'] + delta
        if 0.01 <= new_qty <= item['db_stock']:
            item['qty'] = new_qty
            item['total'] = item['price'] * new_qty
            self.refresh_cart()
        elif new_qty < 0.01:
            self.remove_cart_item(row)
        else:
            ProMessageBox.warning(self, "Limit Reached", f"Max stock ({item['db_stock']}) reached.")

    def apply_item_discount(self, row, percentage):
        if not (0 <= row < len(self.cart_items)): return
        item = self.cart_items[row]
        
        # Phase 6: Dynamic Max Free Discount
        settings = self.db_manager.get_shop_settings()
        try:
            max_free = float(settings.get("max_free_discount", 9.0))
        except (ValueError, TypeError):
            max_free = 9.0
        
        if percentage > max_free:
            if not self.prompt_admin_pin("item discount"):
                return
                
        # Original price is set once when added to cart? 
        # Actually item['price'] might already be discounted if we do it multiple times.
        # Let's assume we want to apply to the current price or maybe we need 'original_price'.
        # For simplicity, we'll apply it once to the current item price.
        original_price = item.get('base_price', item['price'])
        if 'base_price' not in item:
            item['base_price'] = original_price
            
        discount_factor = (100 - percentage) / 100
        item['price'] = item['base_price'] * discount_factor
        item['total'] = item['price'] * item['qty']
        self.refresh_cart()

    def show_part_intel(self, row):
        if not (0 <= row < len(self.cart_items)): return
        item = self.cart_items[row]
        
        # Fetch full details from DB
        part = self.db_manager.get_part_by_id(item['sys_id'])
        if not part: return
        
        # part mapping: 0=id, 1=name, 2=description, 3=unit_price, 4=stock, 5=rack_no, ..., 10=category
        info_msg = f"<span style='font-size: 14pt; color: #00e5ff;'>{part[1]}</span><br><br>"
        info_msg += f"<b>📦 Category:</b> {part[10] if part[10] else 'N/A'}<br>"
        info_msg += f"<b>📍 Location:</b> {part[5] if part[5] else 'Main Store'}<br>"
        info_msg += f"<b>📊 Available Stock:</b> {part[4]}<br>"
        info_msg += f"<b>💰 Base Unit Price:</b> ₹ {part[3]:.2f}"
        
        ProMessageBox.information(self, "PART INTEL", info_msg)

    def prompt_admin_pin(self, action_name):
        from PyQt6.QtWidgets import QInputDialog, QLineEdit
        from custom_components import ProMessageBox
        
        admin_pin = self.db_manager.get_admin_override_pin()
        if not admin_pin:
            ProMessageBox.warning(self, "Setup Required", "No Admin Recovery PIN found. Please set one in Settings.")
            return False
            
        pin, ok = QInputDialog.getText(
            self, 
            "Manager Override Required", 
            f"Enter 6-Digit Admin Recovery PIN to authorize {action_name}:",
            QLineEdit.EchoMode.Password
        )
        
        if ok and pin == str(admin_pin):
            return True
            
        if ok:
            ProMessageBox.critical(self, "Access Denied", "Invalid Security PIN. Override failed.")
        return False
        
    def handle_global_discount_change(self):
        txt = self.in_discount_pct.text().strip()
        try:
            val = float(txt)
            last_discount = getattr(self, '_last_auth_discount', 0.0)
            
            # Phase 6: Dynamic Max Free Discount
            settings = self.db_manager.get_shop_settings()
            try:
                max_free = float(settings.get("max_free_discount", 9.0))
            except (ValueError, TypeError):
                max_free = 9.0
            
            if val > 0 and val != last_discount:
                if val > max_free:
                    if not self.prompt_admin_pin("global discount"):
                        self.in_discount_pct.blockSignals(True)
                        self.in_discount_pct.setText(str(last_discount) if last_discount > 0 else "0")
                        self.in_discount_pct.blockSignals(False)
                        self.calculate_totals()
                        return
                self._last_auth_discount = val
            elif val == 0:
                self._last_auth_discount = 0.0
                
        except ValueError:
            if not txt:
                self._last_auth_discount = 0.0
        self.refresh_cart()  # repaint table to show live discount per row

    def calculate_totals(self):
        """MRP-Based Hybrid Logic (v2.0): Reverse Tax Extraction."""
        # Guard: nothing to calculate on empty cart
        if not self.cart_items:
            self.tax_details = []
            return 0.0, 0.0, 0.0, 0.0, 0.0

        original_mrp_sum = 0.0
        total_savings    = 0.0
        grand_total      = 0.0
        total_gst        = 0.0
        
        # 1. Item-Level Processing
        for item in self.cart_items:
            qty = item.get('qty', 1)
            raw_mrp = item.get('base_price', item['price'])
            item_mrp_total = raw_mrp * qty
            original_mrp_sum += item_mrp_total
            
            # Item discount has already been applied to item['price'] in apply_item_discount
            # Use item['total'] which is qty * item['price']
            grand_total += item['total']
            
            # Savings from item-level discount
            item_savings = item_mrp_total - item['total']
            total_savings += item_savings

        # 2. Bill-Wide Processing
        try:
            txt = self.in_discount_pct.text().strip()
            bill_perc = float(txt) if txt else 0.0
            if bill_perc > 100: bill_perc = 100
        except ValueError:
            bill_perc = 0.0
            
        if bill_perc > 0:
            bill_savings = (grand_total * bill_perc) / 100
            total_savings += bill_savings
            grand_total -= bill_savings

        if grand_total < 0: grand_total = 0
        
        exact_grand_total = grand_total

        # Synchronize back-end DB total exactly with printing rounding requirement
        # This completely resolves the "rounding off" payment discrepancy.
        grand_total = round(grand_total)

        # 3. Reverse Tax Extraction (per-item, proportional to final grand_total)
        # Each item gets a pro-rata slice of exact_grand_total so that sum(per-item-final) == exact_grand_total
        self.tax_details = []
        pre_bill_total = sum(item['total'] for item in self.cart_items)  # cart before bill discount

        for item in self.cart_items:
            # Pro-rata share of exact grand_total for this item to avoid fractional .91/.98 visual artifacts
            if pre_bill_total > 0:
                item_share = item['total'] / pre_bill_total
            else:
                item_share = 1.0 / max(len(self.cart_items), 1)
            final_item_total = exact_grand_total * item_share  # exact proportional amount

            try:
                gst_rate = float(item.get('gst_rate', 18.0))
            except (ValueError, TypeError):
                gst_rate = 18.0

            hsn = item.get('hsn_code', 'N/A')

            # Back-calculate: final_item_total is GST-inclusive
            base_amt = final_item_total / (1 + gst_rate / 100)
            gst_amt  = final_item_total - base_amt
            total_gst += gst_amt

            self.tax_details.append({
                'id':    item['sys_id'],
                'hsn':   hsn,
                'gst_rate': gst_rate,
                'final_selling_price': final_item_total,
                'taxable_base': base_amt,
                'gst_amt':     gst_amt,
                # Store the final_item_total so generate_invoice can use it directly
                '_final_total': final_item_total,
            })

        taxable_base_value = exact_grand_total - total_gst
        self._exact_grand_total = exact_grand_total

        # --- ANIMATED UPDATES ---
        parts_count = len(self.cart_items)
        items_count = sum(item['qty'] for item in self.cart_items)
        
        try:
            old_parts = float(self.lbl_parts_count.text()) if self.lbl_parts_count.text() else 0.0
            old_items = float(self.lbl_items_count.text()) if self.lbl_items_count.text() else 0.0
        except (ValueError, AttributeError):
            old_parts = old_items = 0
        
        if parts_count != old_parts: self.lbl_parts_count.animateTo(parts_count)
        if items_count != old_items: self.lbl_items_count.animateTo(items_count)
        
        self.lbl_subtotal.animateTo(original_mrp_sum)
        self.lbl_savings.animateTo(total_savings)
        self.lbl_grand_total.setText(f"₹ {grand_total:.2f}")

        # Update GST badge (always calculate, visibility controlled separately)
        if hasattr(self, 'lbl_gst_taxable'):
            half_gst = total_gst / 2
            self.lbl_gst_taxable.setText(f"Taxable: ₹ {taxable_base_value:.2f}")
            self.lbl_gst_cgst.setText(f"CGST: ₹ {half_gst:.2f}")
            self.lbl_gst_sgst.setText(f"SGST: ₹ {half_gst:.2f}")
            self.lbl_gst_total.setText(f"Total GST: ₹ {total_gst:.2f}")

        return original_mrp_sum, total_savings, taxable_base_value, total_gst, grand_total

    # ─── Called live by MainWindow when Settings GST toggle changes ──────────
    def refresh_gst_display(self, show_gst: bool):
        """Show or hide the GST breakdown badge in real-time."""
        self._gst_visible = show_gst
        if hasattr(self, 'gst_badge'):
            self.gst_badge.setVisible(show_gst)
        # Recalculate so badge values are fresh if just turned on
        if show_gst and self.cart_items:
            self.calculate_totals()

    def recall_customer(self):
        """Omni-Search Trigger (Activated via Enter Key on Phone/Reg/GSTIN)"""
        sender = self.sender()
        if not sender: return
        
        search_term = sender.text().strip()
        if not search_term or len(search_term) < 4:
            return  # Prevent loose queries
            
        history = self.db_manager.get_customer_history(search_term)
        if history:
            # history: [customer_name, mobile, vehicle_model, reg_no, customer_gstin]
            
            # Temporarily block signals to avoid flashing HUD multiple times
            self.in_mobile.blockSignals(True)
            self.in_cust_name.setText(history[0] if history[0] else "")
            self.in_mobile.setText(history[1] if history[1] else "")
            self.in_vehicle.setText(history[2] if history[2] else "")
            self.in_reg_no.setText(history[3] if history[3] else "")
            self.in_customer_gstin.setText(history[4] if history[4] else "")
            self.in_mobile.blockSignals(False)
            
            # Trigger HUD manually
            self.check_customer_history()
            
    def check_customer_history(self):
        """Live recall: tries mobile (10-digit) OR reg_no (4+ chars).
        Skipped once a customer has been recalled — user can freely edit filled fields.
        """
        # ── Once recalled, stop overriding edits ──────────────────────
        if getattr(self, '_recall_done', False):
            return

        mobile = self.in_mobile.text().strip()
        reg_no = self.in_reg_no.text().strip()

        # Choose the best search term available
        if len(mobile) == 10 and mobile.isdigit():
            search_term = mobile
        elif len(reg_no) >= 4:
            search_term = reg_no
        else:
            self.hud_container.setVisible(False)
            return

        try:
            history = self.db_manager.get_customer_history(search_term)
            if history:
                # history: [0]=name, [1]=mobile, [2]=vehicle, [3]=reg_no, [4]=gstin
                # Block signals to avoid recursive recall
                for w in [self.in_mobile, self.in_cust_name,
                           self.in_vehicle, self.in_reg_no,
                           self.in_customer_gstin]:
                    w.blockSignals(True)

                self.in_cust_name.setText(history[0] or "")
                self.in_mobile.setText(history[1] or "")
                self.in_vehicle.setText(history[2] or "")
                self.in_reg_no.setText(history[3] or "")
                self.in_customer_gstin.setText(history[4] or "")

                for w in [self.in_mobile, self.in_cust_name,
                           self.in_vehicle, self.in_reg_no,
                           self.in_customer_gstin]:
                    w.blockSignals(False)

                # ── Mark recall complete so edits aren't overridden ──
                self._recall_done = True

                self.hud_container.setVisible(False)

                # Neon glow animation on all filled fields
                from PyQt6.QtWidgets import QGraphicsDropShadowEffect
                for widget in [self.in_cust_name, self.in_vehicle,
                                self.in_reg_no, self.in_customer_gstin,
                                self.in_mobile]:
                    glow = QGraphicsDropShadowEffect()
                    glow.setBlurRadius(20)
                    glow.setColor(QColor("#00e5ff"))
                    glow.setOffset(0, 0)
                    widget.setGraphicsEffect(glow)
                    QTimer.singleShot(1800, lambda w=widget: w.setGraphicsEffect(None))
            else:
                self.hud_container.setVisible(False)
        except Exception as e:
            app_logger.error(f"Error checking customer history: {e}")

    
    def add_dynamic_field(self):
        # Custom input dialog for Label
        dialog = QDialog(self)
        dialog.setWindowTitle("ADD DETAIL")
        dialog.setFixedSize(300, 150)
        dialog.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        layout = QVBoxLayout(dialog)
        frame = QFrame()
        frame.setStyleSheet(f"background-color: #0b0b14; border: 1px solid {COLOR_ACCENT_CYAN}; border-radius: 8px;")
        f_layout = QVBoxLayout(frame)
        
        label_in = QLineEdit()
        label_in.setPlaceholderText("Field Name (e.g., Chassis No)")
        label_in.setStyleSheet(ui_theme.get_lineedit_style())
        f_layout.addWidget(label_in)
        
        btn_add = QPushButton("ADD")
        btn_add.setStyleSheet(ui_theme.get_primary_button_style())
        btn_add.clicked.connect(dialog.accept)
        f_layout.addWidget(btn_add)
        
        layout.addWidget(frame)
        
        if dialog.exec() == QDialog.DialogCode.Accepted and label_in.text().strip():
            field_name = label_in.text().strip()
            
            # Save to database for persistence
            if self.db_manager.add_custom_billing_field(field_name):
                self._create_field_ui(field_name)
            else:
                # Field already exists
                ProMessageBox.warning(self, "Duplicate", f"Field '{field_name}' already exists!")

    def remove_dynamic_field(self, row_widget_to_remove):
        # 1. Find and remove from list
        field_name_to_remove = None
        for i, (fname, finp, frow) in enumerate(self.dynamic_fields):
            if frow == row_widget_to_remove:
                field_name_to_remove = fname
                self.dynamic_fields.pop(i)
                break
        
        # 2. Remove from database for permanent deletion
        if field_name_to_remove:
            self.db_manager.remove_custom_billing_field(field_name_to_remove)
        
        # 3. Remove from UI
        self.dynamic_container.removeWidget(row_widget_to_remove)
        row_widget_to_remove.deleteLater()
        row_widget_to_remove = None

    def _create_field_ui(self, field_name):
        """Create UI elements for a custom field"""
        # Container for the Row (Label + Input + Remove Button)
        row_widget = QWidget()
        row_layout = QVBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 10)
        row_layout.setSpacing(5)
        
        # Label
        lbl = QLabel(f"{field_name}:")
        lbl.setStyleSheet(ui_theme.get_page_title_style())
        row_layout.addWidget(lbl)
        
        # Input & Remove Button Horizontal Layout
        input_row_layout = QHBoxLayout()
        input_row_layout.setContentsMargins(0, 0, 0, 0)
        input_row_layout.setSpacing(5)
        
        inp = QLineEdit()
        inp.setPlaceholderText(f"Enter {field_name}")
        inp.setFixedHeight(40)
        inp.setStyleSheet(ui_theme.get_lineedit_style())
        input_row_layout.addWidget(inp)
        
        # Remove Button
        btn_remove = QPushButton("🗑️")
        btn_remove.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_remove.setStyleSheet(ui_theme.get_icon_btn_red())
        btn_remove.clicked.connect(lambda: self.remove_dynamic_field(row_widget))
        
        input_row_layout.addWidget(btn_remove)
        
        row_layout.addLayout(input_row_layout)
        
        self.dynamic_container.addWidget(row_widget)
        
        # Store reference: field_name, input_widget, row_widget
        self.dynamic_fields.append((field_name, inp, row_widget))

    def load_saved_fields(self):
        """Load and restore custom fields from database on startup"""
        saved_fields = self.db_manager.get_custom_billing_fields()
        for field_name in saved_fields:
            self._create_field_ui(field_name)

    def load_invoice_for_edit(self, invoice_id):
        self.reset_form()
        inv_details = self.db_manager.get_invoice_details(invoice_id)
        if not inv_details: return False

        self.editing_invoice_id = invoice_id
        self.editing_date_str = inv_details.get('date')
        self.original_upi = float(inv_details.get('payment_upi', 0.0))
        self.original_cash = float(inv_details.get('payment_cash', 0.0))

        # Change checkout button appearance for update mode
        self.btn_checkout.setText("⚠️ UPDATE INVOICE [F12]")
        self.btn_checkout.setStyleSheet("""
            QPushButton {
                background-color: rgba(243, 156, 18, 0.85); color: #fff; font-weight: bold; 
                border: 1px solid #e67e22; border-radius: 8px; font-size: 14px;
            }
            QPushButton:hover { background-color: #f39c12; }
        """)

        self.in_cust_name.setText(inv_details.get('customer', ''))
        self.in_mobile.setText(inv_details.get('mobile', ''))
        self.in_vehicle.setText(inv_details.get('vehicle', ''))
        self.in_reg_no.setText(inv_details.get('reg_no', ''))
        self.in_customer_gstin.setText(inv_details.get('customer_gstin', ''))
        
        extra_details = inv_details.get('extra_details', {})
        for fname, finput, _ in self.dynamic_fields:
            if fname in extra_details:
                finput.setText(str(extra_details[fname]))
        
        for item in inv_details.get('items', []):
            part_id = item.get('sys_id', item.get('id', ''))
            part = self.db_manager.get_part_by_id(part_id)
            if part:
                # Add current qty in DB to the qty already sold to get total available
                item['db_stock'] = part[4] + item.get('qty', 0)
            else:
                item['db_stock'] = item.get('qty', 0) 
                
            self.cart_items.append(item)
            
        try:
             tot_sav = float(inv_details.get('total_savings', 0))
             orig = float(inv_details.get('original_mrp', 0))
             if orig > 0 and tot_sav > 0:
                 disc = (tot_sav / orig) * 100
                 self.in_discount_pct.setText(f"{disc:.2f}")
        except: pass

        self.refresh_cart()
        return True

    def generate_invoice(self, silent=False):
        if not self.cart_items: return None, None, None

        original_mrp_sum, total_savings, taxable_base_value, total_gst, grand_total = self.calculate_totals()

        cust_name = self.in_cust_name.text() or "Walk-in"
        mobile = self.in_mobile.text() or ""
        vehicle = self.in_vehicle.text()
        reg_no = self.in_reg_no.text()

        # Deterministic IDs
        inv_id = self.editing_invoice_id if self.editing_invoice_id else self.db_manager.get_next_invoice_id()
        date_str = self.editing_date_str if self.editing_date_str else datetime.now().strftime("%Y-%m-%d %H:%M")

        extra_details = {}
        for fname, finput, _ in self.dynamic_fields:
             val = finput.text().strip()
             if val: extra_details[fname] = val

        if self.editing_invoice_id:
             extra_details["_is_edited"] = True

        final_json = {
            "cart": self.cart_items,
            "tax_details": self.tax_details,
            "vehicle": vehicle,
            "reg_no": reg_no,
            "extra_details": extra_details
        }
        json_items_str = json.dumps(final_json, default=str)

        items_count = sum(item['qty'] for item in self.cart_items)
        customer_gstin = self.in_customer_gstin.text().strip()
        inv_data = (inv_id, cust_name, mobile, vehicle, reg_no, grand_total, total_savings, date_str,
                    json_items_str, items_count, customer_gstin)

        # ── STEP 1: Collect payment BEFORE touching the DB (fixes B2) ──────
        # This ensures no invoice is ever committed without known payment intent.
        already_paid = 0.0
        if self.editing_invoice_id:
            already_paid = getattr(self, 'original_cash', 0.0) + getattr(self, 'original_upi', 0.0)
            
        target = max(0.0, grand_total - already_paid)
        delta_cash, delta_upi, delta_due = 0.0, 0.0, target
        
        if target > 0:
            dlg = PaymentDialog(grand_total, inv_id, self, previously_paid=already_paid)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                if dlg.get_result():
                    delta_cash, delta_upi, delta_due, _ = dlg.get_result()
            else:
                # Cancelled → treat as fully-due (no stock committed yet, safe to abort)
                delta_cash, delta_upi, delta_due = 0.0, 0.0, target

        # Calculate final totals for the DB row
        if self.editing_invoice_id:
            cash = getattr(self, 'original_cash', 0.0) + delta_cash
            upi = getattr(self, 'original_upi', 0.0) + delta_upi
            due = max(0.0, grand_total - cash - upi)
            if cash > 0 and upi > 0: mode = "SPLIT"
            elif upi > 0: mode = "UPI"
            elif cash > 0: mode = "CASH"
            else: mode = "DUE"
            if due > 0: mode = "PARTIAL" if (cash+upi)>0 else "DUE"
        else:
            cash, upi, due = delta_cash, delta_upi, delta_due
            if cash > 0 and upi > 0: mode = "SPLIT"
            elif upi > 0: mode = "UPI"
            elif cash > 0: mode = "CASH"
            else: mode = "DUE"
            if due > 0: mode = "PARTIAL" if (cash+upi)>0 else "DUE"

        # ── STEP 2: If editing, REVERT existing invoice stock impact ─────────
        if self.editing_invoice_id:
            suc, m = self.db_manager.revert_invoice(inv_id)
            if not suc:
                ProMessageBox.critical(self, "Edit Failed", f"Could not reverse old stock: {m}")
                return None, None, None

        # ── STEP 3: Persist invoice row with payment in one call ─────────────
        success, msg = self.db_manager.save_invoice(inv_data)
        if not success:
            app_logger.error(f"Failed to save invoice: {msg}")
            ProMessageBox.critical(self, "Invoice Error", f"Failed to save invoice.\n\nReason: {msg}")
            return None, None, None

        # Immediately write payment so the row is never in an ambiguous state
        self.db_manager.update_invoice_payment(inv_id, cash, upi, due, mode)
        app_logger.info(f"Invoice saved+payment recorded: {inv_id} for {cust_name}")

        # Log payment history to ensure math stays synced forever
        if not self.editing_invoice_id:
            if cash > 0: self.db_manager.log_payment(inv_id, cash, 'CASH')
            if upi > 0: self.db_manager.log_payment(inv_id, upi, 'UPI')
            if due > 0: self.db_manager.log_payment(inv_id, due, 'DUE PENDING')
        else:
            # We ONLY log the NEW deltas! NEVER clear history to preserve timestamps of old payments.
            if delta_cash > 0: self.db_manager.log_payment(inv_id, delta_cash, 'CASH')
            if delta_upi > 0: self.db_manager.log_payment(inv_id, delta_upi, 'UPI')
            # Only record a new DUE entry if there is a leftover delta unpaid today.
            if delta_due > 0: self.db_manager.log_payment(inv_id, delta_due, 'DUE PENDING')

        # ── STEP 4: Decrement stock — check every sell_part result (fixes B1/B4)
        sell_errors = []
        sold_items = []      # track successfully sold for rollback
        for item in self.cart_items:
            tax_info   = next((t for t in self.tax_details if t['id'] == item['sys_id']), {})
            final_unit = (tax_info.get('_final_total', 0.0) / item['qty']) \
                         if item['qty'] > 0 and tax_info.get('_final_total') else item['price']
            ok, err_msg = self.db_manager.sell_part(
                item['sys_id'], item['qty'], inv_id, cust_name,
                price_override=round(final_unit, 4)
            )
            if ok:
                sold_items.append(item)
            else:
                sell_errors.append(f"• {item['name']} ({item['sys_id']}): {err_msg}")

        if sell_errors:
            # Attempt to revert everything that was already committed
            app_logger.error(f"sell_part failures for {inv_id}: {sell_errors}")
            self.db_manager.revert_invoice(inv_id)
            ProMessageBox.critical(
                self, "Stock Error",
                "Invoice has been cancelled — could not update stock:\n\n" +
                "\n".join(sell_errors) +
                "\n\nPlease check stock levels and try again."
            )
            return None, None, None

        # ── STEP 5: Build PDF items list ──────────────────────────────────────
        pre_bill_total = sum(i['total'] for i in self.cart_items)
        pdf_items = []
        for idx, i in enumerate(self.cart_items, 1):
            tax_info = next((t for t in self.tax_details if t['id'] == i['sys_id']), {})
            final_item_total = tax_info.get('_final_total', 0.0)
            if final_item_total == 0.0 and pre_bill_total > 0:
                final_item_total = getattr(self, '_exact_grand_total', grand_total) * (i['total'] / pre_bill_total)

            raw_mrp = i.get('base_price', i['price'])
            qty     = i['qty']
            unit_final = final_item_total / qty if qty > 0 else 0.0
            effective_disc = (1 - unit_final / raw_mrp) * 100 if raw_mrp > 0 else 0.0
            effective_disc = max(0.0, effective_disc)

            pdf_items.append([
                idx,
                i['sys_id'],
                i['name'],
                tax_info.get('hsn', i.get('hsn_code', 'N/A')),
                tax_info.get('gst_rate', i.get('gst_rate', 18.0)),
                round(effective_disc, 2),
                qty,
                raw_mrp,
                round(final_item_total, 2),
            ])

        inv_meta = {
            "invoice_id": inv_id,
            "date": date_str,
            "customer": cust_name,
            "mobile": mobile,
            "vehicle": vehicle,
            "reg_no": reg_no,
            "original_mrp": original_mrp_sum,
            "total_savings": total_savings,
            "taxable_value": taxable_base_value,
            "gst_included": total_gst,
            "total": grand_total,
            "exact_total": getattr(self, '_exact_grand_total', grand_total),
            "extra_details": extra_details,
            "customer_gstin": customer_gstin,
            "payment_cash": cash,
            "payment_upi":  upi,
            "payment_due":  due,
            "payment_mode": mode,
        }

        # Calculate delta for QR code and new payment block if editing
        if self.editing_invoice_id and hasattr(self, 'original_upi'):
            delta_upi = upi - self.original_upi
            if delta_upi > 0:
                inv_meta["_qr_amount"] = delta_upi
            else:
                inv_meta["_qr_amount"] = 0
                
            delta_cash = cash - getattr(self, 'original_cash', 0.0)
            if delta_cash > 0:
                inv_meta["_delta_cash"] = delta_cash

        try:
            pdf_path = self.pdf_generator.generate_invoice_pdf(inv_meta, pdf_items)
        except Exception as e:
            app_logger.error(f"PDF Generation Failed: {e}")
            ProMessageBox.critical(self, "PDF Error", str(e))
            return None, None, None

        if not silent:
            try:
                os.startfile(pdf_path)
            except Exception as e:
                app_logger.error(f"Error opening PDF: {e}")

        # Reset form for next customer
        self.reset_form()
        return inv_id, grand_total, pdf_path

    def reset_form(self):
        self.cart_items = []
        self._recall_done = False   # reset so next customer can be looked up
        self.refresh_cart()
        self.in_cust_name.clear()
        self.in_mobile.clear()
        self.in_vehicle.clear()
        self.in_reg_no.clear()
        self.in_customer_gstin.clear()
        self.in_discount_pct.setText("0")
        self._last_auth_discount = 0.0
        self.lbl_savings.setText("0.00")
        self.lbl_grand_total.setText("₹ 0.00")
        
        # Reset Edit Mode
        self.editing_invoice_id = None
        self.editing_date_str = None
        self.btn_checkout.setText("GENERATE INVOICE [F12]")
        self.btn_checkout.setStyleSheet(ui_theme.get_neon_action_button())
        
        # Clear custom field VALUES only, not the fields themselves
        for field_name, input_widget, row_widget in self.dynamic_fields:
            input_widget.clear()

    def send_whatsapp(self):
        if not self.cart_items:
            ProMessageBox.warning(self, "Empty Cart", "Add Items first")
            return

        if not ProMessageBox.question(self, "Confirm", "Save & WhatsApp?"):
            return
            
        # Real-Time Capture
        current_name = self.in_cust_name.text().strip() or "Customer"
        current_mobile = self.in_mobile.text().strip()
        
        # Validation - Neon Red Warning
        import re
        clean_mobile = re.sub(r'\D', '', current_mobile)
        if len(clean_mobile) < 10:
             ProMessageBox.critical(self, "Invalid Mobile", "Please enter a valid 10-digit mobile number.")
             return
            
        # 1. Generate (Silent)
        inv_id, grand_total, pdf_path = self.generate_invoice(silent=True)
        
        if inv_id and pdf_path:
            # 2. Open PDF (Instant)
            try:
                os.startfile(pdf_path)
            except: pass
            
            # 3. Open Folder (Instant)
            try:
                folder = os.path.dirname(pdf_path)
                os.startfile(folder)
            except: pass

            # 4. Trigger WhatsApp (API)
            try:
                settings = self.db_manager.get_shop_settings()
                shop_name = settings.get("shop_name", "SpareParts Pro")
            except:
                shop_name = "SpareParts Pro"
                
            # Fetch the final due amount calculated during generation
            due_amt = 0.0
            try:
                conn = self.db_manager.get_connection()
                cur = conn.cursor()
                cur.execute("SELECT payment_due FROM invoices WHERE invoice_id = ?", (inv_id,))
                res = cur.fetchone()
                if res and res[0]:
                    due_amt = float(res[0])
            except Exception:
                pass
                
            app_logger.info(f"Sending WhatsApp for {inv_id} to {current_mobile}")
            send_invoice_msg(current_mobile, current_name, inv_id, grand_total, pdf_path, shop_name, due_amount=due_amt)
            self.reset_form()
