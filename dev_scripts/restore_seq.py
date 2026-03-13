import sys
import os

sys.path.append(os.getcwd())
from database_manager import DatabaseManager

def restore():
    db = DatabaseManager('data/spareparts_pro.db')
    try:
        success, msg = db.set_invoice_sequence(1054)
        if success:
            print(f"SUCCESS: Sequence restored to 1054")
        else:
            print(f"FAILED: {msg}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    restore()
