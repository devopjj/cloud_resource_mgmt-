# collectors/aws/vpc_collector.py
from typing import List, Dict, Any, Callable, Optional
from core.pipeline import process_resources

def collect_vpcs(
    ec2_client,
    account_id: Optional[str],
    region: Optional[str],
    upsert_callback: Optional[Callable[[Dict[str, Any]], None]] = None
) -> List[Dict[str, Any]]:
    # resp = ec2_client.describe_vpcs()
    # vpcs = resp.get("Vpcs", [])
    vpcs: List[Dict[str, Any]] = ec2_client.describe_vpcs().get("Vpcs", [])
    return process_resources(
        provider="aws",
        resource_type="vpc",
        records=vpcs,
        upsert_callback=upsert_callback,
        account_id=account_id,
        region=region,
        status="available"
    )
