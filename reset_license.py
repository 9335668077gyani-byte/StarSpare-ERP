"""
Reset License Status Utility
For SpareParts Pro ERP System

This utility resets the license status to allow testing of the activation system.
Run this before launching the app to see the activation dialog.
"""

import sqlite3
import sys
import os

db_path = os.path.join("data", "spareparts_pro.db")

if not os.path.exists(db_path):
    print(f"❌ Database not found at: {db_path}")
    input("Press Enter to exit...")
    sys.exit(1)

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check current status
    cursor.execute("SELECT status, license_key, hardware_id FROM app_license LIMIT 1")
    row = cursor.fetchone()
    
    if row:
        print("=" * 60)
        print(" LICENSE STATUS - CURRENT")
        print("=" * 60)
        print(f"   Status: {row[0]}")
        print(f"   License Key: {row[1] or 'None'}")
        print(f"   Hardware ID: {row[2] or 'None'}")
        print()
    
    print("Choose an option:")
    print("1. Reset to NEW (shows activation dialog on next launch)")
    print("2. Reset to TRIAL (15 days, can still activate)")
    print("3. Set to EXPIRED (forces activation)")
    print("4. Cancel")
    print()
    
    choice = input("Enter choice (1-4): ").strip()
    
    if choice == "1":
        conn.execute("""
            UPDATE app_license 
            SET status = 'NEW', 
                license_key = NULL, 
                hardware_id = NULL,
                trial_start_date = NULL,
                trial_end_date = NULL,
                activation_date = NULL
            WHERE id = (SELECT id FROM app_license LIMIT 1)
        """)
        conn.commit()
        print("\n✓ License reset to NEW status.")
        print("  Launch the app to see the activation dialog!")
        
    elif choice == "2":
        from datetime import datetime, timedelta
        now = datetime.now()
        end_date = now + timedelta(days=15)
        
        start_str = now.strftime("%Y-%m-%d %H:%M:%S")
        end_str = end_date.strftime("%Y-%m-%d %H:%M:%S")
        
        conn.execute("""
            UPDATE app_license 
            SET status = 'TRIAL', 
                license_key = NULL,
                hardware_id = NULL,
                trial_start_date = ?,
                trial_end_date = ?,
                activation_date = NULL
            WHERE id = (SELECT id FROM app_license LIMIT 1)
        """, (start_str, end_str))
        conn.commit()
        print(f"\n✓ License reset to TRIAL (15 days).")
        print(f"  Trial expires: {end_str}")
        print("  Launch the app to see trial status and activate option!")
        
    elif choice == "3":
        from datetime import datetime
        expired_date = "2020-01-01 00:00:00"
        
        conn.execute("""
            UPDATE app_license 
            SET status = 'EXPIRED', 
                license_key = NULL,
                hardware_id = NULL,
                trial_start_date = '2020-01-01 00:00:00',
                trial_end_date = ?,
                activation_date = NULL
            WHERE id = (SELECT id FROM app_license LIMIT 1)
        """, (expired_date,))
        conn.commit()
        print("\n✓ License set to EXPIRED.")
        print("  Launch the app - activation will be REQUIRED!")
        
    else:
        print("\n✓ No changes made.")
    
    conn.close()
    
except Exception as e:
    print(f"\n❌ Error: {e}")

print()
print("=" * 60)
input("Press Enter to exit...")
