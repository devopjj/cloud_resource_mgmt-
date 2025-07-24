from abc import ABC, abstractmethod
from typing import List
from core.models import ResourceItem
from core.context import CollectorContext
from core.models import ResourceItem

class BaseCollector(ABC):
    def __init__(self, context: CollectorContext):
        self.context = context

    def collect(self, context: "CollectContext") -> List[ResourceItem]:
        raise NotImplementedError
    
    @abstractmethod
    def collect(self) -> List[ResourceItem]:
        ...
