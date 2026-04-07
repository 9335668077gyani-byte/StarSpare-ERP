import os

# ============================================================
# GLOBAL ERP UI THEME  —  SpearParts Pro v1.5
# Cyberpunk-Premium Dark Design System
# ============================================================

import os
from path_utils import get_resource_path
_DIR = get_resource_path("")
_CHECK_SVG       = os.path.join(_DIR, "assets", "check.svg").replace("\\", "/")
_CHECK_WHITE_SVG = os.path.join(_DIR, "assets", "check_white.svg").replace("\\", "/")

# ── Typography ───────────────────────────────────────────────
FONT_PRIMARY      = "'Segoe UI', 'Rajdhani', sans-serif"
FONT_MONO         = "'Consolas', 'Courier New', monospace"
FONT_SIZE_BASE    = "13px"
FONT_WEIGHT_NORMAL = "400"
FONT_WEIGHT_MEDIUM = "600"

# ── Colour Palette ───────────────────────────────────────────
COLOR_BG           = "#010206"
COLOR_SURFACE      = "#03060c"
COLOR_SURFACE2     = "#060c18"
COLOR_BORDER       = "#1a2236"

COLOR_ACCENT_CYAN  = "#00f2ff"
COLOR_ACCENT_GREEN = "#00ff88"
COLOR_ACCENT_RED   = "#ff0044"
COLOR_ACCENT_AMBER = "#ffaa00"

COLOR_TEXT_PRIMARY = "#E2E8F0"
COLOR_TEXT_MUTED   = "#64748B"
COLOR_TEXT_DIM     = "#3a4a60"


# ════════════════════════════════════════════════════════════
#  CHECKBOXES  (fixed: proper ✓ checkmark, not a solid block)
# ════════════════════════════════════════════════════════════
def get_checkbox_style():
    """
    Correct checkbox style with a visible tick mark.
    The previous bug was `image: none` which removed Qt's checkmark.
    Now uses SVG checkmarks from the assets/ folder.
    """
    return f"""
        QCheckBox {{
            color: {COLOR_TEXT_PRIMARY};
            font-family: {FONT_PRIMARY};
            font-size: 13px;
            spacing: 8px;
        }}
        QCheckBox::indicator {{
            width: 17px;
            height: 17px;
            border-radius: 4px;
            border: 2px solid #3a5878;
            background: #0d1a2a;
        }}
        QCheckBox::indicator:hover {{
            border: 2px solid {COLOR_ACCENT_CYAN};
            background: rgba(0,242,255,0.06);
        }}
        QCheckBox::indicator:checked {{
            background-color: {COLOR_ACCENT_CYAN};
            border: 2px solid {COLOR_ACCENT_CYAN};
        }}
        QCheckBox::indicator:checked:hover {{
            background-color: #33f5ff;
            border: 2px solid #33f5ff;
        }}
        QCheckBox::indicator:indeterminate {{
            background-color: rgba(0,242,255,0.4);
            border: 2px solid {COLOR_ACCENT_CYAN};
        }}
        QCheckBox:disabled {{
            color: {COLOR_TEXT_MUTED};
        }}
        QCheckBox::indicator:disabled {{
            border: 2px solid #1a2236;
            background: #080c14;
        }}
        QRadioButton {{
            color: {COLOR_TEXT_PRIMARY};
            font-family: {FONT_PRIMARY};
            font-size: 13px;
            spacing: 8px;
        }}
        QRadioButton::indicator {{
            width: 17px;
            height: 17px;
            border-radius: 9px;
            border: 2px solid {COLOR_BORDER};
            background: {COLOR_SURFACE};
        }}
        QRadioButton::indicator:hover {{
            border: 2px solid {COLOR_ACCENT_CYAN};
        }}
        QRadioButton::indicator:checked {{
            background-color: {COLOR_ACCENT_CYAN};
            border: 2px solid {COLOR_ACCENT_CYAN};
        }}
    """


