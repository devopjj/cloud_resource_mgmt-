from typing import Dict, Type
from core.base_collector import BaseCollector

COLLECTOR_REGISTRY: Dict[str, Type[BaseCollector]] = {}

def register_collector(name: str):
    def decorator(cls):
        COLLECTOR_REGISTRY[name] = cls
        return cls
    return decorator
