# collectors/aws/route53_collector.py
# -*- coding: utf-8 -*-
from typing import List, Dict, Any, Callable, Optional
from core.resource_pipeline import process_resources

def _rstrip_dot(s: Optional[str]) -> Optional[str]:
    return s[:-1] if isinstance(s, str) and s.endswith(".") else s

def _ensure_zone_name(route53_client, hosted_zone_id: str, zone_name: Optional[str]) -> str:
    if zone_name:
        return _rstrip_dot(zone_name)
    resp = route53_client.get_hosted_zone(Id=hosted_zone_id)
    # HostedZone.Name 通常带一个结尾的点
    return _rstrip_dot(resp.get("HostedZone", {}).get("Name"))

def collect_dns_records(
    route53_client,
    hosted_zone_id: str,
    zone_name: Optional[str],
    account_id: Optional[str],
    upsert_callback: Optional[Callable[[Dict[str, Any]], None]] = None
) -> List[Dict[str, Any]]:
    zone_name = _ensure_zone_name(route53_client, hosted_zone_id, zone_name)

    paginator = route53_client.get_paginator("list_resource_record_sets")
    all_records: List[Dict[str, Any]] = []
    for page in paginator.paginate(HostedZoneId=hosted_zone_id):
        all_records.extend(page.get("ResourceRecordSets", []))

    return process_resources(
        provider="aws",
        resource_type="dns_record",
        records=all_records,
        upsert_callback=upsert_callback,
        account_id=account_id,
        zone_id=hosted_zone_id,
        zone_name=zone_name,   # <- 关键：传给 normalizer
        status="active",
        region=None,
    )
