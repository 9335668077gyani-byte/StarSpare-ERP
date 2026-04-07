"""
db_engine.py — Database Engine for Nexses e-Catalog
=====================================================

Handles all SQLite database initialization, schema creation, and
low-level CRUD helper functions. Every other module imports this
to interact with the database.

Schema (3 core tables):
    - vehicles_master   : Unique vehicle definitions (brand, segment, series, model, variant)
    - parts_master      : Unique part definitions (part_code PK, description, pricing, etc.)
    - compatibility_map : Many-to-many bridge linking parts ↔ vehicles

Design decisions:
    - Brand is hardcoded to 'TVS' (single-brand catalog for now).
    - SEGMENT_NAME from CSV maps to `segment`, SERIES_NAME maps to `series`.
    - `last_updated` TIMESTAMP on all tables for future sync/audit.
    - `diagram_ref` in parts_master prepares for Phase 2 visual hotspot loading.
    - Performance indexes on part_code, description, and the composite FK pair.
"""

import sqlite3
import os
from datetime import datetime


# ---------------------------------------------------------------------------
#  Default database path (read-only bundled catalog)
# ---------------------------------------------------------------------------
import sys as _sys
try:
    from path_utils import get_resource_path as _get_resource_path
    DEFAULT_DB_PATH = _get_resource_path("nexses_ecatalog.db")
except Exception:
    DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nexses_ecatalog.db")

# Writable base dir (used by modules that need the AppData location)
try:
    from path_utils import get_app_data_path as _get_app_data_path
    DEFAULT_DB_DIR = _get_app_data_path("data")
except Exception:
    DEFAULT_DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database")


# ===========================================================================
#  Connection Helper
# ===========================================================================

def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """
    Open (or create) a SQLite connection with foreign-key enforcement ON.

    Args:
        db_path: Absolute or relative path to the .db file.
                 Use ":memory:" for unit-testing.

    Returns:
        sqlite3.Connection with row_factory set to sqlite3.Row for
        dict-like access on query results.
    """
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")       # enforce FK constraints
    conn.execute("PRAGMA journal_mode = WAL;")       # better concurrent-read perf
    conn.row_factory = sqlite3.Row                   # rows behave like dicts
    return conn


# ===========================================================================
#  Schema Initialization
# ===========================================================================

# ---- SQL statements kept as module-level constants for clarity -------------

_CREATE_VEHICLES_MASTER = """
CREATE TABLE IF NOT EXISTS vehicles_master (
    vehicle_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    brand        TEXT    NOT NULL DEFAULT 'TVS',
    segment      TEXT    NOT NULL DEFAULT '',
    series       TEXT    NOT NULL DEFAULT '',
    model_name   TEXT    NOT NULL DEFAULT '',
    variant      TEXT    NOT NULL DEFAULT '',
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Prevent duplicate vehicle rows
    UNIQUE (brand, segment, series, model_name, variant)
);
"""

_CREATE_PARTS_MASTER = """
CREATE TABLE IF NOT EXISTS parts_master (
    part_code    TEXT    PRIMARY KEY,
    description  TEXT    NOT NULL DEFAULT '',
    category     TEXT    NOT NULL DEFAULT '',
    mrp          REAL    NOT NULL DEFAULT 0.0,
    ndp          REAL    NOT NULL DEFAULT 0.0,
    moq          INTEGER NOT NULL DEFAULT 0,
    remarks      TEXT    NOT NULL DEFAULT '',
    diagram_ref  TEXT    DEFAULT NULL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_CREATE_COMPATIBILITY_MAP = """
