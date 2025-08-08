# collectors/cloudflare/dns_collector.py
# -*- coding: utf-8 -*-
from typing import List, Dict, Any, Callable, Optional
from core.resource_pipeline import process_resources

def _ensure_zone_name(cf_client, zone_id: str, zone_name: Optional[str]) -> str:
    if zone_name:
        return zone_name
    # 适配常见 Python Cloudflare SDK：/zones/:id
    resp = cf_client.zones.get(zone_id=zone_id)
    # 有的 SDK 是 resp["result"]["name"]，也见过 resp["name"]
    return (resp.get("result") or {}).get("name") or resp.get("name")

def collect_dns_records(
    cf_client,
    zone_id: str,
    zone_name: Optional[str],
    account_id: Optional[str],
    upsert_callback: Optional[Callable[[Dict[str, Any]], None]] = None
) -> List[Dict[str, Any]]:
    zone_name = _ensure_zone_name(cf_client, zone_id, zone_name)

    records: List[Dict[str, Any]] = []
    page = 1
    while True:
        resp = cf_client.zones.dns_records.get(zone_id=zone_id, page=page, per_page=100)
        result = resp.get("result", [])
        records.extend(result)
        info = resp.get("result_info") or {}
        if not info or info.get("page") >= info.get("total_pages", 1):
            break
        page += 1

    return process_resources(
        provider="cloudflare",
        resource_type="dns_record",
        records=records,
        upsert_callback=upsert_callback,
        account_id=account_id,
        zone_id=zone_id,
        zone_name=zone_name,   # <- 关键
        status="active",
        region=None,
    )
