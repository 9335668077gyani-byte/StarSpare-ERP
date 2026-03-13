import sqlite3
conn = sqlite3.connect('C:/Users/Admin/Desktop/spare_ERP/data/spareparts_pro.db')
cursor = conn.cursor()
cursor.execute('SELECT part_id, last_edited_date, added_date, part_name FROM parts ORDER BY added_date DESC LIMIT 10')
for row in cursor.fetchall():
    print(row)