CREATE TABLE IF NOT EXISTS compatibility_map (
    map_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    part_code    TEXT    NOT NULL,
    vehicle_id   INTEGER NOT NULL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Referential integrity
    FOREIGN KEY (part_code)  REFERENCES parts_master   (part_code),
    FOREIGN KEY (vehicle_id) REFERENCES vehicles_master (vehicle_id),

    -- One mapping per (part, vehicle) pair
    UNIQUE (part_code, vehicle_id)
);
"""

_CREATE_VISUAL_COORDINATES = """
CREATE TABLE IF NOT EXISTS visual_coordinates (
    coord_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    series_id     TEXT    NOT NULL,
    assembly_id   TEXT    NOT NULL,
    assembly_name TEXT    NOT NULL DEFAULT '',
    coord_data    TEXT    NOT NULL DEFAULT '[]',
    image_url     TEXT    DEFAULT NULL,
    last_updated  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (series_id, assembly_id)
);
"""

# Checkpoint table — tracks what has already been synced
# so interrupted syncs can resume from where they left off.
_CREATE_SYNC_PROGRESS = """
CREATE TABLE IF NOT EXISTS sync_progress (
    sync_type  TEXT NOT NULL,   -- 'vehicle' | 'painted'
    key1       TEXT NOT NULL,   -- series_id  (vehicle) | model_id  (painted)
    key2       TEXT NOT NULL DEFAULT '',  -- '' (vehicle) | color_id (painted)
    synced_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (sync_type, key1, key2)
);
"""

# ---- Performance indexes --------------------------------------------------

_CREATE_INDEXES = [
    # Speed up text searches on part description (Nexses AI will use this)
    "CREATE INDEX IF NOT EXISTS idx_parts_description ON parts_master (description);",

    # Speed up lookups by part_code in the bridge table
    "CREATE INDEX IF NOT EXISTS idx_compat_part_code  ON compatibility_map (part_code);",

    # Speed up lookups by vehicle_id in the bridge table
    "CREATE INDEX IF NOT EXISTS idx_compat_vehicle_id ON compatibility_map (vehicle_id);",

    # Speed up vehicle filtering by series/model (left-panel tree)
    "CREATE INDEX IF NOT EXISTS idx_vehicles_series   ON vehicles_master (series, model_name);",
]


def initialize_database(db_path: str = DEFAULT_DB_PATH) -> None:
    """
    Create the database file (if it doesn't exist) and ensure all tables
    and indexes are present.

    Safe to call on every application startup — uses IF NOT EXISTS guards.

    Args:
        db_path: Path to the SQLite database file.
    """
    # Ensure the directory exists (skip for in-memory DBs used in tests)
    if db_path != ":memory:":
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()

        # --- Create core tables ---
        cursor.execute(_CREATE_VEHICLES_MASTER)
        cursor.execute(_CREATE_PARTS_MASTER)
        cursor.execute(_CREATE_COMPATIBILITY_MAP)
        cursor.execute(_CREATE_VISUAL_COORDINATES)
        cursor.execute(_CREATE_SYNC_PROGRESS)   # <-- checkpoint table

        # --- Create performance indexes ---
        for idx_sql in _CREATE_INDEXES:
            cursor.execute(idx_sql)

        conn.commit()
        print(f"[db_engine] Database initialized at: {db_path}")
    finally:
        conn.close()


# ===========================================================================
#  CRUD Helper Functions
# ===========================================================================

def get_vehicle_id(conn: sqlite3.Connection,
                   brand: str, segment: str, series: str,
                   model_name: str, variant: str) -> int | None:
    """
    Look up a vehicle by its full composite key.

    Returns:
        The vehicle_id if found, otherwise None.
    """
    cursor = conn.execute(
        """
        SELECT vehicle_id FROM vehicles_master
        WHERE brand = ? AND segment = ? AND series = ?
          AND model_name = ? AND variant = ?
        """,
        (brand, segment, series, model_name, variant)
    )
    row = cursor.fetchone()
    return row["vehicle_id"] if row else None


def insert_vehicle(conn: sqlite3.Connection,
                   brand: str, segment: str, series: str,
                   model_name: str, variant: str) -> int:
    """
    Insert a new vehicle row. If the exact combination already exists,
    the INSERT OR IGNORE silently skips and we return the existing id.

    Returns:
        vehicle_id of the inserted (or existing) row.
    """
    conn.execute(
        """
        INSERT OR IGNORE INTO vehicles_master
            (brand, segment, series, model_name, variant)
        VALUES (?, ?, ?, ?, ?)
        """,
        (brand, segment, series, model_name, variant)
    )
    # Retrieve the id whether it was just inserted or already existed
    vid = get_vehicle_id(conn, brand, segment, series, model_name, variant)
    return vid


def upsert_part(conn: sqlite3.Connection,
                part_code: str, description: str, category: str,
                mrp: float, ndp: float = 0.0,
                moq: int = 0, remarks: str = "") -> None:
    """
    Insert a part or update it if the part_code already exists.
    This ensures MRP/NDP updates propagate on re-import without
    duplicating records.
    """
    conn.execute(
        """
        INSERT INTO parts_master
            (part_code, description, category, mrp, ndp, moq, remarks, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(part_code) DO UPDATE SET
            description  = excluded.description,
            category     = excluded.category,
            mrp          = excluded.mrp,
            ndp          = excluded.ndp,
            moq          = excluded.moq,
            remarks      = excluded.remarks,
            last_updated = excluded.last_updated
        """,
        (part_code, description, category, mrp, ndp, moq, remarks,
         datetime.now().isoformat())
    )


def insert_compatibility(conn: sqlite3.Connection,
                         part_code: str, vehicle_id: int) -> None:
    """
    Map a part to a vehicle. Silently ignores if the mapping already exists
    (thanks to the UNIQUE constraint + INSERT OR IGNORE).
    """
    conn.execute(
        """
        INSERT OR IGNORE INTO compatibility_map (part_code, vehicle_id)
        VALUES (?, ?)
        """,
        (part_code, vehicle_id)
    )


# ===========================================================================
#  Batch Insert Helpers  (used by data_importer for executemany)
# ===========================================================================

def batch_upsert_parts(conn: sqlite3.Connection,
                       parts_data: list[tuple]) -> None:
    """
    Batch-insert/update parts using executemany for performance.

    Args:
        parts_data: List of tuples, each:
            (part_code, description, category, mrp, ndp, moq, remarks, last_updated)
    """
    conn.executemany(
        """
        INSERT INTO parts_master
            (part_code, description, category, mrp, ndp, moq, remarks, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(part_code) DO UPDATE SET
            description  = excluded.description,
            category     = excluded.category,
            mrp          = excluded.mrp,
            ndp          = excluded.ndp,
            moq          = excluded.moq,
            remarks      = excluded.remarks,
            last_updated = excluded.last_updated
        """,
        parts_data
    )


def batch_insert_compatibility(conn: sqlite3.Connection,
                               mappings: list[tuple]) -> None:
    """
    Batch-insert compatibility mappings using executemany.

    Args:
        mappings: List of (part_code, vehicle_id) tuples.
    """
    conn.executemany(
        """
        INSERT OR IGNORE INTO compatibility_map (part_code, vehicle_id)
        VALUES (?, ?)
        """,
        mappings
    )


# ===========================================================================
#  Query Helpers  (used by UI and Nexses AI)
# ===========================================================================

def search_parts(conn: sqlite3.Connection, keyword: str) -> list[dict]:
    """
    Search parts by partial match on part_code or description.
    Returns a list of dicts with part info.
    """
    if not keyword:
        # Return empty list or a default fast query to avoid full table scan
        cursor = conn.execute(
            """
            SELECT part_code, description, category, mrp, ndp, moq, remarks
            FROM parts_master
            ORDER BY part_code
            LIMIT 500
            """
        )
        return [dict(row) for row in cursor.fetchall()]

    cursor = conn.execute(
        """
        SELECT part_code, description, category, mrp, ndp, moq, remarks
        FROM parts_master
        WHERE part_code LIKE ? OR description LIKE ?
        ORDER BY part_code
        LIMIT 500
        """,
        (f"%{keyword}%", f"%{keyword}%")
    )
    return [dict(row) for row in cursor.fetchall()]


def get_parts_by_vehicle(conn: sqlite3.Connection,
                         vehicle_id: int, category: str = None) -> list[dict]:
    """
    Retrieve all parts compatible with a given vehicle.
    Optionally filter to a specific category (assembly).
    """
    query = """
        SELECT p.part_code, p.description, p.category,
               p.mrp, p.ndp, p.moq, p.remarks
        FROM parts_master p
        JOIN compatibility_map cm ON p.part_code = cm.part_code
        WHERE cm.vehicle_id = ?
    """
    params = [vehicle_id]

    if category:
        query += " AND p.category = ?"
        params.append(category)

    query += " ORDER BY p.category, p.part_code"

    cursor = conn.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def get_vehicles_by_part(conn: sqlite3.Connection,
                         part_code: str) -> list[dict]:
    """
    Retrieve all vehicles that use a given part_code.
    """
    cursor = conn.execute(
        """
        SELECT v.vehicle_id, v.brand, v.segment, v.series, v.model_name, v.variant
        FROM vehicles_master v
        JOIN compatibility_map cm ON v.vehicle_id = cm.vehicle_id
        WHERE cm.part_code = ?
        ORDER BY v.brand, v.segment, v.series, v.model_name
        """,
        (part_code,)
    )
    return [dict(row) for row in cursor.fetchall()]


def get_common_parts(conn: sqlite3.Connection,
                     min_vehicles: int, category_filter: str = None) -> list[dict]:
    """
    Retrieve parts that fit at least `min_vehicles` vehicles.
    Optionally filter by a specific category.
    """
    query = """
        SELECT p.part_code, p.description, p.category, p.mrp, COUNT(DISTINCT cm.vehicle_id) as vehicle_count
        FROM parts_master p
        JOIN compatibility_map cm ON p.part_code = cm.part_code
    """
    params = []

    if category_filter and category_filter != "All Categories":
        query += " WHERE p.category = ?"
        params.append(category_filter)

    query += """
        GROUP BY p.part_code
        HAVING COUNT(DISTINCT cm.vehicle_id) >= ?
        ORDER BY vehicle_count DESC, p.mrp DESC, p.part_code
    """
    params.append(min_vehicles)

    cursor = conn.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def get_all_categories(conn: sqlite3.Connection) -> list[str]:
    """Retrieve all unique part categories from the database."""
    cursor = conn.execute(
        "SELECT DISTINCT category FROM parts_master "
        "WHERE category IS NOT NULL AND category != '' "
        "ORDER BY category"
    )
    return [row["category"] for row in cursor.fetchall()]


def get_vehicle_tree(conn: sqlite3.Connection) -> list[dict]:
    """
    Return all vehicles and their associated assemblies (categories) 
    for building the left-panel filter tree:
        Brand → Segment → Series → Model → Variant → Category (Assembly)
    """
    cursor = conn.execute(
        """
        SELECT DISTINCT 
            v.vehicle_id, v.brand, v.segment, v.series, v.model_name, v.variant, p.category
        FROM vehicles_master v
        JOIN compatibility_map cm ON v.vehicle_id = cm.vehicle_id
        JOIN parts_master p ON cm.part_code = p.part_code
        ORDER BY v.brand, v.segment, v.series, v.model_name, v.variant, p.category
        """
    )
    return [dict(row) for row in cursor.fetchall()]


# ===========================================================================
#  Sync Progress (Checkpoint / Resume)
# ===========================================================================

def is_synced(conn: sqlite3.Connection,
              sync_type: str, key1: str, key2: str = "") -> bool:
    """
    Check whether a specific sync unit has already been completed.

    Args:
        sync_type: 'vehicle' or 'painted'
        key1:      series_id (vehicle) or model_id (painted)
        key2:      '' (vehicle) or color_id (painted)

    Returns:
        True if the checkpoint exists (skip this unit), False if not yet synced.
    """
    row = conn.execute(
        "SELECT 1 FROM sync_progress WHERE sync_type=? AND key1=? AND key2=?",
        (sync_type, key1, key2)
    ).fetchone()
    return row is not None


def mark_synced(conn: sqlite3.Connection,
               sync_type: str, key1: str, key2: str = "") -> None:
    """
    Record that a sync unit has been successfully completed.
    Safe to call multiple times (INSERT OR REPLACE).
    """
    conn.execute(
        """
        INSERT OR REPLACE INTO sync_progress (sync_type, key1, key2, synced_at)
        VALUES (?, ?, ?, ?)
        """,
        (sync_type, key1, key2, datetime.now().isoformat())
    )
    conn.commit()


def reset_sync_progress(conn: sqlite3.Connection,
                        sync_type: str = None) -> int:
    """
    Clear sync checkpoints to force a full re-sync.

    Args:
        sync_type: If provided, only clears that type ('vehicle' or 'painted').
                   If None, clears ALL checkpoints.

    Returns:
        Number of rows deleted.
    """
    if sync_type:
        cur = conn.execute(
            "DELETE FROM sync_progress WHERE sync_type=?", (sync_type,)
        )
    else:
        cur = conn.execute("DELETE FROM sync_progress")
    conn.commit()
    return cur.rowcount


# ===========================================================================
#  Module self-test (run directly: python db_engine.py)
# ===========================================================================

if __name__ == "__main__":
    print("Initializing database...")
    initialize_database()
    print("Done. Database is ready.")
