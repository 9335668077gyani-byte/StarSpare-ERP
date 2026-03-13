import sys
import os
from PyQt6.QtWidgets import QApplication

# Add current dir to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database_manager import DatabaseManager
from logger import app_logger

def verify_pages():
    app_logger.info("Starting Full Flow Verification...")
    
    # Mock App
    app = QApplication(sys.argv)
    
    # Mock DB
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "spareparts_pro.db")
    db = DatabaseManager(db_path)
    
    pages_to_check = [
        ("DashboardPage", "dashboard_page"),
        ("BillingPage", "billing_page"),
        ("InventoryPage", "inventory_page"),
        ("ReportsPage", "reports_page"), 
        ("ExpensePage", "expense_page"),
        ("PurchaseOrderPage", "purchase_order_page"),
        ("UserManagementPage", "user_management_page"),
        ("SettingsPage", "settings_page")
    ]
    
    success_count = 0
    
    for class_name, module_name in pages_to_check:
        try:
            app_logger.info(f"Verifying {class_name}...")
            import importlib
            module = importlib.import_module(module_name)
            page_class = getattr(module, class_name)
            
            # Instantiate with DB
            if class_name == "InventoryPage":
                 page = page_class(db, "ADMIN")
            else:
                 page = page_class(db)
            
            app_logger.info(f"✅ {class_name} Instantiated Successfully.")
            success_count += 1
            
        except Exception as e:
            app_logger.critical(f"❌ FAILED to instantiate {class_name}: {e}")
            import traceback
            traceback.print_exc()

    if success_count == len(pages_to_check):
        print("\n✅ ALL PAGES VERIFIED SUCCESSFULLY!")
    else:
        print(f"\n⚠️ {len(pages_to_check) - success_count} PAGES FAILED VERIFICATION.")

if __name__ == "__main__":
    verify_pages()
