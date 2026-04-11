from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem, 
                             QPushButton, QHeaderView, QTabWidget, QAbstractItemView, QFrame, QLineEdit, 
                             QDialog, QFormLayout, QFileDialog, QCheckBox, QCompleter, QComboBox, QDoubleSpinBox, QDateEdit, QMessageBox, QGridLayout, QDoubleSpinBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QDate
from PyQt6.QtGui import QColor
from pandas import DataFrame
import pandas as pd
import ui_theme
from styles import (STYLE_TABLE_CYBER, STYLE_INPUT_CYBER, COLOR_ACCENT_CYAN, 
                   COLOR_SURFACE, COLOR_TEXT_PRIMARY, DIM_MARGIN_STD, DIM_SPACING_STD, COLOR_ACCENT_GREEN, 
                   STYLE_TAB_WIDGET, STYLE_GLASS_PANEL, COLOR_ACCENT_RED, COLOR_ACCENT_YELLOW,
                   STYLE_DROPDOWN_CYBER)
from logger import app_logger
from custom_components import ProMessageBox, ProDialog, ProTableDelegate
from vendor_manager import VendorManagerDialog, VendorManagerWidget
from report_generator import ReportGenerator
from whatsapp_helper import send_po_msg, send_report_msg
from auto_enrich_worker import AutoEnrichWorker

class _POCard(QWidget):
    """Custom QWidget for PO list rows that captures right-click reliably.
    All child label events are made transparent so the click always reaches here."""
    def __init__(self, po_id, menu_callback, parent=None):
        super().__init__(parent)
        self._po_id = po_id
        self._menu_callback = menu_callback

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self._menu_callback(self._po_id)
            event.accept()
        else:
            super().mousePressEvent(event)


class PODataThread(QThread):
    data_loaded = pyqtSignal(list)
    
    def __init__(self, db_manager, method_name):
        super().__init__()
        self.db_manager = db_manager
        self.method_name = method_name
        
    def run(self):
        if self.method_name == "get_open_po_items":
            data = self.db_manager.get_open_po_items()
            self.data_loaded.emit(data)
        elif self.method_name == "get_backlog_items":
            data = self.db_manager.get_backlog_items()
            self.data_loaded.emit(data)

class CatalogImportThread(QThread):
    progress = pyqtSignal(int, str) # value, message
    finished = pyqtSignal(bool, str, list, list) # success, message, data(list of dicts for UI), extra_col_names
    
    def __init__(self, file_path, vendor_name, db_manager):
        super().__init__()
        self.file_path = file_path
        self.vendor_name = vendor_name
        self.db_manager = db_manager
        
    def run(self):
        import json
        try:
            self.progress.emit(10, "Scanning Data Structure...")
            
            # 1. Read File
            if self.file_path.endswith('.csv'):
                df = pd.read_csv(self.file_path)
            else:
                df = pd.read_excel(self.file_path)
                
            self.progress.emit(30, "Normalizing Columns...")
            
            # Keep original column names for display (title case)
            original_columns = [str(c).strip() for c in df.columns]
            
            # Normalize columns for matching
            df.columns = [str(c).strip().lower() for c in df.columns]
            
            # Create mapping: normalized -> original
            col_name_map = {norm: orig for norm, orig in zip(df.columns, original_columns)}
            
            # Smart column matching: exact > word-boundary > substring
            import re
            def find_col(keywords, exclude=None):
                """Find best matching column. Tries exact match, then word match, then substring."""
                if exclude is None:
                    exclude = set()
                candidates = [c for c in df.columns if c not in exclude]
                
                # Pass 1: Exact match (column name IS the keyword)
                for k in keywords:
                    for col in candidates:
                        if col == k:
                            return col
                
                # Pass 2: Word-boundary match (keyword is a whole word in column)
                for k in keywords:
                    pattern = r'(?:^|[\s_\-])' + re.escape(k) + r'(?:$|[\s_\-])'
                    for col in candidates:
                        if re.search(pattern, col):
                            return col
                
                # Pass 3: Starts-with match
                for k in keywords:
                    for col in candidates:
                        if col.startswith(k):
                            return col
                
                # Pass 4: Substring match (only for multi-word keywords, skip single short ones)
                for k in keywords:
                    if len(k) >= 4:  # Only match substrings for longer keywords
                        for col in candidates:
                            if k in col:
                                return col
                
                return None
            
            # Find columns in order: name first (required), then others excluding already-found
            col_name = find_col(['part name', 'part_name', 'partname', 'name', 'description', 'item name', 'item'])
            found = {col_name} if col_name else set()
            
            col_id = find_col(['part code', 'part_code', 'partcode', 'part id', 'part_id', 'partid', 'sr no', 'sr.no', 'sno', 'code'], exclude=found)
            found.add(col_id)
            
            col_price = find_col(['mrp', 'price', 'rate', 'cost', 'amount', 'unit price', 'unit_price'], exclude=found)
            found.add(col_price)
            
            col_qty = find_col(['qty', 'quantity', 'moq', 'pack', 'stock'], exclude=found)
            found.add(col_qty)
            found.discard(None)
            
            if not col_name:
                self.finished.emit(False, "Could not find 'Part Name' column.", [], [])
                return

            # Identify EXTRA columns (not mapped to fixed fields)
            extra_cols = [c for c in df.columns if c not in found]
            extra_col_display_names = [col_name_map.get(c, c.title()) for c in extra_cols]

            # Prepare Data
            all_parts = self.db_manager.get_all_parts() 
            name_map = {str(p[1]).lower(): p for p in all_parts} # Name -> Part
            id_map = {str(p[0]).lower(): p for p in all_parts}   # ID -> Part
            
            items_to_save = [] # For DB (code, name, price, stock, extra_json)
            ids_to_link_vendor = [] # List of part IDs to update vendor_name in main inventory
            ui_items = []      # For UI (dict with all fields)
            
            total_rows = len(df)
            processed = 0
            
            # Aggregate duplicates by part name (sum quantities)
            from collections import OrderedDict
            aggregated = OrderedDict()  # name_lower -> {data}
            
            for _, row in df.iterrows():
                processed += 1
                if processed % 50 == 0 or processed == total_rows:
                    prog = 30 + int((processed / total_rows) * 50)
                    self.progress.emit(prog, f"Processing Row {processed}/{total_rows}...")
                
                name = str(row[col_name]).strip() if col_name else ""
                if not name or name.lower() in ['nan', 'none', '']: continue
                
                # ID
                p_id = str(row[col_id]).strip() if col_id else "NEW"
                if p_id.lower() in ['nan', 'none', '']: p_id = "NEW"
                
                # Price
                price = 0.0
                if col_price:
                    try: price = float(row[col_price])
                    except: price = 0.0
                
                # Qty
                sheet_qty = 0
                if col_qty:
                    try: sheet_qty = float(row[col_qty])
                    except: sheet_qty = 0
                
                # Collect extra column data
                extra_data = {}
                for ec in extra_cols:
                    val = row[ec]
                    if pd.notna(val):
                        extra_data[col_name_map.get(ec, ec)] = str(val).strip()
                    else:
                        extra_data[col_name_map.get(ec, ec)] = ""
                
                extra_json = json.dumps(extra_data) if extra_data else None
                
                # Compound key: part_code + name.
                # Same code + same name = truly identical row (merge/sum qty).
                # Same code + different name = distinct variant (keep both, do NOT merge).
                key = f"{p_id.lower()}||{name.lower()}"

                if key in aggregated:
                    aggregated[key]["qty"] += sheet_qty
                    # Keep the latest price
                    if price > 0:
                        aggregated[key]["price"] = price
                    # Merge extra data
                    if extra_data:
                        aggregated[key]["extra"].update(extra_data)
                        aggregated[key]["extra_json"] = json.dumps(aggregated[key]["extra"])
                else:
                    aggregated[key] = {
                        "p_id": p_id, "name": name, "price": price,
                        "qty": sheet_qty, "extra": extra_data, "extra_json": extra_json
                    }
            
            # Build final lists from aggregated data
            for key, data in aggregated.items():
                p_id = data["p_id"]
                name = data["name"]
                price = data["price"]
                sheet_qty = data["qty"]
                extra_data = data["extra"]
                extra_json = data["extra_json"]
                
                # DB Match Logic
                existing = None
                
                # 1. Try Match by ID
                if p_id != "NEW":
                    existing = id_map.get(p_id.lower())
                
                # 2. Try Match by Name (Fallback)
                if not existing and name:
                     existing = name_map.get(name.lower())
                
                db_reorder = 0
                db_stock = 0
                
                if existing:
                    db_id = existing[0]
                    db_stock = existing[2]
                    db_reorder = existing[3]
                    disp_id = db_id
                    disp_stock = db_stock
                    
                    # Update ID if we found a match in DB
                    p_id = db_id
                else:
                    disp_id = p_id
                    disp_stock = 0
                
                # Add to DB Batch (code, name, price, stock, extra_json)
                items_to_save.append((p_id, name, price, sheet_qty, extra_json))
                
                if p_id != "NEW":
                    ids_to_link_vendor.append(p_id)
                
                # Add to UI List
                # Stock = vendor's available qty from Excel
                # Order Qty = 0 (user fills in what they want to order)
                ui_item = {
                    "id": disp_id,
                    "name": name,
                    "stock": sheet_qty, 
                    "price": price,
                    "reorder": db_reorder,
                    "qty": 0,
                    "extra": extra_data
                }
                ui_items.append(ui_item)

            self.progress.emit(85, "Saving to Neural Core...")
            
            # Bulk Save
            if items_to_save:
                success, msg = self.db_manager.save_catalog_items_bulk(self.vendor_name, items_to_save)
                if not success:
                    self.finished.emit(False, msg, [], [])
                    return
                
                # Link vendors in main inventory
                if ids_to_link_vendor:
                    self.db_manager.update_part_vendors_bulk(self.vendor_name, ids_to_link_vendor)
            
            # Save column definitions for this vendor
            self.db_manager.save_vendor_catalog_columns(self.vendor_name, extra_col_display_names)
            
            self.progress.emit(100, "Import Complete.")
            self.finished.emit(True, f"Imported {len(items_to_save)} items successfully.", ui_items, extra_col_display_names)
            
        except Exception as e:
            app_logger.error(f"Thread Error: {e}")
            self.finished.emit(False, str(e), [], [])


class BatteryProgressDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(450, 280)
        
        # Setup smooth animation timer
        self.current_progress = 0
        self.target_progress = 0
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.animate_progress)
        self.anim_timer.start(20)  # 50 FPS smooth animation
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Main Frame
        self.frame = QFrame()
        self.frame.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 rgba(5, 8, 12, 0.95), 
                    stop:1 rgba(2, 5, 10, 0.95));
                border: 2px solid {COLOR_ACCENT_CYAN};
                border-radius: 12px;
            }}
        """)
        fr_layout = QVBoxLayout(self.frame)
        fr_layout.setSpacing(20)
        fr_layout.setContentsMargins(25, 25, 25, 25)
        
        # Title
        lbl_title = QLabel("◢ SYSTEM IMPORT ◣")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_title.setStyleSheet(f"""
            color: {COLOR_ACCENT_CYAN}; 
            font-weight: bold; 
            font-size: 18px; 
            letter-spacing: 3px;
            font-family: 'Orbitron', 'Segoe UI', sans-serif;
        """)
        fr_layout.addWidget(lbl_title)
        
        # Progress Bar Container (Custom painted)
        self.progress_widget = QWidget()
        self.progress_widget.setFixedHeight(70)
        self.progress_widget.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(0, 0, 0, 0.8),
                    stop:1 rgba(10, 15, 25, 0.8));
                border: 2px solid rgba(0, 242, 255, 0.3);
                border-radius: 6px;
            }}
        """)
        
        # Progress bar layout
        prog_layout = QVBoxLayout(self.progress_widget)
        prog_layout.setContentsMargins(4, 4, 4, 4)
        
        # Inner fill bar
        self.fill_bar = QLabel()
        self.fill_bar.setFixedHeight(60)
        self.fill_bar.setStyleSheet("background: transparent;")
        prog_layout.addWidget(self.fill_bar)
        
        fr_layout.addWidget(self.progress_widget)
        
        # Percentage & Status
        self.lbl_percent = QLabel("0%")
        self.lbl_percent.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_percent.setStyleSheet(f"""
            color: {COLOR_ACCENT_CYAN}; 
            font-size: 28px; 
            font-weight: bold; 
            font-family: 'Consolas', monospace;
            letter-spacing: 2px;
        """)
        fr_layout.addWidget(self.lbl_percent)
        
        self.lbl_status = QLabel("Initializing...")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet(f"""
            color: rgba(0, 242, 255, 0.7); 
            font-size: 13px;
            letter-spacing: 1px;
        """)
        fr_layout.addWidget(self.lbl_status)
        
        layout.addWidget(self.frame)
        
    def animate_progress(self):
        """Smooth animation interpolation"""
        if self.current_progress < self.target_progress:
            # Ease-out animation
            diff = self.target_progress - self.current_progress
            self.current_progress += diff * 0.15  # Smooth acceleration
            if diff < 0.5:
                self.current_progress = self.target_progress
            self.update_fill()
    
    def update_progress(self, val, msg):
        self.target_progress = val
        self.lbl_percent.setText(f"{int(val)}%")
        self.lbl_status.setText(msg)
        
    def update_fill(self):
        """Update the fill bar with gradient"""
        width_percent = self.current_progress
        
        # Create gradient fill with glow effect
        gradient_style = f"""
            QLabel {{
                background: qlineargradient(x1:0, y1:0 , x2:1, y2:0,
                    stop:0 rgba(0, 242, 255, 0.6),
                    stop:0.5 rgba(0, 242, 255, 0.8),
                    stop:1 rgba(0, 200, 255, 0.6));
                border: 1px solid {COLOR_ACCENT_CYAN};
                border-radius: 4px;
            }}
        """
        
        if width_percent > 0:
            # Calculate actual pixel width
            max_width = self.progress_widget.width() - 12  # Account for padding
            fill_width = int((width_percent / 100) * max_width)
            self.fill_bar.setFixedWidth(fill_width)
            self.fill_bar.setStyleSheet(gradient_style)
        else:
            self.fill_bar.setFixedWidth(0)
            self.fill_bar.setStyleSheet("background: transparent;")

class ReceiveItemDialog(ProDialog):
    def __init__(self, parent=None, item_data=None, is_bulk=False):
        super().__init__(parent, title="RECEIVE ITEMS", width=400, height=380)
        self.item_data = item_data # (id, po_id, supplier, part_name, ordered, received, pending, part_id)
        self.is_bulk = is_bulk
        
        # Content Widget
        content_widget = QWidget()
        layout = QFormLayout(content_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        
        # Styles
        lbl_style = f"color: {COLOR_TEXT_PRIMARY}; font-size: 13px; font-weight: bold;"
        val_style = f"color: {COLOR_ACCENT_CYAN}; font-size: 13px;"
        
        self.lbl_part = QLabel(item_data[3])
        self.lbl_part.setStyleSheet(val_style)
        
        self.lbl_ordered = QLabel(str(item_data[4]))
        self.lbl_ordered.setStyleSheet(val_style)
        
        self.lbl_pending = QLabel(str(item_data[6]))
        self.lbl_pending.setStyleSheet(val_style)
        
        self.in_qty = QLineEdit()
        self.in_qty.setText(str(item_data[6]))          # Pre-fill with pending qty (editable)
        self.in_qty.setPlaceholderText(f"Max: {item_data[6]}")
        self.in_qty.setStyleSheet(ui_theme.get_lineedit_style())
        self.in_qty.setFixedHeight(35)
        
        self.in_price = QLineEdit()
        self.in_price.setPlaceholderText("Enter New Buy Price")
        self.in_price.setStyleSheet(ui_theme.get_lineedit_style())
        self.in_price.setFixedHeight(35)

        # Auto-fill Price from PO ordered_price
        try:
            line_item_id = item_data[0]  # First element is the po_items.id
            if parent and hasattr(parent, 'db_manager'):
                # Query po_items for ordered_price
                conn = parent.db_manager.get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT ordered_price FROM po_items WHERE id = ?", (line_item_id,))
                result = cursor.fetchone()
                conn.close()
                
                if result and result[0] and result[0] > 0:
                    self.in_price.setText(f"{float(result[0]):.2f}")
                else:
                    # Fallback: Try last_cost from inventory (index 13)
                    part_id = item_data[7]
                    part = parent.db_manager.get_part_by_id(part_id)
                    if part:
                        # Explicit SELECT column order: 3=unit_price, 17=last_cost
                        last_cost = float(part[17]) if len(part) > 17 and part[17] else 0.0
                        unit_price = float(part[3]) if len(part) > 3 and part[3] else 0.0
                        best_price = last_cost if last_cost > 0 else unit_price
                        if best_price > 0:
                            self.in_price.setText(f"{best_price:.2f}")
        except Exception as e:
            app_logger.error(f"Error pre-filling price: {e}")
        
        # Labels
        def make_lbl(text):
            l = QLabel(text)
            l.setStyleSheet(lbl_style)
            return l

        layout.addRow(make_lbl("Part Name:"), self.lbl_part)
        layout.addRow(make_lbl("Ordered:"), self.lbl_ordered)
        layout.addRow(make_lbl("Pending:"), self.lbl_pending)
        layout.addRow(make_lbl("Receive Qty:"), self.in_qty)
        layout.addRow(make_lbl("Buy Price (₹):"), self.in_price)
        
        self.set_content(content_widget)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_cancel = QPushButton("CANCEL")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setStyleSheet(ui_theme.get_cancel_button_style())
        btn_cancel.clicked.connect(self.reject)
        
        btn_ok = QPushButton("RECEIVE")
        btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_ok.setStyleSheet(ui_theme.get_primary_button_style())
        btn_ok.clicked.connect(self.accept)
        
        if self.is_bulk:
            btn_skip = QPushButton("SKIP ITEM")
            btn_skip.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_skip.setStyleSheet("background: rgba(255,255,255,0.1); color: #ccc; border: 1px solid #555; border-radius: 4px; padding: 6px 12px;")
            btn_skip.clicked.connect(lambda: self.done(2)) # 2 = Skip
            
            btn_cancel.setText("ABORT BULK")
            btn_cancel.clicked.disconnect()
            btn_cancel.clicked.connect(lambda: self.done(0)) # 0 = Abort All (Reject)
            
            btn_ok.clicked.disconnect()
            btn_ok.clicked.connect(lambda: self.done(1)) # 1 = Receive (Accept)
            
            btn_layout.addWidget(btn_cancel)
            btn_layout.addWidget(btn_skip)
            btn_layout.addWidget(btn_ok)
        else:
            btn_layout.addWidget(btn_cancel)
            btn_layout.addWidget(btn_ok)
        
        self.add_buttons(btn_layout)
        
    def get_data(self):
        try:
            qty_text = self.in_qty.text().strip()
            if not qty_text:
                return None, None   # Guard: user left qty blank

            qty = float(qty_text)
            price_text = self.in_price.text().strip()

            if not price_text:
                return None, None  # Guard: price left blank

            price = float(price_text)

            if qty <= 0:
                return None, None  # Guard: nonsense quantity

            # Validate: cannot receive more than pending
            max_pending = float(self.item_data[6]) if self.item_data else 0.0
            if max_pending > 0 and qty > max_pending:
                qty = max_pending  # Cap at pending

            return qty, price
        except ValueError:
            return None, None

class BulkReceiveDialog(QDialog):
    def __init__(self, parent, db_manager, items_data):
        super().__init__(parent)
        self.setWindowTitle("Bulk Receive Items")
        self.resize(850, 500)
        self.setStyleSheet(f"background-color: {COLOR_SURFACE}; color: {COLOR_TEXT_PRIMARY};")
        self.db_manager = db_manager
        self.items_data = items_data
        
        layout = QVBoxLayout(self)
        
        # Table
        self.table = QTableWidget()
        cols = ["Part Name", "Ordered", "Prev Rcvd", "Pending", "Receiving NOW", "Buy Price (₹)"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setStyleSheet(STYLE_TABLE_CYBER)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 6):
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        
        self.table.setRowCount(len(self.items_data))
        for r, row_data in enumerate(self.items_data):
            # item_data = (id, po_id, supplier, part_name, qty_ordered, qty_received, pending, part_id)
            po_item_id = row_data[0]
            part_name = row_data[3]
            ordered = str(row_data[4])
            prev_rcvd = str(row_data[5] if row_data[5] else 0)
            pending = float(row_data[6])
            part_id = row_data[7]
            
            p_name_item = QTableWidgetItem(part_name)
            # Store primary keys in item data
            p_name_item.setData(Qt.ItemDataRole.UserRole, (po_item_id, part_id))
            
            p_ord_item = QTableWidgetItem(ordered)
            p_ord_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            p_prv_item = QTableWidgetItem(prev_rcvd)
            p_prv_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            p_prv_item.setForeground(QColor("#8899aa")) # Dim color for prev rcvd
            
            p_pen_item = QTableWidgetItem(f"{round(pending, 3):g}")
            p_pen_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            self.table.setItem(r, 0, p_name_item)
            self.table.setItem(r, 1, p_ord_item)
            self.table.setItem(r, 2, p_prv_item)
            self.table.setItem(r, 3, p_pen_item)
            
            # Use QDoubleSpinBox for Qty — pre-filled with pending (most common: receive full pending shipment)
            # User can edit DOWN for partial receives.
            spin_qty = QDoubleSpinBox()
            spin_qty.setDecimals(2)
            spin_qty.setSingleStep(1.0)
            spin_qty.setStyleSheet(ui_theme.get_lineedit_style() + " QDoubleSpinBox { padding: 4px; }")
            spin_qty.setRange(0, 999999.99)
            spin_qty.setValue(pending)
            spin_qty.setFixedWidth(80)
            
            qty_cw = QWidget()
            qty_cl = QHBoxLayout(qty_cw)
            qty_cl.setContentsMargins(4, 2, 4, 2)
            qty_cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            qty_cl.addWidget(spin_qty)
            self.table.setCellWidget(r, 4, qty_cw)
            
            # Use QDoubleSpinBox for Price
            spin_price = QDoubleSpinBox()
            spin_price.setStyleSheet(ui_theme.get_lineedit_style() + " QDoubleSpinBox { padding: 4px; }")
            spin_price.setRange(0, 999999.99)
            spin_price.setDecimals(2)
            spin_price.setFixedWidth(100)
            
            # Try to get best price
            best_price = 0.0
            try:
                conn = self.db_manager.get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT ordered_price FROM po_items WHERE id = ?", (po_item_id,))
                res = cursor.fetchone()
                if res and res[0] and float(res[0]) > 0:
                    best_price = float(res[0])
                else:
                    part = self.db_manager.get_part_by_id(part_id)
                    if part:
                        # Explicit SELECT column order: 3=unit_price, 17=last_cost
                        last_cost = float(part[17]) if len(part) > 17 and part[17] else 0.0
                        unit_price = float(part[3]) if len(part) > 3 and part[3] else 0.0
                        best_price = last_cost if last_cost > 0 else unit_price
            except Exception as e:
                pass
            finally:
                if 'conn' in locals():
                    try:
                        conn.close()
                    except:
                        pass
                
            spin_price.setValue(best_price)
            
            price_cw = QWidget()
            price_cl = QHBoxLayout(price_cw)
            price_cl.setContentsMargins(4, 2, 4, 2)
            price_cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            price_cl.addWidget(spin_price)
            self.table.setCellWidget(r, 5, price_cw)
            
            # Make readonly
            for c in range(4):
                it = self.table.item(r, c)
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)

        layout.addWidget(self.table)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_cancel = QPushButton("CANCEL")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setStyleSheet(ui_theme.get_cancel_button_style())
        btn_cancel.clicked.connect(self.reject)
        
        btn_ok = QPushButton("RECEIVE ALL (VALID)")
        btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_ok.setStyleSheet(ui_theme.get_neon_action_button())
        btn_ok.clicked.connect(self.accept)
        
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)
        
    def get_received_data(self):
        results = []
        for r in range(self.table.rowCount()):
            item_name = self.table.item(r, 0)
            po_item_id, part_id = item_name.data(Qt.ItemDataRole.UserRole)

            qty_cw   = self.table.cellWidget(r, 4)
            price_cw = self.table.cellWidget(r, 5)

            spin_qty   = qty_cw.findChild(QDoubleSpinBox) if qty_cw else None
            spin_price = price_cw.findChild(QDoubleSpinBox) if price_cw else None

            # Force spinbox to commit any pending keyboard input before reading
            if spin_qty: spin_qty.interpretText()
            if spin_price: spin_price.interpretText()

            qty   = spin_qty.value()   if spin_qty   else 0
            price = spin_price.value() if spin_price else 0.0

            if qty > 0 and price >= 0:
                results.append((po_item_id, part_id, qty, price))
        return results


