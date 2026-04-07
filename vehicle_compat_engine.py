# vehicle_compat_engine.py
import sys
import json
import urllib.request
import urllib.parse
import urllib.error
import re
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTableWidget, QTableWidgetItem,
                             QProgressBar, QCheckBox, QFrame, QHeaderView, QWidget, QAbstractItemView, QApplication, QLineEdit, QInputDialog)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont, QBrush
import ui_theme
from styles import (
    COLOR_ACCENT_GREEN, COLOR_ACCENT_RED, COLOR_ACCENT_AMBER,
    COLOR_TEXT_PRIMARY, COLOR_ACCENT_CYAN
)

# ─────────────────────────────────────────────────────────────────────────────
# LOCAL REFERENCE DATABASE  (India-focused, 2-wheeler + 4-wheeler)
# ─────────────────────────────────────────────────────────────────────────────
VEHICLE_COMPAT_DB = {
    # ── TVS Models ──────────────────────────────────────────────────────────
    "apache rtr 160":   ["TVS Apache RTR 160", "TVS Apache RTR 160 2V", "TVS Apache RTR 160 4V"],
    "apache rtr 200":   ["TVS Apache RTR 200", "TVS Apache RTR 200 4V"],
    "apache rtr 180":   ["TVS Apache RTR 180"],
    "apache rr 310":    ["TVS Apache RR 310"],
    "apache":           ["TVS Apache RTR 160", "TVS Apache RTR 160 4V", "TVS Apache RTR 200 4V"],
    "raider 125":       ["TVS Raider 125", "TVS Raider 125 BS6"],
    "raider":           ["TVS Raider 125", "TVS Raider 125 BS6"],
    "ntorq":            ["TVS Ntorq 125", "TVS Ntorq 125 Race Edition"],
    "jupiter":          ["TVS Jupiter 110", "TVS Jupiter Classic", "TVS Jupiter ZX"],
    "xl 100":           ["TVS XL 100", "TVS XL Super"],
    "xl super":         ["TVS XL Super", "TVS XL 100"],
    "sport":            ["TVS Sport 100", "TVS Star City+"],
    "star city":        ["TVS Star City+", "TVS Star City"],
    "scooty pep":       ["TVS Scooty Pep+", "TVS Scooty Pep"],
    "scooty zest":      ["TVS Scooty Zest 110"],
    "radeon":           ["TVS Radeon 110"],
    "ronin":            ["TVS Ronin 225"],
    "iqube":            ["TVS iQube Electric"],
    "tvs":              ["TVS Apache RTR 160", "TVS Jupiter", "TVS Raider 125"],

    # ── Honda Models ────────────────────────────────────────────────────────
    "cb shine":         ["Honda CB Shine 125", "Honda CB Shine SP"],
    "cb unicorn":       ["Honda CB Unicorn 150", "Honda CB Unicorn 160"],
    "cb hornet":        ["Honda CB Hornet 160R", "Honda CB Hornet 2.0"],
    "cb350":            ["Honda H'ness CB350", "Honda CB350RS"],
    "activa 3g":        ["Honda Activa 3G"],
    "activa 4g":        ["Honda Activa 4G"],
    "activa 5g":        ["Honda Activa 5G"],
    "activa 6g":        ["Honda Activa 6G"],
    "activa 125":       ["Honda Activa 125", "Honda Activa 125 BS6"],
    "activa":           ["Honda Activa 6G", "Honda Activa 125", "Honda Activa i"],
    "dio":              ["Honda Dio 110", "Honda Dio BS6"],
    "grazia":           ["Honda Grazia 125"],
    "aviator":          ["Honda Aviator 110"],
    "dream yuga":       ["Honda Dream Yuga"],
    "livo":             ["Honda Livo 110"],
    "xblade":           ["Honda X-Blade 160"],
    "sp 125":           ["Honda SP125 BS6"],
    "honda":            ["Honda CB Shine", "Honda Activa 6G", "Honda SP125"],

    # ── Hero Models ─────────────────────────────────────────────────────────
    "splendor plus":    ["Hero Splendor Plus", "Hero Splendor+ XTEC"],
    "splendor pro":     ["Hero Splendor Pro Classic"],
    "splendor":         ["Hero Splendor Plus", "Hero Splendor iSmart"],
    "passion pro":      ["Hero Passion Pro"],
    "passion xpro":     ["Hero Passion X Pro"],
    "glamour":          ["Hero Glamour", "Hero Glamour XTEC"],
    "super splendor":   ["Hero Super Splendor 125"],
    "xtreme 160r":      ["Hero Xtreme 160R", "Hero Xtreme 160R 4V"],
    "xtreme 200r":      ["Hero Xtreme 200R"],
    "xpulse 200":       ["Hero XPulse 200", "Hero XPulse 200 4V"],
    "maestro":          ["Hero Maestro Edge 110", "Hero Maestro Edge 125"],
    "destini":          ["Hero Destini 125"],
    "pleasure":         ["Hero Pleasure+ 110"],
    "mavrick":          ["Hero Mavrick 440"],
    "hf deluxe":        ["Hero HF Deluxe"],
    "hero":             ["Hero Splendor Plus", "Hero HF Deluxe", "Hero Glamour"],

    # ── Bajaj Models ────────────────────────────────────────────────────────
    "pulsar 150":       ["Bajaj Pulsar 150", "Bajaj Pulsar 150 Neon", "Bajaj Pulsar 150 Twin Disc"],
    "pulsar 125":       ["Bajaj Pulsar 125", "Bajaj Pulsar 125 Neon"],
    "pulsar 180":       ["Bajaj Pulsar 180F"],
    "pulsar 220":       ["Bajaj Pulsar 220F"],
    "pulsar ns200":     ["Bajaj Pulsar NS200"],
    "pulsar ns160":     ["Bajaj Pulsar NS160"],
    "pulsar rs200":     ["Bajaj Pulsar RS200"],
    "pulsar n250":      ["Bajaj Pulsar N250"],
    "pulsar f250":      ["Bajaj Pulsar F250"],
    "pulsar":           ["Bajaj Pulsar 150", "Bajaj Pulsar 125", "Bajaj Pulsar 220F"],
    "dominar 400":      ["Bajaj Dominar 400"],
    "dominar 250":      ["Bajaj Dominar 250"],
    "avenger":          ["Bajaj Avenger Street 160", "Bajaj Avenger Cruise 220"],
    "ct 100":           ["Bajaj CT 100"],
    "ct 110":           ["Bajaj CT 110", "Bajaj CT 110X"],
    "platina":          ["Bajaj Platina 100", "Bajaj Platina 110 H-Gear"],
    "chetak":           ["Bajaj Chetak Electric"],
    "bajaj":            ["Bajaj Pulsar 150", "Bajaj Platina 100", "Bajaj CT 110"],

    # ── Royal Enfield ────────────────────────────────────────────────────────
    "bullet 350":       ["Royal Enfield Bullet 350"],
    "classic 350":      ["Royal Enfield Classic 350", "Royal Enfield Classic 350 Reborn"],
    "classic 500":      ["Royal Enfield Classic 500"],
    "thunderbird":      ["Royal Enfield Thunderbird 350X", "Royal Enfield Thunderbird 500X"],
    "meteor 350":       ["Royal Enfield Meteor 350"],
    "hunter 350":       ["Royal Enfield Hunter 350"],
    "scram 411":        ["Royal Enfield Scram 411"],
    "himalayan":        ["Royal Enfield Himalayan 411", "Royal Enfield Himalayan 450"],
    "interceptor 650":  ["Royal Enfield Interceptor 650"],
    "continental gt":   ["Royal Enfield Continental GT 650"],
    "royal enfield":    ["Royal Enfield Classic 350", "Royal Enfield Meteor 350"],
    "enfield":          ["Royal Enfield Classic 350", "Royal Enfield Bullet 350"],

    # ── Suzuki ──────────────────────────────────────────────────────────────
    "access 125":       ["Suzuki Access 125", "Suzuki Access 125 BS6"],
    "burgman":          ["Suzuki Burgman Street 125"],
    "gixxer 150":       ["Suzuki Gixxer 150"],
    "gixxer 250":       ["Suzuki Gixxer 250", "Suzuki Gixxer SF 250"],
    "gixxer sf":        ["Suzuki Gixxer SF 150", "Suzuki Gixxer SF 250"],
    "hayabusa":         ["Suzuki Hayabusa"],
    "suzuki":           ["Suzuki Access 125", "Suzuki Gixxer 150"],

    # ── Yamaha ──────────────────────────────────────────────────────────────
    "fzs 25":           ["Yamaha FZS 25"],
    "fz 25":            ["Yamaha FZ 25"],
    "fz-s fi":          ["Yamaha FZ-S FI V3", "Yamaha FZ-S FI V2"],
    "fz fi":            ["Yamaha FZ FI V3", "Yamaha FZ FI"],
    "fz v3":            ["Yamaha FZ-S FI V3"],
    "fazer 25":         ["Yamaha Fazer 25"],
    "r15 v4":           ["Yamaha R15 V4", "Yamaha R15M"],
    "r15 v3":           ["Yamaha R15 V3"],
    "r15":              ["Yamaha R15 V4", "Yamaha R15 V3", "Yamaha R15M"],
    "mt 15":            ["Yamaha MT 15 V2", "Yamaha MT 15"],
    "ray zr":           ["Yamaha Ray ZR 125", "Yamaha Ray ZR Street Rally"],
    "fascino":          ["Yamaha Fascino 125 FI", "Yamaha Fascino 125"],
    "saluto":           ["Yamaha Saluto 125"],
    "szr 150":          ["Yamaha SZR 150"],
    "yamaha":           ["Yamaha FZ-S FI", "Yamaha R15 V4", "Yamaha Fascino 125"],

    # ── KTM / Husqvarna ─────────────────────────────────────────────────────
    "duke 125":         ["KTM Duke 125"],
    "duke 200":         ["KTM Duke 200"],
    "duke 250":         ["KTM Duke 250"],
    "duke 390":         ["KTM Duke 390"],
    "rc 200":           ["KTM RC 200"],
    "rc 390":           ["KTM RC 390"],
    "adventure 250":    ["KTM Adventure 250"],
    "adventure 390":    ["KTM 390 Adventure"],
    "ktm":              ["KTM Duke 200", "KTM Duke 390", "KTM RC 200"],

    # ── 4-Wheeler / Car ─────────────────────────────────────────────────────
    "swift":            ["Maruti Suzuki Swift", "Maruti Swift Dzire"],
    "baleno":           ["Maruti Suzuki Baleno"],
    "alto":             ["Maruti Alto 800", "Maruti Alto K10"],
    "wagonr":           ["Maruti Wagon R"],
    "vitara brezza":    ["Maruti Vitara Brezza"],
    "ertiga":           ["Maruti Ertiga"],
    "creta":            ["Hyundai Creta"],
    "i20":              ["Hyundai i20"],
    "verna":            ["Hyundai Verna"],
    "nexon":            ["Tata Nexon", "Tata Nexon EV"],
    "thar":             ["Mahindra Thar"],
    "bolero":           ["Mahindra Bolero"],
    "scorpio":          ["Mahindra Scorpio", "Mahindra Scorpio-N"],

    # ── Generic Part Types (universal) ──────────────────────────────────────
    "chain sprocket":   ["All TVS Models", "All Honda Models", "All Bajaj Pulsar Models"],
    "brake pad":        ["Universal - All Disc Brake Vehicles"],
    "brake shoe":       ["Universal - All Drum Brake Vehicles"],
    "engine oil":       ["Universal - All Vehicles"],
    "spark plug":       ["Universal - All Petrol Vehicles"],
    "air filter":       ["Universal - All Vehicles"],
    "oil filter":       ["Universal - All 4-Stroke Vehicles"],
    "battery":          ["Universal - All Vehicles"],
    "headlamp":         ["Make/Model Specific - Check Part Number"],
    "tail lamp":        ["Make/Model Specific - Check Part Number"],
    "mirror":           ["Universal / Make Specific"],
    "handle bar":       ["Make/Model Specific"],
    "clutch plate":     ["Make/Model Specific - Check Part Number"],
    "piston":           ["Make/Model Specific - Check Part Number"],
    "carburetor":       ["Make/Model Specific - Check Part Number"],
}

