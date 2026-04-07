import sys
import os
sys._MEIPASS = os.path.abspath(".")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from database_manager import DatabaseManager
from main_window import MainWindow

app = QApplication(sys.argv)
db = DatabaseManager('test_crash.db')
try:
    mw = MainWindow('admin', db)
    mw.show()
    print("MainWindow shown OK")
except Exception as e:
    import traceback
    traceback.print_exc()
QTimer.singleShot(1000, app.quit)
sys.exit(app.exec())
