# settings_page.py — Enhanced Settings (v2.0)
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QScrollArea, QComboBox, QGroupBox, QCheckBox, QFileDialog,
                             QDialog, QListWidget, QListWidgetItem, QLineEdit, QTextEdit,
                             QFrame, QGridLayout, QButtonGroup, QRadioButton, QSizePolicy,
                             QFormLayout)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QFont, QIcon, QPixmap
from styles import (COLOR_ACCENT_CYAN, COLOR_ACCENT_GREEN, COLOR_TEXT_PRIMARY,
                    COLOR_ACCENT_RED, COLOR_ACCENT_YELLOW, COLOR_SURFACE)
from custom_components import ProMessageBox, ProTableDelegate
import ui_theme
import os, shutil


# ─── Theme definitions for visual cards ──────────────────────────────────────
INVOICE_THEMES = [
    {
        "name": "Modern (Blue)",
        "colors": ["#1A4FA0", "#2563EB", "#DBEAFE"],
        "desc": "Clean navy blue • Professional",
        "icon": "🔵",
    },
    {
        "name": "Executive (Black/Gold)",
        "colors": ["#1A1A1E", "#D4A827", "#FFFBEB"],
        "desc": "Luxury Black & Gold • Premium",
        "icon": "🏆",
    },
    {
        "name": "Minimal (B&W)",
        "colors": ["#222222", "#555555", "#F5F5F5"],
        "desc": "Clean monochrome • Simple",
        "icon": "⬜",
    },
    {
        "name": "Saffron (Indian)",
        "colors": ["#E06000", "#FF9933", "#FFF3E0"],
        "desc": "Saffron & orange • Desi",
        "icon": "🇮🇳",
    },
    {
        "name": "Green (Eco)",
        "colors": ["#166534", "#22C55E", "#DCFCE7"],
        "desc": "Forest green • Fresh",
        "icon": "🌿",
    },
    {
        "name": "Logo Adaptive",
        "colors": ["#7C3AED", "#A78BFA", "#EDE9FE"],
        "desc": "Auto-extract from logo",
        "icon": "🎨",
    },
]


class ThemeCard(QFrame):
    """A clickable theme preview card"""
    def __init__(self, theme_data, is_selected=False, on_select=None, parent=None):
        super().__init__(parent)
        self.theme_name = theme_data["name"]
        self.on_select = on_select
        self.setFixedSize(155, 100)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_style(is_selected)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(3)

        # Color swatches row
        swatch_row = QHBoxLayout()
        swatch_row.setSpacing(3)
        for clr in theme_data["colors"]:
            sw = QFrame()
            sw.setFixedSize(28, 18)
            sw.setStyleSheet(f"background-color: {clr}; border-radius: 3px; border: 1px solid rgba(255,255,255,0.2);")
            swatch_row.addWidget(sw)
        swatch_row.addStretch()
        layout.addLayout(swatch_row)

        # Icon + name
        name_row = QHBoxLayout()
        icon_lbl = QLabel(theme_data["icon"])
        icon_lbl.setStyleSheet("font-size: 14px; border: none; background: transparent;")
        name_lbl = QLabel(theme_data["name"])
        name_lbl.setStyleSheet("color: white; font-weight: bold; font-size: 10px; border: none; background: transparent;")
        name_lbl.setWordWrap(True)
        name_row.addWidget(icon_lbl)
        name_row.addWidget(name_lbl)
        name_row.addStretch()
        layout.addLayout(name_row)

        # Description
        desc_lbl = QLabel(theme_data["desc"])
        desc_lbl.setStyleSheet("color: #888; font-size: 8px; border: none; background: transparent;")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)

    def _update_style(self, selected):
        if selected:
            self.setStyleSheet(f"""
                ThemeCard {{
                    background: rgba(0, 242, 255, 0.12);
                    border: 2px solid {COLOR_ACCENT_CYAN};
                    border-radius: 8px;
                }}
                ThemeCard:hover {{
                    background: rgba(0, 242, 255, 0.18);
                }}
            """)
        else:
            self.setStyleSheet("""
                ThemeCard {
                    background: rgba(255,255,255,0.05);
                    border: 1px solid rgba(255,255,255,0.1);
                    border-radius: 8px;
                }
                ThemeCard:hover {
                    background: rgba(255,255,255,0.09);
                    border: 1px solid rgba(0, 242, 255, 0.4);
                }
            """)

    def set_selected(self, selected):
        self._update_style(selected)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.on_select:
            self.on_select(self.theme_name)
        super().mousePressEvent(event)


