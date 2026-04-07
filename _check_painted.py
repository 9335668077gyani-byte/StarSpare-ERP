import sqlite3

conn = sqlite3.connect('nexses_ecatalog.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Find vehicle_id for Apache RTR 160 4V
cur.execute("SELECT vehicle_id, segment, model_name FROM vehicles_master WHERE model_name LIKE '%Apache%' OR model_name LIKE '%RTR%'")
vehicles = cur.fetchall()
print("=== VEHICLES for Apache ===")
for v in vehicles:
    print(dict(v))

# Check how many parts for first vehicle, broken down by type
if vehicles:
    vid = vehicles[0]['vehicle_id']
    print(f"\n=== PARTS for vehicle_id={vid} ===")
    cur.execute("""
        SELECT COUNT(*), 
               SUM(CASE WHEN UPPER(pm.category) LIKE 'PAINTED PARTS%' THEN 1 ELSE 0 END) as painted,
               SUM(CASE WHEN UPPER(pm.category) NOT LIKE 'PAINTED PARTS%' THEN 1 ELSE 0 END) as spare
        FROM compatibility_map cm
        JOIN parts_master pm ON pm.part_code = cm.part_code
        WHERE cm.vehicle_id = ?
    """, (vid,))
    row = cur.fetchone()
    print(f"Total: {row[0]}, Painted: {row[1]}, Spare: {row[2]}")

# Also check Raider 125
cur.execute("SELECT vehicle_id, segment, model_name FROM vehicles_master WHERE model_name LIKE '%Raider%' OR model_name LIKE '%RAIDER%'")
raiders = cur.fetchall()
print("\n=== VEHICLES for Raider ===")
for v in raiders:
    print(dict(v))
    vid = v['vehicle_id']
    cur.execute("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN UPPER(pm.category) LIKE 'PAINTED PARTS%' THEN 1 ELSE 0 END) as painted,
               SUM(CASE WHEN UPPER(pm.category) NOT LIKE 'PAINTED PARTS%' THEN 1 ELSE 0 END) as spare
        FROM compatibility_map cm
        JOIN parts_master pm ON pm.part_code = cm.part_code
        WHERE cm.vehicle_id = ?
    """, (vid,))
    row = cur.fetchone()
    print(f"  -> Total: {row[0]}, Painted: {row[1]}, Spare: {row[2]}")

conn.close()
