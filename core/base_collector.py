from abc import ABC, abstractmethod
from typing import List
from core.models import ResourceItem
from core.context import CollectorContext

class BaseCollector(ABC):
    def __init__(self, context: CollectorContext):
        self.context = context

    @abstractmethod
    def collect(self) -> List[ResourceItem]:
        ...
