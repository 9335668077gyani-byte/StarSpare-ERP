import os
from database_manager import DatabaseManager

db_path = os.path.join("data", "spareparts_pro.db")
db = DatabaseManager(db_path)

print("--- get_shop_settings() ---")
print(db.get_shop_settings())

print("\n--- RAW SETTINGS TABLE ---")
conn = db.get_connection()
cursor = conn.cursor()
cursor.execute("SELECT key, value FROM settings")
for row in cursor.fetchall():
    print(f"{row[0]}: {row[1]}")
conn.close()