class SupplierProfileDialog(QDialog):
    def __init__(self, parent=None, vendor_name="", db_manager=None):
        super().__init__(parent)
        self.setWindowTitle(f"Supplier Profile: {vendor_name}")
        self.resize(950, 700)
        self.setStyleSheet(f"background-color: {COLOR_SURFACE}; color: {COLOR_TEXT_PRIMARY};")
        self.db_manager = db_manager
        self.vendor_name = vendor_name
        
        self.setup_ui()
        
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # Check if focus is on a button
            focus_widget = QApplication.focusWidget()
            if isinstance(focus_widget, QPushButton):
                super().keyPressEvent(event)
            else:
                # Ignore enter for everything else (like Table cells) to prevent closing
                return
        super().keyPressEvent(event)
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Fetch Data
        details = self.db_manager.get_vendor_details(self.vendor_name)
        stats = self.db_manager.get_vendor_stats(self.vendor_name)
        
        # details: id, name, rep, phone, address, gstin, notes
        rep_name = details[2] if details else "N/A"
        phone = details[3] if details else "N/A"
        total_spend = stats.get('total_spend', 0)
        
        # --- COMPACT HEADER ---
        header_frame = QFrame()
        header_frame.setStyleSheet(STYLE_GLASS_PANEL)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(20, 15, 20, 15)
        
        # 1. Name & Badge
        v_layout = QVBoxLayout()
        lbl_name = QLabel(self.vendor_name)
        lbl_name.setStyleSheet(ui_theme.get_page_title_style())
        v_layout.addWidget(lbl_name)
        
        lbl_badge = QLabel("OFFICIAL VENDOR")
        lbl_badge.setStyleSheet(ui_theme.get_page_title_style())
        lbl_badge.setFixedSize(110, 20)
        lbl_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v_layout.addWidget(lbl_badge)
        header_layout.addLayout(v_layout)
        
        header_layout.addSpacing(30)
        
        # 2. Key Details (Horizontal)
        def make_info(label, value, icon="🔹"):
            l = QLabel(f"{icon} <b>{label}:</b> <span style='color:{COLOR_TEXT_PRIMARY}'>{value}</span>")
            l.setStyleSheet(ui_theme.get_page_title_style())
            return l
            
        info_layout = QGridLayout()
        info_layout.setHorizontalSpacing(30)
        info_layout.setVerticalSpacing(10)
        info_layout.addWidget(make_info("Rep", rep_name, "👤"), 0, 0)
        info_layout.addWidget(make_info("Phone", phone, "📞"), 1, 0)
        info_layout.addWidget(make_info("Spend", f"₹{total_spend:,.0f}", "💰"), 0, 1)
        info_layout.addWidget(make_info("Open POs", stats.get('open_pos', 0), "📦"), 1, 1)
        
        header_layout.addLayout(info_layout)
        header_layout.addStretch()
        
        # Close Button (Top Right)
        btn_close = QPushButton("✖")
        btn_close.setFixedSize(30, 30)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(ui_theme.get_page_title_style())
        btn_close.clicked.connect(self.accept)
        header_layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignTop)
        
        layout.addWidget(header_frame)
        
        # --- MAIN CONTENT TABS ---
        tabs = QTabWidget()
        tabs.setStyleSheet(STYLE_TAB_WIDGET)
        
        # Tab A: History
        tab_hist = QWidget()
        l_hist = QVBoxLayout(tab_hist)
        l_hist.setContentsMargins(DIM_MARGIN_STD, DIM_MARGIN_STD, DIM_MARGIN_STD, DIM_MARGIN_STD)
        l_hist.setSpacing(DIM_SPACING_STD)
        
        # Filters
        filter_layout = QHBoxLayout()
        self.date_start = QDateEdit()
        self.date_start.setCalendarPopup(True)
        self.date_start.setDisplayFormat("yyyy-MM-dd")
        self.date_start.setDate(QDate.currentDate().addDays(-365))
        self.date_start.setStyleSheet(ui_theme.get_lineedit_style())
        self.date_start.setFixedWidth(120)
        
        self.date_end = QDateEdit()
        self.date_end.setCalendarPopup(True)
        self.date_end.setDisplayFormat("yyyy-MM-dd")
        self.date_end.setDate(QDate.currentDate())
        self.date_end.setStyleSheet(ui_theme.get_lineedit_style())
        self.date_end.setFixedWidth(120)
        
        self.txt_po_search = QLineEdit()
        self.txt_po_search.setPlaceholderText("Search PO ID...")
        self.txt_po_search.setStyleSheet(ui_theme.get_lineedit_style())
        
        btn_filter = QPushButton("SEARCH")
        btn_filter.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_filter.setStyleSheet(ui_theme.get_primary_button_style())
        btn_filter.clicked.connect(self.load_history)
        
        btn_export = QPushButton("📤 Export Report")
        btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_export.setStyleSheet(ui_theme.get_primary_button_style())
        btn_export.clicked.connect(self.export_orders_pdf)
        
        filter_layout.addWidget(QLabel("From:"))
        filter_layout.addWidget(self.date_start)
        filter_layout.addWidget(QLabel("To:"))
        filter_layout.addWidget(self.date_end)
        filter_layout.addWidget(self.txt_po_search)
        filter_layout.addWidget(btn_filter)
        filter_layout.addWidget(btn_export)
        l_hist.addLayout(filter_layout)
        
        self.table_hist = QTableWidget()
        cols_h = ["PO ID", "Date", "Status", "Items", "Total Amount"]
        self.table_hist.setColumnCount(len(cols_h))
        self.table_hist.setHorizontalHeaderLabels(cols_h)
        self.table_hist.setStyleSheet(ui_theme.get_table_style())
        self.table_hist.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        l_hist.addWidget(QLabel("ORDER HISTORY"))
        l_hist.addWidget(self.table_hist)
        self.load_history() # Initial Load
        
        tabs.addTab(tab_hist, "ORDERS")
        
        # Financial Ledger Tab
        tab_ledger = QWidget()
        l_ledger = QVBoxLayout(tab_ledger)
        l_ledger.setContentsMargins(DIM_MARGIN_STD, DIM_MARGIN_STD, DIM_MARGIN_STD, DIM_MARGIN_STD)
        self.table_ledger = QTableWidget()
        self.table_ledger.setColumnCount(4)
        self.table_ledger.setHorizontalHeaderLabels(["Datetime", "Purchase Order", "Payment Mode", "Amount"])
        self.table_ledger.setStyleSheet(ui_theme.get_table_style())
        self.table_ledger.horizontalHeader().setStretchLastSection(True)
        l_ledger.addWidget(self.table_ledger)
        
        self.lbl_ledger_total = QLabel("Total Paid: ₹ 0.00")
        self.lbl_ledger_total.setStyleSheet(f"color: {COLOR_ACCENT_GREEN}; font-size: 14px; font-weight: bold;")
        self.lbl_ledger_total.setAlignment(Qt.AlignmentFlag.AlignRight)
        l_ledger.addWidget(self.lbl_ledger_total)
        
        self.load_vendor_ledger()
        tabs.addTab(tab_ledger, "💳 FINANCIAL LEDGER")
        
        # Tab B: Catalog
        tab_cat = QWidget()
        l_cat = QVBoxLayout(tab_cat)
        
        # Toolbar
        cat_toolbar = QHBoxLayout()
        btn_import = QPushButton("📥 Import Excel")
        btn_import.setStyleSheet(ui_theme.get_primary_button_style())
        btn_import.clicked.connect(self.import_catalog_excel)
        
        btn_create_po = QPushButton("📝 Create PO from Selection")
        btn_create_po.setStyleSheet(ui_theme.get_neon_action_button())
        btn_create_po.clicked.connect(self.create_po_from_selection)
        
        cat_toolbar.addWidget(QLabel("SUPPLY CATALOG"))
        
        # Total Parts Count
        self.lbl_catalog_count = QLabel("📦 Total: 0")
        self.lbl_catalog_count.setStyleSheet(ui_theme.get_page_title_style())
        cat_toolbar.addWidget(self.lbl_catalog_count)
        
        # Selected Parts Count
        self.lbl_selected_count = QLabel("✅ Selected: 0")
        self.lbl_selected_count.setStyleSheet(ui_theme.get_page_title_style())
        cat_toolbar.addWidget(self.lbl_selected_count)
        
        # Order Value Counter
        self.lbl_order_value = QLabel("💰 Value: ₹0.00")
        self.lbl_order_value.setStyleSheet(ui_theme.get_page_title_style())
        cat_toolbar.addWidget(self.lbl_order_value)
        
        # Search Bar
        self.txt_cat_search = QLineEdit()
        self.txt_cat_search.setPlaceholderText("Search Part Name or ID...")
        self.txt_cat_search.setStyleSheet(ui_theme.get_lineedit_style())
        self.txt_cat_search.setFixedWidth(200)
        self.txt_cat_search.textChanged.connect(self.filter_catalog)
        cat_toolbar.addWidget(self.txt_cat_search)
        
        cat_toolbar.addStretch()
        cat_toolbar.addWidget(btn_import)
        
        # Export Catalog Button
        btn_export_cat = QPushButton("📤 Export Catalog")
        btn_export_cat.setStyleSheet(ui_theme.get_primary_button_style())
        btn_export_cat.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_export_cat.clicked.connect(self.export_catalog_excel)
        cat_toolbar.addWidget(btn_export_cat)
        
        cat_toolbar.addWidget(btn_create_po)
        l_cat.addLayout(cat_toolbar)
        
        # --- Build Dynamic Column Headers ---
        self.fixed_cols = ["Select", "ID", "PART NAME", "Vendor Stock", "VENDOR MRP", "VENDOR DISC%", "Reorder", "Order Qty"]
        self.extra_col_names = self.db_manager.get_vendor_catalog_columns(self.vendor_name)
        all_cols = self.fixed_cols + self.extra_col_names
        
        self.table_cat = QTableWidget()
        self.table_cat.setColumnCount(len(all_cols))
        self.table_cat.setHorizontalHeaderLabels(all_cols)
        chk_css = """
        QTableView::indicator {
            width: 20px; height: 20px;
            border-radius: 4px;
        }
        QTableView::indicator:unchecked {
            border: 2px solid #666;
            background-color: #1a1a2e;
        }
        QTableView::indicator:checked {
            border: 2px solid #00F2FF;
            background-color: #00F2FF;
        }
        """
        self.table_cat.setStyleSheet(STYLE_TABLE_CYBER + f"\nQTableWidget {{ background-color: #0b0b14; gridline-color: #1a1a2e; }}\n{chk_css}")
        self.table_cat.setAlternatingRowColors(False) # Force custom background colors to render instead of alternate ones
        
        # Apply ProTableDelegate (same as inventory table)
        self.cat_delegate = ProTableDelegate(self.table_cat)
        for c in range(self.table_cat.columnCount()):
            self.table_cat.setItemDelegateForColumn(c, self.cat_delegate)
        
        # Column Resizing
        header = self.table_cat.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch) # Part Name fills space
        
        self.table_cat.setColumnWidth(0, 40) # Checkbox (narrowed for better centering)
        self.table_cat.setColumnWidth(1, 100) # ID
        self.table_cat.setColumnWidth(3, 80) # Stock
        self.table_cat.setColumnWidth(4, 90) # VENDOR MRP
        self.table_cat.setColumnWidth(5, 90) # VENDOR DISC%
        self.table_cat.setColumnWidth(6, 80) # Reorder
        self.table_cat.setColumnWidth(7, 80) # Order Qty
        
        self.table_cat.itemChanged.connect(self.on_catalog_item_changed)
        
        l_cat.addWidget(self.table_cat)
        
        # Lazy-load catalog data after UI is shown (for speed)
        self.recently_ordered = set()
        QTimer.singleShot(100, self._load_catalog_data)
        
        tabs.addTab(tab_cat, "📦 CATALOG")
        
        layout.addWidget(tabs)
    
    def _load_catalog_data(self):
        """Lazy-load catalog data from DB (called after dialog is visible for speed)."""
        import json as _json
        
        catalog_items = self.db_manager.get_supplier_catalog(self.vendor_name)
        if not catalog_items:
            self.lbl_catalog_count.setText("📦 Total: 0")
            return
        
        all_parts = self.db_manager.get_all_parts()
        part_map = {str(p[1]).lower(): p for p in all_parts}
        
        # Load recently ordered parts for this vendor (last 7 days)
        self.recently_ordered = self.db_manager.get_recently_ordered_parts(self.vendor_name, days=7)
        
        display_items = []
        
        for cat in catalog_items:
            # cat: code, name, price, ref_stock, extra_data, vendor_disc_percent
            code, name, price, ref_stock = cat[0], cat[1], cat[2], cat[3]
            extra_raw = cat[4] if len(cat) > 4 else None
            vendor_disc_val = cat[5] if len(cat) > 5 else 0.0
            
            # Parse extra data JSON
            extra = {}
            if extra_raw:
                try:
                    extra = _json.loads(extra_raw)
                except:
                    extra = {}
            
            # Check Inventory Match
            existing = part_map.get(name.lower() if name else "")
            
            if existing:
                d_id = existing[0]
                d_stock = existing[2]
                d_price = existing[4]
                d_reorder = existing[3]
            else:
                d_id = code
                d_stock = 0
                d_price = price
                d_reorder = 0
            
            display_items.append({
                "id": d_id, "name": name, "stock": ref_stock, "price": d_price,
                "vendor_disc": vendor_disc_val, "reorder": d_reorder, "qty": 0, "extra": extra
            })
        
        self.table_cat.setUpdatesEnabled(False)
        self.table_cat.setRowCount(len(display_items))
        for r, item in enumerate(display_items):
            self.table_cat.blockSignals(True)
            self._populate_catalog_row(r, item)
            self.table_cat.blockSignals(False)
        
        self.table_cat.setUpdatesEnabled(True)
        
        # Update catalog count
        self.lbl_catalog_count.setText(f"📦 Total: {len(display_items)}")

    def import_catalog_excel(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Catalog", "", "Excel Files (*.xlsx);;CSV Files (*.csv)")
        if not path: return
        
        # 1. Setup Progress Dialog
        self.dlg_progress = BatteryProgressDialog(self)
        self.dlg_progress.show()
        
        # 2. Setup Thread
        self.thread_import = CatalogImportThread(path, self.vendor_name, self.db_manager)
        self.thread_import.progress.connect(self.dlg_progress.update_progress)
        self.thread_import.finished.connect(self.on_import_finished)
        self.thread_import.start()
        
    def on_import_finished(self, success, msg, ui_items, extra_col_names):
        self.dlg_progress.close()
        
        if not success:
            ProMessageBox.critical(self, "Import Failed", msg)
            return
            
        ProMessageBox.information(self, "Success", msg)
        
        # Update extra column names
        self.extra_col_names = extra_col_names
        
        # Rebuild table columns
        all_cols = self.fixed_cols + self.extra_col_names
        self.table_cat.setColumnCount(len(all_cols))
        self.table_cat.setHorizontalHeaderLabels(all_cols)
        
        # Re-apply ProTableDelegate to new columns
        for c in range(self.table_cat.columnCount()):
            self.table_cat.setItemDelegateForColumn(c, self.cat_delegate)
        
        # Batch UI Update
        self.table_cat.setRowCount(0)
        self.table_cat.setUpdatesEnabled(False)
        self.table_cat.setSortingEnabled(False) 
        
        self.table_cat.setRowCount(len(ui_items))
        
        for r, item in enumerate(ui_items):
             self.table_cat.blockSignals(True)
             self._populate_catalog_row(r, item)
             self.table_cat.blockSignals(False)
             
        self.table_cat.setUpdatesEnabled(True)
        self.table_cat.setSortingEnabled(True)
        
        # Refresh recently ordered parts for color coding
        self.recently_ordered = self.db_manager.get_recently_ordered_parts(self.vendor_name, days=7)
        # Re-apply colors now that we have updated data
        for r in range(self.table_cat.rowCount()):
            self.apply_row_color(r)
        
        # Update counts after import
        self.lbl_catalog_count.setText(f"📦 Total: {len(ui_items)}")
        self.lbl_selected_count.setText("✅ Selected: 0")
        self.lbl_order_value.setText("💰 Value: ₹0.00")
    
    def export_catalog_excel(self):
        """Export the full catalog table (fixed + dynamic columns) to Excel."""
        rows = []
        for r in range(self.table_cat.rowCount()):
            if self.table_cat.isRowHidden(r):
                continue
            row_data = {}
            for c in range(1, self.table_cat.columnCount()):  # Skip checkbox column
                header = self.table_cat.horizontalHeaderItem(c).text()
                cell = self.table_cat.item(r, c)
                row_data[header] = cell.text() if cell else ""
            rows.append(row_data)
        
        if not rows:
            ProMessageBox.warning(self, "Export", "No catalog data to export.")
            return
        
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Catalog", f"{self.vendor_name}_Catalog.xlsx", "Excel Files (*.xlsx)"
        )
        if path:
            try:
                df = DataFrame(rows)
                df.to_excel(path, index=False)
                ProMessageBox.information(self, "Success", f"Exported {len(rows)} items to Excel!")
            except Exception as e:
                app_logger.error(f"Catalog export failed: {e}")
                ProMessageBox.critical(self, "Error", f"Export failed: {e}")

    def create_po_from_selection(self):
        items = []
        for r in range(self.table_cat.rowCount()):
            if self.table_cat.item(r, 0).checkState() == Qt.CheckState.Checked:
                # Capture Data
                p_id = self.table_cat.item(r, 1).text()
                name = self.table_cat.item(r, 2).text()
                stock = self.table_cat.item(r, 3).text()
                price = self.table_cat.item(r, 4).text()
                vendor_disc_txt = self.table_cat.item(r, 5).text()
                reorder = self.table_cat.item(r, 6).text()
                
                # Get Order Qty
                try:
                    qty = float(self.table_cat.item(r, 7).text())
                except:
                    qty = 1
                    
                try: vendor_disc_percent = float(vendor_disc_txt)
                except: vendor_disc_percent = 0.0
                
                items.append({
                    "id": p_id,
                    "name": name,
                    "stock": stock,
                    "reorder": reorder,
                    "price": price,
                    "vendor_disc_percent": vendor_disc_percent,
                    "vendor": self.vendor_name,
                    "qty": qty  # Pass actual qty
                })
        
        if not items:
            ProMessageBox.warning(self, "Selection", "Please select items to order.")
            return

        # Batch-save Order Qty values and Disc% for selected items to the catalog DB
        for item_data in items:
            try:
                self.db_manager.save_catalog_item(
                    self.vendor_name,
                    item_data["id"],
                    item_data["name"],
                    float(item_data["price"]) if item_data["price"] else 0.0,
                    int(item_data["stock"]) if item_data["stock"] else 0,
                    None, # extra_data
                    float(item_data.get("vendor_disc_percent", 0.0))
                )
            except Exception as e:
                app_logger.warning(f"Catalog batch save skipped for {item_data.get('name')}: {e}")

        # Send to Parent
        if self.parent() and hasattr(self.parent(), "load_catalog_items_into_po"):
            self.parent().load_catalog_items_into_po(items)
            self.accept()
        else:
             ProMessageBox.warning(self, "Error", "Parent window not found.")

    def filter_catalog(self, text):
        text = text.lower().strip()
        for r in range(self.table_cat.rowCount()):
            # Col 1: ID, Col 2: Name
            item_id = self.table_cat.item(r, 1)
            item_name = self.table_cat.item(r, 2)
            
            show = True
            if text:
                txt_id = item_id.text().lower() if item_id else ""
                txt_name = item_name.text().lower() if item_name else ""
                
                if text not in txt_id and text not in txt_name:
                    show = False
            
            self.table_cat.setRowHidden(r, not show)

    def update_selected_count(self):
        """Update the selected parts counter label."""
        count = 0
        for r in range(self.table_cat.rowCount()):
            chk = self.table_cat.item(r, 0)
            if chk and chk.checkState() == Qt.CheckState.Checked:
                count += 1
        self.lbl_selected_count.setText(f"✅ Selected: {count}")

    def on_catalog_item_changed(self, item):
        # Handle Checkbox Toggle (Column 0)
        if item.column() == 0:
            row = item.row()
            self.apply_row_color(row)
            self.update_selected_count()
            self.update_order_value()
            return

        # Handle Order Qty Edit (Column 7) or Disc Edit
        if item.column() not in (5, 7): return
        
        # Determine if we are updating order value vs also subtracting stock (only do stock for Qty = col 7)
        if item.column() == 7:
            row = item.row()
            try:
                p_id = self.table_cat.item(row, 1).text()
                name = self.table_cat.item(row, 2).text()
                price_txt = self.table_cat.item(row, 4).text()
                price = float(price_txt) if price_txt else 0.0
                
                new_qty_txt = item.text()
                new_qty = float(new_qty_txt) if new_qty_txt else 0.0
                
                # Auto-subtract from stock display
                stock_item = self.table_cat.item(row, 3)
                if stock_item:
                    # Get original stock from stored data
                    orig_stock = int(stock_item.data(Qt.ItemDataRole.UserRole) or 0)
                    remaining = orig_stock - new_qty
                    self.table_cat.blockSignals(True)
                    stock_item.setText(f"{remaining}")
                    # Color the stock cell based on remaining
                    if remaining < 0:
                        stock_item.setForeground(QColor("#FF4444"))  # Red - deficit
                    elif remaining == 0:
                        stock_item.setForeground(QColor("#FFA500"))  # Orange - zero
                    else:
                        stock_item.setForeground(QColor(COLOR_ACCENT_GREEN))  # Green - ok
                    self.table_cat.blockSignals(False)
                
                # Update order value
                self.update_order_value()
                #  DB save is deferred — happens in batch when user clicks 'Create PO from Selection'
                
            except Exception as e:
                app_logger.error(f"Failed to update catalog item qty logic: {e}")
                item.setForeground(QColor("red"))
            
        # Update order value again for any disc edits
        self.update_order_value()

    def _populate_catalog_row(self, r, item):
        """Populate a single catalog table row with data and color coding."""
        # Checkbox
        chk_item = QTableWidgetItem()
        chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        chk_item.setCheckState(Qt.CheckState.Unchecked)
        self.table_cat.setItem(r, 0, chk_item)
        
        def make_readonly(val):
            it = QTableWidgetItem(str(val))
            it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            return it

        self.table_cat.setItem(r, 1, make_readonly(item["id"]))
        self.table_cat.setItem(r, 2, make_readonly(item["name"]))
        
        # Stock cell - store original value in UserRole for auto-subtract
        stock_val = item["stock"] if item["stock"] is not None else 0
        try:
            stock_int = int(stock_val)
        except (ValueError, TypeError):
            stock_int = 0
        stock_cell = make_readonly(stock_int)
        stock_cell.setData(Qt.ItemDataRole.UserRole, stock_int)
        self.table_cat.setItem(r, 3, stock_cell)
        
        try:
            p_val = float(item['price']) if item['price'] is not None else 0.0
        except (ValueError, TypeError):
            p_val = 0.0
        self.table_cat.setItem(r, 4, make_readonly(f"{p_val:.2f}"))
        
        # Vendor Disc % (Editable)
        v_disc = float(item.get("vendor_disc", 0.0))
        item_disc = QTableWidgetItem(f"{v_disc:.2f}")
        item_disc.setForeground(QColor("#FFA500")) # orange tint for edit
        self.table_cat.setItem(r, 5, item_disc)

        self.table_cat.setItem(r, 6, make_readonly(item["reorder"]))
        
        # Order Qty (Editable)
        qty_val = f"{float(item["qty"]):g}" if item["qty"] else "0"
        item_qty = QTableWidgetItem(qty_val)
        item_qty.setForeground(QColor(COLOR_ACCENT_CYAN))
        self.table_cat.setItem(r, 7, item_qty)
        
        # Extra columns
        for ci, col_name_x in enumerate(self.extra_col_names):
            val = item.get("extra", {}).get(col_name_x, "")
            self.table_cat.setItem(r, 8 + ci, make_readonly(val))
        
        # Apply color coding
        self.apply_row_color(r)

    def apply_row_color(self, row):
        """Apply priority-based color coding to a catalog row.
        Priority: Selected (cyan) > Recently Ordered (orange) > Low Stock (red) > Default"""
        name_item = self.table_cat.item(row, 2)
        chk_item = self.table_cat.item(row, 0)
        stock_item = self.table_cat.item(row, 3)
        reorder_item = self.table_cat.item(row, 6)
        
        name = name_item.text().lower() if name_item else ""
        is_selected = chk_item and chk_item.checkState() == Qt.CheckState.Checked
        
        # Get stock and reorder values
        try:
            stock = int(stock_item.text()) if stock_item else 0
        except:
            stock = 0
        try:
            reorder = int(reorder_item.text()) if reorder_item else 0
        except:
            reorder = 0
        
        is_low_stock = stock <= reorder and reorder > 0
        is_recently_ordered = name in getattr(self, 'recently_ordered', set())
        
        # Determine color by priority
        if is_selected:
            bg_color = QColor(0, 242, 255, 35)      # Bright Cyan tint - SELECTED
            tag_color = QColor(COLOR_ACCENT_CYAN)
        elif is_recently_ordered:
            bg_color = QColor("#3d2e0f")      # Orange tint - RECENTLY ORDERED
            tag_color = QColor("#FFA500")
        elif is_low_stock:
            bg_color = QColor("#3d0f0f")      # Red tint - LOW STOCK
            tag_color = QColor("#FF4444")
        else:
            bg_color = QColor("#0b0e14")      # Default dark
            tag_color = None
        
        for c in range(self.table_cat.columnCount()):
            cell = self.table_cat.item(row, c)
            if cell:
                if c == 7:
                    # Make Order Qty column emphatically prompt the user for input when selected
                    if is_selected:
                        cell.setBackground(QColor(255, 170, 0, 50)) # Bright Amber background
                        cell.setForeground(QColor("#FFD700"))       # Bright Gold text
                        font = cell.font()
                        font.setBold(True)
                        cell.setFont(font)
                    else:
                        cell.setBackground(QColor("#1a2236"))
                        cell.setForeground(QColor(COLOR_ACCENT_CYAN))
                        font = cell.font()
                        font.setBold(False)
                        cell.setFont(font)
                elif c == 5:
                    # Make Vendor Disc % column also look editable
                    cell.setBackground(QColor("#1a2236") if not is_selected else bg_color)
                else:
                    cell.setBackground(bg_color)
        
        # Add status indicator to the name cell
        if name_item and tag_color:
            name_item.setForeground(tag_color)

    def update_order_value(self):
        """Calculate and display total value of selected items (price × qty)."""
        total = 0.0
        for r in range(self.table_cat.rowCount()):
            chk = self.table_cat.item(r, 0)
            if chk and chk.checkState() == Qt.CheckState.Checked:
                try:
                    price = float(self.table_cat.item(r, 4).text())
                    
                    try: disc_percent = float(self.table_cat.item(r, 5).text())
                    except: disc_percent = 0.0
                    
                    qty = float(self.table_cat.item(r, 7).text() or "0")
                    
                    # Apply disc percent
                    discounted_price = price - (price * disc_percent / 100)
                    total += discounted_price * qty
                except:
                    pass
        self.lbl_order_value.setText(f"💰 Value: ₹{total:,.2f}")

    def highlight_row(self, row, active):
        """Legacy highlight - now delegates to apply_row_color."""
        self.apply_row_color(row)


    def load_history(self):
        start = self.date_start.date().toString("yyyy-MM-dd")
        end = self.date_end.date().toString("yyyy-MM-dd")
        search = self.txt_po_search.text().strip()
        
        pos = self.db_manager.search_vendor_history(self.vendor_name, start, end, search)
        
        self.table_hist.setRowCount(0)
        self.table_hist.setRowCount(len(pos))
        for r, p in enumerate(pos):
             # p: id, date, status, item_count
            self.table_hist.setItem(r, 0, QTableWidgetItem(str(p[0])))
            self.table_hist.setItem(r, 1, QTableWidgetItem(str(p[1])))
            self.table_hist.setItem(r, 2, QTableWidgetItem(str(p[2])))
            self.table_hist.setItem(r, 3, QTableWidgetItem(str(p[3])))
            
            # Total Amount (New)
            total = p[4] if len(p) > 4 and p[4] is not None else 0.0
            self.table_hist.setItem(r, 4, QTableWidgetItem(f"₹{total:,.2f}"))

    def export_orders_pdf(self):
        """Export the current view of the vendor's orders into a professional PDF statement."""
        if self.table_hist.rowCount() == 0:
            ProMessageBox.warning(self, "Export Failed", "There is no order history to export.")
            return

        start = self.date_start.date().toString("yyyy-MM-dd")
        end = self.date_end.date().toString("yyyy-MM-dd")
        search = self.txt_po_search.text().strip()
        
        # We re-fetch to ensure data integrity
        pos = self.db_manager.search_vendor_history(self.vendor_name, start, end, search)
        
        if not pos:
            ProMessageBox.warning(self, "Export Failed", "There is no order history to export.")
            return

        total_amt = 0.0
        total_items = 0
        for p in pos:
            total_items += int(p[3] if len(p) > 3 and p[3] is not None else 0)
            total_amt += float(p[4] if len(p) > 4 and p[4] is not None else 0.0)

        # Generate Report
        try:
            from report_generator import ReportGenerator
            import os
            
            rg = ReportGenerator(self.db_manager)
            success, path = rg.generate_vendor_statement_pdf(self.vendor_name, start, end, pos, total_amt, total_items)
            
            if success:
                from whatsapp_helper import send_report_msg
                ans = ProMessageBox.question(self, "Success", f"Vendor Statement generated successfully at:\n{path}\n\nDo you want to share this report via WhatsApp?")
                if ans:
                    try:
                        settings = self.db_manager.get_shop_settings()
                        shop_name = settings.get("shop_name", "SpareParts Pro")
                    except: shop_name = "SpareParts Pro"
                    send_report_msg("Vendor Statement", shop_name)
                    try: os.startfile(os.path.dirname(path))
                    except: pass
                    ProMessageBox.information(self, "WhatsApp", "Please attach the PDF manually into the chat once WhatsApp Web opens.")
                else:
                    try: os.startfile(path)
                    except: pass
            else:
                ProMessageBox.critical(self, "Error", f"Failed to generate PDF: {path}")

        except Exception as e:
            app_logger.error(f"Error generating Vendor Statement PDF: {e}")
            ProMessageBox.critical(self, "Error", f"An error occurred: {e}")

    def load_vendor_ledger(self):
        logs = self.db_manager.get_vendor_ledger(self.vendor_name)
        self.table_ledger.setRowCount(len(logs))
        total_paid = 0.0
        from PyQt6.QtGui import QColor
        for r, row in enumerate(logs):
            # row: 0=payment_date, 1=po_id, 2=amount, 3=payment_mode
            amt = float(row[2])
            total_paid += amt
            m = str(row[3]).upper()
            
            self.table_ledger.setItem(r, 0, QTableWidgetItem(str(row[0])))
            self.table_ledger.setItem(r, 1, QTableWidgetItem(str(row[1])))
            
            item_m = QTableWidgetItem(m)
            if m == "CASH": item_m.setForeground(QColor(COLOR_ACCENT_CYAN))
            elif m == "UPI": item_m.setForeground(QColor(COLOR_ACCENT_GREEN))
            self.table_ledger.setItem(r, 2, item_m)
            
            item_a = QTableWidgetItem(f"₹ {amt:,.2f}")
            item_a.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table_ledger.setItem(r, 3, item_a)
            
        self.lbl_ledger_total.setText(f"Total Paid: ₹ {total_paid:,.2f}")

