import pandas as pd
import json
import re
from collections import OrderedDict
import time

file_path = 'VENDOR DATA PART.xlsx'

print(f"Reading {file_path}...")
start_time = time.time()

try:
    df = pd.read_excel(file_path)
    print(f"Read {len(df)} rows in {time.time() - start_time:.2f}s")
    
    # Simulate Thread Logic
    # 1. Normalize Columns
    original_columns = [str(c).strip() for c in df.columns]
    df.columns = [str(c).strip().lower() for c in df.columns]
    col_name_map = {norm: orig for norm, orig in zip(df.columns, original_columns)}
    
    # 2. Find Cols
    def find_col(keywords, exclude=None):
        if exclude is None: exclude = set()
        candidates = [c for c in df.columns if c not in exclude]
        # Pass 1: Exact
        for k in keywords:
            if k in candidates: return k
        # Pass 2: Word boundary
        for k in keywords:
            pattern = r'(?:^|[\s_\-])' + re.escape(k) + r'(?:$|[\s_\-])'
            for col in candidates:
                if re.search(pattern, col): return col
        # Pass 3: Starts with
        for k in keywords:
            for col in candidates:
                if col.startswith(k): return col
        # Pass 4: Substring
        for k in keywords:
            if len(k) >= 4:
                for col in candidates:
                    if k in col: return col
        return None

    col_name = find_col(['part name', 'part_name', 'partname', 'name', 'description', 'item name', 'item'])
    found = {col_name} if col_name else set()
    col_id = find_col(['part code', 'part_code', 'partcode', 'part id', 'part_id', 'partid', 'sr no', 'sr.no', 'sno', 'code'], exclude=found)
    found.add(col_id)
    col_price = find_col(['mrp', 'price', 'rate', 'cost', 'amount', 'unit price', 'unit_price'], exclude=found)
    found.add(col_price)
    col_qty = find_col(['qty', 'quantity', 'stock', 'pack', 'moq'], exclude=found)
    found.add(col_qty)
    found.discard(None)
    
    print(f"Mapped Columns: Name={col_name}, ID={col_id}, Price={col_price}, Qty={col_qty}")
    
    extra_cols = [c for c in df.columns if c not in found]
    print(f"Extra Columns: {len(extra_cols)}")
    
    # 3. Aggregation Loop (UPDATED LOGIC)
    aggregated = OrderedDict()
    processed = 0
    total_rows = len(df)
    
    print("Starting Aggregation Loop (ID Priority)...")
    loop_start = time.time()
    
    for _, row in df.iterrows():
        processed += 1
        
        name = str(row[col_name]).strip() if col_name else ""
        if not name or name.lower() in ['nan', 'none', '']: continue
        
        p_id = str(row[col_id]).strip() if col_id else "NEW"
        if p_id.lower() in ['nan', 'none', '']: p_id = "NEW"
        
        # ... (price/qty/extra logic same as before) ...
        price = 0.0
        if col_price:
            try: price = float(row[col_price])
            except: price = 0.0
            
        sheet_qty = 0
        if col_qty:
            try: sheet_qty = int(float(row[col_qty]))
            except: sheet_qty = 0
            
        extra_data = {}
        for ec in extra_cols:
            val = row[ec]
            if pd.notna(val):
                extra_data[col_name_map.get(ec, ec)] = str(val).strip()
            else:
                extra_data[col_name_map.get(ec, ec)] = ""
        
        extra_json = json.dumps(extra_data) if extra_data else None

        # NEW LOGIC: Key by ID if valid, else Name
        if p_id != "NEW":
            key = p_id.lower()
        else:
            key = name.lower()

        if key in aggregated:
            aggregated[key]["qty"] += sheet_qty
            if price > 0: aggregated[key]["price"] = price
            # If we keyed by ID, p_id is already set. 
            # If we keyed by Name, we might update p_id if we found one now (unlikely if logic holds)
            if p_id != "NEW": aggregated[key]["p_id"] = p_id 
            
            if extra_data:
                aggregated[key]["extra"].update(extra_data)
                aggregated[key]["extra_json"] = json.dumps(aggregated[key]["extra"])
        else:
            aggregated[key] = {
                "p_id": p_id, "name": name, "price": price,
                "qty": sheet_qty, "extra": extra_data, "extra_json": extra_json
            }
            
        if processed % 1000 == 0:
            print(f"Processed {processed} rows...")

    print(f"Aggregation Complete. Total Unique Items: {len(aggregated)}")
    print(f"Loop Time: {time.time() - loop_start:.2f}s")
    
    # 4. Preparing Save List
    items_to_save = []
    for key, data in aggregated.items():
        items_to_save.append((data["p_id"], data["name"], data["price"], data["qty"], data["extra_json"]))

    print(f"Items to save: {len(items_to_save)}")
    
    # 5. Simulate DB Save
    from database_manager import DatabaseManager
    db = DatabaseManager("test_inventory_repro.db")
    
    print("Saving to DB...")
    success, msg = db.save_catalog_items_bulk("Test Vendor", items_to_save)
    print(f"DB Save Result: {success}, {msg}")

except Exception as e:
    print(f"CRITICAL ERROR: {e}")
    import traceback
    traceback.print_exc()