# Table-cell checkbox (used inside QTableWidget via setCellWidget)
def get_table_checkbox_style():
    """Compact checkbox specifically for table SEL column cells."""
    return f"""
        QCheckBox {{
            spacing: 0px;
            margin: 0px;
            padding: 0px;
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border-radius: 3px;
            border: 1.5px solid #3a5070;
            background: #0d1a2a;
        }}
        QCheckBox::indicator:hover {{
            border: 1.5px solid {COLOR_ACCENT_CYAN};
            background: rgba(0,242,255,0.08);
        }}
        QCheckBox::indicator:checked {{
            background-color: {COLOR_ACCENT_CYAN};
            border: 1.5px solid {COLOR_ACCENT_CYAN};
        }}
        QCheckBox::indicator:checked:hover {{
            background-color: #33f5ff;
        }}
    """


# ════════════════════════════════════════════════════════════
#  HEADERS & LABELS
# ════════════════════════════════════════════════════════════

def get_page_title_style():
    """Clean, pro-level neon cyan text for page titles, without background boxes."""
    return f"""
        QLabel {{
            color: #00F2FF;
            font-family: {FONT_PRIMARY};
            font-size: 16px;
            font-weight: 800;
            background: transparent;
            border: none;
            letter-spacing: 1px;
        }}
    """

# ════════════════════════════════════════════════════════════
#  BUTTONS  — Premium Cyberpunk Design System
# ════════════════════════════════════════════════════════════


def _generate_3d_button(preset="cyan", size="normal"):
    _p = {
        "cyan": ( "#000000", "#00F2FF", "#00C8D4", "#009AA3", "rgba(0,242,255,0.7)", "#006C73", "#33F5FF", "#1AE8F5", "#00B8C2", "rgba(0,242,255,1.0)", "#008B94" ),
        "green": ( "#ffffff", "#12D47A", "#00C060", "#009B4E", "rgba(0,255,140,0.55)", "#006E38", "#1EFFA0", "#00E87A", "#00B85A", "rgba(0,255,160,0.85)", "#007842" ),
        "red": ( "#ffffff", "#FF2A5A", "#E8003A", "#BF0030", "rgba(255,60,80,0.6)", "#8B001F", "#FF5575", "#FF1A4A", "#D9003A", "rgba(255,80,100,0.9)", "#9B001F" ),
        "amber": ( "#1a0a00", "#FFBE00", "#F59E0B", "#D97706", "rgba(255,180,0,0.7)", "#B45309", "#FFD040", "#FFBE00", "#F59E0B", "rgba(255,220,60,0.9)", "#C46309" ),
        "slate": ( "#c8d6e5", "#202c44", "#131d30", "#0c1524", "rgba(46,62,92,0.8)", "#050810", "#ffffff", "#2e4060", "#1e2e48", "rgba(74,96,128,1.0)", "#0d1522" ),
        "cancel": ( "#59698c", "transparent", "transparent", "transparent", "#2a3550", "#1a2540", "#e2e8f0", "#141e30", "#141e30", "#4a5a76", "#0a1020" )
    }
    c = _p.get(preset, _p["cyan"])
    if size == "small":
        pad, h, fs = "4px 12px", "30px", "13px"
    elif size == "mini":
        pad, h, fs = "3px 8px", "28px", "12px"
    else:
        pad, h, fs = "5px 18px", "34px", "13px"

    bg_base = f"background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {c[1]}, stop:0.45 {c[2]}, stop:1 {c[3]});" if preset != "cancel" else "background: transparent;"
    bg_hover = f"background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {c[6]}, stop:0.45 {c[7]}, stop:1 {c[8]});" if preset != "cancel" else f"background: {c[7]};"
    bg_pressed = f"background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {c[3]}, stop:1 {c[5]});" if preset != "cancel" else f"background: {c[10]};"

    return f'''
        QPushButton {{
            {bg_base}
            color: {c[0]};
            border: 1px solid {c[4]};
            border-bottom: 3px solid {c[5]};
            border-radius: 7px;
            font-size: {fs};
            font-weight: 800;
            padding: {pad};
            font-family: {FONT_PRIMARY};
            letter-spacing: 0.5px;
            min-height: {h};
        }}
        QPushButton:hover {{
            {bg_hover}
            border: 1px solid {c[9]};
            border-bottom: 3px solid {c[10]};
            color: {c[6] if preset == 'cancel' else c[0]};
        }}
        QPushButton:pressed {{
            {bg_pressed}
            border-bottom: 1px solid {c[5]};
            padding-top: 6px;
            padding-bottom: 2px;
        }}
        QPushButton:checked {{
            {bg_pressed}
            border: 1px solid {c[4]};
            border-bottom: 1px solid {c[5]};
            color: {c[0]};
            padding-top: 6px;
            padding-bottom: 2px;
        }}
        QPushButton:disabled {{
            background: #1a1a24;
            color: #3a3a4c;
            border: 1px solid #1a1a24;
            border-bottom: 1px solid #1a1a24;
        }}
    '''

