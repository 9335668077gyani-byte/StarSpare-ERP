# Colors
# Colors - Anti-Gravity Cyberpunk Spec
COLOR_BACKGROUND = "#010206" # Deepest Cosmic Void
COLOR_SURFACE = "#03060c"    # Nebulous Surface
COLOR_ACCENT_CYAN = "#00f2ff" # Plasma Cyan
COLOR_ACCENT_RED = "#ff0044"  # Alert Crimson
COLOR_ACCENT_GREEN = "#00ff88" # Energy Green
COLOR_ACCENT_YELLOW = "#ffe600" # Cyber Yellow (Warning)
COLOR_ACCENT_AMBER = "#ffaa00" # Plasma Amber
COLOR_TEXT_PRIMARY = "#e2e8f0" # Astral White
# Professional Brand Color
COLOR_NAVY_BLUE = "#040c1a"

# Dimensions & Spacing
DIM_BUTTON_HEIGHT = 45
DIM_INPUT_HEIGHT = 45
DIM_ICON_SIZE = 24
DIM_MARGIN_STD = 20
DIM_SPACING_STD = 15
DIM_CORNER_RADIUS = 0 # Sharp corners for tech look (or slightly rounded 4px)

# Cyber-Mechanical Styles
STYLE_MAIN_WINDOW = f"""
    QMainWindow {{
        background-color: {COLOR_BACKGROUND};
    }}
"""

STYLE_NEON_BUTTON = f"""
    QPushButton {{
        background-color: transparent; 
        color: {COLOR_ACCENT_CYAN}; 
        border: 1px solid {COLOR_ACCENT_CYAN}; 
        border-radius: 4px; 
        padding: 8px 16px; 
        font-family: 'Segoe UI', sans-serif;
        font-weight: bold;
        font-size: 14px;
        letter-spacing: 1px;
    }}
    QPushButton:hover {{
        background-color: {COLOR_ACCENT_CYAN};
        border: 1px solid {COLOR_ACCENT_CYAN};
        color: #000;
        /* box-shadow removed */
    }}
    QPushButton:pressed {{
        background-color: rgba(0, 242, 255, 0.8);
        color: #000;
        border: 1px solid {COLOR_ACCENT_CYAN};
    }}
"""

STYLE_BUTTON_PRIMARY = f"""
    QPushButton {{
        background-color: {COLOR_ACCENT_CYAN};
        color: #000;
        border: none;
        border-radius: 4px;
        padding: 8px 16px;
        font-family: 'Segoe UI', sans-serif;
        font-weight: bold;
        font-size: 14px;
        letter-spacing: 1px;
    }}
    QPushButton:hover {{
        background-color: #fff; /* White on hover for contrast */
    }}
    QPushButton:pressed {{
        background-color: #00c4ce; /* Darker cyan */
    }}
"""

STYLE_BUTTON_SUCCESS = f"""
    QPushButton {{
        background-color: rgba(0, 255, 157, 0.1); 
        color: {COLOR_ACCENT_GREEN}; 
        border: 1px solid {COLOR_ACCENT_GREEN}; 
        border-radius: 4px; 
        padding: 8px 16px;
        font-family: 'Segoe UI', sans-serif;
        font-weight: bold;
        font-size: 14px;
        letter-spacing: 1px;
    }}
    QPushButton:hover {{
        background-color: {COLOR_ACCENT_GREEN};
        color: #000;
    }}
    QPushButton:pressed {{
        background-color: #00cc7a;
    }}
"""

STYLE_SIDEBAR_BTN = f"""
    QPushButton {{
        text-align: left;
        padding-left: 20px;
        border: none;
        background-color: transparent;
        color: #6c7a89;
        font-size: 14px;
        font-family: 'Segoe UI', sans-serif;
        font-weight: 500;
        letter-spacing: 1px;
    }}
    QPushButton:hover {{
        color: {COLOR_TEXT_PRIMARY};
        background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {COLOR_SURFACE}, stop:1 rgba(0, 242, 255, 0.05));
        border-left: 2px solid {COLOR_ACCENT_CYAN};
    }}
    QPushButton:checked {{
        color: {COLOR_ACCENT_CYAN};
        background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(0, 242, 255, 0.15), stop:1 transparent);
        border-left: 4px solid {COLOR_ACCENT_CYAN};
        font-weight: bold;
    }}
"""

STYLE_DOCK_BTN = f"""
    QToolButton {{
        background-color: transparent;
        border: none;
        border-left: 3px solid transparent; 
        color: #6c7a89; /* Muted Slate */
        font-family: 'Orbitron', 'Segoe UI', sans-serif;
        font-size: 10px;
        font-weight: bold;
        letter-spacing: 2px;
        padding: 5px;
        margin-bottom: 5px;
        text-transform: uppercase;
    }}
    QToolButton:hover {{
        color: {COLOR_ACCENT_CYAN};
        background-color: rgba(255, 255, 255, 0.05);
        border-left: 3px solid rgba(0, 242, 255, 0.5);
    }}
    QToolButton:checked {{
        color: {COLOR_ACCENT_CYAN};
        background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(0, 242, 255, 0.2), stop:1 transparent);
        border-left: 3px solid {COLOR_ACCENT_CYAN}; /* Active Indicator */
    }}
"""

