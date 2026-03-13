from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, 
                             QSpinBox, QFrame, QAbstractItemView)
from PyQt6.QtCore import Qt
from styles import COLOR_ACCENT_CYAN, STYLE_NEON_BUTTON, STYLE_TABLE_CYBER, COLOR_BACKGROUND
from custom_components import ProMessageBox

class ReturnDialog(QDialog):
    def __init__(self, db_manager, invoice_id, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.invoice_id = invoice_id
        
        self.setWindowTitle(f"Return Items - {invoice_id}")
        self.resize(750, 550)
        self.setStyleSheet(f"background-color: {COLOR_BACKGROUND}; color: white;")
        
        # Center on parent or screen
        if parent:
            self.move(parent.geometry().center() - self.rect().center())
        
        self.setup_ui()
        self.load_invoice_items()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # Header Container
        header_frame = QFrame()
        header_frame.setStyleSheet("background: transparent;")
        h_layout = QHBoxLayout(header_frame)
        h_layout.setContentsMargins(0, 0, 0, 0)
        
        # Title
        title_lbl = QLabel(f"PROCESS RETURN")
        title_lbl.setStyleSheet(f"font-size: 24px; font-weight: 900; color: {COLOR_ACCENT_CYAN}; letter-spacing: 2px;")
        
        # Subtitle (Inv ID)
        sub_lbl = QLabel(f"#{self.invoice_id}")
        sub_lbl.setStyleSheet("font-size: 16px; color: #888; font-family: Consolas;")
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignBottom)
        
        h_layout.addWidget(title_lbl)
        h_layout.addStretch()
        h_layout.addWidget(sub_lbl)
        
        layout.addWidget(header_frame)
        
        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color: {COLOR_ACCENT_CYAN}; background-color: {COLOR_ACCENT_CYAN}; border: none; min-height: 2px;")
        layout.addWidget(line)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Item Code", "Product Name", "Sold Qty", "Unit Price", "Return Qty"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(4, 120)
        self.table.setStyleSheet(STYLE_TABLE_CYBER)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(self.table)
        
        # Summary Section (Right Aligned)
        summary_layout = QHBoxLayout()
        summary_layout.addStretch()
        
        summary_box = QFrame()
        summary_box.setStyleSheet(f"""
            background-color: rgba(20, 20, 30, 0.8); 
            border: 1px solid {COLOR_ACCENT_CYAN}; 
            border-radius: 8px;
        """)
        sb_layout = QVBoxLayout(summary_box)
        sb_layout.setContentsMargins(15, 10, 15, 10)
        
        lbl_refund_title = QLabel("TOTAL REFUND")
        lbl_refund_title.setStyleSheet("color: #aaa; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        lbl_refund_title.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        self.lbl_refund = QLabel("₹ 0.00")
        self.lbl_refund.setStyleSheet(f"color: #ffeb3b; font-size: 20px; font-weight: bold; font-family: Segoe UI;")
        self.lbl_refund.setAlignment(Qt.AlignmentFlag.AlignRight)
        
        sb_layout.addWidget(lbl_refund_title)
        sb_layout.addWidget(self.lbl_refund)
        
        summary_layout.addWidget(summary_box)
        layout.addLayout(summary_layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)
        
        btn_cancel = QPushButton("CANCEL")
        btn_cancel.setFixedSize(120, 45)
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton { border: 1px solid #555; color: #888; border-radius: 6px; background: transparent; font-weight: bold; }
            QPushButton:hover { border-color: #aaa; color: white; }
        """)
        btn_cancel.clicked.connect(self.reject)
        
        btn_confirm = QPushButton("CONFIRM RETURN")
        btn_confirm.setFixedHeight(45)
        btn_confirm.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_confirm.setStyleSheet(STYLE_NEON_BUTTON)
        btn_confirm.clicked.connect(self.process_returns)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_confirm)
        layout.addLayout(btn_layout)
        
    def load_invoice_items(self):
        # Fetch items from DB
        items = self.db_manager.get_invoice_items(self.invoice_id)
        
        self.table.setRowCount(0)
        self.spinboxes = {} # Map row -> spinbox
        self.item_data = {} # Map row -> item dict
        
        for i, item in enumerate(items):
            # item dict: {'id':..., 'name':..., 'qty':..., 'price':..., 'total':...}
            self.table.insertRow(i)
            
            # 0: ID
            # Safe get for sys_id or id
            pid = item.get('sys_id', item.get('id', 'Unknown'))
            
            self.table.setItem(i, 0, QTableWidgetItem(str(pid)))
            self.table.setItem(i, 1, QTableWidgetItem(str(item.get('name', 'Unknown'))))
            
            sold_qty = int(item.get('qty', 0))
            # Center align numbers
            t_qty = QTableWidgetItem(str(sold_qty))
            t_qty.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 2, t_qty)
            
            price = float(item.get('price', 0.0))
            t_price = QTableWidgetItem(f"{price:,.2f}")
            t_price.setTextAlignment(Qt.AlignmentFlag.AlignRight)
            self.table.setItem(i, 3, t_price)
            
            # SpinBox
            spin = QSpinBox()
            spin.setRange(0, sold_qty)
            spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
            spin.setStyleSheet("background: #0b0b14; color: white; border: 1px solid #444; border-radius: 4px; padding: 4px;")
            spin.valueChanged.connect(self.calculate_refund)
            
            container = QFrame()
            clayout = QVBoxLayout(container)
            clayout.setContentsMargins(10, 2, 10, 2) # Padding for nicer look
            clayout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            clayout.addWidget(spin)
            self.table.setCellWidget(i, 4, container)
            
            self.spinboxes[i] = spin
            self.item_data[i] = item
            
    def calculate_refund(self):
        total_refund = 0.0
        for i, spin in self.spinboxes.items():
            qty = spin.value()
            if qty > 0:
                price = float(self.item_data[i].get('price', 0.0))
                total_refund += (qty * price)
        
        self.lbl_refund.setText(f"₹ {total_refund:,.2f}")
        
    def process_returns(self):
        return_items = []
        total_refund = 0.0
        
        for i, spin in self.spinboxes.items():
            qty = spin.value()
            if qty > 0:
                item = self.item_data[i]
                price = float(item.get('price', 0.0))
                refund = qty * price
                # Get Correct ID (Check sys_id or id)
                pid = item.get('sys_id', item.get('id', 'Unknown'))
                
                return_items.append({
                    'part_id': pid,
                    'qty': qty,
                    'refund': refund
                })
                total_refund += refund
        
        if not return_items:
            ProMessageBox.warning(self, "No Items", "Please select at least one item to return.")
            return

        # Confirm
        if not ProMessageBox.question(self, "Confirm Return", 
                                      f"Process return for {len(return_items)} items?\nTotal Refund: ₹ {total_refund:,.2f}\n\nThis will restore stock and log the return."):
            return
            
        # Process
        success_count = 0
        errors = []
        
        for r_item in return_items:
            success, msg = self.db_manager.process_return(
                self.invoice_id, 
                r_item['part_id'], 
                r_item['qty'], 
                r_item['refund']
            )
            if success:
                success_count += 1
            else:
                errors.append(f"Part {r_item['part_id']}: {msg}")
        
        # --- REGENERATE PDF IF SUCCESSFUL ---
        if success_count > 0:
            from invoice_generator import InvoiceGenerator
            gen = InvoiceGenerator(self.db_manager)
            new_path = gen.regenerate_invoice(self.invoice_id)
            if new_path:
                ProMessageBox.information(self, "Success", f"Return processed and Invoice updated.\nSaved to: {new_path}")
            else:
                 ProMessageBox.warning(self, "Success (Partial)", "Return processed but failed to update PDF.")
        
        if errors:
            ProMessageBox.warning(self, "Partial Errors", "\n".join(errors))
            
        self.accept()
