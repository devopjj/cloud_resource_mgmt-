# collectors/aliyun/dns.py
from typing import List
from datetime import datetime
from core.base_collector import BaseCollector
from core.models import ResourceItem
from core.registry import register_collector
import json
import time

from aliyunsdkcore.client import AcsClient
from aliyunsdkalidns.request.v20150109.DescribeDomainsRequest import DescribeDomainsRequest
from aliyunsdkalidns.request.v20150109.DescribeDomainRecordsRequest import DescribeDomainRecordsRequest

@register_collector("aliyun_dns")
class AliyunDNSCollector(BaseCollector):
    def collect(self) -> List[ResourceItem]:
        access_key = self.context.config["credentials"]["access_key"]
        secret_key = self.context.config["credentials"]["secret_key"]

        region = self.context.region or "cn-hangzhou"

        client = AcsClient(access_key, secret_key, region)
        results = []

        # 1. 获取所有域名
        domains = []
        try:
            page = 1
            while True:
                req = DescribeDomainsRequest()
                req.set_PageNumber(page)
                req.set_PageSize(100)
                resp = client.do_action_with_exception(req)
                data = json.loads(resp)
                items = data.get("Domains", {}).get("Domain", [])
                if not items:
                    break
                domains.extend(items)
                if page * 100 >= data.get("TotalCount", 0):
                    break
                page += 1
        except Exception as e:
            print(f"[!] Aliyun list domains failed: {e}")
            return []

        # 2. 遍历每个域名取解析记录
        for idx, d in enumerate(domains, 1):
            domain_name = d.get("DomainName")
            domain_id = d.get("DomainId")

            # 注册域名
            results.append(ResourceItem(
                provider="aliyun",
                account_id=self.context.account_id,
                region="global",
                resource_type="registered_domain",
                resource_id=domain_name,
                name=domain_name,
                status=None,
                zone=None,
                tags={},
                metadata=d,
                fetched_at=datetime.now()
            ))

            # 记录集
            try:
                page = 1
                while True:
                    req = DescribeDomainRecordsRequest()
                    req.set_DomainName(domain_name)
                    req.set_PageNumber(page)
                    req.set_PageSize(100)
                    resp = client.do_action_with_exception(req)
                    data = json.loads(resp)
                    records = data.get("DomainRecords", {}).get("Record", [])
                    if not records:
                        break

                    for rec in records:
                        rr_name = rec["RR"]
                        rr_type = rec["Type"]
                        rr_value = rec["Value"]
                        rr_status = rec["Status"]

                        results.append(ResourceItem(
                            provider="aliyun",
                            account_id=self.context.account_id,
                            region="global",
                            resource_type="dns_record",
                            resource_id=f"{domain_id}:{rr_name}:{rr_type}",
                            name=rr_name,
                            status="normal" if rr_status == "ENABLE" else "disabled",
                            zone=domain_name,
                            tags={},
                            metadata=rec,
                            fetched_at=datetime.now()
                        ))

                    if page * 100 >= data.get("TotalCount", 0):
                        break
                    page += 1
                    time.sleep(0.1)
            except Exception as e:
                print(f"[!] Aliyun DNS record list failed for domain {domain_name}: {e}")

        return results
