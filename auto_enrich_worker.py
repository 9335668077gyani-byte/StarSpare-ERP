import time
from PyQt6.QtCore import QThread, pyqtSignal
from vehicle_compat_engine import local_vehicle_match, nexses_catalog_lookup, brand_extract_fallback

class AutoEnrichWorker(QThread):
    """
    Silent background worker that fetches category, compatibility, and tax 
    data for newly received PO items WITHOUT overwriting any manual user edits.
    """
    finished = pyqtSignal(int)  # emits number of parts enriched

    def __init__(self, db_manager, part_ids):
        super().__init__()
        self.db_manager = db_manager
        self.part_ids = list(set(part_ids))  # deduplicate

    def run(self):
        if not self.part_ids:
            self.finished.emit(0)
            return

        enriched_count = 0
        settings = self.db_manager.get_shop_settings() or {}
        catalog_db = settings.get("nexses_catalog_db", "")
        
        # Load local tax rules for smart matching
        hsn_rules = self.db_manager.get_hsn_rules()

        def _guess_hsn(name, category, current_hsn, current_gst):
            if current_hsn and current_gst > 0:
                return current_hsn, current_gst
            
            # Simple keyword matching based on hsn_rules
            text_to_search = f"{name} {category}".upper()
            best_hsn = current_hsn or ""
            best_gst = current_gst or 18.0
            
            for rule in hsn_rules:
                # rule length is 6: id, keyword, category, hsn_code, gst_rate, priority
                if len(rule) >= 5:
                    pattern = rule[1]
                    r_hsn = rule[3]
                    r_gst = rule[4]
                else: 
                    continue
                    
                if pattern.upper() in text_to_search:
                    best_hsn = r_hsn
                    best_gst = float(r_gst)
                    break 

            if not best_hsn:
                best_hsn = "8714" # default automotive parts
                best_gst = 28.0   # default gst for auto spares

            return best_hsn, best_gst

        for pid in self.part_ids:
            conn = self.db_manager.get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT part_name, description, compatibility, category, hsn_code, gst_rate FROM parts WHERE part_id = ?", (pid,))
                row = cursor.fetchone()
                if not row:
                    continue
                
                name, desc, compat, cat, hsn, gst = row
                name = name or ""
                desc = desc or ""
                compat = compat or ""
                cat = cat or ""
                hsn = hsn or ""
                gst = float(gst) if gst else 0.0
                
                updated = False
                
                # 1. Compatibility formatting (Only update if empty/useless)
                if not compat or str(compat).strip() in ("None", "N/A", "-", "Universal"):
                    veh, conf, src = local_vehicle_match(name, compat, desc)
                    if not veh and catalog_db:
                        veh, conf, src = nexses_catalog_lookup(pid, name, desc, catalog_db)
                    if not veh:
                        veh, conf, src = brand_extract_fallback(name)
                        
                    if veh and conf > 30:
                        compat = ", ".join(veh)
                        updated = True

                # 2. HSN / GST Prediction (Only update if missing)
                if not hsn or gst == 0:
                    best_hsn, best_gst = _guess_hsn(name, cat, hsn, gst)
                    if best_hsn != hsn or best_gst != gst:
                        hsn = best_hsn
                        gst = best_gst
                        updated = True
                        
                # 3. Category grouping (Only update if Uncategorized)
                if not cat or cat.lower() == "uncategorized":
                    name_up = name.upper()
                    new_cat = cat
                    if "CABLE" in name_up: new_cat = "Cables"
                    elif "FILTER" in name_up: new_cat = "Filters"
                    elif "BEARING" in name_up: new_cat = "Bearings"
                    elif "PAD" in name_up or "SHOE" in name_up or "BRAKE" in name_up: new_cat = "Brakes"
                    elif "OIL" in name_up or "LUBE" in name_up: new_cat = "Oils & Lubes"
                    elif "MIRROR" in name_up: new_cat = "Mirrors"
                    elif "BULB" in name_up or "LAMP" in name_up or "LIGHT" in name_up or "HEADLAMP" in name_up: new_cat = "Lighting"
                    elif "PLUG" in name_up or "RELAY" in name_up or "SENSOR" in name_up: new_cat = "Electricals"
                    elif "CHAIN" in name_up or "SPROCKET" in name_up: new_cat = "Drive Chain"
                    elif "NUT" in name_up or "BOLT" in name_up or "SCREW" in name_up or "WASHER" in name_up: new_cat = "Hardware"
                    
                    if new_cat and new_cat != cat:
                        cat = new_cat
                        updated = True

                # Save ONLY if missing data was discovered
                if updated:
                    cursor.execute("""
                        UPDATE parts 
                        SET compatibility = ?, category = ?, hsn_code = ?, gst_rate = ?
                        WHERE part_id = ?
                    """, (compat, cat, hsn, gst, pid))
                    conn.commit()
                    enriched_count += 1
            except Exception as e:
                print(f"Error auto-enriching part {pid}: {e}")
            finally:
                conn.close()
                
            time.sleep(0.05) # Yield to UI thread to prevent blocking
            
        self.finished.emit(enriched_count)
