# storage/mysql_store.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.models import Base, ResourceItem
from core.models import ResourceDiffLog

from datetime import datetime
import json

# 请根据你的实际 MySQL 连接配置修改以下内容
MYSQL_URL = "mysql+mysqlconnector://user:password@localhost:3306/cloud_resources?charset=utf8mb4"

engine = create_engine(MYSQL_URL, echo=False, pool_pre_ping=True)
Session = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(engine)

def diff_fields(old: CloudResource, new: CloudResource) -> dict:
    changes = {}
    for field in ["name", "status", "domain_name", "ip_addresses", "tags"]:
        if getattr(old, field) != getattr(new, field):
            changes[field] = {
                "old": getattr(old, field),
                "new": getattr(new, field)
            }
    return changes

def save_resource_items(items: list[CloudResource], relationships: list[ResourceRelationship] = None):
    session = Session()
    try:
        for item in items:
            existing = session.query(CloudResource).filter_by(
                cloud_account_id=item.cloud_account_id,
                resource_type=item.resource_type,
                resource_id=item.resource_id
            ).first()

            if existing:
                changes = diff_fields(existing, item)
                if changes:
                    # inside `if changes:` block
                    diff_log = ResourceDiffLog(
                        cloud_account_id=item.cloud_account_id,
                        provider=item.provider,
                        region=item.region,
                        resource_type=item.resource_type,
                        resource_id=item.resource_id,
                        changed_fields=json.dumps(changes, ensure_ascii=False),
                        raw_before=existing.resource_metadata,
                        raw_after=item.resource_metadata,
                        changed_at=datetime.now()
                    )
                    session.add(diff_log)        
                                
                    for field in changes.keys():
                        setattr(existing, field, getattr(item, field))
                    existing.fetched_at = datetime.now()
                    session.add(existing)
                    print(f"[UPDATED] {item.resource_type} {item.name} changes: {json.dumps(changes)}")
                else:
                    print(f"[UNCHANGED] {item.resource_type} {item.name}")
            else:
                session.add(item)
                print(f"[NEW] {item.resource_type} {item.name}")

        # 保存资源关系（可选）
        if relationships:
            for rel in relationships:
                session.add(rel)

        session.commit()

    except Exception as e:
        session.rollback()
        print(f"[!] Save to MySQL failed: {e}")
    finally:
        session.close()
