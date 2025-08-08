# collectors/aws/slb_collector.py   （ELB/ALB/NLB 你按需拆分）
from typing import List, Dict, Any, Callable, Optional
from core.pipeline import process_resources

def collect_load_balancers(
    elb_client,
    account_id: Optional[str],
    region: Optional[str],
    upsert_callback: Optional[Callable[[Dict[str, Any]], None]] = None
) -> List[Dict[str, Any]]:
    # resp = elb_client.describe_load_balancers()
    # lbs = resp.get("LoadBalancerDescriptions", [])
    lbs: List[Dict[str, Any]] = elb_client.describe_load_balancers().get("LoadBalancerDescriptions", [])
    return process_resources(
        provider="aws",
        resource_type="slb",
        records=lbs,
        upsert_callback=upsert_callback,
        account_id=account_id,
        region=region,
    )
