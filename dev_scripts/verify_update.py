import sqlite3
from database_manager import DatabaseManager
import os
import time

DB_PATH = "spareparts.db"
if not os.path.exists(DB_PATH):
    print("WARNING: spareparts.db not found, using test DB")
    DB_PATH = "test_verify_update.db"
    
print(f"Using DB: {DB_PATH}")
db = DatabaseManager(DB_PATH)

# 1. Add VENDOR
v_name = f"UpdateTest_{int(time.time())}"
print(f"Adding Vendor: {v_name}")
db.add_vendor(v_name, "Rep1", "Phone1", "Addr1", "GST1", "Note1")

# 2. Verify Initial
v = db.get_vendor_details(v_name)
print(f"Initial: {v}")
assert v[2] == "Rep1"
assert v[6] == "Note1"

# 3. UPDATE VENDOR
print("Updating Vendor...")
# v[0] is ID
new_rep = "Rep_Updated"
new_gst = "GST_Updated"
new_note = "Note_Updated"
success, msg = db.update_vendor(v[0], v_name, new_rep, "Phone1", "Addr1", new_gst, new_note)
print(f"Update Result: {success} - {msg}")
assert success

# 4. Verify Persistence (Immediate Read)
v_new = db.get_vendor_details(v_name)
print(f"Updated: {v_new}")

if v_new[2] != new_rep:
    print(f"❌ FAIL: Rep Name mismatch. Expected '{new_rep}', Got '{v_new[2]}'")
else:
    print("✅ Rep Name Verified")

if v_new[5] != new_gst:
    print(f"❌ FAIL: GSTIN mismatch. Expected '{new_gst}', Got '{v_new[5]}'")
else:
    print("✅ GSTIN Verified")

if v_new[6] != new_note:
    print(f"❌ FAIL: Notes mismatch. Expected '{new_note}', Got '{v_new[6]}'")
else:
    print("✅ Notes Verified")

# 5. Verify List Order (get_all_vendors)
print("Checking get_all_vendors order...")
all_v = db.get_all_vendors()
target = None
for row in all_v:
    if row[1] == v_name:
        target = row
        break
        
print(f"List Row: {target}")
if target[2] == new_rep and target[6] == new_note:
    print("✅ List View Verified")
else:
    print("❌ List View Failed")
