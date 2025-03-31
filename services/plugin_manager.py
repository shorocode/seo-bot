from typing import Dict, Type
import importlib
from pathlib import Path
from config import settings
import logging

logger = logging.getLogger(__name__)

class PluginManager:
    """سیستم مدیریت پلاگین‌های پویا"""
    
    def __init__(self):
        self.plugins: Dict[str, Type] = {}
        self.plugins_dir = Path(settings.PLUGINS_DIR)
        
    def load_plugins(self):
        """بارگذاری تمام پلاگین‌ها از دایرکتوری"""
        for plugin_file in self.plugins_dir.glob("*.py"):
            try:
                module_name = f"plugins.{plugin_file.stem}"
                module = importlib.import_module(module_name)
                self.plugins[plugin_file.stem] = module.Plugin
            except Exception as e:
                logger.error(f"Failed to load plugin {plugin_file}: {str(e)}")

    def get_plugin(self, name: str):
        """دریافت نمونه پلاگین"""
        return self.plugins.get(name)

# نمونه Singleton
plugin_manager = PluginManager()
