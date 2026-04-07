from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
                             QDialog, QFormLayout, QDialogButtonBox, QAbstractItemView, QFileDialog,
                             QProgressBar, QCheckBox, QComboBox, QStyledItemDelegate, QStyle,
                             QInputDialog, QMenu, QApplication)
import pandas as pd
import openpyxl
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QRect, QPointF, QSize, QEvent
from PyQt6.QtGui import QColor, QBrush, QPainter, QPen, QFont, QLinearGradient, QFontMetrics
from styles import (COLOR_SURFACE, COLOR_ACCENT_CYAN, COLOR_ACCENT_GREEN, COLOR_ACCENT_YELLOW, COLOR_TEXT_PRIMARY, COLOR_ACCENT_RED,
                   STYLE_INPUT_CYBER, STYLE_TABLE_CYBER, STYLE_GLASS_PANEL, STYLE_ACTION_HOLO,
                   DIM_BUTTON_HEIGHT, DIM_INPUT_HEIGHT, DIM_MARGIN_STD, DIM_SPACING_STD, DIM_ICON_SIZE)
import ui_theme
from custom_components import ProMessageBox, ProDialog, ReactorStatCard, AINexusNode
from vendor_manager import VendorManagerDialog
from logger import app_logger
from hsn_sync_engine import HsnSyncDialog
from vehicle_compat_engine import VehicleCompatDialog
import os
from datetime import datetime
import webbrowser

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
                fill_color = QColor(255, 0, 0, 25)
                side_border_color = QColor(255, 60, 60, 180)
                text_color = QColor(255, 120, 120)
            else:
                fill_color = QColor(0, 242, 255, 12)
                side_border_color = QColor(0, 242, 255, 180)
                text_color = QColor(0, 242, 255)
        
        elif col_type == 'name':
            if is_low_stock:
                fill_color = QColor(255, 0, 0, 15)
                side_border_color = QColor(255, 0, 0, 80)
                text_color = QColor(255, 180, 180)
            else:
                fill_color = QColor(255, 255, 255, 6)
                side_border_color = QColor(255, 255, 255, 20)
                text_color = QColor(230, 230, 230)

        elif col_type == 'price':
            fill_color = QColor(255, 170, 0, 12)
            side_border_color = QColor(255, 170, 0, 150)
            text_color = QColor(255, 210, 80)

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
            
            # ── Cell-fill: the background IS the bar ─────────────────────
            # The filled portion of the cell is color-washed; the rest stays dark.
            # Zero glow bleed, zero visual competition with adjacent columns.

            if val <= 3:
                r, g, b = 255, 60, 60
                pulse = int(15 + 12 * abs((self.pulse_frame % 40) - 20) / 20.0)
            elif val <= 8:
                r, g, b = 255, 160, 0
                pulse = 18
            else:
                r, g, b = 0, 200, 80
                pulse = 16

            fill_w = int(rect.width() * ratio)

            # Dark empty zone (full cell first)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(14, 16, 26))
            painter.drawRect(rect)

            # Color fill zone (left portion = filled stock)
            if fill_w > 0:
                fill_rect = QRect(rect.left(), rect.top(), fill_w, rect.height())
                grad = QLinearGradient(QPointF(fill_rect.left(), 0), QPointF(fill_rect.right(), 0))
                grad.setColorAt(0.0, QColor(r, g, b, 0))       # transparent start
                grad.setColorAt(0.6, QColor(r, g, b, pulse))   # build up
                grad.setColorAt(1.0, QColor(r, g, b, pulse + 10))  # slightly brighter edge
                painter.setBrush(grad)
                painter.drawRect(fill_rect)

            # Bright leading-edge line at fill boundary
            if 0 < fill_w < rect.width():
                painter.setPen(QPen(QColor(r, g, b, 90), 1))
                painter.drawLine(rect.left() + fill_w, rect.top() + 3,
                                 rect.left() + fill_w, rect.bottom() - 3)

            # Number centered, bold, matching color
            painter.setPen(QColor(r, g, b))
            nf = QFont("Segoe UI", 9)
            nf.setBold(True)
            painter.setFont(nf)
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
            elif col_type == 'id':
                self._draw_3d_chip(painter, rect, text, text_color,
                                   QColor(0, 242, 255, 18), bold=True)
            elif col_type == 'price' and text:
                self._draw_3d_chip(painter, rect, f"₹ {text}", text_color,
                                   QColor(255, 170, 0, 12), bold=True)
            elif col_type == 'description':
                # Parse comma separated tags
                tags = [t.strip() for t in text.split(',') if t.strip()]
                if tags:
                     self._draw_tags_only(painter, rect, tags)
                else:
                     painter.drawText(rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
            elif col_type == 'compat':
                # Render compatibility text as amber pills
                if text and text not in ('None', 'N/A', '-', ''):
                    self._draw_compat_pills(painter, rect, text)
                else:
                    painter.setPen(QColor('#444'))
                    painter.drawText(rect.adjusted(5,0,0,0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, '—')
            elif col_type == 'vendor' and text and text not in ('None', ''):
                v_color = self._get_vendor_color(text)
                self._draw_3d_chip(painter, rect, text, v_color,
                                   QColor(v_color.red(), v_color.green(), v_color.blue(), 20), bold=False)
            else:
                 align = Qt.AlignmentFlag.AlignCenter
                 draw_rect = QRect(rect).adjusted(5, 0, -5, 0)
                 painter.drawText(draw_rect, align, text)

        painter.restore()

    def _draw_3d_chip(self, painter, rect, text, text_color, bg_color, bold=False):
        """Draw text inside a floating 3D raised chip with bevel highlight/shadow."""
        fm = painter.fontMetrics()
        chip_font = QFont("Segoe UI", 8)
        chip_font.setBold(bold)
        painter.setFont(chip_font)
        fm = QFontMetrics(chip_font)
        tw = fm.horizontalAdvance(text)
        chip_w = min(tw + 16, rect.width() - 8)
        chip_h = rect.height() - 8
        chip_x = rect.left() + 4
        chip_y = rect.top() + 4
        chip_rect = QRect(chip_x, chip_y, chip_w, chip_h)

        # Base fill
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg_color)
        painter.drawRoundedRect(chip_rect, 4, 4)

        # Top-left highlight (makes it look raised)
        hl = QColor(255, 255, 255, 30)
        painter.setPen(QPen(hl, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(chip_rect.left()+2, chip_rect.top()+1,
                         chip_rect.right()-2, chip_rect.top()+1)     # top edge
        painter.drawLine(chip_rect.left()+1, chip_rect.top()+2,
                         chip_rect.left()+1, chip_rect.bottom()-2)   # left edge

        # Bottom-right shadow (depth)
        sh = QColor(0, 0, 0, 60)
        painter.setPen(QPen(sh, 1))
        painter.drawLine(chip_rect.left()+2, chip_rect.bottom()-1,
                         chip_rect.right()-2, chip_rect.bottom()-1)  # bottom edge
        painter.drawLine(chip_rect.right()-1, chip_rect.top()+2,
                         chip_rect.right()-1, chip_rect.bottom()-2)  # right edge

        # Outer subtle border
        painter.setPen(QPen(QColor(text_color.red(), text_color.green(),
                                   text_color.blue(), 50), 1))
        painter.drawRoundedRect(chip_rect.adjusted(0,0,-1,-1), 4, 4)

        # Elide text if it doesn't fit inside the chip
        display_text = fm.elidedText(text, Qt.TextElideMode.ElideRight, chip_w - 8)
        painter.setPen(text_color)
        painter.drawText(chip_rect, Qt.AlignmentFlag.AlignCenter, display_text)

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

    def _draw_compat_pills(self, painter, rect, text):
        """Draw vehicle compatibility text as amber semi-transparent pills in the cell."""
        vehicles = [v.strip() for v in text.split(',') if v.strip()]
        x = rect.left() + 5
        y = rect.top() + 4

        painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        fm = painter.fontMetrics()
        AMBER = QColor("#ffaa00")

        for v in vehicles:
            w = fm.horizontalAdvance(v) + 10
            h = 16
            if x + w > rect.right():
                break
            pill = QRect(x, y, w, h)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 170, 0, 35))
            painter.drawRoundedRect(pill, 4, 4)
            painter.setPen(AMBER)
            painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, v)
            x += w + 4

    def _draw_name_with_tags_extended(self, painter, rect, text, tags, is_new, is_edited):
        # Draw the part name - left aligned, vertically centered
        name_font = QFont("Segoe UI", 9)
        name_font.setBold(False)
        painter.setFont(name_font)
        painter.setPen(QColor(220, 220, 220))

        fm = painter.fontMetrics()
        text_w = min(fm.horizontalAdvance(text), 200)  # cap name width
        name_rect = QRect(rect.left() + 8, rect.top(), text_w + 4, rect.height())
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)

        # Badges flow inline after the name text
        badge_font = QFont("Segoe UI", 7)
        badge_font.setBold(True)
        painter.setFont(badge_font)
        badge_fm = painter.fontMetrics()

        current_x = rect.left() + 8 + text_w + 8
        badge_h = 14
        badge_y = rect.center().y() - badge_h // 2

        def _draw_badge(label, bg_color, fg_color):
            nonlocal current_x
            bw = badge_fm.horizontalAdvance(label) + 8
            if current_x + bw > rect.right() - 4:
                return  # clip, don't overflow
            br = QRect(current_x, badge_y, bw, badge_h)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(bg_color)
            painter.drawRoundedRect(br, 3, 3)
            painter.setPen(fg_color)
            painter.drawText(br, Qt.AlignmentFlag.AlignCenter, label)
            current_x += bw + 4

        if is_new:
            _draw_badge("NEW", QColor(0, 200, 80, 55), QColor(0, 255, 100))
        if is_edited:
            _draw_badge("EDITED", QColor(0, 170, 255, 50), QColor(0, 229, 255))
        if tags:
            _draw_badge(f"🚗 {len(tags)}", QColor(160, 0, 200, 45), QColor(200, 80, 255))

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

