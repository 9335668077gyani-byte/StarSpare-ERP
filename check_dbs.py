import sqlite3
import os

def check_db(path):
    print(f"\nChecking: {path}")
    if not os.path.exists(path):
        print("  -> File not found!")
        return
    try:
        conn = sqlite3.connect(path)
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM settings WHERE key IN ('invoice_theme', 'invoice_format')")
        for row in cur.fetchall():
            print(f"  -> {row[0]}: {row[1]}")
        conn.close()
    except Exception as e:
        print(f"  -> Error: {e}")

print("=== DATABASE CHECK ===")
check_db(r"c:\Users\Admin\Desktop\spare_ERP\data\spareparts_pro.db")
check_db(r"c:\Users\Admin\AppData\Roaming\SparePartsPro_v1.5\data\spareparts_pro.db")
print("======================")
