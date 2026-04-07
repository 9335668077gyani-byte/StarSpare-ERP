"""
api_sync_engine.py — Stealth API Sync Engine for Nexses e-Catalog
===================================================================

Fetches live catalog data from the TVS Advantage eCatalog REST API
and injects it into the local SQLite database via db_engine helpers.

Strategy:
    Instead of scraping the DOM with Selenium/Playwright, this engine
    consumes the same REST endpoints that the TVS Angular frontend uses.
    This is faster, lighter, and produces cleaner data.

API Flow (sequential):
    1. POST /Setting/tokenGeneration          → get auth Bearer token
    2. GET  /api/Catalouge/GetMenuCategory     → get segment categories
    3. GET  /api/Catalouge/GetVehicalDataByCategoryID  → models per segment
    4. GET  /api/Catalouge/GetVehCoordinatesbySeries   → hotspot coordinates
    5. GET  /api/Catalouge/GetPartDetailsByAssemblyID   → parts per assembly

Anti-blocking measures:
    - Standard Chrome User-Agent header
    - requests.Session() for natural cookie/connection reuse
    - time.sleep(random.uniform(2, 5)) between EVERY API call
    - Graceful HTTP error handling (no crashes)
    - Console progress logging

Usage:
    python api_sync_engine.py
    python api_sync_engine.py --dealer-id 63735
    python api_sync_engine.py --categories-only        # just list categories
    python api_sync_engine.py --category MOTORCYCLE    # sync one category
"""

import sys
import os
import json
import time
import random
import argparse
from datetime import datetime

import requests

# ── Add project root to path ──────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db_engine import (
    get_connection, initialize_database, DEFAULT_DB_PATH,
    insert_vehicle, upsert_part, insert_compatibility,
    batch_upsert_parts, batch_insert_compatibility,
    is_synced, mark_synced,
)


# ===========================================================================
#  Configuration
# ===========================================================================

BASE_URL = "https://www.advantagetvs.com/PartEcommerceAPI"
DEFAULT_DEALER_ID = "63050"

# Realistic browser headers to avoid bot detection
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.advantagetvs.com/NewPartsECatalog/",
    "Origin": "https://www.advantagetvs.com",
    "Connection": "keep-alive",
}

# Path for saving hotspot coordinate JSON files
from path_utils import get_app_data_path
HOTSPOTS_DIR = get_app_data_path(os.path.join("assets", "hotspots"))

# ===========================================================================
#  Terminal UI Helpers
# ===========================================================================

def log(msg: str, level: str = "INFO"):
    """Print a timestamped log message to the console."""
    ts = datetime.now().strftime("%H:%M:%S")
    prefix = {
        "INFO":    "🔵",
        "OK":      "✅",
        "WARN":    "⚠️",
        "ERROR":   "❌",
        "SLEEP":   "💤",
        "DB":      "💾",
        "FETCH":   "📡",
    }.get(level, "▪️")
    print(f"  [{ts}] {prefix}  {msg}")


def stealth_sleep(min_s: float = 1.5, max_s: float = 3.5):
    """Random delay between API calls to avoid rate-limiting."""
    delay = random.uniform(min_s, max_s)
    log(f"Sleeping for {delay:.1f}s...", "SLEEP")
    time.sleep(delay)


# ===========================================================================
#  JSON Decoding Helper
# ===========================================================================

def clean_tvs_json(data):
    """
    Recursively unwraps double/triple-encoded JSON strings from the TVS API.
    Guarantees no strings remain that look like JSON objects/arrays.
    """
    if isinstance(data, str):
        s = data.strip()
        # Sometimes strings are additionally wrapped in quotes: '"[{\...}]"'
        if s.startswith('"') and s.endswith('"') and len(s) >= 2:
            s_unquoted = s[1:-1].replace('\\"', '"').replace('\\\\"', '\\"')
            if s_unquoted.startswith(("{", "[")):
                s = s_unquoted

        if s.startswith(("{", "[")):
            try:
                decoded = json.loads(s)
                return clean_tvs_json(decoded)  # recurse in case it's still a string
            except Exception:
                pass
        return data  # Return original string if not JSON

    elif isinstance(data, list):
        return [clean_tvs_json(item) for item in data]
        
    elif isinstance(data, dict):
        return {k: clean_tvs_json(v) for k, v in data.items()}
        
    return data


# ===========================================================================
#  API Client Class
# ===========================================================================

