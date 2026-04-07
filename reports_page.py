from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QPushButton, QFrame, QDateEdit, QDialog, QFormLayout, 
                              QLineEdit, QDialogButtonBox, QAbstractItemView, QTextEdit, QFileDialog, QProgressBar, QGridLayout, QStackedWidget,
                              QMenu, QCheckBox, QTabWidget, QInputDialog, QTabBar)
from PyQt6.QtGui import QAction, QCursor
from PyQt6.QtCharts import QChart, QChartView, QLineSeries, QBarSeries, QBarSet, QValueAxis, QBarCategoryAxis
from custom_components import ProMessageBox, ProTableDelegate, ProDialog, ReactorStatCard
from return_dialog import ReturnDialog
from PyQt6.QtCore import Qt, QDate, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty, QMargins
from PyQt6.QtGui import QPixmap, QPainter, QColor, QPen, QLinearGradient, QFont
from report_generator import ReportGenerator
from whatsapp_helper import send_report_msg
from styles import (COLOR_ACCENT_CYAN, COLOR_BACKGROUND, COLOR_SURFACE, COLOR_TEXT_PRIMARY, COLOR_ACCENT_GREEN,
                   COLOR_ACCENT_YELLOW, COLOR_ACCENT_RED, STYLE_GLASS_PANEL)
import ui_theme
import os
import sys
import shutil
import json
import hashlib
from datetime import datetime, timedelta
from logger import app_logger
from PyQt6.QtWidgets import QInputDialog

class AnimatedStatCard(QFrame):
    """Animated statistics card with glow effect and counting animation"""
    def __init__(self, title, value="0", icon="📊", color=COLOR_ACCENT_CYAN, parent=None):
        super().__init__(parent)
        self.setFixedHeight(120)
        self._current_value = 0
        self._target_value = 0
        self._color = color
        self._is_currency = False
        
        self.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(11, 11, 20, 0.9),
                    stop:1 rgba(20, 20, 35, 0.9));
                border: 2px solid {color};
                border-radius: 12px;
            }}
            QFrame:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(15, 15, 25, 0.95),
                    stop:1 rgba(25, 25, 40, 0.95));
                border: 2px solid {color};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        
        # Icon + Title
        top_row = QHBoxLayout()
        self.lbl_icon = QLabel(icon)
        self.lbl_icon.setStyleSheet(f"font-size: 32px; border: none; background: transparent;")
        
        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet(f"color: #aaa; font-size: 11px; font-weight: bold; border: none; background: transparent;")
        
        top_row.addWidget(self.lbl_icon)
        top_row.addStretch()
        top_row.addWidget(self.lbl_title)
        layout.addLayout(top_row)
        
        # Value
        self.lbl_value = QLabel(value)
        self.lbl_value.setStyleSheet(f"color: {color}; font-size: 28px; font-weight: bold; border: none; background: transparent;")
        layout.addWidget(self.lbl_value)
        
        layout.addStretch()
        
        # Animation timer
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self._animate_step)
        
    def set_value(self, value, animate=True):
        """Set value with optional animation"""
        # Detect if currency
        if isinstance(value, str) and '₹' in value:
            self._is_currency = True
            # Extract numeric value
            numeric_str = value.replace('₹', '').replace(',', '').strip()
            try:
                self._target_value = float(numeric_str)
            except:
                self.lbl_value.setText(value)
                return
        elif isinstance(value, str) and '%' in value:
            self.lbl_value.setText(value)
            return
        else:
            self._is_currency = False
            try:
                self._target_value = float(str(value).replace(',', ''))
            except:
                self.lbl_value.setText(str(value))
                return
        
        if animate and self._target_value > 0:
            self._current_value = 0
            self.animation_timer.start(20)  # Update every 20ms
        else:
            self._current_value = self._target_value
            self._update_display()
    
    def _animate_step(self):
        """Animate counting up"""
        if self._current_value < self._target_value:
            # Increment by 5% of remaining value or minimum 1
            increment = max(1, (self._target_value - self._current_value) * 0.15)
            self._current_value = min(self._current_value + increment, self._target_value)
            self._update_display()
        else:
            self.animation_timer.stop()
    
    def _update_display(self):
        """Update the displayed value"""
        if self._is_currency:
            self.lbl_value.setText(f"₹ {self._current_value:,.0f}")
        else:
            self.lbl_value.setText(f"{int(self._current_value)}")


class TopPerformerWidget(QFrame):
    """Widget showing top selling parts"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(11, 11, 20, 0.8);
                border: 1px solid #333;
                border-radius: 10px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Header
        header = QLabel("🎯 TOP PERFORMERS")
        header.setStyleSheet(f"color: {COLOR_ACCENT_YELLOW}; font-size: 16px; font-weight: bold; border: none; background: transparent;")
        layout.addWidget(header)
        
        # List container
        self.list_layout = QVBoxLayout()
        layout.addLayout(self.list_layout)
        layout.addStretch()
        
    def set_data(self, top_parts):
        """Display top selling parts with animated bars"""
        # Clear existing
        while self.list_layout.count():
            child = self.list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        if not top_parts:
            no_data = QLabel("No sales data available")
            no_data.setStyleSheet("color: #666; font-style: italic; border: none; background: transparent;")
            self.list_layout.addWidget(no_data)
            return
        
        max_qty = max([p[2] for p in top_parts]) if top_parts else 1
        
        for idx, (part_id, part_name, qty, revenue) in enumerate(top_parts):
            # Item frame
            item_frame = QFrame()
            item_frame.setStyleSheet("background: transparent; border: none;")
            item_layout = QVBoxLayout(item_frame)
            item_layout.setContentsMargins(0, 5, 0, 5)
            item_layout.setSpacing(3)
            
            # Rank + Name
            rank_colors = ["#FFD700", "#C0C0C0", "#CD7F32", "#00e5ff", "#00e5ff"]
            medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
            
            name_row = QHBoxLayout()
            rank_lbl = QLabel(medals[idx])
            rank_lbl.setStyleSheet(f"font-size: 18px; border: none; background: transparent;")
            
            name_lbl = QLabel(part_name[:30])
            name_lbl.setStyleSheet(f"color: {rank_colors[idx]}; font-weight: bold; font-size: 12px; border: none; background: transparent;")
            
            qty_lbl = QLabel(f"{float(qty)} units")
            qty_lbl.setStyleSheet(f"color: #aaa; font-size: 10px; border: none; background: transparent;")
            
            name_row.addWidget(rank_lbl)
            name_row.addWidget(name_lbl)
            name_row.addStretch()
            name_row.addWidget(qty_lbl)
            item_layout.addLayout(name_row)
            
            # Progress bar
            progress = QProgressBar()
            progress.setRange(0, 100)
            progress.setValue(int((qty / max_qty) * 100))
            progress.setTextVisible(False)
            progress.setFixedHeight(8)
            progress.setStyleSheet(f"""
                QProgressBar {{
                    background-color: #1a1a2e;
                    border: none;
                    border-radius: 4px;
                }}
                QProgressBar::chunk {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 {rank_colors[idx]},
                        stop:1 rgba(0, 229, 255, 0.3));
                    border-radius: 4px;
                }}
            """)
            item_layout.addWidget(progress)
            
            self.list_layout.addWidget(item_frame)

class CustomerInsightsWidget(QFrame):
    """Widget showing top customers"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(11, 11, 20, 0.8);
                border: 1px solid #333;
                border-radius: 10px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Header
        header = QLabel("💎 TOP CUSTOMERS")
        header.setStyleSheet(f"color: {COLOR_ACCENT_GREEN}; font-size: 16px; font-weight: bold; border: none; background: transparent;")
        layout.addWidget(header)
        
        # List container
        self.list_layout = QVBoxLayout()
        layout.addLayout(self.list_layout)
        layout.addStretch()
        
    def set_data(self, top_customers):
        """Display top customers"""
        # Clear existing
        while self.list_layout.count():
            child = self.list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        if not top_customers:
            no_data = QLabel("No customer data available")
            no_data.setStyleSheet("color: #666; font-style: italic; border: none; background: transparent;")
            self.list_layout.addWidget(no_data)
            return
        
        for idx, (name, purchase_count, total_spent) in enumerate(top_customers):
            # Item frame
            item_frame = QFrame()
            item_frame.setStyleSheet("""
                QFrame {
                    background: rgba(0, 255, 136, 0.05);
                    border: 1px solid rgba(0, 255, 136, 0.2);
                    border-radius: 6px;
                    padding: 8px;
                }
            """)
            item_layout = QHBoxLayout(item_frame)
            item_layout.setContentsMargins(8, 5, 8, 5)
            
            # Rank
            rank_lbl = QLabel(f"#{idx+1}")
            rank_lbl.setStyleSheet(f"color: {COLOR_ACCENT_GREEN}; font-weight: bold; font-size: 14px; border: none; background: transparent;")
            rank_lbl.setFixedWidth(30)
            
            # Name
            name_lbl = QLabel(name[:25])
            name_lbl.setStyleSheet("color: white; font-weight: bold; font-size: 11px; border: none; background: transparent;")
            
            # Stats
            stats_layout = QVBoxLayout()
            stats_layout.setSpacing(2)
            
            spent_lbl = QLabel(f"₹{total_spent:,.0f}")
            spent_lbl.setStyleSheet(f"color: {COLOR_ACCENT_YELLOW}; font-size: 12px; font-weight: bold; border: none; background: transparent;")
            
            orders_lbl = QLabel(f"{purchase_count} orders")
            orders_lbl.setStyleSheet("color: #888; font-size: 9px; border: none; background: transparent;")
            
            stats_layout.addWidget(spent_lbl)
            stats_layout.addWidget(orders_lbl)
            
            item_layout.addWidget(rank_lbl)
            item_layout.addWidget(name_lbl)
            item_layout.addStretch()
            item_layout.addLayout(stats_layout)
            
            self.list_layout.addWidget(item_frame)

