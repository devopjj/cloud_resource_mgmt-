#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
File    : resolve_all_domains.py
Function: 批次解析 cloud_resource 中所有域名，写入 resolved_dns_record 表
Author  : Jimmy
Email   : devopjj@gmail.com
Created : 2025-08-05 , 23:51
Modified: 2025-08-06 , 00:05
Version: 1.1
"""

import json
from core.database import setup_database, get_session
from core import models
from resolvers.dns_resolver import resolve_dns
import os

DB_NAME = "cloud_resources"
MYSQL_URL = f"mysql+mysqlconnector://dbuser:12345@10.11.11.62:3306/{DB_NAME}?charset=utf8mb4"
DB_URL = os.getenv("DB_URL", MYSQL_URL)

def main():
    engine = setup_database(DB_URL)
    session = get_session()

    rows = session.query(models.CloudResource).filter(models.CloudResource.domain_name.isnot(None)).all()
    print(f"[+] 共发现 {len(rows)} 个域名，准备解析并写入解析结果…")

    for r in rows:
        try:
            res = resolve_dns(r.domain_name, region=r.region or "global", description="batch resolve")
            record = models.ResolvedDnsRecord(
                id=res["id"],
                cloud_resource_id=r.id,
                domain_name=res["domain_name"],
                region=res["region"],
                record_type=res["record_type"],
                resolved_data=json.dumps(res["resolved_data"], ensure_ascii=False),
                description=res["description"],
                resolved_at=res["resolved_at"]
            )
            session.add(record)
            print(f"  - {r.domain_name} [{res['region']}] => {res['resolved_data']}")
        except Exception as e:
            print(f"[!] 无法解析 {r.domain_name}: {e}")
            continue

    session.commit()
    print("[+] 所有解析结果已写入 resolved_dns_record")


if __name__ == "__main__":
    main()
