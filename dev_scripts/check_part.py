import sqlite3
import json

db_file = 'data/spareparts_pro.db'
try:
    db = sqlite3.connect(db_file)
    c = db.cursor()
    
    # Dump PRAGMA to be sure
    c.execute('PRAGMA table_info(parts)')
    cols = c.fetchall()
    print("Columns:")
    for col in cols:
        print(col)
        
    c.execute("SELECT * FROM parts WHERE part_id = 'N91151005D'")
    row = c.fetchone()
    print("\nRow for N91151005D:")
    if row:
        for i, val in enumerate(row):
            print(f"[{i}]: {val}")
    else:
        print("Not found")
except Exception as e:
    print(f"Error: {e}")
