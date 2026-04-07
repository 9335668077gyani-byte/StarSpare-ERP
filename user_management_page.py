from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QFrame, QDialog, QFormLayout, QDialogButtonBox, 
                             QGridLayout, QScrollArea, QComboBox, QInputDialog, QFileDialog, QTableWidget, QHeaderView, QTableWidgetItem, QCheckBox, QGroupBox)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt6.QtGui import QColor, QFont, QIcon, QPixmap, QPainter, QBitmap
from custom_components import ProMessageBox, ProDialog, ProTableDelegate
import ui_theme
from styles import (COLOR_BACKGROUND, COLOR_SURFACE, COLOR_ACCENT_CYAN, COLOR_ACCENT_RED,
                    COLOR_ACCENT_GREEN, COLOR_ACCENT_YELLOW, COLOR_TEXT_PRIMARY,
                    STYLE_TABLE_CYBER)
import random
import os
import shutil
from path_utils import get_app_data_path  # type: ignore

class SecurityCard(QFrame):
    """
    Holographic Identity Card for a User.
    """
    action_triggered = pyqtSignal(str, int) # action (edit/delete), user_id

    def __init__(self, user_data, parent=None):
        super().__init__(parent)
        self.user_data = user_data # (id, username, password, role, last_login, perm, profile_pic)
        self.user_id = user_data[0]
        self.username = user_data[1]
        self.role = user_data[3]
        self.last_login = user_data[4] if len(user_data) > 4 else "N/A"
        self.profile_pic = user_data[6] if len(user_data) > 6 else None
        
        self.setFixedSize(300, 220) # Slightly Taller
        self.setStyleSheet(f"""
            SecurityCard {{
                background-color: rgba(11, 16, 32, 0.9);
                border: 1px solid {COLOR_ACCENT_CYAN};
                border-radius: 10px;
            }}
            SecurityCard:hover {{
                background-color: rgba(0, 242, 255, 0.05);
                border: 1px solid #fff;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Header: Avatar + Role
        header_layout = QHBoxLayout()
        
        # Avatar logic
        avatar_color = COLOR_ACCENT_GREEN if self.role == "ADMIN" else COLOR_ACCENT_CYAN
        if self.profile_pic and os.path.exists(self.profile_pic):
             from PyQt6.QtGui import QPainterPath
             avatar = QLabel()
             avatar.setFixedSize(50, 50)
             pixmap = QPixmap(self.profile_pic)
             
             # perfectly crop to 50x50 center to prevent bleeding out of label
             scaled = pixmap.scaled(50, 50, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
             crop_x = (scaled.width() - 50) // 2
             crop_y = (scaled.height() - 50) // 2
             cropped = scaled.copy(crop_x, crop_y, 50, 50)
             
             circular = QPixmap(50, 50)
             circular.fill(Qt.GlobalColor.transparent)
             
             painter = QPainter(circular)
             painter.setRenderHint(QPainter.RenderHint.Antialiasing)
             
             path = QPainterPath()
             # Clip exactly inside the border
             path.addEllipse(1, 1, 48, 48)
             painter.setClipPath(path)
             
             painter.drawPixmap(0, 0, cropped)
             
             # Now draw the cyan/green border directly onto the image
             painter.setClipping(False)
             from PyQt6.QtGui import QPen, QColor
             pen = QPen(QColor(avatar_color))
             pen.setWidth(2)
             painter.setPen(pen)
             painter.setBrush(Qt.BrushStyle.NoBrush)
             painter.drawEllipse(1, 1, 48, 48)
             
             painter.end()
             
             avatar.setPixmap(circular)
             
             # Clean CSS - No borders needed as it's baked in the image
             avatar.setStyleSheet("background: transparent; border: none;")
        else:
            # Fallback Initials
            avatar = QLabel(self.username[:1].upper())
            avatar.setFixedSize(50, 50)
            avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
            avatar.setStyleSheet(f"""
                background-color: transparent;
                color: {avatar_color};
                border: 2px solid {avatar_color};
                border-radius: 25px;
                font-size: 20px;
                font-weight: bold;
            """)
            
        header_layout.addWidget(avatar)
        
        # Info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        lbl_name = QLabel(self.username.upper())
        lbl_name.setStyleSheet(f"color: {COLOR_ACCENT_CYAN}; font-size: 15px; font-weight: bold; background: transparent;")
        
        lbl_role = QLabel(f"[{self.role}]")
        lbl_role.setStyleSheet(f"color: {ui_theme.COLOR_TEXT_MUTED}; font-size: 11px; font-weight: bold; letter-spacing: 1px; background: transparent;")
        
        info_layout.addWidget(lbl_name)
        info_layout.addWidget(lbl_role)
        header_layout.addLayout(info_layout)
        header_layout.addStretch()
        
        # Status Light
        status = QLabel("●")
        status_color = COLOR_ACCENT_GREEN if self.role == "ADMIN" else COLOR_ACCENT_CYAN
        status.setStyleSheet(f"color: {status_color}; font-size: 14px; background: transparent;")
        header_layout.addWidget(status)
        
        layout.addLayout(header_layout)
        
        # Grid Pattern Overlay
        grid_line = QFrame()
        grid_line.setFrameShape(QFrame.Shape.HLine)
        grid_line.setStyleSheet(f"color: rgba(0, 242, 255, 0.2);")
        layout.addWidget(grid_line)
        
        # Details
        lbl_login_title = QLabel("LAST LOGIN RECORDED:")
        lbl_login_title.setStyleSheet(f"color: {ui_theme.COLOR_TEXT_MUTED}; font-size: 10px; font-weight: bold; letter-spacing: 1px; background: transparent;")
        
        lbl_login_val = QLabel(f"{self.last_login}")
        lbl_login_val.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: 13px; background: transparent;")
        
        layout.addWidget(lbl_login_title)
        layout.addWidget(lbl_login_val)
        
        layout.addStretch()
        
        # Actions Row 1
        row1 = QHBoxLayout()
        row1.setSpacing(5)
        
        btn_history = QPushButton("HISTORY")
        btn_history.setFlat(True)
        btn_history.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_history.setStyleSheet(f"color: {COLOR_ACCENT_CYAN}; font-size: 10px; border: none; text-decoration: underline;")
        btn_history.clicked.connect(lambda: self.action_triggered.emit("history", self.user_id))
        row1.addWidget(btn_history)
        row1.addStretch()

        # Row 2: Edit | Revoke
        row2 = QHBoxLayout()
        row2.setSpacing(10)
        
        btn_edit = QPushButton("EDIT PROFILE")
        btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_edit.setStyleSheet(f"""
        QPushButton {{
            background: transparent; border: 1px solid {COLOR_ACCENT_CYAN}; color: {COLOR_ACCENT_CYAN};
            border-radius: 4px; font-size: 10px; padding: 5px;
        }}
        QPushButton:hover {{ background: {COLOR_ACCENT_CYAN}; color: black; }}
        """)
        btn_edit.clicked.connect(lambda: self.action_triggered.emit("edit", self.user_id))
        row2.addWidget(btn_edit)
        
        if self.username != "admin":
             btn_revoke = QPushButton("REVOKE")
             btn_revoke.setCursor(Qt.CursorShape.PointingHandCursor)
             btn_revoke.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; border: 1px solid {COLOR_ACCENT_RED}; color: {COLOR_ACCENT_RED};
                    border-radius: 4px; font-size: 10px; padding: 5px;
                }}
                QPushButton:hover {{ background: {COLOR_ACCENT_RED}; color: white; }}
             """)
             btn_revoke.clicked.connect(lambda: self.action_triggered.emit("delete", self.user_id))
             
             row2.addWidget(btn_revoke)
             
             btn_reset = QPushButton("RESET KEY")
             btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
             btn_reset.setStyleSheet(f"color: {COLOR_ACCENT_YELLOW}; border: none; font-size: 9px;")
             btn_reset.clicked.connect(lambda: self.action_triggered.emit("reset", self.user_id))
             
             layout.addLayout(row1)
             layout.addLayout(row2)
             layout.addWidget(btn_reset, alignment=Qt.AlignmentFlag.AlignCenter)
        else:
             # Admin Card Layout (No Revoke/Reset for self here, just Edit)
             lbl_master = QLabel("MASTER CONTROL")
             lbl_master.setStyleSheet(f"color: {COLOR_ACCENT_GREEN}; font-size: 10px; letter-spacing: 1px; border: none;")
             row2.addWidget(lbl_master)
             
             layout.addLayout(row1)
             layout.addLayout(row2)

