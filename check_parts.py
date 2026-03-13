import sqlite3
conn = sqlite3.connect("spare_parts.db")
cursor = conn.execute("PRAGMA table_info(parts)")
for col in cursor.fetchall():
    print(col[0], col[1])
