from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QFrame, 
                             QDialog, QFormLayout, QDialogButtonBox, QAbstractItemView, QFileDialog, QProgressBar, QCheckBox, QComboBox, QStyledItemDelegate, QStyle, QInputDialog)
import pandas as pd
import openpyxl
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QRect, QPointF, QSize, QEvent
from PyQt6.QtGui import QColor, QBrush, QPainter, QPen, QFont, QLinearGradient, QFontMetrics
from styles import (COLOR_SURFACE, COLOR_ACCENT_CYAN, COLOR_ACCENT_GREEN, COLOR_ACCENT_YELLOW, COLOR_TEXT_PRIMARY, COLOR_ACCENT_RED,
                   STYLE_NEON_BUTTON, STYLE_INPUT_CYBER, STYLE_TABLE_CYBER, STYLE_GLASS_PANEL, STYLE_ACTION_HOLO,
                   DIM_BUTTON_HEIGHT, DIM_INPUT_HEIGHT, DIM_MARGIN_STD, DIM_SPACING_STD, DIM_ICON_SIZE)
from custom_components import ProMessageBox, ProDialog, ReactorStatCard, AINexusNode
from vendor_manager import VendorManagerDialog
from logger import app_logger
import os
from datetime import datetime

class BladeDelegate(QStyledItemDelegate):
    """
    Cyber-Blade Cell Delegate.
    Optimized for performance: Paints Checkboxes, Progress Bars, and Buttons directly.
    """
    # Signals for actions
    editClicked = pyqtSignal(int)   # Row index
    deleteClicked = pyqtSignal(int) # Row index
    infoClicked = pyqtSignal(int)   # Row index
    selectToggled = pyqtSignal(int, bool) # Row index, New State

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pulse_frame = 0 # 0-20
        self.pulse_increasing = True
        
        # Cache standard sizes/colors
        self.chk_size = 18
        self.btn_width = 50
        self.btn_height = 22
        self.btn_spacing = 4
        
    def sizeHint(self, option, index):
        """Ensure cell size fits tags and content"""
        # Base Size
        base_size = super().sizeHint(option, index)
        
        # Get data
        data = index.data(Qt.ItemDataRole.UserRole)
        if not data or not isinstance(data, dict): return base_size
            
        # Extract vehicle tags logic (keep existing logic for name column)
        col_type = data.get('type', 'generic')
        
        if col_type == 'name':
            vehicle_tags = data.get('vehicle_tags', [])
            is_new = data.get('is_new', False)
            text = str(index.data(Qt.ItemDataRole.DisplayRole))
            
            font = QFont(option.font)
            font.setPointSize(9)
            fm = QFontMetrics(font)
            w = fm.horizontalAdvance(text) + 20 
            
            if vehicle_tags:
                 badge_font = QFont(option.font)
                 badge_font.setPointSize(7)
                 badge_font.setBold(True)
                 bfm = QFontMetrics(badge_font)
                 for tag in vehicle_tags:
                     tag_w = bfm.horizontalAdvance(tag) + 12 
                     w += (tag_w + 5)
            if is_new: w += 25
            if data.get('is_edited', False): w += 40
            return QSize(int(w + 20), max(base_size.height(), 40))
            
        return QSize(base_size.width(), max(base_size.height(), 40))

    def paint(self, painter, option, index):
        if not index.isValid(): return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Get data
        data = index.data(Qt.ItemDataRole.UserRole)
        # If no custom data or not a dict (catalog cells store int), draw default
        if not data or not isinstance(data, dict):
            QStyledItemDelegate.paint(self, painter, option, index)
            painter.restore()
            return

        text = index.data(Qt.ItemDataRole.DisplayRole)
        col_type = data.get('type', 'generic')
        
        rect = QRect(option.rect)
        rect.adjust(1, 1, -1, -1) # 1px gap
        
        # HOVER STATE CHECK
        is_hover = (option.state & QStyle.StateFlag.State_MouseOver)
        
        # --- BACKGROUND ---
        fill_color = QColor(255, 255, 255, 5) # Default generic
        border_color = QColor(0, 0, 0, 0)
        text_color = QColor(COLOR_TEXT_PRIMARY)
        side_border_color = QColor(0, 0, 0, 0)
        
        is_low_stock = data.get('is_low_stock', False)
        
        # Color Logic
        if col_type == 'id':
            if is_low_stock:
                fill_color = QColor(255, 0, 0, 40)
                side_border_color = QColor(255, 0, 0, 200)
                text_color = QColor(255, 100, 100)
            else:
                fill_color = QColor(0, 68, 255, 40)
                side_border_color = QColor(0, 242, 255)
                text_color = QColor(0, 242, 255)
        
        elif col_type == 'name':
            if is_low_stock:
                fill_color = QColor(255, 0, 0, 30)
                side_border_color = QColor(255, 0, 0, 150)
                text_color = QColor(255, 150, 150)
            else:
                fill_color = QColor(0, 255, 208, 20)
                side_border_color = QColor(0, 255, 208, 100)
                text_color = QColor(255, 255, 255)

        elif col_type == 'price':
            fill_color = QColor(255, 170, 0, 20)
            side_border_color = QColor(255, 170, 0)
            text_color = QColor(255, 215, 0)

        elif col_type == 'stock':
            # Background handled by Progress Bar logic below, but set base here
            pass

        elif option.state & QStyle.StateFlag.State_Selected:
             fill_color = QColor(0, 229, 255, 120)
             text_color = QColor(255, 255, 255)
        elif is_hover:
             fill_color = fill_color.lighter(150)
        
        # Draw Background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill_color)
        painter.drawRect(rect)
        
        # Draw Side Borders
        if side_border_color.alpha() > 0:
            painter.setBrush(side_border_color)
            painter.drawRect(rect.left(), rect.top(), 3, rect.height())

        # --- CONTENT DRAWING ---
        
        # 1. CHECKBOX (Col 0)
        if col_type == 'select':
            checked = data.get('checked', False)
            chk_rect = QRect(rect.center().x() - 9, rect.center().y() - 9, 18, 18)
            
            painter.setPen(QPen(QColor(COLOR_ACCENT_CYAN), 1))
            if checked:
                painter.setBrush(QColor(COLOR_ACCENT_CYAN))
                painter.drawRect(chk_rect)
                # Checkmark
                painter.setPen(QPen(Qt.GlobalColor.black, 2))
                painter.drawLine(chk_rect.left()+3, chk_rect.center().y(), chk_rect.center().x(), chk_rect.bottom()-3)
                painter.drawLine(chk_rect.center().x(), chk_rect.bottom()-3, chk_rect.right()-3, chk_rect.top()+3)
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(chk_rect)
                
        # 2. PROGRESS BAR (Col Stock)
        elif col_type == 'stock':
            val = int(data.get('val', 0))
            max_val = int(data.get('max_val', 100))
            ratio = min(1.0, val / max(1, max_val))
            
            # Pulse Low Stock
            bar_color = QColor(0, 255, 0)
            if val <= 5: # Critical
                pulse_alpha = int(100 + (155 * (self.pulse_frame / 20.0)))
                bar_color = QColor(255, 0, 0, pulse_alpha)
            
            # Draw Bar Background
            bar_rect = QRect(rect.left() + 5, rect.top() + 8, rect.width() - 10, rect.height() - 16)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(30, 30, 30))
            painter.drawRect(bar_rect)
            
            # Draw Progress
            prog_w = int(bar_rect.width() * ratio)
            if prog_w > 0:
                painter.setBrush(bar_color)
                painter.drawRect(bar_rect.left(), bar_rect.top(), prog_w, bar_rect.height())
                
            # Draw Text
            painter.setPen(Qt.GlobalColor.black)
            font_qty = painter.font()
            font_qty.setBold(True)
            painter.setFont(font_qty)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(val))

        # 3. ACTION BUTTONS (Col Actions)
        elif col_type == 'actions':
            # Data should provide which actions to show
            actions = data.get('actions', ['info']) # default minimal
            
            # Simple layout: spaced
            total_w = (len(actions) * self.btn_width) + ((len(actions)-1) * self.btn_spacing)
            start_x = rect.center().x() - (total_w // 2)
            y = rect.center().y() - (self.btn_height // 2)
            
            curr_x = start_x
            for act in actions:
                color = "#ffe600" # default info
                if act == 'edit': color = "#00e5ff"
                elif act == 'delete': color = "#ff4444"
                
                btn_r = QRect(curr_x, y, self.btn_width, self.btn_height)
                self._draw_btn(painter, btn_r, act.upper(), color, is_hover)
                curr_x += self.btn_width + self.btn_spacing

        # 4. TEXT CONTENT (ID, Name, Price, etc.)
        else:
            painter.setPen(text_color)
            font = option.font
            font.setPointSize(9)
            if col_type in ['id', 'price']: font.setBold(True)
            painter.setFont(font)
            
            # Vehicle Tags logic for Name column
            vehicle_tags = data.get('vehicle_tags', [])
            is_new = data.get('is_new', False)
            is_edited = data.get('is_edited', False)
            if col_type == 'name':
                self._draw_name_with_tags_extended(painter, rect, text, vehicle_tags, is_new, is_edited)
            elif col_type == 'description':
                # Parse comma separated tags
                tags = [t.strip() for t in text.split(',') if t.strip()]
                if tags:
                     self._draw_tags_only(painter, rect, tags)
                else:
                     painter.drawText(rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
            else:
                 align = Qt.AlignmentFlag.AlignCenter
                 if col_type in ['name', 'vendor', 'description']: 
                     align = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
                 elif col_type == 'price':
                     align = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
                 
                 draw_rect = QRect(rect)
                 # Add padding for text
                 if col_type in ['name', 'vendor', 'description']: 
                     draw_rect.adjust(5, 0, 0, 0)
                 elif col_type == 'price':
                     draw_rect.adjust(0, 0, -5, 0)
                     
                 # VENDOR GLOW LOGIC
                 if col_type == 'vendor' and text:
                     v_color = self._get_vendor_color(text)
                     
                     # 1. Glow Background
                     painter.setPen(Qt.PenStyle.NoPen)
                     painter.setBrush(QColor(v_color.red(), v_color.green(), v_color.blue(), 25))
                     # Smaller pill shape for the tag
                     # Measure text width to make the pill fit? Or just fill cell? 
                     # User said "every vender name have glowing color coding", usually implies a tag look.
                     # Let's make it a pill around the text.
                     fm = painter.fontMetrics()
                     t_w = fm.horizontalAdvance(text)
                     pill_rect = QRect(draw_rect.left(), draw_rect.center().y() - 10, t_w + 10, 20)
                     painter.drawRoundedRect(pill_rect, 4, 4)
                     
                     # 2. Text Color
                     painter.setPen(v_color)
                     
                 painter.drawText(draw_rect, align, text)

        painter.restore()

    def _get_vendor_color(self, name):
        if not name: return QColor(200, 200, 200)
        h = sum(ord(c) for c in name) * 33
        hue = h % 360
        # Neon: High Sat (200-255), High Lightness (180-220)
        return QColor.fromHsl(hue, 230, 180)

    def _draw_btn(self, painter, rect, text, color_hex, parent_hover):
        # Specific hover check would require mouse tracking, 
        # for now we just draw the button style.
        # Ideally we check if mouse is inside THIS rect.
        # But QStyledItemDelegate paint doesn't give mouse pos easily without option.
        
        c = QColor(color_hex)
        painter.setPen(c)
        painter.setBrush(QColor(c.red(), c.green(), c.blue(), 20)) # Tint
        painter.drawRoundedRect(rect, 3, 3)
        
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

    def _draw_tags_only(self, painter, rect, tags):
        """Draws a list of tags in the given rect, wrapping if needed (simple flow)"""
        x = rect.left() + 5
        y = rect.top() + 4
        
        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        fm = painter.fontMetrics()
        
        for tag in tags:
            w = fm.horizontalAdvance(tag) + 10
            h = 16
            
            # Check bounds (simple clip)
            if x + w > rect.right(): 
                break # Clip for now, or wrap? Row height is fixed, so clip.
                
            # Draw Tag logic
            tag_rect = QRect(x, y, w, h)
            
            # Hash color from tag text for variety
            h_val = sum(ord(c) for c in tag)
            hue = (h_val * 50) % 255
            tag_color = QColor.fromHsl(hue, 200, 100, 200) # Pastels
            
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(tag_color.red(), tag_color.green(), tag_color.blue(), 40))
            painter.drawRoundedRect(tag_rect, 4, 4)
            
            painter.setPen(tag_color)
            painter.drawText(tag_rect, Qt.AlignmentFlag.AlignCenter, tag)
            
            x += w + 4

    def _draw_name_with_tags_extended(self, painter, rect, text, tags, is_new, is_edited):
        fm = painter.fontMetrics()
        text_w = fm.horizontalAdvance(text)
        start_x = rect.left() + 10
        
        # Draw Name
        name_r = QRect(start_x, rect.y(), text_w, rect.height())
        painter.drawText(name_r, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
        
        current_x = start_x + text_w + 10
        
        # Draw NEW Badge
        if is_new:
            badge_w = 35
            br = QRect(current_x, rect.y() + (rect.height()-16)//2, badge_w, 16)
            
            # Glowing Green
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 255, 0, 50))
            painter.drawRoundedRect(br, 4, 4)
            
            painter.setPen(QColor(0, 255, 0))
            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            painter.drawText(br, Qt.AlignmentFlag.AlignCenter, "NEW")
            
            current_x += badge_w + 5
            
        # Draw EDITED Badge
        if is_edited:
            badge_w = 45
            br = QRect(current_x, rect.y() + (rect.height()-16)//2, badge_w, 16)
            
            # Glowing Cyan
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 229, 255, 50))
            painter.drawRoundedRect(br, 4, 4)
            
            painter.setPen(QColor(0, 229, 255))
            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            painter.drawText(br, Qt.AlignmentFlag.AlignCenter, "EDITED")
            
            current_x += badge_w + 5
        
        badge_font = QFont(painter.font())
        badge_font.setPointSize(7)
        badge_font.setBold(True)
        painter.setFont(badge_font)
        badge_fm = painter.fontMetrics()
        
        for tag in tags:
            bw = badge_fm.horizontalAdvance(tag) + 12
            # Simple Color Hash
            kc = QColor(COLOR_ACCENT_CYAN)
            if "HONDA" in tag: kc = QColor("#ff9900")
            elif "TVS" in tag: kc = QColor("#00ff00")
            
            br = QRect(current_x, rect.y() + (rect.height()-16)//2, bw, 16)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(kc.red(), kc.green(), kc.blue(), 40))
            painter.drawRect(br)
            
            painter.setPen(kc)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(br)
            painter.drawText(br, Qt.AlignmentFlag.AlignCenter, tag)
            current_x += bw + 5

    def editorEvent(self, event, model, option, index):
        """Handle mouse clicks for interactive elements"""
        if event.type() == QEvent.Type.MouseButtonRelease:
            data = index.data(Qt.ItemDataRole.UserRole)
            if data is None:
                return super().editorEvent(event, model, option, index)
            col_type = data.get('type', 'generic')
            
            # CHECKBOX CLICK
            if col_type == 'select':
                current = data.get('checked', False)
                # Toggle
                # We need to update the model/view. 
                # Since we use QTableWidget, we can update item data directly?
                # Best practice: Emit signal to View or Update Model
                self.selectToggled.emit(index.row(), not current)
                return True
                
            # ACTION BUTTON CLICKS
            elif col_type == 'actions':
                actions = data.get('actions', ['info'])
                
                total_w = (len(actions) * self.btn_width) + ((len(actions)-1) * self.btn_spacing)
                start_x = option.rect.center().x() - (total_w // 2)
                y = option.rect.center().y() - (self.btn_height // 2)
                
                mx = event.pos().x()
                my = event.pos().y()
                
                if y <= my <= y + self.btn_height:
                    curr_x = start_x
                    for act in actions:
                        if curr_x <= mx <= curr_x + self.btn_width:
                            if act == 'edit': self.editClicked.emit(index.row())
                            elif act == 'delete': self.deleteClicked.emit(index.row())
                            elif act == 'info': self.infoClicked.emit(index.row())
                            return True
                        curr_x += self.btn_width + self.btn_spacing
                        
        return False


class DataLoadThread(QThread):
    data_loaded = pyqtSignal(list)
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
    def run(self):
        try:
            rows = self.db_manager.get_all_parts()
            self.data_loaded.emit(rows)
        except Exception as e:
            app_logger.error(f"Data load thread error: {e}")
            self.data_loaded.emit([])

class AddPartDialog(QDialog):
    def __init__(self, parent=None, part_data=None):
        super().__init__(parent)
        self.setWindowTitle("Add/Edit Part")
        self.setStyleSheet(f"background-color: #1a1a2e; color: {COLOR_TEXT_PRIMARY};")
        self.layout = QFormLayout(self)
        self.part_data = part_data

        self.in_id = QLineEdit()
        self.in_name = QLineEdit()
        self.in_desc = QLineEdit()
        self.in_price = QLineEdit()
        self.in_qty = QLineEdit()
        self.in_rack = QLineEdit()
        self.in_col = QLineEdit()
        self.in_reorder = QLineEdit("5")
        self.in_vendor = QLineEdit()

        for w in [self.in_id, self.in_name, self.in_desc, self.in_price, self.in_qty, self.in_rack, self.in_col, self.in_reorder, self.in_vendor]:
            w.setStyleSheet(STYLE_INPUT_CYBER)

        if part_data:
            self.in_id.setText(str(part_data[0]))
            self.in_id.setReadOnly(True) 
            self.in_name.setText(str(part_data[1]))
            self.in_desc.setText(str(part_data[2]))
            self.in_price.setText(str(part_data[3]))
            self.in_qty.setText(str(part_data[4]))
            self.in_rack.setText(str(part_data[5]))
            self.in_col.setText(str(part_data[6]))
            if len(part_data) > 7:
                 self.in_reorder.setText(str(part_data[7]))
                 self.in_vendor.setText(str(part_data[8]))

        self.layout.addRow("Part ID:", self.in_id)
        self.layout.addRow("Name:", self.in_name)
        self.layout.addRow("Description:", self.in_desc)
        self.layout.addRow("Price (MRP):", self.in_price)
        self.layout.addRow("Quantity:", self.in_qty)
        self.layout.addRow("Rack:", self.in_rack)
        self.layout.addRow("Column:", self.in_col)
        self.layout.addRow("Reorder Level:", self.in_reorder)
        self.layout.addRow("Vendor Name:", self.in_vendor)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setStyleSheet(STYLE_NEON_BUTTON)
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setStyleSheet("color: white; background: transparent;")
        
        self.layout.addRow(self.buttons)

    def get_data(self):
        return {
            'id': self.in_id.text(), 
            'name': self.in_name.text(), 
            'desc': self.in_desc.text(), 
            'price': float(self.in_price.text() or 0), 
            'qty': int(self.in_qty.text() or 0), 
            'rack': self.in_rack.text(), 
            'col': self.in_col.text(),
            'reorder': int(self.in_reorder.text() or 5), 
            'vendor': self.in_vendor.text()
        }

class PurchaseOrderDialog(QDialog):
    def __init__(self, parent=None, items=None):
        super().__init__(parent)
        self.setWindowTitle("Purchase Command Center")
        self.resize(1000, 700)
        self.setStyleSheet(f"background-color: #1a1a2e; color: {COLOR_TEXT_PRIMARY};")
        self.items = items or [] 
        self.selected_ids = set() # Track selected Part IDs
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        hud_layout = QHBoxLayout()
        stats_container = QFrame()
        stats_container.setStyleSheet(f"background-color: {COLOR_SURFACE}; border-radius: 12px; border: 1px solid #333;")
        stats_layout = QHBoxLayout(stats_container)
        stats_layout.setContentsMargins(20, 15, 20, 15)
        stats_layout.setSpacing(40)
        
        self.card_reorder = ReactorStatCard("LOW STOCK", "0", COLOR_ACCENT_RED, small=True)
        self.card_vendors = ReactorStatCard("ACTIVE VENDORS", "0", COLOR_ACCENT_GREEN, small=True)
        self.card_val = ReactorStatCard("TOTAL VALUE", "₹ 0", COLOR_ACCENT_YELLOW, small=True)
        
        stats_layout.addWidget(self.card_reorder)
        stats_layout.addWidget(self.card_vendors)
        stats_layout.addWidget(self.card_val)
        
        layout.addWidget(stats_container)

        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(10)
        
        self.btn_auto = QPushButton("🚀 AUTO-SELECT LOW STOCK")
        self.btn_auto.setStyleSheet(STYLE_NEON_BUTTON)
        self.btn_auto.setFixedSize(220, DIM_BUTTON_HEIGHT)
        self.btn_auto.clicked.connect(self.auto_select_low_stock)
        controls_layout.addWidget(self.btn_auto)
        
        self.input_search = QLineEdit()
        self.input_search.setPlaceholderText("🔍 Search Part / Vendor...")
        self.input_search.setStyleSheet(STYLE_INPUT_CYBER)
        self.input_search.textChanged.connect(self.filter_table)
        controls_layout.addWidget(self.input_search)
        
        controls_layout.addWidget(QLabel("Filter Vendor:"))
        self.combo_vendor = QComboBox()
        self.combo_vendor.addItem("All Vendors")
        self.combo_vendor.setStyleSheet(STYLE_INPUT_CYBER)
        self.combo_vendor.setFixedWidth(200)
        
        vendors = sorted(list(set([i[4] for i in self.items if i[4]])))
        self.combo_vendor.addItems(vendors)
        self.combo_vendor.currentTextChanged.connect(self.filter_table)
        controls_layout.addWidget(self.combo_vendor)
        
        layout.addLayout(controls_layout)
        
        self.table = QTableWidget()
        cols = ["Select", "Part ID", "Name", "Vendor", "Stock", "Reorder", "Cost", "Total", "Added On", "Last Ordered"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setStyleSheet(STYLE_TABLE_CYBER + "\nQTableWidget { background-color: #0b0b14; gridline-color: #1a1a2e; }")
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        
        btn_layout = QHBoxLayout()
        self.btn_generate = QPushButton("📥 GENERATE PURCHASE LIST")
        self.btn_generate.setStyleSheet(STYLE_NEON_BUTTON)
        self.btn_generate.setFixedSize(250, 40)
        self.btn_generate.clicked.connect(self.accept)
        
        self.btn_cancel = QPushButton("CANCEL")
        self.btn_cancel.setStyleSheet("color: #ff4444; border: 1px solid #ff4444; padding: 5px; border-radius: 4px; background: transparent;")
        self.btn_cancel.setFixedSize(100, 40)
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_generate)
        layout.addLayout(btn_layout)
        
        self.current_items = self.items
        self.rows_map = {}
        self.populate_table(self.items)
        self.update_dashboard()

    def populate_table(self, items_to_show):
        self.table.setRowCount(0)
        self.table.setRowCount(len(items_to_show))
        self.rows_map = {}
        
        for i, item in enumerate(items_to_show):
            self.rows_map[i] = item
            
            chk = QCheckBox()
            chk.setStyleSheet(f"QCheckBox::indicator:checked {{ background-color: {COLOR_ACCENT_CYAN}; border: 1px solid {COLOR_ACCENT_CYAN}; }}")
            # Use a closure/lambda to capture the row index 'i'
            # We need to make sure i is bound correctly
            chk.stateChanged.connect(lambda state, row=i: self.on_item_checked(row, state))
            
            cw = QWidget()
            cl = QHBoxLayout(cw); cl.setContentsMargins(0,0,0,0); cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(chk)
            self.table.setCellWidget(i, 0, cw)
            
            self.table.setItem(i, 1, QTableWidgetItem(str(item[0])))
            self.table.setItem(i, 2, QTableWidgetItem(str(item[1])))
            self.table.setItem(i, 3, QTableWidgetItem(str(item[4])))
            
            max_stock = max(int(item[3] or 5) * 2, 10) 
            pb = QProgressBar()
            pb.setRange(0, max_stock)
            pb.setValue(int(item[2] or 0)) 
            pb.setTextVisible(True)
            pb.setFormat(f"{int(item[2] or 0)}")
            pb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            color = "#ff4444" if (item[2] or 0) <= (item[3] or 5) else "#00ff00"
            pb.setStyleSheet(f"QProgressBar {{ background: #222; border: none; border-radius: 2px; }} QProgressBar::chunk {{ background: {color}; }}")
            self.table.setCellWidget(i, 4, pb)
            
            self.table.setItem(i, 5, QTableWidgetItem(str(item[3])))
            
            cost_item = QTableWidgetItem(f"{item[5]:.2f}")
            cost_item.setToolTip(f"Last Purchase Price: ₹ {item[5]}")
            self.table.setItem(i, 6, cost_item)
            
            total = (item[3] - item[2]) * item[5] 
            if total < 0: total = 0
            self.table.setItem(i, 7, QTableWidgetItem(f"{total:.2f}"))
            self.table.setItem(i, 8, QTableWidgetItem(str(item[6] if len(item)>6 else "")))
            self.table.setItem(i, 9, QTableWidgetItem(str(item[7] if len(item)>7 else "")))

        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch) # Description stretch

    def filter_table(self):
        vendor = self.combo_vendor.currentText()
        search = self.input_search.text().lower()
        
        filtered = []
        for item in self.items:
            v_match = (vendor == "All Vendors") or (item[4] == vendor)
            s_match = (search in str(item[1]).lower()) or (search in str(item[0]).lower()) or (search in str(item[4]).lower())
            
            if v_match and s_match:
                filtered.append(item)
                
        self.current_items = filtered
        self.populate_table(self.current_items)
        self.update_dashboard()

    def on_item_checked(self, row, state):
        itm = self.table.item(row, 0)
        if itm:
            data = itm.data(Qt.ItemDataRole.UserRole)
            data['checked'] = bool(state)
            itm.setData(Qt.ItemDataRole.UserRole, data)
            self.update_dashboard()

    def auto_select_low_stock(self):
        for i in range(self.table.rowCount()):
            item = self.rows_map[i]
            if item[2] <= item[3]: # q <= reorder
                 cw = self.table.cellWidget(i, 0)
                 if cw:
                     # Find checkbox in layout
                     chk = cw.findChild(QCheckBox)
                     if chk:
                         chk.setChecked(True)
        self.update_dashboard()

    def update_dashboard(self):
        selected_count = 0
        total_invest = 0
        vendors = set()
        
        for i in range(self.table.rowCount()):
             itm = self.table.item(i, 0)
             if itm:
                 data = itm.data(Qt.ItemDataRole.UserRole)
                 if data.get('checked', False):
                     item = self.rows_map[i]
                     selected_count += 1
                     qty_needed = max(0, item[3] - item[2])
                     total_invest += (qty_needed * item[5])
                     if item[4]: vendors.add(item[4])
                 
        if selected_count: self.card_reorder.set_value(str(selected_count))
        else: self.card_reorder.set_value("0")
        
        self.card_val.set_value(f"₹ {total_invest:,.0f}")
        self.card_vendors.set_value(str(len(vendors)))

    def get_selected_items(self):
        selected = []
        for i in range(self.table.rowCount()):
             itm = self.table.item(i, 0)
             if itm:
                 data = itm.data(Qt.ItemDataRole.UserRole)
                 if data.get('checked', False):
                     item = self.rows_map[i]
                     selected.append([item[0], item[1], item[2], item[3], item[4]])
        return selected
    


class InventoryPage(QWidget):
    def __init__(self, db_manager, user_role="ADMIN", username="admin"):
        super().__init__()
        try:
            app_logger.info("Initializing InventoryPage...")
            self.db_manager = db_manager
            self.user_role = user_role
            self.username = username
            
            # Persist selection across searches
            self.selected_part_ids = set()

            self.user_role = user_role 
            self.username = username
            
            # Fetch Permissions
            self.permissions = []
            if self.user_role == "STAFF":
                user_profile = self.db_manager.get_user_profile(self.username)
                if user_profile and user_profile.get("permissions"):
                    import json
                    try:
                        self.permissions = json.loads(user_profile["permissions"])
                    except:
                        self.permissions = []
            
            # Helper to check edit permission
            self.can_edit = (self.user_role == "ADMIN") or ("can_edit_inventory" in self.permissions)
            
            self.loader_thread = DataLoadThread(db_manager)
            self.loader_thread.data_loaded.connect(self.on_data_loaded)
            
            self.search_timer = QTimer()
            self.search_timer.setInterval(300)
            self.search_timer.setSingleShot(True)
            self.search_timer.timeout.connect(self.filter_table)
            
            self.all_rows = [] 
            
            self.setup_ui()
            self.load_data()
            app_logger.info("InventoryPage Initialized Successfully.")
        except Exception as e:
            app_logger.critical(f"Failed to initialize InventoryPage: {e}", exc_info=True)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(DIM_MARGIN_STD, DIM_MARGIN_STD, DIM_MARGIN_STD, DIM_MARGIN_STD)
        layout.setSpacing(DIM_SPACING_STD)
        
        # --- PRE-INIT COMPONENTS (Safety) ---
        self.card_val = ReactorStatCard("TOTAL VALUE", "₹ 0", COLOR_ACCENT_YELLOW, small=True)
        self.card_reorder = ReactorStatCard("LOW STOCK", "0", COLOR_ACCENT_RED, small=True)
        self.card_vendors = ReactorStatCard("ACTIVE VENDORS", "0", COLOR_ACCENT_GREEN, small=True)
        self.card_stock = ReactorStatCard("TOTAL STOCK", "0", COLOR_ACCENT_CYAN, small=True)
        self.card_parts = ReactorStatCard("TOTAL PARTS", "0", "#bc13fe", small=True)
        self.ai_nexus = AINexusNode()
        
        # --- ROW 1: Navigation & Actions ---
        top_row = QHBoxLayout()
        top_row.setSpacing(10)
        
        title = QLabel("📦 INVENTORY")
        title.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {COLOR_ACCENT_CYAN};")
        top_row.addWidget(title)
        
        self.loading_bar = QProgressBar()
        self.loading_bar.setFixedSize(80, 4)
        self.loading_bar.setTextVisible(False)
        self.loading_bar.setStyleSheet(f"background-color: #333; chunk {{ background-color: {COLOR_ACCENT_GREEN}; }}")
        top_row.addWidget(self.loading_bar)
        
        top_row.addStretch()

        # Search Center
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search Parts / Vehicle...")
        self.search_bar.setFixedWidth(250)
        self.search_bar.setFixedHeight(35)
        self.search_bar.setStyleSheet(STYLE_INPUT_CYBER + "border: none; background: transparent;")
        self.search_bar.textChanged.connect(lambda: self.search_timer.start())
        
        search_frame = QFrame()
        search_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(11, 11, 20, 0.6);
                border: 1px solid #1a1a2e;
                border-radius: 12px;
            }
        """)
        sf_layout = QHBoxLayout(search_frame)
        sf_layout.setContentsMargins(10, 0, 10, 0)
        sf_layout.addWidget(self.search_bar)
        
        top_row.addWidget(search_frame)
        
        top_row.addStretch()
        top_row.addStretch()
        
        # Operational Buttons (Require Edit Permission)
        if self.can_edit:
            self.btn_add = QPushButton("➕ NEW")
            self.btn_add.setFixedSize(90, 40)
            self.btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_add.setStyleSheet(STYLE_NEON_BUTTON)
            self.btn_add.clicked.connect(lambda: self.open_add_dialog())
            top_row.addWidget(self.btn_add)
            
            self.btn_import = QPushButton("📊 IMPORT")
            self.btn_import.setFixedSize(100, 40)
            self.btn_import.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_import.setStyleSheet(STYLE_NEON_BUTTON)
            self.btn_import.clicked.connect(self.import_data)
            top_row.addWidget(self.btn_import)
            
            self.btn_export = QPushButton("📥 EXPORT")
            self.btn_export.setFixedSize(100, 40)
            self.btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_export.setStyleSheet(STYLE_NEON_BUTTON)
            self.btn_export.clicked.connect(self.export_to_excel)
            top_row.addWidget(self.btn_export)
            
            self.btn_purchase = QPushButton("📜 BUY")
            self.btn_purchase.setFixedSize(90, 40)
            self.btn_purchase.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_purchase.setStyleSheet("background-color: rgba(241, 196, 15, 0.1); color: #f1c40f; border: 1px solid #f1c40f; border-radius: 6px; font-weight: bold;")
            self.btn_purchase.clicked.connect(self.generate_purchase_list)
            top_row.addWidget(self.btn_purchase)
            
            # SEPARATOR
            line = QFrame()
            line.setFrameShape(QFrame.Shape.VLine)
            line.setFrameShadow(QFrame.Shadow.Sunken)
            line.setStyleSheet("background-color: #333;")
            top_row.addWidget(line)
            
            # --- ACTION BUTTONS (Moved from Table) ---
            self.btn_edit_part = QPushButton("✏️ EDIT")
            self.btn_edit_part.setFixedSize(90, 40)
            self.btn_edit_part.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_edit_part.setStyleSheet("background-color: rgba(0, 229, 255, 0.1); color: #00e5ff; border: 1px solid #00e5ff; border-radius: 6px; font-weight: bold;")
            self.btn_edit_part.clicked.connect(self.on_edit_click)
            top_row.addWidget(self.btn_edit_part)

            self.btn_del_part = QPushButton("🗑️ DEL")
            self.btn_del_part.setFixedSize(90, 40)
            self.btn_del_part.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_del_part.setStyleSheet("background-color: rgba(255, 68, 68, 0.1); color: #ff4444; border: 1px solid #ff4444; border-radius: 6px; font-weight: bold;")
            self.btn_del_part.clicked.connect(self.on_delete_click)
            top_row.addWidget(self.btn_del_part)
            
        # Info Button available to all
        self.btn_info_part = QPushButton("ℹ️ INFO")
        self.btn_info_part.setFixedSize(90, 40)
        self.btn_info_part.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_info_part.setStyleSheet("background-color: rgba(255, 230, 0, 0.1); color: #ffe600; border: 1px solid #ffe600; border-radius: 6px; font-weight: bold;")
        self.btn_info_part.clicked.connect(self.on_info_click)
        top_row.addWidget(self.btn_info_part)
        
        layout.addLayout(top_row)
        
        # --- ROW 2: Holographic HUD ---
        stats_container = QFrame()
        stats_container.setStyleSheet(f"background-color: {COLOR_SURFACE}; border-radius: 12px; border: 1px solid #333;")
        stats_layout = QHBoxLayout(stats_container)
        stats_layout.setContentsMargins(20, 15, 20, 15)
        stats_layout.setSpacing(40)
        
        stats_layout.addWidget(self.card_val)
        stats_layout.addWidget(self.card_stock)
        stats_layout.addWidget(self.card_parts)
        stats_layout.addWidget(self.card_reorder)
        stats_layout.addWidget(self.card_vendors)
        stats_layout.addWidget(self.ai_nexus, 1) 
        
        layout.addWidget(stats_container)
        
        # --- FILTER BAR ROW (Replaced with Multi-Filter Panel) ---
        
        # Toggle Button for Filters
        self.filter_btn = QPushButton("🌪️ MULTI-FILTER")
        self.filter_btn.setCheckable(True)
        self.filter_btn.setChecked(False)
        self.filter_btn.setStyleSheet(STYLE_NEON_BUTTON + "padding: 5px; font-size: 10pt;")
        self.filter_btn.clicked.connect(self.toggle_filter_panel)
        
        self.btn_select_all = QPushButton("☑ SELECT ALL")
        self.btn_select_all.setStyleSheet(STYLE_NEON_BUTTON + "padding: 5px; font-size: 10pt; background-color: rgba(0, 242, 255, 0.1);")
        self.btn_select_all.clicked.connect(self.select_all_filtered)
        
        self.btn_deselect_all = QPushButton("☐ DESELECT ALL")
        self.btn_deselect_all.setStyleSheet(STYLE_NEON_BUTTON + "padding: 5px; font-size: 10pt; background-color: rgba(255, 68, 68, 0.1); color: #ff4444; border-color: #ff4444;")
        self.btn_deselect_all.clicked.connect(self.deselect_all_filtered)

        filter_header_layout = QHBoxLayout()
        filter_header_layout.addWidget(self.filter_btn)
        filter_header_layout.addSpacing(10)
        filter_header_layout.addWidget(self.btn_select_all)
        filter_header_layout.addWidget(self.btn_deselect_all)
        filter_header_layout.addStretch()
        layout.addLayout(filter_header_layout)

        # Collapsible Panel
        self.filter_panel = QFrame()
        self.filter_panel.setVisible(False)
        self.filter_panel.setStyleSheet(f"background-color: {COLOR_SURFACE}; border: 1px solid #333; border-radius: 8px;")
        fp_layout = QVBoxLayout(self.filter_panel)
        fp_layout.setContentsMargins(10, 10, 10, 10)
        
        # Row 1: Status & Category
        fp_row1 = QHBoxLayout()
        
        self.combo_status = QComboBox()
        self.combo_status.addItems(["All Stock Status", "Low Stock", "Critical (<=3)", "Dead Stock (>50)"])
        self.combo_status.setStyleSheet(STYLE_INPUT_CYBER)
        self.combo_status.currentTextChanged.connect(self.filter_table)
        fp_row1.addWidget(QLabel("Stock:"))
        fp_row1.addWidget(self.combo_status)
        
        self.combo_description = QComboBox()
        self.combo_description.addItem("All Descriptions")
        self.combo_description.setStyleSheet(STYLE_INPUT_CYBER)
        self.combo_description.currentTextChanged.connect(self.filter_table)
        fp_row1.addWidget(QLabel("Description:"))
        fp_row1.addWidget(self.combo_description)

        self.chk_new_only = QCheckBox("✨ Show ONLY Newly Added")
        self.chk_new_only.setStyleSheet(f"color: {COLOR_ACCENT_GREEN}; font-weight: bold;")
        self.chk_new_only.stateChanged.connect(self.filter_table)
        fp_row1.addWidget(self.chk_new_only)
        
        self.chk_edited_only = QCheckBox("⏳ Show ONLY Edited Recently")
        self.chk_edited_only.setStyleSheet(f"color: {COLOR_ACCENT_CYAN}; font-weight: bold;")
        self.chk_edited_only.stateChanged.connect(self.filter_table)
        fp_row1.addWidget(self.chk_edited_only)
        
        fp_row1.addStretch()
        fp_layout.addLayout(fp_row1)
        
        
        # Removed Manual Column Filters (User Request)
        # fp_row2 = QHBoxLayout()
        # ... removed ...
        
        layout.addWidget(self.filter_panel)

        # --- ROW 3: Table ---
        self.table = QTableWidget()
        cols = ["SEL", "PART ID", "NAME", "DESCRIPTION", "VENDOR", "PRICE", "QTY", "RACK", "COL"] 
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        
        # Styling
        self.table.setStyleSheet(STYLE_TABLE_CYBER)
        self.table.setAlternatingRowColors(False)
        self.table.setShowGrid(False) 
        self.table.setGridStyle(Qt.PenStyle.NoPen)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setStyleSheet(STYLE_TABLE_CYBER + "QTableWidget { background-color: #050505; alternate-background-color: #050505; }")
        
        self.delegate = BladeDelegate(self.table)
        for c in range(self.table.columnCount()): 
             self.table.setItemDelegateForColumn(c, self.delegate)
             
        self.delegate.selectToggled.connect(self.handle_select_toggle)
        layout.addWidget(self.table)

    def toggle_filter_panel(self):
        is_visible = self.filter_btn.isChecked()
        self.filter_panel.setVisible(is_visible)

    def open_add_dialog(self, part_data=None):
        try:
            dialog = AddPartDialog(self, part_data)
            if dialog.exec():
                data = dialog.get_data()
                success, msg, is_duplicate = self.db_manager.add_part(data)
                
                if is_duplicate:
                    # Show duplicate warning with option to update
                    update_msg = f"{msg}\n\nDo you want to UPDATE the existing part?"
                    if ProMessageBox.question(self, "⚠️ DUPLICATE DETECTED", update_msg):
                        # User chose to update
                        success, msg, _ = self.db_manager.add_part(data, allow_update=True)
                        if success:
                            ProMessageBox.information(self, "Updated", "Part updated successfully.")
                            self.load_data()
                        else:
                            ProMessageBox.critical(self, "Error", f"Failed to update part.\n{msg}")
                    # else: User cancelled, do nothing
                elif success:
                    ProMessageBox.information(self, "Success", "Part added successfully.")
                    self.load_data()
                else:
                    ProMessageBox.critical(self, "Error", f"Failed to save part.\n{msg}")
        except Exception as e:
            app_logger.error(f"Error opening add dialog: {e}")
            ProMessageBox.critical(self, "Error", f"An error occurred: {e}")

    def import_data(self):
        try:
            path, _ = QFileDialog.getOpenFileName(self, "Import Inventory", "", "CSV Files (*.csv);;Excel Files (*.xlsx)")
            if not path: return
            # Vendor Assignment Prompt
            vendor_override = None
            vendors = self.db_manager.get_all_vendors()
            if vendors:
                vendor_names = [v[1] for v in vendors]
                if vendor_names:
                    items = ["(No Assignment)"] + vendor_names
                    item, ok = QInputDialog.getItem(self, "Assign Vendor", 
                                                  "Would you like to assign a Vendor to these parts?", 
                                                  items, 0, False)
                    if ok and item and item != "(No Assignment)":
                        vendor_override = item

            if path.endswith(".csv"):
                 success = self.db_manager.import_inventory_data(path, vendor_override=vendor_override)
            else:
                 ProMessageBox.information(self, "Info", "Excel import not fully supported here yet. Please use CSV or Import via Catalog Tab.")
                 return

            if success:
                ProMessageBox.information(self, "Success", "Inventory imported successfully.")
                self.load_data()
            else:
                ProMessageBox.critical(self, "Error", "Failed to import data. Check logs.")
        except Exception as e:
            app_logger.error(f"Error importing data: {e}")
            ProMessageBox.critical(self, "Error", f"Import failed: {e}")

    def export_to_excel(self):
        try:
            if not self.all_rows:
                ProMessageBox.show_info(self, "Info", "No data to export.")
                return

            path, _ = QFileDialog.getSaveFileName(self, "Export Inventory", f"Inventory_{datetime.now().strftime('%Y%m%d')}.xlsx", "Excel Files (*.xlsx)")
            if not path: return
            
            cols = ["Part ID", "Name", "Description", "MRP", "Stock", "Rack", "Column", "Reorder Level", "Vendor", "Compatibility", "Category", "Added On", "Last Ordered"]
            df = pd.DataFrame(self.all_rows, columns=cols)
            df.to_excel(path, index=False)
            ProMessageBox.information(self, "Success", f"Exported successfully to:\n{path}")
        except Exception as e:
             app_logger.error(f"Error exporting data: {e}")
             ProMessageBox.critical(self, "Error", f"Export failed: {e}")

    # Old generate_purchase_list implementation removed.
    # The active implementation is at the bottom of the file which redirects to MainWindow.


    def pulse_animation(self):
        # Update Delegate Pulse
        if hasattr(self, 'delegate'):
             if self.delegate.pulse_increasing:
                 self.delegate.pulse_frame += 1
                 if self.delegate.pulse_frame >= 20: 
                     self.delegate.pulse_increasing = False
             else:
                 self.delegate.pulse_frame -= 1
                 if self.delegate.pulse_frame <= 0:
                     self.delegate.pulse_increasing = True
             self.table.viewport().update()

    def load_data(self):
        self.loading_bar.setVisible(True)
        self.loading_bar.setRange(0, 0) 
        self.loader_thread.start()
        
        # Start Pulse Timer (200ms = 5fps, enough for subtle animation)
        if not hasattr(self, 'pulse_timer'):
             self.pulse_timer = QTimer(self)
             self.pulse_timer.timeout.connect(self.pulse_animation)
             self.pulse_timer.start(200)

    def on_data_loaded(self, rows):
        try:
            if hasattr(self, 'loading_bar'): self.loading_bar.setVisible(False)
            self.all_rows = rows
            
            # --- Populate Description Combo ---
            descriptions = set()
            for r in rows:
                if len(r) > 2 and r[2]: # Index 2 is Description
                    descriptions.add(str(r[2]).strip())
            
            current_desc = self.combo_description.currentText()
            self.combo_description.blockSignals(True)
            self.combo_description.clear()
            self.combo_description.addItem("All Descriptions")
            self.combo_description.addItems(sorted(list(descriptions)))
            self.combo_description.setCurrentText(current_desc) # Restore if possible
            self.combo_description.blockSignals(False)
            # ---------------------------------
            
            # Stats (Check existence first)
            total_val = 0
            low_stock_count = 0
            vendors = set()
            
            for r in rows:
                price = float(r[3] or 0)
                qty = int(r[4] or 0)
                total_val += (price * qty)
                reorder = int(r[7] or 5)
                if len(r) > 8: vendors.add(r[8])
                if qty <= reorder: low_stock_count += 1
                    
            if hasattr(self, 'card_val'): self.card_val.set_value(f"₹ {total_val:,.0f}")
            if hasattr(self, 'card_reorder'): self.card_reorder.set_value(str(low_stock_count))
            if hasattr(self, 'card_vendors'): self.card_vendors.set_value(str(len(vendors)))
            
            self.generateSmartInsights(rows)
            # self.add_log(f"System initialized. Loaded {len(rows)} parts.")
            self.filter_table()
            
            # Prune selected_part_ids to only include valid IDs
            current_ids = set(str(r[0]) for r in rows)
            self.selected_part_ids.intersection_update(current_ids)
            
        except Exception as e:

            app_logger.error(f"Error in on_data_loaded: {e}")

    def add_log(self, text):
        app_logger.info(f"[Inventory] {text}")

    def generateSmartInsights(self, rows):
        insights = []
        critical_items = []
        dead_stock_items = []
        max_price = 0
        high_value_item = None
        
        for r in rows:
            name = r[1]
            price = float(r[3] or 0)
            qty = int(r[4] or 0)
            if qty <= 3: critical_items.append(name)
            if qty > 50: dead_stock_items.append(name)
            if price > max_price:
                max_price = price
                high_value_item = (name, price)
        
        if critical_items:
            import random
            item = random.choice(critical_items)
            insights.append(f"CRITICAL: {item} is nearly empty.")
        if dead_stock_items:
            import random
            item = random.choice(dead_stock_items)
            insights.append(f"DEAD STOCK: {item} > 50 units.")
        if high_value_item:
            insights.append(f"HIGH VALUE: {high_value_item[0]}")
            
        if not insights: insights.append("System All Clear.")
        if hasattr(self, 'ai_nexus'): self.ai_nexus.set_insights(insights)


    # --- ACTION HANDLERS ---
    def on_edit_click(self):
        if not self.can_edit:
             ProMessageBox.warning(self, "Access Denied", "You do not have permission to edit inventory.\nContact Admin.")
             return

        row = self.table.currentRow()
        if row < 0:
            ProMessageBox.warning(self, "Select Part", "Please select a part to edit.")
            return
        item_id_w = self.table.item(row, 1) 
        if item_id_w:
            # Handle alphanumeric IDs (no int conversion)
            part_id_str = str(item_id_w.text()).strip()
            part_data = None
            for r in self.all_rows:
                if str(r[0]) == part_id_str:
                    part_data = r
                    break
            if part_data:
                self.open_add_dialog(part_data)

    def on_delete_click(self):
        if not self.can_edit:
             ProMessageBox.warning(self, "Access Denied", "You do not have permission to delete inventory.\nContact Admin.")
             return

        row = self.table.currentRow()
        if row < 0:
            ProMessageBox.warning(self, "Select Part", "Please select a part to delete.")
            return
        item_id_w = self.table.item(row, 1)
        if item_id_w:
            part_id = item_id_w.text() # String ID
            self.delete_part(part_id)

    def on_info_click(self):
        row = self.table.currentRow()
        if row < 0:
            ProMessageBox.warning(self, "Select Part", "Please select a part to view info.")
            return
        item_id_w = self.table.item(row, 1)
        if item_id_w:
            part_id_str = str(item_id_w.text()).strip()
            part_data = None
            for r in self.all_rows:
                if str(r[0]) == part_id_str:
                    part_data = r
                    break
            if part_data:
                self.show_part_info(part_data)


    def handle_select_toggle(self, row, state):
        itm = self.table.item(row, 0)
        if itm:
            data = itm.data(Qt.ItemDataRole.UserRole)
            data['checked'] = state
            itm.setData(Qt.ItemDataRole.UserRole, data)
            
            # Update Persistent Set
            if row in self.rows_map:
                part_id = str(self.rows_map[row][0])
                if state:
                    self.selected_part_ids.add(part_id)
                else:
                    self.selected_part_ids.discard(part_id)
            
            self.update_dashboard()

    def select_all_filtered(self):
        """Select all currently visible (filtered) items"""
        for i in range(self.table.rowCount()):
            if i in self.rows_map:
                part_id = str(self.rows_map[i][0])
                self.selected_part_ids.add(part_id)
                # Update visual state
                itm = self.table.item(i, 0)
                if itm:
                    data = itm.data(Qt.ItemDataRole.UserRole)
                    data['checked'] = True
                    itm.setData(Qt.ItemDataRole.UserRole, data)
        self.update_dashboard()
        self.table.viewport().update()

    def deselect_all_filtered(self):
        """Deselect all currently visible (filtered) items"""
        for i in range(self.table.rowCount()):
            if i in self.rows_map:
                part_id = str(self.rows_map[i][0])
                self.selected_part_ids.discard(part_id)
                # Update visual state
                itm = self.table.item(i, 0)
                if itm:
                    data = itm.data(Qt.ItemDataRole.UserRole)
                    data['checked'] = False
                    itm.setData(Qt.ItemDataRole.UserRole, data)
        self.update_dashboard()
        self.table.viewport().update()


    def filter_table(self):
        # Advanced Filtering Logic
        global_search = self.search_bar.text().lower()
        
        # New Panel Filters
        status_filter = self.combo_status.currentText()
        desc_filter = self.combo_description.currentText()
        new_only = self.chk_new_only.isChecked()
        edited_only = self.chk_edited_only.isChecked()
        
        # Column Filters REMOVED
        # col_filters = {}
        # ...
            
        filtered_rows = []
        
        # Pre-calc date for new check
        today = datetime.now()
        
        for r in self.all_rows:
            # r indices: 0:ID, 1:Name, 2:Desc, 3:Price, 4:Qty, ...
            
            # 1. Global Search
            id_val = str(r[0]).lower()
            name_val = str(r[1]).lower()
            vendor_val = str(r[8]).lower() if len(r)>8 else ""
            desc_val = str(r[2]).lower()
            
            if global_search:
                if (global_search not in id_val) and (global_search not in name_val) and (global_search not in vendor_val) and (global_search not in desc_val):
                    continue

            # 2. Status Filter
            qty = int(r[4] or 0)
            reorder = int(r[7] or 5) if len(r) > 7 else 5
            
            if status_filter == "Low Stock":
                if qty > reorder: continue
            elif status_filter == "Critical (<=3)":
                if qty > 3: continue
            elif status_filter == "Dead Stock (>50)":
                if qty <= 50: continue
                
            # 3. Description Filter
            if desc_filter != "All Descriptions":
                item_desc = str(r[2]).strip()
                if item_desc != desc_filter: continue
                
            # 4. New Only Filter
            if new_only:
                added_date_str = r[11] if len(r) > 11 else ""
                is_new = False
                if added_date_str:
                    try:
                        # Try parsing various formats
                        # DB default seems to be YYYY-MM-DD or YYYY-MM-DD HH:MM
                         # We only care about YYYY-MM-DD
                        d_str = added_date_str.split(" ")[0]
                        d_obj = datetime.strptime(d_str, "%Y-%m-%d")
                        if (today - d_obj).days <= 7:
                            is_new = True
                    except:
                        pass
                if not is_new: continue

            # 5. Edited Recently Filter
            if edited_only:
                edited_date_str = r[14] if len(r) > 14 else ""
                is_edited = False
                if edited_date_str:
                    try:
                        d_obj = datetime.strptime(edited_date_str, "%Y-%m-%d %H:%M")
                        if (today - d_obj).total_seconds() <= 86400: # 24h
                            is_edited = True
                    except: pass
                if not is_edited: continue

            # 5. Removed Column Filter Logic
            
            # if col_match:
            #     filtered_rows.append(r)
            filtered_rows.append(r)
                
        self.populate_table(filtered_rows)

    def _create_item(self, val, col_type, extra_data=None):
        """Helper to create a styled table item (defined once, reused per row)."""
        item = QTableWidgetItem(str(val))
        data_dict = {'type': col_type, 'val': val}
        if extra_data:
            data_dict.update(extra_data)
        item.setData(Qt.ItemDataRole.UserRole, data_dict)
        return item

    def populate_table(self, rows):
        """Ultra-fast population using ItemData instead of Widgets"""
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        self.table.setRowCount(len(rows))
        self.rows_map = {}
        
        today = datetime.now()
        
        for i, r in enumerate(rows):
            self.rows_map[i] = r 

            # col 0: Checkbox (Select)
            # Check against persistent selection
            is_checked = str(r[0]) in self.selected_part_ids
            item0 = self._create_item("", 'select', {'checked': is_checked})
            self.table.setItem(i, 0, item0)

            
            qty = int(r[4] or 0)
            reorder_level = int(r[7] or 5) if len(r) > 7 else 5
            is_low_stock = qty <= reorder_level
            
            # Calculate is_new & is_edited
            is_new = False
            added_date_str = r[11] if len(r) > 11 else ""
            if added_date_str:
                try:
                    d_str = added_date_str.split(" ")[0]
                    d_obj = datetime.strptime(d_str, "%Y-%m-%d")
                    if (today - d_obj).days <= 7:
                        is_new = True
                except: pass
            
            is_edited = False
            edited_date_str = r[14] if len(r) > 14 else "" # last_edited_date is index 14
            if edited_date_str:
                try:
                    # edited_date format: %Y-%m-%d %H:%M
                    d_obj = datetime.strptime(edited_date_str, "%Y-%m-%d %H:%M")
                    if (today - d_obj).total_seconds() <= 86400: # 24h
                        is_edited = True
                except: pass

            # 1: ID
            self.table.setItem(i, 1, self._create_item(r[0], 'id', {'is_low_stock': is_low_stock}))
            
            # 2: Name (With Vehicle Tags & Badges)
            item2 = self._create_item(r[1], 'name', {
                'is_low_stock': is_low_stock, 
                'is_new': is_new,
                'is_edited': is_edited
            })
            # Add Vehicle Tags if present
            if len(r) > 9 and r[9]:
                tags = [t.strip() for t in r[9].split(',') if t.strip()]
                data = item2.data(Qt.ItemDataRole.UserRole)
                data['vehicle_tags'] = tags
                item2.setData(Qt.ItemDataRole.UserRole, data)
            self.table.setItem(i, 2, item2)
            
            # 3: Description 
            self.table.setItem(i, 3, self._create_item(r[2], 'description'))
            
            # 4: Vendor (New)
            vendor_name = r[8] if len(r) > 8 else ""
            self.table.setItem(i, 4, self._create_item(vendor_name, 'vendor'))

            # 5: Price
            self.table.setItem(i, 5, self._create_item(r[3], 'price'))
            
            # 6: Qty
            max_val = max(reorder_level * 2, 10)
            item5 = self._create_item("", 'stock', {'val': qty, 'max_val': max_val})
            self.table.setItem(i, 6, item5)
            
            # 7: Rack
            self.table.setItem(i, 7, self._create_item(r[5], 'generic'))
            
            # 8: Col
            self.table.setItem(i, 8, self._create_item(r[6], 'generic'))
                
        self.table.blockSignals(False)
        self.table.setUpdatesEnabled(True)
        
        # Auto-Resize Columns to Content
        self.table.resizeColumnsToContents()
        
        # Adjust specific columns if needed (Optional)
        # self.table.setColumnWidth(0, 40)   # SEL
        
        # Update Dashboard with fresh stats
        self.update_dashboard()


    def update_dashboard(self):
        """Update dashboard stats using global DB values (Fixed for accuracy)"""
        # Get Global Stats from DB
        stats = self.db_manager.get_inventory_stats()
        
        if stats:
            total_val = stats.get("total_val", 0.0)
            total_stock = stats.get("total_stock", 0)
            part_count = stats.get("part_count", 0)
            low_stock_count = stats.get("low_stock_count", 0)
            vendor_count = stats.get("vendor_count", 0)
        else:
            total_val = 0
            total_stock = 0
            part_count = 0
            low_stock_count = 0
            vendor_count = 0

        # Update Cards
        if hasattr(self, 'card_val'): self.card_val.set_value(f"₹ {total_val:,.0f}")
        if hasattr(self, 'card_stock'): self.card_stock.set_value(str(total_stock))
        if hasattr(self, 'card_parts'): self.card_parts.set_value(str(part_count))
        if hasattr(self, 'card_reorder'): self.card_reorder.set_value(str(low_stock_count))
        if hasattr(self, 'card_vendors'): self.card_vendors.set_value(str(vendor_count))

    def auto_select_low_stock(self):
        """Select all rows with low stock"""
        for i in range(self.table.rowCount()):
            if i in self.rows_map:
                r = self.rows_map[i]
                qty = int(r[4] or 0)
                reorder = int(r[7] or 5) if len(r) > 7 else 5
                
                if qty <= reorder:
                     itm = self.table.item(i, 0)
                     if itm:
                         data = itm.data(Qt.ItemDataRole.UserRole)
                         data['checked'] = True
                         itm.setData(Qt.ItemDataRole.UserRole, data)
                         
                         self.selected_part_ids.add(str(r[0]))
                         
        self.table.viewport().update()
        self.update_dashboard()


    def get_selected_items(self):
        """Return list of selected items based on persistent ID set + all_rows"""
        selected = []
        # Filter all_rows for IDs in selected_part_ids
        for r in self.all_rows:
            if str(r[0]) in self.selected_part_ids:
                # Same format as before
                # ID, Name, Stock, Reorder, Vendor
                reorder = r[7] if len(r) > 7 else 5
                vendor = r[8] if len(r) > 8 else ""
                selected.append([r[0], r[1], r[4], reorder, vendor])
        
        return selected


    def show_part_info(self, row_data):
        """Show detailed info about the part including added date and who added it"""
        # row_data indices: 
        # 0:ID, 1:Name, 2:Desc, 3:Price, 4:Qty, 5:Rack, 6:Col, 7:Reorder, 
        # 8:Vendor, 9:Compat, 10:Cat, 11:AddedDate, 12:LastOrdered, 13:AddedBy
        
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLabel, QDialogButtonBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Part Details - {row_data[1]}")
        dialog.setMinimumWidth(400)
        dialog.setStyleSheet(f"background-color: {COLOR_SURFACE}; color: white;")
        
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        
        def add_row(label, value):
            lbl = QLabel(str(value))
            lbl.setStyleSheet("color: #00f2ff; font-weight: bold; font-size: 11pt;")
            form.addRow(f"{label}:", lbl)

        add_row("Part ID", row_data[0])
        add_row("Name", row_data[1])
        add_row("Description", row_data[2])
        add_row("Price", f"₹ {row_data[3]}")
        add_row("Quantity", row_data[4])
        add_row("Location", f"Rack {row_data[5]}, Col {row_data[6]}")
        add_row("Vendor", row_data[8] if len(row_data) > 8 else "N/A")
        add_row("Added Date", row_data[11] if len(row_data) > 11 and row_data[11] else "Old Stock")
        add_row("Last Updated", row_data[12] if len(row_data) > 12 and row_data[12] else "Never")
        
        # safely get added_by if it exists in tuple
        added_by = row_data[13] if len(row_data) > 13 else "System"
        add_row("Added By", added_by)

        layout.addLayout(form)
        
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(dialog.reject)
        btn_box.setStyleSheet(STYLE_NEON_BUTTON)
        layout.addWidget(btn_box)
        
        dialog.exec()

    def delete_part(self, part_id):
        if ProMessageBox.question(self, "Confirm Delete", f"Are you sure you want to delete Part ID: {part_id}?"):
            try:
                success, msg = self.db_manager.delete_part(part_id)
                if success:
                    ProMessageBox.information(self, "Success", "Part deleted successfully.")
                    self.selected_part_ids.discard(str(part_id))
                    self.load_data()
                else:
                    ProMessageBox.critical(self, "Error", f"Failed to delete part: {msg}")
            except Exception as e:
                app_logger.error(f"Error deleting part: {e}")
                ProMessageBox.critical(self, "Error", f"An error occurred: {e}")



    def extract_vehicle_tags(self, text):
        """Extracts known vehicle names from text."""
        if not text: return []
        text_upper = text.upper()
        
        keywords = [
            "ACTIVA", "JUPITER", "SPLENDOR", "PASSION", "PLATINA", "PULSAR", "APACHE", 
            "ROYAL ENFIELD", "ACCESS", "DIO", "SCOOTY", "SHINE", "UNICORN", "CLASSIC", 
            "BULLET", "RX100", "R15", "MT15", "DUKE", "KTM", "DOMINAR", "AVENGER", 
            "FZ", "GIXXER", "BURGMAN", "NTORQ", "AEROX", "OLA", "ATHER", "CHETAK", 
            "XL100", "SUPER XL", "VICTOR", "STAR CITY", "SPORT", "RADON", "HF DELUXE", 
            "GLAMOUR", "SUPER SPLENDOR", "XPRO", "DREAM YUGA", "LIVO", "CB SHINE", 
            "SP 125", "GRAZIA", "AVIATOR", "MAESTRO", "PLEASURE", "DESTINI", "PEP+", 
            "ZEST", "WEGO", "FASCINO", "RAYZR", "SZ-RR", "SALUTO"
        ]
        
        found = []
        for k in keywords:
            if k in text_upper:
                found.append(k)
                
        return found

    def generate_purchase_list(self):
        """
        Collects selected items and opens the Purchase Order Page.
        """
        selected_items = self.get_selected_items()
        
        if not selected_items:
            # If no manual selection, ask if user wants to auto-select low stock?
            # Or just show error.
            # Step 2 instructions say "From Inventory Selection".
            # "Tab 1 receives a list of selected items".
            # Let's show a message if empty.
            ProMessageBox.information(self, "No Selection", "Please select items from the table to create a Purchase Order.")
            return

        # Interface with MainWindow
        try:
            main_win = self.window()
            if hasattr(main_win, "go_to_purchase_page"):
                success = main_win.go_to_purchase_page(selected_items)
                
                if success:
                    # Auto-clear selection after operation
                    self.selected_part_ids.clear()
                    self.filter_table()
                    self.update_dashboard()

            else:
                app_logger.error("MainWindow does not have 'go_to_purchase_page' method")
                ProMessageBox.critical(self, "Error", "Navigation to Purchase Page failed.")
        except Exception as e:
            app_logger.error(f"Error navigating to PO Page: {e}")
            ProMessageBox.critical(self, "Error", f"Navigation Error: {e}")
