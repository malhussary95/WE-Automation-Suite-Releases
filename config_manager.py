"""
Central Configuration Manager for all automation tools
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "launcher_config.json"
TOOLS_CONFIG = BASE_DIR / "tools_config.json"


class ConfigManager:
    def __init__(self):
        self._config: Dict[str, Any] = {}
        self._tools_config: Dict[str, Any] = {}
        self.load()
    
    def load(self):
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                self._config = json.load(f)
        else:
            self._config = self._default_config()
            
        if TOOLS_CONFIG.exists():
            with open(TOOLS_CONFIG, "r", encoding="utf-8") as f:
                self._tools_config = json.load(f)
    
    def save(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)
    
    def _default_config(self) -> Dict:
        return {
            "theme": "Light",
            "geometry": "1200x800",
            "favorites": [],
            "auto_check_deps": True,
            "last_used_tool": None,
            "log_level": "INFO"
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any):
        self._config[key] = value
        self.save()
    
    def get_tool_config(self, tool_id: str) -> Dict[str, Any]:
        return self._tools_config.get(tool_id, {})
    
    def set_tool_config(self, tool_id: str, data: Dict[str, Any]):
        self._tools_config[tool_id] = {**self._tools_config.get(tool_id, {}), **data}
        with open(TOOLS_CONFIG, "w", encoding="utf-8") as f:
            json.dump(self._tools_config, f, indent=2, ensure_ascii=False)


# Global instance
config = ConfigManager()