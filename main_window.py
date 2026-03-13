from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QStackedWidget, QLabel, QFrame, QSizePolicy, QToolButton)
from PyQt6.QtCore import Qt, QSize, QTimer
from styles import COLOR_BACKGROUND, COLOR_SURFACE, COLOR_ACCENT_CYAN
from logger import app_logger

# Page modules are imported lazily in switch_page() for fast startup

class MainWindow(QMainWindow):
    def __init__(self, db_manager, user_role="ADMIN", username="admin"): 
        super().__init__()
        app_logger.info("Initializing MainWindow...")
        self.db_manager = db_manager
        self.user_role = user_role
        self.username = username
        self.setWindowTitle(f"SpareParts Pro v1.5 - {username} ({user_role})")
        from PyQt6.QtWidgets import QApplication
        
        # Determine Screen Size for Responsive bounds
        screen = QApplication.primaryScreen()
        screen_geom = screen.availableGeometry() if screen else None
        
        if screen_geom:
            w, h = screen_geom.width(), screen_geom.height()
            
            # If screen is small (e.g. 1366x768), adjust minimums so it fits
            # The available geometry subtracts the Windows Taskbar for maximum fit
            min_w = min(1100, int(w * 0.9))
            min_h = min(750, int(h * 0.95))
            
            self.setMinimumSize(min_w, min_h)
            
            # Try to start maximized if resolution is low, otherwise 1400x900
            if w <= 1400 or h <= 900:
                self.setWindowState(Qt.WindowState.WindowMaximized)
            else:
                self.resize(1400, 900)
        else:
            # Fallback
            self.resize(1400, 900)
            self.setMinimumSize(1100, 750) # Safe Zone

        # FLASH FIX: Set background immediately in multiple ways
        self.setStyleSheet(f"background-color: {COLOR_BACKGROUND};")
        
        # Fetch Permissions if STAFF
        self.permissions = []
        if self.user_role == "STAFF":
            user_profile = self.db_manager.get_user_profile(self.username)
            if user_profile and user_profile.get("permissions"):
                import json
                try:
                    self.permissions = json.loads(user_profile["permissions"])
                except:
                    self.permissions = []
        
        # Hard Force Palette on Window
        from PyQt6.QtGui import QPalette, QColor
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor(COLOR_BACKGROUND))
        self.setPalette(pal)
        self.setAutoFillBackground(True)
        
        self.setup_ui()

    def setup_ui(self):
        main_widget = QWidget()
        main_widget.setStyleSheet(f"background-color: {COLOR_BACKGROUND};")
        self.setCentralWidget(main_widget)
        
        layout = QHBoxLayout(main_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # --- Sidebar (Slim Vertical Dock) ---
        sidebar = QFrame()
        sidebar.setStyleSheet(f"background-color: #080a10; border-right: 1px solid rgba(0, 242, 255, 0.1);") 
        sidebar.setFixedWidth(90) # Slim Dock
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 20, 0, 20)
        sidebar_layout.setSpacing(24) # Generous vertical spacing
        
        # Logo Area (Compact)
        logo_label = QLabel("PRO")
        logo_label.setStyleSheet(f"""
            color: {COLOR_ACCENT_CYAN}; 
            font-size: 16px; 
            font-weight: 800; 
            letter-spacing: 1px;
            font-family: 'Orbitron', sans-serif;
            padding-bottom: 10px;
            border-bottom: 1px solid #333;
        """)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(logo_label)
        
        # Spacer
        sidebar_layout.addSpacing(10)
        
        self.nav_buttons = {} # Changed to dict {page_idx: button}
        
        # Menu Items: Name, Icon (Emoji as placeholder for Lucide), Index, Role, Permission Key
        menu_structure = [
            ("DASHBOARD", "🏠", 0, "STAFF", None),
            ("BILLING", "💳", 1, "STAFF", "can_manage_billing"),
            ("INVENTORY", "📦", 2, "STAFF", "can_manage_inventory"),
            ("REPORTS", "📊", 3, "ADMIN", "can_view_reports"),  
            ("EXPENSES", "💸", 4, "ADMIN", None),
            ("ORDERS", "🛒", 6, "ADMIN", "can_manage_orders"),
            ("ACCESS", "🔒", 5, "ADMIN", "can_manage_self"),
            ("SETTINGS", "⚙️", 7, "ADMIN", "can_backup_data")
        ]
        
        self.stacked_widget = QStackedWidget()
        
        # LAZY LOADING: Create empty placeholders, load pages on-demand
        # Store module and class names as strings for deferred import
        self.page_instances = {}  # Cache loaded pages
        self.page_classes = {
            0: ("Dashboard", "dashboard_page", "DashboardPage"),
            1: ("Billing", "billing_page", "BillingPage"),
            2: ("Inventory", "inventory_page", "InventoryPage"),
            3: ("Reports", "reports_page", "ReportsPage"),
            4: ("Expenses", "expense_page", "ExpensePage"),
            5: ("Access", "user_management_page", "UserManagementPage"),
            6: ("Orders", "purchase_order_page", "PurchaseOrderPage"),
            7: ("Settings", "settings_page", "SettingsPage")
        }
        
        # Add empty placeholder widgets for each page
        for idx in range(8):
            placeholder = QWidget()
            placeholder.setStyleSheet(f"background-color: {COLOR_BACKGROUND};")
            self.stacked_widget.addWidget(placeholder) 
        
        # Build Sidebar using CyberSidebarButton for Reactor Box Look
        from custom_components import CyberSidebarButton
        
        for name, icon, page_idx, min_role, perm_key in menu_structure:
            
            # Logic: 
            # 1. If Role is ADMIN, show everything
            # 2. If Role is STAFF:
            #    - Skip if min_role is ADMIN (and no special permission overrides?)
            #    - OR check if specific permission is present
            
            allow = False
            if self.user_role == "ADMIN":
                allow = True
            else:
                # STAFF Logic
                if min_role == "ADMIN":
                    # Usually hidden, but check if we want to allow override?
                    # For now, strictly enforce Role for Access/Expenses
                    # But Reports/Settings might be allowed via permissions
                    if perm_key and perm_key in self.permissions:
                        allow = True
                    else:
                        allow = False
                else:
                    # STAFF level item (Dashboard, Billing, Inventory)
                    # Check if restricted by permission?
                    if perm_key:
                        allow = perm_key in self.permissions
                    else:
                        allow = True # Dashboard is always allowed
            
            if not allow:
                continue
            
            # Use new Reactor Component    
            btn = CyberSidebarButton(name, icon)
            # Signal connection slightly different for custom widget signal
            btn.clicked.connect(lambda idx=page_idx, b=btn: self.switch_page(idx, b))
            
            sidebar_layout.addWidget(btn)
            self.nav_buttons[page_idx] = btn # Map index to button
            
        sidebar_layout.addStretch()
        
        # UNIVERSAL REFRESH BUTTON
        btn_refresh = QPushButton("🔄")
        btn_refresh.setFixedSize(70, 35)
        btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 229, 255, 0.15);
                color: #00e5ff;
                border: 2px solid #00e5ff;
                border-radius: 6px;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00e5ff;
                color: #000;
            }
        """)
        btn_refresh.setToolTip("Refresh Current Page Data")
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.clicked.connect(self.refresh_current_page)
        sidebar_layout.addWidget(btn_refresh)
        
        # Logout
        btn_logout = QPushButton("Logout")
        btn_logout.setStyleSheet("border: 1px solid #ff4444; color: #ff4444; border-radius: 5px; height: 30px;")
        btn_logout.clicked.connect(self.close) 
        sidebar_layout.addWidget(btn_logout)
        
        layout.addWidget(sidebar)
        layout.addWidget(self.stacked_widget, 1) # Main content stretches
        
        # Quick Win #2: Setup keyboard shortcuts
        self.setup_shortcuts()
        
        # Defer first page load so window renders instantly
        # Find first available button
        if self.nav_buttons:
            # Get the button with lowest index
            first_idx = min(self.nav_buttons.keys())
            QTimer.singleShot(0, lambda: self.nav_buttons[first_idx].click())

    def setup_shortcuts(self):
        """Setup global keyboard shortcuts for productivity (Quick Win #2)"""
        from PyQt6.QtGui import QShortcut, QKeySequence
        
        # Ctrl+F: Focus search (context-aware)
        shortcut_search = QShortcut(QKeySequence("Ctrl+F"), self)
        shortcut_search.activated.connect(self.focus_search)
        
        # F5: Refresh current page
        shortcut_refresh = QShortcut(QKeySequence("F5"), self)
        shortcut_refresh.activated.connect(self.refresh_current_page)
        
        # Ctrl+B: Quick jump to Billing page
        shortcut_billing = QShortcut(QKeySequence("Ctrl+B"), self)
        shortcut_billing.activated.connect(lambda: self.quick_navigate(1))  # Index 1 = Billing
        
        # Ctrl+I: Quick jump to Inventory page
        shortcut_inventory = QShortcut(QKeySequence("Ctrl+I"), self)
        shortcut_inventory.activated.connect(lambda: self.quick_navigate(2))  # Index 2 = Inventory
        
        # Ctrl+O: Quick jump to Orders page
        shortcut_orders = QShortcut(QKeySequence("Ctrl+O"), self)
        shortcut_orders.activated.connect(lambda: self.quick_navigate(6))  # Index 6 = Orders
        
        app_logger.info("Keyboard shortcuts configured successfully.")
    
    def focus_search(self):
        """Focus the search box on the current page (context-aware)"""
        current_widget = self.stacked_widget.currentWidget()
        # Try to find and focus search field by common attribute names
        if hasattr(current_widget, 'search_input'):
            current_widget.search_input.setFocus()
        elif hasattr(current_widget, 'filter_input'):
            current_widget.filter_input.setFocus()
        elif hasattr(current_widget, 'search_bar'):
            current_widget.search_bar.setFocus()
    
    def quick_navigate(self, page_index):
        """Quick navigate to a specific page"""
        if page_index in self.nav_buttons:
             self.nav_buttons[page_index].click()

    def switch_page(self, index, button):
        # LAZY LOAD: Import module and create page if not already loaded
        if index not in self.page_instances and index in self.page_classes:
            page_info = self.page_classes[index]
            if page_info is not None:
                page_name, module_name, class_name = page_info
                app_logger.info(f"Lazy loading page: {page_name}")
                
                # Lazy import the module
                import importlib
                module = importlib.import_module(module_name)
                page_class = getattr(module, class_name)
                
                # Create page instance
                if class_name == "InventoryPage":
                    page = page_class(self.db_manager, self.user_role, self.username)
                elif class_name == "UserManagementPage":
                    page = page_class(self.db_manager)
                    page.set_user_context(self.user_role, self.username)
                else:
                    page = page_class(self.db_manager)
                
                # Replace placeholder with real page
                self.stacked_widget.removeWidget(self.stacked_widget.widget(index))
                self.stacked_widget.insertWidget(index, page)
                self.page_instances[index] = page
        
        self.stacked_widget.setCurrentIndex(index)
        # Uncheck all in dict
        for btn in self.nav_buttons.values():
            btn.setChecked(False)
        button.setChecked(True)
    
    def refresh_current_page(self):
        current_index = self.stacked_widget.currentIndex()
        current_widget = self.stacked_widget.currentWidget()
        if hasattr(current_widget, 'load_data'):
            app_logger.info(f"Refreshing page at index {current_index}")
            current_widget.load_data()
        else:
            app_logger.warning(f"Current page (index {current_index}) does not have a load_data method")

    def go_to_purchase_page(self, items):
        """
        Switch to Purchase Order Page and populate it with items.
        items: List of selected parts from Inventory.
        """
        # Ensure Page 6 is loaded
        if 6 not in self.page_instances:
             try:
                 import importlib
                 module = importlib.import_module("purchase_order_page")
                 page_class = getattr(module, "PurchaseOrderPage")
                 page = page_class(self.db_manager)
                 
                 # Replace placeholder if exists, else add
                 if self.stacked_widget.count() > 6:
                    self.stacked_widget.removeWidget(self.stacked_widget.widget(6))
                    self.stacked_widget.insertWidget(6, page)
                 else:
                    self.stacked_widget.addWidget(page)
                 
                 self.page_instances[6] = page
             except Exception as e:
                 app_logger.error(f"Failed to load PurchaseOrderPage: {e}")
                 return

        self.stacked_widget.setCurrentIndex(6)
        
        # Pass data
        page = self.page_instances[6]
        success = True
        if hasattr(page, 'load_items_from_inventory'):
            success = page.load_items_from_inventory(items)
            
        # Update Sidebar Highlight (Uncheck all as we don't have direct ref to button 6 easily)
        for btn in self.nav_buttons.values():
            btn.setChecked(False)
        
        # If button 6 exists, highlight it
        if 6 in self.nav_buttons:
            self.nav_buttons[6].setChecked(True)
            
        return success

