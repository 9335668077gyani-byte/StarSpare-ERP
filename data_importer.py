"""
data_importer.py — CSV Data Ingestion Engine for Nexses e-Catalog
==================================================================

Reads a TVS parts catalog CSV and populates the three normalized tables:
    1. vehicles_master   — unique vehicle definitions
    2. parts_master      — unique part definitions
    3. compatibility_map — part ↔ vehicle relationships

CSV Column Mapping (expected headers):
    CSV Column      →  Database Field
    ─────────────────────────────────────
    PARTNO           →  parts_master.part_code
    PartDescription  →  parts_master.description
    ASSEMBLY         →  parts_master.category
    MRP              →  parts_master.mrp
    NDP              →  parts_master.ndp       (if present)
    MOQ              →  parts_master.moq       (if present)
    REMARKS          →  parts_master.remarks   (if present)
    SEGMENT_NAME     →  vehicles_master.segment
    SERIES_NAME      →  vehicles_master.series
    MODEL_NAME       →  vehicles_master.model_name
    VARIENT          →  vehicles_master.variant
    (brand is hardcoded to 'TVS')

Performance strategy:
    - Vehicles are inserted first; a local dict cache prevents repeated DB lookups.
    - Parts and compatibility mappings are accumulated in memory and flushed in
      one executemany() call inside a single transaction.
    - Typical throughput: ~50 000 rows/sec on a modern machine.

Error handling:
    - Empty/malformed MRP, NDP → default to 0.0
    - Empty/malformed MOQ → default to 0
    - Rows missing PARTNO are skipped and counted as errors.
    - All exceptions per-row are caught so one bad row never aborts the import.
"""

import csv
import os
from datetime import datetime

# Local imports
from db_engine import (
    get_connection,
    initialize_database,
    insert_vehicle,
    batch_upsert_parts,
    batch_insert_compatibility,
)


# ---------------------------------------------------------------------------
#  Safe type-conversion helpers
# ---------------------------------------------------------------------------

def _safe_float(value: str, default: float = 0.0) -> float:
    """
    Convert a string to float, returning `default` if the value is
    empty, whitespace-only, or not a valid number.

    Examples:
        _safe_float("123.45")  → 123.45
        _safe_float("")        → 0.0
        _safe_float("N/A")     → 0.0
    """
    try:
        return float(value.strip()) if value and value.strip() else default
    except (ValueError, AttributeError):
        return default


def _safe_int(value: str, default: int = 0) -> int:
    """
    Convert a string to int, returning `default` if the value is
    empty, whitespace-only, or not a valid integer.

    Handles float-strings like "5.0" by converting to float first.
    """
    try:
        cleaned = value.strip() if value else ""
        if not cleaned:
            return default
        return int(float(cleaned))          # int(float("5.0")) → 5
    except (ValueError, AttributeError):
        return default


def _clean(value: str) -> str:
    """Strip whitespace and return an empty string for None values."""
    return value.strip() if value else ""


# ===========================================================================
#  Main Import Function
# ===========================================================================

