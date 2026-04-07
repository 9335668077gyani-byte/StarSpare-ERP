"""
catalog_page.py — Nexses eCatalog Browser (ERP Page)
=====================================================
A faithful port of Nexses_eCatalog/ui_layout.py embedded as a QWidget
inside spare_ERP's main navigation at index 8.

All AI-engine references have been removed.
The SyncWorker calls the same api_sync_engine.run_sync() used in the
original standalone app.

Layout mirrors the original:
    Left  : Filter tree  (Brand → Segment → Series → Model)
    Center: QTabWidget
               Tab 1 – Catalog View  (parts table + supporting vehicles)
               Tab 2 – Common Parts  (analyzer)
               Tab 3 – Data Sync     (CSV import + TVS API sync)
"""

import os
import csv
import ui_theme

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QFrame, QSplitter, QTreeWidget, QTreeWidgetItem, QTabWidget,
    QProgressBar, QTextEdit, QSizePolicy, QComboBox, QDoubleSpinBox,
    QGroupBox, QFileDialog, QMenu, QApplication,
    QDialog, QDialogButtonBox, QFormLayout,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QBrush, QFont, QAction

# ─────────────────────────────────────────────────────────────────────────────
# Settings
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# Helper — open catalog DB (returns None if not found)
# ─────────────────────────────────────────────────────────────────────────────
def _open_catalog_db(db_path: str):
    import sqlite3
    if db_path and os.path.isfile(db_path):
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            return conn
        except Exception:
            pass
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Background workers
# ─────────────────────────────────────────────────────────────────────────────

class SyncWorker(QThread):
    """Runs the full TVS API sync engine in background (same as original)."""
    progress     = pyqtSignal(str)
    progress_pct = pyqtSignal(int, str)
    finished     = pyqtSignal(dict)
    error        = pyqtSignal(str)

    def __init__(self, db_path: str, category: str = None, series_id: str = None, dealer_id: str = "63050"):
        super().__init__()
        self.db_path   = db_path
        self.category  = category
        self.series_id = series_id
        self.dealer_id = dealer_id
        self._stopped  = False

    def stop(self):
        self._stopped = True

    def run(self):
        try:
            from api_sync_engine import run_sync
            import api_sync_engine as ase
            original_log = ase.log

            def ui_log(msg, level="INFO"):
                original_log(msg, level)
                self.progress.emit(f"[{level}] {msg}")

            ase.log = ui_log
            run_sync(
                db_path=self.db_path,
                dealer_id=self.dealer_id,
                target_category=self.category,
                target_series=self.series_id,
                progress_callback=lambda pct, msg: self.progress_pct.emit(pct, msg),
            )
            ase.log = original_log
            self.finished.emit({"status": "complete"})
        except Exception as e:
            self.error.emit(str(e))


class ModelFetchWorker(QThread):
    """Fetches available models for a given category from TVS API."""
    finished = pyqtSignal(list)
    error    = pyqtSignal(str)

    def __init__(self, category_name: str, dealer_id: str = "63050"):
        super().__init__()
        self.category_name = category_name
        self.dealer_id     = dealer_id

    def run(self):
        try:
            from api_sync_engine import TVSApiClient, _force_dict, _safe_str
            client = TVSApiClient(dealer_id=self.dealer_id)
            if not client.connect():
                self.error.emit("Failed to authenticate with TVS API.")
                return
            cats = client.get_categories()
            cat_id = None
            if cats:
                for c in cats:
                    c = _force_dict(c)
                    name = _safe_str(c.get("name") or c.get("CATEGORY_NAME") or "")
                    if name.strip().upper() == self.category_name.strip().upper():
                        cat_id = str(c.get("CATEGORY_ID") or c.get("categoryId") or "")
                        break
            if not cat_id:
                self.error.emit(f"Category '{self.category_name}' not found.")
                return
            models = client.get_models_by_category(cat_id)
            result = []
            if models:
                for m in models:
                    m = _force_dict(m)
                    name = _safe_str(
                        m.get("DESCRIPTION") or m.get("name") or
                        m.get("SERIES_NAME") or m.get("MODEL_NAME") or "Unknown"
                    )
                    sid = str(m.get("series") or m.get("SERIES") or
                               m.get("SERIES_ID") or "")
                    if sid:
                        result.append({"name": name, "series": sid})
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


# ─────────────────────────────────────────────────────────────────────────────
# Qty Entry Dialog — shown when a part is checked into the PO cart
# ─────────────────────────────────────────────────────────────────────────────

