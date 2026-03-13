import os
from database_manager import DatabaseManager
import pandas as pd

# Create dummy db
db = DatabaseManager('test_import.db')

# Create a test Excel file
data = {
    'Part ID': ['PART-001', 'PART-002'],
    'Description': ['Spark Plug', 'Brake Pad'],
    'Stock': [10, 20],
    'MRP': [150.0, 450.0]
}
df = pd.DataFrame(data)
df.to_excel('test_excel_import.xlsx', index=False)
df.to_csv('test_csv_import.csv', index=False, sep=';') # Semicolon separated

print("Testing Excel Import...")
success, msg = db.smart_import_csv('test_excel_import.xlsx')
print(f"Excel Success: {success}, Msg: {msg}")

print("Testing CSV (Semicolon) Import...")
success, msg = db.smart_import_csv('test_csv_import.csv')
print(f"CSV Success: {success}, Msg: {msg}")

# Let's see what got imported
print("Parts in DB:", db.get_all_parts())

# Cleanup
if os.path.exists('test_import.db'): os.remove('test_import.db')
if os.path.exists('test_excel_import.xlsx'): os.remove('test_excel_import.xlsx')
if os.path.exists('test_csv_import.csv'): os.remove('test_csv_import.csv')
