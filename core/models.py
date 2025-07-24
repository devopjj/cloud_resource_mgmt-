from pydantic import BaseModel
from typing import Optional, Dict, Any

class ResourceItem(BaseModel):
    provider: str
    account: str
    region: Optional[str]
    resource_type: str
    id: str
    name: Optional[str]
    tags: Dict[str, str] = {}
    metadata: Dict[str, Any] = {}
    raw: Optional[dict] = None
