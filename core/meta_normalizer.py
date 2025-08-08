# core/meta_normalizer.py
# -*- coding: utf-8 -*-
from datetime import datetime, timezone
from typing import Any, Dict, Callable, Optional, Union, List

ISO8601_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"

def _to_iso8601_utc(dt: Union[str, int, float, datetime, None]) -> Optional[str]:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.strftime(ISO8601_FMT)
    if isinstance(dt, (int, float)):
        return datetime.fromtimestamp(dt, tz=timezone.utc).strftime(ISO8601_FMT)
    if isinstance(dt, str):
        s = dt.strip()
        for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                d = datetime.strptime(s.replace("Z", ""), fmt)
                return d.replace(tzinfo=timezone.utc).strftime(ISO8601_FMT)
            except:
                pass
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return d.astimezone(timezone.utc).strftime(ISO8601_FMT)
        except:
            return None
    return None

def _rstrip_dot(name: Optional[str]) -> Optional[str]:
    return name[:-1] if name and name.endswith(".") else name

def _compact(d: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for k, v in d.items():
        if k in ("tags", "extra"):
            out[k] = v if isinstance(v, dict) else {}
            continue
        if v is None:
            continue
        out[k] = v
    return out

def base_schema(record: Dict[str, Any], **ctx) -> Dict[str, Any]:
    return {
        "provider_raw": record,
        "resource_id": ctx.get("resource_id"),
        "resource_name": ctx.get("resource_name"),
        "resource_type": ctx.get("resource_type"),
        "region": ctx.get("region"),
        "status": ctx.get("status"),
        "created_at": _to_iso8601_utc(ctx.get("created_at")),
        "updated_at": _to_iso8601_utc(ctx.get("updated_at")),
        "tags": ctx.get("tags") or {},
        "extra": {},
    }

# ---------- DNS ----------
def normalize_dns_aws(record: Dict[str, Any], **ctx) -> Dict[str, Any]:
    base = base_schema(record, **ctx)
    values = []
    for rr in record.get("ResourceRecords") or []:
        if rr.get("Value") is not None:
            values.append(rr["Value"])
    alias_target = record.get("AliasTarget")
    if alias_target:
        alias_name = _rstrip_dot(alias_target.get("DNSName"))
        if alias_name:
            values.append(alias_name)
    base.update({
        "resource_id": record.get("SetIdentifier") or None,
        "resource_name": _rstrip_dot(record.get("Name")),
        "status": ctx.get("status") or "active",
        "extra": {
            "record_type": record.get("Type"),
            "value": values if len(values) > 1 else (values[0] if values else None),
            "ttl": record.get("TTL"),
            "zone_id": ctx.get("zone_id"),
            "zone_name": ctx.get("zone_name"),
            "alias_target": alias_target
        }
    })
    return _compact(base)

def normalize_dns_cf(record: Dict[str, Any], **ctx) -> Dict[str, Any]:
    base = base_schema(record, **ctx)
    base.update({
        "resource_id": record.get("id"),
        "resource_name": record.get("name"),
        "status": "proxied" if record.get("proxied") else (record.get("status") or "active"),
        "extra": {
            "record_type": record.get("type"),
            "value": record.get("content"),
            "ttl": record.get("ttl"),
            "zone_id": record.get("zone_id") or ctx.get("zone_id"),
            "zone_name": ctx.get("zone_name"),
            "proxied": record.get("proxied"),
            "priority": record.get("priority"),
        }
    })
    return _compact(base)

def normalize_dns_ali(record: Dict[str, Any], **ctx) -> Dict[str, Any]:
    base = base_schema(record, **ctx)
    domain = record.get("DomainName") or ctx.get("zone_name")
    rr = record.get("RR")
    name = f"{rr}.{domain}" if rr and rr != "@" else domain
    base.update({
        "resource_id": record.get("RecordId"),
        "resource_name": name,
        "status": record.get("Status") or "ENABLE",
        "extra": {
            "record_type": record.get("Type"),
            "value": record.get("Value"),
            "ttl": record.get("TTL"),
            "zone_id": ctx.get("zone_id"),
            "zone_name": domain,
            "weight": record.get("Weight"),
        }
    })
    return _compact(base)

# ---------- VPC ----------
def normalize_vpc_aws(record: Dict[str, Any], **ctx) -> Dict[str, Any]:
    base = base_schema(record, **ctx)
    base.update({
        "resource_id": record.get("VpcId"),
        "resource_name": record.get("VpcId"),
        "status": record.get("State"),
        "extra": {
            "cidr_block": record.get("CidrBlock"),
            "is_default": record.get("IsDefault"),
        }
    })
    return _compact(base)

def normalize_vpc_ali(record: Dict[str, Any], **ctx) -> Dict[str, Any]:
    base = base_schema(record, **ctx)
    base.update({
        "resource_id": record.get("VpcId"),
        "resource_name": record.get("VpcName"),
        "status": record.get("Status"),
        "extra": {
            "cidr_block": record.get("CidrBlock"),
            "vrouter_id": record.get("VRouterId"),
        }
    })
    return _compact(base)

# ---------- ECS ----------
def normalize_ecs_aws(record: Dict[str, Any], **ctx) -> Dict[str, Any]:
    base = base_schema(record, **ctx)
    base.update({
        "resource_id": record.get("InstanceId"),
        "resource_name": record.get("InstanceId"),
        "status": record.get("State", {}).get("Name"),
        "extra": {
            "instance_type": record.get("InstanceType"),
            "public_ip": record.get("PublicIpAddress", {}).get("PublicIp", []),
            "private_ip": record.get("PrivateIpAddress", {}),
        }
    })
    return _compact(base)

def normalize_ecs_ali(record: Dict[str, Any], **ctx) -> Dict[str, Any]:
    base = base_schema(record, **ctx)
    base.update({
        "resource_id": record.get("InstanceId"),
        "resource_name": record.get("InstanceName"),
        "status": record.get("Status"),
        "extra": {
            "instance_type": record.get("InstanceType"),
            "public_ip": record.get("PublicIpAddress", {}).get("IpAddress", []),
            "private_ip": record.get("InnerIpAddress", {}).get("IpAddress", []),
            "vpc_id": record.get("VpcAttributes", {}).get("VpcId"),
        }
    })
    return _compact(base)

# ---------- SLB ----------
def normalize_slb_aws(record: Dict[str, Any], **ctx) -> Dict[str, Any]:
    base = base_schema(record, **ctx)
    base.update({
        "resource_id": record.get("LoadBalancerName"),
        "resource_name": record.get("LoadBalancerName"),
        "status": record.get("State", {}).get("Code"),
        "extra": {
            "dns_name": record.get("DNSName"),
            "listeners": record.get("ListenerDescriptions", []),
        }
    })
    return _compact(base)

def normalize_slb_ali(record: Dict[str, Any], **ctx) -> Dict[str, Any]:
    base = base_schema(record, **ctx)
    base.update({
        "resource_id": record.get("LoadBalancerId"),
        "resource_name": record.get("LoadBalancerName"),
        "status": record.get("LoadBalancerStatus"),
        "extra": {
            "address": record.get("Address"),
            "listeners": record.get("ListenerPortsAndProtocol", {}).get("ListenerPortsAndProtocol", []),
        }
    })
    return _compact(base)

NORMALIZERS: Dict[str, Callable[..., Dict[str, Any]]] = {
    "aws.dns_record": normalize_dns_aws,
    "cloudflare.dns_record": normalize_dns_cf,
    "aliyun.dns_record": normalize_dns_ali,

    "aws.vpc": normalize_vpc_aws,
    "aliyun.vpc": normalize_vpc_ali,

    "aws.ecs": normalize_ecs_aws,
    "aliyun.ecs": normalize_ecs_ali,

    "aws.slb": normalize_slb_aws,
    "aliyun.slb": normalize_slb_ali,
}

def normalize_meta(provider: str, resource_type: str, record: dict, **context) -> dict:
    key = f"{provider.lower()}.{resource_type.lower()}"
    fn = NORMALIZERS.get(key)
    if not fn:
        return base_schema(record, resource_type=resource_type, **context)
    return fn(record, resource_type=resource_type, **context)