def local_vehicle_match(part_name: str, existing_compat: str, description: str = "") -> tuple:
    name_lower = part_name.lower()
    desc_lower = description.lower() if description else ""

    # Priority 1: existing compat already filled — keep it
    if existing_compat and len(existing_compat.strip()) > 4:
        return [v.strip() for v in existing_compat.split(",")], 100, "✅ Existing"

    # Constraint 1: Length-Descending Sorting
    sorted_keys = sorted(VEHICLE_COMPAT_DB.keys(), key=len, reverse=True)

    # Priority 2: check DESCRIPTION column first — it often already contains model text
    if desc_lower and desc_lower not in ("none", "n/a", "-", ""):
        matched_vehicles = set()
        matched_keys = []
        temp_desc = desc_lower
        
        for key in sorted_keys:
            # Constraint 2: Word Boundary Regex Match
            pattern = r'\b' + re.escape(key) + r'\b'
            if re.search(pattern, temp_desc, flags=re.IGNORECASE):
                # Constraint 3: Deduplication
                matched_vehicles.update(VEHICLE_COMPAT_DB[key])
                matched_keys.append(key)
                temp_desc = re.sub(pattern, " ", temp_desc, flags=re.IGNORECASE)

        if matched_vehicles:
            vehicles = list(matched_vehicles)
            desc_clean = description.strip()
            # Add raw description as first suggestion so technician sees original text
            if desc_clean and desc_clean not in vehicles:
                vehicles.insert(0, desc_clean)
            
            keys_str = ", ".join(matched_keys).title()
            if len(keys_str) > 20: keys_str = keys_str[:17] + "..."
            return vehicles, 95, f"📋 Desc ({keys_str})"

    # Priority 3: match against part name
    matched_vehicles_name = set()
    matched_keys_name = []
    temp_name = name_lower

    for key in sorted_keys:
        pattern = r'\b' + re.escape(key) + r'\b'
        if re.search(pattern, temp_name, flags=re.IGNORECASE):
            matched_vehicles_name.update(VEHICLE_COMPAT_DB[key])
            matched_keys_name.append(key)
            temp_name = re.sub(pattern, " ", temp_name, flags=re.IGNORECASE)

    if matched_vehicles_name:
        vehicles = list(matched_vehicles_name)
        keys_str = ", ".join(matched_keys_name).title()
        if len(keys_str) > 20: keys_str = keys_str[:17] + "..."
        return vehicles, 85, f"📚 Part ({keys_str})"

    # Priority 4: if description has content at all, use it raw as a suggestion
    if desc_lower and desc_lower not in ("none", "n/a", "-", ""):
        return [description.strip()], 70, "📋 Raw Description"

    return [], 0, "—"

