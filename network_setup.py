"""
Network Setup Dialog - First-Time Server/Client Configuration
Shown when network_config.json doesn't exist (first launch or reset).
"""
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
                             QLineEdit, QFrame, QGraphicsDropShadowEffect)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from styles import COLOR_ACCENT_CYAN, COLOR_ACCENT_GREEN, COLOR_BACKGROUND
from logger import app_logger
import db_config


# --- Shared Styles ---
CARD_STYLE = """
    QFrame {{
        background-color: {bg};
        border: 2px solid {border};
        border-radius: 12px;
    }}
    QFrame:hover {{
        border-color: {hover};
    }}
"""

BTN_STYLE = """
    QPushButton {{
        background-color: rgba({r}, {g}, {b}, 0.1);
        color: {color};
        border: 2px solid {color};
        border-radius: 8px;
        font-size: 14px;
        font-weight: bold;
        padding: 12px;
    }}
    QPushButton:hover {{
        background-color: {color};
        color: #000;
    }}
"""


class NetworkSetupDialog(QDialog):
    """First-time network setup - choose Server or Client mode."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SpareParts Pro - Network Setup")
        self.setFixedSize(520, 480)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setup_ui()
    
    def setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Main Card
        card = QFrame()
        card.setFixedSize(480, 440)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: #080810;
                border: 2px solid {COLOR_ACCENT_CYAN};
                border-radius: 15px;
            }}
        """)
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(COLOR_ACCENT_CYAN))
        shadow.setOffset(0, 0)
        card.setGraphicsEffect(shadow)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(12)
        
        # Header
        title = QLabel("🌐 NETWORK SETUP")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {COLOR_ACCENT_CYAN}; font-size: 20px; font-weight: bold; letter-spacing: 2px; border: none;")
        layout.addWidget(title)
        
        subtitle = QLabel("Configure this PC for multi-computer access")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #888; font-size: 11px; border: none;")
        layout.addWidget(subtitle)
        
        layout.addSpacing(10)
        
        # --- SERVER BUTTON ---
        btn_server = QPushButton("🖥️  MAIN PC (SERVER)")
        btn_server.setFixedHeight(55)
        btn_server.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_server.setStyleSheet(BTN_STYLE.format(r=0, g=229, b=255, color=COLOR_ACCENT_CYAN))
        btn_server.clicked.connect(self.select_server)
        layout.addWidget(btn_server)
        
        lbl_server = QLabel("This is the main shop PC. Database stays here.\nOther PCs will connect to this machine.")
        lbl_server.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_server.setStyleSheet("color: #666; font-size: 10px; border: none;")
        layout.addWidget(lbl_server)
        
        # Separator
        sep = QLabel("─────────── OR ───────────")
        sep.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sep.setStyleSheet("color: #333; font-size: 11px; border: none; margin: 5px 0;")
        layout.addWidget(sep)
        
        # --- CLIENT BUTTON ---
        btn_client = QPushButton("💻  COUNTER PC (CLIENT)")
        btn_client.setFixedHeight(55)
        btn_client.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_client.setStyleSheet(BTN_STYLE.format(r=0, g=255, b=65, color=COLOR_ACCENT_GREEN))
        btn_client.clicked.connect(self.select_client)
        layout.addWidget(btn_client)
        
        lbl_client = QLabel("This PC connects to the main server PC.\nYou'll need the server's name or IP address.")
        lbl_client.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_client.setStyleSheet("color: #666; font-size: 10px; border: none;")
        layout.addWidget(lbl_client)
        
        layout.addStretch()
        
        # Close
        btn_close = QPushButton("CANCEL")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet("color: #555; border: none; font-weight: bold; background: transparent;")
        btn_close.clicked.connect(self.reject)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignCenter)
        
        outer.addWidget(card)
    
    def select_server(self):
        """Server mode selected - show info dialog then save."""
        dlg = ServerInfoDialog(self)
        if dlg.exec():
            db_config.save_config("SERVER")
            self.accept()
    
    def select_client(self):
        """Client mode selected - show IP entry dialog."""
        dlg = ClientSetupDialog(self)
        if dlg.exec():
            self.accept()


class ServerInfoDialog(QDialog):
    """Shows server info: IP, computer name, and share instructions."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Server Setup")
        self.setFixedSize(480, 380)
        self.setStyleSheet(f"background-color: #0a0a14; color: white;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(12)
        
        title = QLabel("🖥️ SERVER MODE")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {COLOR_ACCENT_CYAN}; font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        
        # PC Info
        ip = db_config.get_local_ip()
        pc_name = db_config.get_computer_name()
        share_path = db_config.get_share_path()
        
        info_frame = QFrame()
        info_frame.setStyleSheet("background-color: #111; border: 1px solid #333; border-radius: 8px; padding: 10px;")
        info_layout = QVBoxLayout(info_frame)
        info_layout.setSpacing(8)
        
        lbl_ip = QLabel(f"🌐 This PC's IP:  {ip}")
        lbl_ip.setStyleSheet(f"color: {COLOR_ACCENT_GREEN}; font-size: 14px; font-weight: bold; border: none;")
        info_layout.addWidget(lbl_ip)
        
        lbl_name = QLabel(f"💻 Computer Name:  {pc_name}")
        lbl_name.setStyleSheet(f"color: {COLOR_ACCENT_CYAN}; font-size: 14px; font-weight: bold; border: none;")
        info_layout.addWidget(lbl_name)
        
        layout.addWidget(info_frame)
        
        # Share Instructions
        lbl_instr = QLabel("📋 SETUP INSTRUCTIONS:")
        lbl_instr.setStyleSheet(f"color: {COLOR_ACCENT_CYAN}; font-weight: bold; margin-top: 5px;")
        layout.addWidget(lbl_instr)
        
        steps = QLabel(
            f"1. Open File Explorer → Navigate to:\n"
            f"   {share_path}\n\n"
            f"2. Right-click 'data' folder → Properties → Sharing\n\n"
            f"3. Share as: SparePartsDB\n"
            f"   (Give Read/Write access to Everyone)\n\n"
            f"4. Tell client PCs to enter:\n"
            f"   {pc_name}  or  {ip}"
        )
        steps.setStyleSheet("color: #aaa; font-size: 11px; background: #0d0d15; padding: 10px; border-radius: 6px;")
        steps.setWordWrap(True)
        layout.addWidget(steps)
        
        # Buttons
        btn_row = QHBoxLayout()
        
        btn_cancel = QPushButton("← Back")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setStyleSheet("color: #888; border: 1px solid #444; border-radius: 6px; padding: 8px 20px;")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        
        btn_save = QPushButton("✓ CONFIRM SERVER MODE")
        btn_save.setFixedHeight(40)
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_ACCENT_CYAN};
                color: #000;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{ background-color: #33f5ff; }}
        """)
        btn_save.clicked.connect(self.accept)
        btn_row.addWidget(btn_save)
        
        layout.addLayout(btn_row)