class TVSApiClient:
    """
    Wraps a requests.Session with token auth and rate-limited helpers.

    All public methods return parsed JSON (dict/list) or None on failure.
    """

    def __init__(self, dealer_id: str = DEFAULT_DEALER_ID):
        self.dealer_id = dealer_id
        self.session = requests.Session()
        self.session.headers.update(BROWSER_HEADERS)
        self.token = None

    # ── Internal request wrapper ───────────────────────────────────────

    def _get(self, endpoint: str, params: dict = None,
             timeout: int = 60) -> dict | list | None:
        """
        Make a GET request with auth headers and error handling.

        Args:
            endpoint: Relative API path (e.g., '/api/Catalouge/...').
            params: Optional query parameters.
            timeout: Request timeout in seconds.

        Returns:
            Parsed JSON response, or None on failure.
        """
        url = f"{BASE_URL}{endpoint}"
        try:
            if self.token:
                self.session.headers["Authorization"] = f"Bearer {self.token}"

            resp = self.session.get(url, params=params, timeout=timeout)

            # Handle WAF / Rate limits with a mandatory 30-second backoff
            retries = 3
            while resp.status_code in [403, 429] and retries > 0:
                log(f"Server returned {resp.status_code} (WAF/Rate Limit). Pausing 30s...", "WARN")
                time.sleep(30)
                resp = self.session.get(url, params=params, timeout=timeout)
                retries -= 1

            if resp.status_code == 200:
                data = resp.json()
                return clean_tvs_json(data)

            elif resp.status_code == 401:
                log(f"Auth expired (401). Re-authenticating...", "WARN")
                if self._authenticate():
                    self.session.headers["Authorization"] = f"Bearer {self.token}"
                    resp = self.session.get(url, params=params, timeout=timeout)
                    if resp.status_code == 200:
                        return clean_tvs_json(resp.json())
                log(f"Retry failed after re-auth: {resp.status_code}", "ERROR")
                return None

            elif resp.status_code == 404:
                # TVS API returns 404 when token is absent/expired — try re-auth once
                if not self.token:
                    log(f"HTTP 404 on {endpoint} — no token present. Authenticating...", "WARN")
                    if self._authenticate():
                        self.session.headers["Authorization"] = f"Bearer {self.token}"
                        resp = self.session.get(url, params=params, timeout=timeout)
                        if resp.status_code == 200:
                            return clean_tvs_json(resp.json())
                log(f"HTTP 404 from {endpoint} (full url: {url})", "ERROR")
                log(f"  → This endpoint may not exist or requires dealer authentication.", "WARN")
                return None

            else:
                log(f"HTTP {resp.status_code} from {endpoint} — url: {url}", "ERROR")
                return None

        except requests.exceptions.Timeout:
            log(f"Timeout on {endpoint}", "ERROR")
            return None
        except requests.exceptions.ConnectionError as e:
            log(f"Connection error on {endpoint}: {e}", "ERROR")
            return None
        except requests.exceptions.RequestException as e:
            log(f"Request error: {e}", "ERROR")
            return None
        except json.JSONDecodeError:
            log(f"Invalid JSON from {endpoint}", "ERROR")
            return None

    # ── Authentication ─────────────────────────────────────────────────

    def _authenticate(self) -> bool:
        """
        Call the tokenGeneration endpoint to get a Bearer token.

        The TVS API requires a specific JSON body:
            {"dealerId": 10001, "branchId": 1, "Type": "Customer"}
        Response contains: {"access_token": "<jwt_token>"}

        Returns:
            True if token was obtained, False otherwise.
        """
        url = f"{BASE_URL}/Setting/tokenGeneration"
        try:
            # The exact payload the TVS Angular frontend sends
            payload = {
                "dealerId": 10001,
                "branchId": 1,
                "Type": "Customer"
            }

            resp = self.session.post(
                url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=30
            )
            if resp.status_code == 200:
                data = resp.json()
                # Token is returned in the "access_token" field
                if isinstance(data, dict):
                    self.token = (
                        data.get("access_token")
                        or data.get("token")
                        or data.get("Token")
                        or None
                    )
                elif isinstance(data, str):
                    self.token = data

                if self.token:
                    log(f"Token acquired: {self.token[:50]}...", "OK")
                    return True
                else:
                    log(f"Token response had no token: {str(data)[:200]}", "ERROR")
                    return False
            else:
                log(f"Token request failed: HTTP {resp.status_code} — {resp.text[:200]}", "ERROR")
                return False

        except Exception as e:
            log(f"Token error: {e}", "ERROR")
            return False

    def ensure_authenticated(self) -> bool:
        """
        Guarantee we have a valid bearer token before calling protected endpoints.
        Returns True if authenticated, False otherwise.
        """
        if not self.token:
            log("No token present — authenticating before request...", "WARN")
            return self._authenticate()
        return True

    def connect(self) -> bool:
        """
        Initialize the session: authenticate and validate the connection.

        Returns:
            True if ready to make API calls, False otherwise.
        """
        log("Connecting to TVS Advantage API...", "FETCH")
        success = self._authenticate()
        if success:
            log("Connected and authenticated successfully.", "OK")
        else:
            log("Authentication failed. Will attempt unauthenticated calls.", "WARN")
        return success

    # ── Public API Methods ─────────────────────────────────────────────

    def get_categories(self) -> list | None:
        """Fetch menu categories (MOTORCYCLE, SCOOTER, SCOOTY, MOPED, etc.)."""
        log(f"Fetching vehicle categories (dealer={self.dealer_id})...", "FETCH")
        data = self._get(
            "/api/Catalouge/GetMenuCategory",
            params={"dealerID": self.dealer_id}
        )
        # Handle {"data": [...]} wrapping natively here
        if isinstance(data, dict) and "data" in data:
            data = data.get("data")
            
        if data:
            log(f"Found {len(data)} categories.", "OK")
        return data

    def get_models_by_category(self, category_id: str) -> list | None:
        """Fetch all vehicle models for a given category ID."""
        log(f"Fetching models for category_id={category_id}...", "FETCH")
        data = self._get(
            "/api/Catalouge/GetVehicalDataByCategoryID",
            params={"CATEGORY_ID": category_id, "dealerId": self.dealer_id}
        )
        if isinstance(data, dict) and "data" in data:
            data = data.get("data")
            
        if data:
            log(f"Found {len(data)} models.", "OK")
        return data

    def get_coordinates_by_series(self, series_id: str) -> dict | None:
        """
        Fetch hotspot coordinates (assembly areas) for a vehicle series.
        
        Returns a dict like:
            {"SERIES": "...", "IMAGE_LINK": "...", "coordinates": [...]}
        """
        log(f"Fetching hotspot coordinates for series={series_id}...", "FETCH")
        data = self._get(
            "/api/Catalouge/GetVehCoordinatesbySeries",
            params={"series": series_id}
        )
        if isinstance(data, dict) and "data" in data:
            data = data.get("data")

        # The API returns a single dict for a series, with a "coordinates" list inside
        if isinstance(data, dict):
            coords_list = data.get("coordinates", [])
            log(f"Found {len(coords_list)} hotspot(s).", "OK")
            return data
        # Sometimes it might return a list with one item
        elif isinstance(data, list) and len(data) > 0:
            item = _force_dict(data[0]) if len(data) == 1 else data
            if isinstance(item, dict):
                coords_list = item.get("coordinates", [])
                log(f"Found {len(coords_list)} hotspot(s).", "OK")
                return item
        
        log(f"No coordinate data found for series={series_id}.", "WARN")
        return None

    def get_parts_by_assembly(self, series_id: str,
                               assembly_id: str) -> list | None:
        """Fetch parts list for a specific assembly within a vehicle series."""
        data = self._get(
            "/api/Catalouge/GetPartDetailsByAssemblyID",
            params={
                "SERIES": series_id,
                "ASSEMBLY_ID": assembly_id,
                "DealerID": self.dealer_id,
            }
        )
        if isinstance(data, dict) and "data" in data:
            data = data.get("data")
        # The actual parts list is nested under "partDetails"
        if isinstance(data, dict) and "partDetails" in data:
            data = data.get("partDetails")
        return data if isinstance(data, list) else None

    # ── Painted Parts API Methods ───────────────────────────────────────

    def get_painted_models_with_colors(self, vehicle_type: str = "MOTORCYCLE") -> dict:
        """
        Fetch ALL painted-parts models AND their color variants for a vehicle type
        in a SINGLE API call.

        The TVS API consolidates everything in one response:
          data.imageData  → list of {ModelID, ColorID, name (color name), image, image2}
          data.tabData    → list of series groups (just for display, not synced)
          data.innerDate  → list of model entries (without colors, used for display only)

        Returns:
            {
              "models":   list of innerDate entries (for names/display),
              "colors":   list of imageData entries (ModelID + ColorID pairs),
            }
        """
        self.ensure_authenticated()
        log(f"[Painted] Fetching models+colors for type={vehicle_type}...", "FETCH")
        raw = self._get(
            "/api/Catalouge/GetPaintedModelDetails",
            params={"Type": vehicle_type, "dealerId": self.dealer_id}
        )
        inner_data = {}
        if isinstance(raw, dict) and "data" in raw:
            inner_data = raw.get("data") or {}

        image_data = inner_data.get("imageData") or []
        inner_date = inner_data.get("innerDate") or []

        # Filter out entries with blank ModelIDs from imageData
        valid_colors = [
            entry for entry in image_data
            if isinstance(entry, dict)
            and str(entry.get("ModelID") or "").strip()
            and str(entry.get("ColorID") or "").strip()
        ]
        log(f"[Painted] {vehicle_type}: {len(inner_date)} models, {len(valid_colors)} color variants.", "OK")
        return {"models": inner_date, "colors": valid_colors}

    def get_painted_parts_by_color(self, model_id: str, color_id: str,
                                    fig_no: str) -> list | None:
        """
        Fetch painted parts list for a specific model + color combination.
        Requires bearer token — 404 if unauthenticated.
        """
        self.ensure_authenticated()
        log(f"[Painted] Fetching parts for model={model_id}, color={color_id}...", "FETCH")
        data = self._get(
            "/api/Catalouge/GetPaintedPartDetailsByModelID",
            params={
                "MODEL_ID": model_id,
                "COLOR_ID": color_id,
                "FIG_NO": fig_no,
                "DealerID": self.dealer_id,
            }
        )
        if isinstance(data, dict) and "data" in data:
            data = data.get("data")
        if isinstance(data, dict) and "partDetails" in data:
            data = data.get("partDetails")
        if isinstance(data, list):
            log(f"[Painted] Found {len(data)} painted part(s).", "OK")
        return data if isinstance(data, list) else None