STYLE_ACTION_HOLO = f"""
    QPushButton {{
        background-color: rgba(0, 242, 255, 0.05);
        border: 1px solid rgba(0, 242, 255, 0.3);
        border-radius: 15px; /* Circular/Pill */
        color: {COLOR_ACCENT_CYAN};
        font-size: 12px;
    }}
    QPushButton:hover {{
        background-color: {COLOR_ACCENT_CYAN};
        color: #000;
        border: 1px solid {COLOR_ACCENT_CYAN};
    }}
"""

STYLE_GLASS_PANEL = f"""
    QFrame {{
        background-color: rgba(11, 14, 20, 0.6); /* Translucent dark blue tint */
        border: 1px solid rgba(0, 242, 255, 0.2); /* Faint cyan border */
        border-radius: 8px; /* Slight rounding */
    }}
"""

STYLE_GLASS_SIDEBAR = f"""
    QFrame {{
        background-color: {COLOR_SURFACE}; 
        border-right: 1px solid rgba(255, 255, 255, 0.05); /* Very subtle divider */
        border-radius: 0px;
    }}
"""

STYLE_HEADER_ACCENT = f"""
    QFrame {{
        background-color: {COLOR_ACCENT_CYAN}; 
        max-height: 2px;
        border: none;
    }}
"""

STYLE_TAB_WIDGET = f"""
    QTabWidget::pane {{ 
        border: 1px solid #1a2a3a; 
        background: {COLOR_BACKGROUND}; 
        border-radius: 4px;
    }}
    QTabBar::tab {{ 
        background: #0b0e14; 
        color: #6c7a89; 
        padding: 8px 20px; 
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        margin-right: 2px;
        font-family: 'Segoe UI', sans-serif;
        font-weight: 600;
        letter-spacing: 0.5px;
    }}
    QTabBar::tab:selected {{ 
        background: rgba(0, 242, 255, 0.1); 
        color: {COLOR_ACCENT_CYAN}; 
        border-bottom: 2px solid {COLOR_ACCENT_CYAN};
        font-weight: bold; 
    }}
    QTabBar::tab:hover {{ 
        background: #151a25; 
        color: #e0e6ed;
    }}
"""

STYLE_INPUT_CYBER = f"""
    QLineEdit, QTextEdit, QDateEdit {{
        background-color: rgba(5, 11, 20, 0.8);
        color: {COLOR_ACCENT_CYAN};
        border: 1px solid #1a2a3a;
        border-radius: 4px;
        padding: 10px; 
        font-family: 'Consolas', 'Segoe UI', monospace; /* Monospace for data entry feel */
        font-size: 13px;
    }}
    QLineEdit:focus, QTextEdit:focus {{
        border: 1px solid {COLOR_ACCENT_CYAN};
        background-color: rgba(0, 242, 255, 0.05);
    }}
"""

STYLE_DROPDOWN_CYBER = f"""
    QComboBox {{
        background-color: rgba(10, 15, 25, 0.8);
        color: {COLOR_ACCENT_CYAN};
        border: 1px solid {COLOR_ACCENT_CYAN};
        border-radius: 4px;
        padding: 5px 10px;
        font-family: 'Segoe UI', sans-serif;
        font-size: 14px;
    }}
    QComboBox:hover {{
        background-color: rgba(0, 242, 255, 0.1);
    }}
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 30px;
        border-left: 1px solid {COLOR_ACCENT_CYAN};
        border-top-right-radius: 4px;
        border-bottom-right-radius: 4px;
        background: rgba(0, 0, 0, 0.2);
    }}
    QComboBox::down-arrow {{
        image: none;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 5px solid {COLOR_ACCENT_CYAN};
        width: 0;
        height: 0;
        margin-top: 2px;
        margin-right: 2px;
    }}
    QComboBox QAbstractItemView {{
        background-color: #0b0b14;
        color: white;
        selection-background-color: {COLOR_ACCENT_CYAN};
        selection-color: black;
        border: 1px solid {COLOR_ACCENT_CYAN};
        outline: 0;
    }}
"""

STYLE_LCD_DISPLAY = f"""
    QLabel {{
        font-family: 'Orbitron', 'Segoe UI', sans-serif; /* Orbitron if available, else Segoe */
        font-size: 32px;
        font-weight: bold;
        color: {COLOR_ACCENT_GREEN};
        letter-spacing: 2px;
    }}
"""

STYLE_DIGITAL_LABEL = f"""
    QLabel {{
        font-family: 'Consolas', monospace;
        font-size: 16px;
        color: {COLOR_ACCENT_YELLOW};
        font-weight: bold;
        background-color: #080a10;
        padding: 4px 8px;
        border: 1px solid #333;
        border-radius: 4px;
    }}
"""