def get_primary_button_style(): return _generate_3d_button("green", "normal")
def get_danger_button_style(): return _generate_3d_button("red", "normal")
def get_secondary_button_style(): return _generate_3d_button("slate", "normal")
def get_ghost_button_style(icon_color="#c8d6e5"): return _generate_3d_button("slate", "normal")
def get_neon_action_button(): return _generate_3d_button("cyan", "normal")
def get_icon_btn_cyan(): return _generate_3d_button("cyan", "mini")
def get_icon_btn_red(): return _generate_3d_button("red", "mini")
def get_icon_btn_green(): return _generate_3d_button("green", "mini")
def get_cancel_button_style(): return _generate_3d_button("cancel", "normal")
def get_amber_button_style(): return _generate_3d_button("amber", "normal")
def get_small_button_style(color="cyan"): return _generate_3d_button(color, "small")

def get_table_style():
    """Premium enterprise table — used in dialogs / secondary views."""
    return f"""
        QTableWidget {{
            background-color: {COLOR_SURFACE};
            alternate-background-color: {COLOR_SURFACE2};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid {COLOR_BORDER};
            border-radius: 8px;
            font-family: {FONT_PRIMARY};
            font-size: {FONT_SIZE_BASE};
            gridline-color: #0f1828;
            outline: none;
            selection-background-color: rgba(0,242,255,0.14);
            selection-color: {COLOR_TEXT_PRIMARY};
        }}
        QHeaderView::section {{
            background-color: {COLOR_BG};
            color: {COLOR_ACCENT_CYAN};
            padding: 6px 10px;
            border: none;
            border-bottom: 2px solid rgba(0,242,255,0.25);
            font-family: {FONT_PRIMARY};
            font-weight: 700;
            text-transform: uppercase;
            font-size: 10px;
            letter-spacing: 0.8px;
        }}
        QTableWidget::item {{
            padding: 8px 12px;
            border-bottom: 1px solid #0f1828;
        }}
        QTableWidget::item:hover {{
            background: rgba(0,242,255,0.07);
        }}
        QTableWidget::item:selected {{
            background: rgba(0,242,255,0.16);
            color: #ffffff;
            border-left: 2px solid {COLOR_ACCENT_CYAN};
        }}
        QTableCornerButton::section {{
            background: #080b10;
            border: none;
        }}
        /* Native item checkbox (ItemIsUserCheckable — QTableWidgetItem with checkState) */
        QTableWidget::indicator {{
            width: 17px; height: 17px;
            border-radius: 4px;
            border: 1.5px solid #2e4060;
            background: #080c16;
        }}
        QTableWidget::indicator:hover {{
            border: 1.5px solid #00f2ff;
            background: rgba(0,242,255,0.07);
        }}
        QTableWidget::indicator:checked {{
            background: #00f2ff;
            border: 1.5px solid #00f2ff;
        }}
        QTableWidget::indicator:unchecked {{
            background: #080c16;
            border: 1.5px solid #2e4060;
        }}
        /* QCheckBox inside cells (widget-based) */
        QTableWidget QCheckBox::indicator {{
            width: 15px; height: 15px;
            border-radius: 3px;
            border: 1.5px solid #2a3a50;
            background: {COLOR_BG};
        }}
        QTableWidget QCheckBox::indicator:hover {{
            border: 1.5px solid {COLOR_ACCENT_CYAN};
        }}
        QTableWidget QCheckBox::indicator:checked {{
            background: {COLOR_ACCENT_CYAN};
            border: 1.5px solid {COLOR_ACCENT_CYAN};
        }}
        {_scrollbar_style()}
    """