#  Database Injection Logic
# ===========================================================================

def _force_dict(obj) -> dict:
    """Ensure an object is a dictionary (parses stray JSON strings)."""
    if isinstance(obj, dict):
        return obj
    if isinstance(obj, str):
        try:
            parsed = json.loads(obj)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return {}

def _safe_float(val, default=0.0) -> float:
    """Safely convert any value to float."""
    try:
        return float(val) if val else default
    except (ValueError, TypeError):
        return default


def _safe_str(val, default="") -> str:
    """Safely convert any value to stripped string."""
    return str(val).strip() if val else default


def inject_model_data(conn, category_name: str, model_info: dict,
                      parts_list: list) -> dict:
    """
    Inject one model's data into the database.

    Args:
        conn:          SQLite connection.
        category_name: Segment name (e.g., 'MOTORCYCLE').
        model_info:    Dict with model metadata from the API.
        parts_list:    List of part dicts from GetPartDetailsByAssemblyID.

    Returns:
        Stats dict: { vehicles: int, parts: int, mappings: int }
    """
    stats = {"vehicles": 0, "parts": 0, "mappings": 0}

    # Extract model fields — API key casing may vary
    brand = "TVS"
    segment = _safe_str(category_name)
    series = _safe_str(
        model_info.get("series") or model_info.get("SERIES") or model_info.get("SERIES_ID")
        or model_info.get("seriesId") or model_info.get("Series_Id")
        or ""
    )
    model_name = _safe_str(
        model_info.get("DESCRIPTION") or model_info.get("name") or model_info.get("SERIES_NAME")
        or model_info.get("seriesName") or model_info.get("MODEL_NAME")
        or model_info.get("modelName") or model_info.get("Model")
        or ""
    )
    variant = _safe_str(
        model_info.get("VARIANT")
        or model_info.get("variant")
        or model_info.get("Variant")
        or ""
    )

    # Insert vehicle (or get existing)
    vehicle_id = insert_vehicle(conn, brand, segment, series, model_name, variant)
    if vehicle_id:
        stats["vehicles"] = 1

    # Accumulate parts and mappings for batch insert
    parts_batch = []
    mappings_batch = []
    seen_parts = set()
    now = datetime.now().isoformat()

    for part in parts_list:
        part_code = _safe_str(
            part.get("PART_NO") or part.get("PART_NUMBER")
            or part.get("PartNo") or part.get("partNumber")
            or part.get("PARTNO") or part.get("partNo")
            or part.get("part_number") or part.get("Part_Number")
            or ""
        )
        if not part_code:
            continue

        description = _safe_str(
            part.get("PART_DESC") or part.get("DESCRIPTION")
            or part.get("PartDescription") or part.get("description")
            or ""
        )
        category = _safe_str(
            part.get("INJECTED_ASSEMBLY_NAME")
            or part.get("ASSEMBLY")
            or part.get("Assembly")
            or part.get("assembly")
            or part.get("ASSEMBLY_NAME")
            or ""
        )
        mrp = _safe_float(
            part.get("MRP")
            or part.get("mrp")
            or 0
        )
        ndp = _safe_float(
            part.get("NDP")
            or part.get("ndp")
            or part.get("NDP_PRICE")
            or 0
        )

        parts_batch.append((
            part_code, description, category, mrp, ndp, 0, "", now
        ))

        if part_code not in seen_parts:
            seen_parts.add(part_code)
            stats["parts"] += 1

        if vehicle_id:
            mappings_batch.append((part_code, vehicle_id))
            stats["mappings"] += 1

    # Batch flush
    if parts_batch:
        batch_upsert_parts(conn, parts_batch)
    if mappings_batch:
        batch_insert_compatibility(conn, mappings_batch)

    return stats


