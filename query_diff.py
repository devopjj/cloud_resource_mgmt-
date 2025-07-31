#!/usr/bin/env python3

import argparse
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.models import ResourceDiffLog
from storage.mysql_store import MYSQL_URL

engine = create_engine(MYSQL_URL, echo=False)
Session = sessionmaker(bind=engine)

def query_diff(account_id=None, resource_type=None, resource_id=None):
    session = Session()
    try:
        query = session.query(ResourceDiffLog)

        if account_id:
            query = query.filter(ResourceDiffLog.cloud_account_id == account_id)
        if resource_type:
            query = query.filter(ResourceDiffLog.resource_type == resource_type)
        if resource_id:
            query = query.filter(ResourceDiffLog.resource_id == resource_id)

        results = query.order_by(ResourceDiffLog.changed_at.desc()).all()

        for row in results:
            print("🆔 Resource:", row.resource_id)
            print("📅 Changed at:", row.changed_at)
            print("📍 Type:", row.resource_type, "| Provider:", row.provider, "| Region:", row.region)
            print("📝 Diff:")
            changes = json.loads(row.changed_fields)
            for k, v in changes.items():
                print(f"  - {k}: {v['old']} → {v['new']}")
            print("-" * 50)

    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query resource diff log")
    parser.add_argument("--account", help="Cloud account ID")
    parser.add_argument("--type", help="Resource type (ecs, slb, etc.)")
    parser.add_argument("--id", help="Resource ID")

    args = parser.parse_args()

    query_diff(account_id=args.account, resource_type=args.type, resource_id=args.id)
