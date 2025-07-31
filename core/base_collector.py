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