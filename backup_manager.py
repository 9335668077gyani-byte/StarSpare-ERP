import sqlite3
import shutil
import os
from datetime import datetime
from logger import app_logger

class BackupManager:
    """Auto-Backup system for database protection (Quick Win #3)"""
    
    def __init__(self, db_path):
        self.db_path = db_path
        self.backup_dir = os.path.join(os.path.dirname(db_path), "data", "backups")
        
        # Create backup directory if it doesn't exist
        if not os.path.exists(self.backup_dir):
            try:
                os.makedirs(self.backup_dir)
                app_logger.info(f"Created backup directory: {self.backup_dir}")
            except OSError as e:
                app_logger.error(f"Failed to create backup directory: {e}")
    
    def create_backup(self, cloud_path=None):
        """Create a backup of the database, optionally sync to cloud"""
        try:
            if not os.path.exists(self.db_path):
                app_logger.error(f"Database file not found: {self.db_path}")
                return False, "Database file not found"
            
            # Generate backup filename with timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            backup_filename = f"backup_{timestamp}.db"
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            # Copy database file to local backup
            shutil.copy2(self.db_path, backup_path)
            
            # Cleanup old local backups (keep last 7)
            self.cleanup_old_backups()
            
            message = f"Backup created: {backup_filename}"
            app_logger.info(f"Backup created successfully: {backup_filename}")
            
            # Optional: Sync to cloud
            if cloud_path:
                cloud_success, cloud_msg = self.create_cloud_backup(cloud_path, backup_filename)
                if cloud_success:
                    message += f" → Cloud synced ☁️"
                else:
                    message += f" (Cloud sync failed: {cloud_msg})"
            
            return True, message
            
        except Exception as e:
            app_logger.error(f"Backup failed: {e}")
            return False, f"Backup failed: {str(e)}"
    
    def cleanup_old_backups(self, keep_count=7):
        """Remove old backups, keeping only the last 'keep_count' backups"""
        try:
            # Get all backup files
            backups = []
            for f in os.listdir(self.backup_dir):
                if f.startswith("backup_") and f.endswith(".db"):
                    full_path = os.path.join(self.backup_dir, f)
                    backups.append((full_path, os.path.getmtime(full_path)))
            
            # Sort by modification time (newest first)
            backups.sort(key=lambda x: x[1], reverse=True)
            
            # Delete old backups
            for backup_path, _ in backups[keep_count:]:
                try:
                    os.remove(backup_path)
                    app_logger.info(f"Removed old backup: {os.path.basename(backup_path)}")
                except Exception as e:
                    app_logger.error(f"Failed to delete old backup {backup_path}: {e}")
                    
        except Exception as e:
            app_logger.error(f"Cleanup failed: {e}")
    
    def get_backups(self):
        """Get list of all available backups"""
        try:
            backups = []
            if not os.path.exists(self.backup_dir):
                return backups
                
            for f in os.listdir(self.backup_dir):
                if f.startswith("backup_") and f.endswith(".db"):
                    full_path = os.path.join(self.backup_dir, f)
                    size = os.path.getsize(full_path)
                    mtime = datetime.fromtimestamp(os.path.getmtime(full_path))
                    backups.append({
                        "filename": f,
                        "path": full_path,
                        "size": size,
                        "date": mtime.strftime("%Y-%m-%d %H:%M:%S")
                    })
            
            # Sort by date (newest first)
            backups.sort(key=lambda x: x["date"], reverse=True)
            return backups
            
        except Exception as e:
            app_logger.error(f"Failed to get backups list: {e}")
            return []
    
    def restore_backup(self, backup_filename):
        """Restore database from a backup file"""
        try:
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            if not os.path.exists(backup_path):
                app_logger.error(f"Backup file not found: {backup_filename}")
                return False, "Backup file not found"
            
            # Create a backup of current database before restoring
            current_backup = f"pre_restore_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.db"
            current_backup_path = os.path.join(self.backup_dir, current_backup)
            shutil.copy2(self.db_path, current_backup_path)
            app_logger.info(f"Created safety backup: {current_backup}")
            
            # Restore from backup
            shutil.copy2(backup_path, self.db_path)
            
            app_logger.info(f"Database restored from: {backup_filename}")
            return True, f"Database restored successfully from {backup_filename}"
            
        except Exception as e:
            app_logger.error(f"Restore failed: {e}")
            return False, f"Restore failed: {str(e)}"
    
    # ========== CLOUD BACKUP FEATURES ==========
    
    def set_cloud_backup_path(self, path):
        """Set and validate cloud backup location"""
        try:
            if not path or path.strip() == "":
                return False, "Path cannot be empty"
            
            # Normalize path
            normalized_path = os.path.normpath(path)
            
            # Create directory if it doesn't exist
            if not os.path.exists(normalized_path):
                try:
                    os.makedirs(normalized_path)
                    app_logger.info(f"Created cloud backup directory: {normalized_path}")
                except Exception as e:
                    app_logger.error(f"Failed to create cloud directory: {e}")
                    return False, f"Cannot create directory: {str(e)}"
            
            # Test write permission
            test_file = os.path.join(normalized_path, ".spareparts_test")
            try:
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
            except Exception as e:
                app_logger.error(f"No write permission in cloud path: {e}")
                return False, "No write permission in selected folder"
            
            app_logger.info(f"Cloud backup path validated: {normalized_path}")
            return True, normalized_path
            
        except Exception as e:
            app_logger.error(f"Cloud path validation failed: {e}")
            return False, str(e)
    
    def create_cloud_backup(self, cloud_path, backup_filename):
        """Copy backup to cloud folder"""
        try:
            if not cloud_path or not os.path.exists(cloud_path):
                return False, "Cloud path not configured or doesn't exist"
            
            source_path = os.path.join(self.backup_dir, backup_filename)
            if not os.path.exists(source_path):
                return False, f"Backup file not found: {backup_filename}"
            
            dest_path = os.path.join(cloud_path, backup_filename)
            
            # Copy to cloud folder
            shutil.copy2(source_path, dest_path)
            
            app_logger.info(f"Cloud backup created: {dest_path}")
            return True, f"Synced to cloud: {backup_filename}"
            
        except Exception as e:
            app_logger.error(f"Cloud backup failed: {e}")
            return False, f"Cloud sync failed: {str(e)}"
    
    def get_cloud_backup_status(self, cloud_path):
        """Check if cloud path is valid and accessible"""
        try:
            if not cloud_path or cloud_path.strip() == "":
                return False, "Not configured", None
            
            if not os.path.exists(cloud_path):
                return False, "Folder doesn't exist", None
            
            if not os.path.isdir(cloud_path):
                return False, "Not a valid folder", None
            
            # Check write permission
            test_file = os.path.join(cloud_path, ".test")
            try:
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
                
                # Count backups in cloud folder
                cloud_backups = [f for f in os.listdir(cloud_path) 
                                if f.startswith("backup_") and f.endswith(".db")]
                count = len(cloud_backups)
                
                return True, f"{count} backups in cloud", cloud_path
                
            except Exception as e:
                return False, "No write permission", None
                
        except Exception as e:
            app_logger.error(f"Cloud status check failed: {e}")
            return False, str(e), None
