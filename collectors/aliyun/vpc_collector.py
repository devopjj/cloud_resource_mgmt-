# collectors/aliyun/vpc_collector.py
from typing import List, Dict, Any, Callable, Optional
from core.pipeline import process_resources

def collect_vpcs(
    vpc_client,
    account_id: Optional[str],
    region: Optional[str],
    upsert_callback: Optional[Callable[[Dict[str, Any]], None]] = None
) -> List[Dict[str, Any]]:
    # resp = vpc_client.describe_vpcs(RegionId=region)
    # vpcs = resp.get("Vpcs", {}).get("Vpc", [])
    vpcs = (vpc_client.describe_vpcs(RegionId=region).get("Vpcs", {}) or {}).get("Vpc", [])
    return process_resources(
        provider="aliyun",
        resource_type="vpc",
        records=vpcs,
        upsert_callback=upsert_callback,
        account_id=account_id,
        region=region,
        status="Available"
    )
