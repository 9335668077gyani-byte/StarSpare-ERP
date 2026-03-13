import sys
import os

sys.path.append(os.getcwd())
from database_manager import DatabaseManager

def inspect():
    db = DatabaseManager('data/spareparts_pro.db')
    print("--- Inspecting Expenses ---")
    rows = db.get_all_expenses(None, None)
    for r in rows:
        print(f"ID: {r[0]} | Title: {r[1]} | Amt: {r[2]}")
        
    print(f"Total rows: {len(rows)}")

if __name__ == "__main__":
    inspect()