class ShopBrandingDialog(QDialog):
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.setWindowTitle("Config Settings")
        self.setStyleSheet(f"background-color: #050505; color: {COLOR_TEXT_PRIMARY};")
        self.resize(550, 650)
        
        self.logo_path_to_save = None
        
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # --- Tabs ---
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid #333;
                background: #0f0f0f;
                border-radius: 6px;
                top: -1px;
            }}
            QTabBar::tab {{
                background: #111;
                color: #888;
                padding: 10px 20px;
                border: 1px solid #333;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
                font-weight: bold;
            }}
            QTabBar::tab:selected {{
                background: #1a1a1a;
                color: {COLOR_ACCENT_CYAN};
                border-top: 2px solid {COLOR_ACCENT_CYAN};
            }}
        """)
        main_layout.addWidget(self.tabs)
        
        # Tab 1: SHOP IDENTITY
        tab_shop = QWidget()
        self._setup_shop_tab(tab_shop)
        self.tabs.addTab(tab_shop, "🏪 SHOP IDENTITY")
        
        # Tab 2: TVS ECATALOG
        tab_tvs = QWidget()
        self._setup_tvs_tab(tab_tvs)
        self.tabs.addTab(tab_tvs, "🏍️ TVS ECATALOG")
        
        # --- Bottom Buttons ---
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_save = QPushButton("SAVE CHANGES")
        self.btn_save.setFixedHeight(36)
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.setStyleSheet(ui_theme.get_neon_action_button())
        self.btn_save.clicked.connect(self.save_settings)
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setFixedHeight(36)
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.setStyleSheet(ui_theme.get_cancel_button_style())
        self.btn_cancel.clicked.connect(self.reject)

        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_cancel)
        
        main_layout.addLayout(btn_layout)
        
        # --- Factory Reset Link ---
        self.btn_reset = QPushButton("⚠️ Factory Reset System")
        self.btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #666;
                border: none;
                font-size: 10px;
                text-decoration: underline;
                margin-top: 5px;
            }
            QPushButton:hover {
                color: #ff4444;
            }
        """)
        self.btn_reset.clicked.connect(self.perform_factory_reset)
        main_layout.addWidget(self.btn_reset, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Load Existing Data
        self.load_data()

    def _setup_shop_tab(self, tab):
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        self.lbl_title = QLabel("⚙️ SHOP BRANDING")
        self.lbl_title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {COLOR_ACCENT_CYAN}; border-bottom: 2px solid {COLOR_ACCENT_CYAN}; padding-bottom: 5px;")
        layout.addWidget(self.lbl_title)
        
        logo_frame = QFrame()
        logo_frame.setStyleSheet("border: 1px solid #333; border-radius: 8px; padding: 10px; background: #111;")
        logo_layout = QHBoxLayout(logo_frame)
        self.logo_preview = QLabel("No Logo")
        self.logo_preview.setFixedSize(160, 90)
        self.logo_preview.setStyleSheet("border: 1px dashed #666; background: #000; color: #aaa;")
        self.logo_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_preview.setScaledContents(True)
        btn_upload = QPushButton("🖼️ UPLOAD SHOP LOGO")
        btn_upload.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_upload.setStyleSheet(ui_theme.get_primary_button_style())
        btn_upload.clicked.connect(self.browse_logo)
        logo_layout.addWidget(self.logo_preview)
        logo_layout.addWidget(btn_upload)
        layout.addWidget(logo_frame)
        
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form_layout.setVerticalSpacing(20)
        
        self.in_name = QLineEdit()
        self.in_name.setStyleSheet(ui_theme.get_lineedit_style())
        form_layout.addRow("Shop Name:", self.in_name)
        
        self.in_gst = QLineEdit()
        self.in_gst.setStyleSheet(ui_theme.get_lineedit_style())
        form_layout.addRow("GSTIN No:", self.in_gst)
        
        self.in_mobile = QLineEdit()
        self.in_mobile.setPlaceholderText("e.g. 9800012345, 9900054321")
        self.in_mobile.setStyleSheet(ui_theme.get_lineedit_style())
        form_layout.addRow("Mobile Nos:", self.in_mobile)
        
        self.in_addr = QTextEdit()
        self.in_addr.setFixedHeight(80)
        self.in_addr.setStyleSheet(ui_theme.get_lineedit_style())
        form_layout.addRow("Address:", self.in_addr)
        
        layout.addLayout(form_layout)
        layout.addStretch()

    def _setup_tvs_tab(self, tab):
        from styles import COLOR_ACCENT_AMBER
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        lbl_title = QLabel("🏍️ TVS ECATALOG LOOKUP")
        lbl_title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {COLOR_ACCENT_CYAN}; border-bottom: 2px solid {COLOR_ACCENT_CYAN}; padding-bottom: 5px;")
        layout.addWidget(lbl_title)
        
        desc = QLabel(
            "Configure your TVS Advantage dealer credentials.\n"
            "Used by the Vehicle Compatibility Engine's \"🔎 TVS Lookup\" button — "
            "one part at a time, with automatic rate limiting."
        )
        desc.setStyleSheet("color: #999; font-weight: normal; margin-bottom: 5px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setVerticalSpacing(15)
        
        self.in_tvs_dealer_id = QLineEdit()
        self.in_tvs_dealer_id.setPlaceholderText("e.g. 63050")
        self.in_tvs_dealer_id.setStyleSheet(ui_theme.get_lineedit_style())
        
        self.in_tvs_branch_id = QLineEdit()
        self.in_tvs_branch_id.setPlaceholderText("e.g. 1")
        self.in_tvs_branch_id.setStyleSheet(ui_theme.get_lineedit_style())
        
        form.addRow(QLabel("Dealer ID:"), self.in_tvs_dealer_id)
        form.addRow(QLabel("Branch ID:"), self.in_tvs_branch_id)
        layout.addLayout(form)
        
        db_row = QHBoxLayout()
        db_lbl = QLabel("Catalog DB:")
        db_lbl.setStyleSheet("color: #aaa; font-weight: bold; min-width: 90px;")
        self.lbl_catalog_db = QLabel("Not configured")
        self.lbl_catalog_db.setStyleSheet(
            "color: #777; font-size: 11px; padding: 6px 10px;"
            " background: #0a0a0a; border-radius: 5px; border: 1px solid #222;"
        )
        self.lbl_catalog_db.setWordWrap(False)
        btn_browse_db = QPushButton("📂  Browse")
        btn_browse_db.setFixedSize(110, 36)
        btn_browse_db.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_browse_db.setStyleSheet(f"background: #1a1a1a; color: {COLOR_ACCENT_CYAN}; border: 1px solid #333; border-radius: 6px; font-weight: bold;")
        btn_browse_db.clicked.connect(self._browse_catalog_db)
        db_row.addWidget(db_lbl)
        db_row.addWidget(self.lbl_catalog_db, 1)
        db_row.addWidget(btn_browse_db)
        layout.addLayout(db_row)
        
        btn_row = QHBoxLayout()
        btn_test = QPushButton("🔌  TEST CONNECTION")
        btn_test.setFixedHeight(36)
        btn_test.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_test.setStyleSheet(
            f"QPushButton {{ background:rgba(255,170,0,0.1); color:{COLOR_ACCENT_AMBER};"
            f" border:2px solid {COLOR_ACCENT_AMBER}; border-radius:7px; font-weight:bold; padding:0 14px; }}"
            f"QPushButton:hover {{ background:{COLOR_ACCENT_AMBER}; color:black; }}"
        )
        btn_test.clicked.connect(self._test_tvs_connection)
        
        self.lbl_tvs_status = QLabel("Not tested")
        self.lbl_tvs_status.setStyleSheet("color: #666; font-size: 11px; font-style: italic; margin-left: 12px;")
        
        btn_row.addWidget(btn_test)
        btn_row.addWidget(self.lbl_tvs_status, 1)
        layout.addLayout(btn_row)
        
        warn = QLabel(
            "⚠️  Rate Limit: This lookup is for single-part use only. "
            "Never run bulk automated requests against the TVS server."
        )
        warn.setStyleSheet("color: #664400; font-size: 10px; font-style: italic;")
        warn.setWordWrap(True)
        layout.addWidget(warn)
        layout.addStretch()

    def load_data(self):
        import os
        current = self.db_manager.get_shop_settings()
        
        # Tab 1
        self.in_name.setText(current.get("shop_name", ""))
        self.in_gst.setText(current.get("gstin", ""))
        self.in_mobile.setText(current.get("mobile", ""))
        self.in_addr.setPlainText(current.get("address", ""))
        
        existing_logo = current.get("logo_path", "")
        if existing_logo and os.path.exists(existing_logo):
            self.logo_preview.setPixmap(QPixmap(existing_logo))
            self.logo_path_to_save = existing_logo 
            
        # Tab 2
        self.in_tvs_dealer_id.setText(current.get("tvs_dealer_id", "63050"))
        self.in_tvs_branch_id.setText(current.get("tvs_branch_id", ""))
        
        cat_db = current.get("nexses_catalog_db", "")
        if not cat_db or not os.path.exists(cat_db):
            from path_utils import get_resource_path
            cat_db = get_resource_path("nexses_ecatalog.db")
            if not os.path.exists(cat_db):
                try:
                    import db_engine
                    db_engine.initialize_database(cat_db)
                except Exception:
                    pass
            try:
                self.db_manager.update_setting("nexses_catalog_db", cat_db)
            except Exception:
                pass
        
        self._catalog_db_path = cat_db
        if cat_db and os.path.isfile(cat_db):
            self.lbl_catalog_db.setText(os.path.basename(cat_db))
            self.lbl_catalog_db.setStyleSheet(
                "color: #00ff41; font-size: 11px; padding: 6px 10px;"
                " background: #0a0a0a; border-radius: 5px; border: 1px solid #222;"
            )
            self.lbl_catalog_db.setToolTip(cat_db)
        else:
            self.lbl_catalog_db.setText("Not configured" if not cat_db else f"⚠️ Not found: {os.path.basename(cat_db)}")
            self.lbl_catalog_db.setStyleSheet("color: #777; font-size: 11px; padding: 6px 10px; background: #0a0a0a; border-radius: 5px; border: 1px solid #222;")

    def browse_logo(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Select Logo", "", "Images (*.png *.jpg *.jpeg)")
        if fname:
            pix = QPixmap(fname)
            self.logo_preview.setPixmap(pix)
            self.logo_path_to_save = fname

    def _browse_catalog_db(self):
        import os
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Nexses eCatalog DB", "", "SQLite DB (*.db *.sqlite *.sqlite3)"
        )
        if path:
            self._catalog_db_path = path
            self.lbl_catalog_db.setText(os.path.basename(path))
            self.lbl_catalog_db.setStyleSheet(
                "color: #00ff41; font-size: 11px; padding: 6px 10px;"
                " background: #0a0a0a; border-radius: 5px; border: 1px solid #222;"
            )
            self.lbl_catalog_db.setToolTip(path)

    def _test_tvs_connection(self):
        from tvs_catalog_client import TVSCatalogClient
        from PyQt6.QtWidgets import QApplication
        
        dealer_id = self.in_tvs_dealer_id.text().strip() or "63050"
        self.lbl_tvs_status.setText("🔄  Connecting... ")
        self.lbl_tvs_status.setStyleSheet("color: #aaa; font-size: 11px;")
        QApplication.processEvents()
        try:
            client = TVSCatalogClient(dealer_id=dealer_id)
            ok = client.connect()
            if ok:
                self.lbl_tvs_status.setText("✅  Connected & Authenticated")
                self.lbl_tvs_status.setStyleSheet("color: #00ff41; font-size: 11px; font-weight: bold;")
            else:
                self.lbl_tvs_status.setText("❌  Auth Failed (Check ID)")
                self.lbl_tvs_status.setStyleSheet("color: #ff4444; font-size: 11px;")
        except Exception as e:
            self.lbl_tvs_status.setText(f"❌  Error: {str(e)[:30]}")
            self.lbl_tvs_status.setStyleSheet("color: #ff4444; font-size: 11px;")

    def save_settings(self):
        import os
        import shutil
        from path_utils import get_app_data_path  # type: ignore
        logos_dir = get_app_data_path("logos")
        final_logo_path = os.path.join(logos_dir, "logo.png")
        
        if self.logo_path_to_save and os.path.abspath(self.logo_path_to_save) != os.path.abspath(final_logo_path):
            try:
                shutil.copy(self.logo_path_to_save, final_logo_path)
            except Exception as e:
                ProMessageBox.warning(self, "Warning", f"Could not save logo file: {e}")

        new_shop_settings = {
            "shop_name": self.in_name.text(),
            "shop_address": self.in_addr.toPlainText(),
            "shop_mobile": self.in_mobile.text(),
            "shop_gstin": self.in_gst.text(),
            "logo_path": final_logo_path 
        }
        
        if not ProMessageBox.question(self, "Confirm Save", "Are you sure you want to save all changes?"):
            return

        success, msg = self.db_manager.update_shop_settings(new_shop_settings)
        
        # Save TVS settings
        self.db_manager.update_setting("tvs_dealer_id", self.in_tvs_dealer_id.text().strip() or "63050")
        self.db_manager.update_setting("tvs_branch_id", self.in_tvs_branch_id.text().strip())
        if hasattr(self, '_catalog_db_path') and self._catalog_db_path:
            self.db_manager.update_setting("nexses_catalog_db", self._catalog_db_path)

        if success:
            ProMessageBox.information(self, "Success", "Configuration Updated Successfully!")
            self.accept()
        else:
            ProMessageBox.warning(self, "Error", msg)

    def perform_factory_reset(self):
        # 1. First Warning
        if not ProMessageBox.question(self, "FACTORY RESET", "⚠️ WARNING: This will DELETE ALL DATA.\\n\\nAre you absolutely sure you want to proceed?"):
            return
            
        # 2. Second Confirmation
        text, ok = QInputDialog.getText(self, "Confirm Reset", "Type 'RESET' to confirm deletion:", QLineEdit.EchoMode.Normal)
        
        if ok and text == "RESET":
            success, msg = self.db_manager.factory_reset()
            if success:
                ProMessageBox.information(self, "System Reset", "System has been reset successfully.\\nThe application will now restart/close.")
                import sys
                sys.exit(0)
            else:
                ProMessageBox.critical(self, "Reset Failed", f"Error: {msg}")
        else:
             if ok:
                 ProMessageBox.warning(self, "Cancelled", "Incorrect confirmation text. Reset cancelled.")


class ReportsPage(QWidget):
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self.setup_ui()
        self.load_data()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # --- Header ---
        header_row = QHBoxLayout()
        # Config Shop Button (Stealth Mode - Top Left)
        self.btn_config = QPushButton("")
        self.btn_config.setFixedSize(36, 36)
        self.btn_config.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_config.setStyleSheet("background: transparent; border: none;")
        self.btn_config.clicked.connect(self.open_config_dialog)
        header_row.addWidget(self.btn_config)

        self.title = QLabel("📊 SALES ANALYTICS & REPORTS")
        self.title.setStyleSheet(ui_theme.get_page_title_style())
        header_row.addWidget(self.title)
        header_row.addStretch()
        layout.addLayout(header_row)
        
        # Toggle Button
        self.btn_view_toggle = QPushButton("📈 INSIGHTS")
        self.btn_view_toggle.setFixedHeight(36)
        self.btn_view_toggle.setCheckable(True)
        self.btn_view_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_view_toggle.setStyleSheet(ui_theme.get_small_button_style("green"))
        self.btn_view_toggle.toggled.connect(self.toggle_view)
        header_row.addWidget(self.btn_view_toggle)
        # (header_row already added to layout above — do NOT add again here)
        
        # --- Top Filter Bar ---
        self.filter_frame = QFrame()
        self.filter_frame.setStyleSheet(STYLE_GLASS_PANEL)
        filter_layout = QHBoxLayout(self.filter_frame)
        filter_layout.setContentsMargins(15, 10, 15, 10)
        
        # Live Search
        self.search_in = QLineEdit()
        self.search_in.setPlaceholderText("🔍 Search Customer, Mobile, or Inv ID...")
        self.search_in.setStyleSheet(ui_theme.get_lineedit_style())
        self.search_in.setFixedWidth(300)
        self.search_in.textChanged.connect(self.load_data)
        
        # Date Pickers
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addDays(-30))
        self.date_from.setStyleSheet(ui_theme.get_lineedit_style())
        self.date_from.setFixedWidth(120)
        self.date_from.dateChanged.connect(self.load_data)
        
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setStyleSheet(ui_theme.get_lineedit_style())
        self.date_to.setFixedWidth(120)
        self.date_to.dateChanged.connect(self.load_data)
        
        # Refresh Button
        btn_refresh = QPushButton("🔄 REFRESH")
        btn_refresh.setFixedWidth(110)
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.setStyleSheet(ui_theme.get_small_button_style("green"))
        btn_refresh.clicked.connect(self.load_data)
        
        # Export Button (Now with menu)
        self.btn_export = QPushButton("📥 EXPORT")
        self.btn_export.setFixedWidth(110)
        self.btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_export.setStyleSheet(ui_theme.get_small_button_style("amber") + " QPushButton::menu-indicator { image: none; width: 0px; }")
        
        self.export_menu = QMenu(self)
        self.export_menu.setStyleSheet(ui_theme.get_menu_style())
        
        # Section 1: Excel
        self.export_menu.addSection("📊 EXCEL EXPORT")
        excel_all_action = QAction("📥 Export All to Excel", self)
        excel_all_action.triggered.connect(lambda: self.export_to_excel(selection_only=False))
        self.export_menu.addAction(excel_all_action)
        
        excel_sel_action = QAction("📍 Export Selected to Excel", self)
        excel_sel_action.triggered.connect(lambda: self.export_to_excel(selection_only=True))
        self.export_menu.addAction(excel_sel_action)
        
        self.export_menu.addSeparator()
        
        # Section 2: PDF
        self.export_menu.addSection("📄 PDF EXPORT")
        pdf_all_action = QAction("📄 Export All to PDF", self)
        pdf_all_action.triggered.connect(lambda: self.export_to_pdf(selection_only=False))
        self.export_menu.addAction(pdf_all_action)
        
        pdf_sel_action = QAction("🎯 Export Selected to PDF", self)
        pdf_sel_action.triggered.connect(lambda: self.export_to_pdf(selection_only=True))
        self.export_menu.addAction(pdf_sel_action)
        
        self.export_menu.addSeparator()
        
        self.btn_select_all = QPushButton("✅ Select All")
        self.btn_select_all.setCheckable(True)
        self.btn_select_all.setFixedWidth(110)
        self.btn_select_all.setStyleSheet(ui_theme.get_small_button_style("cyan"))
        self.btn_select_all.clicked.connect(self.toggle_select_all)
        
        comp_report_action = QAction("📑 Comprehensive Detailed Report (PDF)", self)
        comp_report_action.triggered.connect(self.export_comprehensive_report)
        self.export_menu.addAction(comp_report_action)

        self.btn_export.setMenu(self.export_menu)

        self.lbl_search = QLabel("Search:")
        filter_layout.addWidget(self.lbl_search)
        filter_layout.addWidget(self.search_in)
        filter_layout.addSpacing(20)
        filter_layout.addWidget(QLabel("From:"))
        filter_layout.addWidget(self.date_from)
        filter_layout.addWidget(QLabel("To:"))
        filter_layout.addWidget(self.date_to)
        filter_layout.addWidget(btn_refresh)
        filter_layout.addSpacing(10)
        filter_layout.addWidget(self.btn_select_all)

        # Dues-only toggle
        self.btn_dues_only = QPushButton("🔴 SHOW DUES")
        self.btn_dues_only.setCheckable(True)
        self.btn_dues_only.setFixedWidth(120)
        self.btn_dues_only.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_dues_only.setStyleSheet(ui_theme.get_small_button_style("red"))
        self.btn_dues_only.toggled.connect(self._on_dues_filter_toggled)
        filter_layout.addWidget(self.btn_dues_only)
        filter_layout.addStretch()

        # Dedicated Print Comprehensive Report button (themed)
        self.btn_print_report = QPushButton("\U0001f5a8\ufe0f  PRINT REPORT")
        self.btn_print_report.setFixedWidth(145)
        self.btn_print_report.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_print_report.setStyleSheet(ui_theme.get_small_button_style("cyan"))
        self.btn_print_report.clicked.connect(self.export_comprehensive_report)
        filter_layout.addWidget(self.btn_print_report)
        filter_layout.addSpacing(8)
        filter_layout.addWidget(self.btn_export)

        
        layout.addWidget(self.filter_frame)
        
        # --- Content Stack ---
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)
        
        # PAGE 0: Table View
        self.page_table = QWidget()
        page_table_layout = QVBoxLayout(self.page_table)
        page_table_layout.setContentsMargins(0, 0, 0, 0)
        
        # --- Smart Table ---
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        # CHECK, DATE, INVOICE ID, CUSTOMER, ITEMS, AMOUNT, STATUS, PAYMENT, DAY EXPENSE
        self.table.setHorizontalHeaderLabels(["", "DATE", "INVOICE ID", "CUSTOMER", "ITEMS", "AMOUNT", "STATUS", "PAYMENT", "DAY EXPENSE"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)  # Check
        self.table.setColumnWidth(0, 40)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Date
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Items
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # Status
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)  # Payment
        
        # Context Menu
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.viewport().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.viewport().customContextMenuRequested.connect(self.show_context_menu)
        
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setStyleSheet(ui_theme.get_table_style())
        
        self.delegate = ProTableDelegate(self.table)
        for c in range(self.table.columnCount()): 
             self.table.setItemDelegateForColumn(c, self.delegate)

        page_table_layout.addWidget(self.table)
        
        # Double-click opens invoice tracker
        self.table.doubleClicked.connect(self._on_row_double_click)
        
        # --- Bottom Analytics Bar ---
        analytics_frame = QFrame()
        analytics_frame.setStyleSheet(f"""
            QFrame {{
                background-color: rgba(0, 0, 0, 0.6);
                border-top: 2px solid {COLOR_ACCENT_CYAN};
                border-bottom-left-radius: 10px;
                border-bottom-right-radius: 10px;
            }}
        """)
        an_layout = QHBoxLayout(analytics_frame)
        an_layout.setContentsMargins(20, 15, 20, 15)
        self.lbl_total_rev = QLabel("REVENUE: ₹ 0.00")
        self.lbl_total_rev.setStyleSheet(f"color: {COLOR_ACCENT_GREEN}; font-size: 16px; font-weight: bold;")
        
        self.lbl_total_exp = QLabel("EXPENSES: ₹ 0.00")
        self.lbl_total_exp.setStyleSheet(f"color: {COLOR_ACCENT_RED}; font-size: 16px; font-weight: bold;")

        self.lbl_net_profit = QLabel("NET PROFIT: ₹ 0.00")
        self.lbl_net_profit.setStyleSheet(f"color: {COLOR_ACCENT_CYAN}; font-size: 18px; font-weight: bold;")

        self.lbl_total_count = QLabel("COUNT: 0")
        self.lbl_total_count.setStyleSheet("color: #ecf0f1; font-size: 14px;")

        an_layout.addWidget(self.lbl_total_rev)
        an_layout.addSpacing(30)
        an_layout.addWidget(self.lbl_total_exp)
        an_layout.addSpacing(30)
        an_layout.addWidget(self.lbl_net_profit)
        an_layout.addStretch()

        # ── Payment breakdown labels ──────────────────────────────────
        sep_v = QFrame()
        sep_v.setFrameShape(QFrame.Shape.VLine)
        sep_v.setStyleSheet("color: #222;")
        an_layout.addWidget(sep_v)

        self.lbl_pay_cash = QLabel("💵 CASH: ₹ 0")
        self.lbl_pay_cash.setStyleSheet("color: #00e5ff; font-size: 13px; font-weight: bold;")
        an_layout.addWidget(self.lbl_pay_cash)

        self.lbl_pay_upi = QLabel("📱 UPI: ₹ 0")
        self.lbl_pay_upi.setStyleSheet("color: #00ff88; font-size: 13px; font-weight: bold;")
        an_layout.addWidget(self.lbl_pay_upi)

        self.lbl_pay_due = QLabel("⚠️ DUES: ₹ 0")
        self.lbl_pay_due.setStyleSheet("color: #ff6b35; font-size: 13px; font-weight: bold;")
        an_layout.addWidget(self.lbl_pay_due)

        an_layout.addSpacing(20)
        an_layout.addWidget(self.lbl_total_count)

        page_table_layout.addWidget(analytics_frame)
        
        self.stack.addWidget(self.page_table)
        
        # PAGE 1: Dashboard
        self.setup_dashboard_ui()

    def setup_dashboard_ui(self):
        self.page_dashboard = QWidget()
        dash_layout = QVBoxLayout(self.page_dashboard)
        dash_layout.setContentsMargins(0, 5, 0, 0)
        dash_layout.setSpacing(12)

        # ── Row 1: Five Stat Cards ────────────────────────────────────────────
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(10)
        self.card_revenue   = AnimatedStatCard("TOTAL REVENUE",  "₹ 0", "💰", COLOR_ACCENT_YELLOW)
        self.card_orders    = AnimatedStatCard("TOTAL ORDERS",   "0",   "📦", COLOR_ACCENT_CYAN)
        self.card_avg_order = AnimatedStatCard("AVG ORDER VALUE","₹ 0", "📊", "#a78bfa")
        self.card_profit    = AnimatedStatCard("NET PROFIT",     "₹ 0", "📈", COLOR_ACCENT_GREEN)
        self.card_top_item  = AnimatedStatCard("TOP ITEM",       "-",   "🔥", COLOR_ACCENT_RED)

        for card in (self.card_revenue, self.card_orders, self.card_avg_order,
                     self.card_profit, self.card_top_item):
            cards_layout.addWidget(card)
        dash_layout.addLayout(cards_layout)

        # ── Row 2: Charts row ─────────────────────────────────────────────────
        charts_row = QHBoxLayout()
        charts_row.setSpacing(10)

        # Left: Daily Sales Bar Chart
        self.chart_frame_daily = QFrame()
        self.chart_frame_daily.setStyleSheet("""
            QFrame {
                background-color: rgba(11,11,20,0.85);
                border: 1px solid #2a2a3e;
                border-radius: 10px;
            }
        """)
        daily_vlay = QVBoxLayout(self.chart_frame_daily)
        daily_vlay.setContentsMargins(12, 8, 12, 8)
        daily_hdr = QLabel("📅 DAILY SALES TREND")
        daily_hdr.setStyleSheet(f"color: {COLOR_ACCENT_CYAN}; font-size: 13px; font-weight: bold; border:none; background:transparent;")
        daily_vlay.addWidget(daily_hdr)

        # QChartView for daily bar chart
        self._chart_daily = QChart()
        self._chart_daily.setBackgroundBrush(QColor("#0b0b14"))
        self._chart_daily.setPlotAreaBackgroundBrush(QColor("#0d0d1a"))
        self._chart_daily.setPlotAreaBackgroundVisible(True)
        self._chart_daily.legend().setVisible(False)
        self._chart_daily.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        self._chart_daily.layout().setContentsMargins(0, 0, 0, 0)
        self._chart_daily.setMargins(QMargins(4, 4, 4, 4))

        self._chartview_daily = QChartView(self._chart_daily)
        self._chartview_daily.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._chartview_daily.setMinimumHeight(180)
        self._chartview_daily.setStyleSheet("background: transparent; border: none;")
        daily_vlay.addWidget(self._chartview_daily)

        # Right: Payment Mode Breakdown
        self.chart_frame_pay = QFrame()
        self.chart_frame_pay.setStyleSheet("""
            QFrame {
                background-color: rgba(11,11,20,0.85);
                border: 1px solid #2a2a3e;
                border-radius: 10px;
            }
        """)
        self.chart_frame_pay.setFixedWidth(260)
        pay_vlay = QVBoxLayout(self.chart_frame_pay)
        pay_vlay.setContentsMargins(12, 8, 12, 8)
        pay_hdr = QLabel("💳 PAYMENT SPLIT")
        pay_hdr.setStyleSheet(f"color: {COLOR_ACCENT_GREEN}; font-size: 13px; font-weight: bold; border:none; background:transparent;")
        pay_vlay.addWidget(pay_hdr)
        self._pay_bars_layout = QVBoxLayout()
        self._pay_bars_layout.setSpacing(8)
        pay_vlay.addLayout(self._pay_bars_layout)
        pay_vlay.addStretch()

        charts_row.addWidget(self.chart_frame_daily, 1)
        charts_row.addWidget(self.chart_frame_pay, 0)
        dash_layout.addLayout(charts_row)

        # ── Row 3: Performers | Customers | Low Stock | Activity ─────────────
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(10)

        # Top Performers
        self.widget_top_parts = TopPerformerWidget()
        bottom_row.addWidget(self.widget_top_parts, 2)

        # Top Customers
        self.widget_top_customers = CustomerInsightsWidget()
        bottom_row.addWidget(self.widget_top_customers, 2)

        # Low Stock Alert
        self.widget_low_stock = self._make_low_stock_widget()
        bottom_row.addWidget(self.widget_low_stock, 2)

        # Recent Activity Feed
        self.widget_activity = self._make_activity_widget()
        bottom_row.addWidget(self.widget_activity, 2)

        dash_layout.addLayout(bottom_row)
        self.stack.addWidget(self.page_dashboard)

    # ── Helper: Low-Stock Widget frame ───────────────────────────────────────
    def _make_low_stock_widget(self):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: rgba(11,11,20,0.85);
                border: 1px solid #2a2a3e;
                border-radius: 10px;
            }
        """)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)
        hdr = QLabel("⚠️ LOW STOCK ALERT")
        hdr.setStyleSheet(f"color: {COLOR_ACCENT_RED}; font-size: 13px; font-weight: bold; border:none; background:transparent;")
        layout.addWidget(hdr)
        self._low_stock_list = QVBoxLayout()
        self._low_stock_list.setSpacing(4)
        layout.addLayout(self._low_stock_list)
        layout.addStretch()
        return frame

    # ── Helper: Activity Feed frame ───────────────────────────────────────────
    def _make_activity_widget(self):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: rgba(11,11,20,0.85);
                border: 1px solid #2a2a3e;
                border-radius: 10px;
            }
        """)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(5)
        hdr = QLabel("🕐 RECENT INVOICES")
        hdr.setStyleSheet(f"color: #a78bfa; font-size: 13px; font-weight: bold; border:none; background:transparent;")
        layout.addWidget(hdr)
        self._activity_list = QVBoxLayout()
        self._activity_list.setSpacing(4)
        layout.addLayout(self._activity_list)
        layout.addStretch()
        return frame


    def toggle_view(self, checked):
        if checked:
            self.btn_view_toggle.setText("📋 LIST")
            self.stack.setCurrentIndex(1)
            # Hide Search
            self.search_in.setVisible(False)
            self.lbl_search.setVisible(False)
            self.load_dashboard_data()
        else:
            self.btn_view_toggle.setText("📈 INSIGHTS")
            self.stack.setCurrentIndex(0)
            # Show Search
            self.search_in.setVisible(True)
            self.lbl_search.setVisible(True)

    def _clear_layout(self, layout):
        """Recursively remove and delete all items from a layout (widgets + sub-layouts)."""
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            else:
                sub = item.layout()
                if sub is not None:
                    self._clear_layout(sub)

    def load_dashboard_data(self):

        """Load / refresh all dashboard widgets."""
        d_from = self.date_from.date().toString("yyyy-MM-dd")
        d_to   = self.date_to.date().toString("yyyy-MM-dd")

        # ── 1. Stat Cards ─────────────────────────────────────────────────────
        stats = self.db_manager.get_sales_statistics(d_from, d_to)
        # (total_invoices, total_revenue, avg_order, max_order, min_order)
        rev    = stats[1] if stats and stats[1] else 0.0
        orders = stats[0] if stats and stats[0] else 0
        avg    = stats[2] if stats and stats[2] else 0.0

        # Net profit = revenue − expenses − COGS for the period
        try:
            total_exp  = sum(self.db_manager.get_expenses_by_day(d_from, d_to).values())
            total_cogs = self.db_manager.get_total_cogs(d_from, d_to)
            net_profit = rev - total_exp - total_cogs
        except Exception:
            net_profit = 0.0

        self.card_revenue.set_value(f"₹ {rev:,.0f}")
        self.card_orders.set_value(str(orders))
        self.card_avg_order.set_value(f"₹ {avg:,.0f}")
        self.card_profit.set_value(f"₹ {net_profit:,.0f}")

        # ── 2. Daily Bar Chart ────────────────────────────────────────────────
        daily_rows = self.db_manager.get_sales_by_date_range(d_from, d_to)
        # daily_rows: [(date_str, daily_net_total, invoice_count), ...]
        self._chart_daily.removeAllSeries()
        for ax in list(self._chart_daily.axes()):  # snapshot list – avoid mutating while iterating
            self._chart_daily.removeAxis(ax)

        if daily_rows:
            bar_set = QBarSet("Sales")
            bar_set.setColor(QColor("#00e5ff"))
            bar_set.setBorderColor(QColor("#00e5ff"))
            categories = []
            max_val = 0.0
            for (dt, total, _count) in daily_rows:
                val = max(0.0, float(total or 0))
                bar_set.append(val)
                # Short label: e.g. "Apr 3"
                try:
                    from datetime import datetime as _dt
                    label = _dt.strptime(dt, "%Y-%m-%d").strftime("%d %b")
                except Exception:
                    label = str(dt)[-5:]
                categories.append(label)
                if val > max_val:
                    max_val = val

            bar_series = QBarSeries()
            bar_series.append(bar_set)
            self._chart_daily.addSeries(bar_series)

            axis_x = QBarCategoryAxis()
            axis_x.append(categories)
            axis_x.setLabelsColor(QColor("#888"))
            axis_x.setGridLineColor(QColor("#1a1a2e"))
            self._chart_daily.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
            bar_series.attachAxis(axis_x)

            axis_y = QValueAxis()
            axis_y.setRange(0, max_val * 1.15 if max_val > 0 else 100)
            axis_y.setLabelsColor(QColor("#888"))
            axis_y.setGridLineColor(QColor("#1a1a2e"))
            axis_y.setTickCount(5)
            self._chart_daily.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
            bar_series.attachAxis(axis_y)
        else:
            # Placeholder when no data
            bar_set = QBarSet("No Data")
            bar_set.append(0)
            bar_set.setColor(QColor("#2a2a3e"))
            empty_series = QBarSeries()
            empty_series.append(bar_set)
            self._chart_daily.addSeries(empty_series)

        # ── 3. Payment Split Bars ─────────────────────────────────────────────
        pay_data = self.db_manager.get_payment_mode_breakdown(d_from, d_to)
        cash_v = pay_data["cash"]
        upi_v  = pay_data["upi"]
        due_v  = pay_data["due"]
        total_pay = max(cash_v + upi_v + due_v, 1.0)

        self._clear_layout(self._pay_bars_layout)

        pay_items = [
            ("💵 Cash",  cash_v, "#00e5ff"),
            ("📱 UPI",   upi_v,  "#00ff88"),
            ("⚠️ Due",   due_v,  "#ff6b35"),
        ]
        for (label, value, color) in pay_items:
            pct = int((value / total_pay) * 100)
            row_frame = QFrame()
            row_frame.setStyleSheet("background: transparent; border: none;")
            row_layout = QVBoxLayout(row_frame)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(2)

            top_row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: bold; border:none; background:transparent;")
            amt_lbl = QLabel(f"₹{value:,.0f}  ({pct}%)")
            amt_lbl.setStyleSheet("color: #aaa; font-size: 10px; border:none; background:transparent;")
            top_row.addWidget(lbl)
            top_row.addStretch()
            top_row.addWidget(amt_lbl)
            row_layout.addLayout(top_row)

            prog = QProgressBar()
            prog.setRange(0, 100)
            prog.setValue(pct)
            prog.setTextVisible(False)
            prog.setFixedHeight(7)
            prog.setStyleSheet(f"""
                QProgressBar {{
                    background: #1a1a2e;
                    border: none;
                    border-radius: 3px;
                }}
                QProgressBar::chunk {{
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                        stop:0 {color}, stop:1 rgba(0,0,0,0.2));
                    border-radius: 3px;
                }}
            """)
            row_layout.addWidget(prog)
            self._pay_bars_layout.addWidget(row_frame)

        # ── 4. Top Parts + Top Customers ─────────────────────────────────────
        top_parts = self.db_manager.get_top_selling_parts(d_from, d_to, 5)
        self.widget_top_parts.set_data(top_parts)

        if top_parts:
            name = top_parts[0][1] if top_parts[0][1] else "Unknown"
            self.card_top_item.set_value(str(name)[:15])
        else:
            self.card_top_item.set_value("-")

        # get_top_customers returns (name, mobile, count, net_spent)
        raw_customers = self.db_manager.get_top_customers(d_from, d_to, 5)
        # CustomerInsightsWidget.set_data expects (name, purchase_count, total_spent)
        top_customers = [(r[0], r[2], r[3]) for r in raw_customers]
        self.widget_top_customers.set_data(top_customers)

        # ── 5. Low Stock Alert ────────────────────────────────────────────────
        self._clear_layout(self._low_stock_list)

        low_stock = self.db_manager.get_low_stock_parts(6)
        if low_stock:
            for (pid, pname, qty, reorder, cat) in low_stock:
                urgency_color = "#ff4444" if qty == 0 else "#ff9800" if qty <= 2 else "#ffcc00"
                row_frame = QFrame()
                row_frame.setStyleSheet(f"""
                    QFrame {{
                        background: rgba(255,100,0,0.05);
                        border: 1px solid {urgency_color}40;
                        border-radius: 5px;
                    }}
                """)
                r_layout = QHBoxLayout(row_frame)
                r_layout.setContentsMargins(6, 3, 6, 3)
                dot = QLabel("●")
                dot.setStyleSheet(f"color: {urgency_color}; font-size: 10px; border:none; background:transparent;")
                name_lbl = QLabel(str(pname)[:22])
                name_lbl.setStyleSheet("color: #ddd; font-size: 10px; font-weight:bold; border:none; background:transparent;")
                qty_lbl = QLabel(f"Qty:{qty}/{reorder}")
                qty_lbl.setStyleSheet(f"color: {urgency_color}; font-size: 10px; font-weight:bold; border:none; background:transparent;")
                r_layout.addWidget(dot)
                r_layout.addWidget(name_lbl)
                r_layout.addStretch()
                r_layout.addWidget(qty_lbl)
                self._low_stock_list.addWidget(row_frame)
        else:
            ok_lbl = QLabel("✅ All stock levels OK")
            ok_lbl.setStyleSheet("color: #00ff88; font-size: 11px; font-style:italic; border:none; background:transparent;")
            self._low_stock_list.addWidget(ok_lbl)

        # ── 6. Recent Invoices Feed ───────────────────────────────────────────
        self._clear_layout(self._activity_list)

        recent = self.db_manager.get_recent_invoices(6)
        if recent:
            mode_colors = {
                "CASH":    "#00e5ff",
                "UPI":     "#00ff88",
                "SPLIT":   "#f1c40f",
                "PARTIAL": "#ff9800",
                "DUE":     "#ff4444",
            }
            for (inv_id, cust, amount, mode, due_amt, date_val) in recent:
                color = mode_colors.get(str(mode).upper(), "#aaa")
                if due_amt and float(due_amt) > 0.01 and mode not in ("PARTIAL", "DUE"):
                    color = mode_colors["PARTIAL"]

                row_frame = QFrame()
                row_frame.setStyleSheet(f"""
                    QFrame {{
                        background: rgba(167,139,250,0.05);
                        border: 1px solid rgba(167,139,250,0.15);
                        border-radius: 5px;
                    }}
                """)
                r_layout = QHBoxLayout(row_frame)
                r_layout.setContentsMargins(6, 3, 6, 3)

                id_lbl = QLabel(f"#{inv_id}")
                id_lbl.setStyleSheet("color: #a78bfa; font-size: 9px; font-weight:bold; min-width:45px; border:none; background:transparent;")
                cust_lbl = QLabel(str(cust)[:18])
                cust_lbl.setStyleSheet("color: #ccc; font-size: 10px; border:none; background:transparent;")
                amt_lbl = QLabel(f"₹{amount:,.0f}")
                amt_lbl.setStyleSheet(f"color: {color}; font-size: 10px; font-weight:bold; border:none; background:transparent;")

                r_layout.addWidget(id_lbl)
                r_layout.addWidget(cust_lbl)
                r_layout.addStretch()
                r_layout.addWidget(amt_lbl)
                self._activity_list.addWidget(row_frame)
        else:
            empty_lbl = QLabel("No invoices yet")
            empty_lbl.setStyleSheet("color: #555; font-style:italic; border:none; background:transparent;")
            self._activity_list.addWidget(empty_lbl)



    def show_context_menu(self, pos):
        # Using global position mapped to viewport is most reliable for QTableWidget
        viewport_pos = self.table.viewport().mapFromGlobal(QCursor.pos())
        index = self.table.indexAt(viewport_pos)
        if not index.isValid(): return
        
        row = index.row()
        invoice_id = self.table.item(row, 2).text().split(' ')[0] # Extract ID safely
        customer_name = self.table.item(row, 3).text() if self.table.item(row, 3) else "Walk-in"
        is_return = "(RET)" in self.table.item(row, 2).text()
        
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #0b0b14;
                color: #00e5ff;
                border: 1px solid rgba(0, 229, 255, 0.4);
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
        """)

        # ── NEW: Invoice Tracker & Customer History ────────────────────────
        inv_detail_action = QAction("🔍 View Invoice Details", self)
        inv_detail_action.triggered.connect(
            lambda: self._open_invoice_tracker(invoice_id)
        )
        menu.addAction(inv_detail_action)

        cust_action = QAction("💎 Customer Profile & History", self)
        cust_action.triggered.connect(
            lambda: self._open_customer_history(customer_name)
        )
        menu.addAction(cust_action)

        menu.addSeparator()
        
        # 1. View PDF
        view_action = QAction("📄 View Invoice PDF", self)
        view_action.triggered.connect(lambda: self.open_pdf(invoice_id))
        menu.addAction(view_action)
        
        # 2. WhatsApp
        wa_action = QAction("📱 Share to WhatsApp", self)
        wa_action.triggered.connect(lambda: self.share_to_whatsapp_history(row))
        menu.addAction(wa_action)
        
        menu.addSeparator()
        
        # 3. Edit Invoice / Process Return (If not completely returned)
        if not is_return:
            edit_action = QAction("✏️ Edit Invoice", self)
            edit_action.triggered.connect(lambda: self.trigger_edit_invoice(invoice_id))
            menu.addAction(edit_action)

            ret_action = QAction("↩️ Process Return", self)
            ret_action.triggered.connect(lambda: self.open_return_dialog(invoice_id))
            menu.addAction(ret_action)

            # 4. Collect Due (only shown if there is a pending due)
            try:
                conn = self.db_manager.get_connection()
                cur = conn.execute(
                    "SELECT COALESCE(payment_due,0), COALESCE(payment_cash,0), COALESCE(payment_upi,0), total_amount FROM invoices WHERE invoice_id=?",
                    (invoice_id,)
                )
                pay_row = cur.fetchone()
                conn.close()
                if pay_row and float(pay_row[0]) > 0:
                    due_action = QAction(f"💰 Collect Due (₹ {float(pay_row[0]):,.2f})", self)
                    due_action.triggered.connect(
                        lambda _, iid=invoice_id, pr=pay_row: self.collect_due_payment(iid, pr)
                    )
                    menu.addAction(due_action)
            except Exception:
                pass
        else:
             info_action = QAction("ℹ️ Return Details", self)
             info_action.setEnabled(False)
             menu.addAction(info_action)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _on_row_double_click(self, index):
        """Double-click on any report row → open Invoice Tracker."""
        row = index.row()
        inv_item = self.table.item(row, 2)
        if inv_item:
            invoice_id = inv_item.text().split(' ')[0]
            self._open_invoice_tracker(invoice_id)

    def _open_invoice_tracker(self, invoice_id):
        """Fetch the full row from DB and open InvoiceTrackerDialog."""
        try:
            from report_tracker_dialogs import InvoiceTrackerDialog
            d_from = "2000-01-01"
            d_to   = "2099-12-31"
            rows = self.db_manager.get_sales_report(d_from, d_to, invoice_id)
            # get_sales_report with an exact invoice_id search always returns that invoice first
            match = next((r for r in rows if str(r[1]) == invoice_id), None)
            if not match and rows:
                match = rows[0]
            if match:
                dlg = InvoiceTrackerDialog(self.db_manager, match, parent=self)
                dlg.exec()
            else:
                ProMessageBox.warning(self, "Not Found", f"Invoice #{invoice_id} not found.")
        except Exception as e:
            app_logger.error(f"InvoiceTrackerDialog error: {e}")
            ProMessageBox.critical(self, "Error", str(e))

    def _open_customer_history(self, customer_name):
        """Open CustomerHistoryDialog for the given customer."""
        try:
            from report_tracker_dialogs import CustomerHistoryDialog
            dlg = CustomerHistoryDialog(self.db_manager, customer_name, parent=self)
            dlg.exec()
        except Exception as e:
            app_logger.error(f"CustomerHistoryDialog error: {e}")
            ProMessageBox.critical(self, "Error", str(e))

    def _on_dues_filter_toggled(self, checked):
        if checked:
            self.btn_dues_only.setText("✅ All Invoices")
        else:
            self.btn_dues_only.setText("🔴 SHOW DUES")
        self.load_data()

    def collect_due_payment(self, invoice_id, pay_row):
        """Open a payment dialog to collect the pending due on an existing invoice."""
        from billing_page import PaymentDialog
        existing_due  = float(pay_row[0])
        existing_cash = float(pay_row[1])
        existing_upi  = float(pay_row[2])
        total_amount  = float(pay_row[3])

        dlg = PaymentDialog(existing_due, invoice_id, self)
        if dlg.exec() != 1:  # QDialog.DialogCode.Accepted == 1
            return

        new_cash, new_upi, new_due, mode = dlg.get_result()

        # Accumulate with previously collected amounts
        final_cash = existing_cash + new_cash
        final_upi  = existing_upi  + new_upi
        final_due  = max(0.0, existing_due - new_cash - new_upi)

        if final_cash > 0 and final_upi > 0:
            final_mode = "SPLIT"
        elif final_upi > 0:
            final_mode = "UPI"
        else:
            final_mode = "CASH"
        if final_due > 0:
            final_mode = "PARTIAL" if (final_cash + final_upi) > 0 else "DUE"

        ok, msg = self.db_manager.update_invoice_payment(
            invoice_id, final_cash, final_upi, final_due, final_mode
        )
        if ok:
            # Re-generate the physical PDF receipt with the updated partial/full payment info!
            try:
                from invoice_generator import InvoiceGenerator
                ig = InvoiceGenerator(self.db_manager)
                ig.regenerate_invoice(invoice_id)
            except PermissionError:
                from custom_components import ProMessageBox
                ProMessageBox.warning(self, "Close PDF Please", "Payment saved!\n\nCould not update the PDF file because it is OPEN in your browser or another program.\n\nClose the PDF, then right-click and select 'View Invoice PDF' to see the updated dues.")
                self.load_data()
                return
            except Exception as e:
                import logging
                logging.getLogger("app").error(f"Error auto-regenerating due payment invoice: {e}")

            from custom_components import ProMessageBox
            if final_due <= 0:
                ProMessageBox.information(self, "✅ Paid", f"Invoice #{invoice_id} is now fully paid!")
            else:
                ProMessageBox.information(self, "Partial", f"Collected. Remaining due: ₹ {final_due:,.2f}")
            self.load_data()
        else:
            from custom_components import ProMessageBox
            ProMessageBox.critical(self, "Error", f"Could not update payment: {msg}")

    def trigger_edit_invoice(self, invoice_id):
        main_win = self.window()
        if hasattr(main_win, 'go_to_edit_invoice'):
            main_win.go_to_edit_invoice(invoice_id)
        else:
            ProMessageBox.warning(self, "Error", "Edit routing not available in main window.")

    def share_to_whatsapp_history(self, row):
        """Helper to share existing invoice to WhatsApp from history"""
        invoice_id = self.table.item(row, 2).text().split(' ')[0]
        cust_name = self.table.item(row, 3).text()
        # Find mobile from DB since it's not in the table
        try:
            # We might need to fetch invoice bundle to get mobile
            # For now, let's assume we can at least open the PDF directory or similar
            # More professional: query DB for this specific invoice mobile
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT mobile, total_amount, payment_due FROM invoices WHERE invoice_id = ?", (invoice_id,))
            res = cursor.fetchone()
            if res and res[0]:
                from whatsapp_helper import send_invoice_msg
                mobile = res[0]
                total = res[1]
                due_amt = res[2] if res[2] else 0.0
                
                # Get PDF Path
                from path_utils import get_app_data_path  # type: ignore
                pdf_path = get_app_data_path(os.path.join("invoices", f"{invoice_id}.pdf"))
                
                if not os.path.exists(pdf_path):
                    ProMessageBox.warning(self, "PDF Missing", "Generate PDF first or check 'invoices' folder.")
                    return
                
                shop_name = self.db_manager.get_shop_settings().get("shop_name", "SpareParts Pro")
                send_invoice_msg(mobile, cust_name, invoice_id, total, pdf_path, shop_name, due_amount=due_amt)
            else:
                ProMessageBox.warning(self, "No Mobile", "No mobile number associated with this invoice.")
        except Exception as e:
            app_logger.error(f"WhatsApp Share Error: {e}")
            ProMessageBox.critical(self, "Error", str(e))

    def load_data(self):
        # Update Dashboard if active
        if self.stack.currentIndex() == 1:
            self.load_dashboard_data()
            
        d_from = self.date_from.date().toString("yyyy-MM-dd")
        d_to = self.date_to.date().toString("yyyy-MM-dd")
        query = self.search_in.text().strip()
        
        # Fetch Data — pass dues_only filter if toggle is active
        dues_only = self.btn_dues_only.isChecked() if hasattr(self, 'btn_dues_only') else False
        rows = self.db_manager.get_sales_report(d_from, d_to, query, dues_only=dues_only)
        
        # Fetch Daily Expenses
        expense_map = self.db_manager.get_expenses_by_day(d_from, d_to)
        
        self.table.setRowCount(0)
        
        total_rev = 0.0
        total_exp_period = sum(expense_map.values()) if expense_map else 0.0
        
        sum_cash = 0.0
        sum_upi = 0.0
        sum_due = 0.0
        count_due = 0
        
        for i, row in enumerate(rows):
            self.table.insertRow(i)
            
            # Check Return Status (index 7: return_count)
            has_return = False
            if len(row) > 7 and row[7] > 0:
                has_return = True
                
            # Check Edit Status inside json_items
            is_edited = False
            try:
                j_data = json.loads(row[5]) if row[5] else {}
                if isinstance(j_data, str): j_data = json.loads(j_data)
                extra = j_data.get("extra_details", {})
                if extra.get("_is_edited"):
                    is_edited = True
            except:
                pass
                
            # Helper to create item with conditional styling
            def create_item(text, is_ret=False, is_edt=False):
                item = QTableWidgetItem(str(text))
                item.setData(Qt.ItemDataRole.UserRole, {'type': 'generic'})
                if is_ret:
                    item.setForeground(QColor("#ff4e4e"))
                    item.setBackground(QColor(42, 15, 18, 180)) # Translucent red
                    font = item.font()
                    font.setStrikeOut(True)
                    item.setFont(font)
                elif is_edt:
                    item.setForeground(QColor("#00e5ff"))
                    item.setBackground(QColor(10, 31, 38, 180)) # Translucent cyan
                    font = item.font()
                    font.setItalic(True)
                    item.setFont(font)
                return item

            # 0: Checkbox
            chk = QCheckBox()
            chk.setStyleSheet(ui_theme.get_table_checkbox_style())
            cw = QWidget()
            if has_return:
                cw.setStyleSheet("background-color: rgba(42, 15, 18, 180);")
            elif is_edited:
                cw.setStyleSheet("background-color: rgba(10, 31, 38, 180);")
            else:
                cw.setStyleSheet("background-color: transparent;")
            cl = QHBoxLayout(cw)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(chk)
            self.table.setCellWidget(i, 0, cw)

            # 1: Date
            dt_str = str(row[0]).split(' ')[0]
            self.table.setItem(i, 1, create_item(row[0], has_return, is_edited))
            
            # 2: Inv ID
            inv_text = str(row[1])
            if has_return: inv_text += " (RET)"
            elif is_edited: inv_text += " (EDT)"
            self.table.setItem(i, 1 + 1, create_item(inv_text, has_return, is_edited))
            
            # 3: Customer
            cust_item = create_item(row[2], has_return, is_edited)
            cust_item.setToolTip(str(row[2]))
            self.table.setItem(i, 2 + 1, cust_item)
            
            # 4: Items
            self.table.setItem(i, 3 + 1, create_item(row[3], has_return, is_edited))
            
            # 5: Amount
            amt = row[4] if row[4] else 0.0
            refund_amt = row[12] if len(row) > 12 and row[12] else 0.0
            actual_revenue = amt - refund_amt
            total_rev += actual_revenue
            item_amt = create_item(f"₹ {amt:,.2f}", has_return, is_edited)
            item_amt.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(i, 5, item_amt)
            
            # 6: Status
            status_text = "NORMAL"
            if has_return and is_edited:
                status_text = "RET/EDT"
            elif has_return:
                if actual_revenue <= 0:
                    status_text = "RETURNED"
                else:
                    status_text = "PARTIAL RET"
            elif is_edited:
                status_text = "REVISED"
                
            status_item = create_item(status_text, has_return, is_edited)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 6, status_item)

            # 7: PAYMENT tag
            pay_mode = str(row[11]) if len(row) > 11 else "CASH"
            pay_due  = float(row[10]) if len(row) > 10 else 0.0
            pay_upi  = float(row[9])  if len(row) > 9  else 0.0
            pay_cash = float(row[8])  if len(row) > 8  else amt
            
            sum_cash += pay_cash
            sum_upi += pay_upi
            sum_due += pay_due
            if pay_due > 0.01:
                count_due += 1

            mode_colors = {
                "CASH":    ("#00e5ff", "rgba(0,229,255,0.10)"),
                "UPI":     ("#00ff88", "rgba(0,255,136,0.10)"),
                "SPLIT":   ("#f1c40f", "rgba(241,196,15,0.10)"),
                "PARTIAL": ("#ff9800", "rgba(255,152,0,0.10)"),
                "DUE":     ("#ff4444", "rgba(255,68,68,0.10)"),
            }
            fg, bg = mode_colors.get(pay_mode, ("#aaa", "transparent"))
            if pay_due > 0.01 and pay_mode not in ("PARTIAL", "DUE"):
                fg, bg = mode_colors["PARTIAL"]
                pay_mode = "PARTIAL"

            pay_tag_txt = pay_mode
            if pay_mode == "SPLIT":
                pay_tag_txt = f"SPLIT (C:{pay_cash:g}|U:{pay_upi:g})"

            if pay_due >= 0.01:
                pay_tag_txt = f"DUE ₹{pay_due:,.2f}"
                
            pay_item = QTableWidgetItem(pay_tag_txt)
            pay_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            pay_item.setForeground(QColor(fg))
            pay_item.setBackground(QColor(bg))
            if has_return:
                pay_item.setBackground(QColor(42, 15, 18, 180))
            elif is_edited:
                pay_item.setBackground(QColor(10, 31, 38, 180))
            self.table.setItem(i, 7, pay_item)

            # 8: Day Expense
            day_exp = expense_map.get(dt_str, 0.0)
            item_exp = QTableWidgetItem(f"₹ {day_exp:,.2f}")
            item_exp.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item_exp.setForeground(QColor(COLOR_ACCENT_RED))
            if has_return:
                item_exp.setBackground(QColor(42, 15, 18, 180))
            elif is_edited:
                item_exp.setBackground(QColor(10, 31, 38, 180))
            self.table.setItem(i, 8, item_exp)


        # Update Analytics — Revenue − Expenses − COGS
        is_filtered = bool(query or dues_only)
        
        if is_filtered:
            # Cannot calculate strict Net Profit / Expenses for a filtered subset
            # because expenses are daily, not per-invoice.
            self.lbl_total_exp.setText("EXPENSES: N/A (Filtered)")
            self.lbl_net_profit.setText("NET PROFIT: N/A (Filtered)")
            self.lbl_net_profit.setStyleSheet(f"color: #888; font-size: 18px; font-weight: bold;")
        else:
            total_cogs = self.db_manager.get_total_cogs(d_from, d_to)
            net_profit = total_rev - total_exp_period - total_cogs
            self.lbl_total_exp.setText(f"EXPENSES: ₹ {total_exp_period:,.2f}")
            self.lbl_net_profit.setText(f"NET PROFIT: ₹ {net_profit:,.2f}")
            self.lbl_net_profit.setStyleSheet(f"color: {COLOR_ACCENT_CYAN}; font-size: 18px; font-weight: bold;")
            
        self.lbl_total_rev.setText(f"REVENUE: ₹ {total_rev:,.2f}")
        self.lbl_total_count.setText(f"COUNT: {len(rows)}")

        # Use dynamically calculated payment summary from visible rows
        self.lbl_pay_cash.setText(f"💵 CASH: ₹ {sum_cash:,.2f}")
        self.lbl_pay_upi.setText(f"📱 UPI: ₹ {sum_upi:,.2f}")
        
        due_lbl = f"⚠️ DUES: ₹ {sum_due:,.2f}"
        if count_due > 0:
            due_lbl += f" ({count_due} invoices)"
        self.lbl_pay_due.setText(due_lbl)
        
        self.lbl_pay_due.setStyleSheet(
            "color: #ff4444; font-size: 13px; font-weight: bold;"
            if sum_due > 0 else
            "color: #00ff88; font-size: 13px; font-weight: bold;"
        )

    def toggle_select_all(self):
        checked = self.btn_select_all.isChecked()
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self.btn_select_all.setText("❌ Unselect All" if checked else "✅ Select All")
        
        for row in range(self.table.rowCount()):
            cw = self.table.cellWidget(row, 0)
            if cw:
                chk = cw.findChild(QCheckBox)
                if chk:
                    chk.setChecked(checked)

    def open_pdf(self, invoice_id):
        from path_utils import get_app_data_path  # type: ignore
        pdf_path = get_app_data_path(os.path.join("invoices", f"{invoice_id}.pdf"))
        
        # ── ALWAYS regenerate from DB source-of-truth before opening ──
        try:
            from invoice_generator import InvoiceGenerator
            ig = InvoiceGenerator(self.db_manager)
            ig.regenerate_invoice(invoice_id)
        except PermissionError:
            from custom_components import ProMessageBox
            ProMessageBox.warning(self, "PDF Locked", "The PDF is currently open in your browser.\nPlease close the browser tab displaying the invoice first, then click 'View' again so the app can rewrite it.")
            return
        except Exception as e:
            import logging
            logging.getLogger("app").error(f"Error regenerating PDF before view: {e}")
            
        if os.path.exists(pdf_path):
            try:
                os.startfile(pdf_path)
            except Exception as e:
                ProMessageBox.warning(self, "Error", f"Could not open PDF: {e}")
        else:
            ProMessageBox.warning(self, "Not Found", f"Invoice PDF not found:\n{pdf_path}")

    def open_return_dialog(self, invoice_id):
        """Open the return dialog for the selected invoice"""
        dialog = ReturnDialog(self.db_manager, invoice_id, self)
        if dialog.exec():
            # Refresh data if return was processed
            self.load_data()

    def export_to_excel(self, selection_only=False):
        # Allow exporting the currently filtered view or selection
        d_from = self.date_from.date().toString("yyyy-MM-dd")
        d_to = self.date_to.date().toString("yyyy-MM-dd")
        query = self.search_in.text().strip()
        
        if selection_only:
            inv_ids = []
            for row in range(self.table.rowCount()):
                cw = self.table.cellWidget(row, 0)
                chk = cw.findChild(QCheckBox) if cw else None
                if chk and chk.isChecked():
                    # Invoice ID is in column 2 (index 2 because Column 0 is check, 1 is date)
                    inv_id = str(self.table.item(row, 2).text()).split(' ')[0]
                    inv_ids.append(inv_id)
            
            if not inv_ids:
                ProMessageBox.warning(self, "No Selection", "Please check the boxes in the table first.")
                return
            
            # Fetch specific invoices
            rows = []
            all_rows = self.db_manager.get_sales_report(d_from, d_to, query)
            for r in all_rows:
                if str(r[1]) in inv_ids:
                    rows.append(r)
        else:
            rows = self.db_manager.get_sales_report(d_from, d_to, query)
        
        if not rows:
            ProMessageBox.information(self, "Empty", "No data to export.")
            return

        try:
            import pandas as pd
            # Columns: date, invoice_id, customer_name, items_count, total_amount, json_items, invoice_id
            data = []
            for r in rows:
                json_str = r[5]
                items_cnt = r[3]
                labour_charge = 0.0
                
                try:
                    items_data = json.loads(json_str)
                    # Support both list and dict-with-cart formats
                    cart = []
                    if isinstance(items_data, list):
                        cart = items_data
                    elif isinstance(items_data, dict):
                        cart = items_data.get('cart', [])
                    
                    # Recalculate items count if it's 0 (historical data)
                    calc_cnt = sum(item.get('qty', 0) for item in cart)
                    if items_cnt == 0:
                         items_cnt = calc_cnt
                    
                    # Calculate Labour Charge: items with 'SERVICE' or 'LABOUR' in name
                    for x in cart:
                        nm = str(x.get('name', '')).upper()
                        if "SERVICE" in nm or "LABOUR" in nm:
                            labour_charge += x.get('total', 0.0)
                            
                except:
                    pass # Fallback to original values if JSON fails
                
                data.append({
                    "Date": r[0],
                    "Invoice ID": r[1],
                    "Customer": r[2],
                    "Items Count": items_cnt,
                    "Labour Charge": labour_charge,
                    "Total Amount": r[4],
                    "Refund": r[12] if len(r) > 12 and r[12] else 0.0,
                    "Revenue": float(r[4] or 0.0) - float(r[12] if len(r) > 12 and r[12] else 0.0)
                })
            
            df = pd.DataFrame(data)
            
            fname, _ = QFileDialog.getSaveFileName(self, "Export Sales Report", f"Sales_Report_{d_from}_to_{d_to}.xlsx", "Excel Files (*.xlsx)")
            if fname:
                df.to_excel(fname, index=False)
                ProMessageBox.information(self, "Success", f"Exported {len(rows)} records to Excel.")
                
        except Exception as e:
            ProMessageBox.critical(self, "Export Error", str(e))
            
    def export_to_pdf(self, selection_only=False):
        """Export current filtered report data to professional PDF"""
        try:
            d_from = self.date_from.date().toString("yyyy-MM-dd")
            d_to = self.date_to.date().toString("yyyy-MM-dd")
            query = self.search_in.text().strip()
            
            # 1. Fetch data
            if selection_only:
                inv_ids = []
                for row in range(self.table.rowCount()):
                    cw = self.table.cellWidget(row, 0)
                    chk = cw.findChild(QCheckBox) if cw else None
                    if chk and chk.isChecked():
                        inv_id = str(self.table.item(row, 2).text()).split(' ')[0]
                        inv_ids.append(inv_id)

                if not inv_ids:
                    ProMessageBox.warning(self, "No Selection", "Please check the boxes in the table first.")
                    return
                
                all_rows = self.db_manager.get_sales_report(d_from, d_to, query)
                rows = [r for r in all_rows if str(r[1]) in inv_ids]
            else:
                rows = self.db_manager.get_sales_report(d_from, d_to, query)

            if not rows:
                ProMessageBox.information(self, "Empty", "No data to export.")
                return
                
            # 2. Calculate Revenue & Expenses
            total_rev = sum((float(r[4]) if r[4] else 0.0) - (float(r[12]) if len(r) > 12 and r[12] else 0.0) for r in rows)
            
            # Fetch expenses for the same period to show in summary
            expense_map = self.db_manager.get_expenses_by_day(d_from, d_to)
            total_exp = sum(expense_map.values()) if expense_map else 0.0
            
            # Fetch total COGS
            total_cogs = self.db_manager.get_total_cogs(d_from, d_to)
            
            total_net = total_rev - total_exp - total_cogs
            
            # 3. Generate PDF
            gen = ReportGenerator(self.db_manager)
            success, result = gen.generate_sales_report_pdf(rows, total_rev, total_exp, total_net, total_cogs, d_from, d_to)
            
            if success:
                ans = ProMessageBox.question(self, "Success", f"Sales Report PDF generated successfully.\nLocation: {result}\n\nDo you want to share this report via WhatsApp?")
                if ans:
                    try:
                        settings = self.db_manager.get_shop_settings()
                        shop_name = settings.get("shop_name", "SpareParts Pro")
                    except: shop_name = "SpareParts Pro"
                    send_report_msg("Sales Report", shop_name)
                    try: os.startfile(os.path.dirname(result))
                    except: pass
                    ProMessageBox.information(self, "WhatsApp", "Please attach the PDF manually into the chat once WhatsApp Web opens.")
                else:
                    try: os.startfile(result)
                    except: pass
            else:
                ProMessageBox.critical(self, "PDF Error", f"Failed to generate PDF: {result}")
                
        except Exception as e:
            app_logger.error(f"Export PDF Error: {e}")
            ProMessageBox.critical(self, "Export Error", str(e))

    def export_comprehensive_report(self):
        """Export a comprehensive report — respects checkbox selection.
        If rows are checked → report only for those invoices.
        If nothing is checked → full date-range report.
        """
        try:
            d_from = self.date_from.date().toString("yyyy-MM-dd")
            d_to   = self.date_to.date().toString("yyyy-MM-dd")
            query  = self.search_in.text().strip()

            # --- Check for checkbox selection ---
            selected_ids = []
            for row in range(self.table.rowCount()):
                cw = self.table.cellWidget(row, 0)
                chk = cw.findChild(QCheckBox) if cw else None
                if chk and chk.isChecked():
                    inv_id = str(self.table.item(row, 2).text()).split(' ')[0]
                    selected_ids.append(inv_id)

            # 1. Fetch sales data
            all_sales = self.db_manager.get_sales_report(d_from, d_to, query)

            if selected_ids:
                # Selection mode — filter to only checked invoices
                sales_data = [r for r in all_sales if str(r[1]) in selected_ids]
                report_label = f"Selected {len(selected_ids)} Invoice(s)"
            else:
                # Full mode — all invoices in the date range
                sales_data = all_sales
                report_label = "Full Date Range"

            # 2. Fetch individual expenses (always full range — expenses aren't invoice-specific)
            expense_data = self.db_manager.get_all_expenses(d_from, d_to)

            if not sales_data and not expense_data:
                ProMessageBox.information(self, "Empty", "No sales or expenses found for the selected scope.")
                return

            # 3. Totals
            total_rev  = sum((float(r[4]) if r[4] else 0.0) - (float(r[12]) if len(r) > 12 and r[12] else 0.0) for r in sales_data)
            total_exp  = sum(float(r[2]) if r[2] else 0.0 for r in expense_data)
            total_cogs = self.db_manager.get_total_cogs(d_from, d_to)
            total_net  = total_rev - total_exp - total_cogs

            # 4. Generate PDF
            gen = ReportGenerator(self.db_manager)
            success, result = gen.generate_comprehensive_report_pdf(
                sales_data, expense_data, total_rev, total_exp, total_net, total_cogs, d_from, d_to
            )

            if success:
                ans = ProMessageBox.question(
                    self, "Success",
                    f"Comprehensive Report ({report_label}) generated successfully.\n"
                    f"Location: {result}\n\nDo you want to share this report via WhatsApp?"
                )
                if ans:
                    try:
                        settings = self.db_manager.get_shop_settings()
                        shop_name = settings.get("shop_name", "SpareParts Pro")
                    except:
                        shop_name = "SpareParts Pro"
                    send_report_msg("Comprehensive Report", shop_name)
                    try: os.startfile(os.path.dirname(result))
                    except: pass
                    ProMessageBox.information(self, "WhatsApp", "Please attach the PDF manually into the chat once WhatsApp Web opens.")
                else:
                    try: os.startfile(result)
                    except: pass
            else:
                ProMessageBox.critical(self, "PDF Error", f"Failed to generate report: {result}")

        except Exception as e:
            app_logger.error(f"Comprehensive Report Error: {e}")
            ProMessageBox.critical(self, "Export Error", str(e))

    def export_daily_report(self):
        """Generates a summary daily report grouping sales by date"""
        try:
            d_from = self.date_from.date().toString("yyyy-MM-dd")
            d_to = self.date_to.date().toString("yyyy-MM-dd")
            query = self.search_in.text().strip()
            
            # 1. Fetch full data for the period
            rows = self.db_manager.get_sales_report(d_from, d_to, query)
            if not rows:
                ProMessageBox.information(self, "Empty", "No data to summarize.")
                return
                
            # 2. Calculate Total Revenue
            total_rev = sum((float(r[4]) if r[4] else 0.0) - (float(r[12]) if len(r) > 12 and r[12] else 0.0) for r in rows)
            
            # 3. Fetch Expenses for the period
            expense_data = self.db_manager.get_expenses_by_day(d_from, d_to)
            
            # Fetch total COGS
            total_cogs = self.db_manager.get_total_cogs(d_from, d_to)
            
            # 4. Generate Daily PDF
            gen = ReportGenerator(self.db_manager)
            success, result = gen.generate_daily_sales_report_pdf(rows, expense_data, total_rev, total_cogs, d_from, d_to)
            
            if success:
                ans = ProMessageBox.question(self, "Success", f"Daily Summary Report generated.\nLocation: {result}\n\nDo you want to share this report via WhatsApp?")
                if ans:
                    try:
                        settings = self.db_manager.get_shop_settings()
                        shop_name = settings.get("shop_name", "SpareParts Pro")
                    except: shop_name = "SpareParts Pro"
                    send_report_msg("Daily Sales Report", shop_name)
                    try: os.startfile(os.path.dirname(result))
                    except: pass
                    ProMessageBox.information(self, "WhatsApp", "Please attach the PDF manually into the chat once WhatsApp Web opens.")
                else:
                    try: os.startfile(result)
                    except: pass
            else:
                ProMessageBox.critical(self, "PDF Error", result)
                
        except Exception as e:
            app_logger.error(f"Daily Report Error: {e}")
            ProMessageBox.critical(self, "Error", str(e))

    def open_config_dialog(self):
        # Re-use existing config dialog logic or simplified
        # For brevity, implementing the password check and dialog open
        dialog = QDialog(self)
        # 1. Ask for Password - Securely
        text, ok = QInputDialog.getText(self, "Security Check", "Enter Admin Password:", QLineEdit.EchoMode.Password)
        
        if ok and text:
            # 2. Hash Input
            input_hash = hashlib.sha256(text.encode()).hexdigest()
            # Hash for 'Chandni@96'
            TARGET_HASH = "c08d268b730facf88cbbb892a25fc697f384a06f854114fd6310ca8f0cc6f6cd"
            
            if input_hash == TARGET_HASH:
                dlg = ShopBrandingDialog(self.db_manager, self)
                if dlg.exec():
                    self.load_data() # Refresh if needed
            else:
                ProMessageBox.warning(self, "Access Denied", "Incorrect Password!")
