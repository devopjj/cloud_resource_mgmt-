from abc import ABC, abstractmethod
from typing import List
from core.models import ResourceItem
from core.context import CollectorContext
from core.models import ResourceItem, CloudResource

class BaseCollector(ABC):
    def __init__(self, context: CollectorContext):
        self.context = context

    def collect(self, context: "CollectContext") -> List[ResourceItem]:
        raise NotImplementedError

    def resolve_real_records(self, item, region: str):
        """
        可选择性覆写：取得该 resource 的真实解析
        item: ResourceItem
        region: 可模拟来自某区域的查询
        """
        return []
        
    @abstractmethod
    def collect(self) -> List[ResourceItem]:
        ...
def diff_fields(old: CloudResource, new: CloudResource) -> dict:
    changes = {}
    for field in ["name", "status", "domain_name", "ip_addresses", "tags"]:
        if getattr(old, field) != getattr(new, field):
            changes[field] = {
                "old": getattr(old, field),
                "new": getattr(new, field)
            }
    return changes
