
import sqlite3
import os

# Confirmed path
DB_PATH = r"c:\Users\Admin\Desktop\spare_ERP\data\spareparts_pro.db"

if not os.path.exists(DB_PATH):
    print(f"DB not found at {DB_PATH}")
    exit(1)

print(f"Connecting to {DB_PATH}")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

query = """
    SELECT 
        SUM(CAST(unit_price AS REAL) * CAST(qty AS INTEGER)),
        SUM(CAST(qty AS INTEGER)),
        COUNT(*),
        SUM(CASE WHEN CAST(qty AS INTEGER) <= CAST(reorder_level AS INTEGER) THEN 1 ELSE 0 END),
        COUNT(DISTINCT vendor_name)
    FROM parts
"""

print("Running Query...")
try:
    cursor.execute(query)
    result = cursor.fetchone()
    print(f"Result Tuple: {result}")
    
    if result:
        # Check carefully for 0
        stats = {
            "total_val": result[0] or 0.0,
            "total_stock": result[1] or 0,
            "part_count": result[2] or 0,
            "low_stock_count": result[3] or 0,
            "vendor_count": result[4] or 0
        }
        print(f"Stats Dict: {stats}")
    else:
        print("No result returned.")
        
except Exception as e:
    print(f"Error: {e}")

conn.close()
