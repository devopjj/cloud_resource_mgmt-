# init_db.py

from core.models import Base
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.engine import Engine
import os

def create_database_if_needed(db_url: str):
    url = make_url(db_url)
    backend = url.get_backend_name()
    db_name = url.database

    if backend.startswith("sqlite"):
        # SQLite 会自动创建 .db 文件
        print(f"🎯 SQLite 自动创建数据库文件：{db_name}")
        return

    if backend.startswith("mysql"):
        tmp_url = url.set(database="information_schema")  # ✅ 不要用 None
        engine = create_engine(tmp_url)
        with engine.connect() as conn:
            conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
        print(f"✅ MySQL 数据库 `{db_name}` 已确认存在")

    elif backend.startswith("postgresql"):
        tmp_url = url.set(database="postgres")
        engine = create_engine(tmp_url)
        with engine.connect() as conn:
            exists = conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname='{db_name}'")).scalar()
            if not exists:
                conn.execute(text(f"CREATE DATABASE {db_name}"))
        print(f"✅ PostgreSQL 数据库 `{db_name}` 已确认存在")
    else:
        raise ValueError(f"❌ 不支持的数据库类型: {backend}")


def create_indexes(engine: Engine):
    backend = engine.url.get_backend_name()
    with engine.connect() as conn:
        print("🔧 创建通用索引...")

        def has_index(index_name):
            if backend.startswith("mysql"):
                res = conn.execute(text(f"""
                    SELECT COUNT(*) FROM information_schema.statistics 
                    WHERE table_schema = DATABASE() 
                    AND table_name = 'cloud_resource' 
                    AND index_name = :idx
                """), {"idx": index_name})
                return res.scalar() > 0
            elif backend.startswith("postgresql"):
                res = conn.execute(text(f"""
                    SELECT to_regclass('public.{index_name}') IS NOT NULL
                """))
                return res.scalar()
            return False

        def safe_create_index(index_name, sql):
            if not has_index(index_name):
                print(f"  → 建立索引 {index_name}")
                conn.execute(text(sql))
            else:
                print(f"  → 已存在索引 {index_name}，跳过")

        safe_create_index("idx_provider_type", "CREATE INDEX idx_provider_type ON cloud_resource(provider, resource_type)")
        safe_create_index("idx_region_zone", "CREATE INDEX idx_region_zone ON cloud_resource(region, zone)")
        safe_create_index("idx_fetched_at", "CREATE INDEX idx_fetched_at ON cloud_resource(fetched_at)")

        if backend.startswith("postgresql"):
            print("🔧 创建 PostgreSQL GIN 索引...")
            safe_create_index("idx_metadata_domain_name", """
                CREATE INDEX idx_metadata_domain_name ON cloud_resource 
                USING GIN ((resource_metadata->>'domain_name'))
            """)
            safe_create_index("idx_metadata_instance_type", """
                CREATE INDEX idx_metadata_instance_type ON cloud_resource 
                USING GIN ((resource_metadata->>'InstanceType'))
            """)
            safe_create_index("idx_metadata_ip", """
                CREATE INDEX idx_metadata_ip ON cloud_resource 
                USING GIN ((resource_metadata->'InnerIpAddress'->'IpAddress'))
            """)
        else:
            print("⚠️  当前数据库不支持 GIN 索引，跳过 JSON 索引")


def reset_tables(db_url: str):
    engine = create_engine(db_url)
    print("⚠️  删除所有已存在的表...")
    Base.metadata.drop_all(engine)
    print("✅ 所有旧表已删除")
    Base.metadata.create_all(engine)
    print("✅ 所有新表已创建")
    
    create_indexes(engine)
    print("✅ 所有索引已创建")

if __name__ == "__main__":
    MYSQL_URL = "mysql+mysqlconnector://dbuser:12345@10.11.11.62:3306/cloud_assets?charset=utf8mb4"
    SQLITE_URL = "sqlite:///cloud_assets2.db"
    POSTGRESQL_URL="postgresql+psycopg2://username:password@localhost:5432/cloud_assets"
    db_url = os.getenv("DB_URL", SQLITE_URL)
     
    print(f"🚀 使用数据库连接：{db_url}")

    create_database_if_needed(db_url)
    reset_tables(db_url)
