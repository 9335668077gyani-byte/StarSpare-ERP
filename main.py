import sys, os, traceback
from PyQt6.QtWidgets import QMessageBox
import PyQt6.QtSvg

# ── Resolve crash log path (EXE-safe) ────────────────────────────────────────
def _get_crash_log_path():
    """Return a writable crash_log.txt path inside AppData (frozen) or project root (dev)."""
    try:
        from path_utils import get_app_data_path
        return get_app_data_path(os.path.join("logs", "crash_log.txt"))
    except Exception:
        return "crash_log.txt"  # fallback for very early failures

_CRASH_LOG = _get_crash_log_path()

class Logger(object):
    def __init__(self, filename=None):
        self.filename = filename or _CRASH_LOG
    def write(self, message):
        try:
            with open(self.filename, 'a', encoding="utf-8") as f:
                f.write(message)
        except: pass
    def flush(self): pass

sys.stdout = Logger()
sys.stderr = Logger()

def excepthook(exc_type, exc_value, exc_tb):
    try:
        with open(_CRASH_LOG, 'a', encoding="utf-8") as f:
            f.write("\n--- PYTHON EXCEPTION ---\n")
            traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
    except: pass
sys.excepthook = excepthook

from PyQt6.QtCore import qInstallMessageHandler, QtMsgType
def qt_message_handler(mode, context, message):
    try:
        with open(_CRASH_LOG, 'a', encoding="utf-8") as f:
            f.write(f"\n[QT MSG] {mode} - {message} (line: {context.line}, func: {context.function}, file: {context.file})\n")
    except: pass
qInstallMessageHandler(qt_message_handler)

from PyQt6.QtWidgets import QMessageBox
import os
from PyQt6.QtGui import QPixmap, QColor, QPalette, QIcon, QClipboard  # type: ignore
from PyQt6.QtWidgets import QApplication, QSplashScreen, QProgressBar, QLabel, QVBoxLayout, QHBoxLayout, QDialog, QLineEdit, QDialogButtonBox, QPushButton, QMessageBox  # type: ignore
from PyQt6.QtCore import Qt, QTimer, QEventLoop  # type: ignore
from logger import app_logger  # type: ignore
from path_utils import get_resource_path, get_app_data_path  # type: ignore
from license_manager import LicenseVerifier  # type: ignore

# IMPORTS FOR PYINSTALLER DETECTION (Lazy loaded modules must be explicit here or in hidden-imports)
if False:
    import dashboard_page
    import billing_page
    import inventory_page
    import reports_page
    import expense_page
    import user_management_page 
    import purchase_order_page
    import settings_page
    import db_config
    import network_setup
    import hardware_id
    import license_manager
    import license_dialog
    import backup_manager
    import custom_components
    import splash_screen
    import styles
    import invoice_generator
    import vendor_manager
    import return_dialog
    import whatsapp_helper
    import ai_manager
    import billing_animations
    import catalog_page
    import vehicle_compat_engine
    import hsn_sync_engine
    import hsn_reference_data
    import tvs_catalog_client
    import api_sync_engine
    import db_engine
    import data_importer
    import report_generator
    import auto_enrich_worker   

# 1. Path Handling — delegated entirely to path_utils (see imports above)

# Ensure all writable subdirectories exist on startup
for d in ["logos", "invoices", "data"]:
    try:
        get_app_data_path(d)
    except OSError as e:
        app_logger.error(f"Failed to create directory '{d}': {e}")

# Thread for non-blocking imports
from PyQt6.QtCore import QThread, pyqtSignal  # type: ignore

