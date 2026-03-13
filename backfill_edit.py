from datetime import datetime
import sqlite3

conn = sqlite3.connect('C:/Users/Admin/Desktop/spare_ERP/data/spareparts_pro.db')
cursor = conn.cursor()
current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

cursor.execute("UPDATE parts SET last_edited_date = ? WHERE part_id = ?", (current_time, 'N9325190'))
conn.commit()

cursor.execute("SELECT part_id, last_edited_date FROM parts WHERE part_id = ?", ('N9325190',))
print(cursor.fetchall())
conn.close()