def save_hotspot_data(conn, series_id: str, coord_response: dict):
    """
    Save hotspot coordinate data to both:
        1. The visual_coordinates DB table
        2. A local JSON file in assets/hotspots/{series_id}.json
    
    coord_response is a dict like:
        {"SERIES": "...", "IMAGE_LINK": "...", "coordinates": [...]}
    """
    image_url = _safe_str(coord_response.get("IMAGE_LINK") or "")
    coordinates = coord_response.get("coordinates", [])
    
    # ── Save to database ──────────────────────────────────────────────
    now = datetime.now().isoformat()
    for coord in coordinates:
        coord = _force_dict(coord)
        assembly_id = _safe_str(
            coord.get("ASSEMBLY_ID")
            or coord.get("assemblyId")
            or ""
        )
        assembly_name = _safe_str(
            coord.get("ASSEMBLY_NAME")
            or coord.get("assemblyName")
            or ""
        )
        # Use the top-level IMAGE_LINK if individual coord has none
        coord_image = _safe_str(coord.get("IMAGE_LINK") or "") or image_url
        coord_json = json.dumps(coord)

        if assembly_id:
            conn.execute(
                """
                INSERT INTO visual_coordinates
                    (series_id, assembly_id, assembly_name, coord_data, image_url, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(series_id, assembly_id) DO UPDATE SET
                    assembly_name = excluded.assembly_name,
                    coord_data    = excluded.coord_data,
                    image_url     = excluded.image_url,
                    last_updated  = excluded.last_updated
                """,
                (series_id, assembly_id, assembly_name, coord_json, coord_image, now)
            )

    # ── Save as local JSON file ───────────────────────────────────────
    os.makedirs(HOTSPOTS_DIR, exist_ok=True)
    json_path = os.path.join(HOTSPOTS_DIR, f"{series_id}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(coord_response, f, indent=2, ensure_ascii=False)
    log(f"Saved hotspot JSON → {json_path}", "DB")


# ===========================================================================
#  Main Sync Orchestrator
# ===========================================================================

def run_sync(db_path: str = DEFAULT_DB_PATH,
             dealer_id: str = DEFAULT_DEALER_ID,
             target_category: str = None,
             target_series: str = None,
             progress_callback=None):
    """
    Main sync function. Orchestrates the full data extraction pipeline.

    Pipeline:
        1. Connect & authenticate
        2. Fetch categories → filter if --category flag used
        3. For each category → fetch models
        4. For each model → fetch coordinates (hotspots)
        5. For each hotspot assembly → fetch parts
        6. Inject everything into SQLite

    Args:
        db_path:           Path to the SQLite database.
        dealer_id:         TVS dealer ID.
        target_category:   Optional category name filter (e.g., 'MOTORCYCLE').
        target_series:     Optional specific series ID to sync only one model.
        progress_callback: Optional callable(pct: int, msg: str) to report progress.
    """
    print("\n" + "=" * 60)
    print("  🚀  NEXSES API SYNC ENGINE  — Starting")
    print("=" * 60 + "\n")

    # ── Step 0: Initialize DB ─────────────────────────────────────────
    initialize_database(db_path)
    conn = get_connection(db_path)

    # ── Step 1: Connect to API ────────────────────────────────────────
    client = TVSApiClient(dealer_id)
    client.connect()
    stealth_sleep(1.5, 3.0)

    # ── Step 2: Fetch categories ──────────────────────────────────────
    categories = client.get_categories()
    if not categories:
        log("Failed to fetch categories. Aborting.", "ERROR")
        conn.close()
        return

    # Filter to target category if specified
    if target_category:
        filtered_c = []
        for c in categories:
            c = _force_dict(c)
            name = _safe_str(c.get("name") or c.get("CATEGORY_NAME") or c.get("categoryName") or "")
            if name.strip().upper() == target_category.strip().upper():
                filtered_c.append(c)
                
        categories = filtered_c
        if not categories:
            log(f"Category '{target_category}' not found.", "ERROR")
            conn.close()
            return

    # Print discovered categories
    print("\n  📂  Categories found:")
    
    for cat in categories:
        cat = _force_dict(cat)
        cat_name = (cat.get("name") or cat.get("CATEGORY_NAME") or cat.get("categoryName")
                    or cat.get("Category_Name") or "Unknown")
        cat_id = (cat.get("CATEGORY_ID") or cat.get("categoryId")
                  or cat.get("Category_Id") or "?")
        print(f"       • {cat_name} (ID: {cat_id})")
    print()

    # ── Step 3: Iterate categories → models → assemblies → parts ─────
    total_stats = {"vehicles": 0, "parts": 0, "mappings": 0,
                   "hotspots": 0, "errors": 0}

    for cat_idx, cat in enumerate(categories, 1):
        cat = _force_dict(cat)
        cat_name = _safe_str(
            cat.get("name") or cat.get("CATEGORY_NAME") or cat.get("categoryName")
            or cat.get("Category_Name") or "Unknown"
        )
        cat_id = str(
            cat.get("CATEGORY_ID") or cat.get("categoryId")
            or cat.get("Category_Id") or ""
        )

        print(f"\n{'─' * 60}")
        print(f"  📂  [{cat_idx}/{len(categories)}] Category: {cat_name}")
        print(f"{'─' * 60}")

        stealth_sleep()

        # Fetch models for this category
        models = client.get_models_by_category(cat_id)
        if not models:
            log(f"No models found for {cat_name}.", "WARN")
            total_stats["errors"] += 1
            continue

        log(f"Processing {len(models)} model(s) in {cat_name}...", "INFO")

        for mdl_idx, model in enumerate(models, 1):
            model = _force_dict(model)
            model_name = _safe_str(
                model.get("DESCRIPTION") or model.get("name") or model.get("SERIES_NAME") or model.get("seriesName")
                or model.get("MODEL_NAME") or model.get("modelName")
                or "Unknown"
            )
            series_id = str(
                model.get("series") or model.get("SERIES") or model.get("SERIES_ID")
                or model.get("seriesId") or model.get("Series_Id")
                or ""
            )

            if not series_id:
                log(f"Skipping model with no series ID: {model_name}", "WARN")
                continue

            # If a specific target series was requested, skip all others
            if target_series and series_id != target_series:
                continue

            # ── RESUME: skip if already fully synced ──────────────────
            if is_synced(conn, 'vehicle', series_id):
                log(f"[SKIP] {model_name} (series={series_id}) already synced.", "OK")
                total_stats["skipped"] = total_stats.get("skipped", 0) + 1
                continue

            print(f"\n    🏕️  [{mdl_idx}/{len(models)}] {model_name} "
                  f"(series={series_id})")

            stealth_sleep()

            # ── Fetch hotspot coordinates ─────────────────────────────
            coord_response = client.get_coordinates_by_series(series_id)
            if coord_response:
                save_hotspot_data(conn, series_id, coord_response)
                coord_list = coord_response.get("coordinates", [])
                total_stats["hotspots"] += len(coord_list)
                conn.commit()
            else:
                log(f"No hotspots for {model_name}.", "WARN")
                continue    # no assemblies means no parts to fetch

            # ── Fetch parts for each assembly ─────────────────────────
            all_parts_for_model = []
            coord_list = coord_response.get("coordinates", [])

            total_assemblies = len(coord_list)

            for assy_idx, coord in enumerate(coord_list, 1):
                coord = _force_dict(coord)
                assembly_id = str(
                    coord.get("ASSEMBLY_ID") or coord.get("assemblyId")
                    or coord.get("Assembly_Id") or ""
                )
                assembly_name = _safe_str(
                    coord.get("ASSEMBLY_NAME") or coord.get("assemblyName")
                    or ""
                )

                if not assembly_id:
                    continue

                if progress_callback:
                    pct = int((assy_idx / total_assemblies) * 100)
                    progress_callback(pct, f"Downloading parts for {assembly_name}...")

                stealth_sleep(1.5, 3.5)     # shorter delay between assemblies

                log(f"Fetching parts: {assembly_name} "
                    f"(assembly={assembly_id})...", "FETCH")

                parts = client.get_parts_by_assembly(series_id, assembly_id)
                if parts:
                    parts = [_force_dict(p) for p in parts]
                    # Directly inject the parent assembly name to guarantee 100% accuracy
                    for p in parts:
                        p["INJECTED_ASSEMBLY_NAME"] = assembly_name
                    
                    log(f"Extracted {len(parts)} part(s) from {assembly_name}.",
                        "OK")
                    all_parts_for_model.extend(parts)
                else:
                    log(f"No parts for assembly {assembly_name}.", "WARN")
                    total_stats["errors"] += 1

            # ── Inject model + parts into DB ──────────────────────────
            if all_parts_for_model:
                stats = inject_model_data(conn, cat_name, model,
                                          all_parts_for_model)
                conn.commit()
                # ── CHECKPOINT: mark this series as done ──────────────
                mark_synced(conn, 'vehicle', series_id)

                total_stats["vehicles"] += stats["vehicles"]
                total_stats["parts"] += stats["parts"]
                total_stats["mappings"] += stats["mappings"]

                log(f"💾 {model_name}: {stats['parts']} parts, "
                    f"{stats['mappings']} mappings saved.", "DB")
            else:
                log(f"No parts extracted for {model_name}.", "WARN")

    # ── Final summary ─────────────────────────────────────────────────
    conn.close()

    print(f"\n{'=' * 60}")
    print(f"  ✅  SYNC COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Vehicles inserted : {total_stats['vehicles']}")
    print(f"  Parts upserted    : {total_stats['parts']}")
    print(f"  Mappings created  : {total_stats['mappings']}")
    print(f"  Hotspots saved    : {total_stats['hotspots']}")
    print(f"  Errors            : {total_stats['errors']}")
    print(f"  Database          : {db_path}")
    print(f"{'=' * 60}\n")


# ===========================================================================
#  Painted Parts Sync Orchestrator
# ===========================================================================

PAINTED_PART_TYPES = ["MOTORCYCLE", "SCOOTER", "SCOOTY", "MOPED"]

def run_painted_parts_sync(db_path: str = DEFAULT_DB_PATH,
                            dealer_id: str = DEFAULT_DEALER_ID,
                            vehicle_type: str = None,
                            model_id: str = None,
                            progress_callback=None):
    """
    Sync Painted Parts from the TVS eCatalog.

    Pipeline:
        1. Connect & authenticate
        2. For each vehicle type (MOTORCYCLE / SCOOTER / SCOOTY / MOPED):
           a. Fetch ALL models + color variants in ONE call → get_painted_models_with_colors()
              (The TVS API bundles models and colors in imageData of the same response)
           b. Build a model_id → model_name lookup from innerDate
           c. For each color entry (ModelID + ColorID) → fetch parts
              (filtered to model_id if supplied)
           d. Inject parts + vehicle mapping into catalog DB

    Args:
        db_path:           Path to the SQLite catalog database.
        dealer_id:         TVS dealer ID.
        vehicle_type:      Optional filter to sync only one type (e.g. 'MOTORCYCLE').
        model_id:          Optional filter to sync only one specific model ID.
        progress_callback: Optional callable(pct: int, msg: str).
    """
    print("\n" + "=" * 60)
    print("  PAINTED PARTS SYNC - Starting")
    print("=" * 60 + "\n")

    initialize_database(db_path)
    conn = get_connection(db_path)

    client = TVSApiClient(dealer_id)
    client.connect()
    stealth_sleep(1.0, 2.0)

    types_to_sync = [vehicle_type] if vehicle_type else PAINTED_PART_TYPES
    total_stats = {"parts": 0, "mappings": 0, "errors": 0}

    for vtype in types_to_sync:
        print(f"\n{'─' * 60}")
        print(f"  Vehicle Type: {vtype}")
        print(f"{'─' * 60}")

        result = client.get_painted_models_with_colors(vehicle_type=vtype)
        color_entries = result.get("colors", [])
        model_entries = result.get("models", [])

        if not color_entries:
            log(f"[Painted] No color variants found for {vtype}.", "WARN")
            total_stats["errors"] += 1
            continue

        # ── Helper: extract readable name from a TVS image URL ───────────────
        import re as _re
        _SKIP_UI = {
            "go button", "o button", "button", "icon", "logo", "bg",
            "background", "arrow", "menu", "nav", "left arrow",
            "right arrow", "home", "back", "logo button",
            "cover page", "cover", "page",
        }
        _LOGO_PREFIXES = ("logo button ", "logo ", "button ")
        _LOGO_SUFFIXES = (" logo button", " logo", " button")

        def _name_from_url(url: str) -> str:
            if not url:
                return ""
            tail = url.rstrip("/").split("/")[-1]
            tail = _re.sub(r'\.(png|jpg|gif|svg|webp)$', '', tail, flags=_re.I)
            tail = tail.replace("-", " ").replace("_", " ").strip()
            for pfx in _LOGO_PREFIXES:
                if tail.lower().startswith(pfx):
                    tail = tail[len(pfx):].strip()
                    break
            for sfx in _LOGO_SUFFIXES:
                if tail.lower().endswith(sfx):
                    tail = tail[:-len(sfx)].strip()
                    break
            if tail.lower() in _SKIP_UI or len(tail) <= 2:
                return ""
            if not _re.search(r'[A-Za-z]', tail):
                return ""
            return tail.upper()

        # Build model_id → readable name lookup
        # Priority: image URL extraction > s_levelName > fallback label
        model_cache = {}
        for m in model_entries:
            m = _force_dict(m)
            mid = _safe_str(m.get("ModelID") or "").strip()
            if not mid:
                continue
            name = _name_from_url(_safe_str(m.get("image") or ""))
            if not name:
                name = _name_from_url(_safe_str(m.get("image2") or ""))
            if not name:
                lvl = _safe_str(m.get("s_levelName") or "")
                if _re.search(r'[A-Za-z]{3,}', lvl):
                    name = lvl.upper()
            if name and mid not in model_cache:
                model_cache[mid] = name

        # If a specific model was requested, filter down to only its color entries
        if model_id:
            color_entries = [e for e in color_entries
                             if _safe_str(e.get("ModelID") or "").strip() == model_id.strip()]
            log(f"[Painted] Filtered to model_id={model_id}: {len(color_entries)} color variant(s).", "INFO")
        else:
            log(f"[Painted] {len(color_entries)} color variants to process for {vtype}...", "INFO")

        for clr_idx, color_entry in enumerate(color_entries, 1):
            color_entry = _force_dict(color_entry)
            model_id = _safe_str(color_entry.get("ModelID") or "").strip()
            color_id = _safe_str(color_entry.get("ColorID") or "").strip()
            color_name = _safe_str(color_entry.get("name") or "")   # 'name' field = color name in imageData

            if not model_id or not color_id:
                continue

            # Resolve model name (fallback to ID tail if not in lookup)
            model_name = model_cache.get(model_id, f"Model #{model_id[-6:]}")

            if progress_callback:
                pct = int((clr_idx / len(color_entries)) * 95)
                progress_callback(pct, f"[Painted] {vtype}: {model_name} / {color_name}...")

            # ── RESUME: skip if already synced ───────────────────────────
            if is_synced(conn, 'painted', model_id, color_id):
                log(f"[SKIP] {model_name} / {color_name} already synced.", "OK")
                total_stats["skipped"] = total_stats.get("skipped", 0) + 1
                continue

            # Ensure vehicle row exists in vehicles_master
            # series = readable name (shown in tree), variant = raw model_id for traceability
            readable_series = model_name if model_name else f"Model #{model_id[-6:]}"
            vehicle_id = insert_vehicle(conn, "TVS", f"PAINTED_{vtype}",
                                        readable_series, readable_series, model_id)
            # Patch any previously synced row that still has a numeric series/model_name
            conn.execute(
                """UPDATE vehicles_master SET series=?, model_name=?, variant=?
                   WHERE segment=? AND variant=? AND (series=? OR series=? OR model_name=?)""",
                (readable_series, readable_series, model_id,
                 f"PAINTED_{vtype}", model_id,
                 model_id, model_id[:8] if len(model_id) > 8 else model_id, model_id)
            )

            stealth_sleep(0.5, 1.5)
            fig_no = color_id   # FIG_NO = ColorID in TVS painted parts API
            parts = client.get_painted_parts_by_color(model_id, color_id, fig_no)
            if not parts:
                log(f"[Painted] No parts for {model_name} / {color_name}.", "WARN")
                continue

            parts_batch = []
            mappings_batch = []
            now = datetime.now().isoformat()

            for part in parts:
                part = _force_dict(part)
                part_code = _safe_str(
                    part.get("PART_NO") or part.get("PartNo") or part.get("partNo") or ""
                )
                if not part_code:
                    continue

                desc = _safe_str(
                    part.get("PART_DESC") or part.get("PartDescription") or
                    part.get("PART_NAME") or part.get("description") or ""
                )
                cat = f"PAINTED PARTS / {color_name}" if color_name else "PAINTED PARTS"
                mrp = _safe_float(part.get("MRP") or part.get("mrp") or 0)
                ndp = _safe_float(part.get("NDP") or part.get("ndp") or 0)
                moq = int(part.get("MOQ") or part.get("moq") or 1)

                parts_batch.append((part_code, desc, cat, mrp, ndp, moq, "", now))
                if vehicle_id:
                    mappings_batch.append((part_code, vehicle_id))
                    total_stats["mappings"] += 1
                total_stats["parts"] += 1

            if parts_batch:
                batch_upsert_parts(conn, parts_batch)
            if mappings_batch:
                batch_insert_compatibility(conn, mappings_batch)

            conn.commit()
            mark_synced(conn, 'painted', model_id, color_id)
            log(f"[Painted] {model_name} / {color_name}: {len(parts_batch)} parts saved.", "DB")


    conn.close()

    print(f"\n{'=' * 60}")
    print(f"  ✅  PAINTED PARTS SYNC COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Parts upserted  : {total_stats['parts']}")
    print(f"  Mappings created: {total_stats['mappings']}")
    print(f"  Errors          : {total_stats['errors']}")
    print(f"  Database        : {db_path}")
    print(f"{'=' * 60}\n")


# ===========================================================================
#  CLI Entry Point
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Nexses API Sync Engine — TVS eCatalog data downloader"
    )
    parser.add_argument(
        "--dealer-id", default=DEFAULT_DEALER_ID,
        help=f"TVS Dealer ID (default: {DEFAULT_DEALER_ID})"
    )
    parser.add_argument(
        "--db-path", default=DEFAULT_DB_PATH,
        help="Path to SQLite database"
    )
    parser.add_argument(
        "--category", default=None,
        help="Sync only one category (e.g., MOTORCYCLE, SCOOTER)"
    )
    parser.add_argument(
        "--categories-only", action="store_true",
        help="Only list available categories, don't sync data"
    )

    args = parser.parse_args()

    if args.categories_only:
        # Quick mode: just list the categories
        client = TVSApiClient(args.dealer_id)
        client.connect()
        stealth_sleep(1, 2)
        categories = client.get_categories()
        if categories:
            print("\n  Available categories:")
            for c in categories:
                c = _force_dict(c)
                name = (c.get("name") or c.get("CATEGORY_NAME") or c.get("categoryName")
                        or c.get("Category_Name") or "?")
                cid = (c.get("CATEGORY_ID") or c.get("categoryId")
                       or c.get("Category_Id") or "?")
                print(f"    • {name} (ID: {cid})")
            print()
        else:
            log("Failed to fetch categories.", "ERROR")
        return

    # Full sync
    run_sync(
        db_path=args.db_path,
        dealer_id=args.dealer_id,
        target_category=args.category,
    )


if __name__ == "__main__":
    main()
