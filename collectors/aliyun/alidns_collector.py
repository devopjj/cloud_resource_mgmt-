# collectors/aliyun/alidns_collector.py
# -*- coding: utf-8 -*-
from typing import List, Dict, Any, Callable, Optional
from core.pipeline import process_resources

def collect_dns_records(
    alidns_client,
    domain_name: str,
    account_id: Optional[str],
    upsert_callback: Optional[Callable[[Dict[str, Any]], None]] = None
) -> List[Dict[str, Any]]:
    """
    采集阿里云 AliDNS 某域名全部记录。
    """
    # 伪代码：根据你的 Alicloud SDK 调整
    # AliDNS 通常需要分页：PageNumber / PageSize
    records: List[Dict[str, Any]] = []
    page = 1
    while True:
        resp = alidns_client.describe_domain_records(
            DomainName=domain_name,
            PageNumber=page,
            PageSize=500
        )
        # 常见结构：{"DomainRecords": {"Record": [ ... ]}, "TotalCount": N, "PageNumber": x, "PageSize": y}
        batch = (resp.get("DomainRecords", {}) or {}).get("Record", [])
        records.extend(batch)
        total = resp.get("TotalCount") or len(records)
        if page * 500 >= total or not batch:
            break
        page += 1

    return process_resources(
        provider="aliyun",
        resource_type="dns_record",
        records=records,
        upsert_callback=upsert_callback,
        account_id=account_id,
        zone_id=None,          # AliDNS 不一定有 zone_id 概念
        zone_name=domain_name, # 用域名作为 zone_name
        status="active",
        region=None,
    )
