# collectors/aws/route53_collector.py
# -*- coding: utf-8 -*-
from typing import List, Dict, Any, Callable, Optional
from core.pipeline import process_resources

def collect_dns_records(
    route53_client,
    hosted_zone_id: str,
    zone_name: str,
    account_id: Optional[str],
    upsert_callback: Optional[Callable[[Dict[str, Any]], None]] = None
) -> List[Dict[str, Any]]:
    """
    采集 AWS Route53 某个 Hosted Zone 的全部记录并入库（按需）。
    """
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
        zone_name=zone_name,
        status="active",
        region=None,  # DNS 无 region
    )
