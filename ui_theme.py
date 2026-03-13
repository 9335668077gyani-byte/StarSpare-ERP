import os

# ==========================================
# GLOBAL ERP UI THEME CONFIGURATION
# ==========================================
# Objective: Modern Soft 3D, Minimalistic & Premium Design
# Focuses on elegant depth, gradients, and clean typography.

# --- TYPOGRAPHY ---
FONT_PRIMARY = "'Orbitron', 'Rajdhani', 'Segoe UI', sans-serif"
FONT_SIZE_BASE = "13px"
FONT_WEIGHT_NORMAL = "400"
FONT_WEIGHT_MEDIUM = "600"  # Refined for cyber tech

# --- COLOR PALETTE ---
COLOR_BG = "#010206"       # Hyper depth void
COLOR_SURFACE = "#03060c"   # Floating glass surfaces
COLOR_ACCENT_CYAN = "#00f2ff"
COLOR_ACCENT_GREEN = "#00ff88"
COLOR_ACCENT_RED = "#ff0044"
COLOR_ACCENT_AMBER = "#ffaa00"

COLOR_TEXT_PRIMARY = "#E2E8F0"   # Crisp bright white
COLOR_TEXT_MUTED = "#64748B"     # Muted grey for cosmic depth

# --- ACTION BUTTON DEFINITIONS (Modern Soft 3D) ---

def get_primary_button_style():
    """Soft 3D Emerald/Green gradient for positive actions (+NEW, SAVE)"""
    return f"""
        QPushButton {{
            background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #10B981, stop:1 #059669);
            color: #ffffff;
            border-bottom: 3px solid #065F46; /* Depth */
            border-radius: 6px;
            padding: 4px 12px;
            font-family: {FONT_PRIMARY};
            font-size: {FONT_SIZE_BASE};
            font-size: {FONT_SIZE_BASE};
            font-weight: {FONT_WEIGHT_MEDIUM};
        }}
        QPushButton:hover {{
            background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #34D399, stop:1 #10B981);
            border-bottom: 3px solid #047857;
        }}
        QPushButton:pressed {{
            background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #059669, stop:1 #047857);
            border-bottom: 1px solid #065F46; /* Pressed effect */
            margin-top: 2px; /* Visual shift down */
        }}
    """

def get_danger_button_style():
    """Soft 3D Crimson/Red gradient for destructive actions (DEL, REMOVE)"""
    return f"""
        QPushButton {{
            background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #EF4444, stop:1 #DC2626);
            color: #ffffff;
            border-bottom: 3px solid #991B1B; /* Depth */
            border-radius: 6px;
            padding: 4px 12px;
            font-family: {FONT_PRIMARY};
            font-size: {FONT_SIZE_BASE};
            font-size: {FONT_SIZE_BASE};
            font-weight: {FONT_WEIGHT_MEDIUM};
        }}
        QPushButton:hover {{
            background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #F87171, stop:1 #EF4444);
            border-bottom: 3px solid #B91C1C;
        }}
        QPushButton:pressed {{
            background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #DC2626, stop:1 #B91C1C);
            border-bottom: 1px solid #991B1B; /* Pressed effect */
            margin-top: 2px;
        }}
    """

def get_ghost_button_style(icon_color="#ffffff"):
    """Premium Dark Grey/Blueish-Grey 3D gradient for Secondary actions (PDF, EXCEL, INFO)"""
    return f"""
        QPushButton {{
            background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #334155, stop:1 #1E293B);
            color: {icon_color};
            border: 1px solid #0F172A;
            border-top: 1px solid #475569; /* Soft highlight */
            border-bottom: 3px solid #0F172A; /* Depth */
            border-radius: 6px;
            padding: 4px 12px;
            font-family: {FONT_PRIMARY};
            font-size: {FONT_SIZE_BASE};
            font-size: {FONT_SIZE_BASE};
            font-weight: {FONT_WEIGHT_MEDIUM};
        }}
        QPushButton:hover {{
            background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #475569, stop:1 #334155);
            border-bottom: 3px solid #0F172A;
        }}
        QPushButton:pressed {{
            background-color: #0F172A;
            border: 1px solid #020617;
            border-bottom: 1px solid #020617; /* Pressed effect */
            margin-top: 2px;
        }}
    """

def get_table_style():
    """Modern enterprise table style"""
    return f"""
        QTableWidget {{
            background-color: {COLOR_SURFACE};
            alternate-background-color: #161A24;
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid #1E293B;
            border-radius: 8px;
            font-family: {FONT_PRIMARY};
            font-size: {FONT_SIZE_BASE};
            gridline-color: #1E293B;
            outline: none;
            selection-background-color: transparent;
            selection-color: {COLOR_TEXT_PRIMARY};
        }}
        QHeaderView::section {{
            background-color: {COLOR_BG};
            color: {COLOR_ACCENT_CYAN};
            padding: 6px 8px;
            border: none;
            border-bottom: 1px solid #334155;
            font-family: {FONT_PRIMARY};
            font-weight: {FONT_WEIGHT_MEDIUM}; 
            text-transform: uppercase;
            font-size: 10px;
            letter-spacing: 0.5px;
        }}
        QTableWidget::item {{
            padding: 10px 16px;
            border-bottom: 1px solid #1E293B;
        }}
        QTableWidget::item:selected {{
            background-color: transparent; 
        }}
        QTableCornerButton::section {{
            background-color: #0B0E14; 
            border: none; 
        }}
        /* Scrollbar styling to match sleek dark theme */
        QScrollBar:vertical {{
            border: none;
            background: {COLOR_BG};
            width: 10px;
            margin: 0px 0px 0px 0px;
        }}
        QScrollBar::handle:vertical {{
            background: #334155;
            min-height: 20px;
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: #475569;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar:horizontal {{
            border: none;
            background: {COLOR_BG};
            height: 10px;
            margin: 0px 0px 0px 0px;
        }}
        QScrollBar::handle:horizontal {{
            background: #334155;
            min-width: 20px;
            border-radius: 4px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: #475569;
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}
    """

