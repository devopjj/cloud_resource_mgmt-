# collectors/aliyun/dns.py
from core.base_collector import BaseCollector
from core.registry import register_collector

@register_collector("cloudflare_dns")
class DummyAliyunRoute53Collector(BaseCollector):
    def collect(self):
        print("[Cloudflare] dummy collector for dns")
        return []
