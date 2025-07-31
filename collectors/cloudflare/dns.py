# collectors/cloudflare/dns.py
import os
from typing import List
from datetime import datetime
from core.base_collector import BaseCollector
from core.models import ResourceItem
from core.registry import register_collector
import CloudFlare

@register_collector("cloudflare_dns")
class CloudflareDNSCollector(BaseCollector):
    def collect(self) -> List[ResourceItem]:
        cf = CloudFlare.CloudFlare(token=os.environ.get("CLOUDFLARE_API_TOKEN"))
        results = []

        try:
            page = 1
            per_page = 50
            zone_count = 0

            while True:
                zones = cf.zones.get(params={"page": page, "per_page": per_page})
                if not zones:
                    break

                for z in zones:
                    zone_id = z["id"]
                    zone_name = z["name"]

                    # registered_domain
                    results.append(ResourceItem(
                        provider="cloudflare",
                        account_id=self.context.account_id,
                        region="global",
                        resource_type="registered_domain",
                        resource_id=zone_name,
                        name=zone_name,
                        status=None,
                        zone=None,
                        tags={},
                        metadata=z,
                        fetched_at=datetime.now()
                    ))

                    # dns_zone
                    results.append(ResourceItem(
                        provider="cloudflare",
                        account_id=self.context.account_id,
                        region="global",
                        resource_type="dns_zone",
                        resource_id=zone_id,
                        name=zone_name,
                        status=None,
                        zone=None,
                        tags={},
                        metadata=z,
                        fetched_at=datetime.now()
                    ))

                    # DNS records
                    rr_page = 1
                    while True:
                        rr = cf.zones.dns_records.get(
                            zone_id,
                            params={"page": rr_page, "per_page": 100}
                        )
                        if not rr:
                            break

                        for r in rr:
                            record_id = r["id"]
                            record_name = r["name"]
                            record_type = r["type"]
                            record_value = r.get("content")
                            record_ttl = r.get("ttl")
                            record_status = "proxied" if r.get("proxied", False) else "normal"

                            results.append(ResourceItem(
                                provider="cloudflare",
                                account_id=self.context.account_id,
                                region="global",
                                resource_type="dns_record",
                                resource_id=f"{zone_id}:{record_id}",
                                name=record_name,
                                status=record_status,
                                zone=zone_id,
                                tags={},
                                metadata={
                                    "type": record_type,
                                    "ttl": record_ttl,
                                    "value": record_value,
                                    **r
                                },
                                fetched_at=datetime.now()
                            ))

                        if len(rr) < 100:
                            break
                        rr_page += 1

                if len(zones) < per_page:
                    break
                page += 1

        except Exception as e:
            print(f"[!] Cloudflare DNS collection failed: {e}")

        return results
