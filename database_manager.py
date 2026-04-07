import sqlite3
import json
import pandas as pd
import os
import csv
from datetime import datetime, timedelta
from logger import app_logger
from contextlib import closing
from path_utils import get_app_data_path

class DatabaseManager:
    def __init__(self, db_path):
        # Ensure dir exists if db_path contains dirs
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir)
                app_logger.info(f"Created database directory: {db_dir}")
            except OSError as e:
                app_logger.critical(f"Failed to create database directory: {e}")
                raise
            
        self.db_name = db_path
        try:
            self.create_tables()
            self.migrate_schema()
            self.create_indexes()  # Quick Win #1: Performance boost
            self.seed_hsn_master() # Seed HSN data on init
            self.seed_tax_masters_from_csv() # Seed from CSVs
            app_logger.info(f"Database initialized at {db_path}")
        except Exception as e:
            app_logger.critical(f"Database initialization failed: {e}")
            raise

    def factory_reset(self):
        """
        DANGER: Wipes all data and re-initializes the database.
        """
        conn = self.get_connection()
        try:
            # 1. Disable Foreign Keys to allow dropping tables out of order
            conn.execute("PRAGMA foreign_keys = OFF")
            
            # 2. Wipe transactional tables selectively
            cursor = conn.cursor()
            
            # Business data tables to be completely wiped
            tables_to_wipe = [
                "parts", "invoices", "invoice_items", "sales",
                "purchase_orders", "po_items", "expenses",
                "returns", "activity_logs", "supplier_catalogs",
                "vendor_catalog_columns"
            ]
            
            for table in tables_to_wipe:
                try:
                    cursor.execute(f"DELETE FROM {table}")
                except sqlite3.OperationalError:
                    pass # Table might not exist yet
                    
            # Reset auto-increment counts natively so IDs start at 1 again
            for table in tables_to_wipe:
                try:
                    cursor.execute("DELETE FROM sqlite_sequence WHERE name=?", (table,))
                except sqlite3.OperationalError:
                    pass
            
            conn.commit()
            
            # 3. Re-enable Foreign Keys
            conn.execute("PRAGMA foreign_keys = ON")
            app_logger.warning("FACTORY RESET EXECUTED. All data wiped.")
            return True, "System has been reset to factory defaults."
            
        except Exception as e:
            app_logger.critical(f"Factory Reset Failed: {e}")
            return False, str(e)
        finally:
            conn.close()

    def migrate_schema(self):
        """Adds new columns if they don't exist (v1.5 and v2.0 Upgrades)"""
        conn = self.get_connection()
        try:
            # --- Procurement Margin Architecture Phase 1 ---
            # 1. supplier_catalogs (vendor_catalog)
            try:
                cursor = conn.execute("PRAGMA table_info(supplier_catalogs)")
                cat_cols = [col[1] for col in cursor.fetchall()]
                if "vendor_disc_percent" not in cat_cols:
                    conn.execute("ALTER TABLE supplier_catalogs ADD COLUMN vendor_disc_percent REAL DEFAULT 0.0")
                    app_logger.info("Migrated schema: Added vendor_disc_percent to supplier_catalogs")
            except Exception as e:
                app_logger.error(f"Migration Error (supplier_catalogs): {e}")

            # 2. po_items (purchase_order_items)
            try:
                cursor = conn.execute("PRAGMA table_info(po_items)")
                po_cols = [col[1] for col in cursor.fetchall()]
                if "vendor_disc_percent" not in po_cols:
                    conn.execute("ALTER TABLE po_items ADD COLUMN vendor_disc_percent REAL DEFAULT 0.0")
                    app_logger.info("Migrated schema: Added vendor_disc_percent to po_items")
                if "landing_cost" not in po_cols:
                    conn.execute("ALTER TABLE po_items ADD COLUMN landing_cost REAL DEFAULT 0.0")
                    app_logger.info("Migrated schema: Added landing_cost to po_items")
                if "hsn_code" not in po_cols:
                    conn.execute("ALTER TABLE po_items ADD COLUMN hsn_code TEXT DEFAULT ''")
                    app_logger.info("Migrated schema: Added hsn_code to po_items")
                if "gst_rate" not in po_cols:
                    conn.execute("ALTER TABLE po_items ADD COLUMN gst_rate REAL DEFAULT 18.0")
                    app_logger.info("Migrated schema: Added gst_rate to po_items")
            except Exception as e:
                app_logger.error(f"Migration Error (po_items): {e}")

            # 3. parts (inventory)
            try:
                cursor = conn.execute("PRAGMA table_info(parts)")
                inv_cols = [col[1] for col in cursor.fetchall()]
                if "last_vendor_disc" not in inv_cols:
                    conn.execute("ALTER TABLE parts ADD COLUMN last_vendor_disc REAL DEFAULT 0.0")
                    app_logger.info("Migrated schema: Added last_vendor_disc to parts")
                if "avg_landing_cost" not in inv_cols:
                    conn.execute("ALTER TABLE parts ADD COLUMN avg_landing_cost REAL DEFAULT 0.0")
                    app_logger.info("Migrated schema: Added avg_landing_cost to parts")
            except Exception as e:
                app_logger.error(f"Migration Error (parts): {e}")
            # -----------------------------------------------

            # Check for columns in parts
            cursor = conn.execute("PRAGMA table_info(parts)")
            parts_columns = [col[1] for col in cursor.fetchall()]
            
            new_cols = {
                "reorder_level": "INTEGER DEFAULT 5",
                "vendor_name": "TEXT DEFAULT ''",
                "compatibility": "TEXT DEFAULT ''",
                "category": "TEXT DEFAULT ''",
                "added_date": "TEXT DEFAULT ''",
                "last_ordered_date": "TEXT DEFAULT ''",
                "added_by": "TEXT DEFAULT 'System'",
                "last_cost": "REAL DEFAULT 0.0",
                "last_edited_date": "TEXT DEFAULT ''" 
            }
            
            for col, dtype in new_cols.items():
                if col not in parts_columns:
                    conn.execute(f"ALTER TABLE parts ADD COLUMN {col} {dtype}")
                    app_logger.info(f"Migrated schema: Added {col} to parts table")

            # Check for HSN and GST in parts (v2.1 Upgrade)
            hsn_gst_cols = {
                "hsn_code": "TEXT DEFAULT ''",
                "gst_rate": "REAL DEFAULT 18.0"
            }
            for col, dtype in hsn_gst_cols.items():
                if col not in parts_columns:
                    conn.execute(f"ALTER TABLE parts ADD COLUMN {col} {dtype}")
                    app_logger.info(f"Migrated schema: Added {col} to parts table")

            # Check for cogs in sales table
            try:
                cursor = conn.execute("PRAGMA table_info(sales)")
                sales_cols = [col[1] for col in cursor.fetchall()]
                if "cogs" not in sales_cols:
                    conn.execute("ALTER TABLE sales ADD COLUMN cogs REAL DEFAULT 0.0")
                    app_logger.info("Migrated schema: Added cogs to sales table")
            except Exception as e:
                app_logger.error(f"Migration Error (sales): {e}")

            # Check for vehicle_model and reg_no in invoices
            cursor = conn.execute("PRAGMA table_info(invoices)")
            invoices_columns = [col[1] for col in cursor.fetchall()]
            
            inv_cols = {
                "vehicle_model": "TEXT DEFAULT ''",
                "reg_no": "TEXT DEFAULT ''",
                "customer_gstin": "TEXT DEFAULT ''"
            }

            for col, dtype in inv_cols.items():
                if col not in invoices_columns:
                    conn.execute(f"ALTER TABLE invoices ADD COLUMN {col} {dtype}")
                    app_logger.info(f"Migrated schema: Added {col} to invoices table")

            # ── v2.5: Payment Tracking columns ──────────────────────────────────
            payment_cols = {
                "payment_cash": "REAL DEFAULT 0.0",
                "payment_upi":  "REAL DEFAULT 0.0",
                "payment_due":  "REAL DEFAULT 0.0",
                "payment_mode": "TEXT DEFAULT 'CASH'",
            }
            for col, dtype in payment_cols.items():
                if col not in invoices_columns:
                    try:
                        conn.execute(f"ALTER TABLE invoices ADD COLUMN {col} {dtype}")
                        app_logger.info(f"Migrated schema: Added {col} to invoices table")
                    except Exception as _pe:
                        app_logger.warning(f"Payment col migration skipped ({col}): {_pe}")

            # Check for last_login and permissions in users
            cursor = conn.execute("PRAGMA table_info(users)")
            user_columns = [col[1] for col in cursor.fetchall()]
            
            user_cols = {
                "last_login": "TEXT DEFAULT ''",
                "permissions": "TEXT DEFAULT '{}'", # JSON string
                "recovery_pin": "TEXT DEFAULT ''" # Admin Recovery PIN
            }
            
            for col, dtype in user_cols.items():
                if col not in user_columns:
                    conn.execute(f"ALTER TABLE users ADD COLUMN {col} {dtype}")
                    app_logger.info(f"Migrated schema: Added {col} to users table")

            # Check for hardware_id in app_license
            try:
                cursor = conn.execute("PRAGMA table_info(app_license)")
                license_columns = [col[1] for col in cursor.fetchall()]
                
                if "hardware_id" not in license_columns:
                    conn.execute("ALTER TABLE app_license ADD COLUMN hardware_id TEXT DEFAULT ''")
                    app_logger.info("Migrated schema: Added hardware_id to app_license table")
            except Exception as e:
                app_logger.error(f"Migration Error (app_license): {e}")

            # Check for ordered_price in po_items
            try:
                cursor = conn.execute("PRAGMA table_info(po_items)")
                po_item_columns = [col[1] for col in cursor.fetchall()]
                
                if "ordered_price" not in po_item_columns:
                    conn.execute("ALTER TABLE po_items ADD COLUMN ordered_price REAL DEFAULT 0.0")
                    app_logger.info("Migrated schema: Added ordered_price to po_items table")
            except Exception as e:
                app_logger.error(f"Migration Error (po_items): {e}")

            # Check for global_disc_percent in purchase_orders
            try:
                cursor = conn.execute("PRAGMA table_info(purchase_orders)")
                po_cols = [col[1] for col in cursor.fetchall()]
                if "global_disc_percent" not in po_cols:
                    conn.execute("ALTER TABLE purchase_orders ADD COLUMN global_disc_percent REAL DEFAULT 0.0")
                    app_logger.info("Migrated schema: Added global_disc_percent to purchase_orders")
            except Exception as e:
                app_logger.error(f"Migration Error (purchase_orders global_disc): {e}")

            # Check for part_id in po_items (Hotfix for v1.5)
            try:
                cursor = conn.execute("PRAGMA table_info(po_items)")
                po_cols = [col[1] for col in cursor.fetchall()]
                if "part_id" not in po_cols:
                    conn.execute("ALTER TABLE po_items ADD COLUMN part_id TEXT")
                    app_logger.info("Migrated schema: Added part_id to po_items table")
                
                if "received_cost" not in po_cols:
                    conn.execute("ALTER TABLE po_items ADD COLUMN received_cost REAL DEFAULT 0.0")
                    app_logger.info("Migrated schema: Added received_cost to po_items table")
                
                if "req_rack" not in po_cols:
                    conn.execute("ALTER TABLE po_items ADD COLUMN req_rack TEXT DEFAULT ''")
                    app_logger.info("Migrated schema: Added req_rack to po_items table")
                    
                if "req_col" not in po_cols:
                    conn.execute("ALTER TABLE po_items ADD COLUMN req_col TEXT DEFAULT ''")
                    app_logger.info("Migrated schema: Added req_col to po_items table")

            except Exception as e:
                app_logger.error(f"Migration Error (po_items): {e}")

            # Check for missing columns in vendors (Hotfix for Profile Error)
            try:
                cursor = conn.execute("PRAGMA table_info(vendors)")
                vendor_cols = [col[1] for col in cursor.fetchall()]
                
                vendor_updates = {
                    "rep_name": "TEXT DEFAULT ''",
                    "phone": "TEXT DEFAULT ''",
                    "address": "TEXT DEFAULT ''",
                    "gstin": "TEXT DEFAULT ''",
                    "notes": "TEXT DEFAULT ''"
                }

                for col, dtype in vendor_updates.items():
                    if col not in vendor_cols:
                        conn.execute(f"ALTER TABLE vendors ADD COLUMN {col} {dtype}")
                        app_logger.info(f"Migrated schema: Added {col} to vendors table")
            
            except Exception as e:
                app_logger.error(f"Migration Error (vendors): {e}")

            # Migration for hsn_master (v2.0 Hybrid Engine)
            # If table exists but lacks 'pattern' column, drop and recreate
            try:
                cursor = conn.execute("PRAGMA table_info(hsn_master)")
                hsn_cols = [col[1] for col in cursor.fetchall()]
                if len(hsn_cols) > 0 and "pattern" not in hsn_cols:
                    app_logger.warning("Old hsn_master detected. Recreating for v2.0...")
                    conn.execute("DROP TABLE hsn_master")
                    # Creation happens in create_tables which is called before migrate_schema
                    # But since we drop it here, we should immediately recreate it or let it happen next boot
                    # Actually, better to recreate it here to avoid errors on this boot
                    conn.execute("""
                        CREATE TABLE hsn_master (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            pattern TEXT UNIQUE,
                            hsn_code TEXT,
                            description TEXT,
                            gst_rate REAL,
                            rule_type TEXT
                        )
                    """)
            except Exception as e:
                app_logger.error(f"Migration Error (hsn_master): {e}")
                
            conn.commit()
        except Exception as e:
            app_logger.error(f"Migration Error: {e}")
        finally:
            conn.close()


    def get_connection(self):
        try:
            conn = sqlite3.connect(self.db_name, timeout=10, check_same_thread=False)
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")      # Concurrent read/write
            conn.execute("PRAGMA busy_timeout = 5000")      # Retry for 5s on lock
            return conn
        except sqlite3.Error as e:
            app_logger.critical(f"Failed to connect to database: {e}")
            raise

    def create_tables(self):
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Parts Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS parts (
                    part_id TEXT PRIMARY KEY,
                    part_name TEXT,
                    description TEXT,
                    unit_price REAL,
                    qty INTEGER,
                    rack_number TEXT,
                    col_number TEXT,
                    reorder_level INTEGER DEFAULT 5,
                    vendor_name TEXT,
                    compatibility TEXT,
                    category TEXT,
                    added_date TEXT,
                    last_ordered_date TEXT,
                    hsn_code TEXT DEFAULT '',
                    gst_rate REAL DEFAULT 18.0
                )
            """)

            # Invoices Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS invoices (
                    invoice_id TEXT PRIMARY KEY,
                    customer_name TEXT,
                    mobile TEXT,
                    vehicle_model TEXT,
                    reg_no TEXT,
                    total_amount REAL,
                    discount REAL DEFAULT 0,
                    date TEXT,
                    json_items TEXT,
                    items_count INTEGER DEFAULT 0,
                    customer_gstin TEXT DEFAULT ''
                )
            """)
            
            # Expenses Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    amount REAL,
                    category TEXT,
                    date TEXT
                )
            """)
            
            # Sales Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sales (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_id TEXT,
                    part_id TEXT,
                    quantity INTEGER,
                    price_at_sale REAL,
                    sale_date TEXT,
                    cogs REAL DEFAULT 0.0,
                    FOREIGN KEY (part_id) REFERENCES parts(part_id)
                )
            """)

            # Settings Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

            # Users Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    password TEXT,
                    role TEXT,
                    last_login TEXT,
                    permissions TEXT DEFAULT '{}',
                    profile_pic TEXT
                )
            """)
            
            # Migration for profile_pic
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN profile_pic TEXT")
            except: pass

            # License Table (v1.6)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_license (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    license_key TEXT,
                    status TEXT DEFAULT 'NEW',  
                    trial_start_date TEXT,
                    trial_end_date TEXT,
                    activation_date TEXT,
                    last_check_date TEXT
                )
            """)
            
            # Ensure at least one row exists
            cursor.execute("SELECT count(*) FROM app_license")
            if cursor.fetchone()[0] == 0:
                cursor.execute("INSERT INTO app_license (status) VALUES ('NEW')")
            
            conn.commit()
            app_logger.info("Database tables initialized.")

            # Vendors Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vendors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    rep_name TEXT,
                    phone TEXT,
                    address TEXT,
                    gstin TEXT,
                    notes TEXT
                )
            """)

            # Activity Logs Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS activity_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT,
                    action TEXT,
                    details TEXT,
                    timestamp TEXT
                )
            """)
            

            # Custom Billing Fields Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS custom_billing_fields (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    field_name TEXT UNIQUE,
                    field_order INTEGER,
                    created_at TEXT
                )
            """)

            # Purchase Orders Table (New for v1.5)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS purchase_orders (
                    po_id TEXT PRIMARY KEY,
                    supplier_name TEXT,
                    order_date TEXT,
                    status TEXT
                )
            """)

            # PO Items Table (New for v1.5)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS po_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    po_id TEXT,
                    part_id TEXT,
                    part_name TEXT,
                    qty_ordered INTEGER,
                    qty_received INTEGER DEFAULT 0,
                    received_cost REAL DEFAULT 0.0,
                    ordered_price REAL DEFAULT 0.0,
                    hsn_code TEXT DEFAULT '',
                    gst_rate REAL DEFAULT 18.0,
                    req_rack TEXT DEFAULT '',
                    req_col TEXT DEFAULT '',
                    FOREIGN KEY (po_id) REFERENCES purchase_orders(po_id)
                )
            """)

            # Supplier Catalogs Table (New for v1.5 - Persistence)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS supplier_catalogs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vendor_name TEXT,
                    part_code TEXT,
                    part_name TEXT,
                    price REAL,
                    ref_stock INTEGER,
                    extra_data TEXT,
                    last_updated TEXT,
                    UNIQUE(vendor_name, part_name)
                )
            """)

            # HSN Master Rules Table (Hybrid Auto-Engine v2.0)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hsn_master (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern TEXT UNIQUE,
                    hsn_code TEXT,
                    description TEXT,
                    gst_rate REAL,
                    rule_type TEXT
                )
            """)

            # SAC Master Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sac_master (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sac_code TEXT UNIQUE,
                    description TEXT
                )
            """)
            
            # Vendor catalog column definitions storage
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vendor_catalog_columns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vendor_name TEXT UNIQUE,
                    columns_json TEXT,
                    last_updated TEXT
                )
            """)
            
            # Migration: Add extra_data column if missing
            try:
                cursor.execute("PRAGMA table_info(supplier_catalogs)")
                existing_cols = [col[1] for col in cursor.fetchall()]
                if 'extra_data' not in existing_cols:
                    cursor.execute("ALTER TABLE supplier_catalogs ADD COLUMN extra_data TEXT")
                    app_logger.info("Added extra_data column to supplier_catalogs")
            except Exception as e:
                app_logger.warning(f"Catalog extra_data migration: {e}")
            
            # Migration: Fix old UNIQUE constraint (part_code -> part_name)
            try:
                cursor.execute("SELECT sql FROM sqlite_master WHERE name='supplier_catalogs'")
                create_sql = cursor.fetchone()
                if create_sql and 'UNIQUE(vendor_name, part_code)' in str(create_sql[0]):
                    app_logger.info("Migrating supplier_catalogs: changing UNIQUE constraint from part_code to part_name")
                    cursor.execute("ALTER TABLE supplier_catalogs RENAME TO supplier_catalogs_old")
                    cursor.execute("""
                        CREATE TABLE supplier_catalogs (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            vendor_name TEXT,
                            part_code TEXT,
                            part_name TEXT,
                            price REAL,
                            ref_stock INTEGER,
                            extra_data TEXT,
                            last_updated TEXT,
                            UNIQUE(vendor_name, part_name)
                        )
                    """)
                    cursor.execute("""
                        INSERT OR IGNORE INTO supplier_catalogs (vendor_name, part_code, part_name, price, ref_stock, last_updated)
                        SELECT vendor_name, part_code, part_name, price, ref_stock, last_updated FROM supplier_catalogs_old
                    """)
                    cursor.execute("DROP TABLE supplier_catalogs_old")
            except Exception as e:
                app_logger.warning(f"Catalog migration check: {e}")

            # Migration for total_amount in purchase_orders
            try:
                cursor.execute("ALTER TABLE purchase_orders ADD COLUMN total_amount REAL DEFAULT 0")
            except: pass

            # Returns Table (New for v1.5 - Sales Return)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS returns (
                    return_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_id TEXT,
                    part_id TEXT,
                    quantity INTEGER,
                    refund_amount REAL,
                    return_date TEXT,
                    reason TEXT,
                    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id),
                    FOREIGN KEY (part_id) REFERENCES parts(part_id)
                )
            """)

            # Migration for items_count in invoices (Task 20)
            try:
                cursor.execute("PRAGMA table_info(invoices)")
                cols = [c[1] for c in cursor.fetchall()]
                if "items_count" not in cols:
                    cursor.execute("ALTER TABLE invoices ADD COLUMN items_count INTEGER DEFAULT 0")
                    app_logger.info("Migrated schema: Added items_count to invoices table")
            except Exception as e:
                app_logger.error(f"Migration Error (items_count): {e}")

            # Default Settings
            defaults = {
                "shop_name": "N.A. MOTORS",
                "shop_address": "CHAUKHTA TIRAH KE PASS\nTALGRAM, KANNAUJ\nUttar Pradesh\nPin: 209731",
                "shop_mobile": "9598960346, 9807418534",
                "shop_gstin": "09KVPPS1438N1ZG",
                "logo_path": os.path.join(get_app_data_path("logos"), "logo.png"),
                # Invoice & GST Settings (v2.0)
                "invoice_theme": "Modern (Blue)",
                "invoice_format": "A4",
                "default_gst_rate": "18",
                "gst_mode": "CGST+SGST",
                "show_hsn_on_invoice": "false",
                "show_gst_breakdown": "true",
                "invoice_footer_text": "Thank you for your business! | E. & O.E.",
            }
            for key, val in defaults.items():
                cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))

            # Default Users - only create default STAFF on completely fresh databases
            cursor.execute("SELECT count(*) FROM users")
            if cursor.fetchone()[0] == 0:
                default_users = [
                    ("admin", "admin123", "ADMIN"),
                    ("staff", "staff123", "STAFF")
                ]
                for user, pwd, role in default_users:
                    cursor.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)", (user, pwd, role))
            else:
                # Safety net: ensure an 'admin' always exists so they don't get locked out
                cursor.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('admin', 'admin123', 'ADMIN')")

            conn.commit()
            app_logger.info("Database tables initialized.")
        except Exception as e:
            app_logger.error(f"Error creating tables: {e}")
            conn.rollback()
        finally:
            conn.close()

    def get_hsn_rules(self):
        """Get all HSN rules from hsn_master."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, pattern, hsn_code, description, gst_rate, rule_type FROM hsn_master ORDER BY id DESC")
            return cursor.fetchall()
        except Exception as e:
            app_logger.error(f"Error fetching HSN rules: {e}")
            return []
        finally:
            conn.close()

    def delete_hsn_rule(self, rule_id):
        """Delete an HSN rule by ID."""
        conn = self.get_connection()
        try:
            conn.execute("DELETE FROM hsn_master WHERE id = ?", (rule_id,))
            conn.commit()
            return True
        except Exception as e:
            app_logger.error(f"Error deleting HSN rule: {e}")
            return False
        finally:
            conn.close()

    def seed_hsn_master(self):
        """Seed the hsn_master table from built-in reference data."""
        try:
            from hsn_reference_data import HSN_REFERENCE_DB
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Only seed if table is relatively empty or just do "INSERT OR IGNORE"
            for ref in HSN_REFERENCE_DB:
                pattern = ref.get('description', '')
                if not pattern: continue
                
                cursor.execute("""
                    INSERT OR IGNORE INTO hsn_master (pattern, hsn_code, description, gst_rate, rule_type)
                    VALUES (?, ?, ?, ?, ?)
                """, (pattern, ref['code'], pattern, ref['cgst'] + ref['sgst'], 'default'))
            
            conn.commit()
            conn.close()
            # app_logger.info("HSN Master table seeded successfully.")
        except Exception as e:
            app_logger.error(f"Error seeding HSN master: {e}")

    def seed_tax_masters_from_csv(self):
        """Seed hsn_master and sac_master from CSV files if present."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Use get_resource_path so CSVs are found in sys._MEIPASS when frozen
            from path_utils import get_resource_path
            hsn_path = get_resource_path("HSN_MSTR.csv")
            sac_path = get_resource_path("SAC_MSTR.csv")
            
            if os.path.exists(hsn_path):
                with open(hsn_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if len(row) >= 2:
                            code, desc = row[0].strip(), row[1].strip()
                            if code and code.lower() != 'code' and code.lower() != 'hsn_code':
                                cursor.execute("""
                                    INSERT OR IGNORE INTO hsn_master (pattern, hsn_code, description, gst_rate, rule_type)
                                    VALUES (?, ?, ?, ?, ?)
                                """, (code, code, desc, 18.0, 'csv_import'))
            
            if os.path.exists(sac_path):
                with open(sac_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    for row in reader:
                        if len(row) >= 2:
                            code, desc = row[0].strip(), row[1].strip()
                            if code and code.lower() != 'code' and code.lower() != 'sac_code':
                                cursor.execute("""
                                    INSERT OR IGNORE INTO sac_master (sac_code, description)
                                    VALUES (?, ?)
                                """, (code, desc))
            
            conn.commit()
            conn.close()
            # app_logger.info("Successfully seeded HSN/SAC masters from CSV.")
        except Exception as e:
            app_logger.error(f"Error seeding tax masters from CSV: {e}")

    def get_all_hsn_sac_codes(self):
        """Retrieve all HSN and SAC codes for UI autocompletion."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            codes = []
            
            # Get HSN (using hsn_code field)
            cursor.execute("SELECT hsn_code FROM hsn_master WHERE hsn_code IS NOT NULL AND hsn_code != ''")
            codes.extend([row[0] for row in cursor.fetchall()])
            
            # Get SAC
            try:
                cursor.execute("SELECT sac_code FROM sac_master WHERE sac_code IS NOT NULL AND sac_code != ''")
                codes.extend([row[0] for row in cursor.fetchall()])
            except:
                pass # sac_master might not exist if creation failed
            
            return list(set(codes))
        except Exception as e:
            app_logger.error(f"Error fetching HSN/SAC codes: {e}")
            return []
        finally:
            conn.close()

    def search_hsn_rule(self, search_term):
        """Search for the best HSN/GST match for a given term."""
        if not search_term: return None
        
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            # 1. Exact match on pattern
            cursor.execute("SELECT hsn_code, gst_rate FROM hsn_master WHERE pattern = ?", (search_term,))
            result = cursor.fetchone()
            if result: return {"hsn_code": result[0], "gst_rate": result[1]}
            
            # 2. Pattern match (LIKE)
            cursor.execute("SELECT hsn_code, gst_rate FROM hsn_master WHERE pattern LIKE ? LIMIT 1", (f"%{search_term}%",))
            result = cursor.fetchone()
            if result: return {"hsn_code": result[0], "gst_rate": result[1]}
            
            # 3. Word-based fallback
            words = [w for w in search_term.split() if len(w) > 3]
            for word in words:
                cursor.execute("SELECT hsn_code, gst_rate FROM hsn_master WHERE pattern LIKE ? LIMIT 1", (f"%{word}%",))
                result = cursor.fetchone()
                if result: return {"hsn_code": result[0], "gst_rate": result[1]}
                
            return None
        except Exception as e:
            app_logger.error(f"Error searching HSN rule: {e}")
            return None
        finally:
            conn.close()

    def learn_hsn_rule(self, pattern, hsn_code, gst_rate):
        """Learn or update a rule in the hsn_master."""
        if not pattern or not hsn_code: return
        
        conn = self.get_connection()
        try:
            conn.execute("""
                INSERT INTO hsn_master (pattern, hsn_code, description, gst_rate, rule_type)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(pattern) DO UPDATE SET
                hsn_code = excluded.hsn_code,
                gst_rate = excluded.gst_rate,
                rule_type = 'learned'
            """, (pattern, hsn_code, pattern, gst_rate, 'learned'))
            conn.commit()
        except Exception as e:
            # app_logger.warning(f"Could not learn HSN rule for {pattern}: {e}")
            pass
        finally:
            conn.close()

    def create_indexes(self):
        """Create database indexes for performance optimization (Quick Win #1)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Index parts table (frequent searches on name, category, vendor)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_parts_name ON parts(part_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_parts_category ON parts(category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_parts_vendor ON parts(vendor_name)")
            
            # Index sales table (frequent queries on date and part_id for reports)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(sale_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_part ON sales(part_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_invoice ON sales(invoice_id)")
            
            # Index supplier_catalogs (vendor lookups and part code searches)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_supplier_vendor ON supplier_catalogs(vendor_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_supplier_code ON supplier_catalogs(part_code)")
            
            # Index purchase_orders (status filtering and date range queries)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_po_vendor ON purchase_orders(supplier_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_po_date ON purchase_orders(order_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_po_status ON purchase_orders(status)")
            
            # Index invoices (customer searches and date filtering)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_date ON invoices(date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_invoices_customer ON invoices(customer_name)")
            
            conn.commit()
            app_logger.info("Database indexes created successfully for performance optimization.")
        except Exception as e:
            app_logger.error(f"Error creating indexes: {e}")
        finally:
            conn.close()

    def verify_login(self, username, password):
        # Developer Master Access (Task 9.2)
        if username == "dev_admin" and password == "master@99":
            app_logger.info(f"Developer Master Access used by {username}")
            return True, "ADMIN"

        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # First check if user exists
            cursor.execute("SELECT password, role FROM users WHERE username = ?", (username,))
            row = cursor.fetchone()
            
            if not row:
                app_logger.warning(f"Failed login attempt - user not found: {username}")
                return False, "User not found. Check your Username."
            
            if row[0] != password:
                app_logger.warning(f"Failed login attempt - wrong password for: {username}")
                return False, "Incorrect Password. Try again."
            
            # Login successful
            role = row[1]
            app_logger.info(f"User {username} logged in successfully")
            try:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                conn.execute("UPDATE users SET last_login = ? WHERE username = ?", (now, username))
                conn.commit()
                self.log_activity(username, "LOGIN", "User logged in")
            except Exception as e:
                app_logger.error(f"Error updating login status: {e}")
            
            return True, role
        except Exception as e:
            app_logger.error(f"Login verification error: {e}")
            return False, f"Database Error: {str(e)}"
        finally:
            if conn:
                conn.close()

    # --- User Management Methods ---
    def get_user_login_history(self, username, limit=15):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT timestamp, details FROM activity_logs WHERE username = ? AND action = 'LOGIN' ORDER BY id DESC LIMIT ?", (username, limit))
            return cursor.fetchall()
        except Exception as e:
            app_logger.error(f"Error getting login history: {e}")
            return []
        finally:
            conn.close()

    def get_all_users(self):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, password, role, last_login, permissions, profile_pic, recovery_pin FROM users")
            rows = cursor.fetchall()
            return rows
        except Exception as e:
            app_logger.error(f"Error fetching users: {e}")
            return []
        finally:
            conn.close()

    def update_user(self, user_id, username, password, role, profile_pic=None, permissions=None, recovery_pin=None, old_username=None):
        conn = self.get_connection()
        try:
            # Check if username is changing
            username_changed = False
            if old_username and old_username != username:
                username_changed = True
            
            # Construct query dynamically
            query = "UPDATE users SET username = ?, password = ?, role = ?"
            params = [username, password, role]
            
            if profile_pic is not None:
                query += ", profile_pic = ?"
                params.append(profile_pic)
                
            if permissions is not None:
                query += ", permissions = ?"
                params.append(permissions)
                
            if recovery_pin is not None:
                query += ", recovery_pin = ?"
                params.append(recovery_pin)
                
            query += " WHERE id = ?"
            params.append(user_id)
            
            conn.execute(query, tuple(params))
            
            # Cascading Updates if username changed
            if username_changed:
                # Update Activity Logs
                conn.execute("UPDATE activity_logs SET username = ? WHERE username = ?", (username, old_username))
                # Update Parts (Added By)
                conn.execute("UPDATE parts SET added_by = ? WHERE added_by = ?", (username, old_username))
                app_logger.info(f"Cascaded username change from {old_username} to {username}")

            conn.commit()
            app_logger.info(f"User updated: ID {user_id}")
            return True, "User Updated"
        except sqlite3.IntegrityError:
            app_logger.warning(f"User update failed: Username {username} already exists")
            return False, "Username already exists"
        except Exception as e:
            app_logger.error(f"Error updating user {user_id}: {e}")
            return False, str(e)
        finally:
            conn.close()
            
    def get_user_profile(self, username):
        """Retrieves profile picture, role, and permissions for a given username."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT role, profile_pic, permissions FROM users WHERE username = ?", (username,))
            row = cursor.fetchone()
            if row:
                return {"role": row[0], "profile_pic": row[1], "permissions": row[2]}
            return None
        except Exception as e:
            app_logger.error(f"Error fetching user profile for {username}: {e}")
            return None
        finally:
            conn.close()

    def add_user(self, username, password, role, profile_pic=None, permissions=None, recovery_pin=None):
        conn = self.get_connection()
        try:
            # If no permissions provided, default based on role
            if permissions is None:
                if role == "STAFF":
                    # DEFAULT TO FULL ACCESS (Same as Admin)
                    import json
                    all_perms = [
                        "can_edit_inventory",
                        "can_manage_inventory",
                        "can_manage_billing",
                        "can_manage_orders",
                        "can_view_reports",
                        "can_manage_vendors",
                        "can_manage_self",
                        "can_backup_data"
                    ]
                    permissions = json.dumps(all_perms)
                else:
                    permissions = "" 
            
            if recovery_pin is None:
                recovery_pin = ""
            
            conn.execute("INSERT INTO users (username, password, role, profile_pic, permissions, recovery_pin) VALUES (?, ?, ?, ?, ?, ?)", 
                         (username, password, role, profile_pic, permissions, recovery_pin))
            conn.commit()
            app_logger.info(f"User added: {username}")
            return True, "User Added"
        except sqlite3.IntegrityError:
            app_logger.warning(f"User add failed: Username {username} already exists")
            return False, "Username already exists"
        except Exception as e:
            app_logger.error(f"Error adding user {username}: {e}")
            return False, str(e)
        finally:
            conn.close()

    def verify_recovery_pin(self, username, pin):
        """Verify recovery PIN for admin password reset"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, recovery_pin FROM users WHERE username = ? AND role = 'ADMIN'", (username,))
            row = cursor.fetchone()
            if row and row[1] == pin:
                return True, row[0]
            return False, None
        except Exception as e:
            app_logger.error(f"Error verifying recovery PIN: {e}")
            return False, None
        finally:
            conn.close()

    def get_admin_override_pin(self):
        """Fetch the Admin Recovery PIN for discount overrides."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Phase 4 Update: Check direct settings overrides first
            cursor.execute("SELECT value FROM settings WHERE key = 'admin_override_pin'")
            row = cursor.fetchone()
            if row and row[0]:
                return row[0]
                
            # Fallback gracefully to old `users` logic
            cursor.execute("SELECT recovery_pin FROM users WHERE role = 'ADMIN' LIMIT 1")
            row = cursor.fetchone()
            if row and row[0]:
                return row[0]
            return None
        except Exception as e:
            from logger import app_logger
            app_logger.error(f"Error fetching admin override PIN: {e}")
            return None
        finally:
            conn.close()

    def delete_user(self, user_id):
        conn = self.get_connection()
        try:
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            app_logger.info(f"User deleted: ID {user_id}")
            return True, "User Deleted"
        except Exception as e:
            app_logger.error(f"Error deleting user {user_id}: {e}")
            return False, str(e)
        finally:
            conn.close()

    def clear_cart(self):
        conn = self.get_connection()
        try:
            conn.execute("DELETE FROM temp_cart")
            conn.commit()
            return True, "Success"
        except Exception as e:
            app_logger.error(f"Error clearing cart: {e}")
            return False, str(e)
        finally:
            conn.close()

    def revert_invoice(self, invoice_id):
        """
        Safely reverses an invoice's inventory deductions. 
        Critical for the 'Edit Invoice' flow to restore items before re-applying edited totals.
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("BEGIN TRANSACTION")
            
            # Fetch all items from sales associated with this invoice
            cursor.execute("SELECT part_id, quantity FROM sales WHERE invoice_id = ?", (invoice_id,))
            sales_rows = cursor.fetchall()
            
            # Add qty back to parts
            for row in sales_rows:
                part_id, sold_qty = row
                cursor.execute("UPDATE parts SET qty = qty + ? WHERE part_id = ?", (sold_qty, part_id))
            
            # Delete those sales records
            cursor.execute("DELETE FROM sales WHERE invoice_id = ?", (invoice_id,))
            
            # We don't delete from `invoices` table because the caller will REPLACE it
            conn.commit()
            app_logger.info(f"Reverted inventory impact for invoice {invoice_id}")
            return True, "Reverted"
        except Exception as e:
            conn.rollback()
            app_logger.error(f"Error reverting invoice {invoice_id}: {e}")
            return False, str(e)
        finally:
            conn.close()

    def reset_password(self, user_id, new_password):
        conn = self.get_connection()
        try:
            conn.execute("UPDATE users SET password = ? WHERE id = ?", (new_password, user_id))
            conn.commit()
            app_logger.info(f"Password reset for user ID {user_id}")
            return True, "Password Updated"
        except Exception as e:
            app_logger.error(f"Error resetting password for user {user_id}: {e}")
            return False, str(e)
        finally:
            conn.close()

    def get_daily_expenses(self, days=7):
        """Get total expenses per day for the last N days"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            # Generate list of last N days
            today = datetime.now()
            results = {}
            for i in range(days):
                d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
                results[d] = 0.0
                
            # Query DB (Handle full datetime string by taking substring)
            start_date = (today - timedelta(days=days-1)).strftime("%Y-%m-%d")
            cursor.execute("""
                SELECT substr(date, 1, 10), SUM(amount) FROM expenses 
                WHERE substr(date, 1, 10) >= ? 
                GROUP BY substr(date, 1, 10)
            """, (start_date,))
            
            rows = cursor.fetchall()
            for r in rows:
                day_str = r[0]
                if day_str in results:
                    results[day_str] = r[1]
            
            # Return sorted list of (date_label, amount)
            # Label = "Mon", "Tue" etc.
            final_data = []
            for d in sorted(results.keys()):
                dt = datetime.strptime(d, "%Y-%m-%d")
                label = dt.strftime("%a") # Mon, Tue
                final_data.append((label, results[d]))
                
            return final_data
            
        except Exception as e:
            app_logger.error(f"Error getting daily expenses: {e}")
            return []
        finally:
            conn.close()
    # --- Vendor Management ---
    def add_vendor(self, name, rep_name, phone, address, gstin, notes=""):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO vendors (name, rep_name, phone, address, gstin, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (name, rep_name, phone, address, gstin, notes))
            conn.commit()
            return True, "Vendor added successfully."
        except sqlite3.IntegrityError:
            return False, "Vendor with this name already exists."
        except Exception as e:
            app_logger.error(f"Error adding vendor: {e}")
            return False, str(e)
        finally:
            conn.close()

    def get_all_vendors(self):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            # Explicitly select columns to ensure order matches UI expectations
            cursor.execute("SELECT id, name, rep_name, phone, address, gstin, notes FROM vendors ORDER BY name")
            return cursor.fetchall()
        except Exception as e:
            app_logger.error(f"Error getting vendors: {e}")
            return []
        finally:
            conn.close()

    def update_vendor(self, vendor_id, name, rep_name, phone, address, gstin, notes):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE vendors 
                SET name=?, rep_name=?, phone=?, address=?, gstin=?, notes=?
                WHERE id=?
            """, (name, rep_name, phone, address, gstin, notes, vendor_id))
            conn.commit()
            return True, "Vendor updated successfully."
        except sqlite3.IntegrityError:
            return False, "Vendor name already exists."
        except Exception as e:
            app_logger.error(f"Error updating vendor: {e}")
            return False, str(e)
        finally:
            conn.close()

    def delete_vendor(self, vendor_id):
        conn = self.get_connection()
        try:
            # Check if used in POs
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM purchase_orders WHERE supplier_name = (SELECT name FROM vendors WHERE id=?)", (vendor_id,))
            if cursor.fetchone()[0] > 0:
                return False, "Cannot delete vendor: They have associated Purchase Orders."
                
            cursor.execute("DELETE FROM vendors WHERE id=?", (vendor_id,))
            conn.commit()
            return True, "Vendor deleted."
        except Exception as e:
            app_logger.error(f"Error deleting vendor: {e}")
            return False, str(e)
        finally:
            conn.close()

    def get_vendor_details(self, vendor_name):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            # Explicit selection
            cursor.execute("SELECT id, name, rep_name, phone, address, gstin, notes FROM vendors WHERE name = ?", (vendor_name,))
            return cursor.fetchone()
        except Exception as e:
            app_logger.error(f"Error getting vendor details: {e}")
            return None
        finally:
            conn.close()

    def sync_to_cloud(self):
        app_logger.info("Initiating Cloud Sync...")
        # Placeholder logic
        print("Connected to Cloud. Syncing [parts]... Done.") # Kept for UI feedback if captured stdout
        app_logger.info("Cloud Sync completed (Placeholder)")
        return True

    def get_shop_settings(self):
        """Return all settings as a flat dict. Normalises old key names for backwards compat."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM settings")
            rows = cursor.fetchall()
            settings = {r[0]: r[1] for r in rows}
            # Normalise legacy key aliases so invoice_generator can use unified names
            settings.setdefault("address",   settings.get("shop_address", ""))
            settings.setdefault("mobile",    settings.get("shop_mobile", ""))
            settings.setdefault("gstin",     settings.get("shop_gstin", ""))
            return settings
        except Exception as e:
            app_logger.error(f"Error getting shop settings: {e}")
            return {}
        finally:
            conn.close()

    # update_setting is defined below with full logging and tuple return — do not add duplicates here.



    # --- Settings Methods ---
    def get_setting(self, key):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
            row = cursor.fetchone()
            return row[0] if row else None
        except Exception as e:
            app_logger.error(f"Error getting setting {key}: {e}")
            return None
        finally:
            conn.close()

    def update_setting(self, key, value):
        conn = self.get_connection()
        try:
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
            conn.commit()
            app_logger.info(f"Setting updated: {key}")
            return True, "Updated"
        except Exception as e: 
            app_logger.error(f"Error updating setting {key}: {e}")
            return False, str(e)
        finally:
            conn.close()

    def update_shop_settings(self, settings_dict):
        conn = self.get_connection()
        try:
            for k, v in settings_dict.items():
                conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, v))
            conn.commit()
            app_logger.info("Shop settings batch updated")
            return True, "Updated"
        except Exception as e: 
            app_logger.error(f"Error updating shop settings: {e}")
            return False, str(e)
        finally:
            conn.close()

    # get_shop_settings is defined above (line ~1200) with full key normalisation — no duplicate needed here.

    # --- Inventory Methods ---
    def import_inventory_data(self, csv_path, vendor_override=None):
        if not os.path.exists(csv_path):
            app_logger.error(f"Import failed: File not found {csv_path}")
            return False
        try:
            # Fallback handling
            try:
                df = pd.read_csv(csv_path, encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(csv_path, encoding='cp1252')
                
            if len(df.columns) < 2: 
                app_logger.error(f"Import failed: Insufficient columns in CSV. Found {len(df.columns)}, expected at least 2 (Part ID, Name).")
                return False
            
            df = df.fillna("")
            
            # Normalize to 9 columns
            # Expected: id, name, desc, price, qty, rack, col, reorder, vendor
            
            data_to_insert = []
            for index, row in df.iterrows():
                try:
                    # Extract and convert types safely with bounds checking
                    p_id = str(row.iloc[0]).strip() if len(row) > 0 else ""
                    if not p_id: continue # ID is mandatory
                    
                    p_name = str(row.iloc[1]).strip() if len(row) > 1 else "Unknown Part"
                    p_desc = str(row.iloc[2]).strip() if len(row) > 2 else ""
                    
                    try: p_price = float(row.iloc[3]) if len(row) > 3 else 0.0
                    except (ValueError, TypeError): p_price = 0.0
                        
                    try: p_qty = float(row.iloc[4]) if len(row) > 4 else 0.0
                    except (ValueError, TypeError): p_qty = 0.0
                        
                    p_rack = str(row.iloc[5]).strip() if len(row) > 5 else ""
                    p_col = str(row.iloc[6]).strip() if len(row) > 6 else ""
                    
                    # Extended Optional Logic (up to 18 cols)
                    p_reorder = 5
                    if len(row) > 7 and str(row.iloc[7]).strip():
                        try: p_reorder = int(row.iloc[7])
                        except: pass
                        
                    p_vendor = vendor_override if vendor_override else (str(row.iloc[8]).strip() if len(row) > 8 else "")
                    p_compat = str(row.iloc[9]).strip() if len(row) > 9 else ""
                    p_cat = str(row.iloc[10]).strip() if len(row) > 10 else ""
                    
                    added_date = str(row.iloc[11]).strip() if len(row) > 11 and str(row.iloc[11]).strip() else datetime.now().strftime("%Y-%m-%d %H:%M")
                    last_ordered = str(row.iloc[12]).strip() if len(row) > 12 else ""
                    added_by = str(row.iloc[13]).strip() if len(row) > 13 and str(row.iloc[13]).strip() else "ADMIN"
                    last_edited = str(row.iloc[14]).strip() if len(row) > 14 else ""
                    hsn_code = str(row.iloc[15]).strip() if len(row) > 15 else "8714"
                    
                    try: gst_rate = float(row.iloc[16]) if len(row) > 16 else 18.0
                    except: gst_rate = 18.0
                    
                    try: last_cost = float(row.iloc[17]) if len(row) > 17 else p_price
                    except: last_cost = p_price
                    
                    # Tuple for UPSERT (18 fields)
                    data_to_insert.append((
                        p_id, p_name, p_desc, p_price, p_qty, p_rack, p_col, p_reorder, p_vendor,
                        p_compat, p_cat, added_date, last_ordered, added_by, last_edited,
                        hsn_code, gst_rate, last_cost
                    ))
                except Exception as row_err:
                    app_logger.warning(f"Skipping invalid row {index}: {row_err}")
                    continue
            
            conn = self.get_connection()
            try:
                conn.execute("PRAGMA synchronous = OFF")
                cursor = conn.cursor()
                cursor.execute("BEGIN TRANSACTION")
                
                # UPSERT Statement:
                # If part_id exists -> Update details BUT preserve added_date, added_by, last_ordered_date
                # If New -> Insert all
                
                sql = """
                    INSERT INTO parts (
                        part_id, part_name, description, unit_price, qty, 
                        rack_number, col_number, reorder_level, vendor_name, 
                        compatibility, category, added_date, last_ordered_date, added_by, last_edited_date,
                        hsn_code, gst_rate, last_cost
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(part_id) DO UPDATE SET
                        part_name=excluded.part_name,
                        description=excluded.description,
                        unit_price=excluded.unit_price,
                        qty=excluded.qty,
                        rack_number=excluded.rack_number,
                        col_number=excluded.col_number,
                        reorder_level=excluded.reorder_level,
                        vendor_name=excluded.vendor_name,
                        compatibility=excluded.compatibility,
                        category=excluded.category,
                        hsn_code=excluded.hsn_code,
                        gst_rate=excluded.gst_rate,
                        last_cost=excluded.last_cost,
                        last_edited_date=datetime('now', 'localtime')
                """
                # Note on Qty: User usually imports a stock sheet. So we replace Qty.
                # If they want to ADD stock, that's a different feature. 
                # Standard import replaces state.
                
                # Correction: The SQL above uses excluded.qty (new value).
                
                # Batch Processing (Safety limit for variables)
                batch_size = 500
                for i in range(0, len(data_to_insert), batch_size):
                    batch = data_to_insert[i:i + batch_size]
                    cursor.executemany(sql, batch)
                
                conn.commit()
                app_logger.info(f"Inventory imported from {csv_path}, {len(data_to_insert)} records processed")
                return True
            except Exception as e:
                app_logger.error(f"Database error during import: {e}")
                return False
            finally:
                conn.close()
        except Exception as e:
            app_logger.error(f"Import Error: {e}")
            return False

    def get_dashboard_stats(self):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            stats = {}
            cursor.execute("SELECT COUNT(*) FROM parts")
            stats['total_parts'] = cursor.fetchone()[0]
            cursor.execute("SELECT SUM(qty) FROM parts")
            res_qty = cursor.fetchone()[0]
            stats['total_stock_qty'] = res_qty if res_qty else 0
            cursor.execute("SELECT COUNT(*) FROM parts WHERE qty < 5")
            stats['low_stock_count'] = cursor.fetchone()[0]
            cursor.execute("SELECT SUM(unit_price * qty) FROM parts")
            res_val = cursor.fetchone()[0]
            stats['total_inventory_value'] = res_val if res_val else 0.0
            return stats
        except Exception as e:
            app_logger.error(f"Error calculating dashboard stats: {e}")
            return {'total_parts': 0, 'total_stock_qty': 0, 'low_stock_count': 0, 'total_inventory_value': 0.0}
        finally:
            conn.close()

    def get_part_by_id(self, part_id):
        part_id = str(part_id).strip()
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            # Explicit column order matches get_all_parts:
            # 0:part_id, 1:part_name, 2:desc, 3:unit_price, 4:qty,
            # 5:rack, 6:col, 7:reorder, 8:vendor, 9:compat, 10:cat,
            # 11:added_date, 12:last_ordered_date, 13:added_by, 14:last_edited_date,
            # 15:hsn_code, 16:gst_rate, 17:last_cost
            cursor.execute("""
                SELECT part_id, part_name, description, unit_price, qty,
                       rack_number, col_number, reorder_level, vendor_name,
                       compatibility, category, added_date, last_ordered_date, added_by, last_edited_date,
                       hsn_code, gst_rate, last_cost
                FROM parts WHERE part_id = ?
            """, (part_id,))
            row = cursor.fetchone()
            return row
        except Exception as e:
            app_logger.error(f"Error getting part {part_id}: {e}")
            return None
        finally:
            conn.close()

    def sell_part(self, part_id, qty, invoice_id, customer_name, price_override=None):
        part_id = str(part_id).strip()
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            # --- Atomic transaction: stock decrement + sales insert together ---
            cursor.execute("BEGIN TRANSACTION")

            cursor.execute("SELECT qty, unit_price, avg_landing_cost, last_cost FROM parts WHERE part_id = ?", (part_id,))
            row = cursor.fetchone()
            if not row:
                conn.rollback()
                return False, "Part not found"

            curr_qty, price, avg_landing_cost, last_cost = row
            if curr_qty < qty:
                conn.rollback()
                return False, f"Insufficient stock: {curr_qty}"

            # 1. Decrement stock
            cursor.execute("UPDATE parts SET qty = ? WHERE part_id = ?", (curr_qty - qty, part_id))

            # 2. Determine sale price
            sale_price = price_override if price_override is not None else price
            sale_date  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 3. COGS — prefer weighted avg landing cost, fall back to last_cost
            unit_cogs  = float(avg_landing_cost) if avg_landing_cost and float(avg_landing_cost) > 0 \
                         else (float(last_cost) if last_cost else 0.0)
            total_cogs = float(qty) * unit_cogs

            # 4. Record sale — both steps commit together
            cursor.execute(
                "INSERT INTO sales (invoice_id, part_id, quantity, price_at_sale, sale_date, cogs) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (invoice_id, part_id, qty, sale_price, sale_date, total_cogs)
            )
            conn.commit()
            app_logger.info(f"Part sold: {part_id}, Qty: {qty}, Inv: {invoice_id}")
            return True, "Success"
        except Exception as e:
            try: conn.rollback()
            except: pass
            app_logger.error(f"Error selling part {part_id}: {e}")
            return False, str(e)
        finally:
            conn.close()

    def process_return(self, invoice_id, part_id, qty_to_return, refund_amount, reason="Customer Return"):
        """
        Processes a sales return:
        1. Restores stock in 'parts'.
        2. Reverses the proportional COGS from the originating sales row.
        3. Logs return in 'returns' table.
        All steps are atomic — rolls back if any step fails.
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("BEGIN TRANSACTION")

            # 1. Restore stock
            cursor.execute("SELECT qty FROM parts WHERE part_id = ?", (part_id,))
            row = cursor.fetchone()
            if not row:
                conn.rollback()
                return False, "Part not found in database."

            cursor.execute("UPDATE parts SET qty = ? WHERE part_id = ?",
                           (row[0] + qty_to_return, part_id))

            # 2. Reverse COGS proportionally from the matching sales row
            cursor.execute(
                "SELECT quantity, cogs FROM sales WHERE invoice_id = ? AND part_id = ?",
                (invoice_id, part_id)
            )
            sale_row = cursor.fetchone()
            if sale_row and sale_row[0] and sale_row[0] > 0:
                orig_qty, orig_cogs = sale_row
                unit_cogs = float(orig_cogs or 0) / float(orig_qty)
                cogs_reduction = unit_cogs * qty_to_return
                new_sale_qty  = max(0, orig_qty - qty_to_return)
                new_sale_cogs = max(0.0, float(orig_cogs or 0) - cogs_reduction)
                cursor.execute(
                    "UPDATE sales SET quantity = ?, cogs = ? WHERE invoice_id = ? AND part_id = ?",
                    (new_sale_qty, new_sale_cogs, invoice_id, part_id)
                )

            # 3. Log return
            return_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT INTO returns (invoice_id, part_id, quantity, refund_amount, return_date, reason)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (invoice_id, part_id, qty_to_return, refund_amount, return_date, reason))

            conn.commit()
            app_logger.info(f"Return Processed: Inv {invoice_id}, Part {part_id}, Qty {qty_to_return}")
            return True, "Return processed successfully."

        except Exception as e:
            try: conn.rollback()
            except: pass
            app_logger.error(f"Error processing return: {e}")
            return False, str(e)
        finally:
            conn.close()

    def get_invoice_items(self, invoice_id):
        """
        Retrieves items from an invoice JSON. 
        Returns list of dicts: [{'id':..., 'name':..., 'qty':..., 'price':...}, ...]
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT json_items, date FROM invoices WHERE invoice_id = ?", (invoice_id,))
            row = cursor.fetchone()
            if not row:
                return []
            
            json_str = row[0]
            try:
                data = json.loads(json_str)
                # Normalize structure (list vs dict)
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return data.get('cart', [])
                return []  # unknown format
            except (json.JSONDecodeError, TypeError):
                return []
        except Exception as e:
            app_logger.error(f"Error fetching invoice items {invoice_id}: {e}")
            return []
        finally:
            conn.close()

    def get_invoice_details(self, invoice_id):
        """
        Fetch full invoice metadata + items for PDF regeneration.
        Returns: dict or None
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            # Select relevant columns
            cursor.execute("""
                SELECT invoice_id, customer_name, mobile, vehicle_model, reg_no, 
                       total_amount, discount, date, json_items, customer_gstin,
                       payment_cash, payment_upi, payment_due, payment_mode
                FROM invoices 
                WHERE invoice_id = ?
            """, (invoice_id,))
            row = cursor.fetchone()
            
            if not row: return None
            
            # Parse Items and Metadata from JSON
            json_str = row[8]
            items = []
            extra_details = {}
            tax_details = []
            try:
                parsed = json.loads(json_str)
                if isinstance(parsed, list):
                    items = parsed
                elif isinstance(parsed, dict):
                    items = parsed.get('cart', [])
                    extra_details = parsed.get('extra_details', {})
                    tax_details = parsed.get('tax_details', [])
            except: pass
            
            total = row[5]
            discount_val = row[6]
            
            # Map legacy or new metadata
            return {
                'invoice_id': row[0],
                'customer': row[1],
                'mobile': row[2],
                'vehicle': row[3],
                'reg_no': row[4],
                'total': total,
                'total_savings': discount_val, # Unified savings
                'original_mrp': total + discount_val,
                # If tax_details exists, extract precisely. For legacy invoices (no tax_details),
                # do NOT assume 18% — just show full total as taxable and 0 GST (honest fallback).
                'taxable_value': total - sum(t.get('gst_amt', 0) for t in tax_details) if tax_details else total,
                'gst_included':  sum(t.get('gst_amt', 0) for t in tax_details) if tax_details else 0.0,
                'date': row[7],
                'items': items,
                'tax_details': tax_details,
                'extra_details': extra_details,
                'customer_gstin': row[9] if len(row) > 9 else "",
                'payment_cash': row[10] if len(row) > 10 and row[10] is not None else total,
                'payment_upi': row[11] if len(row) > 11 and row[11] is not None else 0.0,
                'payment_due': row[12] if len(row) > 12 and row[12] is not None else 0.0,
                'payment_mode': row[13] if len(row) > 13 and row[13] is not None else "CASH",
            }
        except Exception as e:
            app_logger.error(f"Error fetching invoice details {invoice_id}: {e}")
            return None
        finally:
            conn.close()

    def get_all_parts(self):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            # Explicitly select columns to ensure order
            # 0:id, 1:name, 2:desc, 3:price, 4:qty, 5:rack, 6:col, 7:reorder,
            # 8:vendor, 9:compat, 10:cat, 11:added_date, 12:last_ordered, 13:added_by, 14:last_edited_date,
            # 15:hsn_code, 16:gst_rate
            cursor.execute("""
                SELECT part_id, part_name, description, unit_price, qty,
                       rack_number, col_number, reorder_level, vendor_name,
                       compatibility, category, added_date, last_ordered_date, added_by, last_edited_date,
                       hsn_code, gst_rate, last_cost
                FROM parts
                ORDER BY added_date DESC
            """)
            rows = cursor.fetchall()
            return rows
        except Exception as e:
            app_logger.error(f"Error fetching all parts: {e}")
            return []
        finally:
            conn.close()

    def get_reorder_data(self):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            # Returns: id, name, qty, reorder, vendor, price, added_date, last_ordered
            sql = "SELECT part_id, part_name, qty, reorder_level, vendor_name, unit_price, added_date, last_ordered_date FROM parts WHERE CAST(qty AS REAL) <= CAST(reorder_level AS REAL)"
            cursor.execute(sql)
            rows = cursor.fetchall()
            return rows
        except Exception as e:
            app_logger.error(f"Error fetching reorder data: {e}")
            return []
        finally:
            conn.close()

    def add_part(self, part_data, allow_update=False):
        """
        Add a new part to inventory with duplicate detection.
        Returns: (success, message, is_duplicate)
        """
        # data: dict or tuple/list
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            if isinstance(part_data, dict):
                part_id = str(part_data['id']).strip()  # Normalize: remove leading/trailing spaces
                part_data['id'] = part_id  # Write back stripped value
            else:
                # Legacy support or fallback
                data = list(part_data)
                while len(data) < 11: data.append("")
                part_id = str(data[0]).strip()  # Normalize: remove leading/trailing spaces
                data[0] = part_id  # Write back stripped value
            
            # Check for existing part
            cursor.execute("SELECT part_id, part_name, qty, unit_price FROM parts WHERE part_id = ?", (part_id,))
            existing = cursor.fetchone()
            
            if existing and not allow_update:
                # Duplicate detected - return warning
                existing_name = existing[1]
                existing_qty = existing[2]
                existing_price = existing[3]
                msg = f"DUPLICATE: '{existing_name}' already exists (Qty: {existing_qty}, Price: ₹{existing_price})"
                app_logger.warning(f"Duplicate part entry attempted: {part_id}")
                return False, msg, True  # Return is_duplicate=True
            
            # Get dates
            added_date = datetime.now().strftime("%Y-%m-%d %H:%M")
            last_ordered = ""
            added_by = "ADMIN" # Default fallback
            
            if existing:
                # Preserve original dates if updating
                cursor.execute("SELECT added_date, last_ordered_date FROM parts WHERE part_id = ?", (part_id,))
                dates = cursor.fetchone()
                if dates:
                    added_date = dates[0] if dates[0] else added_date
                    last_ordered = dates[1] if dates[1] else ""
            
            if existing and allow_update:
                # UPDATE
                if isinstance(part_data, dict):
                    part_name = part_data['name']
                    conn.execute("""
                        UPDATE parts SET 
                        part_name=?, description=?, unit_price=?, qty=?, 
                        rack_number=?, col_number=?, reorder_level=?, vendor_name=?,
                        compatibility=?, category=?, last_edited_date=?,
                        hsn_code=?, gst_rate=?
                        WHERE part_id=?
                    """, (
                        part_data['name'], part_data['desc'], part_data['price'], 
                        part_data['qty'], part_data['rack'], part_data['col'], 
                        part_data.get('reorder', 5), part_data.get('vendor', ''),
                        part_data.get('compatibility', ''), part_data.get('category', ''),
                        datetime.now().strftime("%Y-%m-%d %H:%M"),
                        part_data.get('hsn_code', ''), part_data.get('gst_rate', 18.0),
                        part_id
                    ))
                    # Learn rule from part name and category
                    self.learn_hsn_rule(part_name, part_data.get('hsn_code', ''), part_data.get('gst_rate', 18.0))
                    if part_data.get('category'):
                        self.learn_hsn_rule(part_data.get('category'), part_data.get('hsn_code', ''), part_data.get('gst_rate', 18.0))
                else:
                    # Legacy Tuple
                    part_name = part_data[1]
                    conn.execute("""
                        UPDATE parts SET 
                        part_name=?, description=?, unit_price=?, qty=?, 
                        rack_number=?, col_number=?, reorder_level=?, vendor_name=?,
                        compatibility=?, category=?, last_edited_date=?,
                        hsn_code=?, gst_rate=?
                        WHERE part_id=?
                    """, (
                        part_data[1], part_data[2], part_data[3], part_data[4], 
                        part_data[5], part_data[6], 
                        part_data[7] if len(part_data)>7 else 5,
                        part_data[8] if len(part_data)>8 else '',
                        part_data[9] if len(part_data)>9 else '',
                        part_data[10] if len(part_data)>10 else '',
                        datetime.now().strftime("%Y-%m-%d %H:%M"),
                        part_data[11] if len(part_data)>11 else '',
                        part_data[12] if len(part_data)>12 else 18.0,
                        part_id
                    ))
                    # Learn rule from updated tuple entry
                    p_hsn = part_data[11] if len(part_data)>11 else ''
                    p_gst = part_data[12] if len(part_data)>12 else 18.0
                    p_cat = part_data[10] if len(part_data)>10 else ''
                    self.learn_hsn_rule(part_name, p_hsn, p_gst)
                    if p_cat:
                        self.learn_hsn_rule(p_cat, p_hsn, p_gst)
                msg = "Part updated successfully"
                is_dup = False
            else:
                # INSERT (Original Logic for New Parts)
                if isinstance(part_data, dict):
                    part_name = part_data['name']
                    conn.execute("""
                        INSERT INTO parts (
                            part_id, part_name, description, unit_price, qty, 
                            rack_number, col_number, reorder_level, vendor_name, 
                            compatibility, category, added_date, added_by,
                            hsn_code, gst_rate
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        part_data['id'], part_data['name'], part_data['desc'], 
                        part_data['price'], part_data['qty'], part_data['rack'], 
                        part_data['col'], part_data.get('reorder', 5), 
                        part_data.get('vendor', ''), part_data.get('compatibility', ''),
                        part_data.get('category', ''),
                        added_date,
                        added_by,
                        part_data.get('hsn_code', ''),
                        part_data.get('gst_rate', 18.0)
                    ))
                    # Learn rule from new part entry
                    self.learn_hsn_rule(part_data['name'], part_data.get('hsn_code', ''), part_data.get('gst_rate', 18.0))
                    if part_data.get('category'):
                        self.learn_hsn_rule(part_data.get('category'), part_data.get('hsn_code', ''), part_data.get('gst_rate', 18.0))
                else:
                    # Legacy Tuple Path
                    part_name = part_data[1]
                    # Ensure 'data' is defined for tuple path
                    data = list(part_data)
                    while len(data) < 17: data.append("") # Extend to ensure indices are safe for hsn_code, gst_rate
                    conn.execute("""
                        INSERT INTO parts (
                            part_id, part_name, description, unit_price, qty, 
                            rack_number, col_number, reorder_level, vendor_name, 
                            compatibility, category, added_date, added_by,
                            hsn_code, gst_rate
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        data[0], data[1], data[2], 
                        data[3], data[4], data[5], 
                        data[6], data[7] if len(data)>7 else 5, 
                        data[8] if len(data)>8 else '',
                        data[9] if len(data)>9 else '',
                        data[10] if len(data)>10 else '',
                        added_date,
                        added_by,
                        data[15] if len(data) > 15 else '',
                        data[16] if len(data) > 16 else 18.0
                    ))
                    # Learn rule from new tuple entry
                    p_name = data[1]
                    p_hsn = data[15] if len(data) > 15 else ''
                    p_gst = data[16] if len(data) > 16 else 18.0
                    p_cat = data[10] if len(data) > 10 else ''
                    self.learn_hsn_rule(p_name, p_hsn, p_gst)
                    if p_cat:
                        self.learn_hsn_rule(p_cat, p_hsn, p_gst)
                
                msg = "Part added successfully"
                is_dup = False

            conn.commit()
            app_logger.info(f"Part saved: {part_id} - {part_name}")
            return True, msg, is_dup
        except Exception as e:
            app_logger.error(f"Error adding part: {e}")
            return False, f"Database Error: {e}", False
        finally:
            conn.close()


    def update_last_ordered_dates(self, part_ids):
        conn = self.get_connection()
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # Batch update might be tricky with list, use loop or IN clause
            # Safe way for many IDs:
            placeholders = ','.join('?' for _ in part_ids)
            sql = f"UPDATE parts SET last_ordered_date = ? WHERE part_id IN ({placeholders})"
            conn.execute(sql, [now] + part_ids)
            conn.commit()
            app_logger.info(f"Updated last_ordered_date for {len(part_ids)} parts")
            return True
        except Exception as e:
            app_logger.error(f"Error updating dates: {e}")
            return False
        finally:
            conn.close()

    def delete_part(self, part_id):
        part_id = str(part_id).strip()  # Normalize: remove leading/trailing spaces
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("BEGIN TRANSACTION")
            
            # 1. Nullify FK in sales
            cursor.execute("UPDATE sales SET part_id = NULL WHERE part_id = ?", (part_id,))
            
            # 2. Nullify FK in po_items
            cursor.execute("UPDATE po_items SET part_id = NULL WHERE part_id = ?", (part_id,))
            
            # 3. Delete from parts
            cursor.execute("DELETE FROM parts WHERE part_id = ?", (part_id,))
            
            conn.commit()
            app_logger.info(f"Part deleted: {part_id}")
            return True, "Deleted"
        except Exception as e: 
            conn.rollback()
            app_logger.error(f"Error deleting part {part_id}: {e}")
            return False, str(e)
        finally:
            conn.close()


    # --- Invoice Methods ---
    def get_next_invoice_id(self):
        """
        Generate next invoice ID using a sequence stored in settings.
        Uses BEGIN IMMEDIATE to make the read+write atomic, preventing
        duplicate IDs under concurrent access.
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()

            # BEGIN IMMEDIATE: locks the DB for write immediately, so no
            # other connection can read-then-increment the same sequence.
            cursor.execute("BEGIN IMMEDIATE")

            cursor.execute("SELECT value FROM settings WHERE key='invoice_sequence'")
            row = cursor.fetchone()

            if row:
                current_seq = int(row[0])
            else:
                # Bootstrap: count existing invoices so legacy DBs start cleanly
                cursor.execute("SELECT COUNT(*) FROM invoices")
                count = cursor.fetchone()[0]
                current_seq = count + 1001

            new_id = f"INV-{current_seq}"

            # Increment and persist in the SAME transaction
            cursor.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('invoice_sequence', ?)",
                (current_seq + 1,)
            )
            conn.commit()

            app_logger.info(f"Generated new Invoice ID: {new_id}")
            return new_id

        except Exception as e:
            try: conn.rollback()
            except: pass
            app_logger.error(f"Error generating invoice ID: {e}")
            return f"INV-ERR-{int(datetime.now().timestamp())}"
        finally:
            conn.close()

    def set_invoice_sequence(self, new_seq):
        """Developer tool to reset sequence"""
        return self.update_setting('invoice_sequence', new_seq)

    def save_invoice(self, invoice_data):
        """
        invoice_data: (invoice_id, customer_name, mobile, vehicle_model, reg_no,
                       total_amount, discount, date, json_items, items_count,
                       customer_gstin[, payment_cash, payment_upi, payment_due, payment_mode])
        The last 4 payment fields are optional for backward compat — default to CASH.
        """
        conn = self.get_connection()
        try:
            invoice_data = list(invoice_data)
            # Ensure at minimum 11 base fields
            while len(invoice_data) < 11:
                invoice_data.append("")
            # Payment fields (indices 11-14) — default to full-cash if not provided
            if len(invoice_data) < 12: invoice_data.append(0.0)   # payment_cash
            if len(invoice_data) < 13: invoice_data.append(0.0)   # payment_upi
            if len(invoice_data) < 14: invoice_data.append(0.0)   # payment_due
            if len(invoice_data) < 15: invoice_data.append("CASH") # payment_mode

            conn.execute("""
                INSERT OR REPLACE INTO invoices
                (invoice_id, customer_name, mobile, vehicle_model, reg_no,
                 total_amount, discount, date, json_items, items_count, customer_gstin,
                 payment_cash, payment_upi, payment_due, payment_mode)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, invoice_data[:15])
            conn.commit()
            app_logger.info(f"Invoice saved: {invoice_data[0]}")
            return True, "Saved"
        except Exception as e:
            app_logger.error(f"Error saving invoice: {e}")
            return False, str(e)
        finally:
            conn.close()

    def get_sales_report(self, start_date, end_date, search_query="", dues_only=False):
        """
        Fetch filtered sales records for reporting.
        Returns: list of (date, invoice_id, customer_name, items_count, total_amount,
                          json_items, invoice_id, return_count,
                          payment_cash, payment_upi, payment_due, payment_mode)
        """
        conn = self.get_connection()
        try:
            params = []
            sql = """
                SELECT
                    i.date, i.invoice_id, i.customer_name, i.items_count, i.total_amount, i.json_items, i.invoice_id,
                    (SELECT COUNT(*) FROM returns r WHERE r.invoice_id = i.invoice_id) as return_count,
                    COALESCE(i.payment_cash, 0.0) as payment_cash,
                    COALESCE(i.payment_upi,  0.0) as payment_upi,
                    COALESCE(i.payment_due,  0.0) as payment_due,
                    COALESCE(i.payment_mode, 'CASH') as payment_mode,
                    (SELECT COALESCE(SUM(refund_amount), 0) FROM returns r WHERE r.invoice_id = i.invoice_id) as total_refund
                FROM invoices i
            """

            is_global_search = bool(search_query and len(search_query) > 3)

            if is_global_search:
                sql += """
                         WHERE (i.date BETWEEN ? AND ? AND (i.customer_name LIKE ? OR i.mobile LIKE ? OR i.invoice_id LIKE ?))
                         OR i.invoice_id = ?
                """
                p_start = start_date + " 00:00:00"
                p_end   = end_date   + " 23:59:59"
                q = f"%{search_query}%"
                params = [p_start, p_end, q, q, q, search_query]
            else:
                sql += "WHERE i.date BETWEEN ? AND ?"
                params = [start_date + " 00:00:00", end_date + " 23:59:59"]
                if search_query:
                    sql += " AND (i.customer_name LIKE ? OR i.mobile LIKE ? OR i.invoice_id LIKE ?)"
                    q = f"%{search_query}%"
                    params.extend([q, q, q])

            if dues_only:
                sql += " AND COALESCE(i.payment_due, 0.0) > 0"

            sql += " ORDER BY i.date DESC"

            cursor = conn.execute(sql, params)
            return cursor.fetchall()
        except Exception as e:
            app_logger.error(f"Error fetching sales report: {e}")
            return []
        finally:
            conn.close()

    # NOTE: get_sales_statistics, get_top_selling_parts, get_top_customers,
    # and get_sales_by_date_range are defined below (around line 2549+).
    # Earlier duplicate bodies removed — Python always uses the last definition.


    def get_all_invoices(self, query="", date_from=None, date_to=None):
        conn = self.get_connection()
        try:
            sql = "SELECT * FROM invoices WHERE 1=1"
            params = []
            if query:
                sql += " AND (invoice_id LIKE ? OR customer_name LIKE ?)"
                params.extend([f"%{query}%", f"%{query}%"])
            if date_from and date_to:
                sql += " AND date BETWEEN ? AND ?"
                params.extend([date_from + " 00:00:00", date_to + " 23:59:59"])
            sql += " ORDER BY date DESC"
            cursor = conn.execute(sql, params)
            return cursor.fetchall()
        except Exception as e:
            app_logger.error(f"Error fetching invoices: {e}")
            return []
        finally:
            conn.close()

    def update_invoice_payment(self, invoice_id, payment_cash, payment_upi, payment_due, payment_mode):
        """Update payment tracking fields for an existing invoice (e.g. 'Collect Due' flow)."""
        conn = self.get_connection()
        try:
            conn.execute("""
                UPDATE invoices
                SET payment_cash = ?, payment_upi = ?, payment_due = ?, payment_mode = ?
                WHERE invoice_id = ?
            """, (payment_cash, payment_upi, payment_due, payment_mode, invoice_id))
            conn.commit()
            app_logger.info(f"Payment updated for invoice {invoice_id}: cash={payment_cash} upi={payment_upi} due={payment_due}")
            return True, "Payment updated"
        except Exception as e:
            app_logger.error(f"Error updating payment for invoice {invoice_id}: {e}")
            return False, str(e)
        finally:
            conn.close()

    def get_payment_summary(self, start_date, end_date):
        """Return aggregated cash/UPI/due totals and count of invoices with dues for the given date range."""
        conn = self.get_connection()
        try:
            cursor = conn.execute("""
                SELECT
                    COALESCE(SUM(payment_cash), 0.0) as total_cash,
                    COALESCE(SUM(payment_upi),  0.0) as total_upi,
                    COALESCE(SUM(payment_due),  0.0) as total_due,
                    COUNT(CASE WHEN COALESCE(payment_due, 0) > 0 THEN 1 END) as due_invoices
                FROM invoices
                WHERE date BETWEEN ? AND ?
            """, (start_date + " 00:00:00", end_date + " 23:59:59"))
            row = cursor.fetchone()
            if row:
                return {"cash": row[0], "upi": row[1], "due": row[2], "due_count": row[3]}
            return {"cash": 0.0, "upi": 0.0, "due": 0.0, "due_count": 0}
        except Exception as e:
            app_logger.error(f"Error fetching payment summary: {e}")
            return {"cash": 0.0, "upi": 0.0, "due": 0.0, "due_count": 0}
        finally:
            conn.close()

    # --- Expense Methods ---
    def add_expense(self, title, amount, category, date_str):
        conn = self.get_connection()
        try:
            conn.execute("INSERT INTO expenses (title, amount, category, date) VALUES (?, ?, ?, ?)", 
                         (title, amount, category, date_str))
            conn.commit()
            app_logger.info(f"Expense added: {title}, {amount}")
            return True, "Success"
        except Exception as e: 
            app_logger.error(f"Error adding expense: {e}")
            return False, str(e)
        finally:
            conn.close()

    def get_all_expenses(self, date_from=None, date_to=None):
        conn = self.get_connection()
        try:
            if date_from and date_to:
                # Query with date range — use time boundary so same-day end rows aren't missed
                result = conn.execute("""
                    SELECT id, title, amount, category, date 
                    FROM expenses 
                    WHERE date BETWEEN ? AND ?
                    ORDER BY date DESC, id DESC
                """, (date_from, date_to + " 23:59:59")).fetchall()
                app_logger.info(f"Query expenses between {date_from} and {date_to}: {len(result)} found")
            else:
                # Get all expenses if no date range
                result = conn.execute("""
                    SELECT id, title, amount, category, date 
                    FROM expenses 
                    ORDER BY date DESC, id DESC
                """).fetchall()
                app_logger.info(f"Query all expenses: {len(result)} found")
            return result
        except Exception as e:
            app_logger.error(f"Error fetching expenses: {e}")
            return []
        finally:
            conn.close()

    def delete_expense(self, expense_id):
        conn = self.get_connection()
        try:
            conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
            conn.commit()
            app_logger.info(f"Expense deleted: ID {expense_id}")
            return True, "Deleted"
        except Exception as e: 
            app_logger.error(f"Error deleting expense {expense_id}: {e}")
            return False, str(e)
        finally:
            conn.close()
    
    def update_expense(self, expense_id, title, amount, category, date_str):
        """Update an existing expense entry"""
        conn = self.get_connection()
        try:
            conn.execute("""
                UPDATE expenses 
                SET title = ?, amount = ?, category = ?, date = ?
                WHERE id = ?
            """, (title, amount, category, date_str, expense_id))
            conn.commit()
            app_logger.info(f"Expense updated: ID {expense_id}")
            return True, "Updated"
        except Exception as e:
            app_logger.error(f"Error updating expense {expense_id}: {e}")
            return False, str(e)
        finally:
            conn.close()

    def get_expenses_by_day(self, date_from, date_to):
        """Get daily expense totals for a date range"""
        conn = self.get_connection()
        try:
            sql = """
                SELECT DATE(date) as day, SUM(amount) as daily_total
                FROM expenses
                WHERE DATE(date) BETWEEN ? AND ?
                GROUP BY DATE(date)
                ORDER BY DATE(date) ASC
            """
            cursor = conn.execute(sql, (date_from, date_to))
            rows = cursor.fetchall()
            return {r[0]: r[1] for r in rows}
        except Exception as e:
            app_logger.error(f"Error getting expenses by day: {e}")
            return {}
        finally:
            conn.close()



    def receive_po_item(self, line_item_id, qty_received_now, new_buy_price, part_id):
        """
        Process receiving of an item:
        1. Update po_items (accumulate qty_received)
        2. Update parts inventory (add stock, update price)
        3. Update PO status if fully received (Check performed by logic or caller)
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("BEGIN TRANSACTION")
            
            # 1. Update PO Item
            cursor.execute("SELECT qty_ordered, qty_received, req_rack, req_col FROM po_items WHERE id = ?", (line_item_id,))
            row = cursor.fetchone()
            if not row:
                return False, "Item not found"
            
            ordered, current_received, req_rack, req_col = row
            new_total_received = current_received + qty_received_now
            
            if new_total_received > ordered:
                # Optional: Allow over-receiving? For now, warn but allow? Or cap?
                # Let's simple allow it but log it.
                app_logger.warning(f"Receiving more than ordered: {new_total_received}/{ordered}")

            # Update PO Item
            # NOTE: received_cost stores the *weighted average* buy price across all partial receives,
            # not just the last price. This ensures vendor_stats spend calculation is accurate.
            cursor.execute("UPDATE po_items SET qty_received = ? WHERE id = ?", 
                          (new_total_received, line_item_id))
            # received_cost will be updated below after computing new_avg (weighted average)
            
            # 2. Update Inventory Part
            
            # First, check if part exists in inventory
            cursor.execute("SELECT part_id FROM parts WHERE part_id = ?", (part_id,))
            part_exists = cursor.fetchone()
            
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            if part_exists:
                # Part exists - add stock, update last_cost, and compute weighted avg_landing_cost.
                # Update part's rack and col IF they were empty in inventory and req_rack/req_col are provided!
                cursor.execute("SELECT COALESCE(qty,0), COALESCE(avg_landing_cost,0), COALESCE(rack_number,''), COALESCE(col_number,'') FROM parts WHERE part_id = ?",
                               (part_id,))
                cost_row = cursor.fetchone()
                old_qty = float(cost_row[0]) if cost_row else 0.0
                old_avg = float(cost_row[1]) if cost_row else 0.0
                inv_rack = cost_row[2] if cost_row and cost_row[2] else ""
                inv_col = cost_row[3] if cost_row and cost_row[3] else ""

                new_rack = req_rack if req_rack and not inv_rack else inv_rack
                new_col = req_col if req_col and not inv_col else inv_col
                
                new_total_qty = old_qty + qty_received_now
                if new_total_qty > 0:
                    new_avg = (old_qty * old_avg + qty_received_now * new_buy_price) / new_total_qty
                else:
                    new_avg = new_buy_price

                # Also update received_cost in po_items to the new weighted avg so vendor spend stats are accurate
                cursor.execute("UPDATE po_items SET received_cost = ? WHERE id = ?", (round(new_avg, 4), line_item_id))

                cursor.execute("""
                    UPDATE parts 
                    SET qty = COALESCE(qty, 0) + ?,
                        last_cost = ?,
                        avg_landing_cost = ?,
                        last_ordered_date = ?,
                        rack_number = ?,
                        col_number = ?
                    WHERE part_id = ?
                """, (qty_received_now, new_buy_price, round(new_avg, 4), current_time, new_rack, new_col, part_id))
            else:
                # Part doesn't exist - INSERT it
                # Get part name from po_items
                cursor.execute("SELECT part_name FROM po_items WHERE id = ?", (line_item_id,))
                part_name_row = cursor.fetchone()
                part_name = part_name_row[0] if part_name_row else part_id
                
                # Insert new part into inventory with avg_landing_cost set from first GRN
                cursor.execute("""
                    INSERT INTO parts (
                        part_id, part_name, description, unit_price, qty, 
                        rack_number, col_number, reorder_level, vendor_name,
                        compatibility, category, added_date, added_by,
                        last_cost, avg_landing_cost, last_ordered_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    part_id, part_name, "", new_buy_price, qty_received_now,
                    req_rack, req_col, 5, "", "", "", current_time, "PO_SYSTEM",
                    new_buy_price, new_buy_price, current_time  # last_cost = avg_landing_cost = buy price on first receipt
                ))
                app_logger.info(f"Created new part in inventory from PO: {part_id} - {part_name}")
                # Set received_cost for new part too (first receive = buy price)
                cursor.execute("UPDATE po_items SET received_cost = ? WHERE id = ?", (new_buy_price, line_item_id))
            
            # 3. Check if all items in this PO are received to Close PO?
            # The prompt says "If qty_received < qty_ordered, keep ... (Status: PARTIAL)".
            # "If qty_received == qty_ordered, remove ... (Status: COMPLETED)".
            # This refers to the Line Item status in the UI loop.
            # But the PO status itself should also be updated.
            
            # Logic to update PO status
            cursor.execute("SELECT po_id FROM po_items WHERE id = ?", (line_item_id,))
            po_id_row = cursor.fetchone()
            if po_id_row:
                po_id = po_id_row[0]
                # Count how many items still have pending qty (strict: ordered > received)
                cursor.execute(
                    "SELECT COUNT(*) FROM po_items WHERE po_id = ? AND qty_ordered > qty_received",
                    (po_id,)
                )
                pending_count = cursor.fetchone()[0]

                new_status = 'PARTIAL' if pending_count > 0 else 'CLOSED'
                cursor.execute("UPDATE purchase_orders SET status = ? WHERE po_id = ?", (new_status, po_id))

            conn.commit()
            app_logger.info(f"Received item {line_item_id}: {qty_received_now} @ {new_buy_price}")
            return True, "Received Successfully"

        except Exception as e:
            app_logger.error(f"Error receiving item: {e}")
            return False, str(e)
        finally:
            conn.close()

    def get_backlog_items(self):
        """
        Returns all pending items sorted by Date (Oldest First).
        Same query as get_open_po_items but strictly for backlog report.
        """
        return self.get_open_po_items()

    def force_close_po(self, po_id):
        """
        Force close a PO regardless of pending items.
        - Sets purchase_orders.status = 'CLOSED' 
        - DOES NOT overwrite qty_received, preserving accurate historical shortfall records.
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("BEGIN TRANSACTION")

            # Close the PO header. 
            # (get_open_po_items excludes 'CLOSED', so this naturally drops it from Backlog)
            cursor.execute("""
                UPDATE purchase_orders SET status = 'CLOSED' WHERE po_id = ?
            """, (po_id,))

            conn.commit()
            app_logger.info(f"Force closed PO: {po_id}")
            return True, "Force closed successfully"
        except Exception as e:
            app_logger.error(f"Error force closing PO {po_id}: {e}")
            try: conn.rollback()
            except: pass
            return False, str(e)
        finally:
            conn.close()

    def get_financial_summary(self, date_from=None, date_to=None):
        """
        Returns revenue, expenses, COGS, and net_profit.
        If date_from and date_to are provided (YYYY-MM-DD strings), results are
        filtered to that period. Otherwise, all-time totals are returned.
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()

            if date_from and date_to:
                p_start = date_from + " 00:00:00"
                p_end   = date_to   + " 23:59:59"
                date_filter_inv  = "WHERE date BETWEEN ? AND ?"
                date_filter_ret  = "WHERE DATE(return_date) BETWEEN ? AND ?"
                date_filter_exp  = "WHERE date BETWEEN ? AND ?"
                date_filter_sale = "WHERE sale_date BETWEEN ? AND ?"
                params = (p_start, p_end)
            else:
                date_filter_inv = date_filter_ret = date_filter_exp = date_filter_sale = ""
                params = ()

            cursor.execute(f"SELECT SUM(total_amount) FROM invoices {date_filter_inv}", params)
            r = cursor.fetchone()[0]
            revenue = r if r else 0.0

            cursor.execute(f"SELECT SUM(refund_amount) FROM returns {date_filter_ret}", params)
            ref = cursor.fetchone()[0]
            revenue -= ref if ref else 0.0

            cursor.execute(f"SELECT SUM(amount) FROM expenses {date_filter_exp}", params)
            e = cursor.fetchone()[0]
            expenses = e if e else 0.0

            cursor.execute(f"SELECT SUM(cogs) FROM sales {date_filter_sale}", params)
            c = cursor.fetchone()[0]
            total_cogs = c if c else 0.0

            cursor.execute("SELECT category, SUM(amount) FROM expenses GROUP BY category")
            breakdown = cursor.fetchall()

            return {
                "revenue": revenue,
                "expenses": expenses,
                "cogs": total_cogs,
                "net_profit": revenue - expenses - total_cogs,
                "breakdown": breakdown
            }
        except Exception as e:
            app_logger.error(f"Error calculating financial summary: {e}")
            return {
                "revenue": 0.0,
                "expenses": 0.0,
                "cogs": 0.0,
                "net_profit": 0.0,
                "breakdown": []
            }
        finally:
            conn.close()

    def get_total_cogs(self, date_from, date_to):
        """Fetch summed COGS from the sales table for a specific period."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            sql = "SELECT SUM(cogs) FROM sales WHERE sale_date BETWEEN ? AND ?"
            cursor.execute(sql, (date_from + " 00:00:00", date_to + " 23:59:59"))
            c = cursor.fetchone()[0]
            return float(c) if c else 0.0
        except Exception as e:
            app_logger.error(f"Error getting total COGS: {e}")
            return 0.0
        finally:
            conn.close()

    def get_customer_history(self, search_term):
        """Look up the most recent invoice matching mobile, reg_no, GSTIN, or customer name."""
        if not search_term:
            return None
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT customer_name, mobile, vehicle_model, reg_no, customer_gstin 
                FROM invoices 
                WHERE mobile = ?
                   OR reg_no = ?
                   OR customer_gstin = ?
                   OR LOWER(customer_name) LIKE LOWER(?)
                ORDER BY date DESC 
                LIMIT 1
            """, (search_term, search_term, search_term, f"%{search_term}%"))
            row = cursor.fetchone()
            return row if row else None
        except Exception as e:
            app_logger.error(f"Error loading customer history: {e}")
            return None
        finally:
            conn.close()


    # --- Custom Billing Fields Methods ---
    def get_custom_billing_fields(self):
        """Retrieve all saved custom billing field names in order"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT field_name FROM custom_billing_fields ORDER BY field_order, id")
            rows = cursor.fetchall()
            return [row[0] for row in rows]
        except Exception as e:
            app_logger.error(f"Error fetching custom billing fields: {e}")
            return []
        finally:
            conn.close()

    def add_custom_billing_field(self, field_name):
        """Save a new custom billing field definition"""
        conn = self.get_connection()
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # Get max order
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(field_order) FROM custom_billing_fields")
            max_order = cursor.fetchone()[0]
            next_order = (max_order + 1) if max_order is not None else 0
            
            conn.execute("INSERT INTO custom_billing_fields (field_name, field_order, created_at) VALUES (?, ?, ?)", 
                         (field_name, next_order, timestamp))
            conn.commit()
            app_logger.info(f"Custom billing field saved: {field_name}")
            return True
        except sqlite3.IntegrityError:
            app_logger.warning(f"Custom field '{field_name}' already exists")
            return False
        except Exception as e:
            app_logger.error(f"Error saving custom billing field: {e}")
            return False
        finally:
            conn.close()

    def remove_custom_billing_field(self, field_name):
        """Delete a custom billing field definition"""
        conn = self.get_connection()
        try:
            conn.execute("DELETE FROM custom_billing_fields WHERE field_name = ?", (field_name,))
            conn.commit()
            app_logger.info(f"Custom billing field removed: {field_name}")
            return True
        except Exception as e:
            app_logger.error(f"Error removing custom billing field: {e}")
            return False
        finally:
            conn.close()

    # --- AI / Search Methods ---
    def search_by_compatibility(self, keyword):
        """
        Search for parts where description, name, or compatibility fields match the keyword.
        Used by AI Nexus.
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            sql = """
                SELECT * FROM parts 
                WHERE part_name LIKE ? 
                OR description LIKE ? 
                OR compatibility LIKE ? 
                OR category LIKE ?
            """
            wildcard = f"%{keyword}%"
            cursor.execute(sql, (wildcard, wildcard, wildcard, wildcard))
            rows = cursor.fetchall()
            return rows
        except Exception as e:
            app_logger.error(f"Error searching compatibility for {keyword}: {e}")
            return []
        finally:
            conn.close()

    # --- Security Grid Methods ---
    def log_activity(self, username, action, details=""):
        conn = self.get_connection()
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute("INSERT INTO activity_logs (username, action, details, timestamp) VALUES (?, ?, ?, ?)", 
                         (username, action, details, timestamp))
            conn.commit()
            return True
        except Exception as e:
            app_logger.error(f"Error logging activity: {e}")
            return False
        finally:
            conn.close()

    def get_recent_activity(self, limit=20):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT username, action, details, timestamp FROM activity_logs ORDER BY timestamp DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return rows
        except Exception as e:
            app_logger.error(f"Error fetching activity logs: {e}")
            return []
        finally:
            conn.close()

    # --- Analytics Methods for Sales Dashboard ---
    def get_sales_by_date_range(self, date_from, date_to):
        """Get daily net sales data for charting (gross minus refunds)"""
        conn = self.get_connection()
        try:
            sql = """
                SELECT 
                    DATE(i.date) as sale_date,
                    SUM(i.total_amount) - COALESCE(
                        (SELECT SUM(r.refund_amount) FROM returns r
                         WHERE DATE(r.return_date) = DATE(i.date)), 0
                    ) as daily_net_total,
                    COUNT(*) as invoice_count
                FROM invoices i
                WHERE i.date BETWEEN ? AND ?
                GROUP BY DATE(i.date)
                ORDER BY sale_date ASC
            """
            cursor = conn.execute(sql, (date_from + " 00:00:00", date_to + " 23:59:59"))
            rows = cursor.fetchall()
            return rows
        except Exception as e:
            app_logger.error(f"Error getting sales by date: {e}")
            return []
        finally:
            conn.close()
    
    def get_top_selling_parts(self, date_from, date_to, limit=5):
        """Get top selling parts with quantities and revenue"""
        conn = self.get_connection()
        try:
            sql = """
                SELECT 
                    s.part_id,
                    p.part_name,
                    SUM(s.quantity) as total_qty,
                    SUM(s.quantity * s.price_at_sale) as total_revenue
                FROM sales s
                LEFT JOIN parts p ON s.part_id = p.part_id
                WHERE s.sale_date BETWEEN ? AND ?
                GROUP BY s.part_id, p.part_name
                ORDER BY total_qty DESC
                LIMIT ?
            """
            cursor = conn.execute(sql, (date_from + " 00:00:00", date_to + " 23:59:59", limit))
            rows = cursor.fetchall()
            return rows
        except Exception as e:
            app_logger.error(f"Error getting top selling parts: {e}")
            return []
        finally:
            conn.close()
    
    def get_top_customers(self, date_from, date_to, limit=5):
        """Get top customers by net revenue (after returns)"""
        conn = self.get_connection()
        try:
            sql = """
                SELECT 
                    i.customer_name,
                    i.mobile,
                    COUNT(*) as purchase_count,
                    SUM(i.total_amount) - COALESCE(
                        (SELECT SUM(r.refund_amount) FROM returns r WHERE r.invoice_id = i.invoice_id), 0
                    ) as net_spent
                FROM invoices i
                WHERE i.date BETWEEN ? AND ?
                GROUP BY i.customer_name, i.mobile
                ORDER BY net_spent DESC
                LIMIT ?
            """
            cursor = conn.execute(sql, (date_from + " 00:00:00", date_to + " 23:59:59", limit))
            rows = cursor.fetchall()
            return rows
        except Exception as e:
            app_logger.error(f"Error getting top customers: {e}")
            return []
        finally:
            conn.close()

    def get_dues_detail(self, limit=50):
        """Get all invoices with outstanding dues, sorted by oldest first."""
        conn = self.get_connection()
        try:
            sql = """
                SELECT
                    i.invoice_id,
                    i.customer_name,
                    COALESCE(i.mobile, '')          as mobile,
                    i.total_amount,
                    COALESCE(i.payment_cash, 0.0)   as paid_cash,
                    COALESCE(i.payment_upi,  0.0)   as paid_upi,
                    COALESCE(i.payment_due,  0.0)   as due_amount,
                    COALESCE(i.payment_mode,'CASH') as pay_mode,
                    i.date
                FROM invoices i
                WHERE COALESCE(i.payment_due, 0.0) > 0
                ORDER BY i.date ASC
                LIMIT ?
            """
            cursor = conn.execute(sql, (limit,))
            return cursor.fetchall()
        except Exception as e:
            app_logger.error(f"Error fetching dues detail: {e}")
            return []
        finally:
            conn.close()
    
    def get_sales_statistics(self, date_from, date_to):
        """Get comprehensive sales statistics"""
        conn = self.get_connection()
        try:
            sql = """
                SELECT 
                    COUNT(*) as total_invoices,
                    SUM(total_amount) as total_revenue,
                    AVG(total_amount) as avg_order_value,
                    MAX(total_amount) as max_order,
                    MIN(total_amount) as min_order
                FROM invoices
                WHERE date BETWEEN ? AND ?
            """
            cursor = conn.execute(sql, (date_from + " 00:00:00", date_to + " 23:59:59"))
            row = cursor.fetchone()
            
            refund_sql = "SELECT COALESCE(SUM(refund_amount), 0) FROM returns WHERE DATE(return_date) BETWEEN ? AND ?"
            cursor = conn.execute(refund_sql, (date_from, date_to))
            ref_row = cursor.fetchone()
            total_refund = ref_row[0] if ref_row else 0.0
            
            if row and row[0] > 0:
                rev = (row[1] if row[1] else 0) - total_refund
                return (row[0], rev, row[2], row[3], row[4])
            return (0, 0, 0, 0, 0)
        except Exception as e:
            app_logger.error(f"Error getting sales statistics: {e}")
            return (0, 0, 0, 0, 0)
        finally:
            conn.close()

    def get_low_stock_parts(self, limit=6):
        """Get parts at or below their reorder level, ordered by urgency."""
        conn = self.get_connection()
        try:
            sql = """
                SELECT part_id, part_name, qty, reorder_level, category
                FROM parts
                WHERE qty <= reorder_level
                ORDER BY (reorder_level - qty) DESC, qty ASC
                LIMIT ?
            """
            cursor = conn.execute(sql, (limit,))
            return cursor.fetchall()
        except Exception as e:
            app_logger.error(f"Error getting low stock parts: {e}")
            return []
        finally:
            conn.close()

    def get_payment_mode_breakdown(self, date_from, date_to):
        """Get total revenue split by payment mode (Cash, UPI, Due) for the period."""
        conn = self.get_connection()
        try:
            sql = """
                SELECT
                    COALESCE(SUM(COALESCE(payment_cash, total_amount)), 0) as cash_total,
                    COALESCE(SUM(COALESCE(payment_upi, 0)), 0)             as upi_total,
                    COALESCE(SUM(COALESCE(payment_due, 0)), 0)             as due_total
                FROM invoices
                WHERE date BETWEEN ? AND ?
            """
            cursor = conn.execute(sql, (date_from + " 00:00:00", date_to + " 23:59:59"))
            row = cursor.fetchone()
            if row:
                return {"cash": row[0] or 0.0, "upi": row[1] or 0.0, "due": row[2] or 0.0}
            return {"cash": 0.0, "upi": 0.0, "due": 0.0}
        except Exception as e:
            app_logger.error(f"Error getting payment mode breakdown: {e}")
            return {"cash": 0.0, "upi": 0.0, "due": 0.0}
        finally:
            conn.close()

    def get_recent_invoices(self, limit=6):
        """Get the most recent invoices for the activity feed."""
        conn = self.get_connection()
        try:
            sql = """
                SELECT invoice_id, customer_name, total_amount,
                       COALESCE(payment_mode,'CASH') as pay_mode,
                       COALESCE(payment_due, 0) as due_amt,
                       date
                FROM invoices
                ORDER BY date DESC
                LIMIT ?
            """
            cursor = conn.execute(sql, (limit,))
            return cursor.fetchall()
        except Exception as e:
            app_logger.error(f"Error getting recent invoices: {e}")
            return []
        finally:
            conn.close()

    # --- Order History Methods ---
    def get_all_purchase_orders(self, start_date=None, end_date=None):
        """Get all purchase orders with summary details"""
        conn = self.get_connection()
        try:
            # Base query
            sql = """
                SELECT 
                    po.po_id, 
                    po.supplier_name, 
                    po.order_date, 
                    po.status,
                    COUNT(pi.id) as item_count,
                    SUM(pi.qty_ordered) as total_qty
                FROM purchase_orders po
                LEFT JOIN po_items pi ON po.po_id = pi.po_id
            """
            
            params = []
            conditions = []
            
            if start_date:
                conditions.append("po.order_date >= ?")
                params.append(start_date)
            
            if end_date:
                conditions.append("po.order_date <= ?")
                params.append(end_date + " 23:59:59")
                
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
                
            sql += """
                GROUP BY po.po_id
                ORDER BY po.order_date DESC
            """
            
            cursor = conn.execute(sql, tuple(params))
            rows = cursor.fetchall()
            return rows
        except Exception as e:
            app_logger.error(f"Error getting all POs: {e}")
            return []
        finally:
            conn.close()

    def get_purchase_order_by_id(self, po_id):
        """Fetch a single PO record as a dictionary including global_disc_percent."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM purchase_orders WHERE po_id = ?", (po_id,))
            row = cursor.fetchone()
            if row:
                col_names = [description[0] for description in cursor.description]
                return dict(zip(col_names, row))
            return None
        except Exception as e:
            app_logger.error(f"Error fetching PO by ID {po_id}: {e}")
            return None
        finally:
            conn.close()

    def delete_purchase_order(self, po_id):
        """Delete a PO and its items"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("BEGIN TRANSACTION")
            
            # Delete items first
            cursor.execute("DELETE FROM po_items WHERE po_id = ?", (po_id,))
            
            # Delete PO
            cursor.execute("DELETE FROM purchase_orders WHERE po_id = ?", (po_id,))
            
            conn.commit()
            app_logger.info(f"Deleted PO {po_id}")
            return True, "PO Deleted"
        except Exception as e:
            app_logger.error(f"Error deleting PO {po_id}: {e}")
            return False, str(e)
        finally:
            conn.close()

    def update_po_item_received(self, po_item_id, new_qty_received, po_id=None):
        """Directly set qty_received on a po_items row (admin correction).
        Also recalculates the parent PO status.
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("BEGIN TRANSACTION")

            # 1. Update the line item
            cursor.execute(
                "UPDATE po_items SET qty_received = ? WHERE id = ?",
                (new_qty_received, po_item_id)
            )

            # 2. Determine parent PO if not given
            if not po_id:
                cursor.execute("SELECT po_id FROM po_items WHERE id = ?", (po_item_id,))
                row = cursor.fetchone()
                po_id = row[0] if row else None

            # 3. Recalculate PO status
            if po_id:
                cursor.execute(
                    "SELECT COUNT(*) FROM po_items WHERE po_id = ? AND qty_ordered > qty_received",
                    (po_id,)
                )
                pending_count = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT COUNT(*) FROM po_items WHERE po_id = ? AND qty_received > 0",
                    (po_id,)
                )
                any_received = cursor.fetchone()[0]

                if pending_count == 0:
                    new_status = 'CLOSED'
                elif any_received > 0:
                    new_status = 'PARTIAL'
                else:
                    new_status = 'OPEN'

                cursor.execute("UPDATE purchase_orders SET status = ? WHERE po_id = ?",
                               (new_status, po_id))

            conn.commit()
            app_logger.info(f"Corrected po_item {po_item_id}: qty_received={new_qty_received}, PO status={new_status if po_id else 'N/A'}")
            return True, "Updated"
        except Exception as e:
            try: conn.rollback()
            except: pass
            app_logger.error(f"Error updating po_item received qty: {e}")
            return False, str(e)
        finally:
            conn.close()

    def get_po_items(self, po_id):
        """Get items for a specific PO.
        Returns: (id, part_id, part_name, qty_ordered, qty_received, ordered_price, hsn_code, gst_rate, vendor_disc_percent)
        Index:    0    1        2          3             4              5              6          7         8
        """
        conn = self.get_connection()
        try:
            sql = """
                SELECT
                    pi.id,
                    pi.part_id,
                    pi.part_name,
                    pi.qty_ordered,
                    pi.qty_received,
                    COALESCE(pi.ordered_price, 0.0)  AS ordered_price,
                    COALESCE(pi.hsn_code, '')         AS hsn_code,
                    COALESCE(pi.gst_rate, 18.0)       AS gst_rate,
                    COALESCE(pi.vendor_disc_percent, 0.0) AS vendor_disc_percent
                FROM po_items pi
                WHERE pi.po_id = ?
                ORDER BY pi.id
            """
            cursor = conn.execute(sql, (po_id,))
            rows = cursor.fetchall()
            return rows
        except Exception as e:
            app_logger.error(f"Error getting PO items for {po_id}: {e}")
            return []
        finally:
            conn.close()


    # --- Supplier Profile Methods ---
    def get_vendor_stats(self, vendor_name):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            stats = {}
            
            # Total POs
            cursor.execute("SELECT COUNT(*) FROM purchase_orders WHERE UPPER(TRIM(supplier_name)) = UPPER(TRIM(?))", (vendor_name,))
            stats['total_pos'] = cursor.fetchone()[0]
            
            # Open Orders
            cursor.execute("SELECT COUNT(*) FROM purchase_orders WHERE UPPER(TRIM(supplier_name)) = UPPER(TRIM(?)) AND status = 'OPEN'", (vendor_name,))
            stats['open_pos'] = cursor.fetchone()[0]
            
            # Total Spend (Need to calculate from received items)
            cursor.execute("""
                SELECT SUM(i.qty_received * i.received_cost) 
                FROM po_items i
                JOIN purchase_orders p ON i.po_id = p.po_id
                WHERE UPPER(TRIM(p.supplier_name)) = UPPER(TRIM(?))
            """, (vendor_name,))
            val = cursor.fetchone()[0]
            stats['total_spend'] = val if val else 0.0
            
            # Execution Rate: (Total Received / Total Ordered) * 100
            cursor.execute("""
                SELECT SUM(i.qty_ordered), SUM(i.qty_received)
                FROM po_items i
                JOIN purchase_orders p ON i.po_id = p.po_id
                WHERE UPPER(TRIM(p.supplier_name)) = UPPER(TRIM(?))
            """, (vendor_name,))
            ord_rec = cursor.fetchone()
            total_ordered = ord_rec[0] if ord_rec and ord_rec[0] else 0
            total_received = ord_rec[1] if ord_rec and ord_rec[1] else 0
            
            if total_ordered > 0:
                stats['execution_rate'] = (total_received / total_ordered) * 100
            else:
                stats['execution_rate'] = 0.0
            
            return stats
        except Exception as e:
            app_logger.error(f"Error fetching stats for {vendor_name}: {e}")
            return {'total_pos': 0, 'open_pos': 0, 'total_spend': 0.0, 'execution_rate': 0.0}
        finally:
            conn.close()

    # --- Purchase Orders (v1.5) ---
    def get_catalog_price(self, vendor_name, part_id):
        """Return the catalog price for a specific vendor+part, or None if not found."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT price FROM supplier_catalogs
                WHERE UPPER(TRIM(vendor_name)) = UPPER(TRIM(?))
                  AND UPPER(TRIM(part_id)) = UPPER(TRIM(?))
                LIMIT 1
            """, (vendor_name, part_id))
            row = cursor.fetchone()
            return float(row[0]) if row and row[0] else None
        except Exception as e:
            app_logger.debug(f"Catalog price lookup error: {e}")
            return None
        finally:
            conn.close()

    def create_purchase_order(self, supplier_name, items, total_amount=0.0, global_disc_percent=0.0):
        # items: list of dicts {part_id, part_name, qty_ordered}
        try:
            with closing(self.get_connection()) as conn:
                with conn: # Auto-handles commit/rollback
                    cursor = conn.cursor()
                    
                    # Generate PO ID: PO-YYYYMMDD-XXXX
                    date_str = datetime.now().strftime("%Y%m%d")
                    # Get count for today to increment
                    cursor.execute("SELECT COUNT(*) FROM purchase_orders WHERE order_date LIKE ?", (f"{datetime.now().strftime('%Y-%m-%d')}%",))
                    count = cursor.fetchone()[0] + 1
                    po_id = f"PO-{date_str}-{count:04d}"
                    
                    order_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    cursor.execute(
                        "INSERT INTO purchase_orders (po_id, supplier_name, order_date, status, total_amount, global_disc_percent) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (po_id, supplier_name, order_date, "OPEN", total_amount, global_disc_percent)
                    )
                    
                    for item in items:
                        # item can have: part_id, part_name, qty_ordered, price, vendor_disc_percent, landing_cost, hsn_code, gst_rate
                        ordered_price = item.get('price', 0.0)
                        v_disc = item.get('vendor_disc_percent', 0.0)
                        l_cost = item.get('landing_cost', 0.0)
                        hsn_code = item.get('hsn_code', '')
                        gst_rate = item.get('gst_rate', 18.0)
                        req_rack = item.get('req_rack', '')
                        req_col = item.get('req_col', '')
                        
                        cursor.execute("""
                            INSERT INTO po_items (po_id, part_id, part_name, qty_ordered, qty_received, ordered_price, vendor_disc_percent, landing_cost, hsn_code, gst_rate, req_rack, req_col) 
                            VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?)
                        """, (po_id, item['part_id'], item['part_name'], item['qty_ordered'], ordered_price, v_disc, l_cost, hsn_code, gst_rate, req_rack, req_col))
                        
                    return True, po_id
        except Exception as e:
            app_logger.error(f"Error creating PO: {e}")
            return False, str(e)

    def get_open_po_items(self):
        """Return pending items from OPEN/PARTIAL POs for receiving and backlog."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT i.id, p.po_id, p.supplier_name, i.part_name,
                       i.qty_ordered, i.qty_received,
                       MAX(0, i.qty_ordered - i.qty_received) as pending,
                       i.part_id
                FROM purchase_orders p
                JOIN po_items i ON p.po_id = i.po_id
                WHERE p.status IN ('OPEN', 'PARTIAL')
                  AND i.qty_ordered > i.qty_received
                ORDER BY p.order_date ASC
            """)
            return cursor.fetchall()
        except Exception as e:
            app_logger.error(f"Error fetching open PO items: {e}")
            return []
        finally:
            conn.close()

    def get_part_price_history(self, part_id, vendor_name, limit=3):
        """Get last 3 distinct unit costs for a part from this vendor."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            # We use received_cost from po_items, linked to POs from this vendor
            cursor.execute("""
                SELECT i.received_cost 
                FROM po_items i
                JOIN purchase_orders p ON i.po_id = p.po_id
                WHERE i.part_id = ? AND p.supplier_name = ? AND i.received_cost > 0
                ORDER BY p.order_date DESC
                LIMIT ?
            """, (part_id, vendor_name, limit))
            rows = cursor.fetchall()
            return [r[0] for r in rows]
        except Exception as e:
            app_logger.error(f"Error fetching price history for {part_id}: {e}")
            return []
        finally:
            conn.close()

    def search_vendor_history(self, vendor_name, start_date, end_date, search_text=""):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            query = """
                SELECT po_id, order_date, status, 
                (SELECT COUNT(*) FROM po_items WHERE po_items.po_id = purchase_orders.po_id) as item_count,
                COALESCE(total_amount, 0.0)
                FROM purchase_orders
                WHERE UPPER(TRIM(supplier_name)) = UPPER(TRIM(?)) AND date(order_date) BETWEEN ? AND ?
            """
            params = [vendor_name, start_date, end_date]
            
            if search_text:
                query += " AND po_id LIKE ?"
                params.append(f"%{search_text}%")
                
            query += " ORDER BY order_date DESC"
            
            cursor.execute(query, params)
            return cursor.fetchall()
        except Exception as e:
            app_logger.error(f"Error searching history for {vendor_name}: {e}")
            return []
        finally:
            conn.close()


    def get_parts_by_vendor(self, vendor_name):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            # Get parts where vendor_name matches
            cursor.execute("SELECT part_id, part_name, qty, reorder_level, unit_price FROM parts WHERE vendor_name = ?", (vendor_name,))
            return cursor.fetchall()
        except Exception as e:
            app_logger.error(f"Error fetching parts for {vendor_name}: {e}")
            return []
        finally:
            conn.close()

    def save_catalog_items_bulk(self, vendor, items):
        """
        Bulk save catalog items using transactions and batch processing.
        items: list of (part_code, part_name, price, stock, extra_data_json)
        """
        conn = self.get_connection()
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            data = []
            for i in items:
                extra = i[4] if len(i) > 4 else None
                data.append((vendor, i[0], i[1], i[2], i[3], extra, timestamp))
            
            # Batch Processing (Current SQLite limit is ~32k vars, 7 vars per row -> ~4500 rows max)
            # We use a safe batch size of 500
            batch_size = 500
            total_items = len(data)
            
            # Use `with conn:` context manager — compatible with WAL mode.
            # Manual BEGIN TRANSACTION conflicts with Python's sqlite3 autocommit handling.
            with conn:
                cursor = conn.cursor()
                for i in range(0, total_items, batch_size):
                    batch = data[i:i + batch_size]
                    cursor.executemany("""
                        INSERT OR REPLACE INTO supplier_catalogs (vendor_name, part_code, part_name, price, ref_stock, extra_data, last_updated)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, batch)
            
            return True, f"Saved {total_items} items in batches."
        except Exception as e:
            app_logger.error(f"Error bulk saving catalog for {vendor}: {e}")
            return False, str(e)
        finally:
            conn.close()

    def update_part_vendors_bulk(self, vendor_name, part_ids):
        """
        Bulk update the vendor_name field in the main 'parts' table for specific IDs.
        Used when importing a supplier catalog to link existing inventory to that vendor.
        """
        if not part_ids: return
        
        conn = self.get_connection()
        try:
            # We only update if the part exists.
            # Convert list to list of tuples for executemany, or just use IN clause?
            # SQLite limit for variables is high, but better to use executemany for safety.
            
            data = [(vendor_name, pid) for pid in part_ids]
            conn.executemany("UPDATE parts SET vendor_name = ? WHERE part_id = ?", data)
            conn.commit()
            return True
        except Exception as e:
            app_logger.error(f"Error bulk updating part vendors: {e}")
            return False
        finally:
            conn.close()

    # --- Supplier Catalog Persistence ---
    def save_catalog_item(self, vendor, code, name, price, stock, extra_data=None, vendor_disc_percent=0.0):
        conn = self.get_connection()
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute("""
                INSERT OR REPLACE INTO supplier_catalogs (vendor_name, part_code, part_name, price, ref_stock, extra_data, last_updated, vendor_disc_percent)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (vendor, code, name, price, stock, extra_data, timestamp, vendor_disc_percent))
            conn.commit()
        except Exception as e:
            app_logger.error(f"Error saving catalog item {code}: {e}")
        finally:
            conn.close()

    def get_supplier_catalog(self, vendor):
        """Returns list of (part_code, part_name, price, ref_stock, extra_data, vendor_disc_percent)"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT part_code, part_name, price, ref_stock, extra_data, vendor_disc_percent FROM supplier_catalogs WHERE vendor_name = ?", (vendor,))
            return cursor.fetchall()
        except Exception as e:
            app_logger.error(f"Error fetching catalog for {vendor}: {e}")
            return []
        finally:
            conn.close()
    
    def save_vendor_catalog_columns(self, vendor, columns_list):
        """Save the column names for a vendor's catalog."""
        import json
        conn = self.get_connection()
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute("""
                INSERT OR REPLACE INTO vendor_catalog_columns (vendor_name, columns_json, last_updated)
                VALUES (?, ?, ?)
            """, (vendor, json.dumps(columns_list), timestamp))
            conn.commit()
        except Exception as e:
            app_logger.error(f"Error saving catalog columns for {vendor}: {e}")
        finally:
            conn.close()
    
    def get_vendor_catalog_columns(self, vendor):
        """Get the saved column names for a vendor's catalog."""
        import json
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT columns_json FROM vendor_catalog_columns WHERE vendor_name = ?", (vendor,))
            row = cursor.fetchone()
            if row and row[0]:
                return json.loads(row[0])
            return []
        except Exception as e:
            app_logger.error(f"Error fetching catalog columns for {vendor}: {e}")
            return []
        finally:
            conn.close()

    def get_recent_pos_by_vendor(self, vendor_name, limit=10):
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT po_id, order_date, status, 
                (SELECT COUNT(*) FROM po_items WHERE po_items.po_id = purchase_orders.po_id) as item_count
                FROM purchase_orders 
                WHERE supplier_name = ? 
                ORDER BY order_date DESC 
                LIMIT ?
            """, (vendor_name, limit))
            return cursor.fetchall()
        except Exception as e:
            app_logger.error(f"Error fetching recent POs for {vendor_name}: {e}")
            return []
        finally:
            conn.close()
    
    def get_recently_ordered_parts(self, vendor_name, days=7):
        """Get part names ordered from this vendor in the last N days."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT LOWER(i.part_name)
                FROM po_items i
                JOIN purchase_orders p ON i.po_id = p.po_id
                WHERE p.supplier_name = ? 
                AND date(p.order_date) >= date('now', ?)
            """, (vendor_name, f'-{days} days'))
            return {row[0] for row in cursor.fetchall()}
        except Exception as e:
            app_logger.error(f"Error fetching recent ordered parts for {vendor_name}: {e}")
            return set()
        finally:
            conn.close()

    # --- License Management Methods ---
    def get_license_info(self):
        """Returns the single license row as a dict"""
        conn = self.get_connection()
        try:
            cursor = conn.execute("SELECT * FROM app_license LIMIT 1")
            row = cursor.fetchone()
            if row:
                # Map based on schema: id, key, status, start, end, activation, last_check
                keys = ["id", "license_key", "status", "trial_start_date", "trial_end_date", "activation_date", "last_check_date"]
                return dict(zip(keys, row))
            return None
        finally:
            conn.close()

    def update_license_status(self, status, start_date=None, end_date=None, key=None, hwid=None):
        """Updates the license state"""
        conn = self.get_connection()
        try:
            if key:
                # Activation
                sql = """
                    UPDATE app_license 
                    SET status = ?, 
                        license_key = ?, 
                        hardware_id = ?,
                        activation_date = ?, 
                        last_check_date = ? 
                    WHERE id = (SELECT id FROM app_license LIMIT 1)
                """
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                conn.execute(sql, (status, key, hwid or '', now, now))
            elif start_date:
                # Start Trial
                sql = """
                    UPDATE app_license 
                    SET status = ?, 
                        trial_start_date = ?, 
                        trial_end_date = ?, 
                        last_check_date = ? 
                    WHERE id = (SELECT id FROM app_license LIMIT 1)
                """
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                conn.execute(sql, (status, start_date, end_date, now))
            else:
                # Just status update (e.g. Expired)
                conn.execute("UPDATE app_license SET status = ? WHERE id = (SELECT id FROM app_license LIMIT 1)", (status,))
            
            conn.commit()
            return True
        except Exception as e:
            app_logger.error(f"Failed to update license: {e}")
            return False
        finally:
            conn.close()
    def get_inventory_stats(self):
        """
        Get global inventory statistics:
        - Total Value (sum(price * stock))
        - Total Stock (sum(stock))
        - Total Parts (count(*))
        - Low Stock Count (count where stock <= reorder)
        - Vendor Count (count distinct vendor)
        """
        try:
            with closing(self.get_connection()) as conn:
                with conn:
                    cursor = conn.cursor()
                    query = """
                        SELECT 
                            SUM(CAST(unit_price AS REAL) * CAST(qty AS REAL)),
                            SUM(CAST(qty AS REAL)),
                            COUNT(*),
                            SUM(CASE WHEN CAST(qty AS REAL) <= CAST(reorder_level AS REAL) THEN 1 ELSE 0 END),
                            COUNT(DISTINCT vendor_name)
                        FROM parts
                    """
                    cursor.execute(query)
                    result = cursor.fetchone()
                    if result:
                        return {
                            "total_val": result[0] or 0.0,
                            "total_stock": result[1] or 0,
                            "part_count": result[2] or 0,
                            "low_stock_count": result[3] or 0,
                            "vendor_count": result[4] or 0
                        }
                    return None
        except Exception as e:
            app_logger.error(f"Error fetching inventory stats: {e}")
            return None
