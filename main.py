# main.py
# -*- coding: utf-8 -*-
"""
tp501 / cloud_resource_mgmt
方案B：使用“直连新管道”跑 DNS 采集（normalize_meta + resource_pipeline）
- 自动从 config/accounts.yaml 读取账户与凭证
- AWS: boto3 列举所有 Hosted Zones -> run_dns_collect_aws
- Cloudflare: 用 REST 列举所有 Zones -> run_dns_collect_cloudflare
- AliDNS: 若 collectors/aliyun/alidns_collector.py 已接好 SDK，则遍历配置的 domains 调用 run_dns_collect_alidns
"""

import os
import sys
import uuid
import json
from datetime import datetime
from typing import Optional, Dict, Any, List

from utils.config_loader import load_accounts_config
from core.database import setup_database, get_session
from core import models
from core.db_writer import insert_if_not_exists_or_log_diff

# ---------------- DB 初始化 ----------------
DB_NAME = "cloud_resources"
MYSQL_URL = f"mysql+mysqlconnector://dbuser:12345@10.11.11.62:3306/{DB_NAME}?charset=utf8mb4"
SQLITE_URL = "sqlite:///CLOUD_ASSETS.db"
POSTGRESQL_URL = "postgresql+psycopg2://username:password@localhost:5432/cloud_resources"
DB_URL = os.getenv("DB_URL", MYSQL_URL)
engine = setup_database(DB_URL)

# ---------------- 直连入口（已封装 normalize + pipeline） ----------------
try:
    from collectors.aws.route53_collector import collect_dns_records as _aws_collect_dns
except Exception:
    _aws_collect_dns = None

try:
    from collectors.cloudflare.dns_collector import collect_dns_records as _cf_collect_dns
except Exception:
    _cf_collect_dns = None

try:
    from collectors.aliyun.alidns_collector import collect_dns_records as _ali_collect_dns
except Exception:
    _ali_collect_dns = None


# ---------------- 公共：CloudAccount / CloudResource 映射 & upsert ----------------
def _ensure_cloud_account(session, provider: str, account_id: Optional[str], name_hint: Optional[str]) -> models.CloudAccount:
    acct = (
        session.query(models.CloudAccount)
        .filter_by(provider=provider, account_id=account_id)
        .first()
    )
    if acct:
        return acct
    acct = models.CloudAccount(
        id=str(uuid.uuid4()),
        name=name_hint or (account_id or f"{provider}-acct"),
        provider=models.CloudProvider(provider),
        account_id=account_id,
    )
    session.add(acct)
    session.flush()
    return acct


def _dict_to_cloud_resource(session, item: Dict[str, Any]) -> models.CloudResource:
    """
    将直连采集器返回的 item(dict) 转为 ORM CloudResource，并挂上 cloud_account_id。
    期望字段（由 core/resource_pipeline.py 产出）：
      provider, account_id, resource_type, resource_id, region, status,
      name, zone, domain_name, vpc_id?, ip_addresses?, tags, resource_metadata
    """
    acct = _ensure_cloud_account(session, item.get("provider"), item.get("account_id"), None)
    rid = item.get("resource_id")
    if not rid:
        raise ValueError("resource_id 不能为空（直连入口请确保已通过 pipeline 合成）")

    obj = models.CloudResource(
        id=str(uuid.uuid4()),
        cloud_account_id=acct.id,
        resource_type=item.get("resource_type"),
        resource_id=rid,
        region=item.get("region"),
        provider=item.get("provider"),
        zone=item.get("zone"),
        name=item.get("name"),
        status=item.get("status"),
        domain_name=item.get("domain_name"),
        vpc_id=item.get("vpc_id"),
        ip_addresses=item.get("ip_addresses"),
        tags=item.get("tags"),
        resource_metadata=item.get("resource_metadata"),
        fetched_at=datetime.utcnow(),
    )
    return obj


def _default_upsert(item: Dict[str, Any]) -> None:
    sess = get_session()
    try:
        obj = _dict_to_cloud_resource(sess, item)
        insert_if_not_exists_or_log_diff(sess, obj)
        sess.commit()
    except Exception as e:
        sess.rollback()
        print(f"[!] default upsert 失败: {e}", file=sys.stderr)
    finally:
        try:
            sess.close()
        except Exception:
            pass


