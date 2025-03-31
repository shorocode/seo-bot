import yaml
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime, timedelta
from pydantic import BaseModel
from config import settings
import logging

logger = logging.getLogger(__name__)

class FeatureToggle(BaseModel):
    """مدل مدیریت ویژگی‌های پویا"""
    name: str
    enabled: bool
    rollout_percentage: float = 100.0
    allowed_users: List[int] = []

class DynamicConfig:
    """مدیریت پیکربندی پویا با قابلیت ریلود خودکار"""
    
    def __init__(self):
        self.config_path = Path(settings.CONFIG_DIR) / "dynamic_config.yaml"
        self.last_modified = 0
        self.config_data: Dict[str, Any] = {}
        self.features: Dict[str, FeatureToggle] = {}
        self.load_config()

    def load_config(self):
        """بارگذاری یا به‌روزرسانی پیکربندی"""
        try:
            current_modified = self.config_path.stat().st_mtime
            if current_modified > self.last_modified:
                with open(self.config_path, 'r') as f:
                    self.config_data = yaml.safe_load(f) or {}
                self._parse_features()
                self.last_modified = current_modified
        except Exception as e:
            logger.error(f"Failed to load config: {str(e)}")

    def _parse_features(self):
        """تبدیل داده‌های خام به مدل FeatureToggle"""
        self.features = {
            name: FeatureToggle(**data)
            for name, data in self.config_data.get("features", {}).items()
        }

    def is_feature_enabled(
        self,
        feature_name: str,
        user_id: Optional[int] = None
    ) -> bool:
        """بررسی فعال بودن یک ویژگی"""
        self.load_config()  # ریلود خودکار اگر فایل تغییر کرده باشد
        
        feature = self.features.get(feature_name)
        if not feature:
            return False
            
        if not feature.enabled:
            return False
            
        if user_id and user_id in feature.allowed_users:
            return True
            
        return feature.rollout_percentage >= 100 or (
            user_id and (user_id % 100) < feature.rollout_percentage
        )

# نمونه Singleton
dynamic_config = DynamicConfig()
