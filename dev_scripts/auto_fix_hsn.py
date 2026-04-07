import os
import sys
import csv

# Ensure imports work from parent dir
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database_manager import DatabaseManager

def main():
    print("Initializing Database Manager...")
    db = DatabaseManager('spare_erp.db')
    
    parts = db.get_all_parts()
    if not parts:
        print("No parts found in the database. Exiting.")
        return

    # Assuming index positions based on earlier query inspection
    # 0:part_id, 1:part_name, 2:description, ..., 15:hsn_code, 16:gst_rate
    missing_hsn_parts = []
    
    print("Scanning for parts with missing HSN Codes...")
    for part in parts:
        hsn_code = str(part[15]).strip() if len(part) > 15 and part[15] is not None else ""
        if not hsn_code:
            missing_hsn_parts.append(part)
            
    if not missing_hsn_parts:
        print("Excellent! All parts already have HSN Codes assigned.")
        return
        
    print(f"Found {len(missing_hsn_parts)} parts missing HSN Codes. Generating suggestions...")
    
    suggestions = []
    for p in missing_hsn_parts:
        p_id = p[0]
        p_name = p[1]
        p_cat = p[10] if len(p) > 10 else ""
        
        # Determine best search term
        term = p_name.strip() if p_name.strip() else p_cat.strip()
        
        if len(term) >= 3:
            rule = db.search_hsn_rule(term)
        else:
            rule = None
            
        suggested_hsn = rule['hsn_code'] if rule else ""
        suggested_gst = rule['gst_rate'] if rule else ""
        
        suggestions.append({
            'Part ID': p_id,
            'Part Name': p_name,
            'Category': p_cat,
            'Suggested HSN': suggested_hsn,
            'Suggested GST%': suggested_gst,
            'Action Needed': "Review and update DB" if suggested_hsn else "Manual lookup required"
        })
        
    csv_file = os.path.join(os.path.dirname(__file__), 'hsn_suggestions.csv')
    try:
        with open(csv_file, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['Part ID', 'Part Name', 'Category', 'Suggested HSN', 'Suggested GST%', 'Action Needed'])
            writer.writeheader()
            writer.writerows(suggestions)
        print(f"\n✅ Safe Execution Complete: Output written to {csv_file}")
    except Exception as e:
        print(f"Error writing CSV: {e}")

if __name__ == "__main__":
    main()