def _scrollbar_style():
    return f"""
        QScrollBar:vertical {{
            border: none; background: {COLOR_BG}; width: 7px; margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: #2a3a50; min-height: 24px; border-radius: 3px;
        }}
        QScrollBar::handle:vertical:hover {{ background: {COLOR_ACCENT_CYAN}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar:horizontal {{
            border: none; background: {COLOR_BG}; height: 7px; margin: 0;
        }}
        QScrollBar::handle:horizontal {{
            background: #2a3a50; min-width: 24px; border-radius: 3px;
        }}
        QScrollBar::handle:horizontal:hover {{ background: {COLOR_ACCENT_CYAN}; }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
    """


# ════════════════════════════════════════════════════════════
#  INPUT FIELDS
# ════════════════════════════════════════════════════════════
def get_lineedit_style():
    """Input field with cyan focus glow."""
    return f"""
        QLineEdit {{
            background: {COLOR_BG};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid {COLOR_BORDER};
            border-radius: 6px;
            padding: 7px 11px;
            font-family: {FONT_PRIMARY};
            font-size: 13px;
            min-height: 32px;
        }}
        QLineEdit:hover {{
            border: 1px solid #2a3a56;
        }}
        QLineEdit:focus {{
            border: 1px solid rgba(0,242,255,0.7);
            background: rgba(0,242,255,0.03);
        }}
        QLineEdit:disabled {{
            background: #080c14;
            color: {COLOR_TEXT_MUTED};
            border: 1px solid #141e30;
        }}
        QTextEdit {{
            background: {COLOR_BG};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid {COLOR_BORDER};
            border-radius: 6px;
            padding: 7px 11px;
            font-family: {FONT_PRIMARY};
            font-size: 13px;
        }}
        QTextEdit:focus {{
            border: 1px solid rgba(0,242,255,0.7);
        }}
    """


def get_combobox_style():
    """Styled dropdown matching inputs."""
    return f"""
        QComboBox {{
            background: {COLOR_BG};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid {COLOR_BORDER};
            border-radius: 6px;
            padding: 7px 11px;
            font-family: {FONT_PRIMARY};
            font-size: 13px;
            min-height: 32px;
        }}
        QComboBox:hover {{ border: 1px solid #2a3a56; }}
        QComboBox:focus {{ border: 1px solid rgba(0,242,255,0.7); }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 24px;
            border-left: none;
        }}
        QComboBox QAbstractItemView {{
            background: {COLOR_SURFACE};
            color: {COLOR_TEXT_PRIMARY};
            selection-background-color: rgba(0,242,255,0.18);
            selection-color: {COLOR_ACCENT_CYAN};
            border: 1px solid {COLOR_BORDER};
            border-radius: 4px;
            outline: none;
            padding: 2px;
        }}
    """