# ─────────────────────────────────────────────────────────────────────────────
def nexses_catalog_lookup(part_code: str, part_name: str, description: str = "",
                          db_path: str = "") -> tuple:
    """
    Priority 3.5 lookup: query the local Nexses eCatalog SQLite DB.

    Schema (from db_engine.py):
        parts_master (part_code, description, category, ...)
        compatibility_map (part_code, vehicle_id)
        vehicles_master (vehicle_id, brand, segment, series, model_name, variant)

    Tries:
      1. Exact part_code match in parts_master -> compatibility_map -> vehicles_master
      2. Description keyword match in parts_master.description  -> same join

    Returns (vehicles_list, confidence, source) or ([], 0, "—") if not found / no DB.
    """
    import sqlite3, os

    if not db_path or not os.path.isfile(db_path):
        return [], 0, "—"

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        def _rows_to_vehicles(rows):
            seen = set()
            result = []
            for row in rows:
                model = row["model_name"].strip() if row["model_name"] else ""
                series = row["series"].strip() if row["series"] else ""
                brand = row["brand"].strip() if row["brand"] else ""
                variant = row["variant"].strip() if row["variant"] else ""
                label = " ".join(filter(None, [brand, model or series, variant])).strip()
                if label and label not in seen:
                    seen.add(label)
                    result.append(label)
            return result

        VEHICLE_JOIN = """
            SELECT vm.brand, vm.segment, vm.series, vm.model_name, vm.variant
            FROM   compatibility_map cm
            JOIN   vehicles_master vm ON vm.vehicle_id = cm.vehicle_id
            WHERE  cm.part_code = ?
        """

        # --- Pass 1: exact part code ---
        clean_code = (part_code or "").strip().upper()
        if clean_code:
            cur.execute(VEHICLE_JOIN, (clean_code,))
            rows = cur.fetchall()
            if rows:
                vehicles = _rows_to_vehicles(rows)
                if vehicles:
                    conn.close()
                    return vehicles, 97, f"🗂️ Nexses DB ({clean_code})"

        # --- Pass 2: description / part-name keyword match in parts_master ---
        keyword = (description.strip() or part_name.strip())[:60]
        if keyword:
            cur.execute("""
                SELECT pm.part_code FROM parts_master pm
                WHERE  pm.description LIKE ? OR pm.part_code LIKE ?
                LIMIT  10
            """, (f"%{keyword}%", f"%{clean_code}%"))
            codes = [r[0] for r in cur.fetchall()]
            if codes:
                placeholders = ",".join(["?"] * len(codes))
                cur.execute(f"""
                    SELECT vm.brand, vm.segment, vm.series, vm.model_name, vm.variant
                    FROM   compatibility_map cm
                    JOIN   vehicles_master vm ON vm.vehicle_id = cm.vehicle_id
                    WHERE  cm.part_code IN ({placeholders})
                """, codes)
                rows = cur.fetchall()
                if rows:
                    vehicles = _rows_to_vehicles(rows)
                    if vehicles:
                        conn.close()
                        return vehicles, 88, "🗂️ Nexses DB (desc)"

        conn.close()
    except Exception:
        pass

    return [], 0, "—"