def get_lineedit_style():
    """Modern input style with focus highlight"""
    return f"""
        QLineEdit {{
            background-color: {COLOR_BG};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid #1E293B;
            border-radius: 6px;
            padding: 8px 12px;
            font-family: {FONT_PRIMARY};
            font-size: 13px;
        }}
        QLineEdit:focus {{
            border: 1px solid {COLOR_ACCENT_CYAN};
            background-color: {COLOR_SURFACE};
        }}
        QLineEdit:disabled {{
            background-color: #0B0E14;
            color: {COLOR_TEXT_MUTED};
            border: 1px solid #1a1a2e;
        }}
    """

def get_combobox_style():
    """Modern dropdown style"""
    return f"""
        QComboBox {{
            background-color: {COLOR_BG};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid #1E293B;
            border-radius: 6px;
            padding: 8px 12px;
            font-family: {FONT_PRIMARY};
            font-size: 13px;
        }}
        QComboBox:hover {{
            border: 1px solid #334155;
        }}
        QComboBox:focus {{
            border: 1px solid {COLOR_ACCENT_CYAN};
        }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 25px;
            border-left-width: 0px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {COLOR_SURFACE};
            color: {COLOR_TEXT_PRIMARY};
            selection-background-color: #1E293B;
            selection-color: {COLOR_ACCENT_CYAN};
            border: 1px solid #1E293B;
            border-radius: 4px;
            outline: none;
        }}
    """

def get_checkbox_style():
    """Modern checkbox styling"""
    return f"""
        QCheckBox {{
            color: {COLOR_TEXT_PRIMARY};
            font-family: {FONT_PRIMARY};
            font-size: 13px;
            spacing: 8px;
        }}
        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border-radius: 4px;
            border: 1px solid #1E293B;
            background: {COLOR_BG};
        }}
        QCheckBox::indicator:hover {{
            border: 1px solid {COLOR_ACCENT_CYAN};
        }}
        QCheckBox::indicator:checked {{
            background-color: {COLOR_ACCENT_CYAN};
            border: 1px solid {COLOR_ACCENT_CYAN};
            image: url(icons/check_dark.png); /* Using standard fallback check style */
        }}
        QCheckBox:disabled {{
            color: {COLOR_TEXT_MUTED};
        }}
    """

def get_dateedit_style():
    """Modern date picker style"""
    return f"""
        QDateEdit, QDateTimeEdit {{
            background-color: {COLOR_BG};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid #1E293B;
            border-radius: 6px;
            padding: 6px 10px;
            font-family: {FONT_PRIMARY};
            font-size: 13px;
        }}
        QDateEdit:hover, QDateTimeEdit:hover {{
            border: 1px solid #334155;
        }}
        QDateEdit:focus, QDateTimeEdit:focus {{
            border: 1px solid {COLOR_ACCENT_CYAN};
            background-color: {COLOR_SURFACE};
        }}
        QDateEdit::drop-down, QDateTimeEdit::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 25px;
            border-left-width: 0px;
        }}
        QDateEdit::down-arrow, QDateTimeEdit::down-arrow {{
            image: none; /* Can add a custom caret icon here if desired */
        }}
        QCalendarWidget QWidget {{
            alternate-background-color: #161A24;
        }}
        QCalendarWidget QToolButton {{
            color: {COLOR_TEXT_PRIMARY};
            background-color: {COLOR_BG};
            border: none;
            border-radius: 4px;
            padding: 4px;
        }}
        QCalendarWidget QToolButton:hover {{
            background-color: #334155;
        }}
        QCalendarWidget QMenu {{
            background-color: {COLOR_SURFACE};
            color: {COLOR_TEXT_PRIMARY};
        }}
        QCalendarWidget QSpinBox {{
            background-color: {COLOR_BG};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid #1E293B;
            border-radius: 4px;
        }}
        QCalendarWidget QAbstractItemView:enabled {{
            background-color: {COLOR_SURFACE};
            color: {COLOR_TEXT_PRIMARY};
            selection-background-color: {COLOR_ACCENT_CYAN};
            selection-color: #000000;
        }}
        QCalendarWidget QAbstractItemView:disabled {{
            color: #475569;
        }}
    """

def get_menu_style():
    """Modern context menu/dropdown menu style"""
    return f"""
        QMenu {{
            background-color: {COLOR_SURFACE};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid #1E293B;
            border-radius: 8px;
            padding: 4px;
        }}
        QMenu::item {{
            padding: 8px 30px 8px 10px;
            border-radius: 4px;
            margin: 2px 4px;
        }}
        QMenu::item:selected {{
            background-color: #1E293B;
            color: {COLOR_ACCENT_CYAN};
        }}
        QMenu::separator {{
            height: 1px;
            background: #1E293B;
            margin: 4px 8px;
        }}
    """
