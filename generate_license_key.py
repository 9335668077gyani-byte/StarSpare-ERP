"""
License Key Generator Utility
For SpareParts Pro ERP System

This utility allows administrators to generate valid license keys
for specific machines using their Hardware IDs.

Usage:
1. Get the Hardware ID from the target machine (shown in activation dialog)
2. Run this script and enter the HWID
3. Copy the generated license key and send it to the user
"""

from hardware_id import generate_license_key, get_hardware_id

def main():
    print("=" * 60)
    print(" SpareParts Pro - LICENSE KEY GENERATOR")
    print("=" * 60)
    print()
    
    # Option 1: Generate key for THIS machine
    print("Option 1: Generate key for THIS machine")
    local_hwid = get_hardware_id()
    print(f"   Hardware ID: {local_hwid}")
    local_key = generate_license_key(local_hwid)
    print(f"   License Key: {local_key}")
    print()
    
    # Option 2: Generate key for ANOTHER machine
    print("Option 2: Generate key for ANY machine")
    print("   Enter the Hardware ID from the target machine:")
    custom_hwid = input("   HWID: ").strip()
    
    if custom_hwid:
        custom_key = generate_license_key(custom_hwid)
        print()
        print(f"   Generated License Key: {custom_key}")
        print()
        print("   ✓ Send this key to the user for activation.")
    else:
        print("   No HWID entered.")
    
    print()
    print("=" * 60)
    input("Press Enter to exit...")

if __name__ == "__main__":
    main()
