#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
File    : resolvers/dns_resolver.py
Function: 解析指定 domain，返回实际解析结果（支援 region 模拟、记录描述）
Author  : Jimmy
Email   : devopjj@gmail.com
Created : 2025-08-05 , 23:50
Modified: 2025-08-05 , 23:50
Version: 1.0
"""

import dns.resolver
import uuid
from datetime import datetime
from typing import List, Dict


def resolve_dns(domain: str, region: str = "global", record_type: str = "A", description: str = "") -> Dict:
    """
    解析指定 domain，返回真实记录
    """
    result = {
        "id": str(uuid.uuid4()),
        "domain_name": domain,
        "region": region,
        "record_type": record_type,
        "resolved_data": [],
        "description": description,
        "resolved_at": datetime.utcnow().isoformat()
    }

    # 可扩展不同 region 使用不同 DNS server 模拟智能解析
    dns_servers = {
        "global": ["8.8.8.8"],
        "cn": ["223.5.5.5"],
        "tw": ["168.95.1.1"],
        "us-west": ["1.1.1.1"],
        "jp": ["8.8.4.4"],
    }

    resolver = dns.resolver.Resolver()
    resolver.timeout = 3
    resolver.lifetime = 5

    resolver.nameservers = dns_servers.get(region, dns_servers["global"])

    try:
        answers = resolver.resolve(domain, record_type)
        result["resolved_data"] = [r.to_text() for r in answers]
    except Exception as e:
        result["description"] += f" (resolve error: {e})"

    return result


# ✅ 快速测试（可移除）
if __name__ == "__main__":
    data = resolve_dns("example.com", region="tw", record_type="A", description="Test resolve")
    print(data)
