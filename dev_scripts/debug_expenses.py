import sys
import os
from datetime import datetime, timedelta

# Add current dir to path
sys.path.append(os.getcwd())

from database_manager import DatabaseManager

def test_daily_expenses():
    db = DatabaseManager('spareparts.db')
    print("Testing get_daily_expenses...")
    try:
        data = db.get_daily_expenses(7)
        print(f"Result: {data}")
        
        if not data:
            print("returned empty list")
        else:
            print(f"Count: {len(data)}")
            
        # Check raw query
        conn = db.get_connection()
        cursor = conn.cursor()
        print("Raw dump of expenses (last 10):")
        cursor.execute("SELECT * FROM expenses ORDER BY id DESC LIMIT 10")
        for r in cursor.fetchall():
            print(r)
            
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_daily_expenses()