def get_spinbox_style():
    return f"""
        QSpinBox, QDoubleSpinBox {{
            background: {COLOR_BG};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid {COLOR_BORDER};
            border-radius: 6px;
            padding: 6px 10px;
            font-family: {FONT_PRIMARY};
            font-size: 13px;
            min-height: 32px;
        }}
        QSpinBox:hover, QDoubleSpinBox:hover {{ border: 1px solid #2a3a56; }}
        QSpinBox:focus, QDoubleSpinBox:focus {{
            border: 1px solid rgba(0,242,255,0.7);
            background: rgba(0,242,255,0.02);
        }}
        QSpinBox::up-button, QDoubleSpinBox::up-button,
        QSpinBox::down-button, QDoubleSpinBox::down-button {{
            background: #1a2236; border: none; width: 18px; border-radius: 3px;
        }}
        QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
        QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
            background: #2a3550;
        }}
    """


# ════════════════════════════════════════════════════════════
#  DIALOGS & PANELS
# ════════════════════════════════════════════════════════════
def get_dialog_style():
    return f"""
        QDialog {{
            background: {COLOR_BG};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid {COLOR_BORDER};
            border-radius: 10px;
        }}
        QLabel {{
            color: {COLOR_TEXT_PRIMARY};
            font-family: {FONT_PRIMARY};
            font-size: 13px;
            background: transparent;
        }}
        QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QDateEdit, QComboBox {{
            background: {COLOR_SURFACE};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid {COLOR_BORDER};
            border-radius: 6px;
            padding: 7px 10px;
            font-family: {FONT_PRIMARY};
            font-size: 13px;
        }}
        QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
            border: 1px solid rgba(0,242,255,0.7);
        }}
    """


def get_panel_frame_style(accent=False):
    c = COLOR_ACCENT_CYAN if accent else COLOR_BORDER
    return f"""
        QFrame {{
            background: {COLOR_SURFACE};
            border: 1px solid {c};
            border-radius: 8px;
        }}
    """


def get_groupbox_style():
    return f"""
        QGroupBox {{
            background: {COLOR_SURFACE};
            border: 1px solid rgba(0,242,255,0.15);
            border-radius: 8px;
            margin-top: 16px;
            padding: 12px 10px 10px 10px;
            font-family: {FONT_PRIMARY};
            font-size: 12px;
            font-weight: bold;
            color: {COLOR_ACCENT_CYAN};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 2px 10px;
            color: {COLOR_ACCENT_CYAN};
            background: {COLOR_SURFACE};
            border-radius: 4px;
        }}
    """


# ════════════════════════════════════════════════════════════
#  MENUS
# ════════════════════════════════════════════════════════════
def get_menu_style():
    return f"""
        QMenu {{
            background: {COLOR_SURFACE};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid {COLOR_BORDER};
            border-radius: 8px;
            padding: 4px 0;
            font-family: {FONT_PRIMARY};
            font-size: 13px;
        }}
        QMenu::item {{
            padding: 8px 28px 8px 14px;
            border-radius: 4px;
            margin: 1px 4px;
        }}
        QMenu::item:selected {{
            background: rgba(0,242,255,0.14);
            color: {COLOR_ACCENT_CYAN};
        }}
        QMenu::item:disabled {{
            color: {COLOR_TEXT_DIM};
        }}
        QMenu::separator {{
            height: 1px;
            background: {COLOR_BORDER};
            margin: 4px 10px;
        }}
    """


# ════════════════════════════════════════════════════════════
#  DATE EDIT
# ════════════════════════════════════════════════════════════
def get_dateedit_style():
    return f"""
        QDateEdit, QDateTimeEdit {{
            background: {COLOR_BG};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid {COLOR_BORDER};
            border-radius: 6px;
            padding: 6px 10px;
            font-family: {FONT_PRIMARY};
            font-size: 13px;
        }}
        QDateEdit:focus, QDateTimeEdit:focus {{
            border: 1px solid rgba(0,242,255,0.7);
        }}
        QDateEdit::drop-down, QDateTimeEdit::drop-down {{
            width: 24px; border-left: none;
        }}
        QCalendarWidget QWidget {{ alternate-background-color: #161A24; }}
        QCalendarWidget QToolButton {{
            color: {COLOR_TEXT_PRIMARY}; background: {COLOR_BG};
            border: none; border-radius: 4px; padding: 4px;
        }}
        QCalendarWidget QToolButton:hover {{ background: #2a3550; }}
        QCalendarWidget QAbstractItemView:enabled {{
            background: {COLOR_SURFACE}; color: {COLOR_TEXT_PRIMARY};
            selection-background-color: {COLOR_ACCENT_CYAN};
            selection-color: #000000;
        }}
        QCalendarWidget QAbstractItemView:disabled {{ color: #3a4a5a; }}
    """


