import sqlite3
import sys

def check_dates():
    try:
        conn = sqlite3.connect('c:/MY PROJECTS/spare_ERP/data/spareparts_pro.db', timeout=10)
        cursor = conn.cursor()
        cursor.execute("SELECT part_id, added_date, last_edited_date FROM parts LIMIT 10")
        rows = cursor.fetchall()
        for r in rows:
            print(f"ID: {r[0]}, Added: '{r[1]}', Edited: '{r[2]}'")
            
        cursor.execute("SELECT part_id, last_edited_date FROM parts WHERE last_edited_date IS NOT NULL AND last_edited_date != '' LIMIT 5")
        edited = cursor.fetchall()
        print(f"\nFound {len(edited)} explicitly edited items:")
        for r in edited:
            print(f"ID: {r[0]}, Edited: '{r[1]}'")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    check_dates()
