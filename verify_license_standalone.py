
import sys
import os
from PyQt6.QtWidgets import QApplication
from database_manager import DatabaseManager
from license_manager import LicenseVerifier
from license_dialog import LicenseDialog

# Setup Test DB to avoid affecting main DB
db_path = "test_license.db"
if os.path.exists(db_path):
    os.remove(db_path)

db = DatabaseManager(db_path)
verifier = LicenseVerifier(db)

app = QApplication(sys.argv)

print("--- TEST 1: NEW INSTALL ---")
status, _ = verifier.check_license()
print(f"Status: {status} (Expected: NEW)")
if status != 'NEW':
    print("FAIL")
    sys.exit(1)

dlg = LicenseDialog(verifier)
print("Launching Dialog... Click 'Start Trial'")
if dlg.exec():
    print("Dialog Accepted.")
else:
    print("Dialog Rejected/Cancelled.")

print("--- TEST 2: TRIAL ACTIVE ---")
status, days = verifier.check_license()
print(f"Status: {status}, Days Left: {days} (Expected: TRIAL, 14 or 15)")
if status != 'TRIAL':
    print("FAIL")

print("--- TEST 3: EXPIRED (Simulated) ---")
# Manually expire
conn = db.get_connection()
conn.execute("UPDATE app_license SET trial_end_date = '2020-01-01 00:00:00', status = 'TRIAL'")
conn.commit()
conn.close()

status, _ = verifier.check_license() # Should update to EXPIRED
print(f"Status: {status} (Expected: EXPIRED)")

print("Launching Dialog... Try entering key 'PRO-ADMIN-2025'")
dlg_exp = LicenseDialog(verifier)
if dlg_exp.exec():
    print("Activated!")
else:
    print("Cancelled.")

print("--- TEST 4: ACTIVE ---")
status, _ = verifier.check_license()
print(f"Status: {status} (Expected: ACTIVE)")

if os.path.exists(db_path):
    print("Cleaning up...")
    # os.remove(db_path) # Keep for inspection if needed

sys.exit(0)
