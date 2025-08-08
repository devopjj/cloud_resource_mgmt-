# collectors/aws/ecs_collector.py  （注意：AWS 里的 ECS 你可能指 EC2）
from typing import List, Dict, Any, Callable, Optional
from core.pipeline import process_resources

def collect_ec2_instances(
    ec2_client,
    account_id: Optional[str],
    region: Optional[str],
    upsert_callback: Optional[Callable[[Dict[str, Any]], None]] = None
) -> List[Dict[str, Any]]:
    # resp = ec2_client.describe_instances()
    # reservations = resp.get("Reservations", [])
    instances: List[Dict[str, Any]] = []
    paginator = ec2_client.get_paginator("describe_instances")
    for page in paginator.paginate():
        for res in page.get("Reservations", []):
            instances.extend(res.get("Instances", []))
    return process_resources(
        provider="aws",
        resource_type="ecs",   # 你如果更喜欢 "ec2" 也行，但要和 NORMALIZERS 对齐
        records=instances,
        upsert_callback=upsert_callback,
        account_id=account_id,
        region=region,
        status=None
    )
