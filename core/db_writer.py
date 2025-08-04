from sqlalchemy.dialects.mysql import insert
from sqlalchemy import text
from datetime import datetime
import json
from core.models import CloudResource

def obj_to_dict(obj):
    def serialize(val):
        if isinstance(val, datetime):
            return val.isoformat()
        return val

    return {
        column.key: serialize(getattr(obj, column.key))
        for column in obj.__table__.columns
    }


def log_diff_if_changed(session, old_obj, new_obj):
    changed_fields = []
    def normalize(val):
        if isinstance(val, dict) or isinstance(val, list):
            return json.dumps(val, sort_keys=True, ensure_ascii=False)
        return str(val)

    compare_fields = [
        "name", "status", "zone", "domain_name",
        "vpc_id", "ip_addresses", "tags", "resource_metadata"
    ]

    for field in compare_fields:
        old_val = normalize(getattr(old_obj, field, None))
        new_val = normalize(getattr(new_obj, field, None))
        if old_val != new_val:
            changed_fields.append(field)

    if changed_fields:
        session.execute(text("""
            INSERT INTO resource_diff_log (
                cloud_account_id, provider, region,
                resource_type, resource_id,
                changed_fields, raw_before, raw_after, changed_at
            ) VALUES (
                :account_id, :provider, :region,
                :type, :rid,
                :fields, :before, :after, :time
            )
        """), {
            "account_id": new_obj.cloud_account_id,
            "provider": new_obj.provider,
            "region": new_obj.region,
            "type": new_obj.resource_type,
            "rid": new_obj.resource_id,
            "fields": json.dumps(changed_fields, ensure_ascii=False),
            "before": json.dumps(obj_to_dict(old_obj), ensure_ascii=False),
            "after": json.dumps(obj_to_dict(new_obj), ensure_ascii=False),
            "time": datetime.utcnow()
        })

def insert_if_not_exists_or_log_diff(session, new_obj: CloudResource):
    existing = session.query(CloudResource).filter_by(
    cloud_account_id=new_obj.cloud_account_id,
    resource_type=new_obj.resource_type,
    resource_id=new_obj.resource_id
    ).first()
    if existing:
        log_diff_if_changed(session, existing, new_obj)
    else:
        session.add(new_obj)

def insert_resolved_dns_record(session, resolved: dict, cloud_resource_id: str):
    record = ResolvedDnsRecord(
        id=resolved["id"],
        cloud_resource_id=cloud_resource_id,
        domain_name=resolved["domain_name"],
        region=resolved["region"],
        record_type=resolved["record_type"],
        resolved_data=json.dumps(resolved["resolved_data"], ensure_ascii=False),
        description=resolved["description"],
        resolved_at=resolved["resolved_at"]
    )
    session.add(record)
    session.commit()
