import sqlite3
import json

db_file = 'data/spareparts_pro.db'
try:
    db = sqlite3.connect(db_file)
    c = db.cursor()
    c.execute("SELECT invoice_id, json_items FROM invoices WHERE invoice_id LIKE '%1076%'")
    rows = c.fetchall()
    for row in rows:
        print(f"--- FOUND IN {db_file}: {row[0]} ---")
        try:
            data = json.loads(row[1])
            print(json.dumps(data, indent=2))
        except:
            print(row[1])
except Exception as e:
    print(f"Error: {e}")
