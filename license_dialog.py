import ui_theme
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, QFrame, QMessageBox)
from PyQt6.QtCore import Qt
from styles import COLOR_ACCENT_CYAN, COLOR_BACKGROUND, STYLE_INPUT_CYBER

class LicenseDialog(QDialog):
    def __init__(self, license_verifier, parent=None):
        super().__init__(parent)
        self.verifier = license_verifier
        self.setWindowTitle("SpareParts Pro - Activation")
        self.setFixedSize(450, 350)
        self.setStyleSheet(f"background-color: {COLOR_BACKGROUND}; color: white; border: 1px solid #333;")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        
        self.setup_ui()
        self.refresh_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Header
        self.lbl_header = QLabel("SYSTEM ACTIVATION")
        self.lbl_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_header.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {COLOR_ACCENT_CYAN}; letter-spacing: 2px;")
        layout.addWidget(self.lbl_header)
        
        # Status Text
        self.lbl_status = QLabel("Checking license status...")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet("font-size: 14px; color: #aaa; margin-bottom: 10px;")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)
        
        # Input Field
        self.in_key = QLineEdit()
        self.in_key.setPlaceholderText("ENTER LICENSE KEY")
        self.in_key.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.in_key.setStyleSheet(STYLE_INPUT_CYBER + "font-size: 16px; padding: 10px;")
        layout.addWidget(self.in_key)
        
        # Buttons
        self.btn_activate = QPushButton("ACTIVATE SYSTEM")
        self.btn_activate.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_activate.setStyleSheet(ui_theme.get_primary_button_style())
        self.btn_activate.clicked.connect(self.do_activate)
        layout.addWidget(self.btn_activate)
        
        self.btn_trial = QPushButton("START 15-DAY TRIAL")
        self.btn_trial.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_trial.setStyleSheet(f"background: transparent; color: {COLOR_ACCENT_CYAN}; border: none; font-size: 12px; text-decoration: underline;")
        self.btn_trial.clicked.connect(self.do_trial)
        layout.addWidget(self.btn_trial)
        
        # Exit Button
        self.btn_exit = QPushButton("EXIT APPLICATION")
        self.btn_exit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_exit.setStyleSheet("background: transparent; color: #666; border: none; font-size: 10px;")
        self.btn_exit.clicked.connect(self.reject)
        layout.addWidget(self.btn_exit)
        
    def refresh_ui(self):
        status, days = self.verifier.check_license()
        
        if status == 'NEW':
            self.lbl_status.setText("Welcome to SpareParts Pro.\nPlease activate your license or start a trial.")
            self.btn_trial.setVisible(True)
            self.btn_trial.setText("START 15-DAY TRIAL")
            
        elif status == 'TRIAL':
            self.lbl_status.setText(f"TRIAL MODE ACTIVE\n{days} Days Remaining")
            self.lbl_status.setStyleSheet("font-size: 16px; color: #00ff88; font-weight: bold;")
            self.btn_trial.setVisible(True)
            self.btn_trial.setText("CONTINUE TRIAL >>") # Allow proceeding
            
        elif status == 'EXPIRED':
            self.lbl_status.setText("TRIAL EXPIRED\nPlease enter a valid license key to continue.")
            self.lbl_status.setStyleSheet("font-size: 14px; color: #ff4444; font-weight: bold;")
            self.btn_trial.setVisible(False)
            
        elif status == 'ACTIVE':
            self.accept() # Should not happen often if logic correct

    def do_activate(self):
        key = self.in_key.text()
        if not key:
            return
            
        if self.verifier.activate_license(key):
            QMessageBox.information(self, "Success", "System Activated Successfully!")
            self.accept()
        else:
            QMessageBox.critical(self, "Failed", "Invalid License Key.")

    def do_trial(self):
        status, _ = self.verifier.check_license()
        if status == 'TRIAL':
            self.accept() # Just continue
            return
            
        if self.verifier.start_trial():
            self.refresh_ui()
            # Auto continue or ask? 
            QMessageBox.information(self, "Trial Started", "15-Day Trial Started Successfully.")
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "Could not start trial.")