class ClientSetupDialog(QDialog):
    """Client mode - enter server IP/name and test connection."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Client Setup")
        self.setFixedSize(460, 340)
        self.setStyleSheet(f"background-color: #0a0a14; color: white;")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(12)
        
        title = QLabel("💻 CLIENT MODE")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {COLOR_ACCENT_GREEN}; font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        
        subtitle = QLabel("Enter the Server PC's name or IP address")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(subtitle)
        
        layout.addSpacing(5)
        
        # Server Input
        lbl = QLabel("Server Name or IP:")
        lbl.setStyleSheet(f"color: {COLOR_ACCENT_CYAN}; font-weight: bold;")
        layout.addWidget(lbl)
        
        self.input_server = QLineEdit()
        self.input_server.setPlaceholderText("e.g.  SHOP-PC  or  192.168.1.5")
        self.input_server.setFixedHeight(40)
        self.input_server.setStyleSheet("""
            QLineEdit {
                background-color: #111;
                color: #00e5ff;
                border: 2px solid #333;
                border-radius: 8px;
                padding: 0 12px;
                font-size: 14px;
                font-weight: bold;
            }
            QLineEdit:focus {
                border-color: #00e5ff;
            }
        """)
        layout.addWidget(self.input_server)
        
        # Share Name
        lbl_share = QLabel("Shared Folder Name:")
        lbl_share.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(lbl_share)
        
        self.input_share = QLineEdit("SparePartsDB")
        self.input_share.setFixedHeight(36)
        self.input_share.setStyleSheet("""
            QLineEdit {
                background-color: #111;
                color: #aaa;
                border: 1px solid #333;
                border-radius: 6px;
                padding: 0 12px;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.input_share)
        
        # Test Connection Button
        self.btn_test = QPushButton("🔍 TEST CONNECTION")
        self.btn_test.setFixedHeight(36)
        self.btn_test.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_test.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 152, 0, 0.1);
                color: #ff9800;
                border: 1px solid #ff9800;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #ff9800;
                color: #000;
            }
        """)
        self.btn_test.clicked.connect(self.test_connection)
        layout.addWidget(self.btn_test)
        
        # Status
        self.lbl_status = QLabel("")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet("font-size: 11px;")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)
        
        # Buttons
        btn_row = QHBoxLayout()
        
        btn_cancel = QPushButton("← Back")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setStyleSheet("color: #888; border: 1px solid #444; border-radius: 6px; padding: 8px 20px;")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        
        self.btn_save = QPushButton("✓ SAVE & CONNECT")
        self.btn_save.setFixedHeight(40)
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLOR_ACCENT_GREEN};
                color: #000;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{ background-color: #33ff55; }}
        """)
        self.btn_save.clicked.connect(self.save_and_connect)
        btn_row.addWidget(self.btn_save)
        
        layout.addLayout(btn_row)
    
    def test_connection(self):
        """Test if the server path is reachable."""
        server = self.input_server.text().strip()
        share = self.input_share.text().strip() or "SparePartsDB"
        
        if not server:
            self.lbl_status.setText("⚠️ Please enter a server name or IP")
            self.lbl_status.setStyleSheet("color: #ff9800; font-size: 11px;")
            return
        
        self.lbl_status.setText("🔄 Testing connection...")
        self.lbl_status.setStyleSheet("color: #888; font-size: 11px;")
        self.lbl_status.repaint()
        
        success, msg = db_config.test_connection(server, share)
        
        if success:
            self.lbl_status.setText(f"✅ {msg}")
            self.lbl_status.setStyleSheet(f"color: {COLOR_ACCENT_GREEN}; font-size: 11px;")
        else:
            self.lbl_status.setText(f"❌ {msg}")
            self.lbl_status.setStyleSheet("color: #ff4444; font-size: 11px;")
    
    def save_and_connect(self):
        """Save client config and close dialog."""
        server = self.input_server.text().strip()
        share = self.input_share.text().strip() or "SparePartsDB"
        
        if not server:
            self.lbl_status.setText("⚠️ Please enter a server name or IP")
            self.lbl_status.setStyleSheet("color: #ff9800; font-size: 11px;")
            return
        
        db_config.save_config("CLIENT", server, share)
        app_logger.info(f"Client mode saved: server={server}, share={share}")
        self.accept()