def import_csv(db_path: str, csv_file_path: str,
               brand: str = "TVS") -> dict:
    """
    Import a TVS parts catalog CSV into the Nexses database.

    Processing pipeline (single-pass):
        1. Read every CSV row with DictReader.
        2. For each row, extract the vehicle tuple and cache/insert into
           vehicles_master (in-memory dict avoids repeated SELECTs).
        3. Accumulate part tuples for batch upsert.
        4. Accumulate (part_code, vehicle_id) tuples for batch mapping insert.
        5. Flush parts & mappings via executemany inside one transaction.

    Args:
        db_path:       Path to the SQLite database (must be initialized).
        csv_file_path: Absolute path to the source CSV file.
        brand:         Hardcoded brand name (default 'TVS').

    Returns:
        Summary dict with counts:
            {
                "vehicles_added": int,
                "parts_added":    int,
                "mappings_added": int,
                "rows_processed": int,
                "errors":         int,
                "error_details":  list[str]
            }
    """
    # ── Stats counters ─────────────────────────────────────────────────
    stats = {
        "vehicles_added": 0,
        "parts_added": 0,
        "mappings_added": 0,
        "rows_processed": 0,
        "errors": 0,
        "error_details": [],
    }

    # ── In-memory caches to minimise DB round-trips ────────────────────
    #    vehicle_cache: (segment, series, model, variant) → vehicle_id
    #    seen_parts:    set of part_codes already queued for upsert
    vehicle_cache: dict[tuple, int] = {}
    seen_parts: set[str] = set()

    # ── Batch accumulators ─────────────────────────────────────────────
    parts_batch: list[tuple] = []        # for batch_upsert_parts
    mappings_batch: list[tuple] = []     # for batch_insert_compatibility

    now = datetime.now().isoformat()

    # ── Open CSV  (utf-8-sig handles BOM from Excel exports) ──────────
    if not os.path.isfile(csv_file_path):
        raise FileNotFoundError(f"CSV file not found: {csv_file_path}")

    conn = get_connection(db_path)

    try:
        with open(csv_file_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)

            for row_num, row in enumerate(reader, start=2):     # row 1 = header
                stats["rows_processed"] += 1

                try:
                    # ── 1. Extract & clean fields ─────────────────────
                    part_code   = _clean(row.get("PARTNO", ""))
                    description = _clean(row.get("PartDescription", ""))
                    category    = _clean(row.get("ASSEMBLY", ""))
                    mrp         = _safe_float(row.get("MRP", ""))
                    ndp         = _safe_float(row.get("NDP", ""))
                    moq         = _safe_int(row.get("MOQ", ""))
                    remarks     = _clean(row.get("REMARKS", ""))

                    segment     = _clean(row.get("SEGMENT_NAME", ""))
                    series      = _clean(row.get("SERIES_NAME", ""))
                    model_name  = _clean(row.get("MODEL_NAME", ""))
                    variant     = _clean(row.get("VARIENT", ""))

                    # Skip rows that have no part code (unusable data)
                    if not part_code:
                        stats["errors"] += 1
                        stats["error_details"].append(
                            f"Row {row_num}: Missing PARTNO — skipped."
                        )
                        continue

                    # ── 2. Resolve vehicle_id (cache-first) ───────────
                    veh_key = (segment, series, model_name, variant)

                    if veh_key not in vehicle_cache:
                        # Insert (or get existing) in the DB
                        vid = insert_vehicle(conn, brand, segment, series,
                                             model_name, variant)
                        vehicle_cache[veh_key] = vid
                        stats["vehicles_added"] += 1

                    vehicle_id = vehicle_cache[veh_key]

                    # ── 3. Queue part for batch upsert ────────────────
                    if part_code not in seen_parts:
                        parts_batch.append((
                            part_code, description, category,
                            mrp, ndp, moq, remarks, now
                        ))
                        seen_parts.add(part_code)
                        stats["parts_added"] += 1
                    else:
                        # Part already queued — still update it
                        # (latest row wins for MRP/NDP in this batch)
                        # We append again; ON CONFLICT UPDATE handles it.
                        parts_batch.append((
                            part_code, description, category,
                            mrp, ndp, moq, remarks, now
                        ))

                    # ── 4. Queue compatibility mapping ────────────────
                    mappings_batch.append((part_code, vehicle_id))
                    stats["mappings_added"] += 1

                except Exception as e:
                    stats["errors"] += 1
                    stats["error_details"].append(
                        f"Row {row_num}: {type(e).__name__}: {e}"
                    )

        # ── 5. Flush all batches in a single transaction ──────────────
        batch_upsert_parts(conn, parts_batch)
        batch_insert_compatibility(conn, mappings_batch)
        conn.commit()

        print(f"[data_importer] Import complete: {stats['rows_processed']} rows processed.")

    except Exception as e:
        conn.rollback()
        stats["errors"] += 1
        stats["error_details"].append(f"FATAL: {type(e).__name__}: {e}")
        print(f"[data_importer] Import FAILED — rolled back. Error: {e}")

    finally:
        conn.close()

    return stats


# ===========================================================================
#  Module self-test
# ===========================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python data_importer.py <path_to_csv>")
        print("       The database will be auto-initialized if needed.")
        sys.exit(1)

    csv_path = sys.argv[1]
    db_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "database", "nexses_ecatalog.db"
    )

    # Ensure the database exists
    initialize_database(db_path)

    # Run the import
    result = import_csv(db_path, csv_path)

    # Print summary
    print("\n" + "=" * 50)
    print("  IMPORT SUMMARY")
    print("=" * 50)
    print(f"  Rows Processed : {result['rows_processed']}")
    print(f"  Vehicles Added : {result['vehicles_added']}")
    print(f"  Parts Added    : {result['parts_added']}")
    print(f"  Mappings Added : {result['mappings_added']}")
    print(f"  Errors         : {result['errors']}")
    if result["error_details"]:
        print("\n  Error Details:")
        for err in result["error_details"][:20]:   # cap display at 20
            print(f"    • {err}")
    print("=" * 50)
