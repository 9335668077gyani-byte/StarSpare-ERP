from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem, 
                             QPushButton, QHeaderView, QTabWidget, QAbstractItemView, QFrame, QLineEdit, 
                             QDialog, QFormLayout, QFileDialog, QCheckBox, QCompleter, QComboBox, QSpinBox, QDateEdit, QMessageBox, QGridLayout)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QDate
from PyQt6.QtGui import QColor
from pandas import DataFrame
import pandas as pd
import ui_theme
from styles import (STYLE_TABLE_CYBER, STYLE_NEON_BUTTON, STYLE_INPUT_CYBER, COLOR_ACCENT_CYAN, 
                   COLOR_SURFACE, COLOR_TEXT_PRIMARY, DIM_MARGIN_STD, DIM_SPACING_STD, COLOR_ACCENT_GREEN, 
                   STYLE_DANGER_BUTTON, STYLE_TAB_WIDGET, STYLE_GLASS_PANEL, STYLE_BUTTON_PRIMARY,
                   STYLE_BUTTON_SUCCESS, STYLE_DROPDOWN_CYBER)
from logger import app_logger
from custom_components import ProMessageBox, ProDialog, ProTableDelegate
from vendor_manager import VendorManagerDialog, VendorManagerWidget
from report_generator import ReportGenerator


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
            
            col_qty = find_col(['qty', 'quantity', 'stock', 'pack', 'moq'], exclude=found)
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
                    try: sheet_qty = int(float(row[col_qty]))
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
                
                # Aggregate by Part ID if available, else Fallback to Name
                if p_id != "NEW":
                    key = p_id.lower()
                else:
                    key = name.lower()

                if key in aggregated:
                    aggregated[key]["qty"] += sheet_qty
                    # Keep the latest price
                    if price > 0:
                        aggregated[key]["price"] = price
                    
                    # Update ID if we found a valid one (merging into a "NEW" id entry)
                    if p_id != "NEW":
                        aggregated[key]["p_id"] = p_id
                        
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
    def __init__(self, parent=None, item_data=None):
        super().__init__(parent, title="RECEIVE ITEMS", width=400, height=380)
        self.item_data = item_data # (id, po_id, supplier, part_name, ordered, received, pending, part_id)
        
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
        self.in_qty.setText(str(item_data[6])) # Default to pending qty
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
                    self.in_price.setText(str(result[0]))
                else:
                    # Fallback: Try to get from inventory if po_items has no price
                    part_id = item_data[7]
                    part = parent.db_manager.get_part_by_id(part_id)
                    if part and part[3]:
                        self.in_price.setText(str(part[3]))
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
        btn_cancel.setStyleSheet(f"background: transparent; color: #888; border: 1px solid #555; padding: 6px 16px; border-radius: 4px; font-weight: bold;")
        btn_cancel.clicked.connect(self.reject)
        
        btn_ok = QPushButton("RECEIVE")
        btn_ok.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_ok.setStyleSheet(ui_theme.get_primary_button_style())
        btn_ok.clicked.connect(self.accept)
        
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_ok)
        
        self.add_buttons(btn_layout)
        
    def get_data(self):
        try:
            qty = int(self.in_qty.text().strip())
            price_text = self.in_price.text().strip()

            if not price_text:
                return None, None  # Guard: price left blank

            price = float(price_text)

            if qty <= 0:
                return None, None  # Guard: nonsense quantity

            return qty, price
        except ValueError:
            return None, None


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
        lbl_name.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {COLOR_ACCENT_CYAN}; letter-spacing: 1px;")
        v_layout.addWidget(lbl_name)
        
        lbl_badge = QLabel("OFFICIAL VENDOR")
        lbl_badge.setStyleSheet(f"background-color: {COLOR_ACCENT_GREEN}; color: black; padding: 2px 8px; border-radius: 3px; font-weight: bold; font-size: 10px;")
        lbl_badge.setFixedSize(110, 20)
        lbl_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v_layout.addWidget(lbl_badge)
        header_layout.addLayout(v_layout)
        
        header_layout.addSpacing(30)
        
        # 2. Key Details (Horizontal)
        def make_info(label, value, icon="🔹"):
            l = QLabel(f"{icon} <b>{label}:</b> <span style='color:{COLOR_TEXT_PRIMARY}'>{value}</span>")
            l.setStyleSheet("color: #aaa; font-size: 13px;")
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
        btn_close.setStyleSheet("background: transparent; color: #888; font-size: 16px; border: none;")
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
        
        filter_layout.addWidget(QLabel("From:"))
        filter_layout.addWidget(self.date_start)
        filter_layout.addWidget(QLabel("To:"))
        filter_layout.addWidget(self.date_end)
        filter_layout.addWidget(self.txt_po_search)
        filter_layout.addWidget(btn_filter)
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
        
        # Tab B: Catalog
        tab_cat = QWidget()
        l_cat = QVBoxLayout(tab_cat)
        
        # Toolbar
        cat_toolbar = QHBoxLayout()
        btn_import = QPushButton("📥 Import Excel")
        btn_import.setStyleSheet(ui_theme.get_primary_button_style())
        btn_import.clicked.connect(self.import_catalog_excel)
        
        btn_create_po = QPushButton("📝 Create PO from Selection")
        btn_create_po.setStyleSheet(f"background-color: {COLOR_ACCENT_CYAN}; color: black; font-weight: bold; border-radius: 4px; padding: 5px 10px;")
        btn_create_po.clicked.connect(self.create_po_from_selection)
        
        cat_toolbar.addWidget(QLabel("SUPPLY CATALOG"))
        
        # Total Parts Count
        self.lbl_catalog_count = QLabel("📦 Total: 0")
        self.lbl_catalog_count.setStyleSheet(f"color: {COLOR_ACCENT_CYAN}; font-weight: bold; font-size: 12px; padding: 4px 10px; background: rgba(0,242,255,0.08); border-radius: 4px;")
        cat_toolbar.addWidget(self.lbl_catalog_count)
        
        # Selected Parts Count
        self.lbl_selected_count = QLabel("✅ Selected: 0")
        self.lbl_selected_count.setStyleSheet(f"color: {COLOR_ACCENT_GREEN}; font-weight: bold; font-size: 12px; padding: 4px 10px; background: rgba(0,255,65,0.08); border-radius: 4px;")
        cat_toolbar.addWidget(self.lbl_selected_count)
        
        # Order Value Counter
        self.lbl_order_value = QLabel("💰 Value: ₹0.00")
        self.lbl_order_value.setStyleSheet(f"color: #FFD700; font-weight: bold; font-size: 12px; padding: 4px 10px; background: rgba(255,215,0,0.08); border-radius: 4px;")
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
        self.fixed_cols = ["Select", "Part ID", "Part Name", "Stock", "Price", "Reorder", "Order Qty"]
        self.extra_col_names = self.db_manager.get_vendor_catalog_columns(self.vendor_name)
        all_cols = self.fixed_cols + self.extra_col_names
        
        self.table_cat = QTableWidget()
        self.table_cat.setColumnCount(len(all_cols))
        self.table_cat.setHorizontalHeaderLabels(all_cols)
        self.table_cat.setStyleSheet(STYLE_TABLE_CYBER + "\nQTableWidget { background-color: #0b0b14; gridline-color: #1a1a2e; }")
        
        # Apply ProTableDelegate (same as inventory table)
        self.cat_delegate = ProTableDelegate(self.table_cat)
        for c in range(self.table_cat.columnCount()):
            self.table_cat.setItemDelegateForColumn(c, self.cat_delegate)
        
        # Column Resizing
        header = self.table_cat.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch) # Part Name fills space
        
        self.table_cat.setColumnWidth(0, 65) # Checkbox
        self.table_cat.setColumnWidth(1, 100) # ID
        self.table_cat.setColumnWidth(3, 80) # Stock
        self.table_cat.setColumnWidth(4, 80) # Price
        self.table_cat.setColumnWidth(5, 80) # Reorder
        self.table_cat.setColumnWidth(6, 80) # Order Qty
        
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
            # cat: code, name, price, ref_stock, extra_data
            code, name, price, ref_stock = cat[0], cat[1], cat[2], cat[3]
            extra_raw = cat[4] if len(cat) > 4 else None
            
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
                "reorder": d_reorder, "qty": 0, "extra": extra
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
                reorder = self.table_cat.item(r, 5).text()
                
                # Get Order Qty
                try:
                    qty = int(self.table_cat.item(r, 6).text())
                except:
                    qty = 1
                
                items.append({
                    "id": p_id,
                    "name": name,
                    "stock": stock,
                    "reorder": reorder,
                    "price": price,
                    "vendor": self.vendor_name,
                    "qty": qty  # Pass actual qty
                })
        
        if not items:
            ProMessageBox.warning(self, "Selection", "Please select items to order.")
            return
            
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

        # Handle Order Qty Edit (Column 6)
        if item.column() != 6: return
        
        row = item.row()
        try:
            p_id = self.table_cat.item(row, 1).text()
            name = self.table_cat.item(row, 2).text()
            price_txt = self.table_cat.item(row, 4).text()
            price = float(price_txt) if price_txt else 0.0
            
            new_qty_txt = item.text()
            new_qty = int(new_qty_txt) if new_qty_txt else 0
            
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
            
            # Save to DB
            self.db_manager.save_catalog_item(self.vendor_name, p_id, name, price, new_qty)
            
            item.setForeground(QColor(COLOR_ACCENT_GREEN))  # Green = saved
            
            # Update order value
            self.update_order_value()
            
        except Exception as e:
            app_logger.error(f"Failed to update catalog item: {e}")
            item.setForeground(QColor("red"))

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
        self.table_cat.setItem(r, 5, make_readonly(item["reorder"]))
        
        # Order Qty (Editable)
        qty_val = str(item["qty"]) if item["qty"] else "0"
        item_qty = QTableWidgetItem(qty_val)
        item_qty.setForeground(QColor(COLOR_ACCENT_CYAN))
        self.table_cat.setItem(r, 6, item_qty)
        
        # Extra columns
        for ci, col_name_x in enumerate(self.extra_col_names):
            val = item.get("extra", {}).get(col_name_x, "")
            self.table_cat.setItem(r, 7 + ci, make_readonly(val))
        
        # Apply color coding
        self.apply_row_color(r)

    def apply_row_color(self, row):
        """Apply priority-based color coding to a catalog row.
        Priority: Selected (cyan) > Recently Ordered (orange) > Low Stock (red) > Default"""
        name_item = self.table_cat.item(row, 2)
        chk_item = self.table_cat.item(row, 0)
        stock_item = self.table_cat.item(row, 3)
        reorder_item = self.table_cat.item(row, 5)
        
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
            bg_color = QColor("#0f3460")      # Cyan/Blue tint - SELECTED
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
                    qty = int(self.table_cat.item(r, 6).text() or "0")
                    total += price * qty
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