class LiveSecurityFeed(QFrame):
    """
    Scrolling Log of System Actions.
    """
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.setFixedWidth(300)
        self.setStyleSheet(f"""
            background-color: #080a10;
            border-left: 1px solid {COLOR_ACCENT_CYAN};
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 20, 10, 20)
        layout.setSpacing(10)
        
        title = QLabel("LIVE SECURITY FEED")
        title.setStyleSheet(f"color: {COLOR_ACCENT_CYAN}; font-weight: bold; font-family: 'Consolas'; letter-spacing: 2px;")
        layout.addWidget(title)
        
        # Log Container
        self.log_container = QWidget()
        self.log_layout = QVBoxLayout(self.log_container)
        self.log_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.log_layout.setSpacing(8)
        self.log_layout.setContentsMargins(0,0,0,0)
        
        scroll = QScrollArea()
        scroll.setWidget(self.log_container)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(scroll)
        
        # Timer for refresh
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_logs)
        self.timer.start(3000) # 3s refresh
        
        self.refresh_logs()
        
    def refresh_logs(self):
        # Clear old logs (simple re-render)
        for i in reversed(range(self.log_layout.count())): 
            self.log_layout.itemAt(i).widget().setParent(None)
            
        logs = self.db_manager.get_recent_activity(15)
        
        for user, action, det, time in logs:
            # Format: [HH:MM] USER :: ACTION
            t_str = time.split(' ')[1] if ' ' in time else time
            
            row = QFrame()
            row.setStyleSheet("background: rgba(255,255,255,0.03); border-radius: 4px;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(5, 5, 5, 5)
            
            lbl = QLabel(f"<font color='#555'>[{t_str}]</font> <font color='{COLOR_ACCENT_CYAN}'>{user}</font> :: <font color='white'>{action}</font>")
            lbl.setFont(QFont("Consolas", 9))
            rl.addWidget(lbl)
            
            self.log_layout.addWidget(row)

class UserDialog(QDialog):
    def __init__(self, parent=None, user_data=None):
        super().__init__(parent)
        self.setWindowTitle("IDENTITY CONFIGURATION")
        self.setStyleSheet(f"background-color: #0b1020; color: {COLOR_TEXT_PRIMARY}; border: 1px solid {COLOR_ACCENT_CYAN};")
        self.resize(500, 550) # Taller for permissions
        
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        lbl_title = QLabel("USER PROTOCOL" if not user_data else "OVERRIDE IDENTITY")
        lbl_title.setStyleSheet(ui_theme.get_page_title_style())
        layout.addWidget(lbl_title)
        
        form_layout = QHBoxLayout() # Split Form and Permissions
        
        # Left: Basic Info
        left_form = QFormLayout()
        left_form.setSpacing(15)
        
        self.in_user = QLineEdit()
        self.in_user.setPlaceholderText("CALLSIGN")
        self.in_user.setStyleSheet(ui_theme.get_lineedit_style())
        
        self.in_pass = QLineEdit()
        self.in_pass.setPlaceholderText("ACCESS CODE")
        self.in_pass.setStyleSheet(ui_theme.get_lineedit_style())
        
        self.in_role = QComboBox()
        self.in_role.addItems(["STAFF", "ADMIN"])
        self.in_role.setStyleSheet(ui_theme.get_lineedit_style())
        
        if user_data:
            self.in_user.setText(user_data[1])
            # self.in_user.setReadOnly(True) # ENABLED EDITING
            self.in_pass.setText(user_data[2])
            self.in_role.setCurrentText(user_data[3])
            
        if user_data and len(user_data) > 6:
            self.profile_path = user_data[6]
        else:
            self.profile_path = None
            
        left_form.addRow(QLabel("IDENTITY:"), self.in_user)
        left_form.addRow(QLabel("AUTH CODE:"), self.in_pass)
        left_form.addRow(QLabel("LEVEL:"), self.in_role)
        
        # Photo Upload
        self.btn_photo = QPushButton("UPLOAD PHOTO 📷")
        self.btn_photo.setStyleSheet("background: transparent; border: 1px dashed #555; color: #888; padding: 5px;")
        self.btn_photo.clicked.connect(self.select_photo)
        self.lbl_photo_path = QLabel("No file selected")
        self.lbl_photo_path.setStyleSheet(ui_theme.get_page_title_style())
        
        if self.profile_path:
             self.lbl_photo_path.setText(os.path.basename(self.profile_path))
             self.btn_photo.setText("CHANGE PHOTO 📷")
        
        left_form.addRow(self.btn_photo, self.lbl_photo_path)
        
        # Recovery PIN (Admin Only)
        self.in_pin = QLineEdit()
        self.in_pin.setPlaceholderText("RECOVERY PIN (6-Digit)")
        self.in_pin.setStyleSheet(ui_theme.get_lineedit_style())
        self.in_pin.setMaxLength(6)
        
        if user_data and len(user_data) > 7:
             self.in_pin.setText(user_data[7]) # recovery_pin
        
        left_form.addRow(QLabel("RECOVERY PIN:"), self.in_pin)
        
        left_widget = QWidget()
        left_widget.setLayout(left_form)
        form_layout.addWidget(left_widget, 60)
        
        layout.addLayout(form_layout)
        
        # Permissions Section
        self.perm_group = QGroupBox("ACCESS AUTHORIZATION")
        self.perm_group.setStyleSheet(f"QGroupBox {{ color: {COLOR_ACCENT_CYAN}; font-weight: bold; border: 1px solid #333; margin-top: 10px; padding: 15px; border-radius: 8px; }}")
        perm_layout = QGridLayout(self.perm_group)
        perm_layout.setSpacing(10)
        
        self.checks = {}
        perms = [
            ("can_view_dashboard", "🏠 Dashboard Access"),
            ("can_manage_billing", "💳 Billing & Invoicing"),
            ("can_manage_inventory", "📦 Inventory Management"),
            ("can_edit_inventory", "✏️ Edit Inventory Items"),
            ("can_manage_orders", "📋 Purchase Orders"),
            ("can_manage_expenses", "💸 Expense Tracking"),
            ("can_view_reports", "📊 Sales Reports"),
            ("can_view_catalog", "📖 Parts Catalog"),
            ("can_manage_vendors", "🚚 Vendor Database"),
            ("can_manage_settings", "⚙️ System Settings"),
            ("can_manage_self", "👤 Edit Own Profile"),
            ("can_backup_data", "💾 System Backups")
        ]
        
        current_perms = []
        if user_data and len(user_data) > 5 and user_data[5]:
            import json
            try:
                current_perms = json.loads(user_data[5])
                if not isinstance(current_perms, list): current_perms = []
            except:
                pass
        
        row, col = 0, 0
        for key, label in perms:
            chk = QCheckBox(label)
            chk.setStyleSheet(ui_theme.get_checkbox_style())
            
            if user_data:
                 chk.setChecked(key in current_perms)
            else:
                 # DEFAULT NEW USER: All Checked (Open Access Policy)
                 chk.setChecked(True)
                 
            self.checks[key] = chk
            perm_layout.addWidget(chk, row, col)
            
            col += 1
            if col > 1:
                col = 0
                row += 1
            
        layout.addWidget(self.perm_group)
        
        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        
        btns.button(QDialogButtonBox.StandardButton.Save).setStyleSheet(ui_theme.get_primary_button_style())
        btns.button(QDialogButtonBox.StandardButton.Cancel).setStyleSheet(ui_theme.get_cancel_button_style())
        
        layout.addWidget(btns)
        
        # Connect signal AFTER initializing perm_group
        self.in_role.currentTextChanged.connect(self.toggle_permissions)
        self.toggle_permissions(self.in_role.currentText())
        
    def toggle_permissions(self, role):
        is_admin = role == "ADMIN"
        self.perm_group.setEnabled(not is_admin)
        self.in_pin.setEnabled(is_admin) # Only Admins need Recovery PIN
        if not is_admin:
            self.in_pin.clear()
            
        if is_admin:
            for chk in self.checks.values():
                chk.setChecked(True)
        
    def select_photo(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select Profile Image", "", "Images (*.png *.jpg *.jpeg)")
        if file:
            self.profile_path = file
            self.lbl_photo_path.setText(os.path.basename(file))

    def get_data(self):
        # Collect Permissions
        import json
        selected_perms = [k for k, v in self.checks.items() if v.isChecked()]
        perm_json = json.dumps(selected_perms)
        
        return self.in_user.text(), self.in_pass.text(), self.in_role.currentText(), self.profile_path, perm_json, self.in_pin.text()

class LoginHistoryDialog(ProDialog):
    def __init__(self, parent, username, history_data):
        super().__init__(parent, title=f"ACCESS LOG: {username}", width=500, height=400)
        
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["TIMESTAMP", "DETAILS"])
        table.setStyleSheet(ui_theme.get_table_style())
        
        delegate = ProTableDelegate(table)
        for c in range(table.columnCount()): 
             table.setItemDelegateForColumn(c, delegate)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.setRowCount(len(history_data))
        
        for i, (time, det) in enumerate(history_data):
            item1 = QTableWidgetItem(str(time))
            item1.setData(Qt.ItemDataRole.UserRole, {'type': 'generic'})
            table.setItem(i, 0, item1)
            
            item2 = QTableWidgetItem(str(det))
            item2.setData(Qt.ItemDataRole.UserRole, {'type': 'generic'})
            table.setItem(i, 1, item2)
            
        self.set_content(table)
        
        btn_close = QPushButton("CLOSE")
        btn_close.setStyleSheet(ui_theme.get_primary_button_style())
        btn_close.clicked.connect(self.accept)
        
        hl = QHBoxLayout()
        hl.addStretch()
        hl.addWidget(btn_close)
        self.add_buttons(hl)

    def get_data(self):
        return self.in_user.text(), self.in_pass.text(), self.in_role.currentText()

class UserManagementPage(QWidget):
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        # Get current user context from MainWindow if possible, or assume ADMIN if not passed?
        # IMPORTANT: We need to know WHO is looking at this page.
        # But this class is instantiated in MainWindow. 
        # MainWindow needs to pass the username/role to this page!
        # Currently MainWindow does: page = page_class(self.db_manager)
        # I need to update MainWindow to pass (db_manager, role, username) like InventoryPage
        
        # Temporary fallback until MainWindow is updated
        self.current_role = "ADMIN" 
        self.current_username = "admin"
        
    def set_user_context(self, role, username):
        self.current_role = role
        self.current_username = username
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        # ... logic to hide feed if STAFF ...
        # (This will be refactored in next step once I update MainWindow)
        pass # Placeholder for now, executed below in logic


    def setup_ui(self):
        main_layout = QHBoxLayout(self) # Split: Grid | Live Feed
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Left: Main Grid Area
        left_panel = QWidget()
        l_layout = QVBoxLayout(left_panel)
        l_layout.setContentsMargins(30, 30, 30, 30)
        l_layout.setSpacing(20)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("SECURITY OPERATIONS CENTER")
        title.setStyleSheet(ui_theme.get_page_title_style())
        header.addWidget(title)
        
        header.addStretch()
        
        btn_add = QPushButton("+ NEW AGENT")
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.setStyleSheet(ui_theme.get_primary_button_style())
        btn_add.clicked.connect(lambda: self.open_dialog())
        header.addWidget(btn_add)
        
        l_layout.addLayout(header)
        
        # Grid Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.grid_layout.setSpacing(20)
        
        scroll.setWidget(self.grid_container)
        l_layout.addWidget(scroll)
        
        # --- Developer Section ---
        dev_frame = QFrame()
        dev_frame.setStyleSheet(f"background-color: rgba(255, 68, 68, 0.05); border: 1px dashed {COLOR_ACCENT_RED}; border-radius: 8px;")
        dev_layout = QHBoxLayout(dev_frame)
        dev_layout.setContentsMargins(10, 5, 10, 5)
        
        lbl_dev = QLabel("⚠️ DEV ZONE")
        lbl_dev.setStyleSheet(ui_theme.get_page_title_style())
        dev_layout.addWidget(lbl_dev)
        
        dev_layout.addStretch()
        
        btn_reset_inv = QPushButton("RESET INVOICE SERIES")
        btn_reset_inv.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reset_inv.setStyleSheet(ui_theme.get_icon_btn_red())
        btn_reset_inv.clicked.connect(self.reset_invoice_sequence)
        dev_layout.addWidget(btn_reset_inv)
        
        l_layout.addWidget(dev_frame)
        
        main_layout.addWidget(left_panel)
        
        # Right: Live Feed
        self.feed = LiveSecurityFeed(self.db_manager)
        main_layout.addWidget(self.feed)

    def load_data(self):
        # Clear Grid
        for i in reversed(range(self.grid_layout.count())): 
            self.grid_layout.itemAt(i).widget().setParent(None)
            
        users = self.db_manager.get_all_users() # (id, username, pass, role, last_login, perm, pic)
        
        row, col = 0, 0
        max_cols = 3 # Cards per row
        
        for u in users:
            # Check length to ensure safe unpacking 
            # (defensive coding in case DB returns fewer cols)
            if len(u) < 8: 
                # Pad with None if permissions or pic or pin missing
                u = list(u)
                while len(u) < 8: u.append(None)
                u = tuple(u)
            
            card = SecurityCard(u)
            card.action_triggered.connect(self.handle_card_action)
            self.grid_layout.addWidget(card, row, col)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

    def handle_card_action(self, action, user_id):
        # Find user data
        u_data = next((u for u in self.db_manager.get_all_users() if u[0] == user_id), None)
        if not u_data: return
        
        if action == "edit":
            self.open_dialog(u_data)
        elif action == "delete":
            self.delete_user(user_id)
        elif action == "history":
            self.show_history(u_data[1])
        elif action == "reset":
            self.reset_user_pass(user_id, u_data[1])

    def show_history(self, username):
        logs = self.db_manager.get_user_login_history(username)
        dlg = LoginHistoryDialog(self, username, logs)
        dlg.exec()
        
    def reset_user_pass(self, uid, username):
        new_pass, ok = QInputDialog.getText(self, "RESET KEY", f"Enter new access code for {username}:", QLineEdit.EchoMode.Password)
        if ok and new_pass:
            success, msg = self.db_manager.reset_password(uid, new_pass)
            if success:
                self.db_manager.log_activity("ADMIN", "RESET_PASS", f"Reset key for {username}")
                ProMessageBox.information(self, "Success", "Access Key Updated")
            else:
                ProMessageBox.warning(self, "Error", msg)

    def open_dialog(self, data=None):
        dlg = UserDialog(self, data)
        if dlg.exec():
            # Get 6 values now: u, p, r, pic, perms, pin
            res = dlg.get_data()
            u, p, r = res[0], res[1], res[2]
            pic_path = res[3]
            perm_json = res[4]
            pin = res[5]
            
            # Handle Image persistence
            final_pic_path = pic_path
            if pic_path:
                try:
                    # Use centralised path — resolves to %APPDATA% when frozen
                    storage_dir = get_app_data_path(os.path.join("data", "avatars"))
                    # If file is not already in storage, copy it
                    if os.path.dirname(os.path.abspath(pic_path)) != os.path.abspath(storage_dir):
                        ext = os.path.splitext(pic_path)[1]
                        new_name = f"{u}_avatar{ext}"
                        target = os.path.join(storage_dir, new_name)
                        shutil.copy2(pic_path, target)
                        final_pic_path = target
                except Exception as e:
                    print(f"Error saving image: {e}")
            
            if not u or not p:
                ProMessageBox.warning(self, "Error", "Username and Password required")
                return
                
            if data:
                # Update (pass permissions + pin + old_username)
                old_u = data[1] # Capture original username
                success, msg = self.db_manager.update_user(data[0], u, p, r, final_pic_path, perm_json, pin, old_username=old_u) 
                if success: self.db_manager.log_activity("ADMIN", "UPDATE_USER", f"Modified {old_u} -> {u}")
            else:
                # Add (pass permissions + pin)
                success, msg = self.db_manager.add_user(u, p, r, final_pic_path, perm_json, pin)
                if success: self.db_manager.log_activity("ADMIN", "ADD_USER", f"Added {u}")
                
            if success:
                self.load_data()
                self.feed.refresh_logs() # Trigger feed update
                ProMessageBox.information(self, "Success", "Protocol Updated")
            else:
                ProMessageBox.warning(self, "Error", "Operation Failed")

    def delete_user(self, uid):
        if ProMessageBox.question(self, "REVOKE CLEARANCE?", "This action is irreversible. Confirm revocation?"):
            self.db_manager.delete_user(uid)
            self.db_manager.log_activity("ADMIN", "DELETE_USER", f"Revoked ID {uid}")
            self.load_data()
            self.feed.refresh_logs()

    def reset_invoice_sequence(self):
        val, ok = QInputDialog.getInt(self, "Developer Reset", "Set Next Invoice Sequence Number:", 1001, 1, 999999, 1)
        if ok:
            if ProMessageBox.question(self, "⚠️ DANGER", f"Resetting sequence.\nNext Invoice will be INV-{val}.\nEnsure no ID clashes!\nProceed?"):
                success, msg = self.db_manager.set_invoice_sequence(val)
                if success:
                    ProMessageBox.information(self, "Reset", f"Next Invoice ID set to INV-{val}")
                    self.db_manager.log_activity("ADMIN", "RESET_SEQ", f"Set Inv Seq to {val}")
                else:
                    ProMessageBox.warning(self, "Error", f"Failed: {msg}")
