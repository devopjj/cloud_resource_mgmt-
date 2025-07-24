# collectors/aliyun/dns.py
from core.base_collector import BaseCollector
from core.registry import register_collector

@register_collector("aliyun_dns")
class DummyAliyunRoute53Collector(BaseCollector):
    def collect(self):
        print("[Aliyun] dummy collector for aliyun_dns")
        return []
