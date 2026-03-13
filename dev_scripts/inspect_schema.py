
import sqlite3
import os

DB_PATH = r"c:\Users\Admin\Desktop\spare_ERP\data\spareparts_pro.db"

if not os.path.exists(DB_PATH):
    print(f"DB not found at {DB_PATH}")
    exit(1)

print(f"Connecting to {DB_PATH}")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("Checking Schema for 'parts' table...")
try:
    cursor.execute("PRAGMA table_info(parts)")
    columns = cursor.fetchall()
    for col in columns:
        print(col)
        
except Exception as e:
    print(f"Error: {e}")

conn.close()
