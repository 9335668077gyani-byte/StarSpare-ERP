from datetime import datetime, timedelta
from logger import app_logger

class LicenseVerifier:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.master_key = "PRO-ADMIN-2025"
        self.trial_days = 15
        
    def check_license(self):
        """
        Returns:
        - ('NEW', None): No license, fresh install
        - ('TRIAL', days_left): Active trial
        - ('EXPIRED', 0): Trial expired
        - ('ACTIVE', None): Fully activated
        """
        info = self.db_manager.get_license_info()
        if not info:
            return 'NEW', None
            
        status = info['status']
        
        if status == 'ACTIVE':
            return 'ACTIVE', None
            
        if status == 'TRIAL':
            try:
                end_date = datetime.strptime(info['trial_end_date'], "%Y-%m-%d %H:%M:%S")
                now = datetime.now()
                
                if now > end_date:
                    self.db_manager.update_license_status('EXPIRED')
                    return 'EXPIRED', 0
                else:
                    days_left = (end_date - now).days
                    return 'TRIAL', days_left
            except Exception as e:
                app_logger.error(f"Date parsing error: {e}")
                return 'EXPIRED', 0 # Fail safe
                
        return status, 0
        
    def start_trial(self):
        now = datetime.now()
        end_date = now + timedelta(days=self.trial_days)
        
        start_str = now.strftime("%Y-%m-%d %H:%M:%S")
        end_str = end_date.strftime("%Y-%m-%d %H:%M:%S")
        
        if self.db_manager.update_license_status('TRIAL', start_date=start_str, end_date=end_str):
            app_logger.info(f"Trial started. Expires on {end_str}")
            return True
        return False
        
    def activate_license(self, key):
        if key.strip() == self.master_key:
            if self.db_manager.update_license_status('ACTIVE', key=key):
                app_logger.info("License activated successfully.")
                return True
        else:
            app_logger.warning(f"Invalid license attempt: {key}")
            
        return False
    
    def verify_license(self, hwid, key):
        """Verify hardware-locked license key"""
        from hardware_id import verify_license_key
        return verify_license_key(hwid, key)
    
    def save_license(self, key, hwid):
        """Save activated hardware-locked license"""
        if self.db_manager.update_license_status('ACTIVE', key=key, hwid=hwid):
            app_logger.info(f"Hardware-locked license activated for {hwid}")
            return True
        return False
