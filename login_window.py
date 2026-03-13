from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QFrame, QHBoxLayout, QGraphicsDropShadowEffect, QWidget, QInputDialog)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRectF, QPropertyAnimation, pyqtProperty, QEasingCurve
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPixmap, QBrush, QPen, QRadialGradient, QConicalGradient
from styles import COLOR_BACKGROUND, COLOR_ACCENT_CYAN, STYLE_NEON_BUTTON, STYLE_INPUT_CYBER
import os

class AvatarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(80, 80)
        self.pixmap = None
        self._wipe_angle = 0 # 0 to 360
        self._glow_alpha = 0
        
    @pyqtProperty(float)
    def wipe_angle(self):
        return self._wipe_angle
        
    @wipe_angle.setter
    def wipe_angle(self, val):
        self._wipe_angle = val
        self.update()
        
    def set_image(self, image_path):
        if image_path and os.path.exists(image_path):
            self.pixmap = QPixmap(image_path)
        else:
            self.pixmap = None # Should draw a placeholder
            
        # Trigger Animation
        self.anim = QPropertyAnimation(self, b"wipe_angle")
        self.anim.setDuration(800)
        self.anim.setStartValue(0)
        self.anim.setEndValue(360)
        self.anim.setEasingCurve(QEasingCurve.Type.OutExpo)
        self.anim.start()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        cx, cy = rect.width() / 2, rect.height() / 2
        radius = 35
        
        # 1. Background Placeholder (Dark Circle)
        painter.setBrush(QColor(10, 15, 25))
        painter.setPen(QPen(QColor(COLOR_ACCENT_CYAN), 2))
        painter.drawEllipse(int(cx - radius), int(cy - radius), int(radius * 2), int(radius * 2))
        
        if self.pixmap:
            # 2. Draw Image with Wipe Mask
            painter.save()
            path = QPainterPath()
            path.moveTo(cx, cy)
            # Pie slice for wipe effect
            path.arcTo(QRectF(cx - radius, cy - radius, radius * 2, radius * 2), 90, -self._wipe_angle)
            path.closeSubpath()
            
            painter.setClipPath(path)
            
            # Scale pixmap to cover
            scaled = self.pixmap.scaled(70, 70, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            
            # Draw center cropped
            px = cx - scaled.width() / 2
            py = cy - scaled.height() / 2
            painter.drawPixmap(int(px), int(py), scaled)
            painter.restore()
            
        # 3. Glowing Ring Overlay
        painter.setBrush(Qt.BrushStyle.NoBrush)
        pen = QPen(QColor(COLOR_ACCENT_CYAN))
        pen.setWidth(3)
        painter.setPen(pen)
        painter.drawEllipse(int(cx - radius), int(cy - radius), int(radius * 2), int(radius * 2))

class LoginWindow(QDialog):
    login_success = pyqtSignal(str, str) # role, username 

    def __init__(self, db_manager, MainWindow_class=None):
        super().__init__()
        self.db_manager = db_manager
        self.MainWindow_class = MainWindow_class
        self.setWindowTitle("SpareParts Pro - Access Control")
        self.resize(500, 480)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.setup_ui()
        
        # Debounce timer for user lookup
        self.user_check_timer = QTimer()
        self.user_check_timer.setSingleShot(True)
        self.user_check_timer.timeout.connect(self.check_user_avatar)
        
        self.user_in.textChanged.connect(self.on_user_text_changed)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Central Card
        card = QFrame()
        card.setFixedSize(380, 420)
        # Clean Border
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #080810; 
                border: 2px solid {COLOR_ACCENT_CYAN}; 
                border-radius: 15px;
            }}
        """)
        
        # Glow Effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(COLOR_ACCENT_CYAN))
        shadow.setOffset(0, 0)
        card.setGraphicsEffect(shadow)
        
        # Inner Layout
        card_layout = QVBoxLayout(card)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.setSpacing(10) 
        card_layout.setContentsMargins(30, 20, 30, 25)
        
        # Avatar Widget (Pro Visual)
        self.avatar = AvatarWidget()
        card_layout.addWidget(self.avatar, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Header
        title = QLabel("ACCESS CONTROL")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {COLOR_ACCENT_CYAN}; font-size: 18px; font-weight: bold; border: none; letter-spacing: 2px; background: transparent;")
        card_layout.addWidget(title)
        
        sub_title = QLabel("SpareParts Pro v1.5")
        sub_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_title.setStyleSheet(f"color: {COLOR_ACCENT_CYAN}; font-size: 12px; border: none; opacity: 0.8; background: transparent;")
        card_layout.addWidget(sub_title)
        
        # Inputs
        self.user_in = QLineEdit()
        self.user_in.setPlaceholderText("USERNAME ID")
        self.user_in.setStyleSheet(STYLE_INPUT_CYBER)
        self.user_in.setFixedHeight(36)
        self.user_in.returnPressed.connect(lambda: self.pass_in.setFocus()) 
        card_layout.addWidget(self.user_in)
        
        self.pass_in = QLineEdit()
        self.pass_in.setPlaceholderText("PASSWORD")
        self.pass_in.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_in.setStyleSheet(STYLE_INPUT_CYBER)
        self.pass_in.setFixedHeight(36)
        self.pass_in.returnPressed.connect(self.handle_login) 
        card_layout.addWidget(self.pass_in)
        
        # Login Button
        self.btn_login = QPushButton("AUTHENTICATE")
        self.btn_login.setFixedHeight(40)
        self.btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_login.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(0, 229, 255, 0.1); 
                color: {COLOR_ACCENT_CYAN}; 
                border: 1px solid {COLOR_ACCENT_CYAN}; 
                border-radius: 6px; 
                font-size: 13px; 
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {COLOR_ACCENT_CYAN};
                border: 1px solid {COLOR_ACCENT_CYAN};
                color: #000;
            }}
        """)
        self.btn_login.clicked.connect(self.handle_login)
        card_layout.addWidget(self.btn_login)
        
        # Status Label
        self.status = QLabel("")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setStyleSheet("color: #ff4444; font-size: 12px; font-weight: bold; border: none;")
        card_layout.addWidget(self.status)
        
        # Close Button
        btn_close = QPushButton("SHUTDOWN")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet("color: #555; border: none; font-weight: bold;")
        btn_close.clicked.connect(self.reject)
        card_layout.addWidget(btn_close)
        
        # Admin Recovery Link
        self.lbl_recovery = QLabel("ADMIN RECOVERY PROTOCOL")
        self.lbl_recovery.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_recovery.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lbl_recovery.setStyleSheet(f"color: #555; font-size: 10px; letter-spacing: 1px; margin-top: 5px;")
        self.lbl_recovery.mousePressEvent = self.initiate_recovery
        card_layout.addWidget(self.lbl_recovery)
        
        main_layout.addWidget(card)

    def on_user_text_changed(self):
        self.user_check_timer.start(500) # Check 500ms after user stops typing

    def check_user_avatar(self):
        username = self.user_in.text().strip()
        if not username:
             self.avatar.set_image(None)
             return
             
        profile = self.db_manager.get_user_profile(username)
        if profile and profile.get("profile_pic"):
             # Construct path
             # Need to find absolute path to data/avatars
             import sys
             if getattr(sys, 'frozen', False):
                 base = os.path.dirname(sys.executable)
             else:
                 base = os.path.dirname(os.path.abspath(__file__))
             
             # Check multiple possible locations for dev vs build
             pic_path = os.path.join(base, "data", "avatars", profile["profile_pic"])
             if not os.path.exists(pic_path):
                 # Try AppData
                 app_data = os.path.join(os.environ.get("APPDATA", ""), "SparePartsPro_v1.5", "data", "avatars", profile["profile_pic"])
                 if os.path.exists(app_data):
                     pic_path = app_data
             
             self.avatar.set_image(pic_path)
        else:
             self.avatar.set_image(None)
        

    def initiate_recovery(self, event):
        """Admin Password Reset via PIN"""
        user, ok = QInputDialog.getText(self, "ADMIN RECOVERY", "ENTER ADMIN USERNAME:", QLineEdit.EchoMode.Normal)
        if not ok or not user: return
        
        pin, ok = QInputDialog.getText(self, "SECURITY CLEARANCE", f"ENTER RECOVERY PIN FOR {user}:", QLineEdit.EchoMode.Password)
        if not ok or not pin: return
        
        # Verify
        from custom_components import ProMessageBox
        
        valid, uid = self.db_manager.verify_recovery_pin(user, pin)
        if valid:
            new_pass, ok = QInputDialog.getText(self, "RESET APPROVED", "ENTER NEW PASSWORD:", QLineEdit.EchoMode.Password)
            if ok and new_pass:
                success, msg = self.db_manager.reset_password(uid, new_pass)
                if success:
                    ProMessageBox.information(self, "SUCCESS", "PASSWORD RESET COMPLETE.\nPLEASE LOGIN.")
                    self.db_manager.log_activity(user, "PIN_RESET", "Password reset via Recovery PIN")
                else:
                    ProMessageBox.warning(self, "ERROR", msg)
        else:
            ProMessageBox.warning(self, "ACCESS DENIED", "INVALID USERNAME OR RECOVERY PIN.")
            self.db_manager.log_activity(user, "PIN_FAIL", "Failed recovery attempt")

    def handle_login(self):
        u = self.user_in.text().strip()
        p = self.pass_in.text().strip()
        
        if not u or not p:
            self.status.setText("Enter Username & Password")
            return
            
        valid, result = self.db_manager.verify_login(u, p)
        if valid:
            self.login_success.emit(result, u)  # result = role
            self.accept()
        else:
            # result = specific error message
            self.status.setText(result if result else "ACCESS DENIED")
            self.pass_in.clear()
            self.user_in.setFocus()
