import sqlite3
conn = sqlite3.connect('c:/Users/Admin/Desktop/spare_ERP/data/spareparts_pro.db')
for row in conn.execute("SELECT key, value FROM settings WHERE key LIKE 'invoice_%'"):
    print(row)