# ---------------- AWS: 直连 ----------------
def _aws_boto3_client(service: str, profile: Optional[str] = None, region: Optional[str] = None):
    try:
        import boto3
    except Exception as e:
        raise RuntimeError("需要 boto3，请先安装：pip install boto3") from e
    if profile:
        import botocore
        try:
            session = boto3.Session(profile_name=profile, region_name=region)
        except Exception as e:
            raise RuntimeError(f"AWS Profile 无法使用：{profile}: {e}") from e
    else:
        session = boto3.Session(region_name=region)
    return session.client(service)


def _aws_list_zones(route53_client) -> List[Dict[str, str]]:
    """返回 [{'id': 'Zxxxxx', 'name': 'example.com'}]"""
    zones = []
    marker = None
    while True:
        kw = {}
        if marker:
            kw["Marker"] = marker
        resp = route53_client.list_hosted_zones(**kw)
        for z in resp.get("HostedZones", []):
            zid = z.get("Id", "").split("/")[-1]
            name = (z.get("Name") or "").rstrip(".")
            zones.append({"id": zid, "name": name})
        if resp.get("IsTruncated"):
            marker = resp.get("NextMarker")
        else:
            break
    return zones


def run_dns_collect_aws(route53_client, hosted_zone_id: str, zone_name: str,
                        account_id: Optional[str] = None, upsert=None) -> List[Dict[str, Any]]:
    if _aws_collect_dns is None:
        raise RuntimeError("collectors.aws.route53_collector 未就绪")
    return _aws_collect_dns(route53_client, hosted_zone_id, zone_name, account_id, upsert or _default_upsert)


