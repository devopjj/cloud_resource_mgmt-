# collectors/aws/dns.py

from typing import List
from datetime import datetime
from core.base_collector import BaseCollector
from core.models import ResourceItem
from core.registry import register_collector
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from tqdm import tqdm
from jjutils.Tools import (
    LoggerSetup,
    q
)

# 設置日誌
logger = LoggerSetup(caller_file='aws_dns', log_dir="log", quiet_mode=False).get_logger()

@register_collector("aws_dns")
class AWSRoute53Collector(BaseCollector):
    def collect(self) -> List[ResourceItem]:
        results = []
        try:
            session = boto3.Session(
                profile_name=self.context.profile,
                region_name="us-east-1"
            )
            route53 = session.client("route53")
            domain_client = session.client("route53domains")
        except Exception as e:
            logger.exception("[!] Failed to initialize AWS session")
            return results

        # 1. 已注册域名
        try:
            domains = domain_client.list_domains().get("Domains", [])
            logger.info(f"[aws_dns] Found {len(domains)} registered domains")

            for d in domains:
                results.append(ResourceItem(
                    provider="aws",
                    account_id=self.context.account_id,
                    region="global",
                    resource_type="registered_domain",
                    resource_id=d["DomainName"],
                    name=d["DomainName"],
                    status=None,
                    zone=None,
                    tags={},
                    metadata=d,
                    fetched_at=datetime.now()
                ))
        except (BotoCoreError, ClientError, Exception) as e:
            logger.exception("[!] Route53Domains list failed")

        # 2. 托管区域
        zones = []
        try:
            zones = route53.list_hosted_zones().get("HostedZones", [])
            logger.info(f"[aws_dns] Found {len(zones)} hosted zones")

            for z in zones:
                zone_id = z["Id"].split("/")[-1]
                results.append(ResourceItem(
                    provider="aws",
                    account_id=self.context.account_id,
                    region="global",
                    resource_type="route53_zone",
                    resource_id=zone_id,
                    name=z["Name"],
                    status=None,
                    zone=None,
                    tags={},
                    metadata=z,
                    fetched_at=datetime.now()
                ))
        except (BotoCoreError, ClientError, Exception) as e:
            logger.exception("[!] Hosted zones list failed")

        # 3. 各托管区的 DNS 解析记录
        for z in tqdm(zones, desc="[aws_dns] Fetching DNS records"):
            try:
                zone_id = z["Id"].split("/")[-1]
                zone_name = z["Name"]

                paginator = route53.get_paginator("list_resource_record_sets")
                record_sets_iter = paginator.paginate(HostedZoneId=zone_id)

                for page in record_sets_iter:
                    for rr in page.get("ResourceRecordSets", []):
                        rr_type = rr.get("Type")
                        rr_name = rr.get("Name")
                        rr_ttl = rr.get("TTL", None)
                        rr_values = [
                            r.get("Value") for r in rr.get("ResourceRecords", [])
                        ] if "ResourceRecords" in rr else []
                        rr_status = "alias" if "AliasTarget" in rr else "normal"

                        results.append(ResourceItem(
                            provider="aws",
                            account_id=self.context.account_id,
                            region="global",
                            resource_type="dns_record",
                            resource_id=f"{zone_id}:{rr_name}:{rr_type}",
                            name=rr_name,
                            status=rr_status,
                            zone=zone_id,
                            tags={},
                            metadata={
                                "type": rr_type,
                                "ttl": rr_ttl,
                                "value": rr_values,
                                **rr
                            },
                            fetched_at=datetime.now()
                        ))
            except (BotoCoreError, ClientError, Exception) as e:
                logger.exception(f"[!] DNS record list failed for zone {z.get('Id')}")

        logger.info(f"[aws_dns] Total resources collected: {len(results)}")
        return results
