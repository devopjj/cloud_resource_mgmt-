#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
File    : core/models.py
Function: 定义 ResolvedDnsRecord 模型，用于储存真实 DNS 解析结果
Author  : Jimmy
Email   : devopjj@gmail.com
Created : 2025-08-05 , 23:53
Modified: 2025-08-05 , 23:53
Version: 1.0
"""
import uuid
from datetime import datetime
import enum
import os
import json
from sqlalchemy import (
    create_engine, Column, String, DateTime, Enum,Index,
    ForeignKey, Text, Integer, JSON
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from pydantic import BaseModel
from typing import Optional, Dict, Any

Base = declarative_base()

# ---------- ENUM TYPES ----------

class CloudProvider(str, enum.Enum):
    aws = "aws"
    aliyun = "aliyun"
    gcp = "gcp"
    azure = "azure"
    cloudflare = "cloudflare"
    tencent = "tencent"

class ResourceType(str, enum.Enum):
    compute = "compute"
    storage = "storage"
    database = "database"
    dns = "dns"
    network = "network"
    certificate = "certificate"
    iam = "iam"
    function = "function"
    unknown = "unknown"
    
class ResourceItem(BaseModel):
    provider: str
    account_id: str
    region: str
    resource_type: str
    resource_id: str  # 使用 resource_id 来保持一致
    name: Optional[str]
    status: Optional[str]
    zone: Optional[str]
    domain_name: Optional[str] = None
    vpc_id: Optional[str] = None
    ip_addresses: Optional[list[str]] = []  
    tags: Dict[str, str] = {}
    metadata: Dict[str, Any] = {}
    fetched_at: datetime  # 确保 fetched_at 字段存在

    def to_orm(self):
        # 将 metadata 中的 datetime 对象转换为 ISO 格式字符串（仅当 metadata 中有 datetime 类型时）
        serialized_metadata = {
            k: (v.isoformat() if isinstance(v, datetime) else v)
            for k, v in self.metadata.items()
        }

        # 直接将 fetched_at 作为 datetime 对象传入
        return CloudResource(
            provider=self.provider,
            cloud_account_id=self.account_id,
            resource_type=self.resource_type,
            resource_id=self.resource_id,
            name=self.name,
            region=self.region,
            zone=self.zone,
            domain_name=self.domain_name,
            vpc_id=self.vpc_id,
            ip_addresses=json.dumps(self.ip_addresses),
            status=self.status,
            tags=self.tags,
            resource_metadata=serialized_metadata,  # 使用序列化后的 metadata
            fetched_at=self.fetched_at  # 直接传递 datetime 对象
        )
# ---------- MODELS ----------
class ResolvedDnsRecord(Base):
    __tablename__ = "resolved_dns_record"

    id = Column(String(36), primary_key=True)
    cloud_resource_id = Column(String(36), ForeignKey("cloud_resource.id"), nullable=False)
    domain_name = Column(String(255), nullable=False)
    region = Column(String(64), nullable=False)
    record_type = Column(String(10), default="A")
    resolved_data = Column(Text, nullable=False)  # 存储 JSON 字串，如 ["1.1.1.1", "2.2.2.2"]
    description = Column(Text)
    resolved_at = Column(DateTime)
    
class CloudAccount(Base):
    __tablename__ = "cloud_account"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(128), nullable=False)
    provider = Column(String(64), nullable=False)
    account_id = Column(String(128), nullable=False)
    region_json = Column(Text)  # JSON string of region status
    tags = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    resources = relationship("CloudResource", back_populates="cloud_account")


class CloudResource(Base):
    __tablename__ = "cloud_resource"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cloud_account_id = Column(String(36), ForeignKey("cloud_account.id"), nullable=False)
    resource_type = Column(String(64), nullable=False)
    resource_id = Column(String(128), nullable=False)  # Native cloud resource ID
    region = Column(String(64))
    provider = Column(String(64), nullable=False)
    zone = Column(String(64))
    name = Column(String(256))
    status = Column(String(64))
    domain_name = Column(String(256))
    vpc_id = Column(String(64))
    ip_addresses = Column(Text)    
    tags = Column(JSON, default={})
    resource_metadata = Column(JSON, default={})  # ✅ renamed from 'metadata'
    fetched_at = Column(DateTime, default=datetime.utcnow)

    cloud_account = relationship("CloudAccount", back_populates="resources")

class ResourceRelationship(Base):
    __tablename__ = "resource_relationship"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(String(64), nullable=False)
    target_id = Column(String(64), nullable=False)
    relation_type = Column(String(64), nullable=False)

    __table_args__ = (
        Index("idx_relation_src", "source_id"),
        Index("idx_relation_tgt", "target_id"),
    )


class ResourceDiffLog(Base):
    __tablename__ = "resource_diff_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cloud_account_id = Column(String(64), nullable=False)
    provider = Column(String(32), nullable=False)
    region = Column(String(64))
    resource_type = Column(String(64), nullable=False)
    resource_id = Column(String(128), nullable=False)
    changed_fields = Column(Text, nullable=False)  # JSON 格式字符串
    raw_before = Column(Text)
    raw_after = Column(Text)
    changed_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("idx_resource_diff_rid", "resource_id"),
        Index("idx_resource_diff_time", "changed_at"),
    )



class DomainRecord(Base):
    __tablename__ = "domain_record"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cloud_account_id = Column(String(36), ForeignKey("cloud_account.id"), nullable=False)
    domain = Column(String(256), nullable=False)
    record_type = Column(String(16))  # A, CNAME, MX, TXT, etc.
    name = Column(String(256))
    value = Column(String(512))
    ttl = Column(Integer)
    line = Column(String(64))  # telecom, unicom, default...
    status = Column(String(32))
    provider_raw = Column(JSON, default={})
    fetched_at = Column(DateTime, default=datetime.utcnow)

# ---------- INIT FUNCTIONS ----------

def init_db(db_url="sqlite:///cloud_resources.db"):
    engine = create_engine(db_url, echo=False, future=True)
    Base.metadata.create_all(engine)
    return engine

def get_session(engine):
    Session = sessionmaker(bind=engine)
    return Session()

# ---------- CLI USAGE ----------

if __name__ == "__main__":
    MYSQL_URL = "mysql+mysqlconnector://dbuser:12345@10.11.11.62:3306/cloud_resources?charset=utf8mb4"
    SQLITE_URL = "sqlite:///cloud_resources.db"
    POSTGRESQL_URL="postgresql+psycopg2://username:password@localhost:5432/cloud_resources"
    db_url = os.getenv("DB_URL", MYSQL_URL)
    engine = init_db(db_url)
    print(f"✅ Initialized DB at {db_url}")