class SettingsPage(QWidget):
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self._theme_cards = {}
        self.setup_ui()
        self.load_settings()

    def load_data(self):
        """Called by Main Window refresh"""
        self.load_settings()

    # ─── UI Setup ────────────────────────────────────────────────────────────
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 30, 30, 30)
        main_layout.setSpacing(20)

        # Header
        header_container = QVBoxLayout()
        header = QLabel("⚙️ SYSTEM SETTINGS")
        header.setStyleSheet(f"color: {COLOR_ACCENT_CYAN}; font-size: 26px; font-weight: bold; letter-spacing: 3px;")
        header_container.addWidget(header)
        subtitle = QLabel("Configure shop identity, invoice format, GST settings, and more")
        subtitle.setStyleSheet("color: #888; font-size: 12px; margin-top: 5px;")
        header_container.addWidget(subtitle)
        main_layout.addLayout(header_container)

        # Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setSpacing(20)

        # ── Sections ──
        self.create_shop_identity_card()
        self.create_invoice_theme_card()
        self.create_gst_settings_card()
        self.create_footer_card()
        self.create_data_management_card()  # Restored from v1
        self.create_backup_card()
        self.create_network_card()

        self.content_layout.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

        # Save Button
        self.btn_save = QPushButton("💾  SAVE ALL SETTINGS")
        self.btn_save.setFixedHeight(55)
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLOR_ACCENT_GREEN}, stop:1 #00cc35);
                color: black; font-weight: bold; border-radius: 8px;
                font-size: 16px; letter-spacing: 1px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00ff41, stop:1 {COLOR_ACCENT_GREEN});
            }}
        """)
        self.btn_save.clicked.connect(self.save_all_settings)
        main_layout.addWidget(self.btn_save)

    # ── Card creator helper ───────────────────────────────────────────────────
    def create_card_frame(self, title, icon=""):
        group = QGroupBox(f"{icon}  {title}")
        group.setStyleSheet(f"""
            QGroupBox {{
                color: {COLOR_TEXT_PRIMARY}; font-weight: bold; font-size: 14px;
                border: 2px solid #1a1a2e;
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 rgba(10,15,25,0.85), stop:1 rgba(5,8,15,0.92));
                margin-top: 15px; padding: 20px; border-radius: 12px;
            }}
            QGroupBox:hover {{ border-color: rgba(0,242,255,0.25); }}
            QGroupBox::title {{
                subcontrol-origin: margin; subcontrol-position: top left;
                padding: 5px 15px;
                background-color: rgba(0,242,255,0.1);
                border-radius: 6px; margin-left: 10px;
            }}
        """)
        layout = QVBoxLayout(group)
        layout.setSpacing(15)
        return group, layout

    # ── 1. Shop Identity ─────────────────────────────────────────────────────
    def create_shop_identity_card(self):
        group, layout = self.create_card_frame("SHOP IDENTITY", "🏪")

        desc = QLabel("Configure your shop's public information — appears on every invoice PDF")
        desc.setStyleSheet("color: #999; font-weight: normal;")
        layout.addWidget(desc)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setVerticalSpacing(12)

        def make_field(placeholder=""):
            f = QLineEdit()
            f.setPlaceholderText(placeholder)
            f.setStyleSheet(ui_theme.get_lineedit_style())
            return f

        self.in_shop_name    = make_field("e.g. N.A. MOTORS")
        self.in_shop_mobile  = make_field("e.g. 9800012345, 9900054321")
        self.in_shop_gstin   = make_field("e.g. 09ABCDE1234F1Z5")
        self.in_shop_address = QTextEdit()
        self.in_shop_address.setPlaceholderText("Full shop address (multi-line)...")
        self.in_shop_address.setFixedHeight(80)
        self.in_shop_address.setStyleSheet(ui_theme.get_lineedit_style())

        form.addRow(QLabel("Shop Name:"), self.in_shop_name)
        form.addRow(QLabel("Mobile Nos:"), self.in_shop_mobile)
        form.addRow(QLabel("GSTIN:"), self.in_shop_gstin)
        form.addRow(QLabel("Address:"), self.in_shop_address)

        layout.addLayout(form)

        # Logo row
        logo_row = QHBoxLayout()
        self.lbl_logo_status = QLabel("No logo uploaded")
        self.lbl_logo_status.setStyleSheet("color: #888; font-size: 11px;")
        btn_logo = QPushButton("🖼️  BROWSE LOGO")
        btn_logo.setFixedHeight(38)
        btn_logo.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_logo.setStyleSheet(ui_theme.get_primary_button_style())
        btn_logo.clicked.connect(self.browse_logo)
        logo_row.addWidget(QLabel("Shop Logo:"))
        logo_row.addWidget(self.lbl_logo_status, 1)
        logo_row.addWidget(btn_logo)
        layout.addLayout(logo_row)

        self.content_layout.addWidget(group)

    # ── 2. Invoice Themes ────────────────────────────────────────────────────
    def create_invoice_theme_card(self):
        group, layout = self.create_card_frame("INVOICE THEME & FORMAT", "🧾")

        desc = QLabel("Select the look of your printed invoices. Changes apply to all new PDFs.")
        desc.setStyleSheet("color: #999; font-weight: normal;")
        layout.addWidget(desc)

        # Theme cards grid
        grid = QGridLayout()
        grid.setSpacing(12)
        self._current_theme = "Modern (Blue)"

        for idx, theme in enumerate(INVOICE_THEMES):
            card = ThemeCard(theme, is_selected=(theme["name"] == self._current_theme),
                             on_select=self.on_theme_selected)
            self._theme_cards[theme["name"]] = card
            grid.addWidget(card, idx // 3, idx % 3)

        layout.addLayout(grid)

        # Paper Size
        paper_row = QHBoxLayout()
        paper_lbl = QLabel("Paper Size:")
        paper_lbl.setStyleSheet("color: #aaa; font-weight: bold;")

        self.combo_paper = QComboBox()
        self.combo_paper.addItems(["A4 (Standard)", "A5 (Half Sheet)", "Thermal 80mm (POS)"])
        self.combo_paper.setFixedHeight(38)
        self.combo_paper.setStyleSheet(ui_theme.get_lineedit_style())

        paper_row.addWidget(paper_lbl)
        paper_row.addWidget(self.combo_paper)
        paper_row.addStretch()
        layout.addLayout(paper_row)

        self.content_layout.addWidget(group)

    def on_theme_selected(self, theme_name):
        """Called when user clicks a theme card"""
        self._current_theme = theme_name
        for name, card in self._theme_cards.items():
            card.set_selected(name == theme_name)

    # ── 3. GST / Tax Settings ────────────────────────────────────────────────
    def create_gst_settings_card(self):
        group, layout = self.create_card_frame("GST / TAX SETTINGS", "💰")

        desc = QLabel("Configure GST rates and how tax details appear on invoices.")
        desc.setStyleSheet("color: #999; font-weight: normal;")
        layout.addWidget(desc)

        row1 = QHBoxLayout()
        row1.setSpacing(20)

        # Default GST Rate
        gst_col = QVBoxLayout()
        gst_lbl = QLabel("Default GST Rate:")
        gst_lbl.setStyleSheet("color: #aaa; font-weight: bold;")
        self.combo_gst_rate = QComboBox()
        self.combo_gst_rate.addItems(["0%", "5%", "12%", "18%", "28%"])
        self.combo_gst_rate.setFixedHeight(38)
        self.combo_gst_rate.setCurrentText("18%")
        self.combo_gst_rate.setStyleSheet(ui_theme.get_lineedit_style())
        gst_col.addWidget(gst_lbl)
        gst_col.addWidget(self.combo_gst_rate)
        row1.addLayout(gst_col)

        # GST Mode
        mode_col = QVBoxLayout()
        mode_lbl = QLabel("GST Mode:")
        mode_lbl.setStyleSheet("color: #aaa; font-weight: bold;")
        self.combo_gst_mode = QComboBox()
        self.combo_gst_mode.addItems(["CGST + SGST (Intra-State)", "IGST (Inter-State)"])
        self.combo_gst_mode.setFixedHeight(38)
        self.combo_gst_mode.setStyleSheet(ui_theme.get_lineedit_style())
        mode_col.addWidget(mode_lbl)
        mode_col.addWidget(self.combo_gst_mode)
        row1.addLayout(mode_col)

        row1.addStretch()
        layout.addLayout(row1)

        # Checkboxes
        self.chk_show_gst = QCheckBox("📊  Show GST Breakdown on Invoice (CGST / SGST lines in summary)")
        self.chk_show_gst.setChecked(True)
        self.chk_show_gst.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: 12px;")

        self.chk_show_hsn = QCheckBox("🔢  Show HSN Code on Invoice Line Items")
        self.chk_show_hsn.setChecked(False)
        self.chk_show_hsn.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: 12px;")

        layout.addWidget(self.chk_show_gst)
        layout.addWidget(self.chk_show_hsn)

        info = QLabel("ℹ️  HSN codes are stored per part in Inventory. Enable to print them on invoices.")
        info.setStyleSheet("color: #555; font-size: 10px; font-style: italic;")
        layout.addWidget(info)

        self.content_layout.addWidget(group)

    # ── 4. Invoice Footer ─────────────────────────────────────────────────────
    def create_footer_card(self):
        group, layout = self.create_card_frame("INVOICE FOOTER TEXT", "📝")

        desc = QLabel("Custom message printed at the bottom of every invoice PDF.")
        desc.setStyleSheet("color: #999; font-weight: normal;")
        layout.addWidget(desc)

        self.in_footer_text = QLineEdit()
        self.in_footer_text.setPlaceholderText("e.g. Thank you for your business! | E. & O.E.")
        self.in_footer_text.setStyleSheet(ui_theme.get_lineedit_style())
        self.in_footer_text.setFixedHeight(42)
        layout.addWidget(self.in_footer_text)

        self.content_layout.addWidget(group)

    # ── 5. Data Management (Export) ──────────────────────────────────────────
    def create_data_management_card(self):
        group, layout = self.create_card_frame("DATA MANAGEMENT", "📊")

        desc = QLabel("Export all your data (Inventory, Sales, Expenses) to Excel format.")
        desc.setStyleSheet("color: #999; font-weight: normal; margin-bottom: 10px;")
        layout.addWidget(desc)

        btn_export = QPushButton("📥  EXPORT DATABASE TO EXCEL")
        btn_export.setFixedHeight(45)
        btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_export.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.05); color: {COLOR_TEXT_PRIMARY};
                border: 1px solid #555; border-radius: 8px; font-weight: bold;
            }}
            QPushButton:hover {{ background: rgba(0,242,255,0.15); border-color: {COLOR_ACCENT_CYAN}; color: {COLOR_ACCENT_CYAN}; }}
        """)
        btn_export.clicked.connect(self.export_data)
        layout.addWidget(btn_export)
        self.content_layout.addWidget(group)

    def export_data(self):
        try:
            import pandas as pd
            import sqlite3
            from datetime import datetime
            
            filepath, _ = QFileDialog.getSaveFileName(self, "Export to Excel", 
                                                      f"SpareERP_Export_{datetime.now().strftime('%Y%m%d')}.xlsx",
                                                      "Excel Files (*.xlsx)")
            if not filepath: return
            
            conn = sqlite3.connect(self.db_manager.db_name)
            # Fetch relevant tables
            writer = pd.ExcelWriter(filepath, engine='openpyxl')
            for table in ["parts", "invoices", "sales", "expenses", "vendors"]:
                try:
                    df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
                    df.to_excel(writer, sheet_name=table.title(), index=False)
                except Exception:
                    pass
            
            writer.close()
            conn.close()
            ProMessageBox.information(self, "Export Complete", f"Data exported successfully to:\n{filepath}")
            
        except ImportError:
            ProMessageBox.warning(self, "Export Error", "Pandas or OpenPyXL library missing. Please install to use Excel export.")
        except Exception as e:
            ProMessageBox.critical(self, "Export Failed", f"An error occurred:\n{str(e)}")


    # ── 6. Backup & Restore ───────────────────────────────────────────────────
    def create_backup_card(self):
        from backup_manager import BackupManager
        self.backup_mgr = BackupManager(self.db_manager.db_name)

        group, layout = self.create_card_frame("BACKUP & RESTORE", "💾")

        desc = QLabel("Protect your data with automatic backups")
        desc.setStyleSheet("color: #999; font-weight: normal; margin-bottom: 10px;")
        layout.addWidget(desc)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(15)

        btn_backup = QPushButton("📦  CREATE BACKUP")
        btn_backup.setFixedHeight(50)
        btn_backup.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_backup.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0,242,255,0.1); color: {COLOR_ACCENT_CYAN};
                border: 2px solid {COLOR_ACCENT_CYAN}; border-radius: 8px;
                font-weight: bold; font-size: 14px;
            }}
            QPushButton:hover {{ background: {COLOR_ACCENT_CYAN}; color: black; }}
        """)
        btn_backup.clicked.connect(self.manual_backup)
        btn_row.addWidget(btn_backup)

        btn_restore = QPushButton("♻️  RESTORE DATA")
        btn_restore.setFixedHeight(50)
        btn_restore.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_restore.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,152,0,0.1); color: #ff9800;
                border: 2px solid #ff9800; border-radius: 8px;
                font-weight: bold; font-size: 14px;
            }}
            QPushButton:hover {{ background: #ff9800; color: black; }}
        """)
        btn_restore.clicked.connect(self.show_restore_dialog)
        btn_row.addWidget(btn_restore)
        layout.addLayout(btn_row)

        self.lbl_backup_status = QLabel("✓ Local backup enabled")
        self.lbl_backup_status.setStyleSheet("color: #00ff41; font-size: 11px; font-style: italic; margin-top: 10px;")
        layout.addWidget(self.lbl_backup_status)

        # Cloud Backup
        sep = QLabel("─── Cloud Backup ───")
        sep.setStyleSheet("color: #444; margin-top: 15px;")
        sep.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sep)

        self.chk_cloud_backup = QCheckBox("☁️  Enable automatic cloud sync")
        self.chk_cloud_backup.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-weight: bold; font-size: 13px;")
        self.chk_cloud_backup.stateChanged.connect(self.on_cloud_backup_toggled)
        layout.addWidget(self.chk_cloud_backup)

        cloud_row = QHBoxLayout()
        cloud_row.setSpacing(10)
        self.lbl_cloud_path = QLabel("Not configured")
        self.lbl_cloud_path.setStyleSheet("color: #888; padding: 10px; background-color: #0a0a0a; border-radius: 6px; font-size: 11px;")
        cloud_row.addWidget(self.lbl_cloud_path, 1)
        btn_browse = QPushButton("📁  Browse")
        btn_browse.setFixedSize(100, 38)
        btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_browse.setStyleSheet(f"background-color: #1a1a1a; color: {COLOR_ACCENT_CYAN}; border: 1px solid #333; border-radius: 6px; font-weight: bold;")
        btn_browse.clicked.connect(self.select_cloud_folder)
        cloud_row.addWidget(btn_browse)
        layout.addLayout(cloud_row)

        self.lbl_cloud_status = QLabel("")
        self.lbl_cloud_status.setStyleSheet("color: #666; font-size: 10px; font-style: italic;")
        layout.addWidget(self.lbl_cloud_status)

        self.content_layout.addWidget(group)
        self.load_cloud_settings()

    # ── 6. Network Setup ──────────────────────────────────────────────────────
    def create_network_card(self):
        group, layout = self.create_card_frame("NETWORK DATABASE", "🌐")

        import db_config
        config = db_config.load_config()
        if config:
            mode = config.get("mode", "LOCAL")
            if mode == "SERVER":
                ip = db_config.get_local_ip()
                pc = db_config.get_computer_name()
                mode_text = f"🖥️ SERVER MODE  •  IP: {ip}  •  PC: {pc}"
                mode_color = COLOR_ACCENT_CYAN
            elif mode == "CLIENT":
                server = config.get("server_ip", "?")
                mode_text = f"💻 CLIENT MODE  •  Server: {server}"
                mode_color = COLOR_ACCENT_GREEN
            else:
                mode_text = "📁 LOCAL MODE (Single PC)"
                mode_color = "#888"
        else:
            mode_text = "⚠️ Not configured"
            mode_color = "#ff9800"

        self.lbl_network_mode = QLabel(mode_text)
        self.lbl_network_mode.setStyleSheet(
            f"color: {mode_color}; font-weight: bold; font-size: 13px; padding: 12px;"
            f" background-color: #0a0a0a; border-radius: 8px; border: 1px solid #222;")
        self.lbl_network_mode.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_network_mode)

        btn_network = QPushButton("🔄  RECONFIGURE NETWORK")
        btn_network.setFixedHeight(45)
        btn_network.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_network.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0,242,255,0.1); color: {COLOR_ACCENT_CYAN};
                border: 2px solid {COLOR_ACCENT_CYAN}; border-radius: 8px;
                font-weight: bold; font-size: 13px;
            }}
            QPushButton:hover {{ background: {COLOR_ACCENT_CYAN}; color: black; }}
        """)
        btn_network.clicked.connect(self.open_network_setup)
        layout.addWidget(btn_network)

        self.content_layout.addWidget(group)

    # ─── Load / Save ─────────────────────────────────────────────────────────
    def load_settings(self):
        s = self.db_manager.get_shop_settings()
        if not s:
            return

        # Shop Identity
        self.in_shop_name.setText(s.get("shop_name", ""))
        self.in_shop_mobile.setText(s.get("mobile", "") or s.get("shop_mobile", ""))
        self.in_shop_gstin.setText(s.get("gstin", "") or s.get("shop_gstin", ""))
        self.in_shop_address.setPlainText(s.get("address", "") or s.get("shop_address", ""))

        logo = s.get("logo_path", "")
        if logo and os.path.exists(logo):
            self.lbl_logo_status.setText(f"✅  {os.path.basename(logo)}")
            self.lbl_logo_status.setStyleSheet("color: #00ff41; font-size: 11px;")
        self._logo_path = logo

        # Invoice Theme
        theme = s.get("invoice_theme", "Modern (Blue)")
        self._current_theme = theme
        for name, card in self._theme_cards.items():
            card.set_selected(name == theme)

        # Paper size
        fmt = s.get("invoice_format", "A4")
        fmt_map = {"A4": "A4 (Standard)", "A5": "A5 (Half Sheet)", "Thermal_80mm": "Thermal 80mm (POS)"}
        self.combo_paper.setCurrentText(fmt_map.get(fmt, "A4 (Standard)"))

        # GST Settings
        gst_rate = s.get("default_gst_rate", "18")
        self.combo_gst_rate.setCurrentText(f"{gst_rate}%")

        gst_mode = s.get("gst_mode", "CGST+SGST")
        if "IGST" in gst_mode:
            self.combo_gst_mode.setCurrentText("IGST (Inter-State)")
        else:
            self.combo_gst_mode.setCurrentText("CGST + SGST (Intra-State)")

        self.chk_show_gst.setChecked(s.get("show_gst_breakdown", "true") == "true")
        self.chk_show_hsn.setChecked(s.get("show_hsn_on_invoice", "false") == "true")

        # Footer
        self.in_footer_text.setText(s.get("invoice_footer_text", "Thank you for your business!"))

    def save_all_settings(self):
        """Save all settings cards at once"""
        def upd(key, val):
            self.db_manager.update_setting(key, val)

        # Shop Identity
        upd("shop_name",    self.in_shop_name.text().strip())
        upd("shop_mobile",  self.in_shop_mobile.text().strip())
        upd("shop_gstin",   self.in_shop_gstin.text().strip())
        upd("shop_address", self.in_shop_address.toPlainText().strip())
        if hasattr(self, '_logo_path') and self._logo_path:
            upd("logo_path", self._logo_path)

        # Invoice Theme
        upd("invoice_theme", self._current_theme)
        paper_text = self.combo_paper.currentText()
        fmt_map = {"A4 (Standard)": "A4", "A5 (Half Sheet)": "A5", "Thermal 80mm (POS)": "Thermal_80mm"}
        upd("invoice_format", fmt_map.get(paper_text, "A4"))

        # GST Settings
        gst_rate_text = self.combo_gst_rate.currentText().replace("%", "")
        upd("default_gst_rate", gst_rate_text)
        gst_mode_text = self.combo_gst_mode.currentText()
        upd("gst_mode", "IGST" if "IGST" in gst_mode_text else "CGST+SGST")
        upd("show_gst_breakdown", "true" if self.chk_show_gst.isChecked() else "false")
        upd("show_hsn_on_invoice", "true" if self.chk_show_hsn.isChecked() else "false")

        # Footer
        upd("invoice_footer_text", self.in_footer_text.text().strip() or "Thank you for your business!")

        ProMessageBox.information(self, "✅ Saved", "All settings saved successfully!\nNew invoices will use the updated configuration.")

    # ─── Logo ────────────────────────────────────────────────────────────────
    def browse_logo(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Select Logo", "", "Images (*.png *.jpg *.jpeg)")
        if fname:
            try:
                os.makedirs("logos", exist_ok=True)
                dest = os.path.join("logos", "logo.png")
                if os.path.abspath(fname) != os.path.abspath(dest):
                    shutil.copy(fname, dest)
                self._logo_path = dest
                self.lbl_logo_status.setText(f"✅  {os.path.basename(fname)}")
                self.lbl_logo_status.setStyleSheet("color: #00ff41; font-size: 11px;")
            except Exception as e:
                ProMessageBox.warning(self, "Logo Error", f"Could not copy logo: {e}")

    # ─── Backup helpers ───────────────────────────────────────────────────────
    def manual_backup(self):
        settings = self.db_manager.get_shop_settings()
        cloud_enabled = settings.get("backup_cloud_enabled", "false") == "true"
        cloud_path = settings.get("backup_cloud_path", "") if cloud_enabled else None
        success, msg = self.backup_mgr.create_backup(cloud_path=cloud_path)
        if success:
            ProMessageBox.information(self, "Backup Created", msg)
            self.lbl_backup_status.setText(f"✓ {msg}")
        else:
            ProMessageBox.critical(self, "Backup Failed", msg)

    def on_cloud_backup_toggled(self, state):
        enabled = state == Qt.CheckState.Checked.value
        self.db_manager.update_setting("backup_cloud_enabled", "true" if enabled else "false")
        self.lbl_backup_status.setText("✓ Local + Cloud backup enabled" if enabled else "✓ Local backup enabled")

    def select_cloud_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Cloud Drive Folder", "", QFileDialog.Option.ShowDirsOnly)
        if folder:
            success, result = self.backup_mgr.set_cloud_backup_path(folder)
            if success:
                self.db_manager.update_setting("backup_cloud_path", result)
                self.lbl_cloud_path.setText(result)
                self.lbl_cloud_path.setStyleSheet("color: #00ff41; padding: 10px; background-color: #0a0a0a; border-radius: 6px; font-size: 11px;")
                self.lbl_cloud_status.setText("✓ Cloud folder configured successfully")
                self.lbl_cloud_status.setStyleSheet("color: #00ff41; font-size: 10px; font-style: italic;")
                ProMessageBox.information(self, "Success", f"Cloud backup folder:\n{result}")
            else:
                ProMessageBox.critical(self, "Error", f"Invalid folder:\n{result}")

    def load_cloud_settings(self):
        settings = self.db_manager.get_shop_settings()
        cloud_enabled = settings.get("backup_cloud_enabled", "false") == "true"
        self.chk_cloud_backup.setChecked(cloud_enabled)
        cloud_path = settings.get("backup_cloud_path", "")
        if cloud_path:
            self.lbl_cloud_path.setText(cloud_path)
            self.lbl_cloud_path.setStyleSheet("color: #00ff41; padding: 10px; background-color: #0a0a0a; border-radius: 6px; font-size: 11px;")
            try:
                is_valid, status_msg, _ = self.backup_mgr.get_cloud_backup_status(cloud_path)
                style = "color: #00ff41;" if is_valid else "color: #ff9800;"
                prefix = "✓" if is_valid else "⚠"
                self.lbl_cloud_status.setText(f"{prefix} {status_msg}")
                self.lbl_cloud_status.setStyleSheet(f"{style} font-size: 10px; font-style: italic;")
            except Exception:
                pass

    def show_restore_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("♻️ Restore Backup")
        dialog.setModal(True)
        dialog.setMinimumSize(600, 400)
        dialog.setStyleSheet("background-color: #080a10;")
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        title = QLabel("Select a backup to restore:")
        title.setStyleSheet(f"color: {COLOR_ACCENT_CYAN}; font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        backup_list = QListWidget()
        backup_list.setStyleSheet(f"""
            QListWidget {{ background-color: #0a0a0a; border: 1px solid #333; border-radius: 6px; color: {COLOR_TEXT_PRIMARY}; padding: 5px; }}
            QListWidget::item {{ padding: 10px; border-radius: 4px; }}
            QListWidget::item:hover {{ background-color: rgba(0,242,255,0.1); }}
            QListWidget::item:selected {{ background-color: rgba(0,242,255,0.2); border: 1px solid {COLOR_ACCENT_CYAN}; }}
        """)

        backups = self.backup_mgr.get_backups()
        if not backups:
            no_backup_item = QListWidgetItem("No backups available")
            no_backup_item.setFlags(Qt.ItemFlag.NoItemFlags)
            backup_list.addItem(no_backup_item)
        else:
            for backup in backups:
                size_mb = backup["size"] / (1024 * 1024)
                item = QListWidgetItem(f"📦 {backup['filename']}\n    📅 {backup['date']}  |  💾 {size_mb:.2f} MB")
                item.setData(Qt.ItemDataRole.UserRole, backup["filename"])
                backup_list.addItem(item)
        layout.addWidget(backup_list)

        warning = QLabel("⚠️ WARNING: This will replace your current database. A safety backup will be created first.")
        warning.setStyleSheet("color: #ff9800; font-size: 11px; font-style: italic; padding: 10px; background-color: rgba(255,152,0,0.1); border-radius: 4px;")
        warning.setWordWrap(True)
        layout.addWidget(warning)

        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("✖️  Cancel")
        btn_cancel.setFixedHeight(40)
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setStyleSheet("background-color: #333; color: white; border-radius: 6px; font-weight: bold;")
        btn_cancel.clicked.connect(dialog.reject)
        btn_row.addWidget(btn_cancel)

        btn_restore = QPushButton("♻️  RESTORE SELECTED")
        btn_restore.setFixedHeight(40)
        btn_restore.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_restore.setStyleSheet("background-color: #ff9800; color: black; border-radius: 6px; font-weight: bold;")
        btn_restore.clicked.connect(lambda: self._perform_restore(backup_list, dialog))
        btn_row.addWidget(btn_restore)
        layout.addLayout(btn_row)
        dialog.exec()

    def _perform_restore(self, backup_list, dialog):
        selected = backup_list.selectedItems()
        if not selected:
            ProMessageBox.warning(self, "No Selection", "Please select a backup to restore.")
            return
        fname = selected[0].data(Qt.ItemDataRole.UserRole)
        if ProMessageBox.question(self, "Confirm Restore", f"Restore from:\n{fname}\n\nThis will replace all current data!"):
            success, msg = self.backup_mgr.restore_backup(fname)
            if success:
                ProMessageBox.information(self, "Restore Complete", f"{msg}\n\nPlease restart the application.")
                dialog.accept()
            else:
                ProMessageBox.critical(self, "Restore Failed", msg)

    # ─── Network ─────────────────────────────────────────────────────────────
    def open_network_setup(self):
        from network_setup import NetworkSetupDialog
        dlg = NetworkSetupDialog(self)
        if dlg.exec():
            ProMessageBox.information(self, "Network Updated", "Network configuration saved!\n\nPlease restart the application for changes to take effect.")
