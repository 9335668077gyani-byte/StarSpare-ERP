
import sqlite3
import os
from datetime import datetime, timedelta

def verify_new_items():
    db_path = r"c:\Users\Admin\Desktop\spare_ERP\data\spareparts_pro.db"
    
    if not os.path.exists(db_path):
        print(f"DB not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check parts with added_date
    cursor.execute("SELECT part_id, part_name, added_date FROM parts")
    rows = cursor.fetchall()
    
    print(f"Total parts: {len(rows)}")
    
    today = datetime.now()
    new_count = 0
    
    print("\n--- Items considered 'NEW' (< 7 days) ---")
    for r in rows:
        added = r[2]
        if added:
            try:
                # Handle potential formats
                d_str = added.split(" ")[0]
                d_obj = datetime.strptime(d_str, "%Y-%m-%d")
                delta = (today - d_obj).days
                if delta <= 7:
                    print(f"[NEW] {r[1]} (ID: {r[0]}) - Added: {added} ({delta} days ago)")
                    new_count += 1
                else:
                    # print(f"[OLD] {r[1]} - Added: {added} ({delta} days ago)")
                    pass
            except Exception as e:
                print(f"Error parsing date for {r[1]}: {added} - {e}")
                
    print(f"\nTotal NEW items: {new_count}")
    
    if new_count == 0:
        print("No new items found. You might want to add one to test the indicator.")
        # Optional: Insert a dummy new item? 
        # Better not mess with DB unless asked.

    conn.close()

if __name__ == "__main__":
    verify_new_items()
