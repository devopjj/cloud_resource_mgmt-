# core/pipeline.py
# -*- coding: utf-8 -*-
from typing import Callable, List, Dict, Any, Optional
from core.meta_normalizer import normalize_meta

def process_resources(
    provider: str,
    resource_type: str,
    records: List[dict],
    upsert_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    **ctx
) -> List[Dict[str, Any]]:
    """
    将原始 records 归一化为 cloud_resource item，并可选执行 upsert（应包含去重与 diff log）。
    ctx 可包含：account_id/region/status/tags/zone_id/zone_name/created_at/updated_at ...
    """
    items = []
    for rec in records:
        meta = normalize_meta(provider, resource_type, rec, **ctx)
        item = {
            "provider": provider,
            "account_id": ctx.get("account_id"),
            "resource_type": resource_type,
            "resource_name": meta.get("resource_name"),
            "resource_id": meta.get("resource_id"),
            "region": meta.get("region"),
            "status": meta.get("status"),
            "resource_metadata": meta,
        }
        if upsert_callback:
            upsert_callback(item)
        items.append(item)
    return items