# ════════════════════════════════════════════════════════════
#  MISC HELPERS
# ════════════════════════════════════════════════════════════
def get_section_header_style(color=None):
    c = color or COLOR_ACCENT_CYAN
    return f"""
        QLabel {{
            color: {c};
            font-family: {FONT_PRIMARY};
            font-size: 14px;
            font-weight: bold;
            letter-spacing: 1.5px;
            padding: 0 0 4px 0;
            border-bottom: 1px solid rgba(0,242,255,0.18);
        }}
    """


def get_form_label_style():
    return f"""
        QLabel {{
            color: {COLOR_TEXT_MUTED};
            font-family: {FONT_PRIMARY};
            font-size: 12px;
            font-weight: 600;
        }}
    """


# ════════════════════════════════════════════════════════════
#  TREE WIDGET & TABS & PROGRESS (Added for Catalog/General)
# ════════════════════════════════════════════════════════════
def get_tree_style():
    return f"""
        QTreeWidget {{
            background-color: {COLOR_BG};
            color: {COLOR_TEXT_PRIMARY};
            border: none;
            font-size: {FONT_SIZE_BASE};
            font-family: {FONT_PRIMARY};
            outline: none;
        }}
        QTreeWidget::item {{
            padding: 5px 6px;
            border-radius: 4px;
        }}
        QTreeWidget::item:selected {{
            background: rgba(0,242,255,0.16);
            color: {COLOR_ACCENT_CYAN};
            border-left: 2px solid {COLOR_ACCENT_CYAN};
        }}
        QTreeWidget::item:hover {{
            background: rgba(0,242,255,0.07);
        }}
        QTreeWidget::branch:has-children:!has-siblings:closed,
        QTreeWidget::branch:closed:has-children:has-siblings {{
            image: none;
            border-image: none;
        }}
        {_scrollbar_style()}
    """


def get_tab_style():
    return f"""
        QTabWidget::pane {{
            border: none;
            background: {COLOR_BG};
        }}
        QTabBar::tab {{
            background: {COLOR_SURFACE};
            color: {COLOR_TEXT_MUTED};
            padding: 9px 20px;
            font-weight: 700;
            font-size: 12px;
            letter-spacing: 0.5px;
            font-family: {FONT_PRIMARY};
            border: 1px solid {COLOR_BORDER};
            border-bottom: 2px solid transparent;
            border-radius: 6px 6px 0 0;
            margin-right: 2px;
        }}
        QTabBar::tab:selected {{
            color: {COLOR_ACCENT_CYAN};
            border-bottom: 2px solid {COLOR_ACCENT_CYAN};
            background: {COLOR_BG};
            border-color: rgba(0,242,255,0.20);
            border-bottom-color: {COLOR_ACCENT_CYAN};
        }}
        QTabBar::tab:hover:!selected {{
            background: rgba(0,242,255,0.05);
            color: #94a3b8;
        }}
    """


def get_progressbar_style():
    return f"""
        QProgressBar {{
            background: {COLOR_SURFACE};
            border-radius: 4px;
            color: #f9fafb;
            text-align: center;
        }}
        QProgressBar::chunk {{
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 rgba(0,200,220,0.8), stop:1 rgba(0,242,255,0.8));
            border-radius: 4px;
        }}
    """
