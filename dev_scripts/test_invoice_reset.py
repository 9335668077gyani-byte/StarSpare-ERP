import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from database_manager import DatabaseManager

def test_reset():
    db_path = "data/spareparts_pro.db"
    if not os.path.exists(db_path):
        print(f"Error: DB not found at {db_path}")
        return

    db = DatabaseManager(db_path)
    
    print("\n--- TEST: Invoice Sequence ---")
    
    # 1. Get initial state
    seq = db.get_setting("invoice_sequence")
    print(f"Initial Sequence: {seq}")
    
    # 2. Generate ID
    inv_id = db.get_next_invoice_id()
    print(f"Generated ID: {inv_id}")
    
    # 3. Check increment
    seq_after = db.get_setting("invoice_sequence")
    print(f"Sequence After: {seq_after}")
    
    if seq_after and (not seq or int(seq_after) > int(seq)):
        print("✅ Increment Successful")
    else:
        print("❌ Increment Failed")
        
    # 4. Test Reset
    print("\n--- TEST: Reset to 8888 ---")
    db.set_invoice_sequence(8888)
    seq_reset = db.get_setting("invoice_sequence")
    print(f"Sequence after Reset: {seq_reset}")
    
    if int(seq_reset) == 8888:
        print("✅ Reset Successful")
    else:
        print(f"❌ Reset Failed (Got {seq_reset})")
        
    # 5. Generate with new sequence
    inv_id_new = db.get_next_invoice_id()
    print(f"Generated ID (Should be INV-8888): {inv_id_new}")
    
    if inv_id_new == "INV-8888":
        print("✅ ID Generation Successful")
    else:
        print(f"❌ ID Generation Failed (Got {inv_id_new})")
        
    # Restore (Optional, or leave it)
    print("\nTests Complete.")

if __name__ == "__main__":
    test_reset()
