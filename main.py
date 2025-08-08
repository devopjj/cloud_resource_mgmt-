# main.py
# -*- coding: utf-8 -*-
"""
tp501 / cloud_resource_mgmt
- 动态加载 collectors（基于 core.registry）
- 逐账户执行采集，入库（去重 + diff log 走 core.db_writer）
- 统一异常保护、会话管理
- 追加三家 DNS 直连入口（run_dns_collect_*），方便独立调用
"""

import importlib
import os
import sys
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List

from utils.config_loader import load_accounts_config
from core.context import CollectorContext
from core.registry import COLLECTOR_REGISTRY
from core.database import setup_database, get_session
from core import models
from core.db_writer import insert_if_not_exists_or_log_diff

# ---- 数据库连接 ----
DB_NAME = "cloud_resources"
MYSQL_URL = f"mysql+mysqlconnector://dbuser:12345@10.11.11.62:3306/{DB_NAME}?charset=utf8mb4"
SQLITE_URL = "sqlite:///CLOUD_ASSETS.db"
POSTGRESQL_URL = "postgresql+psycopg2://username:password@localhost:5432/cloud_resources"
DB_URL = os.getenv("DB_URL", MYSQL_URL)

# 初始化引擎（内部会建表）
engine = setup_database(DB_URL)


# ---- 动态导入所有 collectors 下的模块，确保完成注册 ----
def import_all_collectors() -> None:
    base_dir = "collectors"
    for root, _, files in os.walk(base_dir):
        for file in files:
            if file.endswith(".py") and file != "__init__.py":
                module_name = os.path.join(root, file)[:-3].replace(os.sep, ".")
                try:
                    importlib.import_module(module_name)
                except Exception as e:
                    print(f"[!] 载入收集器 {module_name} 失败: {e}", file=sys.stderr)


# ---- 主流程：基于 registry 的通用执行器（与你现有设计保持一致） ----
def run_registry_collectors() -> None:
    """
    从 config/accounts.yaml 读取账户，根据 provider 组装 collector_name，
    通过 COLLECTOR_REGISTRY 实例化 collector 并执行 .collect()，
    最后将每条资源转换为 ORM 并通过 insert_if_not_exists_or_log_diff 入库。
    """
    session = get_session()
    try:
        import_all_collectors()
        accounts = load_accounts_config()

        for acct in accounts:
            provider = acct["provider"]
            account_name = acct["name"]
            account_id = acct.get("account_id")
            default_region = acct.get("default_region") or (
                acct.get("regions")[0] if acct.get("regions") else None
            )
            profile = acct.get("profile")

            context = CollectorContext(
                provider=provider,
                account_id=account_id,
                region=default_region,
                name=account_name,
                profile=profile,
                config=acct,  # 将账户全部配置下发给 collector（密钥/令牌等）
            )

            collector_name = f"{provider}_dns"  # 如有其它类型可在此扩展
            collector_cls = COLLECTOR_REGISTRY.get(collector_name)
            if not collector_cls:
                print(f"[!] 未找到收集器: {collector_name}（provider={provider}）", file=sys.stderr)
                continue

            collector = collector_cls(context)

            try:
                resources = collector.collect()  # -> List[YourResourceDTO]，含 .to_orm()
            except Exception as e:
                print(f"[!] 采集失败(provider={provider}, account={account_name}): {e}", file=sys.stderr)
                session.rollback()
                continue

            # 账户存在性检查/创建（CloudAccount.id 作为 FK）
            acct_row = (
                session.query(models.CloudAccount)
                .filter_by(provider=provider, account_id=context.account_id)
                .first()
            )
            if not acct_row:
                acct_row = models.CloudAccount(
                    id=str(uuid.uuid4()),
                    name=context.name,
                    provider=models.CloudProvider(provider),
                    account_id=context.account_id,
                )
                session.add(acct_row)
                session.flush()

            # 入库（去重 + diff log）
            for r in resources:
                orm_obj = r.to_orm()  # -> core.models.CloudResource
                orm_obj.cloud_account_id = acct_row.id
                if not getattr(orm_obj, "id", None):
                    orm_obj.id = str(uuid.uuid4())
                if not getattr(orm_obj, "fetched_at", None):
                    orm_obj.fetched_at = datetime.utcnow()
                insert_if_not_exists_or_log_diff(session, orm_obj)
                print(f"[{r.resource_type}] {r.name} ({r.resource_id})")

            session.commit()

    finally:
        try:
            session.close()
        except Exception:
            pass


# ----------------------------
# 追加：三家 DNS 直连入口（可在脚本或调度里直接调用）
# ----------------------------
try:
    # 这些采集器是“简化直连版本”，内部已对接 normalize + pipeline（返回统一 item 列表或走回调写库）
    from collectors.aws.route53_collector import collect_dns_records as _aws_collect_dns
    from collectors.cloudflare.dns_collector import collect_dns_records as _cf_collect_dns
    from collectors.aliyun.alidns_collector import collect_dns_records as _ali_collect_dns
except Exception:
    _aws_collect_dns = _cf_collect_dns = _ali_collect_dns = None


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

    # 生成主键与时间戳
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


# 默认 upsert 回调：严格映射到 ORM 并调用 insert_if_not_exists_or_log_diff
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


def run_dns_collect_aws(route53_client, hosted_zone_id: str, zone_name: str,
                        account_id: Optional[str] = None, upsert=None) -> List[Dict[str, Any]]:
    if _aws_collect_dns is None:
        raise RuntimeError("collectors.aws.route53_collector 未就绪")
    return _aws_collect_dns(route53_client, hosted_zone_id, zone_name, account_id, upsert or _default_upsert)


def run_dns_collect_cloudflare(cf_client, zone_id: str, zone_name: str,
                               account_id: Optional[str] = None, upsert=None) -> List[Dict[str, Any]]:
    if _cf_collect_dns is None:
        raise RuntimeError("collectors.cloudflare.dns_collector 未就绪")
    return _cf_collect_dns(cf_client, zone_id, zone_name, account_id, upsert or _default_upsert)


def run_dns_collect_alidns(alidns_client, domain_name: str,
                           account_id: Optional[str] = None, upsert=None) -> List[Dict[str, Any]]:
    if _ali_collect_dns is None:
        raise RuntimeError("collectors.aliyun.alidns_collector 未就绪")
    return _ali_collect_dns(alidns_client, domain_name, account_id, upsert or _default_upsert)


# ---- CLI 入口 ----
def main():
    """
    默认执行基于 registry 的采集流程（与现有项目兼容）。
    若要使用直连入口，请在其他脚本里调用 run_dns_collect_*。
    """
    print(f"[i] Using DB_URL={DB_URL}")
    run_registry_collectors()


if __name__ == "__main__":
    main()
