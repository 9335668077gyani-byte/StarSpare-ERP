
import sqlite3
import json

db_path = "data/spareparts_pro.db"

def inspect_invoices():
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT invoice_id, json_items FROM invoices ORDER BY date DESC LIMIT 5")
        rows = cursor.fetchall()
        
        print(f"Found {len(rows)} invoices.")
        for row in rows:
            inv_id = row[0]
            json_str = row[1]
            print(f"\n--- Invoice {inv_id} ---")
            try:
                items = json.loads(json_str)
                print(f"  Type: {type(items)}")
                print(f"  Content: {items}")
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            print(f"    Item: {item.get('name')} | Price: {item.get('price')} | Qty: {item.get('qty')}")
                        else:
                            print(f"    Non-dict item: {item}")
                else:
                    print("  Not a list!")
            except json.JSONDecodeError:
                print(f"  Invalid JSON: {json_str}")
                
        cursor.execute("SELECT * FROM parts WHERE part_name LIKE '%Labo%' OR part_name LIKE '%Servic%'")
        parts = cursor.fetchall()
        print(f"\n--- Potential Labor Parts ---")
        for p in parts:
             print(f"  ID: {p[0]} | Name: {p[1]}")

        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_invoices()
