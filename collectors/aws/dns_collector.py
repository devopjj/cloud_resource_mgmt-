# collectors/cloudflare/dns_collector.py
# -*- coding: utf-8 -*-
from typing import List, Dict, Any, Callable, Optional
from core.pipeline import process_resources

def collect_dns_records(
    cf_client,
    zone_id: str,
    zone_name: str,
    account_id: Optional[str],
    upsert_callback: Optional[Callable[[Dict[str, Any]], None]] = None
) -> List[Dict[str, Any]]:
    """
    采集 Cloudflare 区域的全部 DNS 记录。
    cf_client: 需有类似 cf.zones.dns_records.get/list 的方法；按你的 SDK 调整。
    """
    # 伪代码：根据你使用的 Cloudflare SDK 调整
    # resp = cf_client.zones.dns_records.get(zone_id=zone_id, per_page=100, page=1)
    # 做分页聚合...
    records: List[Dict[str, Any]] = []
    page = 1
    while True:
        resp = cf_client.zones.dns_records.get(zone_id=zone_id, page=page, per_page=100)
        result = resp.get("result", [])
        records.extend(result)
        if not resp.get("result_info") or resp["result_info"].get("page") >= resp["result_info"].get("total_pages", 1):
            break
        page += 1

    # Cloudflare 的记录本身带 zone_id（少数 SDK 不带），zone_name 从 ctx 传
    return process_resources(
        provider="cloudflare",
        resource_type="dns_record",
        records=records,
        upsert_callback=upsert_callback,
        account_id=account_id,
        zone_id=zone_id,
        zone_name=zone_name,
        status="active",
        region=None,
    )
