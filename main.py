# main.py
import importlib
import os
from utils.config_loader import load_accounts_config
from core.context import CollectorContext
from core.registry import COLLECTOR_REGISTRY
from core.database import setup_database, get_session  # 引入数据库初始化接口
from core import models 
DB_NAME = "cloud_resources"
MYSQL_URL = f"mysql+mysqlconnector://dbuser:12345@10.11.11.62:3306/{DB_NAME}?charset=utf8mb4"
SQLITE_URL = f"sqlite:///CLOUD_ASSETS.db"
POSTGRESQL_URL = f"postgresql+psycopg2://username:password@localhost:5432/cloud_resources"
DB_URL  = os.getenv("DB_URL", MYSQL_URL)
engine = setup_database(DB_URL )

def import_all_collectors():
    base_dir = "collectors"
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith(".py") and file != "__init__.py":
                module_name = os.path.join(root, file)[:-3].replace(os.sep, ".")
                print(module_name)
                try:
                    importlib.import_module(module_name)
                except Exception as e:
                    print(f"[!] 载入收集器 {module_name} 失败: {e}")

def main():

    session = get_session()

    import_all_collectors()  # 动态导入并注册所有收集器
    accounts = load_accounts_config()

    for acct in accounts:
        provider = acct["provider"]
        account_name = acct["name"]
        # 提取账户ID、默认区域、profile等信息（如存在）
        account_id = acct.get("account_id")
        default_region = acct.get("default_region") or (acct.get("regions")[0] if acct.get("regions") else None)
        profile = acct.get("profile")
    
        # 将整个账户配置字典传入config，包含各云所需密钥/令牌
        context = CollectorContext(
            provider=provider,
            account_id=account_id,
            region=default_region,
            name=account_name,
            profile=profile,
            config=acct
        )

        collector_name = f"{provider}_dns"
        if collector_name not in COLLECTOR_REGISTRY:
            print(f"[!] 未找到收集器: {collector_name}")
            continue

        collector_cls = COLLECTOR_REGISTRY[collector_name]
        collector = collector_cls(context)
    
        resources = collector.collect()

        # 保存收集结果到数据库，并打印输出
        for r in resources:
            # 将ResourceItem转换为ORM对象并入库
            cloud_resource = r.to_orm()
            # 获取或创建对应CloudAccount记录
            acct_query = session.query(models.CloudAccount).filter_by(provider=provider, account_id=context.account_id).first()
            if not acct_query:
                acct_query = models.CloudAccount(name=context.name,
                                                      provider=models.CloudProvider(provider),
                                                      account_id=context.account_id)
                session.add(acct_query)
                session.flush()  # 得到acct_query.id用于外键
            cloud_resource.cloud_account_id = acct_query.id
            session.add(cloud_resource)
            print(f"[{r.resource_type}] {r.name} ({r.resource_id})")
        # 提交当前账户的资源记录
        session.commit()

if __name__ == "__main__":
    main()