class PurchaseOrderPage(QWidget):

    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self.part_cache = [] # List of tuples (id, name, stock, reorder, vendor)
        self.report_gen = ReportGenerator(db_manager)  # Bug fix: was missing, caused AttributeError on PDF export
        self._enrich_workers = set()
        self.setup_ui()
        QTimer.singleShot(500, self.load_inventory_cache)

    def load_data(self):
        """Called by Main Window refresh"""
        self.load_inventory_cache()
        self.on_tab_changed(self.tabs.currentIndex())
        
    def load_inventory_cache(self):
        """Cache parts for search completer"""
        try:
            # Need to method in DB to get simple part list
            rows = self.db_manager.get_all_parts()
            # rows: 0:id, 1:name, 2:desc, 3:unit_price, 4:qty, 5:rack, 6:col,
            #       7:reorder, 8:vendor, 9:compat, 10:cat, 11:added_date,
            #       12:added_by, 13:last_cost, 14:last_ordered_date,
            #       15:hsn_code, 16:gst_rate  (positions may vary by migration)
            self.part_cache = []
            search_list = []
            for r in rows:
                 pid = r[0]
                 name = r[1]
                 qty = r[4]
                 # Price: prefer unit_price (r[3]), fallback to last_cost (r[17])
                 unit_price = float(r[3]) if len(r) > 3 and r[3] else 0.0
                 last_cost  = float(r[17]) if len(r) > 17 and r[17] else 0.0
                 price = unit_price if unit_price > 0 else last_cost
                 reorder = r[7] if len(r) > 7 else 5
                 vendor = r[8] if len(r) > 8 else ""
                 
                 # New columns
                 hsn = r[15] if len(r) > 15 and r[15] else '8714'
                 gst = float(r[16]) if len(r) > 16 and r[16] else 18.0
                 
                 self.part_cache.append((pid, name, qty, reorder, vendor, price, hsn, gst))
                 search_list.append(f"{name} | {pid}")
            
            # Setup Completer
            self.completer = QCompleter(search_list)
            self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self.in_search_add.setCompleter(self.completer)
            
            # Populate Vendor ComboBox (Official Registry + Legacy)
            # Fetch official vendors first
            official_vendors = self.db_manager.get_all_vendors()
            vendor_names = set([v[1] for v in official_vendors])
            
            # Add legacy vendors from parts if not covered
            for r in rows:
                if len(r) > 8 and r[8] and r[8] not in vendor_names:
                    vendor_names.add(r[8])
                    
            vendors = sorted(list(vendor_names))
            self.in_supplier.clear()
            self.in_supplier.addItems(vendors)
            
        except Exception as e:
            app_logger.error(f"Error loading cache for PO: {e}")

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(DIM_MARGIN_STD, DIM_MARGIN_STD, DIM_MARGIN_STD, DIM_MARGIN_STD)
        layout.setSpacing(DIM_SPACING_STD)
        
        # Header
        header_container = QWidget()
        hc_layout = QVBoxLayout(header_container)
        hc_layout.setContentsMargins(0, 0, 0, 0)
        hc_layout.setSpacing(5)
        
        header = QLabel("🛒 PURCHASE ORDERS (JIT SYSTEM)")
        header.setStyleSheet(ui_theme.get_page_title_style())
        hc_layout.addWidget(header)
        
        accent = QFrame()
        accent.setFixedHeight(2)
        accent.setStyleSheet(f"background-color: {COLOR_ACCENT_CYAN}; border: none;")
        hc_layout.addWidget(accent)
        
        layout.addWidget(header_container)
        
        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(STYLE_TAB_WIDGET)
        
        self.tab_create = QWidget()
        self.tab_receive = QWidget()
        self.tab_backlog = QWidget()
        self.tab_history = QWidget()
        self.tab_vendors = QWidget() 
        
        self.setup_create_tab()
        self.setup_receive_tab()
        self.setup_backlog_tab()
        self.setup_history_tab()
        self.setup_vendors_tab()

        self.tabs.addTab(self.tab_create, "1. CREATE PO")
        self.tabs.addTab(self.tab_receive, "2. RECEIVING / GRN")
        self.tabs.addTab(self.tab_backlog, "3. PENDING BACKLOG")
        self.tabs.addTab(self.tab_history, "4. ORDER HISTORY")
        self.tabs.addTab(self.tab_vendors, "5. VENDOR REGISTRY")

        layout.addWidget(self.tabs)

        # Hook tab change to refresh
        self.tabs.currentChanged.connect(self.on_tab_changed)

    # --- TAB 1: CREATE PO ---
    def setup_create_tab(self):
        l = QVBoxLayout(self.tab_create)
        l.setSpacing(20)
        l.setContentsMargins(20, 20, 20, 20)

        # --- Section 1: Supplier & Actions ---
        panel_top = QFrame()
        panel_top.setStyleSheet(STYLE_GLASS_PANEL)
        top_layout = QHBoxLayout(panel_top)
        top_layout.setContentsMargins(15, 15, 15, 15)
        top_layout.setSpacing(15)

        # Supplier Selection
        lbl_supp = QLabel("SUPPLIER:")
        lbl_supp.setStyleSheet(ui_theme.get_page_title_style())
        top_layout.addWidget(lbl_supp)

        self.in_supplier = QComboBox()
        self.in_supplier.setEditable(True)
        self.in_supplier.setPlaceholderText("Select or Type Supplier...")
        self.in_supplier.setMinimumWidth(250)
        self.in_supplier.setFixedHeight(40)
        self.in_supplier.setStyleSheet(STYLE_DROPDOWN_CYBER)
        top_layout.addWidget(self.in_supplier)

        # Profile Button
        self.btn_profile = QPushButton("👤 PROFILE")
        self.btn_profile.setFixedHeight(36)
        self.btn_profile.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_profile.setStyleSheet(ui_theme.get_primary_button_style())
        self.btn_profile.clicked.connect(self.open_supplier_profile)
        top_layout.addWidget(self.btn_profile)

        # New Vendor Button
        self.btn_new_vendor = QPushButton("➕ NEW VENDOR")
        self.btn_new_vendor.setFixedHeight(36)
        self.btn_new_vendor.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new_vendor.setStyleSheet(ui_theme.get_primary_button_style())
        self.btn_new_vendor.clicked.connect(self.open_new_vendor_dialog)
        top_layout.addWidget(self.btn_new_vendor)

        top_layout.addStretch()

        # Action Buttons
        self.btn_export = QPushButton("📥 EXPORT")
        self.btn_export.setFixedHeight(36)
        self.btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_export.setStyleSheet(ui_theme.get_primary_button_style())
        self.btn_export.clicked.connect(self.export_po_excel)
        top_layout.addWidget(self.btn_export)
        
        self.btn_clear_po = QPushButton("🧹 CLEAR PO")
        self.btn_clear_po.setFixedHeight(36)
        self.btn_clear_po.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear_po.setStyleSheet(ui_theme.get_danger_button_style())
        self.btn_clear_po.clicked.connect(self.clear_po_action)
        top_layout.addWidget(self.btn_clear_po)

        self.btn_save_po = QPushButton("💾 SAVE PO")
        self.btn_save_po.setFixedHeight(36)
        self.btn_save_po.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save_po.setStyleSheet(ui_theme.get_primary_button_style())
        self.btn_save_po.clicked.connect(self.save_po)
        top_layout.addWidget(self.btn_save_po)

        l.addWidget(panel_top)

        # --- Section 2: Add Item ---
        panel_add = QFrame()
        panel_add.setStyleSheet(STYLE_GLASS_PANEL)
        add_layout = QHBoxLayout(panel_add)
        add_layout.setContentsMargins(15, 10, 15, 10)
        add_layout.setSpacing(15)

        lbl_add = QLabel("ADD ITEM:")
        lbl_add.setStyleSheet("color: #aaa; font-weight: bold; border: none;")
        add_layout.addWidget(lbl_add)

        self.in_search_add = QLineEdit()
        self.in_search_add.setPlaceholderText("Search Part Name or ID...")
        self.in_search_add.setStyleSheet(ui_theme.get_lineedit_style())
        self.in_search_add.setFixedWidth(300)
        self.in_search_add.setFixedHeight(40)
        self.in_search_add.returnPressed.connect(self.add_item_from_search)
        add_layout.addWidget(self.in_search_add)

        # Quantity Input
        lbl_qty = QLabel("QTY:")
        lbl_qty.setStyleSheet("color: #aaa; font-weight: bold; border: none;")
        add_layout.addWidget(lbl_qty)

        self.in_qty_add = QDoubleSpinBox()
        self.in_qty_add.setRange(0.01, 999999.99)
        self.in_qty_add.setDecimals(2)
        self.in_qty_add.setSingleStep(1.0)
        self.in_qty_add.setValue(10.0)
        self.in_qty_add.setFixedWidth(80)
        self.in_qty_add.setFixedHeight(40)
        self.in_qty_add.setStyleSheet(f"""
            QDoubleSpinBox {{
                background-color: #0b0e14;
                color: {COLOR_ACCENT_CYAN};
                border: 1px solid #1a2a3a;
                border-radius: 4px;
                padding: 5px;
                font-family: 'Consolas', monospace;
                font-size: 14px;
                font-weight: bold;
            }}
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 20px; border: none; background: #1a2a3a; }}
            QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{ background: {COLOR_ACCENT_CYAN}; }}
        """)
        add_layout.addWidget(self.in_qty_add)

        btn_add = QPushButton("➕ ADD TO LIST")
        btn_add.setFixedHeight(36)
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.setStyleSheet(ui_theme.get_primary_button_style())
        btn_add.clicked.connect(self.add_item_from_search)
        add_layout.addWidget(btn_add)
        
        # New Feature: Auto-Fill Shortage
        self.btn_auto_fill = QPushButton("⚡ Auto-Fill Shortage")
        self.btn_auto_fill.setFixedHeight(36)
        self.btn_auto_fill.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_auto_fill.setStyleSheet(ui_theme.get_primary_button_style())
        self.btn_auto_fill.clicked.connect(self.auto_fill_shortage)
        add_layout.addWidget(self.btn_auto_fill)
        
        add_layout.addStretch()

        l.addWidget(panel_add)

        # --- Section 3: Table ---
        self.table_create = QTableWidget()
        cols = ['PART ID', 'PART NAME', 'CURRENT STOCK', 'ORDER QTY', 'BUY PRICE', 'V. DISC %', 'G. DISC %', 'HSN CODE', 'GST %', 'TOTAL', 'REMOVE']
        self.table_create.setColumnCount(len(cols))
        self.table_create.setHorizontalHeaderLabels(cols)
        self.table_create.setStyleSheet(ui_theme.get_table_style())
        self.table_create.verticalHeader().setVisible(False)
        self.table_create.setAlternatingRowColors(True)

        # Column Layout
        header = self.table_create.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch) # Name stretches

        self.table_create.setColumnWidth(0, 100) # ID
        self.table_create.setColumnWidth(2, 110) # Stock
        self.table_create.setColumnWidth(3, 90) # Order Qty
        self.table_create.setColumnWidth(4, 90) # Buy Price
        self.table_create.setColumnWidth(5, 90) # V. DISC %
        self.table_create.setColumnWidth(6, 90) # G. DISC % (new)
        self.table_create.setColumnWidth(7, 100) # HSN Code
        self.table_create.setColumnWidth(8, 70) # GST %
        self.table_create.setColumnWidth(9, 110) # Total
        self.table_create.setColumnWidth(10, 105) # Remove

        self.table_create.itemChanged.connect(self.on_create_item_changed)

        l.addWidget(self.table_create)
        
        # --- Section 4: Summary Panel ---
        panel_summary = QFrame()
        panel_summary.setStyleSheet(STYLE_GLASS_PANEL)
        sum_layout = QHBoxLayout(panel_summary)
        sum_layout.setContentsMargins(15, 10, 15, 10)
        sum_layout.addStretch()
        
        self.lbl_taxable = QLabel("Taxable Value: ₹0.00")
        self.lbl_taxable.setStyleSheet(ui_theme.get_page_title_style())
        sum_layout.addWidget(self.lbl_taxable)
        
        self.lbl_gst = QLabel("Total GST: ₹0.00")
        self.lbl_gst.setStyleSheet(ui_theme.get_page_title_style())
        sum_layout.addWidget(self.lbl_gst)
        
        # New Feature: Global Trade Disc (%) UI
        lbl_global_disc = QLabel("Global Trade Disc (%):")
        lbl_global_disc.setStyleSheet(ui_theme.get_page_title_style())
        sum_layout.addWidget(lbl_global_disc)
        
        self.in_global_disc = QDoubleSpinBox()
        self.in_global_disc.setRange(0.0, 100.0)
        self.in_global_disc.setValue(0.00)
        self.in_global_disc.setDecimals(2)
        self.in_global_disc.setFixedSize(80, 30)
        self.in_global_disc.setStyleSheet(f"""
            QDoubleSpinBox {{
                background-color: #0b0e14;
                color: #FFA500;
                border: 1px solid #1a2a3a;
                border-radius: 4px;
                padding: 2px 5px;
                font-family: 'Consolas', monospace;
                font-size: 14px;
                font-weight: bold;
            }}
        """)
        self.in_global_disc.valueChanged.connect(self.update_po_totals)
        sum_layout.addWidget(self.in_global_disc)
        
        # Add a spacer to separate global disc from grand total
        sum_layout.addSpacing(20)
        
        self.lbl_grand_total = QLabel("Grand Total: ₹0.00")
        self.lbl_grand_total.setStyleSheet(ui_theme.get_page_title_style())
        sum_layout.addWidget(self.lbl_grand_total)
        
        l.addWidget(panel_summary)

    def add_item_from_search(self):
        text = self.in_search_add.text().strip()
        if not text: return

        # Extract Part ID from "Name | ID" format or matches
        part_found = None

        # 1. Exact Match via Completer string
        if "|" in text:
            pid = text.split("|")[-1].strip()
            # Find in cache
            for p in self.part_cache:
                if str(p[0]) == pid:
                    part_found = p
                    break

        # 2. If not found, Loose Search
        if not part_found:
             text_lower = text.lower()
             for p in self.part_cache:
                 if text_lower in str(p[1]).lower() or text_lower in str(p[0]).lower():
                     part_found = p
                     break

        if part_found:
            self.add_row_to_create_table(part_found)
            self.in_search_add.clear()
        else:
             ProMessageBox.information(self, "Not Found", "Part not found in inventory.")

    def update_po_totals(self):
        taxable = 0.0
        total_gst = 0.0
        
        global_disc = self.in_global_disc.value() if hasattr(self, 'in_global_disc') else 0.0
        
        try:
            self.table_create.blockSignals(True)
            for r in range(self.table_create.rowCount()):
                try: qty = float(self.table_create.item(r, 3).text())
                except: qty = 0
                
                try: price = float(self.table_create.item(r, 4).text())
                except: price = 0.0
                
                try: v_disc_percent = float(self.table_create.item(r, 5).text())
                except: v_disc_percent = 0.0
                
                try: gst_percent = float(self.table_create.item(r, 8).text())
                except: gst_percent = 0.0
                
                # Keep G. DISC % column (col 6) in sync with the global disc spinbox
                g_disc_item = self.table_create.item(r, 6)
                if not g_disc_item:
                    g_disc_item = QTableWidgetItem()
                    self.table_create.setItem(r, 6, g_disc_item)
                g_disc_item.setText(f"{global_disc:.2f}")
                g_disc_item.setForeground(QColor("#00BFFF"))
                g_disc_item.setFlags(g_disc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                
                # Math Engine: Price -> V_Disc -> Global_Disc -> Taxable -> GST -> Total
                discounted_price = price - (price * v_disc_percent / 100.0)
                
                # Apply Global Trade Discount correctly on top of vendor disc before multiplying by qty
                discounted_price = discounted_price - (discounted_price * global_disc / 100.0)
                
                row_taxable = discounted_price * qty
                row_gst = row_taxable * (gst_percent / 100.0)
                row_total = row_taxable + row_gst
                
                taxable += row_taxable
                total_gst += row_gst
                
                # Update row total (col 9)
                self.table_create.item(r, 9).setText(f"{row_total:.2f}")
                
            self.lbl_taxable.setText(f"Taxable Value: ₹{taxable:.2f}")
            self.lbl_gst.setText(f"Total GST: ₹{total_gst:.2f}")
            self.lbl_grand_total.setText(f"Grand Total: ₹{(taxable + total_gst):.2f}")
        except Exception as e: 
            app_logger.error(f"Error updating PO totals: {e}")
        finally:
            self.table_create.blockSignals(False)

    def clear_po_action(self):
        if self.table_create.rowCount() == 0:
            return
            
        box = QMessageBox(self)
        box.setWindowTitle("Confirm Clear")
        box.setText("Are you sure you want to clear all items?")
        box.setIcon(QMessageBox.Icon.Warning)
        
        btn_yes = box.addButton("Yes, Clear PO", QMessageBox.ButtonRole.AcceptRole)
        btn_no = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.setStyleSheet(ui_theme.get_page_title_style())
        box.exec()
        
        if box.clickedButton() == btn_yes:
            self.table_create.blockSignals(True)
            self.table_create.setRowCount(0)
            self.table_create.blockSignals(False)
            self.update_po_totals()

    def auto_fill_shortage(self):
        count = 0
        added_ids = set()
        
        # Collect currently existing IDs to prevent duplicate scanning
        for r in range(self.table_create.rowCount()):
            pid_item = self.table_create.item(r, 0)
            if pid_item:
                added_ids.add(pid_item.text())
        
        for p in self.part_cache:
            stock = int(p[2]) if p[2] else 0
            pid = str(p[0])
            
            if stock <= 5 and pid not in added_ids:
                self.add_row_to_create_table(p, default_qty=10)
                added_ids.add(pid)
                count += 1
        
        if count > 0:
            ProMessageBox.information(self, "Auto-Fill", f"Successfully auto-filled {count} items that were short on stock.")
        else:
            ProMessageBox.information(self, "Auto-Fill", "No items are short on stock or they are already added.")

    def add_row_to_create_table(self, item_data, default_qty=None, default_price=None, default_hsn=None, default_gst=None, req_rack="", req_col=""):
        # item_data: (id, name, stock, reorder, vendor, price, hsn, gst)

        # Check if already exists (Duplicate Merge)
        for r in range(self.table_create.rowCount()):
            if self.table_create.item(r, 0).text() == str(item_data[0]):
                add_qty = default_qty if default_qty else self.in_qty_add.value()
                try: curr_qty = float(self.table_create.item(r, 3).text())
                except: curr_qty = 0
                
                self.table_create.blockSignals(True)
                self.table_create.item(r, 3).setText(f"{float(curr_qty + add_qty):g}")
                self.table_create.blockSignals(False)
                
                self.update_po_totals()
                return

        self.table_create.blockSignals(True)

        r = self.table_create.rowCount()
        self.table_create.insertRow(r)
        
        # ID (saving req_rack and req_col in UserRole so we can persist them)
        id_item = QTableWidgetItem(str(item_data[0]))
        id_item.setData(Qt.ItemDataRole.UserRole, {"rack": req_rack, "col": req_col})
        self.table_create.setItem(r, 0, id_item)
        # Name
        part_name = str(item_data[1])
        part_name_lower = part_name.lower()
        self.table_create.setItem(r, 1, QTableWidgetItem(part_name))
        # Stock
        self.table_create.setItem(r, 2, QTableWidgetItem(str(item_data[2])))

        # Calc Qty
        qty = default_qty if default_qty else self.in_qty_add.value()

        self.table_create.setItem(r, 3, QTableWidgetItem(f"{float(qty):g}"))

        # Price Priority:
        #   1. default_price (passed explicitly when loading from vendor catalog)
        #   2. Inventory last_cost or unit_price from cache (when adding manually from inventory)
        #   3. 0.0 (fallback)
        price = 0.0
        if default_price is not None:
            try: price = float(default_price)
            except: price = 0.0
        else:
            # Try inventory cache first (last_cost or unit_price), STRICTLY no catalog fallback
            try: price = float(item_data[5]) if len(item_data) > 5 and item_data[5] else 0.0
            except: price = 0.0
            
        self.table_create.setItem(r, 4, QTableWidgetItem(f"{price:.2f}"))

        # Vendor Disc %
        v_disc = 0.0
        # 1. If item_data already has vendor_disc_percent (e.g. from dict or extended cache)
        if isinstance(item_data, dict) and 'vendor_disc_percent' in item_data:
            try: v_disc = float(item_data['vendor_disc_percent'])
            except: v_disc = 0.0
        elif len(item_data) > 8:
            try: v_disc = float(item_data[8])
            except: pass
        
        # 2. Fallback: look up vendor discount from supplier_catalogs for the selected supplier
        if v_disc == 0.0:
            try:
                supplier = self.in_supplier.currentText().strip()
                part_id_str = str(item_data[0]).strip().upper()
                if supplier:
                    conn = self.db_manager.get_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT vendor_disc_percent FROM supplier_catalogs WHERE vendor_name = ? AND UPPER(part_code) = ? LIMIT 1",
                        (supplier, part_id_str)
                    )
                    row_disc = cursor.fetchone()
                    if row_disc and row_disc[0] is not None:
                        v_disc = float(row_disc[0])
                    conn.close()
            except Exception as disc_err:
                app_logger.warning(f"Could not fetch vendor discount for {item_data[0]}: {disc_err}")
                v_disc = 0.0
            
        item_disc = QTableWidgetItem(f"{v_disc:.2f}")
        item_disc.setForeground(QColor("#FFA500"))
        self.table_create.setItem(r, 5, item_disc)

        # Smart Tax Engine Priority: DB-stored > HSN Reference Search > Default
        hsn = default_hsn if default_hsn is not None else ""
        gst = default_gst if default_gst is not None else 18.0
        
        # 1. Load defaults from DB cache only if missing
        if not hsn or gst == 18.0:
            if hasattr(item_data, '__getitem__') and type(item_data) is not dict:
                if len(item_data) > 6 and item_data[6]:
                    hsn = str(item_data[6])
                if len(item_data) > 7 and item_data[7]:
                    try: gst = float(item_data[7])
                    except: pass

        # 2. Advanced Reference-based overrides ONLY if DB didn't provide anything (New Parts)
        if not hsn:
            try:
                from hsn_reference_data import HSN_REFERENCE_DB
                # Search the reference DB for a matching keyword in description
                # Prioritize explicit keywords from part_name mapping to HSN descriptions
                # Split part name into words and find the best match
                words = [w for w in part_name_lower.replace('-', ' ').split() if len(w) > 3]
                best_match = None
                
                # Try specific part first
                for ref in HSN_REFERENCE_DB:
                    ref_desc = ref['description'].lower()
                    
                    if part_name_lower in ref_desc or any(w in ref_desc for w in words):
                        best_match = ref
                        break
                        
                # If no exact match, fallback to broad categories
                if not best_match:
                    if 'oil' in part_name_lower or 'lubricant' in part_name_lower:
                        hsn = '27101990'
                        gst = 18.0
                    elif 'filter' in part_name_lower:
                        hsn = '84212300'
                        gst = 18.0
                    elif 'brake' in part_name_lower:
                        hsn = '87083000'
                        gst = 18.0
                    elif 'bearing' in part_name_lower:
                        hsn = '84821000'
                        gst = 18.0
                    elif 'bike' in part_name_lower or 'two wheeler' in part_name_lower:
                        hsn = '87141000'
                        gst = 18.0
                    elif 'car' in part_name_lower or 'four wheeler' in part_name_lower:
                        hsn = '87089900'
                        gst = 18.0
                    elif any(k in part_name_lower for k in ['cover', 'frame', 'panel', 'guard', 'body', 'handle']):
                        hsn = '87089900' # Body parts
                        gst = 18.0
                    elif any(k in part_name_lower for k in ['relay', 'switch', 'cable', 'wire', 'sensor', 'bulb']):
                        hsn = '85129000' # Electricals
                        gst = 18.0
                    else:
                        # Ultimate Generic Fallback: Other Motor Vehicle Parts
                        hsn = '87089900'
                        gst = 18.0
                else:
                    hsn = best_match['code']
                    gst = best_match['cgst'] + best_match['sgst']
            except Exception as e:
                app_logger.warning(f"Failed to auto-assign HSN for {part_name}: {e}")
            
        # G. DISC % placeholder — filled/updated by update_po_totals dynamically
        g_disc_item = QTableWidgetItem("0.00")
        g_disc_item.setForeground(QColor("#00BFFF"))
        g_disc_item.setFlags(g_disc_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table_create.setItem(r, 6, g_disc_item)

        self.table_create.setItem(r, 7, QTableWidgetItem(str(hsn) if hsn else "87089900"))
        self.table_create.setItem(r, 8, QTableWidgetItem(f"{gst:.1f}"))

        # Total
        self.table_create.setItem(r, 9, QTableWidgetItem("0.00")) # To be updated by update_po_totals

        # Remove Btn
        btn_del = QPushButton("✖")
        btn_del.setToolTip("Remove Item")
        btn_del.setFixedSize(36, 36)
        btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del.setStyleSheet(ui_theme.get_icon_btn_red())
        
        # We don't capture 'r' in the lambda because row indices shift upon deletion!
        btn_del.clicked.connect(self.remove_create_row)
        
        # Center the button in a widget
        del_cw = QWidget()
        del_cl = QHBoxLayout(del_cw)
        del_cl.setContentsMargins(0, 0, 0, 0)
        del_cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        del_cl.addWidget(btn_del)
        self.table_create.setCellWidget(r, 10, del_cw)
        self.table_create.setRowHeight(r, 54)

        self.table_create.blockSignals(False)
        self.update_po_totals()

        # Auto-fill supplier if empty
        if not self.in_supplier.currentText() and len(item_data) > 4 and item_data[4]:
             self.in_supplier.setCurrentText(item_data[4])
             
    def remove_create_row(self):
        btn = self.sender()
        if not btn: return
        
        # Calculate exactly which row this button belongs to right now
        from PyQt6.QtCore import QPoint
        pos = btn.mapTo(self.table_create.viewport(), QPoint(0, 0))
        index = self.table_create.indexAt(pos)
        
        if index.isValid():
            self.table_create.removeRow(index.row())
            self.update_po_totals()
    def load_catalog_items_into_po(self, items):
        """
        Called from SupplierProfileDialog.
        items: list of dicts {id, name, stock, reorder, price, vendor, qty}
        """
        # Safety Check: Draft Protection
        if self.table_create.rowCount() > 0:
            current_vendor = self.in_supplier.currentText()
            new_vendor = items[0]["vendor"]
            
            msg = "You have unsaved items in your Purchase Order.<br>"
            if current_vendor != new_vendor:
                 msg += f"⚠️ <b>Warning:</b> Current PO is for '<b>{current_vendor}</b>', new items are for '<b>{new_vendor}</b>'.<br>"
            
            msg += "<br>Do you want to <b>APPEND</b> to the current list or <b>OVERWRITE</b> it?"
            
            # Use Standard QMessageBox for Custom Buttons
            box = QMessageBox(self)
            box.setWindowTitle("Draft PO Found")
            box.setText(msg)
            box.setIcon(QMessageBox.Icon.Question)
            
            # Buttons
            btn_append = box.addButton("Append", QMessageBox.ButtonRole.AcceptRole)
            btn_overwrite = box.addButton("Overwrite", QMessageBox.ButtonRole.DestructiveRole)
            btn_cancel = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            
            # Style
            box.setStyleSheet(ui_theme.get_page_title_style())
            
            box.exec()
            
            if box.clickedButton() == btn_cancel:
                return
            elif box.clickedButton() == btn_overwrite:
                self.table_create.setRowCount(0)
            # else Append -> fall through
        else:
             self.table_create.setRowCount(0)

        # Set vendor if empty or overwriting
        if self.table_create.rowCount() == 0:
            self.in_supplier.setCurrentText(items[0]["vendor"])

        # Optimize Lookup
        cache_map = {str(p[1]).lower(): p for p in self.part_cache} # Name -> Part

        for item in items:
            # item["stock"] comes from Catalog (which might be Supplier Stock).
            # We want LOCAL stock for the PO Table.

            real_stock = 0
            real_reorder = 0

            # Try to match with local inventory
            # 1. By Name
            cached = cache_map.get(str(item["name"]).lower())
            if cached:
                real_stock = cached[2]
                real_reorder = cached[3]
                # Update ID to match local if possible?
                # item["id"] might be Supplier Code. If we match local, maybe use local ID?
                # For now, keep the ID from Catalog (Supplier Code) as it's a PO for them.

            item_data = (item["id"], item["name"], real_stock, real_reorder, item["vendor"])

            # Use specific Qty from item (Order Qty)
            qty = item.get("qty", 10)
            price = item.get("price", 0.0)
            self.add_row_to_create_table(item_data, default_qty=qty, default_price=price)

        ProMessageBox.information(self, "PO Created", f"Loaded {len(items)} items into PO Draft.")

    def on_create_item_changed(self, item):
        # We now use update_po_totals instead of handling row-by-row events directly
        # To avoid infinite recursion, blockSignals is safely used in update_po_totals.
        if item.column() in [3, 4, 5, 8]:  # Qty, Price, V. Disc %, GST % (col 6 is read-only G.DISC)
             self.update_po_totals()

    def load_items_from_inventory(self, item_list):
        """
        Called from InventoryPage (5 elements) or CatalogPage (11 elements).

        5-element format  (inventory):
            [id, name, stock, reorder, vendor_name]
        11-element format (catalog):
            [id, name, stock, reorder, vendor,
             price, hsn, gst, qty, rack, col]

        Returns: True if successful, False if cancelled.
        """
        # Safety Check: Draft Protection
        if self.table_create.rowCount() > 0:
            current_vendor = self.in_supplier.currentText()
            new_vendors = set([i[4] for i in item_list if len(i) > 4 and i[4]])
            new_vendor = list(new_vendors)[0] if len(new_vendors) == 1 else "Various"

            msg = "You have unsaved items in your Purchase Order.<br>"
            if current_vendor and new_vendors and current_vendor != new_vendor:
                msg += (f"⚠️ <b>Warning:</b> Current PO is for '<b>{current_vendor}</b>', "
                        f"new items include '<b>{new_vendor}</b>'.<br>")
            msg += "<br>Do you want to <b>APPEND</b> to the current list or <b>OVERWRITE</b> it?"

            box = QMessageBox(self)
            box.setWindowTitle("Draft PO Found")
            box.setText(msg)
            box.setIcon(QMessageBox.Icon.Question)
            btn_append    = box.addButton("Append",    QMessageBox.ButtonRole.AcceptRole)
            btn_overwrite = box.addButton("Overwrite", QMessageBox.ButtonRole.DestructiveRole)
            btn_cancel    = box.addButton("Cancel",    QMessageBox.ButtonRole.RejectRole)
            box.setStyleSheet(ui_theme.get_page_title_style())
            box.exec()

            if box.clickedButton() == btn_cancel:
                return False
            elif box.clickedButton() == btn_overwrite:
                self.table_create.setRowCount(0)
        else:
            self.table_create.setRowCount(0)

        is_fresh = (self.table_create.rowCount() == 0)
        suppliers = set([i[4] for i in item_list if len(i) > 4 and i[4]])
        if is_fresh:
            if len(suppliers) == 1:
                self.in_supplier.setCurrentText(list(suppliers)[0])
            else:
                self.in_supplier.setCurrentIndex(-1)

        for item in item_list:
            # Detect format by length
            if len(item) >= 9:
                # Catalog 11-element format
                # [0]=id [1]=name [2]=stock [3]=reorder [4]=vendor
                # [5]=price [6]=hsn [7]=gst [8]=qty [9]=rack [10]=col
                item_data = tuple(item[:5])  # id, name, stock, reorder, vendor
                default_qty   = float(item[8])    if len(item) > 8 else 1.0
                default_price = float(item[5])  if len(item) > 5 and item[5] else 0.0
                default_hsn   = str(item[6])    if len(item) > 6 and item[6] else ""
                default_gst   = float(item[7])  if len(item) > 7 and item[7] else 18.0
                req_rack      = str(item[9])    if len(item) > 9 and item[9] else ""
                req_col       = str(item[10])   if len(item) > 10 and item[10] else ""
                self.add_row_to_create_table(
                    item_data,
                    default_qty=default_qty,
                    default_price=default_price,
                    default_hsn=default_hsn,
                    default_gst=default_gst,
                    req_rack=req_rack,
                    req_col=req_col
                )
            else:
                # Legacy 5-element inventory format
                self.add_row_to_create_table(tuple(item))

        self.tabs.setCurrentIndex(0)  # Switch to Create PO tab
        return True


    def export_po_excel(self):
        rows = []
        for r in range(self.table_create.rowCount()):
            part_id   = self.table_create.item(r, 0).text()
            part_name = self.table_create.item(r, 1).text()
            qty       = self.table_create.item(r, 3).text()
            price     = self.table_create.item(r, 4).text()   # col 4 = BUY PRICE
            v_disc    = self.table_create.item(r, 5).text()   # col 5 = V. DISC %
            g_disc    = self.table_create.item(r, 6).text()   # col 6 = G. DISC % (read-only)
            hsn       = self.table_create.item(r, 7).text()   # col 7 = HSN CODE
            gst       = self.table_create.item(r, 8).text()   # col 8 = GST %
            total     = self.table_create.item(r, 9).text()   # col 9 = TOTAL
            rows.append({
                "Part ID": part_id, "Part Name": part_name,
                "Qty Required": qty, "Buy Price": price,
                "Vendor Disc %": v_disc, "HSN Code": hsn,
                "GST %": gst, "Total": total
            })

        if not rows: return

        df = DataFrame(rows)
        path, _ = QFileDialog.getSaveFileName(self, "Save PO List", "PurchaseOrdered.xlsx", "Excel Files (*.xlsx)")
        if path:
            try:
                df.to_excel(path, index=False)
                ProMessageBox.information(self, "Success", "Exported successfully!")
            except Exception as e:
                app_logger.error(f"Export failed: {e}")
                ProMessageBox.critical(self, "Error", f"Export failed: {e}")

    def save_po(self):
        rc = self.table_create.rowCount()
        if rc == 0:
            ProMessageBox.warning(self, "Validation", "Cannot save an empty Purchase Order.")
            return

        supplier = self.in_supplier.currentText().strip()
        if not supplier:
            ProMessageBox.warning(self, "Validation", "Please select or type a supplier name.")
            return

        # VENDOR VALIDATION
        # Check if supplier exists in combobox model
        existing_vendors = [self.in_supplier.itemText(i) for i in range(self.in_supplier.count())]
        if supplier not in existing_vendors:
            box = QMessageBox(self)
            box.setWindowTitle("Unregistered Vendor")
            box.setText(f"The vendor '{supplier}' is not currently registered in the system.\n\nDo you want to proceed and temporarily add them for this session?")
            box.setIcon(QMessageBox.Icon.Question)
            
            btn_yes = box.addButton("Yes, Proceed", QMessageBox.ButtonRole.AcceptRole)
            btn_no = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            box.setStyleSheet(ui_theme.get_page_title_style())
            box.exec()
            
            if box.clickedButton() == btn_no:
                return
            else:
                self.in_supplier.addItem(supplier)

        items = []
        total_amount = 0.0
        zero_price_parts = []
        
        global_disc = self.in_global_disc.value() if hasattr(self, 'in_global_disc') else 0.0
        
        for r in range(rc):
            pid = self.table_create.item(r, 0).text()
            pname = self.table_create.item(r, 1).text()
            try: qty = float(self.table_create.item(r, 3).text() or "0")
            except: qty = 0
            
            try: price = float(self.table_create.item(r, 4).text() or "0")
            except: price = 0.0
            
            try: v_disc = float(self.table_create.item(r, 5).text() or "0.0")
            except: v_disc = 0.0
            
            hsn = self.table_create.item(r, 7).text()
            
            try: gst = float(self.table_create.item(r, 8).text() or "0")
            except: gst = 0.0
            
            # Extract requested rack and col from ID cell role data
            pid_item = self.table_create.item(r, 0)
            role_data = pid_item.data(Qt.ItemDataRole.UserRole)
            req_rack, req_col = "", ""
            if isinstance(role_data, dict):
                req_rack = role_data.get("rack", "")
                req_col = role_data.get("col", "")
            
            if qty > 0:
                if price == 0.0:
                    zero_price_parts.append(pname)
                
                # Math for Landing Cost and Row Total (respecting Global Disc)
                disc_price = price - (price * v_disc / 100.0)
                disc_price_global = disc_price - (disc_price * global_disc / 100.0)
                
                taxable = disc_price_global * qty
                row_gst = taxable * (gst / 100.0)
                row_total = taxable + row_gst
                
                # Landing Cost (per unit) = final discounted price + tax per unit
                landing_cost = disc_price_global + (disc_price_global * gst / 100.0)
                
                items.append({
                    "part_id": pid,
                    "part_name": pname,
                    "qty_ordered": qty,
                    "price": price,
                    "vendor_disc_percent": v_disc,
                    "landing_cost": landing_cost,
                    "hsn_code": hsn,
                    "gst_rate": gst,
                    "req_rack": req_rack,
                    "req_col": req_col
                })
                total_amount += row_total
        
        if not items:
            ProMessageBox.warning(self, "Validation", "No valid items with quantity > 0 to save.")
            return
        
        # Zero-price warning — warn user before they silently save a ₹0 PO
        if zero_price_parts:
            names_str = "\n".join(f"  • {n}" for n in zero_price_parts[:8])
            if len(zero_price_parts) > 8:
                names_str += f"\n  ... and {len(zero_price_parts) - 8} more"
            box = QMessageBox(self)
            box.setWindowTitle("⚠️ Zero Price Warning")
            box.setText(
                f"{len(zero_price_parts)} item(s) have BUY PRICE = ₹0.00:\n\n{names_str}\n\n"
                "These will be saved with no cost information.\nDo you still want to save?"
            )
            box.setIcon(QMessageBox.Icon.Warning)
            btn_save = box.addButton("Save Anyway", QMessageBox.ButtonRole.AcceptRole)
            btn_cancel = box.addButton("Go Back & Fix", QMessageBox.ButtonRole.RejectRole)
            box.setStyleSheet(ui_theme.get_page_title_style())
            box.exec()
            if box.clickedButton() == btn_cancel:
                return
        
        success, msg = self.db_manager.create_purchase_order(
            supplier, items, total_amount, global_disc_percent=global_disc
        )
        if success:
            ProMessageBox.information(self, "Success", f"Purchase Order created successfully!\n\nPO ID: {msg}")
            
            # Clear Tab 1
            self.table_create.blockSignals(True)
            self.table_create.setRowCount(0)
            self.table_create.blockSignals(False)
            
            self.in_supplier.setCurrentIndex(-1)
            self.in_search_add.clear()
            self.in_qty_add.setValue(10)
            self.update_po_totals()
            
            # Refresh other tabs
            self.refresh_receive_tab()
            self.refresh_backlog_tab()
            self.refresh_history_tab()
            
            # Switch to Receive Tab
            self.tabs.setCurrentIndex(1)
        else:
            ProMessageBox.critical(self, "Error", msg)

    def open_supplier_profile(self):
        supplier = self.in_supplier.currentText().strip()
        if not supplier:
            ProMessageBox.warning(self, "Select Supplier", "Please select a supplier first.")
            return

        dlg = SupplierProfileDialog(self, supplier, self.db_manager)
        dlg.exec()

    def open_new_vendor_dialog(self):
        """Open the Vendor Manager to add a new vendor."""
        dlg = VendorManagerDialog(self.db_manager, self)
        dlg.exec()

        # Refresh vendor list after dialog closes
        self.load_inventory_cache()

        # Try to select the last added vendor?
        # For now just refreshing is enough, user can select from updated list.

    # --- TAB 2: RECEIVING ---


    def setup_receive_tab(self):
        l = QVBoxLayout(self.tab_receive)
        l.setSpacing(DIM_SPACING_STD)
        l.setContentsMargins(DIM_MARGIN_STD, DIM_MARGIN_STD, DIM_MARGIN_STD, DIM_MARGIN_STD)

        # Controls
        hl = QHBoxLayout()
        hl.setSpacing(15)

        self.txt_search_rx = QLineEdit()
        self.txt_search_rx.setPlaceholderText("Find pending item by Name or PO ID...")
        self.txt_search_rx.setStyleSheet(ui_theme.get_lineedit_style())
        self.txt_search_rx.setFixedHeight(40)
        self.txt_search_rx.textChanged.connect(self.filter_receive_table)
        hl.addWidget(self.txt_search_rx)

        btn_refresh = QPushButton("🔄 REFRESH")
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.setFixedHeight(36)
        btn_refresh.setStyleSheet(ui_theme.get_primary_button_style())
        btn_refresh.clicked.connect(self.refresh_receive_tab)
        hl.addWidget(btn_refresh)
        
        btn_force_close = QPushButton("✅ FORCE CLOSE SELECTED")
        btn_force_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_force_close.setFixedHeight(36)
        btn_force_close.setStyleSheet(ui_theme.get_neon_action_button())
        btn_force_close.clicked.connect(lambda: self.force_close_selected_pos(self.table_receive, self.refresh_receive_tab))
        hl.addWidget(btn_force_close)
        
        btn_bulk_receive = QPushButton("📦 RECEIVE SELECTED")
        btn_bulk_receive.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_bulk_receive.setFixedHeight(36)
        btn_bulk_receive.setStyleSheet(ui_theme.get_primary_button_style())
        btn_bulk_receive.clicked.connect(self.bulk_receive_selected_items)
        hl.addWidget(btn_bulk_receive)

        btn_select_all_rx = QPushButton("☑ SELECT ALL")
        btn_select_all_rx.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_select_all_rx.setFixedHeight(36)
        btn_select_all_rx.setStyleSheet(ui_theme.get_primary_button_style())
        btn_select_all_rx.clicked.connect(self.toggle_select_all_receive)
        hl.addWidget(btn_select_all_rx)

        l.addLayout(hl)

        # Table
        self.table_receive = QTableWidget()
        cols = ["Select", "Part ID", "PO ID", "Supplier", "Part Name", "Ordered", "Received", "Pending", "Buy Price (₹)", "ACTION"]
        self.table_receive.setColumnCount(len(cols))
        self.table_receive.setHorizontalHeaderLabels(cols)
        self.table_receive.setStyleSheet(ui_theme.get_table_style())
        self.table_receive.verticalHeader().setVisible(False)
        self.table_receive.setAlternatingRowColors(False)

        # Column Layout
        header = self.table_receive.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch) # Part Name

        self.table_receive.setColumnWidth(0, 70)   # Select
        self.table_receive.setColumnWidth(1, 100)  # Part ID
        self.table_receive.setColumnWidth(2, 100)  # PO ID
        self.table_receive.setColumnWidth(3, 120)  # Supplier
        self.table_receive.setColumnWidth(5, 75)   # Ordered
        self.table_receive.setColumnWidth(6, 90)   # Received
        self.table_receive.setColumnWidth(7, 75)   # Pending
        self.table_receive.setColumnWidth(8, 110)  # Buy Price
        self.table_receive.setColumnWidth(9, 80)   # Action

        l.addWidget(self.table_receive)

        self.rx_data = [] # Cache

    def toggle_select_all_receive(self):
        """Toggle all checkboxes in the Receiving table."""
        all_checked = True
        for r in range(self.table_receive.rowCount()):
            cw = self.table_receive.cellWidget(r, 0)
            chk = cw.findChild(QCheckBox) if cw else None
            if chk and not chk.isChecked():
                all_checked = False
                break
        
        new_state = not all_checked
        for r in range(self.table_receive.rowCount()):
            cw = self.table_receive.cellWidget(r, 0)
            chk = cw.findChild(QCheckBox) if cw else None
            if chk:
                chk.setChecked(new_state)

    def refresh_receive_tab(self):
        self.thread_rx = PODataThread(self.db_manager, "get_open_po_items")
        self.thread_rx.data_loaded.connect(self.populate_receive_table)
        self.thread_rx.start()

    def populate_receive_table(self, data):
        self.rx_data = data
        self.table_receive.setRowCount(0)
        self.filter_receive_table() # Populate via filter

    def filter_receive_table(self):
        search = self.txt_search_rx.text().lower()
        filtered = [row for row in self.rx_data if search in str(row).lower()]

        self.table_receive.setRowCount(0)
        self.table_receive.setRowCount(len(filtered))

        for r, row in enumerate(filtered):
            # row: (id, po_id, supplier, part_name, qty_ordered, qty_received, pending, part_id)

            # Checkbox — wrapped in centred container
            chk = QCheckBox()
            chk.setStyleSheet(ui_theme.get_table_checkbox_style())
            
            # Persist Checkbox State
            po_id_str = str(row[1])
            part_id_str = str(row[7])
            key = f"{po_id_str}_{part_id_str}"
            
            if not hasattr(self, 'selected_rx_keys'):
                self.selected_rx_keys = set()
                
            if key in self.selected_rx_keys:
                chk.setChecked(True)
                
            chk.stateChanged.connect(lambda state, k=key: self._on_rx_check_changed(state, k))

            _cw = QWidget(); _cl = QHBoxLayout(_cw)
            _cl.setContentsMargins(0, 0, 0, 0)
            _cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            _cl.addWidget(chk)
            self.table_receive.setCellWidget(r, 0, _cw)

            def _make_item(val):
                it = QTableWidgetItem(str(val))
                it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                return it

            # 1: Part ID (from row[7])
            self.table_receive.setItem(r, 1, _make_item(row[7]))
            # 2: PO ID
            self.table_receive.setItem(r, 2, _make_item(row[1]))
            # 3: Supplier
            self.table_receive.setItem(r, 3, _make_item(row[2]))
            # 4: Part Name
            self.table_receive.setItem(r, 4, _make_item(row[3]))
            # 5: Ordered
            self.table_receive.setItem(r, 5, _make_item(row[4]))
            # 6: Received — inline spinbox; user types qty and commits with Enter
            spin_rx = QDoubleSpinBox()
            spin_rx.setDecimals(2)
            spin_rx.setSingleStep(1.0)
            spin_rx.setRange(0.0, float(row[4]) * 10)  # max = 10x ordered
            spin_rx.setValue(float(row[5]) if row[5] else 0.0)
            spin_rx.setStyleSheet(
                "QDoubleSpinBox { background: #0b0e18; color: #00f2ff; border: 1px solid #1a3040;"
                " border-radius: 3px; padding: 2px 4px; font-weight: bold; font-size: 11px; }"
                "QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { width: 14px; }"
            )
            spin_rx.setToolTip("Type qty and press Enter to receive")
            spin_rx.setFixedHeight(30)
            # Store row data for callback
            spin_rx.editingFinished.connect(lambda sp=spin_rx, rd=row: self._on_inline_receive_qty(sp, rd))
            spin_cw = QWidget(); spin_cl = QHBoxLayout(spin_cw)
            spin_cl.setContentsMargins(4, 0, 4, 0)
            spin_cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            spin_cl.addWidget(spin_rx)
            self.table_receive.setCellWidget(r, 6, spin_cw)
            # 7: Pending
            self.table_receive.setItem(r, 7, _make_item(row[6]))

            # 8: Buy Price — inline spinbox, pre-filled from PO
            spin_price = QDoubleSpinBox()
            spin_price.setRange(0, 999999.99)
            spin_price.setDecimals(2)
            spin_price.setStyleSheet(
                "QDoubleSpinBox { background: #0b0e18; color: #ffa500; border: 1px solid #2a1f00;"
                " border-radius: 3px; padding: 2px 4px; font-weight: bold; font-size: 11px; }"
                "QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { width: 14px; }"
            )
            spin_price.setFixedHeight(30)
            # Pre-fill from PO ordered_price
            try:
                conn = self.db_manager.get_connection()
                cur = conn.cursor()
                cur.execute("SELECT ordered_price FROM po_items WHERE id = ?", (row[0],))
                res = cur.fetchone()
                conn.close()
                if res and res[0] and float(res[0]) > 0:
                    spin_price.setValue(float(res[0]))
            except:
                pass
            price_cw = QWidget(); price_cl = QHBoxLayout(price_cw)
            price_cl.setContentsMargins(4, 0, 4, 0)
            price_cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            price_cl.addWidget(spin_price)
            self.table_receive.setCellWidget(r, 8, price_cw)

            # 9: Action Button
            btn = QPushButton("✔")
            btn.setToolTip("Receive Item")
            btn.setFixedSize(36, 36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(ui_theme.get_icon_btn_cyan())
            btn.clicked.connect(lambda _, x=row: self.open_receive_dialog(x))
            
            rx_cw = QWidget()
            rx_cl = QHBoxLayout(rx_cw)
            rx_cl.setContentsMargins(0, 0, 0, 0)
            rx_cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rx_cl.addWidget(btn)
            self.table_receive.setCellWidget(r, 9, rx_cw)
            self.table_receive.setRowHeight(r, 54)

    def _on_rx_check_changed(self, state, key):
        if not hasattr(self, 'selected_rx_keys'):
            self.selected_rx_keys = set()
        if state == Qt.CheckState.Checked.value or state == 2:
            self.selected_rx_keys.add(key)
        else:
            self.selected_rx_keys.discard(key)

    def _on_inline_receive_qty(self, spinbox, row_data):
        """Called when user presses Enter after typing qty. Reads price from same row's spinbox."""
        new_qty = spinbox.value()
        already_received = float(row_data[5]) if row_data[5] else 0.0
        receive_qty = new_qty - already_received
        if receive_qty <= 0:
            return

        # Find which table row this spinbox is in and read price from col 8
        price = 0.0
        for r in range(self.table_receive.rowCount()):
            cw = self.table_receive.cellWidget(r, 6)  # Received col
            if cw:
                sp = cw.findChild(QDoubleSpinBox)
                if sp is spinbox:
                    price_cw = self.table_receive.cellWidget(r, 8)  # Buy Price col
                    if price_cw:
                        sp_price = price_cw.findChild(QDoubleSpinBox)
                        if sp_price:
                            price = sp_price.value()
                    break

        # Guard: Do not receive at ₹0 — this corrupts avg_landing_cost in inventory
        if price <= 0.0:
            ProMessageBox.warning(self, "Buy Price Required",
                                  "Please set a valid Buy Price (> ₹0) before receiving.\nThe Buy Price field is in the last column of this row.")
            return

        success, msg = self.db_manager.receive_po_item(row_data[0], receive_qty, price, row_data[7])
        if success:
            self.refresh_receive_tab()
            try:
                if hasattr(self, '_parent_inventory_ref') and self._parent_inventory_ref:
                    self._parent_inventory_ref.load_data()
            except:
                pass
        else:
            ProMessageBox.critical(self, "Error", f"Receive failed: {msg}")

    def open_receive_dialog(self, item_data):
        dlg = ReceiveItemDialog(self, item_data)
        if dlg.exec():
            qty, price = dlg.get_data()
            if qty is not None and price is not None:
                success, msg = self.db_manager.receive_po_item(item_data[0], qty, price, item_data[7])
                if success:
                    ProMessageBox.information(self, "Success", "Stock updated successfully in Database!")
                    
                    # Background trigger for auto-enriching new parts
                    part_id = item_data[7]
                    worker = AutoEnrichWorker(self.db_manager, [part_id])
                    worker.finished.connect(lambda k=None, w=worker: self._enrich_workers.discard(w))
                    self._enrich_workers.add(worker)
                    worker.start()
                    
                    # Refresh
                    self.refresh_receive_tab()
                    
                    # THE BRIDGE: Force global inventory cache invalidation
                    try:
                        main_window = self.window()
                        inv_page = main_window.page_instances.get(2)
                        if inv_page and hasattr(inv_page, 'load_data'):
                            inv_page.load_data()  # Force fresh DB fetch
                    except Exception as sync_err:
                        app_logger.warning(f"Stock updated, but UI sync failed: {sync_err}")
                else:
                    ProMessageBox.warning(self, "Error", msg)
            else:
                 ProMessageBox.warning(self, "Error", "Invalid Input")

    def bulk_receive_selected_items(self):
        items_to_receive = []
        if not hasattr(self, 'selected_rx_keys'):
            self.selected_rx_keys = set()

        # Gather all checked items mapping back to rx_data using the persistent state
        for row_data in self.rx_data:
            key = f"{row_data[1]}_{row_data[7]}"
            if key in self.selected_rx_keys:
                items_to_receive.append(row_data)

        if not items_to_receive:
            ProMessageBox.warning(self, "Selection", "Please select at least one item to receive.")
            return

        dlg = BulkReceiveDialog(self, self.db_manager, items_to_receive)
        if not dlg.exec():
            return  # User cancelled bulk receive

        processed_data = dlg.get_received_data()
        if not processed_data:
            ProMessageBox.warning(self, "Warning", "No valid quantities to receive were found in the grid.")
            return
            
        success_count = 0
        received_part_ids = []
        
        for po_item_id, part_id, qty, price in processed_data:
            success, msg = self.db_manager.receive_po_item(po_item_id, qty, price, part_id)
            if success:
                success_count += 1
                received_part_ids.append(part_id)
            else:
                app_logger.warning(f"Failed to receive PO item {po_item_id}: {msg}")
                
        if success_count > 0:
            ProMessageBox.information(self, "Bulk Receive", f"Successfully received {success_count} item(s).")
            
            # Extract successfully received part IDs to pass to auto-enrichment
            if received_part_ids:
                worker = AutoEnrichWorker(self.db_manager, received_part_ids)
                worker.finished.connect(lambda k=None, w=worker: self._enrich_workers.discard(w))
                self._enrich_workers.add(worker)
                worker.start()
                
            # Clear selected items set after successful bulk receive
            if hasattr(self, 'selected_rx_keys'):
                self.selected_rx_keys.clear()
                
            self.refresh_receive_tab()
            
            # THE BRIDGE: Force global inventory cache invalidation
            try:
                main_window = self.window()
                inv_page = main_window.page_instances.get(2)
                if inv_page and hasattr(inv_page, 'load_data'):
                    inv_page.load_data()  # Force fresh DB fetch
            except Exception as sync_err:
                app_logger.warning(f"Stock updated, but UI sync failed: {sync_err}")
                
        else:
            ProMessageBox.warning(self, "Bulk Receive", "No items received (Cancelled or Failed).")

    # --- TAB 3: BACKLOG ---
    def setup_backlog_tab(self):
        l = QVBoxLayout(self.tab_backlog)
        l.setContentsMargins(DIM_MARGIN_STD, DIM_MARGIN_STD, DIM_MARGIN_STD, DIM_MARGIN_STD)
        
        # Add Force Close and Export
        hl = QHBoxLayout()
        btn_force_close = QPushButton("✅ FORCE CLOSE SELECTED")
        btn_force_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_force_close.setFixedHeight(36)
        btn_force_close.setStyleSheet(ui_theme.get_neon_action_button())
        btn_force_close.clicked.connect(lambda: self.force_close_selected_pos(self.table_backlog, self.refresh_backlog_tab))
        
        btn_export_backlog = QPushButton("📥 EXPORT PDF")
        btn_export_backlog.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_export_backlog.setFixedHeight(36)
        btn_export_backlog.setStyleSheet(ui_theme.get_icon_btn_red())
        btn_export_backlog.clicked.connect(self.export_backlog_pdf)
        
        btn_select_all_bl = QPushButton("☑ SELECT ALL")
        btn_select_all_bl.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_select_all_bl.setFixedHeight(36)
        btn_select_all_bl.setStyleSheet(ui_theme.get_primary_button_style())
        btn_select_all_bl.clicked.connect(self.toggle_select_all_backlog)
        
        hl.addWidget(btn_force_close)
        hl.addWidget(btn_export_backlog)
        hl.addWidget(btn_select_all_bl)
        hl.addStretch()
        l.addLayout(hl)

        self.table_backlog = QTableWidget()
        cols = ["Select", "Part ID", "PO Date", "PO ID", "Supplier", "Part Name", "Ordered", "Received", "Pending"]
        self.table_backlog.setColumnCount(len(cols))
        self.table_backlog.setHorizontalHeaderLabels(cols)
        self.table_backlog.setStyleSheet(ui_theme.get_table_style())
        self.table_backlog.verticalHeader().setVisible(False)
        self.table_backlog.setAlternatingRowColors(False)

        # Layout
        header = self.table_backlog.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch) # Part Name

        self.table_backlog.setColumnWidth(0, 70) # Select
        self.table_backlog.setColumnWidth(1, 100)
        self.table_backlog.setColumnWidth(2, 100)
        self.table_backlog.setColumnWidth(3, 100)
        self.table_backlog.setColumnWidth(4, 150)

        l.addWidget(self.table_backlog)

    def toggle_select_all_backlog(self):
        """Toggle all checkboxes in the Backlog table."""
        all_checked = True
        for r in range(self.table_backlog.rowCount()):
            cw = self.table_backlog.cellWidget(r, 0)
            chk = cw.findChild(QCheckBox) if cw else None
            if chk and not chk.isChecked():
                all_checked = False
                break
        
        new_state = not all_checked
        for r in range(self.table_backlog.rowCount()):
            cw = self.table_backlog.cellWidget(r, 0)
            chk = cw.findChild(QCheckBox) if cw else None
            if chk:
                chk.setChecked(new_state)

    def refresh_backlog_tab(self):
        # We can reuse get_open_po_items or use get_backlog_items (same query)
        self.thread_bl = PODataThread(self.db_manager, "get_backlog_items")
        self.thread_bl.data_loaded.connect(self.populate_backlog_table)
        self.thread_bl.start()

    def populate_backlog_table(self, data):
        self.table_backlog.setRowCount(0)
        self.table_backlog.setRowCount(len(data))
        for r, row in enumerate(data):
            # row: (id, po_id, supplier, part_name, qty_ordered, qty_received, pending, part_id, hsn_code, gst_rate, order_date)

            # Checkbox — wrapped in centred container
            chk = QCheckBox()
            chk.setStyleSheet(ui_theme.get_table_checkbox_style())
            _cw = QWidget(); _cl = QHBoxLayout(_cw)
            _cl.setContentsMargins(0, 0, 0, 0)
            _cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            _cl.addWidget(chk)
            self.table_backlog.setCellWidget(r, 0, _cw)

            self.table_backlog.setItem(r, 1, QTableWidgetItem(str(row[7]))) # Part ID
            # Bug fix: use actual order_date from row[10] instead of hard-coded "---"
            order_date = str(row[10]) if len(row) > 10 and row[10] else "N/A"
            self.table_backlog.setItem(r, 2, QTableWidgetItem(order_date))  # PO Date
            self.table_backlog.setItem(r, 3, QTableWidgetItem(str(row[1]))) # PO ID
            self.table_backlog.setItem(r, 4, QTableWidgetItem(str(row[2]))) # Supplier
            self.table_backlog.setItem(r, 5, QTableWidgetItem(str(row[3]))) # Name
            self.table_backlog.setItem(r, 6, QTableWidgetItem(str(row[4]))) # Ordered
            self.table_backlog.setItem(r, 7, QTableWidgetItem(str(row[5]))) # Received
            self.table_backlog.setItem(r, 8, QTableWidgetItem(str(row[6]))) # Pending
            
    def force_close_selected_pos(self, table, refresh_callback):
        po_ids = set()
        
        # Determine PO IDs from the current table
        if table == self.table_receive and hasattr(self, 'selected_rx_keys'):
            # Grab from persistent state if it's the receive table
            for key in self.selected_rx_keys:
                po_id = key.split('_')[0]
                po_ids.add(po_id)
        else:
            # Fallback for Backlog (which doesn't have search/state persistence yet)
            for r in range(table.rowCount()):
                cw = table.cellWidget(r, 0)
                chk = cw.findChild(QCheckBox) if cw else None
                if chk and chk.isChecked():
                    if table == self.table_receive:
                        po_ids.add(table.item(r, 2).text())
                    elif table == self.table_backlog:
                        po_ids.add(table.item(r, 3).text())
                        
        if table == self.table_receive and hasattr(self, 'selected_rx_keys'):
            self.selected_rx_keys.clear()
                    
        if not po_ids:
            ProMessageBox.warning(self, "No Selection", "Please select at least one item to force close.")
            return
            
        box = QMessageBox(self)
        box.setWindowTitle("Force Close Selected")
        box.setText(f"Are you sure you want to force close {len(po_ids)} PO(s)?\nThey will be marked as 'CLOSED' (pending items cancelled).")
        box.setIcon(QMessageBox.Icon.Warning)
        btn_yes = box.addButton("Yes, Force Close", QMessageBox.ButtonRole.AcceptRole)
        btn_no = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.setStyleSheet(ui_theme.get_page_title_style())
        box.exec()
        
        if box.clickedButton() == btn_yes:
            for po_id in po_ids:
                self.db_manager.force_close_po(po_id)
            
            ProMessageBox.information(self, "Success", f"Force closed {len(po_ids)} PO(s).")
            # Refresh both tabs
            self.refresh_receive_tab()
            self.refresh_backlog_tab()

    def export_backlog_pdf(self):
        # Gather data direct from the backlog UI or re-query
        rows = []
        for r in range(self.table_backlog.rowCount()):
            # cols = ["Select", "Part ID", "PO Date", "PO ID", "Supplier", "Part Name", "Ordered", "Received", "Pending"]
            po_date = self.table_backlog.item(r, 2).text()
            po_id = self.table_backlog.item(r, 3).text()
            supplier = self.table_backlog.item(r, 4).text()
            part_name = self.table_backlog.item(r, 5).text()
            ordered = self.table_backlog.item(r, 6).text()
            received = self.table_backlog.item(r, 7).text()
            pending = self.table_backlog.item(r, 8).text()
            
            # Pack as expected by ReportGenerator: (id, po_date, po_id, supplier, part_name, ordered, received, pending)
            # using dummy 'id' as index 0, and dummy 'po_date' as index 1 actually 
            # wait, report generator expects date at index 2
            row_tuple = (None, None, po_date, po_id, supplier, part_name, ordered, received, pending)
            rows.append(row_tuple)
            
        if not rows:
            ProMessageBox.warning(self, "Export Failed", "There is no backlog data to export.")
            return
            
        success, path = self.report_gen.generate_po_report_pdf(rows)
        if success:
             import os
             ans = ProMessageBox.question(self, "Success", f"Backlog Report generated successfully at:\n{path}\n\nDo you want to share this report via WhatsApp?")
             if ans:
                 try:
                     settings = self.db_manager.get_shop_settings()
                     shop_name = settings.get("shop_name", "SpareParts Pro")
                 except: shop_name = "SpareParts Pro"
                 send_report_msg("PO Backlog Report", shop_name)
                 try: os.startfile(os.path.dirname(path))
                 except: pass
                 ProMessageBox.information(self, "WhatsApp", "Please attach the PDF manually into the chat once WhatsApp Web opens.")
             else:
                 try: os.startfile(path)
                 except: pass
        else:
             ProMessageBox.critical(self, "Error", f"Failed to generate PDF: {path}")

    def on_tab_changed(self, index):
        if index == 1: # Receive
            self.refresh_receive_tab()
        elif index == 2: # Backlog
            self.refresh_backlog_tab()
        elif index == 3: # History
            self.refresh_history_tab()

    # --- TAB 4: ORDER HISTORY ---
    def setup_history_tab(self):
        l = QVBoxLayout(self.tab_history)
        l.setContentsMargins(DIM_MARGIN_STD, DIM_MARGIN_STD, DIM_MARGIN_STD, DIM_MARGIN_STD)
        l.setSpacing(DIM_SPACING_STD)

        # Splitter for Master-Detail View
        from PyQt6.QtWidgets import QSplitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        # A solid 1px line, no dotted native artifacts
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: rgba(0, 242, 255, 0.25);
                border: none;
            }
            QSplitter::handle:hover {
                background-color: rgba(0, 242, 255, 0.55);
            }
        """)

        # ── Left Panel (Master): PO List ────────────────────────
        left_widget = QWidget()
        left_widget.setStyleSheet("""
            QWidget {
                background-color: #060b14;
                border-right: 1px solid rgba(0,242,255,0.12);
            }
            QLabel { border: none; background: transparent; }
        """)
        ll = QVBoxLayout(left_widget)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(0)

        # ── Styled Section Header ──
        header_bar = QFrame()
        header_bar.setFixedHeight(38)
        header_bar.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(0,242,255,0.12), stop:1 rgba(0,242,255,0.01));
                border-bottom: 1px solid rgba(0,242,255,0.20);
            }
        """)
        hbar_layout = QHBoxLayout(header_bar)
        hbar_layout.setContentsMargins(12, 0, 12, 0)

        lbl_po_header = QLabel("PURCHASE ORDERS")
        lbl_po_header.setStyleSheet(f"""
            QLabel {{
                color: {COLOR_ACCENT_CYAN};
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 2.5px;
                font-family: 'Segoe UI', sans-serif;
                border: none;
                background: transparent;
            }}
        """)
        hbar_layout.addWidget(lbl_po_header)
        hbar_layout.addStretch()
        ll.addWidget(header_bar)

        # ── Date Filter Row ──
        filter_container = QWidget()
        filter_container.setStyleSheet("""
            QWidget { background: rgba(0,0,0,0.25); border-bottom: 1px solid rgba(255,255,255,0.05); }
            QLabel { color: #5a7a99; font-size: 11px; font-weight: 600; border: none; background: transparent; }
        """)
        filter_layout = QHBoxLayout(filter_container)
        filter_layout.setContentsMargins(10, 6, 10, 6)
        filter_layout.setSpacing(6)

        self.date_start = QDateEdit()
        self.date_start.setCalendarPopup(True)
        self.date_start.setDisplayFormat("yyyy-MM-dd")
        self.date_start.setDate(QDate.currentDate().addDays(-30))
        self.date_start.setStyleSheet(ui_theme.get_lineedit_style())
        self.date_start.setFixedWidth(105)
        self.date_start.setFixedHeight(32)

        self.date_end = QDateEdit()
        self.date_end.setCalendarPopup(True)
        self.date_end.setDisplayFormat("yyyy-MM-dd")
        self.date_end.setDate(QDate.currentDate())
        self.date_end.setStyleSheet(ui_theme.get_lineedit_style())
        self.date_end.setFixedWidth(105)
        self.date_end.setFixedHeight(32)

        btn_filter = QPushButton("🔍")
        btn_filter.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_filter.setFixedSize(34, 32)
        btn_filter.setToolTip("Search Orders")
        btn_filter.setStyleSheet("""
            QPushButton {
                background: rgba(0, 242, 255, 0.08);
                color: #00f2ff;
                border: 1px solid rgba(0, 242, 255, 0.30);
                border-radius: 6px;
                font-size: 15px;
                padding: 0px;
            }
            QPushButton:hover {
                background: rgba(0, 242, 255, 0.22);
                border: 1px solid rgba(0, 242, 255, 0.70);
                color: #ffffff;
            }
            QPushButton:pressed {
                background: rgba(0, 242, 255, 0.40);
                border: 1px solid #00f2ff;
                padding-top: 2px;
            }
        """)
        btn_filter.clicked.connect(self.refresh_history_tab)

        filter_layout.addWidget(QLabel("From"))
        filter_layout.addWidget(self.date_start)
        filter_layout.addWidget(QLabel("To"))
        filter_layout.addWidget(self.date_end)
        filter_layout.addWidget(btn_filter)

        ll.addWidget(filter_container)

        # ── Master PO Table ──
        self.table_history_master = QTableWidget()
        self.table_history_master.setColumnCount(2)
        self.table_history_master.setHorizontalHeaderLabels(["", "PURCHASE ORDER"])
        self.table_history_master.setStyleSheet("""
            QTableWidget {
                background-color: #060b14;
                border: none;
                border-radius: 0;
                gridline-color: transparent;
                outline: none;
                selection-background-color: transparent;
                selection-color: transparent;
            }
            QHeaderView::section {
                background-color: #0a1220;
                color: #3a5a78;
                padding: 5px 10px;
                border: none;
                border-bottom: 1px solid rgba(0,242,255,0.10);
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 0.8px;
            }
            QTableWidget::item { padding: 0px; border: none; }
            QTableWidget::item:selected { background: transparent; border: none; }
            QScrollBar:vertical {
                border: none; background: #060b14; width: 5px; margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #1a2a3a; min-height: 24px; border-radius: 2px;
            }
            QScrollBar::handle:vertical:hover { background: rgba(0,242,255,0.4); }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        self.table_history_master.verticalHeader().setVisible(False)
        self.table_history_master.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_history_master.setShowGrid(False)
        self.table_history_master.itemClicked.connect(self.show_po_details)
        # Install event filter on viewport so right-click works even when cellWidgets cover rows
        self.table_history_master.viewport().installEventFilter(self)
        hdr = self.table_history_master.horizontalHeader()
        hdr.setStretchLastSection(True)
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table_history_master.setColumnWidth(0, 38)  # checkbox col
        left_widget.setMinimumWidth(265)

        ll.addWidget(self.table_history_master)

        # Right Panel (Detail): PO Items
        right_widget = QWidget()
        rl = QVBoxLayout(right_widget)
        detail_header = QLabel("ORDER DETAILS")
        detail_header.setStyleSheet(
            f"color: {COLOR_ACCENT_CYAN}; font-size: 13px; font-weight: bold;"
            " letter-spacing: 2px; padding: 4px 0;"
        )
        rl.addWidget(detail_header)

        self.table_history_detail = QTableWidget()
        cols = ["Part", "Name", "Qty", "Rcvd", "Pend", "Disc %", "Price", "GST %", "Total"]
        self.table_history_detail.setColumnCount(len(cols))
        self.table_history_detail.setHorizontalHeaderLabels(cols)
        self.table_history_detail.setStyleSheet(ui_theme.get_table_style())
        self.table_history_detail.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_history_detail.customContextMenuRequested.connect(self._on_history_detail_context_menu)
        self.table_history_detail.verticalHeader().setVisible(False)
        self.table_history_detail.horizontalHeader().setStretchLastSection(False)
        self.table_history_detail.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch) # Name Stretches
        self.table_history_detail.setColumnWidth(0, 110) # Part ID
        self.table_history_detail.setColumnWidth(2, 45)  # Qty
        self.table_history_detail.setColumnWidth(3, 70)  # Rcvd (wider for spinbox)
        self.table_history_detail.setColumnWidth(4, 50)  # Pend
        self.table_history_detail.setColumnWidth(5, 75)  # Disc %
        self.table_history_detail.setColumnWidth(6, 90)  # Price
        self.table_history_detail.setColumnWidth(7, 55)  # GST %
        self.table_history_detail.setColumnWidth(8, 100) # Total

        rl.addWidget(self.table_history_detail)

        # --- Order Summary Frame ---
        self.summary_frame = QFrame()
        self.summary_frame.setStyleSheet(f"""
            QFrame {{
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 8px;
            }}
            QLabel {{ border: none; background: transparent; }}
        """)
        sum_layout = QHBoxLayout(self.summary_frame)
        sum_layout.setContentsMargins(15, 12, 15, 12)
        
        # Summary Labels
        label_style = "color: #a0acb9; font-size: 12px; font-weight: 500;"
        val_style = f"color: {COLOR_TEXT_PRIMARY}; font-size: 14px; font-weight: bold; font-family: 'Segoe UI';"
        
        self.lbl_hist_items = QLabel("0")
        self.lbl_hist_rcvd_items = QLabel("0")
        self.lbl_hist_pend_items = QLabel("0")
        self.lbl_hist_base = QLabel("₹0.00")
        self.lbl_hist_save = QLabel("₹0.00")
        self.lbl_hist_gst = QLabel("₹0.00")
        self.lbl_hist_grand = QLabel("₹0.00")
        self.lbl_hist_rcvd = QLabel("₹0.00")
        
        for lbl in [self.lbl_hist_items, self.lbl_hist_rcvd_items, self.lbl_hist_pend_items]:
            lbl.setStyleSheet(val_style)
            lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        for lbl in [self.lbl_hist_base, self.lbl_hist_gst]:
            lbl.setStyleSheet(val_style)
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.lbl_hist_save.setStyleSheet(ui_theme.get_page_title_style())
        self.lbl_hist_save.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        self.lbl_hist_grand.setStyleSheet(ui_theme.get_page_title_style())
        self.lbl_hist_grand.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        self.lbl_hist_rcvd.setStyleSheet(ui_theme.get_page_title_style())
        self.lbl_hist_rcvd.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        def _make_t(t): 
            l=QLabel(t)
            l.setStyleSheet(label_style)
            l.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return l
        
        # Left Grid - Quantities
        left_grid = QGridLayout()
        left_grid.setVerticalSpacing(8)
        left_grid.setHorizontalSpacing(10)
        
        left_grid.addWidget(_make_t("Ordered Qty:"), 0, 0)
        left_grid.addWidget(self.lbl_hist_items, 0, 1)
        left_grid.addWidget(_make_t("Received Qty:"), 1, 0)
        left_grid.addWidget(self.lbl_hist_rcvd_items, 1, 1)
        self.lbl_hist_pend_title = _make_t("Pending Qty:")
        left_grid.addWidget(self.lbl_hist_pend_title, 2, 0)
        left_grid.addWidget(self.lbl_hist_pend_items, 2, 1)
        left_grid.setRowStretch(3, 1)  # Push to top
        
        # Right Grid - Financials
        right_grid = QGridLayout()
        right_grid.setVerticalSpacing(6)
        right_grid.setHorizontalSpacing(15)
        
        right_grid.addWidget(_make_t("Subtotal:"), 0, 0)
        right_grid.addWidget(self.lbl_hist_base, 0, 1)
        right_grid.addWidget(_make_t("Savings:"), 1, 0)
        right_grid.addWidget(self.lbl_hist_save, 1, 1)
        right_grid.addWidget(_make_t("GST Amount:"), 2, 0)
        right_grid.addWidget(self.lbl_hist_gst, 2, 1)
        
        # Add a subtle divider line before totals
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("background-color: rgba(255,255,255,0.05); border: none; height: 1px;")
        right_grid.addWidget(div, 3, 0, 1, 2)
        
        grand_lbl = _make_t("PO TOTAL:")
        grand_lbl.setStyleSheet(ui_theme.get_page_title_style())
        right_grid.addWidget(grand_lbl, 4, 0)
        right_grid.addWidget(self.lbl_hist_grand, 4, 1)
        
        rcvd_lbl = _make_t("RCVD VALUE:")
        rcvd_lbl.setStyleSheet(ui_theme.get_page_title_style())
        right_grid.addWidget(rcvd_lbl, 5, 0)
        right_grid.addWidget(self.lbl_hist_rcvd, 5, 1)
        
        sum_layout.addLayout(left_grid)
        sum_layout.addStretch()
        sum_layout.addLayout(right_grid)
        
        rl.addWidget(self.summary_frame)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([300, 700])  # 30/70 — order details gets dominant space
        splitter.setStretchFactor(0, 0)  # Left (PO list) doesn't grow with window
        splitter.setStretchFactor(1, 1)  # Right (order details) absorbs all extra width
        l.addWidget(splitter)


        # Bottom Buttons
        btn_layout = QHBoxLayout()

        btn_select_all = QPushButton("☑ SELECT ALL")
        btn_select_all.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_select_all.setFixedHeight(36)
        btn_select_all.setStyleSheet(ui_theme.get_primary_button_style())
        btn_select_all.clicked.connect(self.toggle_select_all_history)

        btn_refresh = QPushButton("🔄 REFRESH HISTORY")
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.setFixedHeight(36)
        btn_refresh.setStyleSheet(ui_theme.get_primary_button_style())
        btn_refresh.clicked.connect(self.refresh_history_tab)

        btn_delete_selected = QPushButton("❌ DELETE PO")
        btn_delete_selected.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_delete_selected.setFixedHeight(36)
        btn_delete_selected.setStyleSheet(ui_theme.get_danger_button_style())
        btn_delete_selected.clicked.connect(self.delete_selected_po)
        
        btn_export_history = QPushButton("📥 EXPORT PO")
        btn_export_history.setToolTip("Export Purchase Order (Ordered quantities)")
        btn_export_history.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_export_history.setFixedHeight(36)
        btn_export_history.setStyleSheet(ui_theme.get_icon_btn_red())
        btn_export_history.clicked.connect(self.export_selected_po_pdf)

        btn_export_grn = QPushButton("📦 EXPORT GRN (BILL)")
        btn_export_grn.setToolTip("Export Inward Bill (Received quantities)")
        btn_export_grn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_export_grn.setFixedHeight(36)
        btn_export_grn.setStyleSheet(ui_theme.get_primary_button_style())
        btn_export_grn.clicked.connect(self.export_selected_grn_pdf)

        btn_whatsapp_history = QPushButton("💬 WHATSAPP PO")
        btn_whatsapp_history.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_whatsapp_history.setFixedHeight(36)
        btn_whatsapp_history.setStyleSheet(ui_theme.get_primary_button_style())
        btn_whatsapp_history.clicked.connect(self.whatsapp_selected_po)

        btn_layout.addWidget(btn_select_all)
        btn_layout.addWidget(btn_refresh)
        btn_layout.addWidget(btn_delete_selected)
        btn_layout.addWidget(btn_export_history)
        btn_layout.addWidget(btn_export_grn)
        btn_layout.addWidget(btn_whatsapp_history)
        btn_layout.addStretch()

        l.addLayout(btn_layout)

    def refresh_history_tab(self):
        # Get dates
        start_date = self.date_start.date().toString("yyyy-MM-dd")
        end_date = self.date_end.date().toString("yyyy-MM-dd")

        # Fetch filtered POs
        rows = self.db_manager.get_all_purchase_orders(start_date, end_date)
        self.populate_history_master(rows)
        self.table_history_detail.setRowCount(0) # Clear details

    def _status_colors(self, status):
        s = str(status).upper()
        if s in ('CLOSED', 'COMPLETED', 'FORCE CLOSED'):
            # Neutral steel-blue/slate: unambiguous "done", not "error"
            return '#2a5a7a', '#6aaccc', 'rgba(20,50,75,0.35)'
        elif s in ('OPEN', 'PENDING'):
            return '#00c864', '#00f288', 'rgba(0,160,80,0.15)'
        elif s == 'PARTIAL':
            return '#cc8800', '#ffb300', 'rgba(180,100,0,0.18)'
        return '#2a3a50', '#5a7a99', 'rgba(20,30,45,0.25)'

    def _make_po_card(self, po_id, supplier, status, due_amount=0.0, pay_status="UNPAID"):
        """Full-width card using _POCard subclass so right-click is always caught."""
        border_col, txt_col, bg_col = self._status_colors(status)
        s = str(status).upper()

        card = _POCard(po_id, self._trigger_po_context_menu)
        card.setStyleSheet(f"""
            QWidget {{
                background-color: #091018;
                border-left: 3px solid {border_col};
                border-bottom: 1px solid rgba(0,0,0,0.5);
            }}
            QLabel {{ border: none; background: transparent; }}
        """)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(10, 6, 8, 6)
        lay.setSpacing(2)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)

        lbl_po = QLabel(po_id)
        lbl_po.setStyleSheet(
            f"color: {txt_col}; font-family: 'Consolas', monospace;"
            " font-size: 11px; font-weight: bold; letter-spacing: 0.5px;"
        )
        lbl_po.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        lbl_status = QLabel(s)
        lbl_status.setStyleSheet(f"""
            QLabel {{
                background: {bg_col}; color: {txt_col};
                border: 1px solid {border_col}; border-radius: 3px;
                font-size: 8px; font-weight: bold;
                letter-spacing: 0.8px; padding: 1px 5px;
            }}
        """)
        lbl_status.setFixedHeight(16)
        lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_status.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        due_amount = float(due_amount or 0)
        fin_col = COLOR_ACCENT_RED if due_amount > 0.01 else COLOR_ACCENT_GREEN
        fin_text = f"DUE: \u20b9{due_amount:,.2f}"
        if str(pay_status).upper() == "PAID":
            fin_text = "\U0001f4b0 PAID"
            fin_col = COLOR_ACCENT_GREEN
        elif str(pay_status).upper() == "PARTIAL":
            fin_col = "#ffb300"

        lbl_fin = QLabel(fin_text)
        lbl_fin.setStyleSheet(
            f"color: {fin_col}; font-size: 9px; font-weight: bold;"
            " background: rgba(0,0,0,0.3); border-radius: 3px; padding: 1px 4px;"
        )
        lbl_fin.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        lbl_sup = QLabel(supplier)
        lbl_sup.setStyleSheet(ui_theme.get_page_title_style())
        lbl_sup.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        top_row.addWidget(lbl_po)
        top_row.addStretch()
        top_row.addWidget(lbl_fin)
        top_row.addWidget(lbl_status)

        lay.addLayout(top_row)
        lay.addWidget(lbl_sup)

        return card

    def _make_status_chip(self, status_text):
        """Return a styled QLabel 3D chip for PO status."""
        s = str(status_text).upper()
        border_col, txt_col, bg_col = self._status_colors(s)
        lbl = QLabel(s)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setFixedHeight(24)
        lbl.setStyleSheet(f"""
            QLabel {{
                background: {bg_col};
                color: {txt_col};
                border: 1px solid {border_col};
                border-radius: 4px;
                font-size: 9px;
                font-weight: bold;
                letter-spacing: 1px;
                padding: 0 6px;
            }}
        """)
        cw = QWidget()
        cl = QHBoxLayout(cw)
        cl.setContentsMargins(4, 0, 4, 0)
        cl.addWidget(lbl)
        return cw

    def populate_history_master(self, rows):
        self.table_history_master.setUpdatesEnabled(False)
        self.table_history_master.blockSignals(True)
        self.table_history_master.setSortingEnabled(False)

        self.table_history_master.setColumnCount(2)
        self.table_history_master.setHorizontalHeaderLabels(["", "PURCHASE ORDER"])
        self.table_history_master.setRowCount(0)
        self.table_history_master.setRowCount(len(rows))

        _CHK_STYLE = """
            QCheckBox { spacing: 0px; }
            QCheckBox::indicator {
                width: 16px; height: 16px;
                border-radius: 3px;
                background: #08111c;
                border: 1.5px solid #1e3550;
            }
            QCheckBox::indicator:hover {
                border: 1.5px solid #00f2ff;
                background: rgba(0,242,255,0.06);
            }
            QCheckBox::indicator:checked {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #006688, stop:1 #003344);
                border: 1.5px solid #00f2ff;
            }
        """

        for r, row in enumerate(rows):
            # row: po_id[0], supplier[1], date[2], status[3]

            # Col 0: Checkbox — compact, centered, consistent with dark theme
            chk = QCheckBox()
            chk.setStyleSheet(_CHK_STYLE)
            _cw = QWidget()
            _cw.setStyleSheet("background-color: #060b14; border: none;")
            _cl = QHBoxLayout(_cw)
            _cl.setContentsMargins(0, 0, 0, 0)
            _cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            _cl.addWidget(chk)
            self.table_history_master.setCellWidget(r, 0, _cw)

            # col 1 has the PO ID in UserRole, and we display it with financials
            ghost = QTableWidgetItem("")  # empty text — prevents bleed-through
            ghost.setData(Qt.ItemDataRole.UserRole, str(row[0]))
            ghost.setFlags(ghost.flags() & ~Qt.ItemFlag.ItemIsEditable)
            
            due_amt = float(row[6]) if len(row) > 6 and row[6] is not None else 0.0
            pay_stat = str(row[7]) if len(row) > 7 and row[7] is not None else "UNPAID"
            
            self.table_history_master.setItem(r, 1, ghost)
            self.table_history_master.setCellWidget(r, 1, self._make_po_card(str(row[0]), str(row[1]), str(row[3]), due_amt, pay_stat))

            self.table_history_master.setRowHeight(r, 48)

        self.table_history_master.setSortingEnabled(True)
        self.table_history_master.blockSignals(False)
        self.table_history_master.setUpdatesEnabled(True)

    def toggle_select_all_history(self):
        """Toggle all checkboxes in the Order History table."""
        # Determine current state: if all are checked, uncheck all; otherwise check all
        all_checked = True
        for r in range(self.table_history_master.rowCount()):
            cw = self.table_history_master.cellWidget(r, 0)
            chk = cw.findChild(QCheckBox) if cw else None
            if chk and not chk.isChecked():
                all_checked = False
                break
        
        new_state = not all_checked
        for r in range(self.table_history_master.rowCount()):
            cw = self.table_history_master.cellWidget(r, 0)
            chk = cw.findChild(QCheckBox) if cw else None
            if chk:
                chk.setChecked(new_state)

    def delete_selected_po(self):
        # Get checked rows
        checked_rows = []
        for r in range(self.table_history_master.rowCount()):
            cw = self.table_history_master.cellWidget(r, 0)
            chk = cw.findChild(QCheckBox) if cw else None
            if chk and chk.isChecked():
                checked_rows.append(r)
        
        if not checked_rows:
            # Fallback to highlighted row
            row = self.table_history_master.currentRow()
            if row < 0:
                ProMessageBox.warning(self, "Selection", "Please select a Purchase Order to delete.")
                return
            checked_rows = [row]
        
        po_ids = [
            self.table_history_master.item(r, 1).data(Qt.ItemDataRole.UserRole)
            or self.table_history_master.item(r, 1).text()
            for r in checked_rows
        ]
        
        msg = f"Are you sure you want to delete {len(po_ids)} PO(s)?\n" + ", ".join(po_ids) + "\nThis cannot be undone."
        reply = ProMessageBox.question(self, "Confirm Delete", msg)
        
        if reply:
            deleted = 0
            for po_id in po_ids:
                success, m = self.db_manager.delete_purchase_order(po_id)
                if success:
                    deleted += 1
            self.refresh_history_tab()
            ProMessageBox.information(self, "Deleted", f"Successfully deleted {deleted} Purchase Order(s).")

    def export_selected_po_pdf(self):
        # Get checked rows
        checked_rows = []
        for r in range(self.table_history_master.rowCount()):
            cw = self.table_history_master.cellWidget(r, 0)
            chk = cw.findChild(QCheckBox) if cw else None
            if chk and chk.isChecked():
                checked_rows.append(r)
        
        if not checked_rows:
            # Fallback to highlighted row
            row = self.table_history_master.currentRow()
            if row >= 0:
                checked_rows = [row]
            else:
                ProMessageBox.warning(self, "Export Failed", "Please check at least one Purchase Order to export.")
                return
        
        # Collect PO data
        po_data_list = []
        for row in checked_rows:
            po_id = (
                self.table_history_master.item(row, 1).data(Qt.ItemDataRole.UserRole)
                or self.table_history_master.item(row, 1).text()
            )
            # All meta from DB — no stale column reads needed
            po_details = self.db_manager.get_purchase_order_by_id(po_id)
            supplier = po_details.get('supplier_name', '') if po_details else ''
            status = po_details.get('status', 'CLOSED') if po_details else 'CLOSED'
            global_disc = po_details.get("global_disc_percent", 0.0) if po_details else 0.0
            # Extract date from PO ID string (e.g. PO-20260328-0003 -> 2026-03-28)
            po_date = "N/A"
            try:
                parts = po_id.split('-')
                if len(parts) >= 3 and len(parts[1]) == 8:
                    d = parts[1]
                    po_date = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
            except:
                pass

            po_header = {
                "PO Number": po_id,
                "To": supplier,
                "Date": po_date,
                "Status": status,
                "global_disc_raw": global_disc
            }
            if global_disc > 0:
                po_header["Global Discount"] = f"{global_disc}%"

            raw_items = self.db_manager.get_po_items(po_id)
            if raw_items:
                po_data_list.append((po_header, raw_items))
        
        if not po_data_list:
            ProMessageBox.warning(self, "Export Failed", "No items found for the selected POs.")
            return
        
        import os
        
        if len(po_data_list) == 1:
            # Single PO → single file
            success, path = self.report_gen.generate_single_po_pdf(po_data_list[0][0], po_data_list[0][1])
        else:
            # Multiple POs → merged file (page by page)
            success, path = self.report_gen.generate_multi_po_pdf(po_data_list)
        
        if success:
            ans = ProMessageBox.question(self, "Success", f"Generated PDF with {len(po_data_list)} PO(s) successfully!\nLocation: {path}\n\nDo you want to share this report via WhatsApp?")
            if ans:
                try:
                    settings = self.db_manager.get_shop_settings()
                    shop_name = settings.get("shop_name", "SpareParts Pro")
                except: shop_name = "SpareParts Pro"
                send_report_msg("Purchase Order Report", shop_name)
                try: os.startfile(os.path.dirname(path))
                except: pass
                ProMessageBox.information(self, "WhatsApp", "Please attach the PDF manually into the chat once WhatsApp Web opens.")
            else:
                try: os.startfile(path)
                except: pass
        else:
            ProMessageBox.critical(self, "Error", f"Failed to generate PDF: {path}")

    def export_selected_grn_pdf(self):
        # Get checked rows
        checked_rows = []
        for r in range(self.table_history_master.rowCount()):
            cw = self.table_history_master.cellWidget(r, 0)
            chk = cw.findChild(QCheckBox) if cw else None
            if chk and chk.isChecked():
                checked_rows.append(r)
        
        if not checked_rows:
            # Fallback to highlighted row
            row = self.table_history_master.currentRow()
            if row >= 0:
                checked_rows = [row]
            else:
                ProMessageBox.warning(self, "Export Failed", "Please check at least one Order to export GRN.")
                return
        
        # Collect PO data
        po_data_list = []
        for row in checked_rows:
            po_id = (
                self.table_history_master.item(row, 1).data(Qt.ItemDataRole.UserRole)
                or self.table_history_master.item(row, 1).text()
            )
            # All meta from DB — no stale column reads needed
            po_details = self.db_manager.get_purchase_order_by_id(po_id)
            supplier = po_details.get('supplier_name', '') if po_details else ''
            status = po_details.get('status', 'CLOSED') if po_details else 'CLOSED'
            global_disc = po_details.get("global_disc_percent", 0.0) if po_details else 0.0
            po_date = "N/A"
            try:
                parts = po_id.split('-')
                if len(parts) >= 3 and len(parts[1]) == 8:
                    d = parts[1]
                    po_date = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
            except:
                pass

            po_header = {
                "PO Number": po_id,
                "To": supplier,
                "Date": po_date,
                "Status": status,
                "global_disc_raw": global_disc
            }
            if global_disc > 0:
                po_header["Global Discount"] = f"{global_disc}%"

            raw_items = self.db_manager.get_po_items(po_id)
            if raw_items:
                po_data_list.append((po_header, raw_items))
        
        if not po_data_list:
            ProMessageBox.warning(self, "Export Failed", "No items found for the selected orders.")
            return
        
        import os
        
        if len(po_data_list) == 1:
            success, path = self.report_gen.generate_single_grn_pdf(po_data_list[0][0], po_data_list[0][1])
        else:
            success, path = self.report_gen.generate_multi_grn_pdf(po_data_list)
        
        if success:
            ans = ProMessageBox.question(self, "Success", f"Generated GRN PDF for {len(po_data_list)} Order(s) successfully!\nLocation: {path}\n\nDo you want to open it right now?")
            if ans:
                try: os.startfile(path)
                except: pass
        else:
            ProMessageBox.critical(self, "Error", f"Failed to generate GRN PDF: {path}")

    def whatsapp_selected_po(self):
        checked_rows = []
        for r in range(self.table_history_master.rowCount()):
            # Col 0 is a cellWidget (QWidget containing QCheckBox), not a QTableWidgetItem
            cw = self.table_history_master.cellWidget(r, 0)
            chk = cw.findChild(QCheckBox) if cw else None
            if chk and chk.isChecked():
                checked_rows.append(r)
        
        if not checked_rows:
            row = self.table_history_master.currentRow()
            if row >= 0:
                checked_rows = [row]
            else:
                ProMessageBox.warning(self, "Export Failed", "Please check at least one Purchase Order to send via WhatsApp.")
                return
                
        if len(checked_rows) > 1:
            ProMessageBox.warning(self, "WhatsApp Limits", "You can only generate a WhatsApp message for 1 Purchase Order at a time. Please uncheck others.")
            return
            
        row = checked_rows[0]
        po_id = self.table_history_master.item(row, 1).text()
        # Extract from DB since col 1 is the only item col now
        po_details_hdr = self.db_manager.get_purchase_order_by_id(po_id)
        supplier = po_details_hdr.get('supplier_name', '') if po_details_hdr else ''
        status = po_details_hdr.get('status', '') if po_details_hdr else ''
        po_date = "N/A"
        try:
            parts = po_id.split('-')
            if len(parts) >= 3 and len(parts[1]) == 8:
                d = parts[1]
                po_date = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
        except:
            pass

        po_details = self.db_manager.get_purchase_order_by_id(po_id)
        global_disc = po_details.get("global_disc_percent", 0.0) if po_details else 0.0
        
        po_header = {
            "PO Number": po_id, "To": supplier, "Date": po_date, "Status": status,
            "global_disc_raw": global_disc  # numeric, used by report math
        }
        if global_disc > 0: po_header["Global Discount"] = f"{global_disc}%"

        raw_items = self.db_manager.get_po_items(po_id)
        if not raw_items:
            ProMessageBox.warning(self, "Export Failed", "No items found for the selected PO.")
            return

        import os
        success, path = self.report_gen.generate_single_po_pdf(po_header, raw_items)
        if not success:
            ProMessageBox.critical(self, "Error", f"Failed to generate PDF: {path}")
            return
            
        vendor_data = self.db_manager.get_vendor_details(supplier)
        vendor_phone = vendor_data[3] if vendor_data else ""
        
        try:
            settings = self.db_manager.get_shop_settings()
            shop_name = settings.get("shop_name", "SpareParts Pro")
        except:
            shop_name = "SpareParts Pro"
            
        msg_success, err = send_po_msg(vendor_phone, supplier, po_id, shop_name)
        
        if msg_success:
             ProMessageBox.information(self, "WhatsApp Triggered", f"Opening WhatsApp for {supplier}...\nPlease attach {path} manually.")
        else:
             ProMessageBox.warning(self, "WhatsApp Failed", f"Missing or invalid mobile number for vendor '{supplier}'.\nPlease update it in the Vendor Registry.")
        
        # Open Folder (Instant drop)
        try:
            folder = os.path.dirname(path)
            os.startfile(folder)
        except: pass

    def show_po_details(self, item):
        row = item.row()
        po_id_item = self.table_history_master.item(row, 1)
        if not po_id_item: return
        # PO ID is stored in UserRole (display text is blank to prevent overlay bleed)
        po_id = po_id_item.data(Qt.ItemDataRole.UserRole) or po_id_item.text()
        if not po_id: return
        
        # Get Header for Global Discount
        po_header = self.db_manager.get_purchase_order_by_id(po_id)
        global_disc = po_header.get('global_disc_percent', 0.0) if po_header else 0.0
        
        items = self.db_manager.get_po_items(po_id)
        self.table_history_detail.setRowCount(0)
        self.table_history_detail.setRowCount(len(items))

        po_status = po_header.get('status', '').upper() if po_header else ''
        if po_status == 'CLOSED':
            self.table_history_detail.horizontalHeaderItem(4).setText("Cancel")
        else:
            self.table_history_detail.horizontalHeaderItem(4).setText("Pend")
        
        total_items = 0
        total_rcvd_qty = 0
        total_pend_qty = 0
        sum_base_val = 0.0
        sum_taxable_val = 0.0
        sum_gst_val = 0.0
        sum_rcvd_taxable_val = 0.0
        sum_rcvd_gst_val = 0.0
        
        _C = QColor  # shorthand
        _DIM = _C('#8899aa')
        _CYAN = _C('#00f2ff')
        _AMBER = _C('#ffb300')
        _ORANGE = _C('#ffa500')
        _GREEN = _C('#00e676')
        _WHITE = _C('#e0eaf5')

        for r, i in enumerate(items):
            # i: id, part_id, part_name, qty_ordered, qty_received, ordered_price, hsn_code, gst_rate, vendor_disc_pct

            # Part ID — cyan chip feel
            it_part = QTableWidgetItem(str(i[1]))
            it_part.setForeground(_CYAN)
            self.table_history_detail.setItem(r, 0, it_part)

            # Part Name
            it_name = QTableWidgetItem(str(i[2]))
            it_name.setForeground(_WHITE)
            self.table_history_detail.setItem(r, 1, it_name)

            # Qty ordered — amber
            it_qty = QTableWidgetItem(str(i[3]))
            it_qty.setForeground(_AMBER)
            it_qty.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            self.table_history_detail.setItem(r, 2, it_qty)

            # Rcvd — static display (Context menu handles edits)
            it_rcvd = QTableWidgetItem(str(i[4]))
            it_rcvd.setForeground(_C('#80d4ff')) # Cyan
            it_rcvd.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            
            # Store PO item data for context menu
            it_rcvd.setData(Qt.ItemDataRole.UserRole, {
                'po_item_id': i[0],
                'po_id': po_id,
                'qty_ordered': float(i[3]),
                'qty_received': float(i[4]),
                'part_name': str(i[2])
            })
            self.table_history_detail.setItem(r, 3, it_rcvd)

            pending = max(0, i[3] - i[4])
            qty = i[3]
            total_items += qty
            total_rcvd_qty += float(i[4])
            total_pend_qty += pending

            it_pend = QTableWidgetItem(str(pending))
            it_pend.setForeground(_C('#ff6b6b') if pending > 0 else _DIM)
            it_pend.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            self.table_history_detail.setItem(r, 4, it_pend)

            # Pricing & Math
            cost = i[5] if len(i) > 5 and i[5] is not None else 0.0
            hsn = i[6] if len(i) > 6 and i[6] else '8714'
            gst = i[7] if len(i) > 7 and i[7] else 18.0
            v_disc = i[8] if len(i) > 8 and i[8] else 0.0

            base_row_total = cost * qty
            sum_base_val += base_row_total
            after_vdisc = cost * (1 - (v_disc / 100.0))
            taxable_rate = after_vdisc * (1 - (global_disc / 100.0))
            row_taxable = taxable_rate * qty
            sum_taxable_val += row_taxable
            row_gst = row_taxable * (gst / 100.0)
            sum_gst_val += row_gst
            row_final = row_taxable + row_gst
            
            qty_rcvd = float(i[4])
            rcvd_taxable = taxable_rate * qty_rcvd
            sum_rcvd_taxable_val += rcvd_taxable
            sum_rcvd_gst_val += (rcvd_taxable * (gst / 100.0))

            if v_disc > 0 and global_disc > 0:
                disc_str = f"{v_disc:g}%+{global_disc:g}%"
            elif v_disc > 0:
                disc_str = f"{v_disc:g}%"
            elif global_disc > 0:
                disc_str = f"{global_disc:g}%(G)"
            else:
                disc_str = "-"

            it_disc = QTableWidgetItem(disc_str)
            it_disc.setForeground(_ORANGE)
            it_disc.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            self.table_history_detail.setItem(r, 5, it_disc)

            it_price = QTableWidgetItem(f"{cost:.2f}")
            it_price.setForeground(_C('#ffe082'))
            it_price.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table_history_detail.setItem(r, 6, it_price)

            it_gst = QTableWidgetItem(str(gst))
            it_gst.setForeground(_DIM)
            it_gst.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            self.table_history_detail.setItem(r, 7, it_gst)

            it_total = QTableWidgetItem(f"{row_final:.2f}")
            it_total.setForeground(_GREEN)
            it_total.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            f = it_total.font(); f.setBold(True); it_total.setFont(f)
            self.table_history_detail.setItem(r, 8, it_total)

            self.table_history_detail.setRowHeight(r, 36)


        # Update Summary Panel
        savings = sum_base_val - sum_taxable_val
        grand_total = sum_taxable_val + sum_gst_val
        rcvd_grand_total = sum_rcvd_taxable_val + sum_rcvd_gst_val
        
        if hasattr(self, 'lbl_hist_items'):
            self.lbl_hist_items.setText(f"{total_items:g}")
            self.lbl_hist_rcvd_items.setText(f"{total_rcvd_qty:g}")
            self.lbl_hist_pend_items.setText(f"{total_pend_qty:g}")
            self.lbl_hist_base.setText(f"₹{sum_base_val:,.2f}")
            self.lbl_hist_save.setText(f"₹{savings:,.2f}")
            self.lbl_hist_gst.setText(f"₹{sum_gst_val:,.2f}")
            self.lbl_hist_grand.setText(f"₹{grand_total:,.2f}")
            
            if hasattr(self, 'lbl_hist_pend_title'):
                if po_header and po_header.get('status', '').upper() == 'CLOSED':
                    self.lbl_hist_pend_title.setText("Cancelled Qty:")
                else:
                    self.lbl_hist_pend_title.setText("Pending Qty:")
            
        if hasattr(self, 'lbl_hist_rcvd'):
            self.lbl_hist_rcvd.setText(f"₹{rcvd_grand_total:,.2f}")

    def _on_history_detail_context_menu(self, pos):
        """Context menu replacing the exposed spinbox for future-readiness."""
        row = self.table_history_detail.rowAt(pos.y())
        if row < 0: return
        
        rcvd_item = self.table_history_detail.item(row, 3)
        if not rcvd_item: return
        
        data = rcvd_item.data(Qt.ItemDataRole.UserRole)
        if not data: return
        
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self.table_history_detail)
        menu.setStyleSheet(r"""
            QMenu { background-color: #0d1117; color: #c9d1d9; border: 1px solid #30363d; border-radius: 4px; }
            QMenu::item { padding: 6px 24px; font-weight: bold; }
            QMenu::item:selected { background-color: #21262d; color: #58a6ff; }
            QMenu::separator { height: 1px; background: #30363d; margin: 4px 0px; }
        """)
        
        action_edit = menu.addAction("✏️ Correct Received Qty")
        menu.addSeparator()
        action_return = menu.addAction("📦 Process Purchase Return (Coming Soon)")
        action_return.setEnabled(False)  # Placeholder for future logic
        
        action = menu.exec(self.table_history_detail.viewport().mapToGlobal(pos))
        
        if action == action_edit:
            self._edit_historical_rcvd_qty(row, data)

    def _edit_historical_rcvd_qty(self, row, data):
        """Securely updates DB + forces an instant full-recalculation of the summary UI."""
        po_item_id = data['po_item_id']
        po_id = data['po_id']
        qty_ordered = data['qty_ordered']
        current_rcvd = data['qty_received']
        part_name = data['part_name']

        from PyQt6.QtWidgets import QInputDialog
        new_rcvd, ok = QInputDialog.getInt(
            self, 
            "Correct Received Qty", 
            f"Enter truthful received quantity for '{part_name}':\n\n(Cannot exceed ordered quantity: {qty_ordered})",
            value=current_rcvd, 
            min=0, 
            max=qty_ordered
        )

        if ok and new_rcvd != current_rcvd:
            # Update DB using existing safe method
            success, msg = self.db_manager.update_po_item_received(po_item_id, new_rcvd, po_id)
            if success:
                app_logger.info(f"Corrected PO item {po_item_id}: rcvd={new_rcvd}")
                # Re-rendering the master row implicitly recalculates all financial totals flawlessly
                master_row = self.table_history_master.currentRow()
                if master_row >= 0:
                    history_item = self.table_history_master.item(master_row, 1)
                    if history_item:
                        self.show_po_details(history_item)
            else:
                ProMessageBox.critical(self, "Error", f"Failed to update: {msg}")

    def eventFilter(self, source, event):
        """Fallback: handle right-click on raw table viewport (empty row area)."""
        from PyQt6.QtCore import QEvent
        if (event.type() == QEvent.Type.MouseButtonPress
                and event.button() == Qt.MouseButton.RightButton
                and source is self.table_history_master.viewport()):
            index = self.table_history_master.indexAt(event.pos())
            if index.isValid():
                po_id_item = self.table_history_master.item(index.row(), 1)
                if po_id_item:
                    pid = po_id_item.data(Qt.ItemDataRole.UserRole) or po_id_item.text()
                    if pid:
                        self._trigger_po_context_menu(pid)
                        return True
        return super().eventFilter(source, event)

    def _trigger_po_context_menu(self, po_id):
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtGui import QAction, QCursor

        menu = QMenu(self)
        menu.setStyleSheet(ui_theme.get_dropdown_style())
        
        act_pay = QAction("💰 Pay Vendor (Settle Due)", self)
        act_pay.triggered.connect(lambda: self._handle_pay_vendor(po_id))
        
        act_hist = QAction("💳 Payment History By Order", self)
        act_hist.triggered.connect(lambda: self._show_po_payment_history(po_id))

        menu.addAction(act_pay)
        menu.addAction(act_hist)
        
        menu.exec(QCursor.pos())
        
    def _handle_pay_vendor(self, po_id):
        po_details = self.db_manager.get_purchase_order_by_id(po_id)
        if not po_details: return
        due = float(po_details.get("due_amount", 0.0))
        if due <= 0:
            ProMessageBox.information(self, "Settled", "This Purchase Order is already fully paid.")
            return

        dialog = VendorPaymentDialog(self, po_id, po_details.get("supplier_name", ""), due)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            cash, upi = dialog.get_payment_data()
            total_paid_now = cash + upi
            if total_paid_now <= 0: return

            new_due = max(0.0, due - total_paid_now)
            prev_paid = float(po_details.get("paid_amount", 0.0))
            new_paid = prev_paid + total_paid_now
            
            new_status = "PARTIAL" if new_due > 0.01 else "PAID"

            success, msg = self.db_manager.update_po_financials(po_id, new_paid, new_due, new_status)
            if success:
                if cash > 0: self.db_manager.log_po_payment(po_id, po_details.get("supplier_name", ""), cash, "CASH")
                if upi > 0: self.db_manager.log_po_payment(po_id, po_details.get("supplier_name", ""), upi, "UPI")
                self.refresh_history_tab()
                ProMessageBox.information(self, "Success", f"Payment logged successfully.\nRemaining Due: ₹ {new_due:,.2f}")
            else:
                ProMessageBox.critical(self, "Error", f"Failed to log payment: {msg}")

    def _show_po_payment_history(self, po_id):
        logs = self.db_manager.get_po_payment_history(po_id)
        if not logs:
            ProMessageBox.information(self, "No History", "No isolated payment history logged for this specific order yet.")
            return
            
        dialog = QDialog(self)
        dialog.setWindowTitle(f"💳 Payment History: {po_id}")
        dialog.setStyleSheet(ui_theme.get_dialog_style())
        dialog.setMinimumSize(450, 400)
        lay = QVBoxLayout(dialog)
        
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Datetime", "Amount", "Mode"])
        table.setStyleSheet(ui_theme.get_table_style())
        table.horizontalHeader().setStretchLastSection(True)
        table.setRowCount(len(logs))
        
        from PyQt6.QtGui import QColor
        for i, row in enumerate(logs):
            table.setItem(i, 0, QTableWidgetItem(str(row[0])))
            table.setItem(i, 1, QTableWidgetItem(f"₹ {float(row[1]):,.2f}"))
            m = str(row[2]).upper()
            item_m = QTableWidgetItem(m)
            if m == "CASH": item_m.setForeground(QColor(COLOR_ACCENT_CYAN))
            elif m == "UPI": item_m.setForeground(QColor(COLOR_ACCENT_GREEN))
            table.setItem(i, 2, item_m)
            
        lay.addWidget(table)
        dialog.exec()

    # --- TAB 5: VENDOR REGISTRY ---
    def setup_vendors_tab(self):
        l = QVBoxLayout(self.tab_vendors)
        l.setContentsMargins(DIM_MARGIN_STD, DIM_MARGIN_STD, DIM_MARGIN_STD, DIM_MARGIN_STD)
        
        self.vendor_manager_widget = VendorManagerWidget(self.db_manager)
        l.addWidget(self.vendor_manager_widget)


class VendorPaymentDialog(ProDialog):
    def __init__(self, parent, po_id, vendor_name, amount_due):
        super().__init__(parent)
        self.setWindowTitle(f"💰 Settle Payment: {po_id}")
        self.amount_due = amount_due
        
        lay = QVBoxLayout(self.content_widget)
        lay.setSpacing(12)
        
        lbl_info = QLabel(f"<b>Vendor:</b> {vendor_name}<br><b>Amount Due:</b> ₹ {amount_due:,.2f}")
        lbl_info.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-size: 13px;")
        lay.addWidget(lbl_info)
        
        form_lay = QFormLayout()
        self.spin_cash = QDoubleSpinBox()
        self.spin_cash.setMaximum(99999999)
        self.spin_cash.setStyleSheet(STYLE_INPUT_CYBER)
        self.spin_cash.setFixedHeight(34)
        
        self.spin_upi = QDoubleSpinBox()
        self.spin_upi.setMaximum(99999999)
        self.spin_upi.setStyleSheet(STYLE_INPUT_CYBER)
        self.spin_upi.setFixedHeight(34)
        
        form_lay.addRow("CASH Payment:", self.spin_cash)
        form_lay.addRow("UPI Payment:", self.spin_upi)
        lay.addLayout(form_lay)
        
        btn_lay = QHBoxLayout()
        btn_save = QPushButton("LOG PAYMENT")
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.setStyleSheet(ui_theme.get_success_button_style())
        btn_save.clicked.connect(self._validate_and_accept)
        btn_lay.addStretch()
        btn_lay.addWidget(btn_save)
        
        lay.addLayout(btn_lay)
        
    def _validate_and_accept(self):
        total = self.spin_cash.value() + self.spin_upi.value()
        if total <= 0:
            QMessageBox.warning(self, "Invalid", "Payment amount must be greater than zero.")
            return
        if total > self.amount_due:
            reply = QMessageBox.question(self, "Overpayment", f"Total payment (₹{total:,.2f}) exceeds the Due Amount (₹{self.amount_due:,.2f}).\\nDo you want to proceed anyway?")
            if reply != QMessageBox.StandardButton.Yes: return
        self.accept()
        
    def get_payment_data(self):
        return self.spin_cash.value(), self.spin_upi.value()