class StartupLoader(QThread):
    progress = pyqtSignal(int, str)
    finished_loading = pyqtSignal(object, object, object, object) # db, Login, Main, Verifier
    
    def run(self):
        try:
            # 1. Database
            self.progress.emit(10, "INITIALIZING DATABASE CORE...")
            from database_manager import DatabaseManager  # type: ignore
            import db_config  # type: ignore
            
            # Get DB path from network config (local or network)
            db_path = db_config.get_db_path()
            
            # Ensure the database directory exists (critical for EXE first launch)
            db_dir = os.path.dirname(db_path)
            if db_dir and not os.path.exists(db_dir):
                try:
                    os.makedirs(str(db_dir), exist_ok=True)
                except OSError as e:
                    app_logger.error(f"Failed to create DB directory {db_dir}: {e}")
            
            db_manager = DatabaseManager(db_path)
            self.progress.emit(30, "DATABASE CONNECTED.")
            
            # 2. Heavy Modules & Logic
            self.progress.emit(40, "LOADING SECURITY MODULE...")
            from license_manager import LicenseVerifier  # type: ignore
            verifier = LicenseVerifier(db_manager)
            
            # Check Status Early
            status, _ = verifier.check_license()
            
            # If ACTIVE, we proceed normally.
            # If NEW, TRIAL, or EXPIRED, we need to pass this info to main thread to show Dialog.
            # But QThread cannot show GUI. 
            # Strategy: Pass verifier to finished_loading and handle logic in App init.
            
            from login_window import LoginWindow  # type: ignore
            
            self.progress.emit(60, "LOADING USER INTERFACE...")
            # Pre-import MainWindow dependencies (Pandas, Matplotlib)
            try:
                import pandas  # type: ignore
                import matplotlib.pyplot  # type: ignore
            except ImportError:
                pass # Optional dependencies or let MainWindow handle it
            
            from main_window import MainWindow  # type: ignore
            
            self.progress.emit(90, "FINALIZING STARTUP...")
            
            # Pass back the initialized DB, LoginWindow, MainWindow, and Verifier
            self.finished_loading.emit(db_manager, LoginWindow, MainWindow, verifier)
            
        except Exception as e:
            app_logger.critical(f"Startup Loader Error: {e}")