class QtyEntryDialog(QDialog):
    """
    Modal dialog shown whenever a part is ticked into the PO cart.
    Collects: required quantity, rack number, column number.
    """
    def __init__(self, part_code: str, description: str,
                 current_stock: int = 0, reorder_level: int = 0,
                 current_rack: str = "", current_col: str = "",
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("🛒  Add to Purchase Order")
        self.setMinimumWidth(440)
        self.setModal(True)
        self.setStyleSheet("""
            QDialog {
                background-color: #0b0e18;
                color: #e2e8f0;
                border: 1px solid rgba(0,242,255,0.25);
                border-radius: 8px;
            }
            QLabel { color: #94a3b8; font-size: 12px; font-family: 'Segoe UI'; }
            QLabel#title { color: #00f2ff; font-size: 15px; font-weight: 700; }
            QLabel#code  { color: #60a5fa; font-size: 13px; font-weight: 700; }
            QLabel#desc  { color: #cbd5e1; font-size: 12px; font-style: italic; }
            QLabel#stock { color: #4ade80; font-size: 12px; }
            QDoubleSpinBox, QLineEdit {
                background: #141928;
                color: #00f2ff;
                border: 1px solid rgba(0,242,255,0.30);
                border-radius: 4px;
                padding: 5px 8px;
                font-size: 13px;
                font-weight: 700;
            }
            QDoubleSpinBox:focus, QLineEdit:focus {
                border: 1px solid #00f2ff;
                background: #0e1420;
            }
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #0ea5e9, stop:1 #0284c7);
                color: white;
                border: none;
                border-radius: 5px;
                padding: 7px 20px;
                font-size: 13px;
                font-weight: 700;
            }
            QPushButton:hover { background: #38bdf8; }
            QPushButton[text="Cancel"] {
                background: rgba(255,255,255,0.05);
                color: #94a3b8;
                border: 1px solid rgba(255,255,255,0.10);
            }
            QPushButton[text="Cancel"]:hover {
                background: rgba(255,255,255,0.10);
                color: #e2e8f0;
            }
        """)

        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(20, 18, 20, 18)

        # Header
        hdr = QLabel("Add Part to Purchase Order")
        hdr.setObjectName("title")
        root.addWidget(hdr)

        lbl_code = QLabel(part_code)
        lbl_code.setObjectName("code")
        root.addWidget(lbl_code)

        lbl_desc = QLabel(description[:80] + ("..." if len(description) > 80 else ""))
        lbl_desc.setObjectName("desc")
        lbl_desc.setWordWrap(True)
        root.addWidget(lbl_desc)

        # Stock info
        stock_txt = f"Current Stock: {current_stock}  |  Reorder Level: {reorder_level}"
        lbl_stock = QLabel(stock_txt)
        lbl_stock.setObjectName("stock")
        root.addWidget(lbl_stock)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background: rgba(0,242,255,0.12); max-height:1px;")
        root.addWidget(sep)

        # Form fields
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.spin_qty = QDoubleSpinBox()
        self.spin_qty.setRange(1, 9999)
        self.spin_qty.setValue(max(1, reorder_level - current_stock) if reorder_level > current_stock else 1)
        self.spin_qty.setFixedHeight(36)
        self.spin_qty.selectAll()
        form.addRow("Req. Quantity *", self.spin_qty)

        self.in_rack = QLineEdit(current_rack)
        self.in_rack.setPlaceholderText("e.g. A, B, C ...")
        self.in_rack.setFixedHeight(34)
        form.addRow("Rack / Row", self.in_rack)

        self.in_col = QLineEdit(current_col)
        self.in_col.setPlaceholderText("e.g. 1, 2, 3 ...")
        self.in_col.setFixedHeight(34)
        form.addRow("Column / Shelf", self.in_col)

        root.addLayout(form)

        # Buttons
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        root.addWidget(btn_box)

        # Focus qty immediately
        self.spin_qty.setFocus()

    def get_qty(self) -> int:
        return self.spin_qty.value()

    def get_rack(self) -> str:
        return self.in_rack.text().strip()

    def get_col(self) -> str:
        return self.in_col.text().strip()


# ─────────────────────────────────────────────────────────────────────────────
# Main page widget
# ─────────────────────────────────────────────────────────────────────────────

class CatalogPage(QWidget):
    """
    Nexses eCatalog embedded as an ERP page.
    Receives db_manager (for settings) but its own catalog DB path is
    configured in Settings → AI ENGINE → TVS ECATALOG → Catalog DB.
    """

    def __init__(self, db_manager):
        super().__init__()
        self.db_manager  = db_manager
        self._catalog_db = ""
        self._dealer_id  = "63050"
        self._branch_id  = 1
        self._sync_worker = None
        self._model_worker = None
        self.selected_parts = {}  # Cart tracker: part_code -> dict
        self._load_settings()
        self._build_ui()
        # Populate filter tree after window is shown
        QTimer.singleShot(200, self._populate_filter_tree)

    # ── Settings ─────────────────────────────────────────────────────────────
    def _load_settings(self):
        s = self.db_manager.get_shop_settings() or {}
        
        cat_db = s.get("nexses_catalog_db", "")
        if not cat_db or not os.path.exists(cat_db):
            from path_utils import get_resource_path  # type: ignore
            cat_db = get_resource_path("nexses_ecatalog.db")
            if not os.path.exists(cat_db):
                try:
                    import db_engine
                    db_engine.initialize_database(cat_db)
                except Exception as e:
                    print(f"[catalog_page] Error initializing catalog DB: {e}")
            try:
                self.db_manager.update_setting("nexses_catalog_db", cat_db)
            except Exception:
                pass

        self._catalog_db = cat_db
        self._dealer_id  = s.get("tvs_dealer_id", "63050")
        try:
            self._branch_id = int(s.get("tvs_branch_id", "1"))
        except ValueError:
            self._branch_id = 1

    def load_data(self):
        """Called by F5 / main_window refresh."""
        self._load_settings()
        self._populate_filter_tree()

    # ── UI Build ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── TOP BAR ──────────────────────────────────────────────────────────
        top = QFrame()
        top.setFixedHeight(60)
        top.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            " stop:0 #03060c, stop:1 #010206);"
            " border-bottom: 1px solid rgba(0,242,255,0.15);"
        )
        tl = QHBoxLayout(top)
        tl.setContentsMargins(18, 8, 18, 8)
        tl.setSpacing(12)

        title = QLabel("🗂  NEXSES eCATALOG")
        title.setStyleSheet(
            "color: #00f2ff;"
            " font-size: 17px;"
            " font-weight: 800;"
            " letter-spacing: 3px;"
            " font-family: 'Segoe UI Semibold', 'Segoe UI', sans-serif;"
            " background: transparent;"
        )
        tl.addWidget(title)
        tl.addStretch(1)

        # Search bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔍  Search by Part Code or Description...")
        self.search_bar.setClearButtonEnabled(True)
        self.search_bar.setMinimumWidth(380)
        self.search_bar.setFixedHeight(38)
        self.search_bar.setStyleSheet(
            ui_theme.get_lineedit_style() + " QLineEdit { border-radius: 19px; padding-left: 16px; }"
        )
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._on_search)
        self.search_bar.textChanged.connect(
            lambda: self._search_timer.start()
        )
        tl.addWidget(self.search_bar)
        tl.addStretch(1)

        # DB badge
        self.lbl_db = QLabel()
        self._refresh_db_badge()
        tl.addWidget(self.lbl_db)
        tl.addSpacing(12)
        
        # Make PO Cart Button
        self.btn_cart = QPushButton("🛒  Make PO (0)")
        from ui_theme import get_neon_action_button
        self.btn_cart.setStyleSheet(get_neon_action_button())
        self.btn_cart.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cart.setFixedHeight(36)
        self.btn_cart.clicked.connect(self._make_po_from_cart)
        tl.addWidget(self.btn_cart)
        
        root.addWidget(top)

        # ── BODY: filter tree | center tabs ──────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background: rgba(0,242,255,0.10); }")

        # LEFT: filter tree
        left = QWidget()
        left.setObjectName("leftPanel")
        left.setMinimumWidth(230)
        left.setMaximumWidth(320)
        left.setStyleSheet("background:#010206;")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(0)

        filter_hdr = QLabel("  ⚙  FILTER BY VEHICLE")
        filter_hdr.setStyleSheet(
            "background: #03060c;"
            " color: #64748B;"
            " font-weight: 700;"
            " font-size: 10px;"
            " letter-spacing: 2px;"
            " padding: 10px 14px;"
            " border-bottom: 1px solid rgba(0,242,255,0.12);"
            " font-family: 'Segoe UI', sans-serif;"
        )
        ll.addWidget(filter_hdr)

        self.filter_tree = QTreeWidget()
        self.filter_tree.setHeaderHidden(True)
        self.filter_tree.setAnimated(True)
        self.filter_tree.setIndentation(18)
        self.filter_tree.setStyleSheet(ui_theme.get_tree_style())
        self.filter_tree.itemClicked.connect(self._on_tree_item_clicked)
        ll.addWidget(self.filter_tree)
        splitter.addWidget(left)

        # CENTER: tab widget
        self.center_tabs = QTabWidget()
        self.center_tabs.setObjectName("centerTabs")
        self.center_tabs.setDocumentMode(False)
        self.center_tabs.setStyleSheet(ui_theme.get_tab_style())
        self._build_tab_catalog()
        self._build_tab_analyzer()
        self._build_tab_all_parts()
        self._build_tab_sync()
        splitter.addWidget(self.center_tabs)
        splitter.setSizes([260, 1100])

        root.addWidget(splitter, 1)

        # ── STATUS BAR ───────────────────────────────────────────────────────
        status_bar = QFrame()
        status_bar.setFixedHeight(28)
        status_bar.setStyleSheet(
            "background: #03060c;"
            " border-top: 1px solid rgba(0,242,255,0.10);"
        )
        sl = QHBoxLayout(status_bar)
        sl.setContentsMargins(14, 0, 14, 0)
        self.lbl_status = QLabel("Ready")
        self.lbl_status.setStyleSheet(
            "color: #475569; font-size: 11px;"
            " font-family: 'Segoe UI', sans-serif;"
        )
        sl.addWidget(self.lbl_status)
        sl.addStretch()
        self.lbl_count = QLabel("")
        self.lbl_count.setStyleSheet(
            "color: #00f2ff; font-size: 11px; font-weight: 700;"
            " background: rgba(0,242,255,0.08);"
            " border: 1px solid rgba(0,242,255,0.20);"
            " border-radius: 10px; padding: 1px 10px;"
        )
        sl.addWidget(self.lbl_count)
        root.addWidget(status_bar)

    # ── Tab 1: Catalog View ───────────────────────────────────────────────────
    def _build_tab_catalog(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(0, 0, 0, 0)

        catalog_splitter = QSplitter(Qt.Orientation.Vertical)

        # Parts table
        self.data_table = QTableWidget()
        self.data_table.setStyleSheet(ui_theme.get_table_style())
        self.data_table.setAlternatingRowColors(True)
        self.data_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.data_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.data_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.data_table.setSortingEnabled(True)
        self.data_table.verticalHeader().setVisible(False)
        cols = ["SEL", "Part Code", "Description", "Category", "MRP (₹)", "NDP (₹)", "MOQ", "Remarks"]
        self.data_table.setColumnCount(len(cols))
        self.data_table.setHorizontalHeaderLabels(cols)
        hdr = self.data_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(6, QHeaderView.ResizeMode.Interactive)
        hdr.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        self.data_table.setColumnWidth(0, 50)
        self.data_table.setColumnWidth(1, 150)
        self.data_table.setColumnWidth(3, 120)
        self.data_table.setColumnWidth(4, 90)
        self.data_table.setColumnWidth(5, 90)
        self.data_table.setColumnWidth(6, 60)
        self.data_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.data_table.customContextMenuRequested.connect(self._show_context_menu)
        self.data_table.itemSelectionChanged.connect(self._on_part_selected)
        self.data_table.itemChanged.connect(self._on_cart_checkbox_toggled_data_table)
        catalog_splitter.addWidget(self.data_table)

        # Supporting vehicles table
        self.vehicles_table = QTableWidget()
        self.vehicles_table.setStyleSheet(ui_theme.get_table_style())
        self.vehicles_table.setAlternatingRowColors(True)
        self.vehicles_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.vehicles_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.vehicles_table.setSortingEnabled(True)
        self.vehicles_table.verticalHeader().setVisible(False)
        vh_cols = ["Brand", "Segment", "Series", "Model", "Variant"]
        self.vehicles_table.setColumnCount(len(vh_cols))
        self.vehicles_table.setHorizontalHeaderLabels(vh_cols)
        vh_hdr = self.vehicles_table.horizontalHeader()
        for i in range(len(vh_cols) - 1):
            vh_hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
        vh_hdr.setSectionResizeMode(len(vh_cols) - 1, QHeaderView.ResizeMode.Stretch)
        catalog_splitter.addWidget(self.vehicles_table)
        catalog_splitter.setSizes([500, 260])

        lay.addWidget(catalog_splitter)
        self.center_tabs.addTab(tab, "🏷️ Catalog View")

    # ── Tab 2: Common Parts Analyzer ─────────────────────────────────────────
    def _build_tab_analyzer(self):
        tab = QWidget()
        tab.setStyleSheet("background: #010206;")
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(12, 12, 12, 8)
        lay.setSpacing(10)

        ctrl = QHBoxLayout()
        ctrl.setSpacing(10)

        lbl_min = QLabel("Min Vehicles:")
        lbl_min.setStyleSheet("color: #64748B; font-size: 12px; font-family: 'Segoe UI';")
        ctrl.addWidget(lbl_min)

        self.min_vehicles_spin = QDoubleSpinBox()
        self.min_vehicles_spin.setRange(2, 500)
        self.min_vehicles_spin.setValue(2)
        self.min_vehicles_spin.setFixedHeight(34)
        self.min_vehicles_spin.setStyleSheet(ui_theme.get_spinbox_style())
        ctrl.addWidget(self.min_vehicles_spin)

        lbl_cat = QLabel("Category:")
        lbl_cat.setStyleSheet("color: #64748B; font-size: 12px; font-family: 'Segoe UI';")
        ctrl.addWidget(lbl_cat)

        self.category_combo_analyzer = QComboBox()
        self.category_combo_analyzer.addItem("All Categories")
        self.category_combo_analyzer.setMinimumWidth(160)
        self.category_combo_analyzer.setFixedHeight(34)
        self.category_combo_analyzer.setStyleSheet(ui_theme.get_combobox_style())
        ctrl.addWidget(self.category_combo_analyzer)

        btn_load = QPushButton("🔄  Load Common Parts")
        btn_load.setStyleSheet(ui_theme.get_neon_action_button())
        btn_load.setFixedHeight(34)
        btn_load.clicked.connect(self._on_load_common_parts)
        ctrl.addWidget(btn_load)

        btn_export = QPushButton("📥  Export CSV")
        btn_export.setStyleSheet(ui_theme.get_ghost_button_style())
        btn_export.setFixedHeight(34)
        btn_export.clicked.connect(self._on_export_common_parts)
        ctrl.addWidget(btn_export)
        ctrl.addStretch()
        lay.addLayout(ctrl)

        analyzer_splitter = QSplitter(Qt.Orientation.Vertical)
        analyzer_splitter.setHandleWidth(1)
        analyzer_splitter.setStyleSheet("QSplitter::handle { background: rgba(0,242,255,0.10); }")

        self.common_parts_table = QTableWidget()
        self.common_parts_table.setStyleSheet(ui_theme.get_table_style())
        self.common_parts_table.setAlternatingRowColors(True)
        self.common_parts_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.common_parts_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.common_parts_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.common_parts_table.setSortingEnabled(True)
        self.common_parts_table.verticalHeader().setVisible(False)
        cp_cols = ["SEL", "Part Code", "Description", "Category", "Vehicle Count", "MRP (₹)"]
        self.common_parts_table.setColumnCount(len(cp_cols))
        self.common_parts_table.setHorizontalHeaderLabels(cp_cols)
        cp_hdr = self.common_parts_table.horizontalHeader()
        cp_hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.common_parts_table.setColumnWidth(0, 50)
        cp_hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.common_parts_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.common_parts_table.customContextMenuRequested.connect(self._show_common_context_menu)
        self.common_parts_table.itemSelectionChanged.connect(self._on_common_part_selected)
        self.common_parts_table.itemChanged.connect(self._on_cart_checkbox_toggled_common_table)
        analyzer_splitter.addWidget(self.common_parts_table)

        self.common_vehicles_table = QTableWidget()
        self.common_vehicles_table.setStyleSheet(ui_theme.get_table_style())
        self.common_vehicles_table.setAlternatingRowColors(True)
        self.common_vehicles_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.common_vehicles_table.verticalHeader().setVisible(False)
        cv_cols = ["Brand", "Segment", "Series", "Model", "Variant"]
        self.common_vehicles_table.setColumnCount(len(cv_cols))
        self.common_vehicles_table.setHorizontalHeaderLabels(cv_cols)
        cv_hdr = self.common_vehicles_table.horizontalHeader()
        cv_hdr.setSectionResizeMode(len(cv_cols) - 1, QHeaderView.ResizeMode.Stretch)
        analyzer_splitter.addWidget(self.common_vehicles_table)
        analyzer_splitter.setSizes([400, 250])
        lay.addWidget(analyzer_splitter, 1)
        self.center_tabs.addTab(tab, "📊 Common Parts")

    # ── Tab 3: All Parts Browser ──────────────────────────────────────────────
    def _build_tab_all_parts(self):
        tab = QWidget()
        tab.setStyleSheet("background: #010206;")
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(12, 12, 12, 8)
        lay.setSpacing(10)

        # ── Filter bar: Single-row ultra-compact layout ────────────────────────
        filter_container = QWidget()
        filter_container.setStyleSheet(
            "background: rgba(255,255,255,0.02);"
            "border: 1px solid rgba(0,242,255,0.08);"
            "border-radius: 6px;"
        )
        # We use a single horizontal layout for everything
        fc_lay = QHBoxLayout(filter_container)
        fc_lay.setContentsMargins(10, 6, 10, 6)
        fc_lay.setSpacing(10)

        COMBO_W  = 130   # compact fixed width
        COMBO_H  = 30
        COMBO_SS = ui_theme.get_combobox_style()

        def _style_combo(combo):
            combo.setFixedWidth(COMBO_W)
            combo.setFixedHeight(COMBO_H)
            combo.setStyleSheet(COMBO_SS)

        # 1. Vehicle
        self.all_parts_veh_combo = QComboBox()
        self.all_parts_veh_combo.addItem("All Vehicles")
        self.all_parts_veh_combo.currentTextChanged.connect(self._on_all_parts_veh_changed)
        _style_combo(self.all_parts_veh_combo)
        fc_lay.addWidget(self.all_parts_veh_combo)

        # 2. Model
        self.all_parts_mod_combo = QComboBox()
        self.all_parts_mod_combo.addItem("All Models")
        self.all_parts_mod_combo.currentTextChanged.connect(self._on_all_parts_mod_changed)
        _style_combo(self.all_parts_mod_combo)
        fc_lay.addWidget(self.all_parts_mod_combo)

        # 3. Color / SYN
        self.all_parts_color_combo = QComboBox()
        self.all_parts_color_combo.addItem("All Colors")
        self.all_parts_color_combo.currentTextChanged.connect(
            lambda: self._populate_all_parts_table()
        )
        _style_combo(self.all_parts_color_combo)
        fc_lay.addWidget(self.all_parts_color_combo)

        # 4. Category
        self.all_parts_cat_combo = QComboBox()
        self.all_parts_cat_combo.addItem("All Categories")
        self.all_parts_cat_combo.currentTextChanged.connect(
            lambda: self._populate_all_parts_table()
        )
        _style_combo(self.all_parts_cat_combo)
        fc_lay.addWidget(self.all_parts_cat_combo)

        # Search box
        self.all_parts_search = QLineEdit()
        self.all_parts_search.setPlaceholderText("🔍  Search code or description...")
        self.all_parts_search.setClearButtonEnabled(True)
        self.all_parts_search.setFixedHeight(COMBO_H)
        self.all_parts_search.setStyleSheet(ui_theme.get_lineedit_style())
        self._all_parts_timer = QTimer()
        self._all_parts_timer.setSingleShot(True)
        self._all_parts_timer.setInterval(300)
        self._all_parts_timer.timeout.connect(self._populate_all_parts_table)
        self.all_parts_search.textChanged.connect(lambda: self._all_parts_timer.start())
        fc_lay.addWidget(self.all_parts_search, 1)

        # Count label
        self.all_parts_count_lbl = QLabel("—")
        self.all_parts_count_lbl.setStyleSheet(
            "color: #38bdf8; font-size: 11px; font-weight: 600;"
            " font-family: 'Segoe UI'; padding: 0 5px;"
        )
        self.all_parts_count_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fc_lay.addWidget(self.all_parts_count_lbl)

        # Refresh Button
        btn_load = QPushButton("🔄 Refresh")
        btn_load.setStyleSheet(ui_theme.get_neon_action_button())
        btn_load.setFixedHeight(COMBO_H)
        btn_load.setFixedWidth(90)
        btn_load.clicked.connect(self._populate_all_parts_table)
        fc_lay.addWidget(btn_load)

        lay.addWidget(filter_container)



        # Vertical splitter: parts table (top) + supporting vehicles (bottom)
        ap_splitter = QSplitter(Qt.Orientation.Vertical)
        ap_splitter.setHandleWidth(1)
        ap_splitter.setStyleSheet("QSplitter::handle { background: rgba(0,242,255,0.10); }")

        # ── Parts table ───────────────────────────────────────────────────────
        self.all_parts_table = QTableWidget()
        self.all_parts_table.setStyleSheet(ui_theme.get_table_style())
        self.all_parts_table.setAlternatingRowColors(True)
        self.all_parts_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.all_parts_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.all_parts_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.all_parts_table.setSortingEnabled(True)
        self.all_parts_table.verticalHeader().setVisible(False)
        ap_cols = ["SEL", "PART CODE", "Description", "Category", "MRP (₹)", "NDP (₹)", "MOQ", "Remarks"]
        self.all_parts_table.setColumnCount(len(ap_cols))
        self.all_parts_table.setHorizontalHeaderLabels(ap_cols)
        ap_hdr = self.all_parts_table.horizontalHeader()
        ap_hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        ap_hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        ap_hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        ap_hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        ap_hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        ap_hdr.setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)
        ap_hdr.setSectionResizeMode(6, QHeaderView.ResizeMode.Interactive)
        ap_hdr.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        self.all_parts_table.setColumnWidth(0, 50)
        self.all_parts_table.setColumnWidth(1, 150)
        self.all_parts_table.setColumnWidth(3, 130)
        self.all_parts_table.setColumnWidth(4, 90)
        self.all_parts_table.setColumnWidth(5, 90)
        self.all_parts_table.setColumnWidth(6, 60)
        self.all_parts_table.itemChanged.connect(self._on_cart_checkbox_toggled_all_parts)
        self.all_parts_table.itemSelectionChanged.connect(self._on_all_part_selected)
        ap_splitter.addWidget(self.all_parts_table)

        # ── Supporting vehicles table ─────────────────────────────────────────
        self.all_parts_vehicles_table = QTableWidget()
        self.all_parts_vehicles_table.setStyleSheet(ui_theme.get_table_style())
        self.all_parts_vehicles_table.setAlternatingRowColors(True)
        self.all_parts_vehicles_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.all_parts_vehicles_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.all_parts_vehicles_table.setSortingEnabled(True)
        self.all_parts_vehicles_table.verticalHeader().setVisible(False)
        apv_cols = ["Brand", "Segment", "Series", "Model", "Variant"]
        self.all_parts_vehicles_table.setColumnCount(len(apv_cols))
        self.all_parts_vehicles_table.setHorizontalHeaderLabels(apv_cols)
        apv_hdr = self.all_parts_vehicles_table.horizontalHeader()
        for i in range(len(apv_cols) - 1):
            apv_hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
        apv_hdr.setSectionResizeMode(len(apv_cols) - 1, QHeaderView.ResizeMode.Stretch)
        ap_splitter.addWidget(self.all_parts_vehicles_table)
        ap_splitter.setSizes([650, 180])

        lay.addWidget(ap_splitter, 1)




        self.center_tabs.addTab(tab, "📋 All Parts")
        self._all_parts_data = []  # cache

    # ── Tab 3: Data Sync ──────────────────────────────────────────────────────
    def _build_tab_sync(self):
        tab = QWidget()
        tab.setStyleSheet(f"background: {ui_theme.COLOR_BG};")
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(20)

        # ── CSV Import ────────────────────────────────────────────────────────
        csv_group = QGroupBox("📂 CSV / Excel Import")
        csv_group.setStyleSheet(ui_theme.get_groupbox_style())
        cg = QVBoxLayout(csv_group)
        cg.addWidget(QLabel("Import offline TVS parts master data from an Excel/CSV file."))
        btn_csv = QPushButton("📂  Select & Import CSV File")
        btn_csv.setFixedWidth(240)
        btn_csv.setStyleSheet(ui_theme.get_ghost_button_style())
        btn_csv.clicked.connect(self._on_import_csv)
        cg.addWidget(btn_csv)
        lay.addWidget(csv_group)

        # ── TVS API Sync ──────────────────────────────────────────────────────
        api_group = QGroupBox("☁️ TVS Advantage API Auto-Sync")
        api_group.setStyleSheet(ui_theme.get_groupbox_style())
        ag = QVBoxLayout(api_group)
        ag.setSpacing(14)

        # ═══════════════════════════════════════════════════════════════════════
        # ── SUB-PANEL A: SPARE PARTS SYNC ─────────────────────────────────────
        # ═══════════════════════════════════════════════════════════════════════
        spare_panel = QFrame()
        spare_panel.setStyleSheet(ui_theme.get_panel_frame_style(accent=True) + " QFrame { padding:10px; }")
        sp_lay = QVBoxLayout(spare_panel)
        sp_lay.setSpacing(8)

        spare_title = QLabel("🔧  SPARE PARTS SYNC")
        spare_title.setStyleSheet(
            "color:#38bdf8; font-weight:bold; font-size:13px;"
            " border:none; background:transparent;"
        )
        sp_lay.addWidget(spare_title)

        sp_desc = QLabel(
            "Select a vehicle category, then optionally pick a specific model.\n"
            "Leave model on 'ALL MODELS' to sync the entire category."
        )
        sp_desc.setStyleSheet("color:#64748b; font-size:11px; border:none; background:transparent;")
        sp_lay.addWidget(sp_desc)

        sp_row = QHBoxLayout()

        self.sync_category = QComboBox()
        self.sync_category.addItems(
            ["SELECT CATEGORY...", "MOPED", "MOTORCYCLE",
             "SCOOTER", "SCOOTY", "THREE WHEELER"]
        )
        self.sync_category.setStyleSheet(ui_theme.get_combobox_style())
        self.sync_category.setMinimumWidth(190)
        self.sync_category.currentTextChanged.connect(self._on_category_changed)
        sp_row.addWidget(self.sync_category)

        self.sync_model = QComboBox()
        self.sync_model.addItem("Select Model...")
        self.sync_model.setEnabled(False)
        self.sync_model.setStyleSheet(ui_theme.get_combobox_style())
        self.sync_model.setMinimumWidth(240)
        sp_row.addWidget(self.sync_model)

        self.sync_btn = QPushButton("🔄  Start Spare Parts Sync")
        self.sync_btn.setEnabled(False)
        self.sync_btn.setStyleSheet(ui_theme.get_neon_action_button())
        self.sync_btn.clicked.connect(self._on_sync_start)
        sp_row.addWidget(self.sync_btn)
        sp_row.addStretch()
        sp_lay.addLayout(sp_row)
        ag.addWidget(spare_panel)

        # ═══════════════════════════════════════════════════════════════════════
        # ── SUB-PANEL B: PAINTED PARTS SYNC ───────────────────────────────────
        # ═══════════════════════════════════════════════════════════════════════
        paint_panel = QFrame()
        paint_panel.setStyleSheet(ui_theme.get_panel_frame_style(accent=True) + " QFrame { padding:10px; border:1px solid #7c3aed; }")
        pp_lay = QVBoxLayout(paint_panel)
        pp_lay.setSpacing(8)

        paint_title = QLabel("🎨  PAINTED PARTS SYNC")
        paint_title.setStyleSheet(
            "color:#c084fc; font-weight:bold; font-size:13px;"
            " border:none; background:transparent;"
        )
        pp_lay.addWidget(paint_title)

        pp_desc = QLabel(
            "Fetch all body/painted parts per vehicle type.\n"
            "ALL color variants are synced automatically — resume-safe."
        )
        pp_desc.setStyleSheet("color:#64748b; font-size:11px; border:none; background:transparent;")
        pp_lay.addWidget(pp_desc)

        pp_row = QHBoxLayout()

        self.paint_type_combo = QComboBox()
        self.paint_type_combo.addItems(
            ["ALL TYPES", "MOTORCYCLE", "SCOOTER", "SCOOTY", "MOPED"]
        )
        self.paint_type_combo.setStyleSheet(ui_theme.get_combobox_style())
        self.paint_type_combo.setMinimumWidth(170)
        self.paint_type_combo.currentTextChanged.connect(self._on_paint_type_changed)
        pp_row.addWidget(self.paint_type_combo)

        self.paint_model_combo = QComboBox()
        self.paint_model_combo.addItem("ALL MODELS")
        self.paint_model_combo.setStyleSheet(ui_theme.get_combobox_style())
        self.paint_model_combo.setMinimumWidth(220)
        self.paint_model_combo.setToolTip("Select a specific model or leave ALL MODELS to sync everything")
        pp_row.addWidget(self.paint_model_combo)

        self.paint_sync_btn = QPushButton("🎨  Start Painted Parts Sync")
        self.paint_sync_btn.setStyleSheet(ui_theme.get_neon_action_button())
        self.paint_sync_btn.clicked.connect(self._on_painted_sync_start)
        pp_row.addWidget(self.paint_sync_btn)
        pp_row.addStretch()
        pp_lay.addLayout(pp_row)
        ag.addWidget(paint_panel)

        # ── Shared Progress Bar + Log ──────────────────────────────────────────
        self.sync_progress = QProgressBar()
        self.sync_progress.setTextVisible(True)
        self.sync_progress.setFixedHeight(18)
        self.sync_progress.setVisible(False)
        self.sync_progress.setStyleSheet(ui_theme.get_progressbar_style())
        ag.addWidget(self.sync_progress)

        self.sync_log = QTextEdit()
        self.sync_log.setReadOnly(True)
        self.sync_log.setFixedHeight(160)
        self.sync_log.setStyleSheet(
            "background:#0f172a; color:#94a3b8; font-family:Consolas; font-size:12px;"
            " border:1px solid #1e293b; border-radius:4px; padding:6px;"
        )
        ag.addWidget(self.sync_log)

        lay.addWidget(api_group)
        lay.addStretch()
        self.center_tabs.addTab(tab, "🔄 Data Sync")


    # ── DB Badge ─────────────────────────────────────────────────────────────
    def _refresh_db_badge(self):
        if self._catalog_db and os.path.isfile(self._catalog_db):
            name = os.path.basename(self._catalog_db)
            self.lbl_db.setText(f"✅ {name}")
            self.lbl_db.setStyleSheet(
                "color: #00ff88; font-size: 11px; font-weight: 700;"
                " padding: 3px 12px;"
                " background: rgba(0,255,136,0.08);"
                " border: 1px solid rgba(0,255,136,0.30);"
                " border-radius: 12px;"
            )
        else:
            self.lbl_db.setText("⚠️ No Catalog DB")
            self.lbl_db.setStyleSheet(
                "color: #ff4444; font-size: 11px; font-weight: 700;"
                " padding: 3px 12px;"
                " background: rgba(255,0,68,0.08);"
                " border: 1px solid rgba(255,0,68,0.30);"
                " border-radius: 12px;"
            )

    # ── Filter Tree ───────────────────────────────────────────────────────────
    def _populate_filter_tree(self):
        self._load_settings()
        self._refresh_db_badge()
        conn = _open_catalog_db(self._catalog_db)
        if not conn:
            self.filter_tree.clear()
            item = QTreeWidgetItem(["⚠️ No catalog DB — configure in Settings"])
            item.setForeground(0, QBrush(QColor("#ef4444")))
            self.filter_tree.addTopLevelItem(item)
            return

        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT DISTINCT 
                    v.vehicle_id, v.brand, v.segment, v.series, v.model_name, v.variant, p.category
                FROM vehicles_master v
                JOIN compatibility_map cm ON v.vehicle_id = cm.vehicle_id
                JOIN parts_master p ON cm.part_code = p.part_code
                ORDER BY v.brand, v.segment, v.series, v.model_name, v.variant, p.category
            """)
            rows = [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

        self.filter_tree.clear()

        import re as _re

        def _is_numeric_id(s: str) -> bool:
            """Return True if s looks like a raw numeric TVS ID (4+ digits)."""
            return bool(s and _re.fullmatch(r'0*\d{4,}', s.strip()))

        # ── Split rows: PAINTED (by category) vs SPARE (everything else) ─────
        # The DB stores painted parts with pm.category = 'PAINTED PARTS / <Color>'
        # segment is just 'MOTORCYCLE' — NOT 'PAINTED_MOTORCYCLE'
        spare_rows   = [r for r in rows if not r.get("category", "").upper().startswith("PAINTED")]
        painted_rows = [r for r in rows if r.get("category", "").upper().startswith("PAINTED")]

        def _make_section_header(label: str, color: str) -> QTreeWidgetItem:
            """Create a bold, non-interactive section divider row."""
            hdr = QTreeWidgetItem([label])
            hdr.setForeground(0, QBrush(QColor(color)))
            f = hdr.font(0)
            f.setBold(True)
            f.setPointSize(f.pointSize() + 1)
            hdr.setFont(0, f)
            hdr.setFlags(Qt.ItemFlag.ItemIsEnabled)   # not selectable
            return hdr

        # ── Section 1: SPARE PARTS tree ──────────────────────────────────────
        def _build_spare_tree(section_rows: list) -> dict:
            """Build nested: segment → model_name → [(category, vid)]"""
            tree: dict = {}
            for r in section_rows:
                raw_seg = r["segment"] or "General"
                # Human-readable segment label (title-case, no underscores)
                seg = raw_seg.replace("_", " ").title()
                raw_ser = r["series"] or ""
                m = r["model_name"] or "(Model)"
                # Filter out raw numeric model_names
                if _is_numeric_id(m):
                    m = raw_ser.title() if raw_ser and not _is_numeric_id(raw_ser) else "(Model)"
                v        = r["variant"] or ""
                cat_name = r.get("category", "") or "General Assembly"
                vid      = r["vehicle_id"]

                # Collapse series level when it is a numeric ID
                if _is_numeric_id(raw_ser):
                    ser = m
                    model_key = v if v and not _is_numeric_id(v) else "All"
                else:
                    ser = raw_ser.title() if raw_ser else m
                    model_key = f"{m} {v}".strip()

                tree.setdefault(seg, {}).setdefault(ser, {}) \
                    .setdefault(model_key, []).append((cat_name, vid))
            return tree

        def _populate_spare_section(section_tree: dict):
            for seg, series_dict in sorted(section_tree.items()):
                s_item = QTreeWidgetItem([f"▸ {seg}"])
                s_item.setForeground(0, QBrush(QColor("#fbbf24")))
                f = s_item.font(0); f.setBold(True); s_item.setFont(0, f)

                for ser, models in sorted(series_dict.items()):
                    ser_item = QTreeWidgetItem([f"🏍️ {ser}"])
                    ser_item.setForeground(0, QBrush(QColor("#94a3b8")))

                    for model_key, categories in sorted(models.items()):
                        m_item = QTreeWidgetItem([model_key])
                        m_item.setForeground(0, QBrush(QColor("#d1d5db")))
                        vid = categories[0][1] if categories else None
                        m_item.setData(0, Qt.ItemDataRole.UserRole, vid)
                        m_item.setData(0, Qt.ItemDataRole.UserRole + 2, False)  # is_painted=False

                        all_parts_item = QTreeWidgetItem(["📦 All Parts"])
                        all_parts_item.setForeground(0, QBrush(QColor("#fca5a5")))
                        all_parts_item.setData(0, Qt.ItemDataRole.UserRole, vid)
                        all_parts_item.setData(0, Qt.ItemDataRole.UserRole + 1, None)
                        all_parts_item.setData(0, Qt.ItemDataRole.UserRole + 2, False)  # is_painted=False
                        m_item.addChild(all_parts_item)

                        unique_cats: dict = {}
                        for cat, cat_vid in categories:
                            if cat not in unique_cats:
                                unique_cats[cat] = cat_vid
                        for cat, cat_vid in sorted(unique_cats.items()):
                            cat_item = QTreeWidgetItem([f"  {cat}"])
                            cat_item.setForeground(0, QBrush(QColor("#9ca3af")))
                            cat_item.setData(0, Qt.ItemDataRole.UserRole, cat_vid)
                            cat_item.setData(0, Qt.ItemDataRole.UserRole + 1, cat)
                            cat_item.setData(0, Qt.ItemDataRole.UserRole + 2, False)  # is_painted=False
                            m_item.addChild(cat_item)

                        ser_item.addChild(m_item)
                    s_item.addChild(ser_item)
                self.filter_tree.addTopLevelItem(s_item)

        # ── Section 2: PAINTED PARTS tree ────────────────────────────────────
        # Structure (mirrors TVS eCatalog): ModelName → 🎨 Color Name
        def _build_painted_tree(section_rows: list) -> dict:
            """
            Build nested: segment → model_name → color_label → (full_cat_raw, vid)
            color_label extracted from category like 'PAINTED PARTS / Furozia Blue'
            """
            tree: dict = {}
            for r in section_rows:
                raw_seg = r["segment"] or "General"
                seg = raw_seg.replace("PAINTED_", "").replace("_", " ").title()
                m = r["model_name"] or ""
                if not m or _is_numeric_id(m):
                    m = r["series"] or "(Model)"
                    if _is_numeric_id(m):
                        m = "(Model)"
                m = m.title()
                full_cat = r.get("category", "") or ""
                # Extract clean color name from 'PAINTED PARTS / COLOR NAME'
                if full_cat.upper().startswith("PAINTED PARTS / "):
                    color = full_cat[16:].title()
                elif full_cat.upper().startswith("PAINTED"):
                    color = full_cat.title()
                else:
                    color = "Unknown Color"
                vid = r["vehicle_id"]
                # tree[seg][model][color] = (full_cat_raw, vid)
                if seg not in tree:
                    tree[seg] = {}
                if m not in tree[seg]:
                    tree[seg][m] = {}
                if color not in tree[seg][m]:
                    tree[seg][m][color] = (full_cat, vid)
            return tree

        def _populate_painted_section(painted_tree: dict):
            for seg, models in sorted(painted_tree.items()):
                s_item = QTreeWidgetItem([f"▸ {seg}"])
                s_item.setForeground(0, QBrush(QColor("#a855f7")))
                f = s_item.font(0); f.setBold(True); s_item.setFont(0, f)

                for model_name, colors in sorted(models.items()):
                    m_item = QTreeWidgetItem([f"🖌️ {model_name}"])
                    m_item.setForeground(0, QBrush(QColor("#e9d5ff")))
                    first_entry = next(iter(colors.values())) if colors else (None, None)
                    first_vid   = first_entry[1]
                    m_item.setData(0, Qt.ItemDataRole.UserRole,     first_vid)
                    m_item.setData(0, Qt.ItemDataRole.UserRole + 2, True)   # is_painted

                    all_clr = QTreeWidgetItem(["📦 All Colors"])
                    all_clr.setForeground(0, QBrush(QColor("#fca5a5")))
                    all_clr.setData(0, Qt.ItemDataRole.UserRole,     first_vid)
                    all_clr.setData(0, Qt.ItemDataRole.UserRole + 1, None)
                    all_clr.setData(0, Qt.ItemDataRole.UserRole + 2, True)  # is_painted
                    m_item.addChild(all_clr)

                    for color_label, (full_cat_raw, cat_vid) in sorted(colors.items()):
                        clr_item = QTreeWidgetItem([f"  🎨 {color_label}"])
                        clr_item.setForeground(0, QBrush(QColor("#c084fc")))
                        clr_item.setData(0, Qt.ItemDataRole.UserRole,     cat_vid)
                        clr_item.setData(0, Qt.ItemDataRole.UserRole + 1, full_cat_raw)
                        clr_item.setData(0, Qt.ItemDataRole.UserRole + 2, True)  # is_painted
                        m_item.addChild(clr_item)

                    s_item.addChild(m_item)
                self.filter_tree.addTopLevelItem(s_item)

        # ── Build and add both sections ───────────────────────────────────────
        if spare_rows:
            spare_hdr = _make_section_header("🔧  SPARE PARTS", "#38bdf8")
            self.filter_tree.addTopLevelItem(spare_hdr)
            _populate_spare_section(_build_spare_tree(spare_rows))

        if painted_rows:
            paint_hdr = _make_section_header("🎨  PAINTED PARTS", "#c084fc")
            self.filter_tree.addTopLevelItem(paint_hdr)
            _populate_painted_section(_build_painted_tree(painted_rows))

        self.lbl_status.setText(
            f"✅ Tree loaded — {len(spare_rows)} spare | {len(painted_rows)} painted"
        )

        # Populate category dropdowns for All Parts + Common Parts tabs
        self._populate_category_combos()




    def _collect_filters(self, item: QTreeWidgetItem) -> list:
        """Return list of (vid, category, is_painted) tuples for this node."""
        label      = item.text(0).strip()
        is_painted = bool(item.data(0, Qt.ItemDataRole.UserRole + 2))

        # Shortcut nodes: load all parts of their type (no specific category)
        if label in ("📦 All Parts", "📦 All Colors"):
            vid = item.data(0, Qt.ItemDataRole.UserRole)
            return [(vid, None, is_painted)] if vid is not None else []

        filters  = []
        vid      = item.data(0, Qt.ItemDataRole.UserRole)
        category = item.data(0, Qt.ItemDataRole.UserRole + 1)

        if vid is not None and category is not None:
            filters.append((vid, category, is_painted))
        elif vid is not None and item.childCount() == 0:
            filters.append((vid, None, is_painted))

        for i in range(item.childCount()):
            filters.extend(self._collect_filters(item.child(i)))

        return list(set(filters))


    def _on_tree_item_clicked(self, item: QTreeWidgetItem, _col: int):
        item.setExpanded(not item.isExpanded())

        filters = self._collect_filters(item)
        if not filters:
            return

        conn = _open_catalog_db(self._catalog_db)
        if not conn:
            return

        all_parts  = []
        seen_codes = set()

        try:
            cur = conn.cursor()
            for vid, category, is_painted in filters:
                if category:
                    # Specific assembly or specific painted color — exact match
                    cur.execute("""
                        SELECT pm.part_code, pm.description, pm.category,
                               pm.mrp, pm.ndp, pm.moq, pm.remarks
                        FROM   compatibility_map cm
                        JOIN   parts_master pm ON pm.part_code = cm.part_code
                        WHERE  cm.vehicle_id = ? AND pm.category = ?
                        ORDER  BY pm.part_code
                    """, (vid, category))
                elif is_painted:
                    # Painted model — ALL colors, but ONLY 'PAINTED PARTS%' categories
                    cur.execute("""
                        SELECT pm.part_code, pm.description, pm.category,
                               pm.mrp, pm.ndp, pm.moq, pm.remarks
                        FROM   compatibility_map cm
                        JOIN   parts_master pm ON pm.part_code = cm.part_code
                        WHERE  cm.vehicle_id = ?
                          AND  UPPER(pm.category) LIKE 'PAINTED PARTS%'
                        ORDER  BY pm.category, pm.part_code
                    """, (vid,))
                else:
                    # Spare model — ALL assemblies, EXCLUDING painted categories
                    cur.execute("""
                        SELECT pm.part_code, pm.description, pm.category,
                               pm.mrp, pm.ndp, pm.moq, pm.remarks
                        FROM   compatibility_map cm
                        JOIN   parts_master pm ON pm.part_code = cm.part_code
                        WHERE  cm.vehicle_id = ?
                          AND  UPPER(pm.category) NOT LIKE 'PAINTED PARTS%'
                        ORDER  BY pm.category, pm.part_code
                    """, (vid,))

                for r in cur.fetchall():
                    d = dict(r)
                    if d["part_code"] not in seen_codes:
                        all_parts.append(d)
                        seen_codes.add(d["part_code"])
        finally:
            conn.close()

        all_parts.sort(key=lambda x: (x.get("category", ""), x.get("part_code", "")))
        self._fill_parts_table(all_parts)
        self.lbl_status.setText(f"🔧 Showing {len(all_parts)} parts for selection")
        self.lbl_count.setText(f"{len(all_parts)} parts")
        self.center_tabs.setCurrentIndex(0)

    # ── Search ────────────────────────────────────────────────────────────────
    def _on_search(self):
        kw = self.search_bar.text().strip()
        if not kw:
            return
        conn = _open_catalog_db(self._catalog_db)
        if not conn:
            self.lbl_status.setText("⚠️ No catalog DB configured")
            return
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT part_code, description, category, mrp, ndp, moq, remarks
                FROM   parts_master
                WHERE  part_code   LIKE ?
                   OR  description LIKE ?
                   OR  category    LIKE ?
                LIMIT 300
            """, (f"%{kw}%",) * 3)
            parts = [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

        self._fill_parts_table(parts)
        self.lbl_status.setText(f'🔍 Search "{kw}" — {len(parts)} results')
        self.lbl_count.setText(f"{len(parts)} results")
        self.center_tabs.setCurrentIndex(0)

    # ── Fill parts table ──────────────────────────────────────────────────────
    def _fill_parts_table(self, parts: list):
        self.data_table.setSortingEnabled(False)
        self.data_table.blockSignals(True)
        self.data_table.setRowCount(0)
        self.data_table.setRowCount(len(parts))
        self._parts_data = parts
        for i, p in enumerate(parts):
            code = p.get("part_code", "")
            chk = QTableWidgetItem("")
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk.setCheckState(Qt.CheckState.Checked if code in getattr(self, "selected_parts", {}) else Qt.CheckState.Unchecked)
            self.data_table.setItem(i, 0, chk)
            
            def _si(col, val, color=None):
                itm = QTableWidgetItem(str(val or ""))
                if color:
                    itm.setForeground(QBrush(QColor(color)))
                self.data_table.setItem(i, col, itm)
            _si(1, code,    "#60a5fa")
            _si(2, p.get("description", ""))
            _si(3, p.get("category", ""),      "#fbbf24")
            mrp = p.get("mrp", 0)
            ndp = p.get("ndp", 0)
            _si(4, f"₹{float(mrp):.2f}" if mrp else "—", "#4ade80")
            _si(5, f"₹{float(ndp):.2f}" if ndp else "—")
            _si(6, p.get("moq", ""))
            _si(7, p.get("remarks", ""))
            
        self.data_table.blockSignals(False)
        self.data_table.setSortingEnabled(True)
        self.vehicles_table.setRowCount(0)

    # ── Part selected → show supporting vehicles ──────────────────────────────
    def _on_part_selected(self):
        rows = self.data_table.selectedItems()
        if not rows:
            return
        row = rows[0].row()
        if not hasattr(self, "_parts_data") or row >= len(self._parts_data):
            return
        part_code = self._parts_data[row].get("part_code", "")
        if not part_code:
            return
        conn = _open_catalog_db(self._catalog_db)
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT vm.brand, vm.segment, vm.series, vm.model_name, vm.variant
                FROM   compatibility_map cm
                JOIN   vehicles_master vm ON vm.vehicle_id = cm.vehicle_id
                WHERE  cm.part_code = ?
                ORDER  BY vm.brand, vm.series, vm.model_name
            """, (part_code,))
            vehs = [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

        self.vehicles_table.setSortingEnabled(False)
        self.vehicles_table.setRowCount(len(vehs))
        for i, v in enumerate(vehs):
            for col, key in enumerate(["brand", "segment", "series", "model_name", "variant"]):
                itm = QTableWidgetItem(str(v.get(key, "") or ""))
                self.vehicles_table.setItem(i, col, itm)
        self.vehicles_table.setSortingEnabled(True)

    # ── Context menu ─────────────────────────────────────────────────────────
    def _show_context_menu(self, pos):
        selected = self.data_table.selectedItems()
        if not selected:
            return
            
        rows = sorted(list(set(item.row() for item in selected)))
        if not rows: return
        first_row = rows[0]
        
        menu = QMenu(self)
        menu.setStyleSheet(ui_theme.get_menu_style())
        
        if len(rows) == 1:
            act_copy = QAction("📋 Copy Part Code", self)
            act_copy.triggered.connect(lambda: self._copy_part_code(first_row))
            menu.addAction(act_copy)
            
            act_inv = QAction("📦 Find in Inventory", self)
            act_inv.triggered.connect(lambda: self._open_in_inventory(first_row))
            menu.addAction(act_inv)
            
            menu.addSeparator()

        lbl = f"➕ Check/Select Highlighted Parts"
        act_sel = QAction(lbl, self)
        
        def _check_selected_data():
            self.data_table.blockSignals(True)
            for r in rows:
                chk = self.data_table.item(r, 0)
                if chk and chk.checkState() == Qt.CheckState.Unchecked:
                    chk.setCheckState(Qt.CheckState.Checked)
                    code = self._parts_data[r].get("part_code", "")
                    getattr(self, "selected_parts", {})[code] = self._parts_data[r]
            self.data_table.blockSignals(False)
            self._refresh_cart_counter()
            self.data_table.clearSelection()
            
        act_sel.triggered.connect(_check_selected_data)
        menu.addAction(act_sel)

        menu.exec(self.data_table.viewport().mapToGlobal(pos))

    def _show_common_context_menu(self, pos):
        selected = self.common_parts_table.selectedItems()
        if not selected:
            return
            
        rows = sorted(list(set(item.row() for item in selected)))
        if not rows: return
        first_row = rows[0]
        
        menu = QMenu(self)
        menu.setStyleSheet(ui_theme.get_menu_style())
        
        if len(rows) == 1:
            act_copy = QAction("📋 Copy Part Code", self)
            act_copy.triggered.connect(lambda: QApplication.clipboard().setText(self._common_parts[first_row].get("part_code", "")))
            menu.addAction(act_copy)
            
            act_inv = QAction("📦 Find in Inventory", self)
            def _find():
                code = self._common_parts[first_row].get("part_code", "")
                mw = self.window()
                if hasattr(mw, "quick_navigate"):
                    mw.quick_navigate(2)
                    def _focus():
                        inv = mw.stacked_widget.currentWidget()
                        for attr in ("search_input", "filter_input", "search_bar"):
                            w = getattr(inv, attr, None)
                            if w:
                                w.setText(code); w.setFocus(); break
                    QTimer.singleShot(300, _focus)
            act_inv.triggered.connect(_find)
            menu.addAction(act_inv)
            menu.addSeparator()
            
        lbl = f"➕ Check/Select Highlighted Parts"
        act_sel = QAction(lbl, self)
        
        def _check_selected_common():
            self.common_parts_table.blockSignals(True)
            for r in rows:
                chk = self.common_parts_table.item(r, 0)
                if chk and chk.checkState() == Qt.CheckState.Unchecked:
                    chk.setCheckState(Qt.CheckState.Checked)
                    code = self._common_parts[r].get("part_code", "")
                    getattr(self, "selected_parts", {})[code] = self._common_parts[r]
            self.common_parts_table.blockSignals(False)
            self._refresh_cart_counter()
            self.common_parts_table.clearSelection()
            
        act_sel.triggered.connect(_check_selected_common)
        menu.addAction(act_sel)

        menu.exec(self.common_parts_table.viewport().mapToGlobal(pos))

    # ── All Parts Table population ────────────────────────────────────────────
    def _populate_all_parts_table(self):
        """Load all parts from catalog DB, filtered by category, vehicle, model, color, and search text.
        All combo labels are human-readable; this method translates them back to raw DB values.
        """
        conn = _open_catalog_db(self._catalog_db)
        if not conn:
            self.all_parts_count_lbl.setText("⚠️  No catalog DB — configure in Settings")
            return

        cat = getattr(self, "all_parts_cat_combo", None)
        cat_display = cat.currentText() if cat else "All Categories"
        veh_display = self.all_parts_veh_combo.currentText() if hasattr(self, "all_parts_veh_combo") else "All Vehicles"
        mod_filter  = self.all_parts_mod_combo.currentText() if hasattr(self, "all_parts_mod_combo") else "All Models"
        col_display = self.all_parts_color_combo.currentText() if hasattr(self, "all_parts_color_combo") else "All Colors"
        kw = (getattr(self, "all_parts_search", None) or QLineEdit()).text().strip().lower()

        # ── Translate display labels → raw DB values ───────────────────────────
        # Category: display label → raw category string
        cat_raw_map = getattr(self, "_cat_label_to_raw", {})
        cat_filter = cat_raw_map.get(cat_display, cat_display)  # fallback = as-is

        # Vehicle segment: display label → raw segment string
        seg_raw_map = getattr(self, "_seg_label_to_raw", {})
        seg_filter = seg_raw_map.get(veh_display, veh_display)

        # Color: the combo shows title-cased color name (e.g. 'Furozia Blue')
        # The DB stores 'PAINTED PARTS / FUROZIA BLUE' in pm.category (case-insensitive match)
        # We reconstruct the full category key for an exact match.
        col_filter = col_display  # e.g. 'Furozia Blue' or 'All Colors'

        try:
            cur = conn.cursor()
            q = "SELECT DISTINCT pm.part_code, pm.description, pm.category, pm.mrp, pm.ndp, pm.moq, pm.remarks FROM parts_master pm"
            params = []
            conditions = []

            needs_vehicle_join = (veh_display != "All Vehicles" or mod_filter != "All Models" or col_filter != "All Colors")
            if needs_vehicle_join:
                q += " JOIN compatibility_map cm ON pm.part_code = cm.part_code JOIN vehicles_master vm ON cm.vehicle_id = vm.vehicle_id"
                if veh_display != "All Vehicles":
                    conditions.append("vm.segment = ?")
                    params.append(seg_filter)
                if mod_filter != "All Models":
                    conditions.append("vm.model_name = ?")
                    params.append(mod_filter)

            # ── KEY FIX: Color/SYN selection filters on pm.category (case-insensitive) ──
            if col_filter != "All Colors":
                # A specific SYN/color was chosen → show ONLY that painted category
                conditions.append("UPPER(pm.category) = UPPER(?)")
                params.append(f"PAINTED PARTS / {col_filter}")
            elif cat_display == "All Categories":
                # No color and no specific category chosen → exclude ALL painted parts
                # so spare parts and painted parts never mix in the default view
                conditions.append("UPPER(pm.category) NOT LIKE 'PAINTED PARTS%'")

            # Category: translate clean label back to raw DB value
            if cat_display and cat_display != "All Categories":
                conditions.append("pm.category = ?")
                params.append(cat_filter)

            if kw:
                conditions.append("(LOWER(pm.part_code) LIKE ? OR LOWER(pm.description) LIKE ?)")
                params += [f"%{kw}%", f"%{kw}%"]

            if conditions:
                q += " WHERE " + " AND ".join(conditions)
            q += " ORDER BY pm.category, pm.part_code LIMIT 2000"
            cur.execute(q, params)
            rows = [dict(r) for r in cur.fetchall()]
        except Exception as e:
            self.all_parts_count_lbl.setText(f"❌ Query error: {e}")
            rows = []
        finally:
            conn.close()

        self._all_parts_data = rows
        self.all_parts_table.setSortingEnabled(False)
        self.all_parts_table.blockSignals(True)
        self.all_parts_table.setRowCount(0)
        self.all_parts_table.setRowCount(len(rows))
        for i, p in enumerate(rows):
            code = p.get("part_code", "")
            chk = QTableWidgetItem("")
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk.setCheckState(
                Qt.CheckState.Checked if code in self.selected_parts
                else Qt.CheckState.Unchecked
            )
            self.all_parts_table.setItem(i, 0, chk)

            def _si(col, val, color=None, tbl=self.all_parts_table, row=i):
                itm = QTableWidgetItem(str(val or ""))
                if color:
                    itm.setForeground(QBrush(QColor(color)))
                tbl.setItem(row, col, itm)
            _si(1, code,                  "#60a5fa")
            _si(2, p.get("description", ""))
            _si(3, p.get("category", ""),  "#fbbf24")
            mrp = p.get("mrp", 0); ndp = p.get("ndp", 0)
            _si(4, f"₹{float(mrp):.2f}" if mrp else "—", "#4ade80")
            _si(5, f"₹{float(ndp):.2f}" if ndp else "—")
            _si(6, p.get("moq", ""))
            _si(7, p.get("remarks", ""))

        self.all_parts_table.blockSignals(False)
        self.all_parts_table.setSortingEnabled(True)
        self.all_parts_count_lbl.setText(f"{len(rows)} parts{' matching' if kw or cat_filter != 'All Categories' else ' total'}")
        # Clear vehicles panel — selection context is now stale
        self.all_parts_vehicles_table.setRowCount(0)

    # ── Cart & Purchase Order Logic ──────────────────────────────────────────

    def _ask_qty_and_add(self, code: str, part_dict: dict):
        """
        Show the QtyEntryDialog. If accepted, store part+qty+rack+col in cart.
        If rejected, uncheck the box in every visible table.
        """
        # Pull current stock + location from the local inventory DB
        stock = 0; reorder = 0; rack = ""; col = ""
        if hasattr(self, "db_manager") and self.db_manager:
            local_conn = None
            try:
                local_conn = self.db_manager.get_connection()
                cur = local_conn.cursor()
                cur.execute(
                    "SELECT qty, reorder_level, rack_number, col_number "
                    "FROM parts WHERE part_id = ?", (code,)
                )
                row = cur.fetchone()
                if row:
                    # Index-based access — get_connection() does not set row_factory
                    stock   = int(row[0] or 0)
                    reorder = int(row[1] or 0)
                    rack    = str(row[2] or "")
                    col     = str(row[3] or "")
            except Exception:
                pass
            finally:
                if local_conn:
                    local_conn.close()

        dlg = QtyEntryDialog(
            code, part_dict.get("description", ""),
            current_stock=stock, reorder_level=reorder,
            current_rack=rack, current_col=col,
            parent=self
        )
        if dlg.exec():
            self.selected_parts[code] = {
                **part_dict,
                "_req_qty":  dlg.get_qty(),
                "_req_rack": dlg.get_rack(),
                "_req_col":  dlg.get_col(),
            }
            self._refresh_cart_counter()
        else:
            # User cancelled — visually uncheck from all tables
            self._uncheck_part_in_all_tables(code)

    def _uncheck_part_in_all_tables(self, code: str):
        """Set the SEL checkbox to Unchecked for `code` across all three tables."""
        for table, data_attr in [
            (self.data_table,        "_parts_data"),
            (self.common_parts_table, "_common_parts"),
            (self.all_parts_table,   "_all_parts_data"),
        ]:
            data = getattr(self, data_attr, [])
            table.blockSignals(True)
            for r in range(table.rowCount()):
                row_code = data[r].get("part_code", "") if r < len(data) else ""
                if row_code == code:
                    chk = table.item(r, 0)
                    if chk:
                        chk.setCheckState(Qt.CheckState.Unchecked)
                    break
            table.blockSignals(False)

    def _on_cart_checkbox_toggled_data_table(self, item):
        if item.column() != 0: return
        row = item.row()
        if not hasattr(self, "_parts_data") or row >= len(self._parts_data): return
        code = self._parts_data[row].get("part_code", "")
        if not code: return
        if item.checkState() == Qt.CheckState.Checked:
            self._ask_qty_and_add(code, self._parts_data[row])
        else:
            self.selected_parts.pop(code, None)
            self._refresh_cart_counter()

    def _on_cart_checkbox_toggled_common_table(self, item):
        if item.column() != 0: return
        row = item.row()
        if not hasattr(self, "_common_parts") or row >= len(self._common_parts): return
        code = self._common_parts[row].get("part_code", "")
        if not code: return
        if item.checkState() == Qt.CheckState.Checked:
            self._ask_qty_and_add(code, self._common_parts[row])
        else:
            self.selected_parts.pop(code, None)
            self._refresh_cart_counter()

    def _on_cart_checkbox_toggled_all_parts(self, item):
        if item.column() != 0: return
        row = item.row()
        if not hasattr(self, "_all_parts_data") or row >= len(self._all_parts_data): return
        code = self._all_parts_data[row].get("part_code", "")
        if not code: return
        if item.checkState() == Qt.CheckState.Checked:
            self._ask_qty_and_add(code, self._all_parts_data[row])
        else:
            self.selected_parts.pop(code, None)
            self._refresh_cart_counter()

    def _refresh_cart_counter(self):
        count = len(getattr(self, "selected_parts", {}))
        self.btn_cart.setText(f"🛒 Make PO ({count})")

    def _make_po_from_cart(self):
        parts_cart = getattr(self, "selected_parts", {})
        if not parts_cart:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "Empty Cart", "No parts selected. Please use the SEL checkboxes to add parts to the order.")
            return

        if not hasattr(self.window(), "go_to_purchase_page"):
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Error", "Navigation to Purchase Order page failed.")
            return

        items = []
        conn = _open_catalog_db(self._catalog_db) if self._catalog_db else None
        
        import sqlite3
        local_conn = None
        if hasattr(self, 'db_manager') and self.db_manager:
            local_conn = self.db_manager.get_connection()

        try:
            cur_local = local_conn.cursor() if local_conn else None

            for code, p_dict in parts_cart.items():
                name   = p_dict.get("description", "")
                price  = float(p_dict.get("mrp") or p_dict.get("unit_price") or 0.0)
                req_qty = int(p_dict.get("_req_qty", 1))
                req_rack = str(p_dict.get("_req_rack", ""))
                req_col  = str(p_dict.get("_req_col",  ""))

                stock = 0; reorder = 5; vendor = ""
                hsn = "87089900"; gst = 18.0

                if cur_local:
                    try:
                        cur_local.execute(
                            "SELECT qty, reorder_level, vendor_name, unit_price, "
                            "hsn_code, gst_rate, rack_number, col_number "
                            "FROM parts WHERE part_id = ?", (code,)
                        )
                        row_data = cur_local.fetchone()
                        if row_data:
                            # Index-based access — get_connection() does not set row_factory
                            # Columns: qty[0], reorder_level[1], vendor_name[2], unit_price[3]
                            # hsn_code[4], gst_rate[5], rack_number[6], col_number[7]
                            stock   = int(row_data[0] or 0)
                            reorder = int(row_data[1] or 5)
                            vendor  = row_data[2] or ""
                            local_price = float(row_data[3] or 0.0)
                            if local_price > 0:
                                price = local_price
                            hsn = row_data[4] or "87089900"
                            gst = float(row_data[5] or 18.0)
                            # Prefer location from dialog if user typed one
                            if not req_rack:
                                req_rack = str(row_data[6] or "")
                            if not req_col:
                                req_col  = str(row_data[7] or "")
                    except Exception:
                        pass

                # 11-element list:
                # [0]=code [1]=name [2]=stock [3]=reorder [4]=vendor
                # [5]=price [6]=hsn [7]=gst [8]=qty [9]=rack [10]=col
                items.append([code, name, stock, reorder, vendor,
                              price, hsn, gst, req_qty, req_rack, req_col])

            # Navigate and clear cart if successful (window might return True if handled)
            self.window().go_to_purchase_page(items)
            
            # Clear Cart
            self.selected_parts.clear()
            self._refresh_cart_counter()
            
            # Refresh all visible tables to clear checkboxes
            if hasattr(self, "_parts_data") and self.data_table.rowCount() > 0:
                self._fill_parts_table(self._parts_data)
            for tbl in (self.common_parts_table, self.all_parts_table):
                tbl.blockSignals(True)
                for r in range(tbl.rowCount()):
                    chk = tbl.item(r, 0)
                    if chk:
                        chk.setCheckState(Qt.CheckState.Unchecked)
                tbl.blockSignals(False)
                
        finally:
            if conn: conn.close()
            if local_conn: local_conn.close()

    def _copy_part_code(self, row: int):
        if hasattr(self, "_parts_data") and row < len(self._parts_data):
            QApplication.clipboard().setText(self._parts_data[row].get("part_code", ""))

    def _open_in_inventory(self, row: int):
        if not hasattr(self, "_parts_data") or row >= len(self._parts_data):
            return
        code = self._parts_data[row].get("part_code", "")
        mw = self.window()
        if hasattr(mw, "quick_navigate"):
            mw.quick_navigate(2)
            def _focus():
                inv = mw.stacked_widget.currentWidget()
                for attr in ("search_input", "filter_input", "search_bar"):
                    w = getattr(inv, attr, None)
                    if w:
                        w.setText(code); w.setFocus(); break
            QTimer.singleShot(300, _focus)

    # ── Common Parts Analyzer ─────────────────────────────────────────────────
    def _on_load_common_parts(self):
        conn = _open_catalog_db(self._catalog_db)
        if not conn:
            self.lbl_status.setText("⚠️ No catalog DB")
            return
        min_v = self.min_vehicles_spin.value()
        cat_filter = self.category_combo_analyzer.currentText()
        try:
            cur = conn.cursor()
            q = """
                SELECT pm.part_code, pm.description, pm.category,
                       COUNT(DISTINCT cm.vehicle_id) AS vcount, pm.mrp
                FROM   compatibility_map cm
                JOIN   parts_master pm ON pm.part_code = cm.part_code
            """
            params = []
            if cat_filter and cat_filter != "All Categories":
                q += " WHERE pm.category = ?"
                params.append(cat_filter)
            q += " GROUP BY pm.part_code HAVING vcount >= ? ORDER BY vcount DESC LIMIT 500"
            params.append(min_v)
            cur.execute(q, params)
            rows = [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

        self._common_parts = rows
        self.common_parts_table.setSortingEnabled(False)
        self.common_parts_table.blockSignals(True)
        self.common_parts_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            code = r.get("part_code", "")
            chk = QTableWidgetItem("")
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk.setCheckState(Qt.CheckState.Checked if code in getattr(self, "selected_parts", {}) else Qt.CheckState.Unchecked)
            self.common_parts_table.setItem(i, 0, chk)
            
            for col, (key, color) in enumerate([
                ("part_code",   "#60a5fa"),
                ("description", None),
                ("category",    "#fbbf24"),
                ("vcount",      "#4ade80"),
                ("mrp",         None),
            ], start=1):
                val = r.get(key, "")
                if key == "mrp":
                    val = f"₹{float(val):.2f}" if val else "—"
                itm = QTableWidgetItem(str(val or ""))
                if color:
                    itm.setForeground(QBrush(QColor(color)))
                self.common_parts_table.setItem(i, col, itm)
        self.common_parts_table.blockSignals(False)
        self.common_parts_table.setSortingEnabled(True)
        self.lbl_status.setText(f"📊 {len(rows)} common parts (min {min_v} vehicles)")

    def _on_common_part_selected(self):
        rows = self.common_parts_table.selectedItems()
        if not rows:
            return
        row = rows[0].row()
        if not hasattr(self, "_common_parts") or row >= len(self._common_parts):
            return
        part_code = self._common_parts[row].get("part_code", "")
        conn = _open_catalog_db(self._catalog_db)
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT vm.brand, vm.segment, vm.series, vm.model_name, vm.variant
                FROM   compatibility_map cm
                JOIN   vehicles_master vm ON vm.vehicle_id = cm.vehicle_id
                WHERE  cm.part_code = ?
            """, (part_code,))
            vehs = [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()
        self.common_vehicles_table.setRowCount(len(vehs))
        for i, v in enumerate(vehs):
            for col, key in enumerate(["brand", "segment", "series", "model_name", "variant"]):
                self.common_vehicles_table.setItem(i, col, QTableWidgetItem(str(v.get(key, "") or "")))

    # ── All Parts tab: row selected → show supporting vehicles ────────────────
    def _on_all_part_selected(self):
        rows = self.all_parts_table.selectedItems()
        if not rows:
            return
        row = rows[0].row()
        if not hasattr(self, "_all_parts_data") or row >= len(self._all_parts_data):
            return
        part_code = self._all_parts_data[row].get("part_code", "")
        if not part_code:
            self.all_parts_vehicles_table.setRowCount(0)
            return
        conn = _open_catalog_db(self._catalog_db)
        if not conn:
            return
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT vm.brand, vm.segment, vm.series, vm.model_name, vm.variant
                FROM   compatibility_map cm
                JOIN   vehicles_master vm ON vm.vehicle_id = cm.vehicle_id
                WHERE  cm.part_code = ?
                ORDER  BY vm.brand, vm.series, vm.model_name
            """, (part_code,))
            vehs = [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()
        self.all_parts_vehicles_table.setSortingEnabled(False)
        self.all_parts_vehicles_table.setRowCount(len(vehs))
        for i, v in enumerate(vehs):
            for col, key in enumerate(["brand", "segment", "series", "model_name", "variant"]):
                self.all_parts_vehicles_table.setItem(
                    i, col, QTableWidgetItem(str(v.get(key, "") or ""))
                )
        self.all_parts_vehicles_table.setSortingEnabled(True)

    def _on_export_common_parts(self):
        if not hasattr(self, "_common_parts") or not self._common_parts:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "common_parts.csv", "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=self._common_parts[0].keys())
            w.writeheader(); w.writerows(self._common_parts)
        self.lbl_status.setText(f"✅ Exported {len(self._common_parts)} rows → {os.path.basename(path)}")

    # ── Populate category dropdowns (All Parts + Analyzer) ───────────────────
    def _on_all_parts_veh_changed(self, seg_display):
        """Vehicle combo changed — repopulate Model combo and reset Color."""
        if hasattr(self, "all_parts_color_combo"):
            self.all_parts_color_combo.blockSignals(True)
            self.all_parts_color_combo.clear()
            self.all_parts_color_combo.addItem("All Colors")
            self.all_parts_color_combo.blockSignals(False)

        if not hasattr(self, "all_parts_mod_combo"): return
        self.all_parts_mod_combo.blockSignals(True)
        self.all_parts_mod_combo.clear()
        self.all_parts_mod_combo.addItem("All Models")

        if seg_display and seg_display != "All Vehicles":
            # Translate display label back to raw DB segment value
            seg_raw = getattr(self, "_seg_label_to_raw", {}).get(seg_display, seg_display)
            conn = _open_catalog_db(self._catalog_db)
            if conn:
                try:
                    cur = conn.cursor()
                    # Fetch model names — filter out pure-numeric rows (raw IDs)
                    cur.execute(
                        "SELECT DISTINCT model_name FROM vehicles_master "
                        "WHERE segment = ? AND model_name != '' ORDER BY model_name",
                        (seg_raw,)
                    )
                    import re as _re
                    models = [
                        r[0] for r in cur.fetchall()
                        if r[0] and not _re.fullmatch(r'0*\d{4,}', r[0].strip())
                    ]
                    self.all_parts_mod_combo.addItems(models)
                finally:
                    conn.close()
        self.all_parts_mod_combo.blockSignals(False)
        self._populate_all_parts_table()

    def _on_all_parts_mod_changed(self, mod):
        """Model combo changed — repopulate Color/SYN combo from parts_master.category."""
        if hasattr(self, "all_parts_color_combo"):
            self.all_parts_color_combo.blockSignals(True)
            self.all_parts_color_combo.clear()
            self.all_parts_color_combo.addItem("All Colors")

            seg_display = getattr(self, "all_parts_veh_combo", None)
            seg_display_txt = seg_display.currentText() if seg_display else "All Vehicles"
            # Translate display label → raw DB segment
            seg_raw = getattr(self, "_seg_label_to_raw", {}).get(seg_display_txt, seg_display_txt)

            if mod and mod != "All Models":
                conn = _open_catalog_db(self._catalog_db)
                if conn:
                    try:
                        cur = conn.cursor()
                        # ── KEY FIX: colors live in parts_master.category as
                        #   'PAINTED PARTS / <Color Name>'. Extract and clean them.
                        q = """
                            SELECT DISTINCT
                                REPLACE(pm.category, 'PAINTED PARTS / ', '') AS color
                            FROM parts_master pm
                            JOIN compatibility_map cm ON pm.part_code = cm.part_code
                            JOIN vehicles_master vm ON cm.vehicle_id = vm.vehicle_id
                            WHERE pm.category LIKE 'PAINTED PARTS / %'
                              AND vm.model_name = ?
                        """
                        params = [mod]
                        if seg_display_txt != "All Vehicles":
                            q += " AND vm.segment = ?"
                            params.append(seg_raw)
                        q += " ORDER BY color"
                        cur.execute(q, params)
                        # Title-case each color for clean display
                        colors = [
                            r[0].title() for r in cur.fetchall()
                            if r[0] and r[0].strip()
                        ]
                        if colors:
                            self.all_parts_color_combo.addItems(colors)
                    finally:
                        conn.close()
            self.all_parts_color_combo.blockSignals(False)
        self._populate_all_parts_table()

    # ── Internal helpers for human-readable combo labels ─────────────────────
    @staticmethod
    def _clean_segment_label(seg: str) -> str:
        """Convert raw DB segment value to a human-readable display label.
        e.g. 'PAINTED_MOTORCYCLE' → 'Motorcycle (Painted)', 'MOTORCYCLE' → 'Motorcycle'
        """
        import re as _re
        if not seg:
            return seg
        label = seg.strip()
        painted = False
        if label.upper().startswith("PAINTED_"):
            label = label[8:]   # strip 'PAINTED_'
            painted = True
        label = label.replace("_", " ").title()
        if painted:
            label = f"{label} (Painted)"
        return label

    @staticmethod
    def _clean_color_label(raw_color: str) -> str:
        """Convert a raw SYN/Color string to a clean title-cased display label.
        e.g. 'FUROZIA BLUE' → 'Furozia Blue', 'Wicked Black' → 'Wicked Black'
        """
        if not raw_color:
            return raw_color
        # Strip 'PAINTED PARTS / ' prefix if present
        label = raw_color.strip()
        if label.upper().startswith("PAINTED PARTS / "):
            label = label[16:]
        return label.title()

    @staticmethod
    def _clean_category_label(cat: str) -> str:
        """Convert raw category to short human-readable label.
        'PAINTED PARTS / FUROZIA BLUE' → '🎨 Painted (Furozia Blue)'
        """
        if not cat:
            return cat
        c = cat.strip()
        if c.upper().startswith("PAINTED PARTS / "):
            color = c[16:].title()
            return f"\U0001f3a8 Painted ({color})"
        return c.title()

    def _populate_category_combos(self):
        """Load distinct categories and segments from the catalog DB into dropdowns.
        All labels are cleaned to be human-readable (no raw codes or numeric IDs).
        """
        conn = _open_catalog_db(self._catalog_db)
        if not conn:
            return
        raw_cats = []; raw_segments = []
        try:
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT category FROM parts_master ORDER BY category")
            raw_cats = [r[0] for r in cur.fetchall() if r[0]]

            cur.execute("SELECT DISTINCT segment FROM vehicles_master ORDER BY segment")
            raw_segments = [r[0] for r in cur.fetchall() if r[0]]
        finally:
            conn.close()

        # Build clean category list — shorten PAINTED PARTS / X entries
        # Store mapping: display_label -> raw_db_value (for query use)
        seen_cats = {}  # display → raw
        for raw in raw_cats:
            label = self._clean_category_label(raw)
            # Keep first occurrence (raw value) for each display label
            if label not in seen_cats:
                seen_cats[label] = raw
        clean_cats = sorted(seen_cats.keys())
        # Store reverse map so _populate_all_parts_table can translate back
        self._cat_label_to_raw = seen_cats

        # Build clean segment list — strip PAINTED_ prefix etc.
        # Store mapping: display_label -> raw_db_value
        clean_seg_map = {}  # display → raw
        for raw_seg in raw_segments:
            label = self._clean_segment_label(raw_seg)
            if label not in clean_seg_map:
                clean_seg_map[label] = raw_seg
        clean_segs = sorted(clean_seg_map.keys())
        self._seg_label_to_raw = clean_seg_map

        # ── Common Parts Analyzer combo ──
        if hasattr(self, "category_combo_analyzer"):
            self.category_combo_analyzer.blockSignals(True)
            self.category_combo_analyzer.clear()
            self.category_combo_analyzer.addItem("All Categories")
            self.category_combo_analyzer.addItems(raw_cats)  # analyzer uses raw names
            self.category_combo_analyzer.blockSignals(False)

        # ── All Parts tab category combo (clean labels) ──
        if hasattr(self, "all_parts_cat_combo"):
            self.all_parts_cat_combo.blockSignals(True)
            self.all_parts_cat_combo.clear()
            self.all_parts_cat_combo.addItem("All Categories")
            self.all_parts_cat_combo.addItems(clean_cats)
            self.all_parts_cat_combo.blockSignals(False)

        # ── All Parts tab vehicle combo (clean segment labels) ──
        if hasattr(self, "all_parts_veh_combo"):
            self.all_parts_veh_combo.blockSignals(True)
            self.all_parts_veh_combo.clear()
            self.all_parts_veh_combo.addItem("All Vehicles")
            self.all_parts_veh_combo.addItems(clean_segs)
            self.all_parts_veh_combo.blockSignals(False)

    # Keep old name as alias for back-compat (called from sync handlers)
    def _populate_analyzer_categories(self):
        self._populate_category_combos()

    # ── Data Sync ─────────────────────────────────────────────────────────────
    def _on_import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select CSV/Excel File", "", "CSV/Excel (*.csv *.xlsx *.xls)")
        if not path or not self._catalog_db:
            return
        try:
            from data_importer import import_csv
            count = import_csv(path, self._catalog_db)
            self.sync_log.append(f"✅ Imported {count} rows from {os.path.basename(path)}")
            self._populate_filter_tree()
        except Exception as e:
            self.sync_log.append(f"❌ Import error: {e}")

    def _on_category_changed(self, cat: str):
        self.sync_model.clear()
        self.sync_model.addItem("Select Model...")
        self.sync_model.setEnabled(False)
        self.sync_btn.setEnabled(False)
        if cat in ("SELECT CATEGORY...", ""):
            return
        # ── Always reload settings so the latest saved Dealer ID is used ──
        self._load_settings()
        self.sync_log.append(f"🔄 Fetching models for: {cat} (Dealer: {self._dealer_id})...")
        self._model_worker = ModelFetchWorker(cat, self._dealer_id)
        self._model_worker.finished.connect(self._on_models_fetched)
        self._model_worker.error.connect(lambda e: self.sync_log.append(f"❌ {e}"))
        self._model_worker.start()

    def _on_models_fetched(self, models: list):
        self.sync_model.clear()
        self.sync_model.addItem("ALL MODELS (full category sync)")
        for m in models:
            self.sync_model.addItem(m["name"], userData=m["series"])
        self.sync_model.setEnabled(True)
        self.sync_btn.setEnabled(True)
        self.sync_log.append(f"✅ {len(models)} models fetched")

    def _on_sync_start(self):
        # ── Always reload settings so the latest saved Dealer ID is used ──
        self._load_settings()
        if not self._catalog_db:
            self.sync_log.append("❌ No catalog DB configured — go to Settings")
            return
        cat = self.sync_category.currentText()
        series_id = self.sync_model.currentData()
        self.sync_btn.setEnabled(False)
        self.sync_progress.setVisible(True)
        self.sync_progress.setRange(0, 100)
        self.sync_log.clear()
        self.sync_log.append(f"🚀 Starting sync: {cat} / {self.sync_model.currentText()} (Dealer: {self._dealer_id})")
        self._sync_worker = SyncWorker(self._catalog_db, category=cat, series_id=series_id, dealer_id=self._dealer_id)
        self._sync_worker.progress.connect(lambda m: self.sync_log.append(m))
        self._sync_worker.progress_pct.connect(
            lambda pct, msg: (self.sync_progress.setValue(pct), self.lbl_status.setText(msg))
        )
        self._sync_worker.finished.connect(self._on_sync_done)
        self._sync_worker.error.connect(lambda e: self.sync_log.append(f"❌ {e}"))
        self._sync_worker.start()

    def _on_sync_done(self, stats: dict):
        self.sync_btn.setEnabled(True)
        self.sync_progress.setVisible(False)
        self.sync_log.append("✅ Sync complete!")
        self.lbl_status.setText("✅ Sync complete — refreshing...")
        self._populate_filter_tree()
        self._populate_analyzer_categories()

    # ── Painted Parts Sync ───────────────────────────────────────────────────

    def _on_paint_type_changed(self, vtype: str):
        """When vehicle type changes in Painted Parts panel, fetch its model list."""
        self.paint_model_combo.clear()
        self.paint_model_combo.addItem("ALL MODELS")
        if vtype in ("ALL TYPES", ""):
            return
        self.sync_log.append(f"🎨 Fetching painted models for: {vtype}...")
        self._paint_model_worker = _PaintedModelFetchWorker(vtype, self._dealer_id)
        self._paint_model_worker.finished.connect(self._on_paint_models_fetched)
        self._paint_model_worker.error.connect(
            lambda e: self.sync_log.append(f"⚠️ Model fetch: {e}")
        )
        self._paint_model_worker.start()

    def _on_paint_models_fetched(self, models: list):
        """Populate the painted parts model dropdown."""
        self.paint_model_combo.clear()
        self.paint_model_combo.addItem("ALL MODELS", userData=None)
        for m in models:
            self.paint_model_combo.addItem(m.get("name", m.get("ModelName", "")),
                                           userData=m.get("model_id", m.get("ModelID", "")))
        self.sync_log.append(f"✅ {len(models)} painted models fetched")

    def _on_painted_sync_start(self):
        """Launch Painted Parts sync in background thread."""
        if not self._catalog_db:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "No DB", "Catalog DB not configured.")
            return

        # Read which vehicle type was selected (None = all types)
        vtype_sel = self.paint_type_combo.currentText()
        vehicle_type = None if vtype_sel == "ALL TYPES" else vtype_sel

        # Read which model was selected (None = all models)
        model_id = self.paint_model_combo.currentData()  # None for "ALL MODELS"
        model_label = self.paint_model_combo.currentText()

        self.paint_sync_btn.setEnabled(False)
        self.sync_progress.setVisible(True)
        self.sync_progress.setRange(0, 100)
        self.sync_log.clear()
        label = vtype_sel if vehicle_type else "ALL vehicle types"
        if model_id:
            label += f" / {model_label}"
        self.sync_log.append(f"🎨 Starting Painted Parts sync — {label}...")

        self._painted_worker = _PaintedSyncWorker(
            self._catalog_db, self._dealer_id,
            vehicle_type=vehicle_type, model_id=model_id
        )
        self._painted_worker.progress.connect(lambda m: self.sync_log.append(m))
        self._painted_worker.progress_pct.connect(
            lambda pct, msg: (self.sync_progress.setValue(pct), self.lbl_status.setText(msg))
        )
        self._painted_worker.finished.connect(self._on_painted_sync_done)
        self._painted_worker.error.connect(lambda e: self.sync_log.append(f"❌ {e}"))
        self._painted_worker.start()

    def _on_painted_sync_done(self):
        self.paint_sync_btn.setEnabled(True)
        self.sync_progress.setVisible(False)
        self.sync_log.append("✅ Painted Parts sync complete!")
        self.lbl_status.setText("✅ Painted Parts done — refreshing...")
        self._populate_filter_tree()
        self._populate_analyzer_categories()


class _PaintedSyncWorker(QThread):
    """Background thread that runs `run_painted_parts_sync`."""
    progress     = pyqtSignal(str)
    progress_pct = pyqtSignal(int, str)
    finished     = pyqtSignal()
    error        = pyqtSignal(str)

    def __init__(self, db_path: str, dealer_id: str,
                 vehicle_type: str = None, model_id: str = None):
        super().__init__()
        self._db_path      = db_path
        self._dealer_id    = dealer_id
        self._vehicle_type = vehicle_type   # None → sync ALL types
        self._model_id     = model_id       # None → sync ALL models

    def run(self):
        try:
            from api_sync_engine import run_painted_parts_sync

            def cb(pct, msg):
                self.progress_pct.emit(pct, msg)
                self.progress.emit(f"[{pct}%] {msg}")

            run_painted_parts_sync(
                db_path=self._db_path,
                dealer_id=self._dealer_id,
                vehicle_type=self._vehicle_type,
                model_id=self._model_id,
                progress_callback=cb,
            )
            self.finished.emit()
        except Exception as exc:
            self.error.emit(str(exc))
            self.finished.emit()


class _PaintedModelFetchWorker(QThread):
    """
    Background thread that fetches the painted-parts model list
    for a given vehicle type from the TVS API.
    Mirrors ModelFetchWorker but calls get_painted_models() instead.
    """
    finished = pyqtSignal(list)
    error    = pyqtSignal(str)

    def __init__(self, vehicle_type: str, dealer_id: str):
        super().__init__()
        self._vehicle_type = vehicle_type
        self._dealer_id    = dealer_id

    def run(self):
        try:
            import re as _re

            from api_sync_engine import TVSApiClient, _force_dict, _safe_str
            client = TVSApiClient(self._dealer_id)
            client.connect()

            # Use the correct API method — get_painted_models() does NOT exist.
            # get_painted_models_with_colors() returns:
            #   { "models": innerDate entries (names),
            #     "colors": imageData entries (ModelID + ColorID pairs) }
            result = client.get_painted_models_with_colors(vehicle_type=self._vehicle_type)
            model_entries = result.get("models", [])
            color_entries = result.get("colors", [])

            # ── Build model_id → readable name from innerDate ─────────────────
            # IMPORTANT: The API's 'name' field in innerDate is a useless group code
            # (e.g. "001001"), NOT a model name. The real name is in the image URL,
            # e.g. ".../LOGO-BUTTON-160-2v.png" → extract "160 2V".
            # Also: ModelIDs may have leading spaces — always .strip() them.
            _SKIP_UI = {
                "go button", "o button", "button", "icon", "logo", "bg",
                "background", "arrow", "menu", "nav", "left arrow",
                "right arrow", "home", "back", "logo button",
                "cover page", "cover", "page",
            }
            _LOGO_PREFIXES = ("logo button ", "logo ", "button ")
            _LOGO_SUFFIXES = (" logo button", " logo", " button")

            def _name_from_url(url: str) -> str:
                """Extract a readable model label from a TVS image URL filename."""
                if not url:
                    return ""
                tail = url.rstrip("/").split("/")[-1]
                tail = _re.sub(r'\.(png|jpg|gif|svg|webp)$', '', tail, flags=_re.I)
                tail = tail.replace("-", " ").replace("_", " ").strip()
                # Strip logo-button PREFIX, e.g. "LOGO BUTTON 160 2V" → "160 2V"
                for pfx in _LOGO_PREFIXES:
                    if tail.lower().startswith(pfx):
                        tail = tail[len(pfx):].strip()
                        break
                # Strip logo-button SUFFIX, e.g. "160 4V LOGO BUTTON" → "160 4V"
                for sfx in _LOGO_SUFFIXES:
                    if tail.lower().endswith(sfx):
                        tail = tail[:-len(sfx)].strip()
                        break
                if tail.lower() in _SKIP_UI or len(tail) <= 2:
                    return ""
                # Must contain at least one letter (exclude pure numbers like "001001")
                if not _re.search(r'[A-Za-z]', tail):
                    return ""
                return tail.upper()

            model_cache: dict = {}
            for m in model_entries:
                m = _force_dict(m)
                # Strip whitespace from ModelID — TVS API sometimes adds leading spaces
                mid = _safe_str(m.get("ModelID") or "").strip()
                if not mid:
                    continue
                # Prefer name from image URL (more reliable than 'name' field)
                name = _name_from_url(_safe_str(m.get("image") or ""))
                if not name:
                    name = _name_from_url(_safe_str(m.get("image2") or ""))
                if not name:
                    # Last resort: s_levelName if it looks like a real name
                    lvl = _safe_str(m.get("s_levelName") or "")
                    if _re.search(r'[A-Za-z]{3,}', lvl):
                        name = lvl
                if name and mid not in model_cache:
                    model_cache[mid] = name

            # ── Deduplicate ModelIDs from color entries ───────────────────────
            # Note: color entry ModelIDs may also have leading spaces — strip them.
            seen_mids: set = set()
            used_names: set = set()
            models: list = []
            
            for entry in color_entries:
                entry = _force_dict(entry)
                mid = _safe_str(entry.get("ModelID") or "").strip()
                if not mid or mid in seen_mids:
                    continue
                seen_mids.add(mid)
                
                base_name = model_cache.get(mid, "")
                if not base_name:
                    # Use last 8 chars to reduce duplicate labels (IDs are 18 chars long)
                    base_name = f"Model #{mid[-8:]}" if len(mid) >= 8 else mid
                
                # Ensure the display name is unique in the dropdown
                final_name = base_name
                counter = 2
                while final_name in used_names:
                    final_name = f"{base_name} ({counter})"
                    counter += 1
                
                used_names.add(final_name)
                models.append({"name": final_name, "model_id": mid})

            # Sort alphabetically by name for easy browsing
            models.sort(key=lambda x: x["name"])
            self.finished.emit(models)
        except Exception as exc:
            self.error.emit(str(exc))
            self.finished.emit([])
