import hashlib
import uuid
import platform

def get_hardware_id():
    """
    Generate a unique hardware ID for this machine.
    Uses MAC address, CPU info, and system details.
    Returns a hash string (e.g., 'HWID-A1B2C3D4E5F6')
    """
    identifiers = []
    
    # 1. MAC Address (most reliable)
    try:
        mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) 
                        for elements in range(0, 2*6, 2)][::-1])
        identifiers.append(mac)
    except:
        identifiers.append("00:00:00:00:00:00")
    
    # 2. System Info
    identifiers.append(platform.system())      # Windows
    identifiers.append(platform.machine())     # AMD64
    identifiers.append(platform.processor())   # CPU name
    
    # 3. Computer Name
    try:
        identifiers.append(platform.node())
    except:
        pass
    
    # Combine and hash
    combined = "-".join(identifiers)
    hash_object = hashlib.sha256(combined.encode())
    hwid_hash = hash_object.hexdigest()[:16].upper()
    
    return f"HWID-{hwid_hash}"


def generate_license_key(hwid, secret="SPAREPARTS_PRO_2025"):
    """
    Generate a valid license key for a given Hardware ID.
    This is the KEY GENERATION function for admins.
    
    Args:
        hwid: Hardware ID string (e.g., 'HWID-A1B2C3D4E5F6')
        secret: Secret salt for key generation
    
    Returns:
        License key string (e.g., 'SPRO-XXXX-XXXX-XXXX-XXXX')
    """
    # Combine HWID + Secret and hash
    combined = f"{hwid}-{secret}"
    hash_object = hashlib.sha256(combined.encode())
    key_hash = hash_object.hexdigest()[:20].upper()
    
    # Format as: SPRO-XXXXX-XXXXX-XXXXX-XXXXX
    formatted_key = f"SPRO-{key_hash[0:5]}-{key_hash[5:10]}-{key_hash[10:15]}-{key_hash[15:20]}"
    return formatted_key


def verify_license_key(hwid, key, secret="SPAREPARTS_PRO_2025"):
    """
    Verify if a license key is valid for this Hardware ID.
    
    Args:
        hwid: Hardware ID string
        key: License key to verify
        secret: Secret salt (must match generation)
    
    Returns:
        bool: True if valid, False otherwise
    """
    expected_key = generate_license_key(hwid, secret)
    return key.strip().upper() == expected_key.strip().upper()


if __name__ == "__main__":
    # Test/Demo
    hwid = get_hardware_id()
    print(f"Hardware ID: {hwid}")
    
    key = generate_license_key(hwid)
    print(f"Generated License Key: {key}")
    
    # Verify
    is_valid = verify_license_key(hwid, key)
    print(f"Key Valid: {is_valid}")
    
    # Test invalid key
    fake_key = "SPRO-00000-00000-00000-00000"
    is_valid_fake = verify_license_key(hwid, fake_key)
    print(f"Fake Key Valid: {is_valid_fake}")