# ---------------- Cloudflare: 直连（REST 轻量封装） ----------------
class _CFZonesDNSRecords:
    def __init__(self, token: str):
        self.token = token

    def get(self, zone_id: str, page: int, per_page: int) -> Dict[str, Any]:
        import requests
        url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
        headers = {"Authorization": f"Bearer {self.token}"}
        params = {"page": page, "per_page": per_page}
        r = requests.get(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        return r.json()


class _CFZones:
    def __init__(self, token: str):
        self.token = token
        self.dns_records = _CFZonesDNSRecords(token)

    def list(self) -> List[Dict[str, Any]]:
        import requests
        out = []
        page = 1
        while True:
            url = "https://api.cloudflare.com/client/v4/zones"
            headers = {"Authorization": f"Bearer {self.token}"}
            params = {"page": page, "per_page": 50}
            r = requests.get(url, headers=headers, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            out.extend(data.get("result", []))
            info = data.get("result_info") or {}
            if not info or info.get("page", 1) >= info.get("total_pages", 1):
                break
            page += 1
        return out


class CFClientLite:
    """尽量贴合 collectors.cloudflare.dns_collector 预期接口"""
    def __init__(self, token: str):
        self.zones = _CFZones(token)


def run_dns_collect_cloudflare(cf_client, zone_id: str, zone_name: str,
                               account_id: Optional[str] = None, upsert=None) -> List[Dict[str, Any]]:
    if _cf_collect_dns is None:
        raise RuntimeError("collectors.cloudflare.dns_collector 未就绪")
    return _cf_collect_dns(cf_client, zone_id, zone_name, account_id, upsert or _default_upsert)


# ---------------- AliDNS: 直连 ----------------
def run_dns_collect_alidns(alidns_client, domain_name: str,
                           account_id: Optional[str] = None, upsert=None) -> List[Dict[str, Any]]:
    if _ali_collect_dns is None:
        raise RuntimeError("collectors.aliyun.alidns_collector 未就绪")
    return _ali_collect_dns(alidns_client, domain_name, account_id, upsert or _default_upsert)


# ---------------- 按 accounts.yaml 执行直连 DNS 采集 ----------------
def collect_dns_direct_from_config():
    accounts = load_accounts_config()
    print(f"[i] Using DB_URL={DB_URL}")
    any_run = False

    for acct in accounts:
        provider = (acct.get("provider") or "").lower()
        account_name = acct.get("name")
        account_id = acct.get("account_id") or acct.get("id")
        print(f"\n=== [{provider}] account={account_name} ({account_id}) ===")

        # ---------- AWS ----------
        if provider == "aws":
            profile = acct.get("profile")
            try:
                r53 = _aws_boto3_client("route53", profile=profile)
            except Exception as e:
                print(f"[!] 跳过 AWS（无法创建 route53 client）: {e}", file=sys.stderr)
                continue

            # 如果 accounts.yaml 里提供了 zones 列表，就只跑这些；否则枚举全部 zones
            zones_cfg = acct.get("dns_zones") or []
            zones: List[Dict[str, str]]
            if zones_cfg:
                zones = [{"id": (z.get("id") or z.get("zone_id")), "name": (z.get("name") or z.get("zone_name"))} for z in zones_cfg]
            else:
                zones = _aws_list_zones(r53)

            if not zones:
                print("[!] AWS 未发现任何 Hosted Zone，已跳过。")
                continue

            for z in zones:
                zid, zname = z.get("id"), (z.get("name") or "").rstrip(".")
                if not zid or not zname:
                    print(f"[!] 忽略非法 zone: {z}")
                    continue
                print(f" -> AWS Zone: {zname} ({zid})")
                run_dns_collect_aws(r53, zid, zname, account_id=account_id)
                any_run = True

        # ---------- Cloudflare ----------
        elif provider == "cloudflare":
            token = acct.get("api_token") or os.getenv("CF_API_TOKEN")
            if not token:
                print("[!] 跳过 Cloudflare：缺少 api_token（accounts.yaml: api_token 或环境变量 CF_API_TOKEN）", file=sys.stderr)
                continue
            cf = CFClientLite(token)

            zones_cfg = acct.get("dns_zones") or []
            if zones_cfg:
                zones = [{"id": (z.get("id") or z.get("zone_id")), "name": (z.get("name") or z.get("zone_name"))} for z in zones_cfg]
            else:
                try:
                    zlist = cf.zones.list()
                except Exception as e:
                    print(f"[!] Cloudflare 列举 zones 失败：{e}", file=sys.stderr)
                    continue
                zones = [{"id": z.get("id"), "name": z.get("name")} for z in zlist]

            if not zones:
                print("[!] Cloudflare 未发现任何 Zone，已跳过。")
                continue

            for z in zones:
                zid, zname = z.get("id"), z.get("name")
                if not zid or not zname:
                    print(f"[!] 忽略非法 zone: {z}")
                    continue
                print(f" -> CF Zone: {zname} ({zid})")
                run_dns_collect_cloudflare(cf, zid, zname, account_id=account_id)
                any_run = True

        # ---------- AliDNS ----------
        elif provider in ("aliyun", "alibaba", "alicloud"):
            # 这里要求你已在 collectors/aliyun/alidns_collector.py 接好 SDK；
            # accounts.yaml 需提供 domains 列表（或根据你现有逻辑获取）
            domains = acct.get("domains") or []
            if not domains:
                print("[!] 跳过 AliDNS：未提供 domains 列表（accounts.yaml: domains: ['example.com', ...]）")
                continue

            # 你自己的 alidns_client 构造（若已有通用工厂，请替换这里）
            alidns_client = acct.get("client")
            if alidns_client is None:
                print("[!] 跳过 AliDNS：未提供 alidns_client 构造（请在此接入你现有 SDK 客户端）")
                continue

            for domain_name in domains:
                print(f" -> AliDNS Domain: {domain_name}")
                run_dns_collect_alidns(alidns_client, domain_name, account_id=account_id)
                any_run = True

        else:
            print(f"[!] 未识别的 provider：{provider}，已跳过。")

    if not any_run:
        print("\n[i] 未运行任何采集任务。请检查 accounts.yaml 配置或凭证。")


# ---------------- CLI 入口 ----------------
def main():
    """
    默认执行【直连新管道】进行 DNS 采集。
    需要使用旧版 registry 流程时，可自行保留原 main 并调用 run_registry_collectors()。
    """
    print(f"[i] Using DB_URL={DB_URL}")
    collect_dns_direct_from_config()


if __name__ == "__main__":
    main()
