import sys
import os
import db_config

with open(r"c:\Users\Admin\Desktop\live_debug.txt", "w") as f:
    f.write(f"frozen: {getattr(sys, 'frozen', False)}\n")
    f.write(f"db_path: {db_config.get_db_path()}\n")
    f.write(f"app_data_dir: {db_config._get_app_data_dir()}\n")
