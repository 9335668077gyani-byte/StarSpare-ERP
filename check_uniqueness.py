import pandas as pd
import openpyxl

file_path = 'VENDOR DATA PART.xlsx'

try:
    print(f"Reading {file_path}...")
    df = pd.read_excel(file_path)
    
    print(f"Total Rows: {len(df)}")
    
    # Try multiple column names for ID/Code
    id_col = None
    for c in df.columns:
        c_clean = str(c).strip().lower()
        if c_clean in ['part code', 'part_code', 'partcode', 'part id', 'part_id', 'code', 'id']:
            id_col = c
            break
            
    # Try multiple column names for Name
    name_col = None
    for c in df.columns:
        c_clean = str(c).strip().lower()
        if c_clean in ['part name', 'part_name', 'partname', 'name', 'description']:
            name_col = c
            break
            
    if id_col:
        unique_ids = df[id_col].dropna().unique()
        print(f"Unique Part IDs: {len(unique_ids)}")
    else:
        print("Could not find ID column")

    if name_col:
        unique_names = df[name_col].dropna().unique()
        print(f"Unique Part Names: {len(unique_names)}")
    else:
        print("Could not find Name column")

except Exception as e:
    print(f"Error: {e}")
