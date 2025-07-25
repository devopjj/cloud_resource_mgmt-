# storage/mysql_store.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.models import Base, ResourceItem

# 请根据你的实际 MySQL 连接配置修改以下内容
MYSQL_URL = "mysql+mysqlconnector://user:password@localhost:3306/cloud_resources?charset=utf8mb4"

engine = create_engine(MYSQL_URL, echo=False, pool_pre_ping=True)
Session = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(engine)

def save_resource_items(items):
    session = Session()
    try:
        for item in items:
            session.merge(item)
        session.commit()
    except Exception as e:
        session.rollback()
        print(f"[!] Save to MySQL failed: {e}")
    finally:
        session.close()
