
import sqlite3
import os

DB_PATH = os.path.join("data", "spareparts_pro.db")

def check_vendors():
    if not os.path.exists(DB_PATH):
        print(f"DB not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT part_id, part_name, vendor_name FROM parts LIMIT 20")
    rows = cursor.fetchall()
    
    print(f"Checking first 20 parts in {DB_PATH}:")
    print(f"{'ID':<15} {'Name':<30} {'Vendor':<20}")
    print("-" * 65)
    for r in rows:
        v = r[2] if r[2] else "[EMPTY]"
        print(f"{r[0]:<15} {r[1]:<30} {v:<20}")
        
    conn.close()

if __name__ == "__main__":
    check_vendors()
