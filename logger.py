import logging
import os
import sys

# Create logs directory if it doesn't exist
# Create logs directory if it doesn't exist
if getattr(sys, 'frozen', False):
    # Running as compiled app - Prefer APPDATA then Home
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    app_data_dir = os.path.join(base, "SparePartsPro_v1.5")
    LOG_DIR = os.path.join(app_data_dir, "logs")
else:
    LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

if not os.path.exists(LOG_DIR):
    try:
        os.makedirs(LOG_DIR)
    except OSError:
        pass # Fallback or silent fail

LOG_FILE = os.path.join(LOG_DIR, "app.log")

def setup_logger(name=__name__):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        # File Handler
        file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        # Console Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    return logger

# Global instance for quick access
app_logger = setup_logger("SpareERP")
