import logging
import os
import sys

# ── Resolve log directory via path_utils ──────────────────────────────────────
# path_utils is safe to import here; it has no app-level dependencies.
from path_utils import get_app_data_path  # type: ignore

LOG_DIR = get_app_data_path("logs")
LOG_FILE = os.path.join(LOG_DIR, "app.log")


# ── Redirect stdout / stderr to log file (critical for --windowed .exe) ───────
# In PyInstaller --windowed mode there is no console.  Any bare print() or
# library that writes to stdout/stderr can trigger an IOError and silently
# crash the process.  We redirect both streams to the log file instead.
if getattr(sys, "frozen", False):
    try:
        _log_stream = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
        sys.stdout = _log_stream  # type: ignore[assignment]
        sys.stderr = _log_stream  # type: ignore[assignment]
    except OSError:
        pass  # If we can't open the file, leave streams as-is


# ── Logger factory ─────────────────────────────────────────────────────────────
def setup_logger(name: str = __name__) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        # File handler — always active
        try:
            fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
            fh.setFormatter(
                logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            )
            logger.addHandler(fh)
        except OSError:
            pass  # Nowhere to write; better than crashing

        # Console handler — only when NOT frozen (dev mode)
        if not getattr(sys, "frozen", False):
            ch = logging.StreamHandler(sys.stdout)
            ch.setFormatter(
                logging.Formatter("%(name)s - %(levelname)s - %(message)s")
            )
            logger.addHandler(ch)

    return logger


# Global instance
app_logger = setup_logger("SpareERP")
