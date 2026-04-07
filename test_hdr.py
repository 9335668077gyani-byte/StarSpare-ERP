import sys, os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
sys.path.insert(0, os.getcwd())
import catalog_page, db_engine
app = QApplication(sys.argv)
db_p = os.path.join(os.getcwd(), "temp_test.db")
db_engine.initialize_database(db_p)
class DummyDB:
    def get_shop_settings(self): return {"nexses_catalog_db": db_p}
    def update_setting(self, k, v): pass
page = catalog_page.CatalogPage(DummyDB())
print("ALL PARTS Cols:", page.all_parts_table.columnCount())
print("ALL PARTS Col 1:", page.all_parts_table.horizontalHeaderItem(1).text() if page.all_parts_table.horizontalHeaderItem(1) else page.all_parts_table.model().headerData(1, Qt.Orientation.Horizontal))
print("CATALOG VIEW Cols:", page.data_table.columnCount())
print("CATALOG VIEW Col 1:", page.data_table.horizontalHeaderItem(1).text() if page.data_table.horizontalHeaderItem(1) else page.data_table.model().headerData(1, Qt.Orientation.Horizontal))
