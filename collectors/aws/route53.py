import boto3
from typing import List
from core.base_collector import BaseCollector
from core.models import ResourceItem
from core.registry import register_collector

@register_collector("aws_route53")
class AWSRoute53Collector(BaseCollector):
    def collect(self) -> List[ResourceItem]:
        session = boto3.Session(profile_name=self.context.profile,
                                region_name=self.context.region or "us-east-1")
        route53 = session.client("route53")
        domain_client = session.client("route53domains")

        results = []

        # 1. 已注册域名
        try:
            domains = domain_client.list_domains().get("Domains", [])
            for d in domains:
                results.append(ResourceItem(
                    provider="aws",
                    account=self.context.account,
                    region="global",
                    resource_type="registered_domain",
                    id=d["DomainName"],
                    name=d["DomainName"],
                    metadata=d,
                    raw=d
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
                    account=self.context.account,
                    region="global",
                    resource_type="route53_zone",
                    id=zone_id,
                    name=z["Name"],
                    metadata=z,
                    raw=z
                ))
        except Exception as e:
            print(f"[!] Hosted zones list failed: {e}")

        return results
