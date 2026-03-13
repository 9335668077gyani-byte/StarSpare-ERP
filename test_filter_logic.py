import sys
import os
from datetime import datetime

# Add path so we can import modules
sys.path.append('C:/Users/Admin/Desktop/spare_ERP')

import database_manager
db = database_manager.DatabaseManager()
rows = db.get_all_parts()

print(f"Total parts: {len(rows)}")
edited_count = 0
today = datetime.now()

for r in rows:
    # Mimic filter_table logic
    if len(r) > 14:
        edited_date_str = r[14]
        is_edited = False
        if edited_date_str:
            try:
                e_str = str(edited_date_str).strip()
                d_obj = None
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                    try:
                        d_obj = datetime.strptime(e_str, fmt)
                        break
                    except ValueError:
                        continue
                if d_obj and (today - d_obj).total_seconds() <= 86400:  # 24h
                    is_edited = True
            except:
                pass
        
        if is_edited:
            edited_count += 1
            print(f"EDITED MATCH: {r[0]} | Date: {edited_date_str}")
    else:
        print(f"Row too short: {len(r)}")

print(f"Total Edited Matched: {edited_count}")
