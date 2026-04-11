from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from styles import (COLOR_BACKGROUND, COLOR_ACCENT_CYAN, STYLE_NEON_BUTTON, STYLE_TABLE_CYBER)

class LowStockDialog(QDialog):
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self.setWindowTitle("Critical Low Stock Alerts")
        self.setFixedSize(800, 500)
        self.setStyleSheet(f"background-color: {COLOR_BACKGROUND};")
        self._setup_ui()
        self._load_data()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        lbl_header = QLabel("⚠️ Low Stock Items")
        lbl_header.setStyleSheet("color: #ff4444; font-size: 18px; font-weight: bold;")
        layout.addWidget(lbl_header)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Part ID", "Name", "Qty", "Reorder Level", "Vendor", "Rack"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setStyleSheet(STYLE_TABLE_CYBER)
        layout.addWidget(self.table)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_export = QPushButton("📄 Export to Excel")
        self.btn_export.setStyleSheet(STYLE_NEON_BUTTON)
        self.btn_export.clicked.connect(self._export_excel)
        
        self.btn_po = QPushButton("🛒 Create PO")
        self.btn_po.setStyleSheet(STYLE_NEON_BUTTON)
        self.btn_po.clicked.connect(self._create_po)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_export)
        btn_layout.addWidget(self.btn_po)
        layout.addLayout(btn_layout)
        
    def _load_data(self):
        rows = self.db_manager.get_low_stock_parts()
        self.table.setRowCount(len(rows))
        
        for i, r in enumerate(rows):
            part_id = str(r[0])
            name = str(r[1])
            qty = int(r[2] or 0)
            reorder = int(r[3] or 0)
            vendor = str(r[4] or "")
            rack = str(r[5] or "")
            
            self.table.setItem(i, 0, QTableWidgetItem(part_id))
            self.table.setItem(i, 1, QTableWidgetItem(name))
            
            qty_item = QTableWidgetItem(str(qty))
            if qty <= 0:
                qty_item.setForeground(QColor("#ff4444")) # Red
            elif qty < reorder:
                qty_item.setForeground(QColor("#ffaa00")) # Orange
            else:
                qty_item.setForeground(QColor("#ffff00")) # Yellow
            qty_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            self.table.setItem(i, 2, qty_item)
            
            self.table.setItem(i, 3, QTableWidgetItem(str(reorder)))
            self.table.setItem(i, 4, QTableWidgetItem(vendor))
            self.table.setItem(i, 5, QTableWidgetItem(rack))
            
    def _export_excel(self):
        from inventory_page import InventoryPage
        try:
            temp_inv = InventoryPage(self.db_manager)
            # Use pandas to directly export instead of copying InventoryPage full logic 
            # if we just want basic low stock export, however we can just write simple pandas implementation:
            import pandas as pd
            import os
            from PyQt6.QtWidgets import QFileDialog, QMessageBox
            
            rows = self.db_manager.get_low_stock_parts()
            if not rows:
                return
            df = pd.DataFrame(rows, columns=["Part ID", "Name", "Qty", "Reorder Level", "Vendor", "Rack"])
            file_path, _ = QFileDialog.getSaveFileName(self, "Export Low Stock", os.path.expanduser("~/Default"), "Excel Files (*.xlsx)")
            if file_path:
                df.to_excel(file_path, index=False)
                QMessageBox.information(self, "Success", "Exported successfully.")
        except Exception as e:
            from logger import app_logger
            app_logger.error(f"Error exporting low stock: {e}")
            
    def _create_po(self):
        # We can emit a signal or instruct to jump to PO page here, but opening window usually requires main app state.
        # So we just close dialog and let user navigate manually. The plan said 'redirect' so:
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Info", "Please navigate to the Purchase Order tab to create orders for these parts.")
        self.accept()
