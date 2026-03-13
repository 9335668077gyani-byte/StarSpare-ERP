import pandas as pd
import sqlite3
import os
from database_manager import DatabaseManager

db = DatabaseManager(r"data/spareparts_pro.db")
csv_path = "parts_inventory.csv"

# Configure logger to output to console for this script
import logging
import sys
logging.getLogger("SpareERP").addHandler(logging.StreamHandler(sys.stdout))

print(f"Testing import from {csv_path}")
if not os.path.exists(csv_path):
    print("CSV not found!")
    exit()

try:
    df = pd.read_csv(csv_path)
    print("CSV Read Success")
    print("Columns Found:", df.columns.tolist())
    print("First row:", df.iloc[0].tolist())
    
    if len(df.columns) < 7:
        print(f"Error: Not enough columns. Found {len(df.columns)}")
    else:
        print("Column count OK.")
        if len(df.columns) >= 9:
            print("Extended columns (Reorder/Vendor) detected.")

    success = db.import_inventory_data(csv_path)
    if success:
        print("Import Function Returned TRUE")
        # Verify first item
        first_id = str(df.iloc[0,0])
        part = db.get_part_by_id(first_id)
        print(f"Verification for {first_id}: {part}")
    else:
        print("Import Function Returned FALSE")

except Exception as e:
    print(f"Outer Exception: {e}")