class CatalogBridgeThread(QThread):
    data_loaded = pyqtSignal(dict, set, dict) 
    
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        
    def run(self):
        try:
            s = self.db_manager.get_shop_settings() or {}
            cat_db = s.get("nexses_catalog_db", "")
            import os
            from path_utils import get_resource_path  # type: ignore
            if not cat_db or not os.path.exists(cat_db):
                cat_db = get_resource_path("nexses_ecatalog.db")
                
            if not os.path.exists(cat_db):
                self.data_loaded.emit({}, set(), {})
                return
                
            import sqlite3
            conn = sqlite3.connect(cat_db, check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT cm.part_code, vm.segment, vm.model_name, pm.category 
                FROM compatibility_map cm
                JOIN vehicles_master vm ON cm.vehicle_id = vm.vehicle_id
                JOIN parts_master pm ON cm.part_code = pm.part_code
            """)
            rows = cursor.fetchall()
            
            mapping = {}
            categories = set()
            hierarchy = {}
            
            for part_code, segment, model_name, section in rows:
                pc = str(part_code).strip().upper()
                seg = str(segment).strip().upper() if segment else "UNCATEGORIZED"
                mod = str(model_name).strip().upper() if model_name else "UNKNOWN"
                sec = str(section).strip().upper() if section else "GENERAL"
                
                if pc not in mapping:
                    mapping[pc] = []
                mapping[pc].append((seg, mod, sec))
                
                categories.add(seg)
                if seg not in hierarchy:
                    hierarchy[seg] = {}
                if mod not in hierarchy[seg]:
                    hierarchy[seg][mod] = set()
                hierarchy[seg][mod].add(sec)
                
            conn.close()
            self.data_loaded.emit(mapping, categories, hierarchy)
        except Exception as e:
            app_logger.error(f"CatalogBridge error: {e}")
            self.data_loaded.emit({}, set(), {})

class DataLoadThread(QThread):
    data_loaded = pyqtSignal(list)
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager

    def _load_catalog_compat(self) -> dict:
        """
        Load a part_code -> 'Model1, Model2, ...' mapping from nexses_ecatalog.db.
        Returns empty dict if catalog DB is not available.
        """
        try:
            import sqlite3, os
            s = self.db_manager.get_shop_settings() or {}
            cat_db = s.get("nexses_catalog_db", "")
            from path_utils import get_resource_path  # type: ignore
            if not cat_db or not os.path.exists(cat_db):
                cat_db = get_resource_path("nexses_ecatalog.db")
            if not os.path.exists(cat_db):
                return {}
            conn = sqlite3.connect(cat_db, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("""
                SELECT cm.part_code,
                       vm.model_name || CASE WHEN vm.variant != '' THEN ' ' || vm.variant ELSE '' END AS label
                FROM compatibility_map cm
                JOIN vehicles_master vm ON vm.vehicle_id = cm.vehicle_id
                ORDER BY cm.part_code, vm.model_name
            """)
            compat: dict = {}
            for row in cur.fetchall():
                pc = str(row["part_code"]).strip().upper()
                lbl = str(row["label"]).strip()
                if lbl and lbl not in ('*', '**', '***', '****', '*****'):
                    compat.setdefault(pc, [])
                    if lbl not in compat[pc]:
                        compat[pc].append(lbl)
            conn.close()
            return compat
        except Exception as e:
            app_logger.warning(f"[DataLoadThread] catalog compat load failed: {e}")
            return {}

    def run(self):
        try:
            rows = self.db_manager.get_all_parts()
            # Enrich rows with catalog-based vehicle compatibility
            cat_compat = self._load_catalog_compat()
            if cat_compat:
                enriched = []
                for r in rows:
                    part_id = str(r[0]).strip().upper()
                    catalog_tags = cat_compat.get(part_id, [])
                    # r[9] is the compatibility column; prefer catalog over manual if catalog has data
                    existing = str(r[9]).strip() if len(r) > 9 and r[9] and str(r[9]) not in ('None','') else ''
                    if catalog_tags:
                        merged_tags = ', '.join(catalog_tags)
                    else:
                        merged_tags = existing
                    # Rebuild the row as a list to mutate index 9
                    row_list = list(r)
                    while len(row_list) <= 9:
                        row_list.append('')
                    row_list[9] = merged_tags
                    enriched.append(tuple(row_list))
                self.data_loaded.emit(enriched)
            else:
                self.data_loaded.emit(rows)
        except Exception as e:
            app_logger.error(f"Data load thread error: {e}")
            self.data_loaded.emit([])

class AddPartDialog(QDialog):
    def __init__(self, parent=None, db_manager=None, part_data=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.setWindowTitle("Add/Edit Part")
        self.setStyleSheet(ui_theme.get_dialog_style())
        self.layout = QFormLayout(self)
        self.part_data = part_data

        # Fields
        self.in_id = QLineEdit()
        self.in_name = QLineEdit()
        self.in_desc = QLineEdit()
        self.in_price = QLineEdit()
        self.in_qty = QLineEdit()
        self.in_rack = QLineEdit()
        self.in_col = QLineEdit()
        self.in_reorder = QLineEdit("5")
        self.in_vendor = QLineEdit()
        self.in_compat = QLineEdit()
        self.in_category = QLineEdit()
        self.in_hsn = QLineEdit()
        self.in_gst = QLineEdit("18.0")

        for w in [self.in_id, self.in_name, self.in_desc, self.in_price, self.in_qty, 
                  self.in_rack, self.in_col, self.in_reorder, self.in_vendor, 
                  self.in_compat, self.in_category, self.in_hsn, self.in_gst]:
            w.setStyleSheet(ui_theme.get_lineedit_style())

        # HSN Layout with Verify Button
        hsn_layout = QHBoxLayout()
        hsn_layout.addWidget(self.in_hsn)
        self.btn_verify = QPushButton("🔗 Verify")
        self.btn_verify.setFixedWidth(80)
        self.btn_verify.setFixedHeight(DIM_INPUT_HEIGHT)
        self.btn_verify.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_verify.setStyleSheet(ui_theme.get_small_button_style())
        self.btn_verify.clicked.connect(self.verify_hsn_online)
        hsn_layout.addWidget(self.btn_verify)

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
            if len(part_data) > 10:
                 self.in_compat.setText(str(part_data[9]))
                 self.in_category.setText(str(part_data[10]))
            if len(part_data) > 15:
                 self.in_hsn.setText(str(part_data[15]))
                 self.in_gst.setText(str(part_data[16]))

        # Signals for Auto-Fill
        self.in_id.textChanged.connect(self.auto_fill_empty_fields) # New connection
        self.in_name.textChanged.connect(self.auto_suggest_tax_info)
        self.in_category.textChanged.connect(self.auto_suggest_tax_info)

        self.layout.addRow("Part ID:", self.in_id)
        self.layout.addRow("Name:", self.in_name)
        self.layout.addRow("Category:", self.in_category)
        self.layout.addRow("Description:", self.in_desc)
        self.layout.addRow("Compatibility:", self.in_compat)
        self.layout.addRow("Price (MRP):", self.in_price)
        self.layout.addRow("Quantity:", self.in_qty)
        self.layout.addRow("Rack:", self.in_rack)
        self.layout.addRow("Column:", self.in_col)
        self.layout.addRow("Reorder Level:", self.in_reorder)
        self.layout.addRow("Vendor Name:", self.in_vendor)
        self.layout.addRow("HSN Code:", hsn_layout)
        self.layout.addRow("GST %:", self.in_gst)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setStyleSheet(ui_theme.get_neon_action_button())
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setStyleSheet(ui_theme.get_cancel_button_style())
        
        self.layout.addRow(self.buttons)

        # Auto-fill empty fields after initial population
        QTimer.singleShot(0, self.auto_fill_empty_fields)

    def auto_fill_empty_fields(self):
        """Smart auto-fill: populate empty fields from catalog DB, supplier catalogs, and HSN rules.
        Only fills fields that are currently empty (non-destructive)."""
        part_id = self.in_id.text().strip().upper()
        part_name = self.in_name.text().strip()
        if not part_id and not part_name:
            return

        # ── 1. Catalog DB lookup → category ─────────────────────────────────
        try:
            import sqlite3, os
            s = self.db_manager.get_shop_settings() if self.db_manager else {}
            cat_db = (s or {}).get("nexses_catalog_db", "")
            from path_utils import get_resource_path  # type: ignore
            if not cat_db or not os.path.exists(cat_db):
                cat_db = get_resource_path("nexses_ecatalog.db")
            if os.path.exists(cat_db):
                conn = sqlite3.connect(cat_db, check_same_thread=False)
                cur = conn.cursor()
                cur.execute("SELECT category FROM parts_master WHERE part_code = ? LIMIT 1", (part_id,))
                row = cur.fetchone()
                if row and row[0] and not self.in_category.text().strip():
                    self.in_category.blockSignals(True)
                    self.in_category.setText(str(row[0]).strip())
                    self.in_category.blockSignals(False)
                conn.close()
        except Exception:
            pass

        # ── 2. Supplier catalogs lookup → vendor ─────────────────────────────
        try:
            if self.db_manager and not self.in_vendor.text().strip():
                conn2 = self.db_manager.get_connection()
                cur2 = conn2.cursor()
                cur2.execute(
                    "SELECT vendor_name FROM supplier_catalogs WHERE part_code = ? AND vendor_name != '' LIMIT 1",
                    (part_id,)
                )
                vrow = cur2.fetchone()
                if vrow and vrow[0]:
                    self.in_vendor.setText(str(vrow[0]).strip())
                elif part_name:
                    # Fallback: match by part name prefix
                    cur2.execute(
                        "SELECT vendor_name FROM supplier_catalogs WHERE part_name LIKE ? AND vendor_name != '' LIMIT 1",
                        (f"%{part_name[:12]}%",)
                    )
                    vrow2 = cur2.fetchone()
                    if vrow2 and vrow2[0]:
                        self.in_vendor.setText(str(vrow2[0]).strip())
                conn2.close()
        except Exception:
            pass

        # ── 3. Description fallback → use part name if empty ─────────────────
        if not self.in_desc.text().strip() and part_name and part_name not in ('None', ''):
            self.in_desc.setText(part_name)

        # ── 4. HSN / GST auto-suggest ─────────────────────────────────────────
        self.auto_suggest_tax_info()

    def auto_suggest_tax_info(self):
        """Smart Auto-Fill HSN/GST based on part name or category."""
        if not self.db_manager: return
        
        # Only suggest if fields are empty
        if self.in_hsn.text().strip() and self.in_gst.text().strip() != "18.0":
            return
            
        term = self.in_name.text().strip() or self.in_category.text().strip()
        if len(term) < 3: return
        
        rule = self.db_manager.search_hsn_rule(term)
        if rule:
            if not self.in_hsn.text().strip():
                self.in_hsn.setText(rule['hsn_code'])
            if self.in_gst.text().strip() == "18.0" or not self.in_gst.text().strip():
                self.in_gst.setText(str(rule['gst_rate']))

    def verify_hsn_online(self):
        """Web Bridge: Verify HSN on the official GST portal."""
        hsn = self.in_hsn.text().strip()
        url = "https://services.gst.gov.in/services/searchhsnsac"
        # We can't deep link directly to a search result easily without a direct query param 
        # but we can copy HSN to clipboard and open the site.
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(hsn)
        webbrowser.open(url)

    def get_data(self):
        return {
            'id': self.in_id.text(), 
            'name': self.in_name.text(), 
            'desc': self.in_desc.text(), 
            'price': float(self.in_price.text() or 0), 
            'qty': float(self.in_qty.text() or 0), 
            'rack': self.in_rack.text(), 
            'col': self.in_col.text(),
            'reorder': int(self.in_reorder.text() or 5), 
            'vendor': self.in_vendor.text(),
            'compat': self.in_compat.text(),
            'category': self.in_category.text(),
            'hsn_code': self.in_hsn.text(),
            'gst_rate': float(self.in_gst.text() or 18.0)
        }

class PurchaseOrderDialog(QDialog):
    def __init__(self, parent=None, items=None):
        super().__init__(parent)
        self.setWindowTitle("Purchase Command Center")
        self.resize(1000, 700)
        self.setStyleSheet(ui_theme.get_dialog_style())
        self.items = items or [] 
        self.selected_ids = set() # Track selected Part IDs
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        hud_layout = QHBoxLayout()
        stats_container = QFrame()
        stats_container.setStyleSheet(ui_theme.get_panel_frame_style())
        stats_layout = QHBoxLayout(stats_container)
        stats_layout.setContentsMargins(5, 5, 5, 5)
        stats_layout.setSpacing(10)
        
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
        self.btn_auto.setStyleSheet(ui_theme.get_neon_action_button())
        self.btn_auto.setFixedSize(220, DIM_BUTTON_HEIGHT)
        self.btn_auto.clicked.connect(self.auto_select_low_stock)
        controls_layout.addWidget(self.btn_auto)
        
        self.input_search = QLineEdit()
        self.input_search.setPlaceholderText("🔍 Search Part / Vendor...")
        self.input_search.setStyleSheet(ui_theme.get_lineedit_style())
        self.input_search.textChanged.connect(self.filter_table)
        controls_layout.addWidget(self.input_search)
        
        controls_layout.addWidget(QLabel("Filter Vendor:"))
        self.combo_vendor = QComboBox()
        self.combo_vendor.addItem("All Vendors")
        self.combo_vendor.setStyleSheet(ui_theme.get_lineedit_style())
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
        self.btn_generate.setStyleSheet(ui_theme.get_neon_action_button())
        self.btn_generate.setFixedSize(250, 40)
        self.btn_generate.clicked.connect(self.accept)
        
        self.btn_cancel = QPushButton("CANCEL")
        self.btn_cancel.setStyleSheet(ui_theme.get_danger_button_style())
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
            chk.setStyleSheet(ui_theme.get_table_checkbox_style())
            # Use a closure/lambda to capture the row index 'i'
            # We need to make sure i is bound correctly
            chk.stateChanged.connect(lambda state, row=i: self.on_item_checked(row, state))
            
            cw = QWidget()
            cl = QHBoxLayout(cw); cl.setContentsMargins(0,0,0,0); cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(chk)
            self.table.setCellWidget(i, 0, cw)
            
            self.table.setItem(i, 1, QTableWidgetItem(str(item[0])))
            self.table.setItem(i, 2, QTableWidgetItem(str(item[1])))
            self.table.setItem(i, 3, QTableWidgetItem(f"{float(item[4]):g}" if item[4] is not None else "0"))
            
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
            
            self.catalog_map = {}
            self.catalog_hierarchy = {}
            self.bridge_thread = CatalogBridgeThread(db_manager)
            self.bridge_thread.data_loaded.connect(self.on_catalog_bridged)
            self.bridge_thread.start()
            
            self.setup_ui()
            self.load_data()
            app_logger.info("InventoryPage Initialized Successfully.")
        except Exception as e:
            app_logger.critical(f"Failed to initialize InventoryPage: {e}", exc_info=True)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
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
        top_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        title = QLabel("📦 INVENTORY")
        title.setStyleSheet(ui_theme.get_page_title_style())
        top_row.addWidget(title)
        
        self.loading_bar = QProgressBar()
        self.loading_bar.setFixedSize(80, 4)
        self.loading_bar.setTextVisible(False)
        self.loading_bar.setStyleSheet(f"background-color: #333; chunk {{ background-color: {COLOR_ACCENT_GREEN}; }}")
        top_row.addWidget(self.loading_bar)
        
        top_row.addStretch()

        # Search Center
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔍 Search Parts / Vehicle...")
        self.search_bar.setFixedWidth(280)
        self.search_bar.setFixedHeight(36)
        # Use simple standard styling to avoid internal clipping issues
        self.search_bar.setStyleSheet(ui_theme.get_lineedit_style())
        self.search_bar.textChanged.connect(lambda: self.search_timer.start())
        
        top_row.addWidget(self.search_bar)
        
        self.filter_btn = QPushButton("🌪️ FILTER & SELECT")
        self.filter_btn.setCheckable(True)
        self.filter_btn.setChecked(False)
        self.filter_btn.setFixedSize(160, 36)
        self.filter_btn.setStyleSheet(ui_theme.get_small_button_style("cyan"))
        self.filter_btn.clicked.connect(self.toggle_filter_panel)
        top_row.addWidget(self.filter_btn)
        
        top_row.addStretch()
        
        # Operational Buttons (Require Edit Permission)
        if self.can_edit:
            self.btn_add = QPushButton("➕ NEW")
            self.btn_add.setFixedSize(90, 36)
            self.btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_add.setStyleSheet(ui_theme.get_small_button_style("green"))
            self.btn_add.clicked.connect(lambda: self.open_add_dialog())
            top_row.addWidget(self.btn_add)
            
            self.btn_purchase = QPushButton("📜 BUY")
            self.btn_purchase.setFixedSize(100, 36)
            self.btn_purchase.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_purchase.setStyleSheet(ui_theme.get_small_button_style("amber"))
            self.btn_purchase.clicked.connect(self.generate_purchase_list)
            top_row.addWidget(self.btn_purchase)
            
            # --- DROPDOWN: DATA ---
            btn_data = QPushButton("📊 DATA ▼")
            btn_data.setFixedSize(110, 36)
            btn_data.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_data.setStyleSheet(ui_theme.get_small_button_style("cyan") + " QPushButton::menu-indicator { image: none; width: 0px; }")
            
            data_menu = QMenu(self)
            data_menu.setStyleSheet("QMenu { background-color: #0b0b14; color: #00e5ff; border: 1px solid #00e5ff; border-radius: 4px; } QMenu::item:selected { background-color: rgba(0,229,255,0.2); }")
            
            act_import = data_menu.addAction("📊 IMPORT EXCEL/CSV")
            act_import.triggered.connect(self.import_data)
            self.btn_import = act_import 
            
            act_export = data_menu.addAction("📥 EXPORT INVENTORY")
            act_export.triggered.connect(self.export_to_excel)
            self.btn_export = act_export
            
            btn_data.setMenu(data_menu)
            top_row.addWidget(btn_data)
            
            # --- DROPDOWN: TOOLS ---
            btn_tools = QPushButton("🛠️ TOOLS ▼")
            btn_tools.setFixedSize(115, 36)
            btn_tools.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_tools.setStyleSheet(ui_theme.get_small_button_style("green") + " QPushButton::menu-indicator { image: none; width: 0px; }")
            
            tools_menu = QMenu(self)
            tools_menu.setStyleSheet("QMenu { background-color: #0b0b14; color: #00ff41; border: 1px solid #00ff41; border-radius: 4px; } QMenu::item:selected { background-color: rgba(0,255,65,0.2); }")
            
            act_hsn = tools_menu.addAction("⚡ HSN/GST SYNC")
            act_hsn.triggered.connect(self.open_hsn_sync)
            self.btn_hsn_sync = act_hsn

            act_compat = tools_menu.addAction("🚗 VEHICLE COMPAT")
            act_compat.triggered.connect(self.open_vehicle_compat)
            self.btn_compat = act_compat
            btn_tools.setMenu(tools_menu)
            top_row.addWidget(btn_tools)

            # Keep edit/delete as refs for use in context menu
            self.btn_edit_part  = None   # accessed via right-click
            self.btn_del_part   = None   # accessed via right-click
            
        self.btn_info_part = QPushButton("ℹ️ INFO")
        self.btn_info_part.setFixedSize(100, 36)
        self.btn_info_part.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_info_part.setStyleSheet(ui_theme.get_small_button_style("amber"))
        self.btn_info_part.clicked.connect(self.on_info_click)
        top_row.addWidget(self.btn_info_part)
        
        layout.addLayout(top_row)
        
        # --- ROW 2: Holographic HUD ---
        stats_container = QFrame()
        stats_container.setStyleSheet(ui_theme.get_panel_frame_style())
        stats_layout = QHBoxLayout(stats_container)
        stats_layout.setContentsMargins(5, 5, 5, 5)
        stats_layout.setSpacing(10)
        
        stats_layout.addWidget(self.card_val)
        stats_layout.addWidget(self.card_stock)
        stats_layout.addWidget(self.card_parts)
        stats_layout.addWidget(self.card_reorder)
        stats_layout.addWidget(self.card_vendors)
        stats_layout.addWidget(self.ai_nexus, 1) 
        
        layout.addWidget(stats_container)
        
        # --- FILTER BAR & PANEL ---


        # Collapsible Panel
        self.filter_panel = QFrame()
        self.filter_panel.setVisible(False)
        self.filter_panel.setStyleSheet(f"background-color: {COLOR_SURFACE}; border: 1px solid #333; border-radius: 8px;")
        fp_layout = QVBoxLayout(self.filter_panel)
        fp_layout.setContentsMargins(10, 10, 10, 10)
        
        fp_row1 = QHBoxLayout()
        fp_row2 = QHBoxLayout()
        
        self.combo_cat = QComboBox()
        self.combo_cat.addItem("All Categories")
        self.combo_cat.setStyleSheet(ui_theme.get_lineedit_style())
        self.combo_cat.currentTextChanged.connect(self._on_cat_changed)
        fp_row1.addWidget(QLabel("Category:"))
        fp_row1.addWidget(self.combo_cat)
        
        self.combo_model = QComboBox()
        self.combo_model.addItem("All Models")
        self.combo_model.setStyleSheet(ui_theme.get_lineedit_style())
        self.combo_model.currentTextChanged.connect(self._on_model_changed)
        fp_row1.addWidget(QLabel("Model:"))
        fp_row1.addWidget(self.combo_model)
        
        self.combo_section = QComboBox()
        self.combo_section.addItem("All Sections")
        self.combo_section.setStyleSheet(ui_theme.get_lineedit_style())
        self.combo_section.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.combo_section.setMinimumWidth(200)
        self.combo_section.currentTextChanged.connect(self.filter_table)
        fp_row1.addWidget(QLabel("Section:"))
        fp_row1.addWidget(self.combo_section)
        
        fp_row1.addStretch()
        
        self.combo_status = QComboBox()
        self.combo_status.addItems(["All Stock Status", "Low Stock", "Critical (<=3)", "Dead Stock (>50)"])
        self.combo_status.setStyleSheet(ui_theme.get_lineedit_style())
        self.combo_status.currentTextChanged.connect(self.filter_table)
        fp_row2.addWidget(QLabel("Stock:"))
        fp_row2.addWidget(self.combo_status)
        
        self.chk_new_only = QCheckBox("✨ Show ONLY Newly Added")
        self.chk_new_only.setStyleSheet(ui_theme.get_checkbox_style() + f"QCheckBox {{ color: {COLOR_ACCENT_GREEN}; font-weight: bold; }}")
        self.chk_new_only.stateChanged.connect(self.filter_table)
        fp_row2.addWidget(self.chk_new_only)
        
        self.chk_edited_only = QCheckBox("⏳ Show ONLY Edited Recently")
        self.chk_edited_only.setStyleSheet(ui_theme.get_checkbox_style() + f"QCheckBox {{ color: {COLOR_ACCENT_CYAN}; font-weight: bold; }}")
        self.chk_edited_only.stateChanged.connect(self.filter_table)
        fp_row2.addWidget(self.chk_edited_only)
        
        self.chk_missing_compat = QCheckBox("❌ Show ONLY Missing Compat")
        self.chk_missing_compat.setStyleSheet(ui_theme.get_checkbox_style() + f"QCheckBox {{ color: {COLOR_ACCENT_RED}; font-weight: bold; }}")
        self.chk_missing_compat.stateChanged.connect(self.filter_table)
        fp_row2.addWidget(self.chk_missing_compat)
        
        fp_row2.addStretch()
        
        # Selection tools
        self.btn_select_all = QPushButton("☑ SELECT ALL")
        self.btn_select_all.setStyleSheet(ui_theme.get_small_button_style())
        self.btn_select_all.clicked.connect(self.select_all_filtered)
        
        self.btn_deselect_all = QPushButton("☐ DESELECT ALL")
        self.btn_deselect_all.setStyleSheet(ui_theme.get_small_button_style("red"))
        self.btn_deselect_all.clicked.connect(self.deselect_all_filtered)
        
        fp_row1.addWidget(self.btn_select_all)
        fp_row1.addWidget(self.btn_deselect_all)
        
        fp_layout.addLayout(fp_row1)
        fp_layout.addLayout(fp_row2)
        
        layout.addWidget(self.filter_panel)

        # --- ROW 3: Table ---
        self.table = QTableWidget()
        cols = ["SEL", "PART ID", "NAME", "VENDOR", "PRICE", "QTY", "RACK", "COL"] 
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)  # QTY fills all empty space
        
        # Sensible initial widths
        self.table.setColumnWidth(0, 40)   # SEL
        self.table.setColumnWidth(1, 110)  # PART ID
        self.table.setColumnWidth(2, 280)  # NAME
        self.table.setColumnWidth(3, 65)   # VENDOR
        self.table.setColumnWidth(4, 80)   # PRICE
        # col 5 (QTY) stretches — fills all remaining space
        self.table.setColumnWidth(6, 70)   # RACK — enough for text values
        self.table.setColumnWidth(7, 65)   # COL — enough for text values like 'ARUN'
        
        # Styling
        self.table.setStyleSheet(
            STYLE_TABLE_CYBER
            + "QTableWidget { background-color: #040810; alternate-background-color: #060c16; }"
        )
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setGridStyle(Qt.PenStyle.NoPen)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setDefaultSectionSize(28)   # row height

        self.delegate = BladeDelegate(self.table)
        for c in range(self.table.columnCount()):
            self.table.setItemDelegateForColumn(c, self.delegate)

        self.delegate.selectToggled.connect(self.handle_select_toggle)
        self.delegate.infoClicked.connect(self._on_delegate_info)
        self.delegate.editClicked.connect(self._on_delegate_edit)
        self.delegate.deleteClicked.connect(self._on_delegate_delete)

        # ── Right-click context menu ──────────────────────────────────────────
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(self.table)

    def _show_context_menu(self, pos):
        """Rich right-click context menu on any inventory row."""
        row = self.table.rowAt(pos.y())
        if row < 0:
            return

        # Make sure the row is selected
        self.table.selectRow(row)

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #0b0b14;
                color: #e0e0e0;
                border: 1px solid #223;
                border-radius: 6px;
                padding: 4px 0;
                font-family: 'Segoe UI';
                font-size: 12px;
            }
            QMenu::item {
                padding: 7px 20px 7px 14px;
                border-radius: 4px;
            }
            QMenu::item:selected  { background: rgba(0,229,255,0.15); color: #00e5ff; }
            QMenu::item:disabled  { color: #555; }
            QMenu::separator      { height: 1px; background: #223; margin: 4px 10px; }
        """)

        # Get part ID from selected row for display
        part_id_item = self.table.item(row, 1)
        part_id = part_id_item.text() if part_id_item else ""
        part_name_item = self.table.item(row, 2)
        part_name = (part_name_item.text()[:28] + "…") if part_name_item and len(part_name_item.text()) > 28 else (part_name_item.text() if part_name_item else "")

        # Header label (non-selectable)
        hdr = menu.addAction(f"  {part_id}  {part_name}")
        hdr.setEnabled(False)
        menu.addSeparator()

        act_info = menu.addAction("ℹ️  View Info")
        act_info.triggered.connect(self.on_info_click)

        if self.can_edit:
            act_edit = menu.addAction("✏️  Edit Part")
            act_edit.triggered.connect(self.on_edit_click)

            menu.addSeparator()

            act_copy = menu.addAction("📋  Copy Part ID")
            act_copy.triggered.connect(lambda: QApplication.clipboard().setText(part_id))

            menu.addSeparator()

            act_del = menu.addAction("🗑️  Delete Part")
            act_del.triggered.connect(self.on_delete_click)
        else:
            act_copy = menu.addAction("📋  Copy Part ID")
            act_copy.triggered.connect(lambda: QApplication.clipboard().setText(part_id))

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def toggle_filter_panel(self):
        is_visible = self.filter_btn.isChecked()
        self.filter_panel.setVisible(is_visible)

    def open_add_dialog(self, part_data=None):
        try:
            is_edit = part_data is not None
            dialog = AddPartDialog(self, self.db_manager, part_data)
            if dialog.exec():
                data = dialog.get_data()

                if is_edit:
                    # Edit mode: update directly
                    success, msg, _ = self.db_manager.add_part(data, allow_update=True)
                    if success:
                        ProMessageBox.information(self, "Updated", "Part updated successfully.")
                        self._fast_update_row(data['id'])
                    else:
                        ProMessageBox.critical(self, "Error", f"Failed to update part.\n{msg}")
                else:
                    # Add mode: check for duplicates
                    success, msg, is_duplicate = self.db_manager.add_part(data)

                    if is_duplicate:
                        update_msg = f"{msg}\n\nDo you want to UPDATE the existing part?"
                        if ProMessageBox.question(self, "⚠️ DUPLICATE DETECTED", update_msg):
                            success, msg, _ = self.db_manager.add_part(data, allow_update=True)
                            if success:
                                ProMessageBox.information(self, "Updated", "Part updated successfully.")
                                self._fast_update_row(data['id'])
                            else:
                                ProMessageBox.critical(self, "Error", f"Failed to update part.\n{msg}")
                    elif success:
                        ProMessageBox.information(self, "Success", "Part added successfully.")
                        self.load_data()  # acceptable for brand new parts
                    else:
                        ProMessageBox.critical(self, "Error", f"Failed to save part.\n{msg}")
        except Exception as e:
            app_logger.error(f"Error opening add dialog: {e}")
            ProMessageBox.critical(self, "Error", f"An error occurred: {e}")

    def _fast_update_row(self, part_id):
        """Optimized targeted UI update to prevent full reload lag when saving edits."""
        try:
            from datetime import datetime
            import sys, os
            updated_tuple = self.db_manager.get_part_by_id(part_id)
            if not updated_tuple:
                self.load_data()
                return
            
            # Enrich compat
            pid_upper = str(part_id).strip().upper()
            try:
                s = self.db_manager.get_shop_settings() or {}
                cat_db = s.get("nexses_catalog_db", "")
                if not cat_db or not os.path.exists(cat_db):
                    from path_utils import get_resource_path
                    cat_db = get_resource_path("nexses_ecatalog.db")
                cat_tags = []
                if os.path.exists(cat_db):
                    import sqlite3
                    conn = sqlite3.connect(cat_db, check_same_thread=False)
                    c = conn.cursor()
                    c.execute('''SELECT vm.model_name || CASE WHEN vm.variant != '' THEN ' ' || vm.variant ELSE '' END AS lbl
                                 FROM compatibility_map cm
                                 JOIN vehicles_master vm ON vm.vehicle_id = cm.vehicle_id
                                 WHERE cm.part_code = ?''', (pid_upper,))
                    for row in c.fetchall():
                        lbl = str(row[0]).strip()
                        if lbl and lbl not in ('*', '**', '***', '****', '*****'):
                            if lbl not in cat_tags: cat_tags.append(lbl)
                    conn.close()
            except Exception as e:
                cat_tags = []
                
            existing_compat = str(updated_tuple[9] or '').strip()
            merged_tags = ', '.join(cat_tags) if cat_tags else existing_compat
            
            # Rebuild tuple
            r_list = list(updated_tuple)
            while len(r_list) <= 9: r_list.append('')
            r_list[9] = merged_tags
            new_r = tuple(r_list)
            
            # Update all_rows map
            for idx, r in enumerate(self.all_rows):
                if str(r[0]) == str(part_id):
                    self.all_rows[idx] = new_r
                    break
                    
            # Update UI row if exists
            row_idx = -1
            for i, mapped_row in self.rows_map.items():
                if str(mapped_row[0]) == str(part_id):
                    row_idx = i
                    break
                    
            if row_idx >= 0:
                self.table.setUpdatesEnabled(False)
                # Apply new_r to this row using the same logic as populate_table
                r = new_r
                qty = float(r[4] or 0)
                reorder_level = int(r[7] or 5) if len(r) > 7 else 5
                is_low_stock = qty <= reorder_level
                
                is_checked = str(r[0]) in self.selected_part_ids
                self.table.setItem(row_idx, 0, self._create_item("", 'select', {'checked': is_checked}))
                self.table.setItem(row_idx, 1, self._create_item(r[0], 'id', {'is_low_stock': is_low_stock}))
                
                item2 = self._create_item(r[1], 'name', {
                    'is_low_stock': is_low_stock, 
                    'is_new': False,
                    'is_edited': True
                })
                if len(r) > 9 and r[9]:
                    tags = [t.strip() for t in str(r[9]).split(',') if t.strip()]
                    d = item2.data(Qt.ItemDataRole.UserRole)
                    if d:
                         d['vehicle_tags'] = tags
                         item2.setData(Qt.ItemDataRole.UserRole, d)
                    item2.setToolTip("Compatibility:\n" + "\n".join(f"• {t}" for t in tags))
                self.table.setItem(row_idx, 2, item2)
                
                vendor_name = r[8] if len(r) > 8 else ""
                self.table.setItem(row_idx, 3, self._create_item(vendor_name, 'vendor'))
                self.table.setItem(row_idx, 4, self._create_item(r[3], 'price'))
                
                max_val = max(reorder_level * 2, 10)
                self.table.setItem(row_idx, 5, self._create_item("", 'stock', {'val': qty, 'max_val': max_val}))
                self.table.setItem(row_idx, 6, self._create_item(r[5], 'generic'))
                self.table.setItem(row_idx, 7, self._create_item(r[6], 'generic'))
                
                self.rows_map[row_idx] = r
                self.table.setUpdatesEnabled(True)
                self.table.viewport().update()
                self.update_dashboard()
            else:
                self.load_data()
        except Exception as e:
            app_logger.error(f"Fast update error: {e}")
            self.load_data()

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
            
            cols = [
                "Part ID", "Name", "Description", "MRP (Unit Price)", "Stock Qty", 
                "Rack", "Column", "Reorder Level", "Vendor", "Compatibility", 
                "Category", "Added Date", "Last Ordered", "Added By", 
                "Last Edited", "HSN Code", "GST Rate %", "Last Cost"
            ]
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
            
            # Note: Catalog Hierarchy is handled by CatalogBridgeThread
            
            # Stats (Check existence first)
            total_val = 0
            low_stock_count = 0
            vendors = set()
            
            for r in rows:
                price = float(r[3] or 0)
                qty = float(r[4] or 0)
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
            qty = float(r[4] or 0)
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

    def _on_delegate_info(self, row):
        """Called when INFO button inside a table cell is clicked."""
        self.table.selectRow(row)
        self.on_info_click()

    def _on_delegate_edit(self, row):
        """Called when EDIT button inside a table cell is clicked."""
        self.table.selectRow(row)
        self.on_edit_click()

    def _on_delegate_delete(self, row):
        """Called when DELETE button inside a table cell is clicked."""
        self.table.selectRow(row)
        self.on_delete_click()

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


    def on_catalog_bridged(self, mapping, categories, hierarchy):
        self.catalog_map = mapping
        self.catalog_hierarchy = hierarchy
        
        self.combo_cat.blockSignals(True)
        self.combo_cat.clear()
        self.combo_cat.addItem("All Categories")
        self.combo_cat.addItems(sorted(list(categories)))
        self.combo_cat.blockSignals(False)
        self._on_cat_changed("All Categories")
        
    def _on_cat_changed(self, cat_name):
        self.combo_model.blockSignals(True)
        self.combo_model.clear()
        self.combo_model.addItem("All Models")
        if cat_name in self.catalog_hierarchy:
            models = sorted(list(self.catalog_hierarchy[cat_name].keys()))
            self.combo_model.addItems(models)
        self.combo_model.blockSignals(False)
        self._on_model_changed("All Models")
        self.filter_table()

    def _on_model_changed(self, model_name):
        self.combo_section.blockSignals(True)
        self.combo_section.clear()
        self.combo_section.addItem("All Sections")
        
        cat_name = self.combo_cat.currentText()
        if cat_name in self.catalog_hierarchy and model_name in self.catalog_hierarchy[cat_name]:
            sections = sorted(list(self.catalog_hierarchy[cat_name][model_name]))
            self.combo_section.addItems(sections)
            
        self.combo_section.blockSignals(False)
        self.filter_table()

    def filter_table(self):
        # Advanced Filtering Logic
        global_search = self.search_bar.text().lower()
        
        # New Panel Filters
        status_filter = self.combo_status.currentText()
        cat_filter = self.combo_cat.currentText()
        mod_filter = self.combo_model.currentText()
        sec_filter = self.combo_section.currentText()
        new_only = self.chk_new_only.isChecked()
        edited_only = self.chk_edited_only.isChecked()
        missing_compat = self.chk_missing_compat.isChecked()
        
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
            compat_val = str(r[9]).lower() if len(r)>9 and r[9] else ""
            
            if global_search:
                if (global_search not in id_val) and (global_search not in name_val) and (global_search not in vendor_val) and (global_search not in desc_val) and (global_search not in compat_val):
                    continue

            # 2. Status Filter
            qty = float(r[4] or 0)
            reorder = int(r[7] or 5) if len(r) > 7 else 5
            
            if status_filter == "Low Stock":
                if qty > reorder: continue
            elif status_filter == "Critical (<=3)":
                if qty > 3: continue
            elif status_filter == "Dead Stock (>50)":
                if qty <= 50: continue
                
            # 3. Catalog Hierarchy Filter
            if cat_filter != "All Categories" or mod_filter != "All Models" or sec_filter != "All Sections":
                part_id = str(r[0]).strip().upper()
                mapped_data = self.catalog_map.get(part_id, [])
                
                matched = False
                for (m_cat, m_mod, m_sec) in mapped_data:
                    c_match = (cat_filter == "All Categories" or m_cat == cat_filter)
                    m_match = (mod_filter == "All Models" or m_mod == mod_filter)
                    s_match = (sec_filter == "All Sections" or m_sec == sec_filter)
                    if c_match and m_match and s_match:
                        matched = True
                        break
                
                if not matched:
                    continue
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
                ordered_date_str = r[12] if len(r) > 12 else ""
                
                is_edited = False
                for d_str in (edited_date_str, ordered_date_str):
                    if d_str:
                        try:
                            d_obj = datetime.strptime(str(d_str)[:16], "%Y-%m-%d %H:%M")
                            if (today - d_obj).total_seconds() <= 86400: # 24h
                                is_edited = True
                                break
                        except: pass
                if not is_edited: continue

            # 6. Missing Compatibility Filter
            if missing_compat:
                c_val = str(r[9]).strip() if len(r) > 9 and r[9] else ""
                if c_val and c_val.lower() not in ("none", "-", "n/a"):
                    continue

            # 7. Removed Column Filter Logic
            
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

            
            qty = float(r[4] or 0)
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
            edited_date_str = r[14] if len(r) > 14 else "" # last_edited_date
            ordered_date_str = r[12] if len(r) > 12 else "" # last_ordered_date
            for d_str in (edited_date_str, ordered_date_str):
                if d_str:
                    try:
                        d_obj = datetime.strptime(str(d_str)[:16], "%Y-%m-%d %H:%M")
                        if (today - d_obj).total_seconds() <= 86400: # 24h
                            is_edited = True
                            break
                    except: pass

            # 1: ID
            self.table.setItem(i, 1, self._create_item(r[0], 'id', {'is_low_stock': is_low_stock}))
            
            # 2: Name (With Vehicle Tags from compatibility field)
            item2 = self._create_item(r[1], 'name', {
                'is_low_stock': is_low_stock, 
                'is_new': is_new,
                'is_edited': is_edited
            })
            # Add Vehicle Tags from compatibility column (index 9)
            if len(r) > 9 and r[9]:
                tags = [t.strip() for t in str(r[9]).split(',') if t.strip()]
                data = item2.data(Qt.ItemDataRole.UserRole)
                data['vehicle_tags'] = tags
                item2.setData(Qt.ItemDataRole.UserRole, data)
                item2.setToolTip("Compatibility:\n" + "\n".join(f"• {t}" for t in tags))
            self.table.setItem(i, 2, item2)
            
            # 3: Vendor
            vendor_name = r[8] if len(r) > 8 else ""
            self.table.setItem(i, 3, self._create_item(vendor_name, 'vendor'))

            # 4: Price
            self.table.setItem(i, 4, self._create_item(r[3], 'price'))
            
            # 5: Qty
            max_val = max(reorder_level * 2, 10)
            item5 = self._create_item("", 'stock', {'val': qty, 'max_val': max_val})
            self.table.setItem(i, 5, item5)
            
            # 6: Rack
            self.table.setItem(i, 6, self._create_item(r[5], 'generic'))
            
            # 7: Col
            self.table.setItem(i, 7, self._create_item(r[6], 'generic'))

        self.table.blockSignals(False)
        self.table.setUpdatesEnabled(True)
        
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
                qty = float(r[4] or 0)
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
                # Same format as before plus price, hsn, gst
                # ID, Name, Stock, Reorder, Vendor, Price, HSN, GST
                reorder = r[7] if len(r) > 7 else 5
                vendor = r[8] if len(r) > 8 else ""
                
                unit_price = float(r[3]) if len(r) > 3 and r[3] else 0.0
                last_cost  = float(r[17]) if len(r) > 17 and r[17] else 0.0
                price = unit_price if unit_price > 0 else last_cost
                
                hsn = r[15] if len(r) > 15 and r[15] else '8714'
                gst = float(r[16]) if len(r) > 16 and r[16] else 18.0
                
                selected.append([r[0], r[1], r[4], reorder, vendor, price, hsn, gst])
        
        return selected


    def show_part_info(self, row_data):
        """Open the full Part Tracker for this part."""
        try:
            from part_tracker_dialog import PartTrackerDialog
            dlg = PartTrackerDialog(self.db_manager, row_data, parent=self)
            dlg.exec()
        except Exception as e:
            app_logger.error(f"Error opening Part Tracker: {e}")
            from custom_components import ProMessageBox
            ProMessageBox.critical(self, "Error", f"Could not open Part Tracker:\n{e}")



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



    # ─── HSN Sync ──────────────────────────────────────────────────
    def open_hsn_sync(self):
        try:
            from hsn_sync_engine import HsnSyncDialog
            dlg = HsnSyncDialog(self, self.db_manager)
            dlg.sync_completed.connect(self._on_hsn_sync_done)
            dlg.exec()
        except Exception as e:
            app_logger.error(f'Failed to open HSN Sync: {e}')
            ProMessageBox.critical(self, 'Error', f'Could not open HSN Sync:\n{e}')

    def _on_hsn_sync_done(self, count: int):
        self.load_data()
        ProMessageBox.information(self, '✅ HSN Sync Complete',
            f'Successfully synced HSN & GST for {count} part(s).')

    # ─── Vehicle Compat ─────────────────────────────────────────────
    def open_vehicle_compat(self):
        try:
            from vehicle_compat_engine import VehicleCompatDialog
            dlg = VehicleCompatDialog(self, self.db_manager)
            dlg.sync_completed.connect(self._on_compat_done)
            dlg.exec()
        except Exception as e:
            app_logger.error(f'Failed to open Vehicle Compat: {e}')
            ProMessageBox.critical(self, 'Error', f'Could not open Vehicle Compat:\n{e}')

    def _on_compat_done(self, count: int):
        self.load_data()
        ProMessageBox.information(self, '🚗 Compatibility Updated',
            f'Vehicle compatibility filled for {count} part(s).')

