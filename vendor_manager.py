from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, 
                             QFormLayout, QMessageBox, QWidget, QFrame)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon
from styles import (COLOR_BACKGROUND, COLOR_SURFACE, COLOR_ACCENT_CYAN, 
                    STYLE_NEON_BUTTON, STYLE_INPUT_CYBER, STYLE_TABLE_CYBER, STYLE_DANGER_BUTTON)
from custom_components import ProMessageBox, ProTableDelegate
import ui_theme

class VendorManagerWidget(QWidget):
    """
    Embeddable Widget to Manage Vendors.
    """
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        # No window title/resize here, handled by parent or layout
        self.setStyleSheet(f"background-color: {COLOR_BACKGROUND}; color: white;")
        
        self.setup_ui()
        self.load_vendors()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        header = QLabel("OFFICIAL VENDOR REGISTRY")
        header.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {COLOR_ACCENT_CYAN}; letter-spacing: 2px;")
        layout.addWidget(header)
        
        # Main Content: Split into List and Form
        content_layout = QHBoxLayout()
        
        # Left: Vendor List
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["ID", "Vendor Name", "Contact"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setStyleSheet(STYLE_TABLE_CYBER)
        self.table.itemClicked.connect(self.populate_form)
        left_layout.addWidget(self.table)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_new = QPushButton("New Vendor")
        self.btn_new.setStyleSheet(ui_theme.get_neon_action_button())
        self.btn_new.clicked.connect(self.clear_form)
        
        self.btn_delete = QPushButton("Delete Selected")
        self.btn_delete.setStyleSheet(ui_theme.get_danger_button_style())
        self.btn_delete.clicked.connect(self.delete_vendor)
        
        btn_layout.addWidget(self.btn_new)
        btn_layout.addWidget(self.btn_delete)
        left_layout.addLayout(btn_layout)
        
        content_layout.addWidget(left_panel, stretch=2)
        
        # Right: Edit Form
        right_panel = QFrame()
        right_panel.setStyleSheet(f"background-color: {COLOR_SURFACE}; border-radius: 8px; border: 1px solid #333;")
        right_layout = QVBoxLayout(right_panel)
        
        form_label = QLabel("VENDOR DETAILS")
        form_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #aaa; margin-bottom: 10px;")
        right_layout.addWidget(form_label)
        
        self.form_layout = QFormLayout()
        self.form_layout.setSpacing(15)
        
        self.inp_name = QLineEdit()
        self.inp_name.setPlaceholderText("Official Business Name")
        self.inp_name.setStyleSheet(ui_theme.get_lineedit_style())
        
        self.inp_rep = QLineEdit()
        self.inp_rep.setPlaceholderText("Representative Name")
        self.inp_rep.setStyleSheet(ui_theme.get_lineedit_style())
        
        self.inp_phone = QLineEdit()
        self.inp_phone.setPlaceholderText("Contact Number")
        self.inp_phone.setStyleSheet(ui_theme.get_lineedit_style())
        
        self.inp_address = QLineEdit()
        self.inp_address.setPlaceholderText("Billing Address")
        self.inp_address.setStyleSheet(ui_theme.get_lineedit_style())
        
        self.inp_gstin = QLineEdit()
        self.inp_gstin.setPlaceholderText("GSTIN / Tax ID")
        self.inp_gstin.setStyleSheet(ui_theme.get_lineedit_style())
        
        self.inp_notes = QLineEdit()
        self.inp_notes.setPlaceholderText("Additional Notes")
        self.inp_notes.setStyleSheet(ui_theme.get_lineedit_style())
        
        self.form_layout.addRow("Name *", self.inp_name)
        self.form_layout.addRow("Rep Name", self.inp_rep)
        self.form_layout.addRow("Phone", self.inp_phone)
        self.form_layout.addRow("Address", self.inp_address)
        self.form_layout.addRow("GSTIN", self.inp_gstin)
        self.form_layout.addRow("Notes", self.inp_notes)
        
        right_layout.addLayout(self.form_layout)
        right_layout.addStretch()
        
        # Action Buttons
        self.btn_save = QPushButton("SAVE VENDOR")
        self.btn_save.setStyleSheet(ui_theme.get_neon_action_button())
        self.btn_save.clicked.connect(self.save_vendor)
        right_layout.addWidget(self.btn_save)
        
        content_layout.addWidget(right_panel, stretch=1)
        
        layout.addLayout(content_layout)
        
        self.current_vendor_id = None
        
    def load_vendors(self):
        self.table.setRowCount(0)
        vendors = self.db_manager.get_all_vendors()
        for i, row in enumerate(vendors):
            self.table.insertRow(i)
            # row: id, name, rep, phone, address, gstin, notes
            self.table.setItem(i, 0, QTableWidgetItem(str(row[0])))
            self.table.setItem(i, 1, QTableWidgetItem(row[1]))
            self.table.setItem(i, 2, QTableWidgetItem(row[3]))
            
            # Store full data
            for j in range(3):
                self.table.item(i, j).setData(Qt.ItemDataRole.UserRole, row)
                
    def populate_form(self, item):
        row = item.tableWidget().item(item.row(), 0).data(Qt.ItemDataRole.UserRole)
        if row:
            self.current_vendor_id = row[0]
            self.inp_name.setText(row[1])
            self.inp_rep.setText(row[2])
            self.inp_phone.setText(row[3])
            self.inp_address.setText(row[4])
            self.inp_gstin.setText(row[5])
            self.inp_notes.setText(row[6])
            self.btn_save.setText("UPDATE VENDOR")
            
    def clear_form(self):
        self.current_vendor_id = None
        self.inp_name.clear()
        self.inp_rep.clear()
        self.inp_phone.clear()
        self.inp_address.clear()
        self.inp_gstin.clear()
        self.inp_notes.clear()
        self.btn_save.setText("ADD VENDOR")
        self.table.clearSelection()
        
    def save_vendor(self):
        name = self.inp_name.text().strip()
        if not name:
            ProMessageBox.warning(self, "Validation Error", "Vendor Name is required.")
            return
            
        rep = self.inp_rep.text().strip()
        phone = self.inp_phone.text().strip()
        addr = self.inp_address.text().strip()
        gstin = self.inp_gstin.text().strip()
        notes = self.inp_notes.text().strip()
        
        if self.current_vendor_id:
            # Update
            success, msg = self.db_manager.update_vendor(self.current_vendor_id, name, rep, phone, addr, gstin, notes)
        else:
            # Add
            success, msg = self.db_manager.add_vendor(name, rep, phone, addr, gstin, notes)
            
        if success:
            self.load_vendors()
            self.clear_form()
            ProMessageBox.information(self, "Success", msg)
        else:
            ProMessageBox.critical(self, "Error", msg)
            
    def delete_vendor(self):
        row = self.table.currentRow()
        if row < 0:
            ProMessageBox.warning(self, "Selection", "Please select a vendor to delete.")
            return
            
        vendor_id = int(self.table.item(row, 0).text())
        name = self.table.item(row, 1).text()
        
        if ProMessageBox.question(self, "Confirm Delete", f"Are you sure you want to delete vendor '{name}'?"):
            success, msg = self.db_manager.delete_vendor(vendor_id)
            if success:
                self.load_vendors()
                self.clear_form()
                ProMessageBox.critical(self, "Error", msg)

class VendorManagerDialog(QDialog):
    """
    Wrapper Dialog for VendorManagerWidget.
    """
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Vendor Management System")
        self.resize(900, 650)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        
        self.widget = VendorManagerWidget(db_manager, self)
        layout.addWidget(self.widget)