def brand_extract_fallback(part_name: str) -> tuple:
    name_upper = part_name.upper()
    brands = {
        "TVS": ["TVS All Models"], "HONDA": ["Honda All Models"], "HERO": ["Hero All Models"],
        "BAJAJ": ["Bajaj All Models"], "YAMAHA": ["Yamaha All Models"], "SUZUKI": ["Suzuki All Models"],
        "RE": ["Royal Enfield All Models"], "KTM": ["KTM All Models"],
        "APACHE": ["TVS Apache RTR 160", "TVS Apache RTR 200"],
        "PULSAR": ["Bajaj Pulsar 150", "Bajaj Pulsar 125"],
        "ACTIVA": ["Honda Activa 6G"], "SPLENDOR": ["Hero Splendor Plus"],
        "FZ": ["Yamaha FZ FI"], "R15": ["Yamaha R15 V4"],
    }
    for key, vehicles in brands.items():
        if key in name_upper:
            return vehicles, 40, f"🔤 Name Extract ({key})"
    return ["Universal / Unknown"], 10, "❓ Unknown"

# ─────────────────────────────────────────────────────────────────────────────
class VehicleCompatScanThread(QThread):
    progress    = pyqtSignal(int)
    result_ready = pyqtSignal(list)
    status_msg  = pyqtSignal(str)
    aborted     = pyqtSignal()

    def __init__(self, db_manager, catalog_db_path=""):
        super().__init__()
        self.db_manager      = db_manager
        self.catalog_db_path = catalog_db_path
        self._abort          = False

    def abort(self):
        self._abort = True

    def run(self):
        self.status_msg.emit("🔍 Local db matching...")
        parts = self.db_manager.get_all_parts()
        total = len(parts)
        results = []

        for i, part in enumerate(parts):
            if self._abort:
                self.status_msg.emit(f"⛔ Scan aborted — showing {len(results)} parts processed so far.")
                self.result_ready.emit(results)
                self.aborted.emit()
                return

            part_id   = str(part[0])
            part_name = str(part[1])
            raw_compat = str(part[9]).strip() if part[9] else ""

            # ── Detect if stored compat is raw numeric IDs (e.g. 001010001) ──
            # Such IDs come from old catalog imports and are NOT vehicle names.
            # Pattern: token is 6+ digits, optionally with leading zeros.
            def _is_numeric_id_blob(text: str) -> bool:
                if not text:
                    return False
                tokens = [t.strip() for t in text.split(",") if t.strip()]
                if not tokens:
                    return False
                # If more than half the tokens look like pure numeric IDs → blob
                numeric_count = sum(1 for t in tokens if re.fullmatch(r'0*\d{4,}', t))
                return numeric_count >= max(1, len(tokens) // 2)

            is_id_blob = _is_numeric_id_blob(raw_compat)

            # curr_compat used for display; if it's a numeric blob show warning prefix
            curr_compat_display = f"⚠️ Old IDs: {raw_compat[:60]}..." if is_id_blob and len(raw_compat) > 60 else (
                f"⚠️ Old IDs: {raw_compat}" if is_id_blob else raw_compat
            )

            # needs_update = True for empty, placeholder, OR numeric ID blobs
            needs_update = (not raw_compat
                            or raw_compat in ("", "None", "N/A", "-")
                            or is_id_blob)

            part_desc = str(part[2]).strip() if part[2] and str(part[2]).lower() not in ("none", "null", "") else ""

            # For numeric blobs, pass empty string to force fresh lookup
            compat_for_lookup = "" if is_id_blob else raw_compat
            veh, conf, src = local_vehicle_match(part_name, compat_for_lookup, part_desc)

            if not veh and needs_update and self.catalog_db_path:
                part_code_col = str(part[3]).strip() if len(part) > 3 and part[3] else part_id
                veh, conf, src = nexses_catalog_lookup(
                    part_code_col, part_name, part_desc, self.catalog_db_path
                )

            if not veh and needs_update:
                v, c, s = brand_extract_fallback(part_name)
                veh, conf, src = v, c, s

            res = {
                'part_id': part_id,
                'part_name': part_name,
                'current_compat': curr_compat_display,
                'suggested': ", ".join(veh) if veh else "",
                'confidence': conf,
                'source': src,
                'needs_update': needs_update,
                'selected': needs_update and conf > 30,
                # keep original raw value so ApplyThread can clear/replace it properly
                '_raw_compat': raw_compat,
            }
            results.append(res)
            self.progress.emit(int((i + 1) / total * 100))

        missing = sum(1 for r in results if r['needs_update'])
        self.status_msg.emit(f"✅ Scan done — {missing} parts need update")
        self.result_ready.emit(results)
        self.progress.emit(100)


# ─────────────────────────────────────────────────────────────────────────────
class TVSCatalogLookupThread(QThread):
    """
    Worker: looks up a single part on the TVS eCatalog API and emits
    the list of matching Series strings.  Respects built-in rate limiting.
    """
    result_ready = pyqtSignal(list)    # list of Series strings
    status_msg   = pyqtSignal(str)
    error        = pyqtSignal(str)

    def __init__(self, part_name: str, dealer_id: str = "63050", branch_id: int = 1):
        super().__init__()
        self.part_name = part_name
        self.dealer_id = dealer_id
        self.branch_id = branch_id

    def run(self):
        try:
            from tvs_catalog_client import TVSCatalogClient
            client = TVSCatalogClient(dealer_id=self.dealer_id, branch_id=self.branch_id)
            self.status_msg.emit("🔄 Authenticating with TVS eCatalog...")
            if not client.connect():
                self.error.emit("❌ TVS Auth failed — check dealer ID in Settings.")
                return
            self.status_msg.emit(f"🔍 Searching TVS for: {self.part_name[:30]}...")
            results = client.search_parts(self.part_name)
            if not results:
                self.error.emit("⚠️ No TVS matches found for this part.")
                return

            # ── Resolve Series to readable vehicle name ────────────────────────
            # The TVS API's 'Series' field is often a raw numeric ID (e.g. 00001000010000762).
            # We try: SeriesName field → local VEHICLE_COMPAT_DB keyword match on Description → Description.
            def _resolve_series_label(item: dict) -> str:
                series_id   = str(item.get("Series", "")).strip()
                series_name = str(item.get("SeriesName", "")).strip()
                desc        = str(item.get("Description", "")).strip()

                # If SeriesName is already a human-readable string, use it
                if series_name and not re.fullmatch(r'0*\d{6,}', series_name):
                    return series_name

                # If series_id is not numeric, it IS the name already
                if series_id and not re.fullmatch(r'0*\d{6,}', series_id):
                    return series_id

                # Try matching description against VEHICLE_COMPAT_DB keywords
                if desc:
                    desc_lower = desc.lower()
                    sorted_keys = sorted(VEHICLE_COMPAT_DB.keys(), key=len, reverse=True)
                    matched = []
                    for key in sorted_keys:
                        if re.search(r'\b' + re.escape(key) + r'\b', desc_lower):
                            matched.extend(VEHICLE_COMPAT_DB[key])
                            break  # first match is enough for a label
                    if matched:
                        return matched[0]
                    # Fall back to raw description text (truncate long ones)
                    return desc[:60] if len(desc) > 60 else desc

                return ""  # skip this item entirely

            seen = set()
            series_list = []
            for item in results:
                label = _resolve_series_label(item)
                if label and label not in seen:
                    seen.add(label)
                    series_list.append(label)

            if not series_list:
                self.error.emit("⚠️ TVS returned only unresolvable series IDs for this part.")
                return

            self.result_ready.emit(series_list)

        except Exception as e:
            self.error.emit(f"❌ TVS Lookup error: {e}")

# ─────────────────────────────────────────────────────────────────────────────
class VehicleCompatDialog(QDialog):
    sync_completed = pyqtSignal(int)

    def __init__(self, parent, db_manager):
        super().__init__(parent)
        self.db_manager       = db_manager
        self.scan_results     = []
        self._apply_aborted   = False
        self.total_tokens     = 0
        self.setWindowTitle("🚗 Vehicle Compatibility Engine")
        self.setMinimumSize(1150, 700)
        self.setStyleSheet(f"""
            QDialog {{ background-color: #0b0b14; color: {COLOR_TEXT_PRIMARY}; font-family: 'Segoe UI'; }}
            QLabel {{ background: transparent; border: none; }}
            QHeaderView::section {{
                background: #141428; color: {COLOR_ACCENT_AMBER}; border: 1px solid #223;
                font-weight: bold; font-size: 11px; padding: 5px;
            }}
        """)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20); root.setSpacing(14)

        hdr = QFrame()
        hdr.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 rgba(255,170,0,0.10), stop:1 rgba(0,229,255,0.06));
                border: 1px solid rgba(255,170,0,0.35); border-radius: 10px;
            }
        """)
        hl = QVBoxLayout(hdr); hl.setContentsMargins(20,12,20,12)
        
        # Title row
        t_row = QHBoxLayout()
        title = QLabel("🚗 VEHICLE COMPATIBILITY AUTO-FILL ENGINE")
        title.setStyleSheet(f"color:{COLOR_ACCENT_AMBER}; font-weight:bold; font-size:15px; letter-spacing:1px;")
        t_row.addWidget(title)
        
        self.lbl_status = QLabel("Press SCAN to begin...")
        self.lbl_status.setStyleSheet("color:#aaa; font-size:12px; margin-left:20px;")
        t_row.addWidget(self.lbl_status)
        t_row.addStretch()
        hl.addLayout(t_row)
        
        # Config row
        c_row = QHBoxLayout(); c_row.setContentsMargins(0, 10, 0, 0)
        c_row.addStretch()
        hl.addLayout(c_row)
        
        root.addWidget(hdr)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100); self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(6); self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(f"QProgressBar {{ background:#1a1a2e; border:none; border-radius:3px; }} "
                                        f"QProgressBar::chunk {{ background: {COLOR_ACCENT_AMBER}; border-radius:3px; }}")
        root.addWidget(self.progress_bar)

        sr = QHBoxLayout()
        self.stat_total   = self._chip("TOTAL PARTS",   "—", COLOR_ACCENT_CYAN)
        self.stat_missing = self._chip("MISSING COMPAT", "—", COLOR_ACCENT_RED)
        self.stat_matched = self._chip("LOCAL MATCH",   "—", COLOR_ACCENT_GREEN)
        for w in [self.stat_total, self.stat_missing, self.stat_matched]: sr.addWidget(w)
        root.addLayout(sr)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["✓", "PART ID", "PART NAME", "CURRENT COMPAT", "SUGGESTED VEHICLES", "CONF%", "SOURCE"])
        self.table.setStyleSheet(ui_theme.get_table_style())
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        hv = self.table.horizontalHeader()
        hv.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hv.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hv.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(2, 220)
        hv.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(3, 160)
        hv.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        hv.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        hv.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.table.selectionModel().selectionChanged.connect(self._on_row_selected)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        root.addWidget(self.table)

        fr = QHBoxLayout()
        self.btn_missing_filter = QPushButton("🔴 Missing Only")
        self.btn_missing_filter.setFixedHeight(34)
        self.btn_missing_filter.setCheckable(True)
        self.btn_missing_filter.setStyleSheet(self._ghost(COLOR_ACCENT_RED))
        self.btn_missing_filter.clicked.connect(self._toggle_missing_filter)
        fr.addWidget(self.btn_missing_filter)

        for label, color, slot in [("☑️ Select All", COLOR_ACCENT_CYAN, self._select_all),
                                   ("☐ Deselect All", "#888", self._deselect_all)]:
            b = QPushButton(label); b.setFixedHeight(34); b.setStyleSheet(self._ghost(color)); b.clicked.connect(slot); fr.addWidget(b)
        fr.addStretch(); root.addLayout(fr)
        self._filter_missing_active = False

        ar = QHBoxLayout(); ar.setSpacing(12)
        self.btn_scan = QPushButton("🔍  SCAN INVENTORY")
        self.btn_scan.setFixedHeight(44); self.btn_scan.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_scan.setStyleSheet(ui_theme.get_amber_button_style())
        self.btn_scan.clicked.connect(self._start_scan); ar.addWidget(self.btn_scan)

        self.btn_abort = QPushButton("⛔  ABORT SCAN")
        self.btn_abort.setVisible(False)
        self.btn_abort.setFixedHeight(44)
        self.btn_abort.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_abort.setStyleSheet(ui_theme.get_danger_button_style())
        self.btn_abort.clicked.connect(self._do_abort)
        ar.addWidget(self.btn_abort)
        
        ar.addStretch()
        
        self.btn_tvs = QPushButton("🔎  TVS LOOKUP")
        self.btn_tvs.setFixedHeight(44)
        self.btn_tvs.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_tvs.setEnabled(False)
        self.btn_tvs.setStyleSheet(ui_theme.get_primary_button_style())
        self.btn_tvs.clicked.connect(self._tvs_lookup)
        ar.addWidget(self.btn_tvs)
        
        self.btn_close = QPushButton("CLOSE")
        self.btn_close.setFixedHeight(44)
        self.btn_close.setFixedWidth(90)
        self.btn_close.setStyleSheet(ui_theme.get_icon_btn_red())
        self.btn_close.clicked.connect(self.reject)
        ar.addWidget(self.btn_close)
        
        self.btn_apply = QPushButton("⚡  APPLY COMPATIBILITY")
        self.btn_apply.setFixedHeight(44)
        self.btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_apply.setEnabled(False)
        self.btn_apply.setStyleSheet(ui_theme.get_primary_button_style())
        self.btn_apply.clicked.connect(self._apply_sync)
        ar.addWidget(self.btn_apply)
        
        root.addLayout(ar)

    def _chip(self, label, value, color):
        frame = QFrame()
        frame.setStyleSheet(f"QFrame {{ background: rgba({QColor(color).red()},{QColor(color).green()},{QColor(color).blue()},0.08); border: 1px solid {color}; border-radius: 8px; }}")
        lay = QVBoxLayout(frame); lay.setContentsMargins(14, 8, 14, 8); lay.setSpacing(2)
        lbl_val = QLabel(value)
        lbl_val.setStyleSheet(f"color: {color}; font-size: 20px; font-weight: bold; font-family: Consolas;"); lbl_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_lbl = QLabel(label)
        lbl_lbl.setStyleSheet("color: #888; font-size: 10px; letter-spacing: 1px;"); lbl_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(lbl_val); lay.addWidget(lbl_lbl)
        frame._value_label = lbl_val
        return frame

    def _set_chip(self, chip, val):
        chip._value_label.setText(str(val))

    def _ghost(self, color):
        return f"QPushButton {{ background: rgba({QColor(color).red()},{QColor(color).green()},{QColor(color).blue()},0.08); color: {color}; border: 1px solid {color}; border-radius: 5px; font-size: 11px; padding: 0 10px; }} QPushButton:hover {{ background: {color}; color: black; }}"

    def _set_item(self, row, col, text, color=None, bld=False):
        itm = QTableWidgetItem(str(text))
        itm.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if color: itm.setForeground(QBrush(QColor(color)))
        if bld: f = QFont(); f.setBold(True); itm.setFont(f)
        self.table.setItem(row, col, itm)

    def _start_scan(self):
        self.btn_scan.setVisible(False); self.btn_abort.setVisible(True); self.btn_abort.setText("⛔  ABORT SCAN")
        self.btn_abort.setEnabled(True); self.btn_apply.setEnabled(False)
        self.table.setRowCount(0); self.progress_bar.setValue(0); self.lbl_status.setText("🔍 Scanning...")
        _s = self.db_manager.get_shop_settings() or {}
        catalog_db = _s.get("nexses_catalog_db", "")
        self._thread = VehicleCompatScanThread(self.db_manager, catalog_db_path=catalog_db)
        self._thread.progress.connect(self.progress_bar.setValue)
        self._thread.status_msg.connect(self.lbl_status.setText)
        self._thread.result_ready.connect(self._on_scan_done)
        self._thread.aborted.connect(self._on_aborted)
        self._thread.start()

    def _on_scan_done(self, results):
        self.scan_results = results
        self.btn_abort.setVisible(False); self.btn_scan.setVisible(True); self.btn_scan.setEnabled(True); self.btn_apply.setEnabled(True)
        self._set_chip(self.stat_total, len(results)); self._set_chip(self.stat_missing, sum(1 for r in results if r['needs_update']))
        self._set_chip(self.stat_matched, sum(1 for r in results if r['confidence'] >= 80))
        self._populate_table(results)

    def _populate_table(self, results):
        self.table.setRowCount(len(results))
        for i, r in enumerate(results):
            cw = QWidget(); cl = QHBoxLayout(cw); cl.setContentsMargins(0,0,0,0); cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chk = QCheckBox(); chk.setChecked(r['selected']); chk.setStyleSheet(ui_theme.get_table_checkbox_style())
            chk.stateChanged.connect(lambda state, idx=i: self._on_chk(idx, state))
            cl.addWidget(chk); self.table.setCellWidget(i, 0, cw)
            
            self._set_item(i, 1, r['part_id'], COLOR_ACCENT_CYAN, bld=True)
            self._set_item(i, 2, r['part_name'])
            self._set_item(i, 3, r['current_compat'], COLOR_ACCENT_RED if r.get('needs_update') else COLOR_ACCENT_GREEN)
            self._set_item(i, 4, r.get('suggested', ''), COLOR_ACCENT_GREEN, bld=True)
            conf = r.get('confidence', 0)
            self._set_item(i, 5, f"{conf}%", COLOR_ACCENT_GREEN if conf >= 80 else COLOR_ACCENT_AMBER if conf >= 50 else COLOR_ACCENT_RED, bld=True)
            self._set_item(i, 6, r.get('source', ''))
            
            if r.get('needs_update'):
                for c in range(7):
                    itm = self.table.item(i, c)
                    if itm: itm.setBackground(QBrush(QColor(255, 80, 80, 18)))


    def _on_aborted(self):
        self.btn_abort.setVisible(False); self.btn_scan.setVisible(True); self.btn_scan.setEnabled(True); self.progress_bar.setValue(0)

    def _on_chk(self, idx, state):
        if idx < len(self.scan_results): self.scan_results[idx]['selected'] = bool(state)

    def _toggle_missing_filter(self):
        """Toggle between showing only missing-compat rows and showing all rows."""
        self._filter_missing_active = self.btn_missing_filter.isChecked()
        if self._filter_missing_active:
            self.btn_missing_filter.setText("📋 Show All")
            self.btn_missing_filter.setStyleSheet(self._ghost(COLOR_ACCENT_AMBER))
            # Show only rows that need updating, hide the rest
            missing_count = 0
            for i, r in enumerate(self.scan_results):
                is_missing = r.get('needs_update', False)
                self.table.setRowHidden(i, not is_missing)
                if is_missing:
                    missing_count += 1
                    # Also check their checkboxes automatically
                    ch = r['confidence'] > 30
                    r['selected'] = ch
                    cw = self.table.cellWidget(i, 0)
                    if cw:
                        chk = cw.findChild(QCheckBox)
                        if chk:
                            chk.blockSignals(True); chk.setChecked(ch); chk.blockSignals(False)
            self.lbl_status.setText(f"🔴 Showing {missing_count} missing-compat part(s) — click 'Show All' to go back")
        else:
            self.btn_missing_filter.setText("🔴 Missing Only")
            self.btn_missing_filter.setStyleSheet(self._ghost(COLOR_ACCENT_RED))
            # Restore all rows
            for i in range(self.table.rowCount()):
                self.table.setRowHidden(i, False)
            total = len(self.scan_results)
            missing = sum(1 for r in self.scan_results if r['needs_update'])
            self.lbl_status.setText(f"📋 Showing all {total} parts — {missing} need update")

    # ── TVS Lookup & Manual Edit ───────────────────────────────────
    def _on_row_selected(self):
        rows = self.table.selectionModel().selectedRows()
        self.btn_tvs.setEnabled(bool(rows) and bool(self.scan_results))

    def _on_cell_double_clicked(self, row, col):
        if col in (3, 4) and row < len(self.scan_results): # Current Compat or Suggested Vehicles
            current_text = self.scan_results[row].get('suggested', '')
            # If suggestion is empty and they clicked current compat, load current compat
            if not current_text and col == 3:
                current_text = self.scan_results[row].get('current_compat', '')
                if current_text.startswith("⚠️ Old IDs:"):
                    current_text = current_text.replace("⚠️ Old IDs:", "").strip()
                    
            new_text, ok = QInputDialog.getText(self, "✍️ Manual Compatibility Edit", 
                "Type the vehicle compatibility and press OK to save immediately:", 
                QLineEdit.EchoMode.Normal, current_text)
            if ok and new_text is not None:
                new_text = new_text.strip()
                if not new_text:
                    new_text = "Universal / Unknown"
                
                part_id = self.scan_results[row].get('part_id', '')
                
                # ── Immediately persist to the database ──────────────────
                try:
                    conn = self.db_manager.get_connection()
                    conn.execute("UPDATE parts SET compatibility=? WHERE part_id=?", (new_text, part_id))
                    conn.commit()
                    conn.close()
                    self.lbl_status.setText(f"✅ Saved: '{part_id}' → {new_text[:50]}")
                    saved = True
                except Exception as e:
                    self.lbl_status.setText(f"❌ Save failed: {e}")
                    saved = False
                # ──────────────────────────────────────────────────────────
                
                # Update in-memory scan results
                self.scan_results[row]['suggested'] = new_text
                self.scan_results[row]['confidence'] = 100
                self.scan_results[row]['source'] = "✅ Saved" if saved else "⚠️ Save Failed"
                self.scan_results[row]['selected'] = False  # Already saved, deselect
                self.scan_results[row]['needs_update'] = False
                
                # Update table cells
                self._set_item(row, 3, new_text, COLOR_ACCENT_GREEN)
                self._set_item(row, 4, new_text, COLOR_ACCENT_GREEN, bld=True)
                self._set_item(row, 5, "100%", COLOR_ACCENT_GREEN, bld=True)
                self._set_item(row, 6, "✅ Saved" if saved else "⚠️ Error")
                
                # Clear the red background since it's now saved
                for c in range(7):
                    itm = self.table.item(row, c)
                    if itm:
                        itm.setBackground(QBrush(QColor(0, 0, 0, 0)))
                
                # Deselect the checkbox (already saved)
                cw = self.table.cellWidget(row, 0)
                if cw:
                    chk = cw.findChild(QCheckBox)
                    if chk:
                        chk.blockSignals(True)
                        chk.setChecked(False)
                        chk.blockSignals(False)
                
                if saved:
                    self.sync_completed.emit(1)

    def _tvs_lookup(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows or not self.scan_results:
            return
        row_idx = rows[0].row()
        if row_idx >= len(self.scan_results):
            return
        part = self.scan_results[row_idx]
        part_name = part['part_name']

        # Read TVS credentials from settings
        s = self.db_manager.get_shop_settings() or {}
        dealer_id = s.get("tvs_dealer_id", "63050")
        try:
            branch_id = int(s.get("tvs_branch_id", "1"))
        except ValueError:
            branch_id = 1

        self.btn_tvs.setEnabled(False)
        self.btn_tvs.setText("🔄  Fetching TVS...")
        self.lbl_status.setText(f"🔍 TVS Lookup for: {part_name[:30]}...")

        self._tvs_thread = TVSCatalogLookupThread(part_name, dealer_id=dealer_id, branch_id=branch_id)
        self._tvs_thread.status_msg.connect(self.lbl_status.setText)
        self._tvs_thread.result_ready.connect(lambda lst: self._on_tvs_result(row_idx, lst))
        self._tvs_thread.error.connect(self._on_tvs_error)
        self._tvs_thread.start()

    def _on_tvs_result(self, row_idx: int, series_list: list):
        self.btn_tvs.setEnabled(True)
        self.btn_tvs.setText("🔎  TVS LOOKUP")
        if row_idx >= len(self.scan_results) or not series_list:
            self.lbl_status.setText("⚠️ TVS: No matching series found.")
            return
        suggested = ", ".join(series_list)
        self.scan_results[row_idx]['suggested']   = suggested
        self.scan_results[row_idx]['confidence']  = 92
        self.scan_results[row_idx]['source']      = "🏍️ TVS eCatalog"
        self.scan_results[row_idx]['selected']    = True
        # Update the table cell
        self._set_item(row_idx, 4, suggested, COLOR_ACCENT_CYAN, bld=True)
        self._set_item(row_idx, 5, "92%", COLOR_ACCENT_GREEN, bld=True)
        self._set_item(row_idx, 6, "🏍️ TVS eCatalog")
        self.lbl_status.setText(f"✅ TVS found {len(series_list)} series for this part.")
        self.btn_apply.setEnabled(True)

    def _on_tvs_error(self, msg: str):
        self.btn_tvs.setEnabled(True)
        self.btn_tvs.setText("🔎  TVS LOOKUP")
        self.lbl_status.setText(msg)

    def _select_all(self):
        for i, r in enumerate(self.scan_results):
            r['selected'] = True; cw = self.table.cellWidget(i, 0)
            if cw: chk=cw.findChild(QCheckBox); chk.blockSignals(True); chk.setChecked(True); chk.blockSignals(False)

    def _deselect_all(self):
        for i, r in enumerate(self.scan_results):
            r['selected'] = False; cw = self.table.cellWidget(i, 0)
            if cw: chk=cw.findChild(QCheckBox); chk.blockSignals(True); chk.setChecked(False); chk.blockSignals(False)

    def _apply_sync(self):
        to_sync = [r for r in self.scan_results if r['selected'] and r['suggested']]
        if not to_sync: return

        self.btn_apply.setEnabled(False); self.btn_apply.setText("⏳  Saving...")
        self.btn_close.setVisible(False); self.btn_abort.setVisible(True)
        self.btn_abort.setText("⛔  ABORT APPLY"); self.btn_abort.setEnabled(True)
        self.progress_bar.setValue(0)

        # ── Run in background thread — single batch transaction ──
        self._apply_thread = VehicleCompatApplyThread(self.db_manager, to_sync)
        self._apply_thread.progress.connect(self.progress_bar.setValue)
        self._apply_thread.status_msg.connect(self.lbl_status.setText)
        self._apply_thread.done.connect(self._on_apply_done)
        self._apply_thread.aborted.connect(self._on_apply_aborted)
        self._apply_thread.start()

    def _on_apply_done(self, ok_count):
        self.btn_abort.setVisible(False); self.btn_close.setVisible(True)
        self.btn_apply.setText("⚡  APPLY TO DATABASE"); self.btn_apply.setEnabled(True)
        self.progress_bar.setValue(100)
        self.sync_completed.emit(ok_count)
        QTimer.singleShot(300, self._start_scan)

    def _on_apply_aborted(self, ok_count):
        self.btn_abort.setVisible(False); self.btn_close.setVisible(True)
        self.btn_apply.setText("⚡  APPLY TO DATABASE"); self.btn_apply.setEnabled(True)
        if ok_count > 0:
            self.sync_completed.emit(ok_count)

    def _do_abort(self):
        if hasattr(self, '_thread') and self._thread.isRunning():
            self._thread.abort()
        if hasattr(self, '_apply_thread') and self._apply_thread.isRunning():
            self._apply_thread.abort()
        self.btn_abort.setEnabled(False)
        self.btn_abort.setText("⛔  Stopping...")
        self.lbl_status.setText("⛔ Aborting...")


# ─────────────────────────────────────────────────────────────────────────────
# Background Apply Thread — batch-updates compatibility in one transaction
# ─────────────────────────────────────────────────────────────────────────────
class VehicleCompatApplyThread(QThread):
    progress   = pyqtSignal(int)
    status_msg = pyqtSignal(str)
    done       = pyqtSignal(int)   # success_count
    aborted    = pyqtSignal(int)   # success_count so far

    def __init__(self, db_manager, to_sync):
        super().__init__()
        self.db_manager = db_manager
        self.to_sync    = to_sync
        self._abort     = False

    def abort(self):
        self._abort = True

    def run(self):
        total         = len(self.to_sync)
        success_count = 0
        conn = self.db_manager.get_connection()
        try:
            cursor = conn.cursor()
            for i, r in enumerate(self.to_sync):
                if self._abort:
                    conn.commit()
                    self.status_msg.emit(f"⛔ Aborted — {success_count} saved.")
                    self.aborted.emit(success_count)
                    return

                try:
                    cursor.execute(
                        "UPDATE parts SET compatibility=? WHERE part_id=?",
                        (r['suggested'], r['part_id'])
                    )
                    success_count += 1
                except Exception as e:
                    from logger import app_logger
                    app_logger.warning(f"Compat apply failed for {r['part_id']}: {e}")

                self.progress.emit(int((i + 1) / total * 100))

            conn.commit()

        except Exception as e:
            conn.rollback()
            self.status_msg.emit(f"❌ Error: {e}")
        finally:
            conn.close()

        self.status_msg.emit(f"✅ Updated {success_count}/{total} parts!")
        self.done.emit(success_count)



