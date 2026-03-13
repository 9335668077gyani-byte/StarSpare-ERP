"""
Network Database Configuration Module
Manages Server/Client mode for multi-computer shared database.
Config stored locally in data/network_config.json (per machine).
"""
import json
import os
import sys
import socket
from logger import app_logger


def _get_app_data_dir():
    """Consolidated logic to get the writable app data directory."""
    if getattr(sys, 'frozen', False):
        # In frozen mode, ALWAYS prefer APPDATA or User Home. 
        # Never fall back to _MEIPASS (dirname of __file__) for writing.
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, "SparePartsPro_v1.5")
    return os.path.dirname(os.path.abspath(__file__))

def _get_config_path():
    """Get path to network_config.json (always local, never shared)."""
    app_data_dir = _get_app_data_dir()
    
    data_dir = os.path.join(app_data_dir, "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)
    
    return os.path.join(data_dir, "network_config.json")


def config_exists():
    """Check if network_config.json exists."""
    return os.path.exists(_get_config_path())


def load_config():
    """Load network config. Returns dict or None if not configured."""
    path = _get_config_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        app_logger.error(f"Error loading network config: {e}")
        return None


def save_config(mode, server_ip="", share_name="SparePartsDB"):
    """
    Save network config.
    mode: "SERVER" or "CLIENT"
    server_ip: IP or computer name (for CLIENT mode)
    share_name: Shared folder name (default: SparePartsDB)
    """
    config = {
        "mode": mode,
        "server_ip": server_ip,
        "share_name": share_name
    }
    path = _get_config_path()
    try:
        with open(path, 'w') as f:
            json.dump(config, f, indent=2)
        app_logger.info(f"Network config saved: mode={mode}, server={server_ip}")
        return True
    except Exception as e:
        app_logger.error(f"Error saving network config: {e}")
        return False


def get_local_ip():
    """Get this machine's LAN IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_computer_name():
    """Get this machine's Windows computer name."""
    return socket.gethostname()


def get_db_path():
    """
    Get the database path based on network config.
    - SERVER/LOCAL: Uses local data/spareparts_pro.db
    - CLIENT: Uses \\\\server_ip\\share_name\\spareparts_pro.db
    """
    config = load_config()
    
    # Default local path
    app_data_dir = _get_app_data_dir()
    local_path = os.path.join(app_data_dir, "data", "spareparts_pro.db")
    
    if not config:
        return local_path
    
    mode = config.get("mode", "SERVER")
    
    if mode == "SERVER":
        return local_path
    
    elif mode == "CLIENT":
        server_ip = config.get("server_ip", "")
        share_name = config.get("share_name", "SparePartsDB")
        if server_ip:
            network_path = f"\\\\{server_ip}\\{share_name}\\spareparts_pro.db"
            return network_path
        else:
            app_logger.warning("CLIENT mode but no server_ip configured, falling back to local.")
            return local_path
    
    return local_path


def test_connection(server_ip, share_name="SparePartsDB"):
    """
    Test if the network path is reachable and writable.
    Returns (success: bool, message: str)
    """
    network_path = f"\\\\{server_ip}\\{share_name}"
    db_path = os.path.join(network_path, "spareparts_pro.db")
    
    try:
        # Check if path is accessible
        if os.path.exists(network_path):
            # Check if DB file exists
            if os.path.exists(db_path):
                return True, f"Connected! Database found at {db_path}"
            else:
                # Folder accessible but no DB yet — that's OK for first setup
                return True, f"Network folder accessible. Database will be created on first use."
        else:
            return False, f"Cannot access: {network_path}\nMake sure the folder is shared and accessible."
    except PermissionError:
        return False, f"Permission denied: {network_path}\nCheck sharing permissions."
    except Exception as e:
        return False, f"Connection failed: {str(e)}"


def get_share_path():
    """Get the local data folder path that should be shared (for SERVER mode)."""
    return os.path.join(_get_app_data_dir(), "data")