class HardwareIDDialog(QDialog):
    def __init__(self, hwid, verifier):
        super().__init__()
        self.hwid = hwid
        self.verifier = verifier
        self.setWindowTitle("🔐 Activate SpareParts Pro")
        self.setFixedSize(550, 450)
        self.setStyleSheet("""
            QDialog { background-color: #1a1a1a; color: #ffffff; }
            QLabel { color: #cccccc; font-size: 14px; }
            QLineEdit { 
                background-color: #333; 
                color: #00ffcc; 
                border: 1px solid #555; 
                padding: 8px; 
                font-family: monospace;
            }
            QPushButton {
                background-color: #007acc;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #0099ff; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("🔐 Hardware-Locked Activation")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #00ffcc;")
        layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Check trial status
        status, days = self.verifier.check_license()
        
        if status == 'TRIAL':
            trial_info = QLabel(f"⏳ TRIAL MODE: {days} Days Remaining")
            trial_info.setStyleSheet("font-size: 16px; color: #00ff88; font-weight: bold;")
            trial_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(trial_info)
        elif status == 'EXPIRED':
            trial_info = QLabel("❌ TRIAL EXPIRED - Activation Required")
            trial_info.setStyleSheet("font-size: 16px; color: #ff4444; font-weight: bold;")
            trial_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(trial_info)
        
        layout.addWidget(QLabel("This application is locked to this machine.\nPlease provide the following Hardware ID to activate:"))
        
        # HWID Display
        self.txt_hwid = QLineEdit(hwid)
        self.txt_hwid.setReadOnly(True)
        layout.addWidget(self.txt_hwid)
        
        btn_copy = QPushButton("📋 Copy Hardware ID")
        btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_copy.clicked.connect(self.copy_hwid)
        layout.addWidget(btn_copy)
        
        layout.addWidget(QLabel("─" * 50))
        
        layout.addWidget(QLabel("Enter your License Key:"))
        self.txt_key = QLineEdit()
        self.txt_key.setPlaceholderText("SPRO-XXXXX-XXXXX-XXXXX-XXXXX")
        layout.addWidget(self.txt_key)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        # Trial Button (only if NEW or TRIAL)
        if status in ['NEW', 'TRIAL']:
            self.btn_trial = QPushButton("🆓 Start 15-Day Trial" if status == 'NEW' else "▶ Continue Trial")
            self.btn_trial.setCursor(Qt.CursorShape.PointingHandCursor)
            self.btn_trial.clicked.connect(self.start_trial)
            self.btn_trial.setStyleSheet("background-color: #666; color: white;")
            btn_layout.addWidget(self.btn_trial)
        
        self.btn_activate = QPushButton("✓ ACTIVATE NOW")
        self.btn_activate.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_activate.clicked.connect(self.activate)
        self.btn_activate.setFixedHeight(40)
        self.btn_activate.setStyleSheet("background-color: #00cc66; font-size: 16px;")
        btn_layout.addWidget(self.btn_activate)
        
        layout.addLayout(btn_layout)
        
        # Info Footer
        info = QLabel("💡 To generate a license key for this machine, contact your administrator with the Hardware ID above.")
        info.setStyleSheet("color: #888; font-size: 11px; font-style: italic; margin-top: 10px;")
        info.setWordWrap(True)
        layout.addWidget(info)
        
    def copy_hwid(self):
        QApplication.clipboard().setText(self.txt_hwid.text())
        self.btn_activate.setText("✓ Hardware ID Copied!")
        QTimer.singleShot(2000, lambda: self.btn_activate.setText("✓ ACTIVATE NOW"))

    def start_trial(self):
        status, _ = self.verifier.check_license()
        if status == 'TRIAL':
            self.accept()  # Just continue
            return
            
        if self.verifier.start_trial():
            QMessageBox.information(self, "Trial Started", "15-Day Trial Started Successfully.\nYou can activate anytime during the trial.")
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "Could not start trial.")

    def activate(self):
        key = self.txt_key.text().strip()
        if not key:
            QMessageBox.warning(self, "Input Error", "Please enter a license key.")
            return
        
        # Debug logging
        app_logger.info(f"Activation attempt - HWID: {self.hwid}, Key: {key}")
        is_valid = self.verifier.verify_license(self.hwid, key)
        app_logger.info(f"Verification result: {is_valid}")
            
        if is_valid:
            self.verifier.save_license(key, self.hwid)
            QMessageBox.information(self, "Success", "Activation Successful!\nWelcome to SpareParts Pro.")
            self.accept()
        else:
            QMessageBox.critical(self, "Activation Failed", f"Invalid License Key.\nPlease check and try again.\n\nHWID: {self.hwid}\nKey: {key}")



def main():
    try:
        # App Setup
        app_logger.info("Application starting...")
        app = QApplication(sys.argv)
        
        # Styles
        from styles import get_stylesheet, COLOR_ACCENT_CYAN, COLOR_BACKGROUND  # type: ignore
        app.setStyleSheet(get_stylesheet())
        
        # Set App Icon (taskbar + window title) — read-only bundled asset
        icon_path = get_resource_path("logo.ico")
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
        
        # Palette fix for dark theme
        from PyQt6.QtGui import QPalette  # type: ignore
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(COLOR_BACKGROUND))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(COLOR_ACCENT_CYAN))
        palette.setColor(QPalette.ColorRole.Base, QColor(0, 0, 0))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(COLOR_BACKGROUND))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.Text, QColor(COLOR_ACCENT_CYAN))
        palette.setColor(QPalette.ColorRole.Button, QColor(COLOR_BACKGROUND))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(COLOR_ACCENT_CYAN))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
        palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(COLOR_ACCENT_CYAN))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))
        app.setPalette(palette)

        # Splash Screen
        from custom_components import SciFiSplashScreen  # type: ignore
        splash = SciFiSplashScreen()
        splash.show()
    
        # Container for loader results
        loader_data = {"db": None, "LoginWindow": None, "MainWindow": None, "Verifier": None}
    
        # Loader Thread
        loader = StartupLoader()
    
        # Connect signals
        loader.progress.connect(splash.update_progress)
    
        def on_loaded(db, LoginClass, MainClass, VerifierInstance):
            loader_data["db"] = db
            loader_data["LoginWindow"] = LoginClass
            loader_data["MainWindow"] = MainClass
            loader_data["Verifier"] = VerifierInstance
            
            # PRE-INSTANTIATE HERE to avoid lag later
            # We need to know if we are allowed to login first? 
            # Actually, we can instantiate LoginWindow, but whether we show it depends on License.
            # But wait, LoginWindow needs MainWindow class passed to it? 
            # Based on previous code: `self.login_window = LoginWindow(db_manager, MainWindow)`
            # Let's check LoginWindow signature if possible, but assuming standard.
            
            # We will handle License Check inside the transition logic below (after loop)
            # just store data here.
            
            # Use a temporary instance just to keep things warm if needed, or delay.
            # Let's delay instantiation of LoginWindow until after License Check to be safe/clean.
            pass
        
        loader.finished_loading.connect(on_loaded)
        loader.start()
    
        # Blocking Loop that processes events (keeps splash animated) 
        # while waiting for BOTH Splash Animation AND Loader to finish.
        loop = QEventLoop()
    
        def check_ready():
            # Check 1: Is Animation Done?
            if splash.is_finished: # Splash sets this flag when battery full
                 # Check 2: Is Loading Done?
                 if loader.isFinished():
                     loop.quit()
    
        # Connect splash finished signal to check
        splash.finished.connect(check_ready)
        # Connect loader finished to check (in case loader is slower than splash)
        loader.finished.connect(check_ready)
    
        # Start the wait loop
        loop.exec()
    
        # --- Transition to Login ---
        if not loader_data["db"] or not loader_data["LoginWindow"] or not loader_data["MainWindow"] or not loader_data["Verifier"]:
             app_logger.critical("Startup failed: Components not loaded.")
             sys.exit(1)
         
        db_manager = loader_data["db"]
        LoginWindow = loader_data["LoginWindow"]
        MainWindow = loader_data["MainWindow"]
        verifier = loader_data["Verifier"]
        
        # --- LICENSE CHECK UI ---
        # Close splash to show dialog cleanly
        splash.close()
        
        # --- NETWORK SETUP CHECK ---
        import db_config  # type: ignore
        if not db_config.config_exists():
            app_logger.info("No network config found. Showing Network Setup Dialog.")
            from network_setup import NetworkSetupDialog  # type: ignore
            net_dlg = NetworkSetupDialog()
            if not net_dlg.exec():
                app_logger.info("Network setup cancelled. Exiting.")
                sys.exit(0)
            
            # Re-initialize DB with new config if changed to CLIENT mode
            config = db_config.load_config()
            if config and config.get('mode') == 'CLIENT':
                from database_manager import DatabaseManager  # type: ignore
                new_path = db_config.get_db_path()
                app_logger.info(f"Client mode: reconnecting to {new_path}")
                db_manager = DatabaseManager(new_path)
                loader_data["db"] = db_manager
        
        # Generate Hardware ID
        from hardware_id import get_hardware_id  # type: ignore
        hwid = get_hardware_id()
        app_logger.info(f"Hardware ID: {hwid}")
        
        status, _ = verifier.check_license()  # type: ignore
        
        if status != 'ACTIVE':
            dlg = HardwareIDDialog(hwid, verifier)
            if not dlg.exec():
                app_logger.info("License Check Failed/Cancelled. Exiting.")
                sys.exit(0)
        
        # If we are here, License is Valid (Active or Trial)
    
        login = loader_data.get("login_instance")
        if not login:
             login = LoginWindow(db_manager, MainWindow) # type: ignore
    
        app_logger.info("Launching Login Window...")
    
        # SHOW LOGIN BEFORE CLOSING SPLASH (for zero gap)
        # But we need exec() to block... 
        # Trick: close splash right after exec starts? No, exec blocks.
        # Solution: Hide splash, show login.
    
        # DWM Dark Mode
    
        # DWM Dark Mode
        try:
             import ctypes
             DWMWA_USE_IMMERSIVE_DARK_MODE = 20
             set_window_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute  # type: ignore
             hwnd = int(login.winId())
             set_window_attribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(ctypes.c_int(1)), ctypes.sizeof(ctypes.c_int))
        except:
             pass
         
        login_state = {"authenticated": False, "role": "STAFF", "username": "staff"}
    
        def on_login_success(role, username):
            login_state["authenticated"] = True
            login_state["role"] = role
            login_state["username"] = username
        
        login.login_success.connect(on_login_success)
    
        if login:
             # Trick to close splash AFTER login window is actually shown
             # We queue the close call. It will execute when login.exec() starts its event loop.
             QTimer.singleShot(100, splash.close)
         
             if login.exec():
                 if login_state["authenticated"]:
                     app_logger.info(f"User authenticated as {login_state['role']}. Launching Main Window.")
                     login.deleteLater() # Cleanup login window
                     # Show Main Window only if authenticated
                     window = MainWindow(db_manager, login_state["role"], login_state["username"])  # type: ignore
                
                     # Fade In Logic or Delayed Show
                     # window.setWindowOpacity(0) # Removed as per user request
                     # DWM Dark Mode Hack (Applied correctly this time)
                     try:
                         import ctypes
                         DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                         set_window_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute  # type: ignore
                         hwnd = int(window.winId())
                         set_window_attribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(ctypes.c_int(1)), ctypes.sizeof(ctypes.c_int))
                     except Exception as e:
                         app_logger.warning(f"Failed to set Windows Dark Mode: {e}")
    
                     # Show - Force a repaint before showing to avoid white flash
                     window.setWindowOpacity(0)
                     window.show()
                     window.repaint()
                     QTimer.singleShot(50, lambda: window.setWindowOpacity(1)) # Short delay to let paint happen
                
                     # Removed fade-in logic, instant show after paint
                     sys.exit(app.exec())
                 else:
                     app_logger.warning("Login dialog finished but not authenticated.")
                     sys.exit(0)
             else:
                 app_logger.info("Login cancelled. Exiting.")
                 sys.exit(0)
        
    except Exception as e:
        msg = f"Unhandled exception in main loop: {e}"
        app_logger.critical(msg, exc_info=True)
        try:
            from PyQt6.QtWidgets import QMessageBox  # type: ignore
            QMessageBox.critical(None, "Application Error", f"A critical error occurred:\n\n{e}\n\nCheck logs for details.")
        except:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()
