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
import ui_theme
import json
import os

class BillingPage(QWidget):
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self.pdf_generator = InvoiceGenerator(db_manager)
        self.cart_items = []
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
                self.lbl_grand_total.setStyleSheet(f"color: {COLOR_ACCENT_GREEN}; font-size: 22pt; font-weight: 900; font-family: Segoe UI;")
             else:
                self.lbl_grand_total.setStyleSheet(f"color: {COLOR_ACCENT_GREEN}; font-size: 28pt; font-weight: 900; font-family: Segoe UI;")
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
        lbl_search.setStyleSheet(f"color: {COLOR_ACCENT_CYAN}; font-weight: bold; font-size: 14px; letter-spacing: 1px; border: none;")
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
        self.btn_add_manual.setFixedHeight(DIM_BUTTON_HEIGHT)
        self.btn_add_manual.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_add_manual.setStyleSheet(ui_theme.get_primary_button_style())
        self.btn_add_manual.clicked.connect(self.add_to_cart_from_search)
        left_layout.addWidget(self.btn_add_manual)
        
        # Customer Info Header
        lbl_cust = QLabel("👤 CUSTOMER INFO")
        lbl_cust.setStyleSheet(f"color: {COLOR_ACCENT_CYAN}; font-weight: bold; font-size: 14px; border: none; margin-top: 15px;")
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
        left_layout.addWidget(self.in_mobile)

        # Dynamic HUD (Hidden by default)
        self.hud_container = QWidget()
        self.hud_layout = QVBoxLayout(self.hud_container)
        self.hud_layout.setContentsMargins(0, 0, 0, 0)
        self.hud_layout.setSpacing(5)
        
        self.lbl_last_visit = QLabel("")
        self.lbl_last_visit.setStyleSheet("color: #888; font-size: 11px; font-family: Consolas;")
        self.hud_layout.addWidget(self.lbl_last_visit)
        
        self.lbl_fav_part = QLabel("")
        self.lbl_fav_part.setStyleSheet("color: #888; font-size: 11px; font-family: Consolas;")
        self.hud_layout.addWidget(self.lbl_fav_part)
        
        self.hud_container.setVisible(False)
        left_layout.addWidget(self.hud_container)

        self.in_vehicle = QLineEdit()
        self.in_vehicle.setPlaceholderText("Vehicle Model")
        self.in_vehicle.setFixedHeight(DIM_INPUT_HEIGHT)
        self.in_vehicle.setStyleSheet(ui_theme.get_lineedit_style())
        left_layout.addWidget(self.in_vehicle)

        self.in_reg_no = QLineEdit()
        self.in_reg_no.setPlaceholderText("Reg No")
        self.in_reg_no.setFixedHeight(DIM_INPUT_HEIGHT)
        self.in_reg_no.setStyleSheet(ui_theme.get_lineedit_style())
        left_layout.addWidget(self.in_reg_no)

        self.in_customer_gstin = QLineEdit()
        self.in_customer_gstin.setPlaceholderText("Customer GSTIN (Optional)")
        self.in_customer_gstin.setFixedHeight(DIM_INPUT_HEIGHT)
        self.in_customer_gstin.setStyleSheet(ui_theme.get_lineedit_style())
        left_layout.addWidget(self.in_customer_gstin)
        
        # Dynamic Fields Container
        self.dynamic_fields = [] # List of (field_name, input_widget, row_widget)
        self.dynamic_container = QVBoxLayout()
        left_layout.addLayout(self.dynamic_container)
        
        # Add Detail Button
        btn_add_detail = QPushButton("➕ ADD EXTRA DETAIL")
        btn_add_detail.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add_detail.setStyleSheet("background-color: transparent; color: #00e5ff; border: 1px dashed #00e5ff; padding: 5px; border-radius: 4px;")
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
        self.cart_table.setColumnCount(6)
        self.cart_table.setHorizontalHeaderLabels(["ID", "NAME", "PRICE", "REMAIN", "QTY", "TOTAL"])
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
        self.lbl_empty_state.setStyleSheet("color: rgba(0, 229, 255, 0.15); font-size: 28pt; font-family: 'Segoe UI'; font-weight: bold; background: transparent;")
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
            lbl.setStyleSheet("color: #888; font-size: 10px; font-weight: bold; font-family: 'Segoe UI'; letter-spacing: 1px; text-transform: uppercase; border: none; background: transparent;")
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
        self.in_discount_pct.textChanged.connect(self.calculate_totals)
        self.in_discount_pct.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.in_discount_pct.setStyleSheet("color: #f1c40f; font-size: 18pt; font-family: 'Segoe UI'; font-weight: bold; border: 1px dashed rgba(0,229,255,0.3); background: transparent; padding: 2px;")
        self.in_discount_pct.setFixedSize(70, 35)
        metrics_layout.addLayout(create_metric("DISCOUNT (%)", self.in_discount_pct))
        
        self.lbl_savings = AnimatedLabel("0.00")
        metrics_layout.addLayout(create_metric("SAVINGS (₹)", self.lbl_savings))
        self.lbl_savings.setStyleSheet("color: #00ff41; font-size: 18pt; font-family: 'Segoe UI'; font-weight: bold; border: none; background: transparent;")
        
        metrics_layout.addStretch(1)
        
        # Grand Total Section
        gt_layout = QVBoxLayout()
        gt_layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        lbl_gt_title = QLabel("TOTAL TO PAY")
        lbl_gt_title.setStyleSheet("color: white; font-size: 12pt; font-weight: bold; letter-spacing: 2px; border: none; background: transparent;")
        lbl_gt_title.setAlignment(Qt.AlignmentFlag.AlignRight)
        gt_layout.addWidget(lbl_gt_title)
        
        self.lbl_grand_total = QLabel("₹ 0.00")
        self.lbl_grand_total.setStyleSheet(f"color: {COLOR_ACCENT_GREEN}; font-size: 32pt; font-weight: 900; font-family: 'Orbitron', 'Segoe UI'; border: none; background: transparent;")
        self.lbl_grand_total.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        gt_glow = QGraphicsDropShadowEffect()
        gt_glow.setBlurRadius(20)
        gt_glow.setColor(QColor("#00ff00"))
        gt_glow.setOffset(0, 0)
        self.lbl_grand_total.setGraphicsEffect(gt_glow)
        gt_layout.addWidget(self.lbl_grand_total)
        
        metrics_layout.addLayout(gt_layout)
        summary_layout.addWidget(panel_metrics)
        
        # ROW 2: Actions
        actions_row = QHBoxLayout()
        actions_row.setSpacing(15)
        # actions_row.setAlignment(Qt.AlignmentFlag.AlignRight) # Standardize stretch?
        
        # Generate Invoice (Cyan)
        self.btn_checkout = QPushButton("GENERATE INVOICE [F12]")
        self.btn_checkout.setFixedHeight(50) # Keep large
        self.btn_checkout.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_checkout.setStyleSheet(f"""
            QPushButton {{
                 background-color: #0b0b14; 
                 color: {COLOR_ACCENT_CYAN}; 
                 font-weight: bold; 
                 border: 2px solid {COLOR_ACCENT_CYAN};
                 border-radius: 8px;
                 font-size: 14px;
            }}
            QPushButton:hover {{ 
                background-color: {COLOR_ACCENT_CYAN}; 
                color: black;
            }}
        """)
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
        self.btn_whatsapp.setFixedHeight(50) 
        self.btn_whatsapp.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_whatsapp.setStyleSheet(f"""
            QPushButton {{
                 background-color: #0b0b14; 
                 color: {COLOR_ACCENT_GREEN}; 
                 font-weight: bold; 
                 border: 2px solid {COLOR_ACCENT_GREEN};
                 border-radius: 8px;
                 font-size: 14px;
            }}
            QPushButton:hover {{ 
                background-color: {COLOR_ACCENT_GREEN}; 
                color: black;
            }}
        """)
        self.btn_whatsapp.clicked.connect(self.send_whatsapp)
        
        glow_g = QGraphicsDropShadowEffect()
        glow_g.setBlurRadius(25)
        glow_g.setColor(QColor(COLOR_ACCENT_GREEN))
        glow_g.setOffset(0,0)
        self.btn_whatsapp.setGraphicsEffect(glow_g)
        actions_row.addWidget(self.btn_whatsapp)
        
        summary_layout.addLayout(actions_row)
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

        if found_item:
            # DUPLICATE DETECTED - Ask for confirmation
            msg = f"'{part[1]}' is already in cart (Qty: {found_item['qty']})\n\nAdd 1 more?"
            if ProMessageBox.question(self, "⚠️ Already in Cart", msg):
                found_item['qty'] += 1
                found_item['total'] = found_item['qty'] * found_item['price']
                found_item['db_stock'] = db_stock
                self.refresh_cart()
        else:
            hsn_code = part[16] if len(part) > 16 else 'N/A'
            gst_rate = float(part[17]) if len(part) > 17 else 18.0
            
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
                'qty': 1,
                'total': part[3],
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
        lbl.setStyleSheet("color: white; font-weight: bold; font-size: 12px;")
        dialog.set_content(lbl)
        
        qty_in = QLineEdit(str(current_qty))
        qty_in.setStyleSheet(ui_theme.get_lineedit_style())
        qty_in.setValidator(QDoubleValidator(1, max_stock, 0))
        dialog.set_content(qty_in)
        
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("UPDATE")
        btn_save.setStyleSheet(ui_theme.get_primary_button_style())
        btn_save.clicked.connect(dialog.accept)
        btn_layout.addWidget(btn_save)
        
        dialog.add_buttons(btn_layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
             try:
                 new_qty = int(float(qty_in.text()))
                 if 1 <= new_qty <= max_stock:
                     item['qty'] = new_qty
                     item['total'] = item['price'] * new_qty
                     self.refresh_cart()
                 else:
                     ProMessageBox.warning(self, "Invalid", f"Qty must be between 1 and {max_stock}")
             except ValueError:
                 pass

    def refresh_cart(self):
        self.populate_cart_table()
        self.calculate_totals()
        
    def populate_cart_table(self):
        self.cart_table.setRowCount(0)
        self.lbl_empty_state.setVisible(len(self.cart_items) == 0)
        for i, item in enumerate(self.cart_items):
            self.cart_table.insertRow(i)
            
            def create_item(text, align=Qt.AlignmentFlag.AlignCenter, col_type='generic'):
                it = QTableWidgetItem(str(text))
                it.setTextAlignment(align)
                # Set UserRole data for ProTableDelegate
                it.setData(Qt.ItemDataRole.UserRole, {'type': col_type})
                return it

            self.cart_table.setItem(i, 0, create_item(item['sys_id'], col_type='id'))
            self.cart_table.setItem(i, 1, create_item(item['name'], Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, col_type='name'))
            self.cart_table.setItem(i, 2, create_item(f"{item['price']:.2f}", col_type='price'))
            
            # REMAIN STOCK
            remain = item['db_stock'] - item['qty']
            rem_item = create_item(remain) # Use generic to avoid progress bar in cart
            rem_item.setForeground(QBrush(QColor("#ff4444") if remain < 5 else QColor(COLOR_ACCENT_GREEN)))
            self.cart_table.setItem(i, 3, rem_item)
            
            self.cart_table.setItem(i, 4, create_item(item['qty']))
            self.cart_table.setItem(i, 5, create_item(f"{item['total']:.2f}"))

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
        for pct in [2, 5, 10, 15, 20]:
            act = QAction(f"{pct}% Off", self)
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
        if 1 <= new_qty <= item['db_stock']:
            item['qty'] = new_qty
            item['total'] = item['price'] * new_qty
            self.refresh_cart()
        elif new_qty < 1:
            self.remove_cart_item(row)
        else:
            ProMessageBox.warning(self, "Limit Reached", f"Max stock ({item['db_stock']}) reached.")

    def apply_item_discount(self, row, percentage):
        if not (0 <= row < len(self.cart_items)): return
        item = self.cart_items[row]
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

    def calculate_totals(self):
        """MRP-Based Hybrid Logic (v2.0): Reverse Tax Extraction."""
        original_mrp_sum = 0.0      # Sum of raw MRPs (before any discounts)
        total_savings = 0.0         # Unified savings (item-level + bill-wide)
        grand_total = 0.0           # Strictly discounted MRP sum
        total_gst = 0.0             # Extracted GST
        
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

        # 3. Reverse Tax Extraction (on final discounted cart)
        # We need to extract GST per item because items can have different rates
        self.tax_details = [] # Store for PDF
        
        for item in self.cart_items:
            # Re-calculate final price for THIS item after bill-wide discount
            final_item_price = item['total'] * (1 - bill_perc/100)
            
            # Retrieve specific GST rate
            # In add_to_cart, we should ideally fetch the latest HSN/GST
            try:
                gst_rate = float(item.get('gst_rate', 18.0))
            except (ValueError, TypeError):
                gst_rate = 18.0
                
            hsn = item.get('hsn_code', 'N/A')
            
            base_amt = final_item_price / (1 + (gst_rate / 100))
            gst_amt = final_item_price - base_amt
            total_gst += gst_amt
            
            self.tax_details.append({
                'id': item['sys_id'],
                'hsn': hsn,
                'gst_rate': gst_rate,
                'final_selling_price': final_item_price,
                'taxable_base': base_amt,
                'gst_amt': gst_amt
            })

        taxable_base_value = grand_total - total_gst

        # --- ANIMATED UPDATES ---
        parts_count = len(self.cart_items)
        items_count = sum(item['qty'] for item in self.cart_items)
        
        try:
            old_parts = int(float(self.lbl_parts_count.text())) if self.lbl_parts_count.text() else 0
            old_items = int(float(self.lbl_items_count.text())) if self.lbl_items_count.text() else 0
        except:
            old_parts = old_items = 0
        
        if parts_count != old_parts: self.lbl_parts_count.animateTo(parts_count)
        if items_count != old_items: self.lbl_items_count.animateTo(items_count)
        
        self.lbl_subtotal.animateTo(original_mrp_sum)
        self.lbl_savings.animateTo(total_savings)
        self.lbl_grand_total.setText(f"₹ {grand_total:.2f}")

        return original_mrp_sum, total_savings, taxable_base_value, total_gst, grand_total

    def check_customer_history(self):
        mobile = self.in_mobile.text().strip()
        if len(mobile) == 10 and mobile.isdigit():
            try:
                # Expected return: (Name, Model, Reg, LastVisit, FavPart)
                # If db returns only 3, we adapt.
                history = self.db_manager.get_customer_history(mobile)
                if history:
                    self.in_cust_name.setText(history[0])
                    self.in_vehicle.setText(history[1])
                    self.in_reg_no.setText(history[2] if history[2] else "")
                    if len(history) > 3:
                        self.in_customer_gstin.setText(history[3] if history[3] else "")
                    
                    # HUD Update
                    if len(history) >= 5:
                        last_visit = history[3]
                        fav_part = history[4]
                        
                        self.lbl_last_visit.setText(f"🕒 LAST VISIT: {last_visit}")
                        self.lbl_fav_part.setText(f"⭐ FAVORITE: {fav_part}")
                        self.hud_container.setVisible(True)
                        
                        # Animate HUD Entry (Simple Opacity/Slide simulation via timer if needed, but simple show is OK)
                    
                    # Visual Cue: Neon Glow
                    from PyQt6.QtWidgets import QGraphicsDropShadowEffect
                    for widget in [self.in_cust_name, self.in_vehicle, self.in_reg_no, self.in_customer_gstin]:
                        glow = QGraphicsDropShadowEffect()
                        glow.setBlurRadius(20)
                        glow.setColor(QColor("#00e5ff"))
                        glow.setOffset(0, 0)
                        widget.setGraphicsEffect(glow)
                        
                        # Remove glow after 1.5 seconds
                        QTimer.singleShot(1500, lambda w=widget: w.setGraphicsEffect(None))
                else:
                    self.hud_container.setVisible(False)
            except Exception as e:
                app_logger.error(f"Error checking customer history: {e}")
        else:
            self.hud_container.setVisible(False)
    
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
        lbl.setStyleSheet(f"color: {COLOR_ACCENT_CYAN}; font-size: 12px;")
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
        btn_remove.setFixedSize(40, 40)
        btn_remove.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_remove.setStyleSheet("QPushButton { background-color: #f44336; border: none; border-radius: 4px; padding: 0px; margin: 0px; text-align: center; font-size: 16px; } QPushButton:hover { background-color: #d32f2f; }")
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

    def generate_invoice(self, silent=False):
        if not self.cart_items: return None, None, None
        
        original_mrp_sum, total_savings, taxable_base_value, total_gst, grand_total = self.calculate_totals()
        
        cust_name = self.in_cust_name.text() or "Walk-in"
        mobile = self.in_mobile.text() or ""
        vehicle = self.in_vehicle.text()
        reg_no = self.in_reg_no.text()
        
        inv_id = self.db_manager.get_next_invoice_id()
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # Collect Dynamic Fields
        extra_details = {}
        for fname, finput, _ in self.dynamic_fields:
             val = finput.text().strip()
             if val:
                 extra_details[fname] = val
        
        final_json = {
            "cart": self.cart_items,
            "tax_details": self.tax_details, # Added per-item breakdown
            "vehicle": vehicle,
            "reg_no": reg_no,
            "extra_details": extra_details
        }
        json_items_str = json.dumps(final_json, default=str)
        
        # Save to DB
        items_count = sum(item['qty'] for item in self.cart_items)
        customer_gstin = self.in_customer_gstin.text().strip()
        inv_data = (inv_id, cust_name, mobile, vehicle, reg_no, grand_total, total_savings, date_str, json_items_str, items_count, customer_gstin)
        success, msg = self.db_manager.save_invoice(inv_data)
        
        if success:
            app_logger.info(f"Invoice generated: {inv_id} for {cust_name}")
            for item in self.cart_items:
                self.db_manager.sell_part(item['sys_id'], item['qty'], inv_id, cust_name, price_override=item['price'])
            
            # Pre-calculate bill-wide discount percentage for item-level effective discount
            try:
                txt = self.in_discount_pct.text().strip()
                bill_perc = float(txt) if txt else 0.0
            except:
                bill_perc = 0.0

            pdf_items = []
            for idx, i in enumerate(self.cart_items, 1):
                # Retrieve tax info for this item from cached tax_details
                tax_info = next((t for t in self.tax_details if t['id'] == i['sys_id']), {})
                
                # Calculate Effective Discount %
                raw_mrp = i.get('base_price', i['price'])
                final_item_total = i['total'] * (1 - bill_perc/100)
                final_item_price = final_item_total / i['qty'] if i['qty'] > 0 else 0
                
                effective_disc = 0.0
                if raw_mrp > 0:
                    effective_disc = (1 - (final_item_price / raw_mrp)) * 100
                
                pdf_items.append([
                    idx, 
                    i['sys_id'], 
                    i['name'], 
                    tax_info.get('hsn', 'N/A'),
                    tax_info.get('gst_rate', i.get('gst_rate', 18.0)),
                    effective_disc,
                    i['qty'], 
                    raw_mrp,
                    final_item_total
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
                "extra_details": extra_details,
                "customer_gstin": customer_gstin
            }
                
            try:
                pdf_path = self.pdf_generator.generate_invoice_pdf(inv_meta, pdf_items)
            except Exception as e:
                app_logger.error(f"PDF Generation Failed: {e}")
                ProMessageBox.critical(self, "PDF Error", str(e))
                return None, None, None
            
            if not silent:
                 # Auto Open PDF
                 try:
                     os.startfile(pdf_path)
                 except Exception as e:
                     app_logger.error(f"Error opening PDF: {e}")
                 
                 self.reset_form()
                
            return inv_id, grand_total, pdf_path
        else:
            # Error Handling - Neon Red
            app_logger.error(f"Failed to save invoice: {msg}")
            ProMessageBox.critical(self, "Invoice Error", f"Failed to save invoice.\n\nReason: {msg}")
            return None, None, None

    def reset_form(self):
        self.cart_items = []
        self.refresh_cart()
        self.in_cust_name.clear()
        self.in_mobile.clear()
        self.in_vehicle.clear()
        self.in_reg_no.clear()
        self.in_customer_gstin.clear()
        self.in_discount_pct.setText("0")
        self.lbl_savings.setText("0.00")
        self.lbl_grand_total.setText("₹ 0.00")
        
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
                
            app_logger.info(f"Sending WhatsApp for {inv_id} to {current_mobile}")
            send_invoice_msg(current_mobile, current_name, inv_id, grand_total, pdf_path, shop_name)
            self.reset_form()
