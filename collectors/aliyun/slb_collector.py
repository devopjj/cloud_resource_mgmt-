# collectors/aliyun/slb_collector.py
from typing import List, Dict, Any, Callable, Optional
from core.pipeline import process_resources

def collect_load_balancers(
    slb_client,
    account_id: Optional[str],
    region: Optional[str],
    upsert_callback: Optional[Callable[[Dict[str, Any]], None]] = None
) -> List[Dict[str, Any]]:
    # resp = slb_client.describe_load_balancers(RegionId=region, PageSize=100)
    # lbs = resp.get("LoadBalancers", {}).get("LoadBalancer", [])
    lbs: List[Dict[str, Any]] = []
    page = 1
    while True:
        resp = slb_client.describe_load_balancers(RegionId=region, PageNumber=page, PageSize=100)
        batch = (resp.get("LoadBalancers", {}) or {}).get("LoadBalancer", [])
        lbs.extend(batch)
        total = resp.get("TotalCount") or len(lbs)
        if page * 100 >= total or not batch:
            break
        page += 1

    return process_resources(
        provider="aliyun",
        resource_type="slb",
        records=lbs,
        upsert_callback=upsert_callback,
        account_id=account_id,
        region=region,
    )