class PurchaseOrderPage(QWidget):

    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self.part_cache = [] # List of tuples (id, name, stock, reorder, vendor)
        self.report_gen = ReportGenerator(db_manager)  # Bug fix: was missing, caused AttributeError on PDF export
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
            # rows: 0:id, 1:name, ..., 4:qty, ..., 7:reorder, 8:vendor
            self.part_cache = []
            search_list = []
            for r in rows:
                 pid = r[0]
                 name = r[1]
                 qty = r[4]
                 price = r[3] if len(r) > 3 and r[3] is not None else 0.0 # Index 3 is unit_price
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
        header.setStyleSheet(f"font-size: 24px; font-weight: bold; color: {COLOR_ACCENT_CYAN}; letter-spacing: 1px;")
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
        lbl_supp.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-weight: bold; font-size: 14px;")
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
        self.btn_profile.setFixedSize(120, 40)
        self.btn_profile.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_profile.setStyleSheet(ui_theme.get_primary_button_style())
        self.btn_profile.clicked.connect(self.open_supplier_profile)
        top_layout.addWidget(self.btn_profile)

        # New Vendor Button
        self.btn_new_vendor = QPushButton("➕ NEW VENDOR")
        self.btn_new_vendor.setFixedSize(140, 40)
        self.btn_new_vendor.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new_vendor.setStyleSheet(STYLE_BUTTON_SUCCESS)
        self.btn_new_vendor.clicked.connect(self.open_new_vendor_dialog)
        top_layout.addWidget(self.btn_new_vendor)

        top_layout.addStretch()

        # Action Buttons
        self.btn_export = QPushButton("📥 EXPORT")
        self.btn_export.setFixedSize(120, 40)
        self.btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_export.setStyleSheet(ui_theme.get_primary_button_style())
        self.btn_export.clicked.connect(self.export_po_excel)
        top_layout.addWidget(self.btn_export)
        
        self.btn_clear_po = QPushButton("🧹 CLEAR PO")
        self.btn_clear_po.setFixedSize(120, 40)
        self.btn_clear_po.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear_po.setStyleSheet(STYLE_DANGER_BUTTON)
        self.btn_clear_po.clicked.connect(self.clear_po_action)
        top_layout.addWidget(self.btn_clear_po)

        self.btn_save_po = QPushButton("💾 SAVE PO")
        self.btn_save_po.setFixedSize(120, 40)
        self.btn_save_po.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save_po.setStyleSheet(STYLE_BUTTON_PRIMARY)
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

        self.in_qty_add = QSpinBox()
        self.in_qty_add.setRange(1, 9999)
        self.in_qty_add.setValue(10)
        self.in_qty_add.setFixedWidth(80)
        self.in_qty_add.setFixedHeight(40)
        self.in_qty_add.setStyleSheet(f"""
            QSpinBox {{
                background-color: #0b0e14;
                color: {COLOR_ACCENT_CYAN};
                border: 1px solid #1a2a3a;
                border-radius: 4px;
                padding: 5px;
                font-family: 'Consolas', monospace;
                font-size: 14px;
                font-weight: bold;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{ width: 20px; border: none; background: #1a2a3a; }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{ background: {COLOR_ACCENT_CYAN}; }}
        """)
        add_layout.addWidget(self.in_qty_add)

        btn_add = QPushButton("➕ ADD TO LIST")
        btn_add.setFixedSize(140, 40)
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.setStyleSheet(STYLE_BUTTON_SUCCESS)
        btn_add.clicked.connect(self.add_item_from_search)
        add_layout.addWidget(btn_add)
        
        # New Feature: Auto-Fill Shortage
        self.btn_auto_fill = QPushButton("⚡ Auto-Fill Shortage")
        self.btn_auto_fill.setFixedSize(170, 40)
        self.btn_auto_fill.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_auto_fill.setStyleSheet(ui_theme.get_primary_button_style())
        self.btn_auto_fill.clicked.connect(self.auto_fill_shortage)
        add_layout.addWidget(self.btn_auto_fill)
        
        add_layout.addStretch()

        l.addWidget(panel_add)

        # --- Section 3: Table ---
        self.table_create = QTableWidget()
        cols = ["Part ID", "Part Name", "Current Stock", "Order Qty", "Buy Price", "HSN Code", "GST %", "Total", "Remove"]
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
        self.table_create.setColumnWidth(2, 100) # Stock
        self.table_create.setColumnWidth(3, 100) # Order Qty
        self.table_create.setColumnWidth(4, 90) # Buy Price
        self.table_create.setColumnWidth(5, 80) # HSN Code
        self.table_create.setColumnWidth(6, 75) # GST %
        self.table_create.setColumnWidth(7, 120) # Total
        self.table_create.setColumnWidth(8, 100) # Remove

        self.table_create.itemChanged.connect(self.on_create_item_changed)

        l.addWidget(self.table_create)
        
        # --- Section 4: Summary Panel ---
        panel_summary = QFrame()
        panel_summary.setStyleSheet(STYLE_GLASS_PANEL)
        sum_layout = QHBoxLayout(panel_summary)
        sum_layout.setContentsMargins(15, 10, 15, 10)
        sum_layout.addStretch()
        
        self.lbl_taxable = QLabel("Taxable Value: ₹0.00")
        self.lbl_taxable.setStyleSheet("color: #ccc; font-weight: bold; font-size: 14px; margin-right: 20px;")
        sum_layout.addWidget(self.lbl_taxable)
        
        self.lbl_gst = QLabel("Total GST: ₹0.00")
        self.lbl_gst.setStyleSheet("color: #ccc; font-weight: bold; font-size: 14px; margin-right: 20px;")
        sum_layout.addWidget(self.lbl_gst)
        
        self.lbl_grand_total = QLabel("Grand Total: ₹0.00")
        self.lbl_grand_total.setStyleSheet(f"color: {COLOR_ACCENT_GREEN}; font-weight: bold; font-size: 16px;")
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
        try:
            self.table_create.blockSignals(True)
            for r in range(self.table_create.rowCount()):
                try: qty = int(self.table_create.item(r, 3).text())
                except: qty = 0
                
                try: price = float(self.table_create.item(r, 4).text())
                except: price = 0.0
                
                try: gst_percent = float(self.table_create.item(r, 6).text())
                except: gst_percent = 0.0
                
                row_total = qty * price
                
                # Reverse Math
                taxable_val = row_total / (1 + (gst_percent / 100.0))
                row_gst = row_total - taxable_val
                
                taxable += taxable_val
                total_gst += row_gst
                
                # Update row total (MRP * Qty)
                self.table_create.item(r, 7).setText(f"{row_total:.2f}")
                
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
        box.setStyleSheet("background-color: #1e1e2d; color: white; font-size: 14px;")
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

    def add_row_to_create_table(self, item_data, default_qty=None, default_price=None):
        # item_data: (id, name, stock, reorder, vendor, price, hsn, gst)

        # Check if already exists (Duplicate Merge)
        for r in range(self.table_create.rowCount()):
            if self.table_create.item(r, 0).text() == str(item_data[0]):
                add_qty = default_qty if default_qty else self.in_qty_add.value()
                try: curr_qty = int(self.table_create.item(r, 3).text())
                except: curr_qty = 0
                
                self.table_create.blockSignals(True)
                self.table_create.item(r, 3).setText(str(curr_qty + add_qty))
                self.table_create.blockSignals(False)
                
                self.update_po_totals()
                return

        self.table_create.blockSignals(True)

        r = self.table_create.rowCount()
        self.table_create.insertRow(r)
        
        # ID
        self.table_create.setItem(r, 0, QTableWidgetItem(str(item_data[0])))
        # Name
        part_name = str(item_data[1])
        part_name_lower = part_name.lower()
        self.table_create.setItem(r, 1, QTableWidgetItem(part_name))
        # Stock
        self.table_create.setItem(r, 2, QTableWidgetItem(str(item_data[2])))

        # Calc Qty
        qty = default_qty if default_qty else self.in_qty_add.value()

        self.table_create.setItem(r, 3, QTableWidgetItem(str(qty)))

        # Price Priority: Passed arg > Cache > 0.0
        price = 0.0
        if default_price is not None:
             try: price = float(default_price)
             except: price = 0.0
        else:
             try: price = float(item_data[5]) if len(item_data) > 5 and item_data[5] else 0.0
             except: price = 0.0
             
        self.table_create.setItem(r, 4, QTableWidgetItem(f"{price:.2f}"))

        # Smart Tax Engine Priority: DB-stored > HSN Reference Search > Default
        hsn = ""
        gst = 18.0
        
        # 1. Load defaults from DB cache
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
            
        self.table_create.setItem(r, 5, QTableWidgetItem(str(hsn) if hsn else "87089900"))
        self.table_create.setItem(r, 6, QTableWidgetItem(f"{gst:.1f}"))

        # Total
        self.table_create.setItem(r, 7, QTableWidgetItem("0.00")) # To be updated by update_po_totals

        # Remove Btn
        btn_del = QPushButton("REMOVE")
        btn_del.setFixedSize(70, 24)
        btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del.setStyleSheet("border: 1px solid red; border-radius: 4px; color: red; font-weight: bold; font-size: 10px;")
        btn_del.clicked.connect(lambda _, row=r: self.remove_create_row(row))
        self.table_create.setCellWidget(r, 8, btn_del)

        self.table_create.blockSignals(False)
        self.update_po_totals()

        # Auto-fill supplier if empty
        if not self.in_supplier.currentText() and len(item_data) > 4 and item_data[4]:
             self.in_supplier.setCurrentText(item_data[4])
             
    def remove_create_row(self, r):
        # We need to find the correct row index dynamically because it might change
        for i in range(self.table_create.rowCount()):
            if self.table_create.cellWidget(i, 8) == self.sender():
                self.table_create.removeRow(i)
                self.update_po_totals()
                return

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
            box.setStyleSheet("background-color: #1e1e2d; color: white; font-size: 14px;")
            
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
        if item.column() in [3, 5, 6]:  # Qty, GST %, Price
             self.update_po_totals()

    def load_items_from_inventory(self, item_list):
        """
        Called from InventoryPage.
        item_list: list of [id, name, stock, reorder, vendor_name]
        Returns: True if successful (items loaded), False if cancelled.
        """
        # Safety Check: Draft Protection
        if self.table_create.rowCount() > 0:
            current_vendor = self.in_supplier.currentText()
            # Try to guess new vendor from first item (if consistent)
            new_vendors = set([i[4] for i in item_list if i[4]])
            new_vendor = list(new_vendors)[0] if len(new_vendors) == 1 else "Various"
            
            msg = "You have unsaved items in your Purchase Order.<br>"
            if current_vendor and new_vendors and current_vendor != new_vendor:
                 msg += f"⚠️ <b>Warning:</b> Current PO is for '<b>{current_vendor}</b>', new items include '<b>{new_vendor}</b>'.<br>"
            
            msg += "<br>Do you want to <b>APPEND</b> to the current list or <b>OVERWRITE</b> it?"
            
            box = QMessageBox(self)
            box.setWindowTitle("Draft PO Found")
            box.setText(msg)
            box.setIcon(QMessageBox.Icon.Question)
            
            btn_append = box.addButton("Append", QMessageBox.ButtonRole.AcceptRole)
            btn_overwrite = box.addButton("Overwrite", QMessageBox.ButtonRole.DestructiveRole)
            btn_cancel = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            
            box.setStyleSheet("background-color: #1e1e2d; color: white; font-size: 14px;")
            box.exec()
            
            if box.clickedButton() == btn_cancel:
                return False
            elif box.clickedButton() == btn_overwrite:
                self.table_create.setRowCount(0)
            # else Append -> fall through
        else:
             self.table_create.setRowCount(0)

        # Reset Supplier if common AND we are starting fresh (or explicitly overwriting)
        # If appending, we probably want to keep the current supplier unless it was empty
        is_fresh = (self.table_create.rowCount() == 0)
        
        suppliers = set([i[4] for i in item_list if i[4]])
        if is_fresh:
            if len(suppliers) == 1:
                self.in_supplier.setCurrentText(list(suppliers)[0])
            else:
                self.in_supplier.setCurrentIndex(-1)

        for item in item_list:
             # Convert list to tuple to match cache format roughly
             # item: [id, name, stock, reorder, vendor]
             self.add_row_to_create_table(tuple(item))

        self.tabs.setCurrentIndex(0) # Switch to this tab
        return True


    def export_po_excel(self):
        rows = []
        for r in range(self.table_create.rowCount()):
            part_id = self.table_create.item(r, 0).text()
            part_name = self.table_create.item(r, 1).text()
            qty = self.table_create.item(r, 3).text()
            price = self.table_create.item(r, 4).text()   # Bug fix: was reading from col 6
            hsn = self.table_create.item(r, 5).text()     # Bug fix: was reading from col 4
            gst = self.table_create.item(r, 6).text()     # Bug fix: was reading from col 5
            total = self.table_create.item(r, 7).text()
            rows.append({
                "Part ID": part_id, "Part Name": part_name, 
                "Qty Required": qty, "Buy Price": price,
                "HSN Code": hsn, "GST %": gst, "Total": total
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
            box.setStyleSheet("background-color: #1e1e2d; color: white; font-size: 14px;")
            box.exec()
            
            if box.clickedButton() == btn_no:
                return
            else:
                self.in_supplier.addItem(supplier)

        items = []
        total_amount = 0.0
        
        for r in range(rc):
            pid = self.table_create.item(r, 0).text()
            pname = self.table_create.item(r, 1).text()
            # Handle empty values gracefully
            try: qty = int(self.table_create.item(r, 3).text() or "0")
            except: qty = 0
            try: price = float(self.table_create.item(r, 4).text() or "0")
            except: price = 0.0
            
            hsn = self.table_create.item(r, 5).text()
            
            try: gst = float(self.table_create.item(r, 6).text() or "0")
            except: gst = 0.0
            
            if qty > 0:
                items.append({
                    "part_id": pid,
                    "part_name": pname,
                    "qty_ordered": qty,
                    "price": price,
                    "hsn_code": hsn,
                    "gst_rate": gst
                })
                # Tax logic calculation for PO Total Amount
                row_total = qty * price
                total_amount += row_total
        
        if not items:
            ProMessageBox.warning(self, "Validation", "No valid items with quantity > 0 to save.")
            return
        
        success, msg = self.db_manager.create_purchase_order(supplier, items, total_amount)
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
        btn_refresh.setFixedSize(120, 40)
        btn_refresh.setStyleSheet(ui_theme.get_primary_button_style())
        btn_refresh.clicked.connect(self.refresh_receive_tab)
        hl.addWidget(btn_refresh)
        
        btn_force_close = QPushButton("✅ FORCE CLOSE SELECTED")
        btn_force_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_force_close.setFixedSize(200, 40)
        btn_force_close.setStyleSheet(STYLE_BUTTON_PRIMARY)
        btn_force_close.clicked.connect(lambda: self.force_close_selected_pos(self.table_receive, self.refresh_receive_tab))
        hl.addWidget(btn_force_close)
        
        btn_bulk_receive = QPushButton("📦 RECEIVE SELECTED")
        btn_bulk_receive.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_bulk_receive.setFixedSize(160, 40)
        btn_bulk_receive.setStyleSheet(STYLE_BUTTON_SUCCESS)
        btn_bulk_receive.clicked.connect(self.bulk_receive_selected_items)
        hl.addWidget(btn_bulk_receive)

        btn_select_all_rx = QPushButton("☑ SELECT ALL")
        btn_select_all_rx.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_select_all_rx.setFixedSize(140, 40)
        btn_select_all_rx.setStyleSheet(ui_theme.get_primary_button_style())
        btn_select_all_rx.clicked.connect(self.toggle_select_all_receive)
        hl.addWidget(btn_select_all_rx)

        l.addLayout(hl)

        # Table
        self.table_receive = QTableWidget()
        cols = ["Select", "Part ID", "PO ID", "Supplier", "Part Name", "Ordered", "Received", "Pending", "ACTION"]
        self.table_receive.setColumnCount(len(cols))
        self.table_receive.setHorizontalHeaderLabels(cols)
        self.table_receive.setStyleSheet(ui_theme.get_table_style())
        self.table_receive.verticalHeader().setVisible(False)
        self.table_receive.setAlternatingRowColors(False)

        # Column Layout
        header = self.table_receive.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch) # Part Name

        self.table_receive.setColumnWidth(0, 70) # Select
        self.table_receive.setColumnWidth(1, 100) # Part ID
        self.table_receive.setColumnWidth(2, 100) # PO ID
        self.table_receive.setColumnWidth(3, 150) # Supplier
        self.table_receive.setColumnWidth(5, 80)  # Ordered
        self.table_receive.setColumnWidth(6, 80)  # Received
        self.table_receive.setColumnWidth(7, 80)  # Pending
        self.table_receive.setColumnWidth(8, 100)  # Action

        l.addWidget(self.table_receive)

        self.rx_data = [] # Cache

    def toggle_select_all_receive(self):
        """Toggle all checkboxes in the Receiving table."""
        all_checked = True
        for r in range(self.table_receive.rowCount()):
            chk = self.table_receive.cellWidget(r, 0)
            if chk and isinstance(chk, QCheckBox) and not chk.isChecked():
                all_checked = False
                break
        
        new_state = not all_checked
        for r in range(self.table_receive.rowCount()):
            chk = self.table_receive.cellWidget(r, 0)
            if chk and isinstance(chk, QCheckBox):
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

            # Checkbox
            chk = QCheckBox()
            chk.setStyleSheet("margin-left: 10px;")
            self.table_receive.setCellWidget(r, 0, chk)

            # 1: Part ID (from row[7])
            self.table_receive.setItem(r, 1, QTableWidgetItem(str(row[7])))

            # 2: PO ID
            self.table_receive.setItem(r, 2, QTableWidgetItem(str(row[1])))

            # 3: Supplier
            self.table_receive.setItem(r, 3, QTableWidgetItem(str(row[2])))

            # 4: Part Name
            self.table_receive.setItem(r, 4, QTableWidgetItem(str(row[3])))

            # 5: Ordered
            self.table_receive.setItem(r, 5, QTableWidgetItem(str(row[4])))

            # 6: Received
            self.table_receive.setItem(r, 6, QTableWidgetItem(str(row[5])))

            # 7: Pending
            self.table_receive.setItem(r, 7, QTableWidgetItem(str(row[6])))

            # 8: Action Button
            btn = QPushButton("RECEIVE")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(STYLE_BUTTON_SUCCESS)
            btn.clicked.connect(lambda _, x=row: self.open_receive_dialog(x))
            self.table_receive.setCellWidget(r, 8, btn)

    def open_receive_dialog(self, item_data):
        dlg = ReceiveItemDialog(self, item_data)
        if dlg.exec():
            qty, price = dlg.get_data()
            if qty is not None and price is not None:
                success, msg = self.db_manager.receive_po_item(item_data[0], qty, price, item_data[7])
                if success:
                    ProMessageBox.information(self, "Success", "Stock updated successfully in Database!")
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
        # Gather all checked items mapping back to rx_data
        for r in range(self.table_receive.rowCount()):
            chk = self.table_receive.cellWidget(r, 0)
            if chk and chk.isChecked():
                part_id = self.table_receive.item(r, 1).text()
                po_id = self.table_receive.item(r, 2).text()
                
                for row_data in self.rx_data:
                    # row: (id, po_id, supplier, part_name, qty_ordered, qty_received, pending, part_id)
                    if str(row_data[1]) == po_id and str(row_data[7]) == part_id:
                        items_to_receive.append(row_data)
                        break

        if not items_to_receive:
            ProMessageBox.warning(self, "Selection", "Please select at least one item to receive.")
            return

        success_count = 0
        for item_data in items_to_receive:
            dlg = ReceiveItemDialog(self, item_data)
            if dlg.exec():
                qty, price = dlg.get_data()
                if qty is not None and price is not None:
                    success, msg = self.db_manager.receive_po_item(item_data[0], qty, price, item_data[7])
                    if success:
                        success_count += 1
                else:
                    ProMessageBox.warning(self, "Error", f"Invalid input for {item_data[3]}. Skipped.")
            else:
                # User cancelled this item, continue to next
                continue
                
        if success_count > 0:
            ProMessageBox.information(self, "Bulk Receive", f"Successfully received {success_count} item(s).")
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
        btn_force_close.setFixedSize(200, 40)
        btn_force_close.setStyleSheet(STYLE_BUTTON_PRIMARY)
        btn_force_close.clicked.connect(lambda: self.force_close_selected_pos(self.table_backlog, self.refresh_backlog_tab))
        
        btn_export_backlog = QPushButton("📥 EXPORT PDF")
        btn_export_backlog.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_export_backlog.setFixedSize(140, 40)
        btn_export_backlog.setStyleSheet("background-color: rgba(255, 68, 68, 0.1); color: #ff4444; border: 1px solid #ff4444; border-radius: 6px; font-weight: bold;")
        btn_export_backlog.clicked.connect(self.export_backlog_pdf)
        
        btn_select_all_bl = QPushButton("☑ SELECT ALL")
        btn_select_all_bl.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_select_all_bl.setFixedSize(140, 40)
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
            chk = self.table_backlog.cellWidget(r, 0)
            if chk and isinstance(chk, QCheckBox) and not chk.isChecked():
                all_checked = False
                break
        
        new_state = not all_checked
        for r in range(self.table_backlog.rowCount()):
            chk = self.table_backlog.cellWidget(r, 0)
            if chk and isinstance(chk, QCheckBox):
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

            # Checkbox
            chk = QCheckBox()
            chk.setStyleSheet("margin-left: 10px;")
            self.table_backlog.setCellWidget(r, 0, chk)

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
        for r in range(table.rowCount()):
            chk = table.cellWidget(r, 0)
            if chk and chk.isChecked():
                # In both receive and backlog tabs, PO ID is at different column index!
                if table == self.table_receive:
                    po_ids.add(table.item(r, 2).text())
                elif table == self.table_backlog:
                    po_ids.add(table.item(r, 3).text())
                    
        if not po_ids:
            ProMessageBox.warning(self, "No Selection", "Please select at least one item to force close.")
            return
            
        box = QMessageBox(self)
        box.setWindowTitle("Force Close Selected")
        box.setText(f"Are you sure you want to force close {len(po_ids)} PO(s)?\nThey will be marked as 'COMPLETED'.")
        box.setIcon(QMessageBox.Icon.Warning)
        btn_yes = box.addButton("Yes, Force Close", QMessageBox.ButtonRole.AcceptRole)
        btn_no = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.setStyleSheet("background-color: #1e1e2d; color: white; font-size: 14px;")
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
             ProMessageBox.information(self, "Success", f"Backlog Report generated successfully at:\n{path}")
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
        splitter.setHandleWidth(2)
        splitter.setStyleSheet(f"QSplitter::handle {{ background-color: {COLOR_ACCENT_CYAN}; }}")

        # Left Panel (Master): PO List
        left_widget = QWidget()
        ll = QVBoxLayout(left_widget)
        ll.setContentsMargins(0, 0, 5, 0)
        ll.addWidget(QLabel("PURCHASE ORDERS"))

        # --- Date Filter ---
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)

        self.date_start = QDateEdit()
        self.date_start.setCalendarPopup(True)
        self.date_start.setDisplayFormat("yyyy-MM-dd")
        self.date_start.setDate(QDate.currentDate().addDays(-30)) # Default last 30 days
        self.date_start.setStyleSheet(ui_theme.get_lineedit_style())
        self.date_start.setFixedWidth(110)
        self.date_start.setFixedHeight(40)

        self.date_end = QDateEdit()
        self.date_end.setCalendarPopup(True)
        self.date_end.setDisplayFormat("yyyy-MM-dd")
        self.date_end.setDate(QDate.currentDate())
        self.date_end.setStyleSheet(ui_theme.get_lineedit_style())
        self.date_end.setFixedWidth(110)
        self.date_end.setFixedHeight(40)

        btn_filter = QPushButton("SEARCH")
        btn_filter.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_filter.setFixedSize(100, 40)
        btn_filter.setStyleSheet(ui_theme.get_primary_button_style())
        btn_filter.clicked.connect(self.refresh_history_tab)

        filter_layout.addWidget(QLabel("From:"))
        filter_layout.addWidget(self.date_start)
        filter_layout.addWidget(QLabel("To:"))
        filter_layout.addWidget(self.date_end)
        filter_layout.addWidget(btn_filter)
        filter_layout.addStretch()

        ll.addLayout(filter_layout)
        # -------------------

        self.table_history_master = QTableWidget()
        self.table_history_master.setColumnCount(5)
        self.table_history_master.setHorizontalHeaderLabels(["Select", "PO ID", "Supplier", "Date", "Status"])
        self.table_history_master.setStyleSheet(ui_theme.get_table_style())
        self.table_history_master.verticalHeader().setVisible(False)
        self.table_history_master.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_history_master.itemClicked.connect(self.show_po_details)
        self.table_history_master.horizontalHeader().setStretchLastSection(False)
        self.table_history_master.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch) # Supplier Stretches
        self.table_history_master.setColumnWidth(0, 65)  # Select
        self.table_history_master.setColumnWidth(1, 80)  # PO ID
        self.table_history_master.setColumnWidth(3, 100) # Date
        self.table_history_master.setColumnWidth(4, 100) # Status

        ll.addWidget(self.table_history_master)

        # Right Panel (Detail): PO Items
        right_widget = QWidget()
        rl = QVBoxLayout(right_widget)
        rl.setContentsMargins(5, 0, 0, 0)
        rl.addWidget(QLabel("ORDER DETAILS"))

        self.table_history_detail = QTableWidget()
        cols = ["Part ID", "Name", "Ordered", "Received", "Pending", "Unit Cost", "HSN Code", "GST %", "Total Cost"]
        self.table_history_detail.setColumnCount(len(cols))
        self.table_history_detail.setHorizontalHeaderLabels(cols)
        self.table_history_detail.setStyleSheet(ui_theme.get_table_style())
        self.table_history_detail.verticalHeader().setVisible(False)
        self.table_history_detail.horizontalHeader().setStretchLastSection(False)
        self.table_history_detail.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch) # Name Stretches
        self.table_history_detail.setColumnWidth(0, 80) # Part ID
        self.table_history_detail.setColumnWidth(2, 80)  # Ordered
        self.table_history_detail.setColumnWidth(3, 80)  # Received
        self.table_history_detail.setColumnWidth(4, 80)  # Pending
        self.table_history_detail.setColumnWidth(5, 90)  # Unit Cost
        self.table_history_detail.setColumnWidth(6, 90)  # HSN Code
        self.table_history_detail.setColumnWidth(7, 70)  # GST %
        self.table_history_detail.setColumnWidth(8, 100) # Total Cost

        rl.addWidget(self.table_history_detail)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([450, 550]) # Initial ratio
        l.addWidget(splitter)


        # Bottom Buttons
        btn_layout = QHBoxLayout()

        btn_select_all = QPushButton("☑ SELECT ALL")
        btn_select_all.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_select_all.setFixedSize(130, 40)
        btn_select_all.setStyleSheet(ui_theme.get_primary_button_style())
        btn_select_all.clicked.connect(self.toggle_select_all_history)

        btn_refresh = QPushButton("🔄 REFRESH HISTORY")
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.setFixedSize(160, 40)
        btn_refresh.setStyleSheet(ui_theme.get_primary_button_style())
        btn_refresh.clicked.connect(self.refresh_history_tab)

        btn_delete_selected = QPushButton("❌ DELETE PO")
        btn_delete_selected.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_delete_selected.setFixedSize(140, 40)
        btn_delete_selected.setStyleSheet(STYLE_DANGER_BUTTON)
        btn_delete_selected.clicked.connect(self.delete_selected_po)
        
        btn_export_history = QPushButton("📥 EXPORT PDF")
        btn_export_history.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_export_history.setFixedSize(140, 40)
        btn_export_history.setStyleSheet("background-color: rgba(255, 68, 68, 0.1); color: #ff4444; border: 1px solid #ff4444; border-radius: 6px; font-weight: bold;")
        btn_export_history.clicked.connect(self.export_selected_po_pdf)

        btn_layout.addWidget(btn_select_all)
        btn_layout.addWidget(btn_refresh)
        btn_layout.addWidget(btn_delete_selected)
        btn_layout.addWidget(btn_export_history)
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

    def populate_history_master(self, rows):
        self.table_history_master.setUpdatesEnabled(False)
        self.table_history_master.blockSignals(True)
        self.table_history_master.setSortingEnabled(False)
        
        self.table_history_master.setColumnCount(5) 
        self.table_history_master.setHorizontalHeaderLabels(["Select", "PO ID", "Supplier", "Date", "Status"])
        self.table_history_master.setRowCount(0)
        self.table_history_master.setRowCount(len(rows))
        for r, row in enumerate(rows):
            # Checkbox
            chk = QCheckBox()
            chk.setStyleSheet("margin-left: 15px;")
            self.table_history_master.setCellWidget(r, 0, chk)
            # row: po_id, supplier, date, status, item_count, total_qty
            self.table_history_master.setItem(r, 1, QTableWidgetItem(str(row[0])))
            self.table_history_master.setItem(r, 2, QTableWidgetItem(str(row[1])))
            self.table_history_master.setItem(r, 3, QTableWidgetItem(str(row[2])))
            self.table_history_master.setItem(r, 4, QTableWidgetItem(str(row[3])))
        
        self.table_history_master.setSortingEnabled(True)
        self.table_history_master.blockSignals(False)
        self.table_history_master.setUpdatesEnabled(True)

    def toggle_select_all_history(self):
        """Toggle all checkboxes in the Order History table."""
        # Determine current state: if all are checked, uncheck all; otherwise check all
        all_checked = True
        for r in range(self.table_history_master.rowCount()):
            chk = self.table_history_master.cellWidget(r, 0)
            if chk and not chk.isChecked():
                all_checked = False
                break
        
        new_state = not all_checked
        for r in range(self.table_history_master.rowCount()):
            chk = self.table_history_master.cellWidget(r, 0)
            if chk:
                chk.setChecked(new_state)

    def delete_selected_po(self):
        # Get checked rows
        checked_rows = []
        for r in range(self.table_history_master.rowCount()):
            chk = self.table_history_master.cellWidget(r, 0)
            if chk and chk.isChecked():
                checked_rows.append(r)
        
        if not checked_rows:
            # Fallback to highlighted row
            row = self.table_history_master.currentRow()
            if row < 0:
                ProMessageBox.warning(self, "Selection", "Please select a Purchase Order to delete.")
                return
            checked_rows = [row]
        
        po_ids = [self.table_history_master.item(r, 1).text() for r in checked_rows]
        
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
            chk = self.table_history_master.cellWidget(r, 0)
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
            po_id = self.table_history_master.item(row, 1).text()
            supplier = self.table_history_master.item(row, 2).text()
            po_date = self.table_history_master.item(row, 3).text()
            status = self.table_history_master.item(row, 4).text()

            po_header = {
                "PO Number": po_id,
                "To": supplier,
                "Date": po_date,
                "Status": status
            }

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
            ProMessageBox.information(self, "Success", f"Generated PDF with {len(po_data_list)} PO(s) successfully!")
            try: os.startfile(path)
            except: pass
        else:
            ProMessageBox.critical(self, "Error", f"Failed to generate PDF: {path}")

    def show_po_details(self, item):
        row = item.row()
        po_id_item = self.table_history_master.item(row, 1)
        if not po_id_item: return
        po_id = po_id_item.text()
        
        items = self.db_manager.get_po_items(po_id)
        self.table_history_detail.setRowCount(0)
        self.table_history_detail.setRowCount(len(items))
        
        for r, i in enumerate(items):
            # i: id, part_id, part_name, qty_ordered, qty_received, ordered_price, hsn_code, gst_rate
            self.table_history_detail.setItem(r, 0, QTableWidgetItem(str(i[1]))) # part_id
            self.table_history_detail.setItem(r, 1, QTableWidgetItem(str(i[2]))) # part_name
            self.table_history_detail.setItem(r, 2, QTableWidgetItem(str(i[3]))) # qty_ordered
            self.table_history_detail.setItem(r, 3, QTableWidgetItem(str(i[4]))) # qty_received
            
            pending = max(0, i[3] - i[4])
            self.table_history_detail.setItem(r, 4, QTableWidgetItem(str(pending))) # pending
            
            # Unit Cost (Ordered Price)
            cost = i[5] if len(i) > 5 and i[5] is not None else 0.0
            self.table_history_detail.setItem(r, 5, QTableWidgetItem(f"{cost:.2f}"))
            
            # HSN
            hsn = i[6] if len(i) > 6 and i[6] else '8714'
            self.table_history_detail.setItem(r, 6, QTableWidgetItem(str(hsn)))
            
            # GST
            gst = i[7] if len(i) > 7 and i[7] else 18.0
            self.table_history_detail.setItem(r, 7, QTableWidgetItem(str(gst)))
            
            # Total Cost (Ordered Qty * MRP)
            total = i[3] * cost
            self.table_history_detail.setItem(r, 8, QTableWidgetItem(f"{total:.2f}"))

    # --- TAB 5: VENDOR REGISTRY ---
    def setup_vendors_tab(self):
        l = QVBoxLayout(self.tab_vendors)
        l.setContentsMargins(DIM_MARGIN_STD, DIM_MARGIN_STD, DIM_MARGIN_STD, DIM_MARGIN_STD)
        
        self.vendor_manager_widget = VendorManagerWidget(self.db_manager)
        l.addWidget(self.vendor_manager_widget)
