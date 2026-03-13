from database_manager import DatabaseManager
import os
import time

# Use a test DB to avoid messing up production
TEST_DB = "test_inventory_repro.db"
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)

print("Initializing DB...")
db = DatabaseManager(TEST_DB)

# Create dummy data > 5000 items
items = []
print("Generating 9000 items...")
for i in range(9000):
    # (part_code, part_name, price, stock, extra_data_json)
    items.append((f"CODE-{i}", f"Part Name {i}", 10.50, 100, "{}"))

print("attempting bulk save...")
start_time = time.time()
success, msg = db.save_catalog_items_bulk("Test Vendor", items)
end_time = time.time()

print(f"Success: {success}")
print(f"Message: {msg}")
print(f"Time Taken: {end_time - start_time:.2f}s")