# New Sharp Grid Style
STYLE_TABLE_CYBER = f"""
    QTableWidget {{
        background-color: {COLOR_BACKGROUND};
        gridline-color: #0f1520; /* Very subtle grid */
        color: {COLOR_TEXT_PRIMARY};
        border: none;
        font-family: 'Segoe UI', sans-serif;
        font-size: 13px;
        selection-background-color: rgba(0, 242, 255, 0.1);
        outline: 0;
    }}
    QTableWidget::viewport {{
        background-color: {COLOR_BACKGROUND};
    }}
    QHeaderView::section {{
        background-color: #080b10;
        color: {COLOR_ACCENT_CYAN}; 
        padding: 5px 10px;
        border: none;
        border-bottom: 2px solid rgba(0, 242, 255, 0.3);
        font-family: 'Segoe UI', sans-serif;
        font-weight: 700;
        text-transform: uppercase;
        font-size: 11px;
        letter-spacing: 1px;
    }}
    QTableCornerButton::section {{
        background-color: #080b10;
        border: none;
    }}
    QTableWidget::item {{
        padding: 2px 5px; /* Tighter padding for cells */
        border-bottom: 1px solid #0f1520;
    }}
    QTableWidget::item:hover {{
        background-color: rgba(0, 242, 255, 0.1); 
        border: 1px solid {COLOR_ACCENT_CYAN};
    }}
    QTableWidget::item:selected {{
        background-color: rgba(0, 242, 255, 0.3); /* Brighter selection */
        color: white;
        border: 1px solid {COLOR_ACCENT_CYAN}; /* Highlight border */
    }}
    QTableWidget::item:focus {{
        outline: none;
        border: none;
    }}
    
    QScrollBar:vertical {{
        border: none;
        background: #050b14;
        width: 6px;
        margin: 0px;
    }}
    QScrollBar::handle:vertical {{
        background: #1a2a3a;
        min-height: 20px;
        border-radius: 3px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {COLOR_ACCENT_CYAN};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar::horizontal {{
        border: none;
        background: #050b14;
        height: 6px;
        margin: 0px;
    }}
    QScrollBar::handle:horizontal {{
        background: #1a2a3a;
        min-width: 20px;
        border-radius: 3px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {COLOR_ACCENT_CYAN};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}
"""

def get_stylesheet():
    return f"""
        {STYLE_MAIN_WINDOW}
        {STYLE_SIDEBAR_BTN}
        {STYLE_GLASS_PANEL}
        /* Global Scrollbar */
        QScrollBar:vertical {{
            border: none;
            background: #222;
            width: 8px;
            margin: 0px 0px 0px 0px;
        }}
        QScrollBar::handle:vertical {{
            background: #444;
            min-height: 20px;
            border-radius: 4px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        
        /* Calendar Widget Styling */
        QCalendarWidget QWidget {{
            background-color: #0b0b14;
            color: white;
            selection-background-color: {COLOR_ACCENT_CYAN};
            selection-color: black;
            font-family: 'Segoe UI', sans-serif;
        }}
        QCalendarWidget QToolButton {{
            color: {COLOR_ACCENT_CYAN};
            icon-size: 24px;
            background-color: transparent;
            font-weight: bold;
        }}
        QCalendarWidget QMenu {{
            background-color: #111;
            color: white;
        }}
        QCalendarWidget QSpinBox {{
            background-color: #111;
            color: white;
            selection-background-color: {COLOR_ACCENT_CYAN};
        }}
        QCalendarWidget QAbstractItemView:enabled {{   
            background-color: #0b0b14;  
            color: white;  
            selection-background-color: {COLOR_ACCENT_CYAN};
            selection-color: black;
        }}
        QCalendarWidget QAbstractItemView:disabled {{ 
            color: #444; 
        }}
        
        /* Dropdown Popup Styling */
        QComboBox QAbstractItemView {{
            background-color: #0b0b14;
            color: white;
            selection-background-color: {COLOR_ACCENT_CYAN};
            selection-color: black;
            border: 1px solid {COLOR_ACCENT_CYAN};
            outline: 0;
        }}
        QComboBox {{
            background-color: rgba(0, 0, 0, 0.6);
            color: {COLOR_ACCENT_CYAN};
            border: 1px solid #333;
            border-radius: 4px;
            padding: 5px;
        }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 25px;
            border-left-width: 1px;
            border-left-color: #333;
            border-left-style: solid;
        }}
    """

STYLE_DANGER_BUTTON = f"""
    QPushButton {{
        background-color: rgba(255, 68, 68, 0.1);
        color: {COLOR_ACCENT_RED};
        border: 1px solid {COLOR_ACCENT_RED};
        border-radius: 4px;
        padding: 5px 15px;
        font-family: 'Segoe UI', sans-serif;
        font-weight: bold;
        font-size: 14px;
        letter-spacing: 1px;
    }}
    QPushButton:hover {{
        background-color: {COLOR_ACCENT_RED};
        color: white;
    }}
    QPushButton:pressed {{
        background-color: rgba(200, 0, 0, 0.8);
        border: 1px solid {COLOR_ACCENT_RED};
    }}
"""
