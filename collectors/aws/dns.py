# collectors/aws/route53.py
from typing import List
from datetime import datetime
from core.base_collector import BaseCollector
from core.models import ResourceItem
from core.registry import register_collector
import boto3
import os
@register_collector("aws_dns")
class AWSRoute53Collector(BaseCollector):
    def collect(self) -> List[ResourceItem]:
        session = boto3.Session(profile_name=self.context.profile,
                                region_name="us-east-1")
        route53 = session.client("route53")
        domain_client = session.client("route53domains")

        results = []

        # 1. 已注册域名
        try:
            domains = domain_client.list_domains().get("Domains", [])

            for d in domains:
                results.append(ResourceItem(
                    provider="aws",
                    account_id=self.context.account_id,
                    region="global",  # AWS全球区域
                    resource_type="registered_domain",
                    resource_id=d["DomainName"],  # 使用DomainName作为resource_id
                    name=d["DomainName"],
                    status=None,  # 如果没有状态字段，可以设为None
                    zone=None,    # 如果没有zone字段，可以设为None
                    tags={},      # 如果没有tags字段，可以用空字典
                    metadata=d,   # 将整个字典d作为metadata存储
                    fetched_at=datetime.now()  # 设置当前时间为fetched_at
                ))
        except Exception as e:
            print(f"[!] Route53Domains list failed: {e}")
        
        # 2. 托管区域与记录集
        try:
            zones = route53.list_hosted_zones().get("HostedZones", [])
            for z in zones:
                zone_id = z["Id"].split("/")[-1]
                results.append(ResourceItem(
                    provider="aws",
                    account_id=self.context.account_id,
                    region="global",  # AWS全球区域
                    resource_type="route53_zone",
                    resource_id=zone_id,  # 使用DomainName作为resource_id
                    name=z["Name"],
                    status=None,  # 如果没有状态字段，可以设为None
                    zone=None,    # 如果没有zone字段，可以设为None
                    tags={},      # 如果没有tags字段，可以用空字典
                    metadata=z,   # 将整个字典d作为metadata存储
                    fetched_at=datetime.now()  # 设置当前时间为fetched_at
                ))
        except Exception as e:
            print(f"[!] Hosted zones list failed: {e}")
        
        # 3. 各托管区的 DNS 解析记录（dns_record）
        try:
            for z in zones:
                zone_id = z["Id"].split("/")[-1]
                zone_name = z["Name"]

                paginator = route53.get_paginator("list_resource_record_sets")
                record_sets_iter = paginator.paginate(HostedZoneId=zone_id)

                for page in record_sets_iter:
                    for rr in page.get("ResourceRecordSets", []):
                        rr_type = rr.get("Type")
                        rr_name = rr.get("Name")
                        rr_ttl = rr.get("TTL", None)
                        rr_values = [r.get("Value") for r in rr.get("ResourceRecords", [])] if "ResourceRecords" in rr else []
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
        except Exception as e:
            print(f"[!] DNS record list failed for zone {zone_id}: {e}")
        
        return results
