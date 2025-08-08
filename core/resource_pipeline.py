# core/resource_pipeline.py
# -*- coding: utf-8 -*-
import os
import re
import json
import hashlib
import ipaddress
from typing import Callable, List, Dict, Any, Optional

from core.meta_normalizer import normalize_meta

# 环境开关：是否在入库前剥离上游原始报文，默认保留（设为 "0" 则剥离）
STRIP_PROVIDER_RAW = os.getenv("STORE_PROVIDER_RAW", "1") == "0"


# ----------------------------
# resource_id 合成（各类型兜底保证稳定）
# ----------------------------
def _mk_dns_resource_id(meta: Dict[str, Any]) -> str:
    """DNS：不依赖上游 ID，使用 <zone_name>|<resource_name>|<record_type>，过长时 sha1。"""
    extra = meta.get("extra") or {}
    zone_name = (extra.get("zone_name") or "").lower()
    name = (meta.get("resource_name") or "").lower()
    rtype = (extra.get("record_type") or "").upper()
    raw = f"{zone_name}|{name}|{rtype}"
    if len(raw) <= 128:
        return raw
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()  # 40 chars


def _mk_vpc_resource_id(meta: Dict[str, Any]) -> str:
    """VPC 兜底：<region>|<cidr_block>"""
    region = (meta.get("region") or "").lower()
    cidr = (meta.get("extra") or {}).get("cidr_block") or ""
    raw = f"{region}|{cidr}"
    return raw if len(raw) <= 128 else hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _first(seq):
    return seq[0] if isinstance(seq, list) and seq else None


def _mk_ecs_resource_id(meta: Dict[str, Any]) -> str:
    """ECS/EC2 兜底：<region>|<name>|<instance_type>|<a_private_ip?>"""
    region = (meta.get("region") or "").lower()
    name = (meta.get("resource_name") or "").lower()
    extra = meta.get("extra") or {}
    itype = (extra.get("instance_type") or "").lower()
    prv = extra.get("private_ip")
    a_ip = None
    if isinstance(prv, list):
        a_ip = _first(prv)
    elif isinstance(prv, dict):
        # AWS 可能是 {"PrivateIpAddress": "..."} 或更复杂结构，这里取常见字段或第一个值
        a_ip = prv.get("PrivateIpAddress") or _first(list(prv.values()))
    raw = f"{region}|{name}|{itype}|{a_ip or ''}"
    return raw if len(raw) <= 128 else hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _mk_slb_resource_id(meta: Dict[str, Any]) -> str:
    """SLB/ELB 兜底：<region>|<name>|<dns_name?>"""
    region = (meta.get("region") or "").lower()
    name = (meta.get("resource_name") or "").lower()
    dns_name = (meta.get("extra") or {}).get("dns_name") or ""
    raw = f"{region}|{name}|{dns_name}"
    return raw if len(raw) <= 128 else hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _synthesize_resource_id(provider: str, resource_type: str, meta: Dict[str, Any]) -> Optional[str]:
    """若上游无 ID，则按类型生成稳定 ID。"""
    rid = meta.get("resource_id")
    if rid:
        return rid

    rt = resource_type.lower()
    if rt == "dns_record":
        return _mk_dns_resource_id(meta)
    if rt == "vpc":
        return _mk_vpc_resource_id(meta)
    if rt in ("ecs", "ec2"):
        return _mk_ecs_resource_id(meta)
    if rt in ("slb", "elb", "alb", "nlb"):
        return _mk_slb_resource_id(meta)
    # 其他类型再按需扩展
    return None


# ----------------------------
# IP 汇总：提取 IPv4/IPv6 并去重，序列化为 JSON 字符串写入 TEXT 列
# ----------------------------
_IP_RE = re.compile(r"[0-9a-fA-F:.]+")


def _is_ip(s: str) -> bool:
    try:
        ipaddress.ip_address(s)
        return True
    except Exception:
        return False


def _collect_ips_from(obj) -> List[str]:
    out = set()
    if obj is None:
        return []
    if isinstance(obj, str):
        if _is_ip(obj):
            out.add(obj)
        else:
            for m in _IP_RE.findall(obj):
                if _is_ip(m):
                    out.add(m)
        return sorted(out)
    if isinstance(obj, (int, float, bool)):
        return []
    if isinstance(obj, list):
        for x in obj:
            for ip in _collect_ips_from(x):
                out.add(ip)
        return sorted(out)
    if isinstance(obj, dict):
        for v in obj.values():
            for ip in _collect_ips_from(v):
                out.add(ip)
        return sorted(out)
    return []


def _extract_ip_addresses(meta: Dict[str, Any], resource_type: str) -> Optional[str]:
    """返回 JSON 字符串（或 None）。"""
    extra = meta.get("extra") or {}
    candidates = []

    rt = resource_type.lower()
    if rt in ("ecs", "ec2"):
        candidates += [extra.get("public_ip"), extra.get("private_ip")]
    elif rt in ("slb", "elb", "alb", "nlb"):
        candidates += [extra.get("address"), extra.get("dns_name")]
    # DNS 不写 ip_addresses，避免歧义
    ips: List[str] = []
    for c in candidates:
        ips.extend(_collect_ips_from(c))
    ips = sorted(set(ips))
    return json.dumps(ips, ensure_ascii=False) if ips else None


# ----------------------------
# 主处理管道
# ----------------------------
def process_resources(
    provider: str,
    resource_type: str,
    records: List[dict],
    upsert_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    **ctx
) -> List[Dict[str, Any]]:
    """
    原始 records -> 统一 meta -> 生成 cloud_resource item -> （可选）upsert（去重 + diff log）
    ctx: account_id/region/status/tags/zone_id/zone_name/created_at/updated_at ...
    """
    items: List[Dict[str, Any]] = []

    for rec in records:
        meta = normalize_meta(provider, resource_type, rec, **ctx)

        # 统一剥离 provider_raw（按需）
        if STRIP_PROVIDER_RAW and "provider_raw" in meta:
            meta.pop("provider_raw", None)

        # 确保 resource_id 存在（合成兜底）
        rid = _synthesize_resource_id(provider, resource_type, meta)
        if rid:
            meta["resource_id"] = rid

        # zone/domain_name 映射到独立列（你的表结构）
        extra = meta.get("extra") or {}
        zone_id = extra.get("zone_id")
        zone_name = extra.get("zone_name")

        item: Dict[str, Any] = {
            "provider": provider,
            "account_id": ctx.get("account_id"),
            "resource_type": resource_type,
            "resource_id": meta.get("resource_id"),
            "region": meta.get("region") or ctx.get("region"),
            "status": meta.get("status"),
            "name": meta.get("resource_name"),
            "zone": zone_id,               # -> cloud_resource.zone
            "domain_name": zone_name,      # -> cloud_resource.domain_name
            "vpc_id": extra.get("vpc_id"),
            "ip_addresses": _extract_ip_addresses(meta, resource_type),
            "tags": meta.get("tags") or {},
            "resource_metadata": meta,
        }

        if upsert_callback:
            upsert_callback(item)

        items.append(item)

    return items
