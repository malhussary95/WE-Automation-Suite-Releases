import json
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Any
from pathlib import Path

# إعداد نظام التسجيل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class Resource:
    """تمثيل احترافي لمورد تقني في النظام."""
    identifier: str
    name: str
    status: str
    component_code: int
    raw_data: dict = field(repr=False)

    @classmethod
    def from_json(cls, data: dict) -> 'Resource':
        return cls(
            identifier=data.get("te_resourceidentifier", "N/A"),
            name=data.get("te_name", "Unknown"),
            status=data.get("statuscode@OData.Community.Display.V1.FormattedValue", "Unknown"),
            component_code=data.get("te_resourcecomponentcode", 0),
            raw_data=data
        )

class ResourceLibrary:
    """مدير الموارد للتعامل مع ملفات JSON الضخمة."""
    def __init__(self, file_path: str):
        self.path = Path(file_path)
        self.data = self._load_file()

    def _load_file(self) -> List[Any]:
        try:
            with open(self.path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load resources from {self.path}: {e}")
            return []

    def get_active_resources(self) -> List[Resource]:
        """استخراج الموارد النشطة فقط بطريقة احترافية."""
        if not isinstance(self.data, list):
            logger.warning("Data format is not a list, cannot parse resources.")
            return []
            
        return [
            Resource.from_json(res)
            for line in self.data
            for res in line.get("resources", [])
            if res.get("statuscode") == 1
        ]

if __name__ == "__main__":
    # مثال للاستخدام
    handler = ResourceLibrary(r"d:\My Project\Automation\ECRM\RR_DEBUG\6051100\IB_RESOURCES_DEBUG.json")
    active = handler.get_active_resources()
    
    print(f"Found {len(active)} active resources:")
    for r in active:
        print(f"ID: {r.identifier} | Name: {r.name}")