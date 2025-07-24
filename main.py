import importlib
import os
from utils.config_loader import load_accounts_config
from core.context import CollectorContext
from core.registry import COLLECTOR_REGISTRY

def import_all_collectors():
    base_dir = "collectors"
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith(".py") and file != "__init__.py":
                rel_path = os.path.join(root, file).replace("/", ".").replace("\\", ".")
                module_name = rel_path[:-3]  # remove ".py"
                try:
                    importlib.import_module(module_name)
                except Exception as e:
                    print(f"[!] 载入收集器 {module_name} 失败: {e}")
                    
def main():
    import_all_collectors()  # <-- 确保注册收集器
    accounts = load_accounts_config()
    for acct in accounts:
        provider = acct["provider"]
        account = acct["name"]
        profile = acct.get("profile")
        context = CollectorContext(provider=provider, account=account, profile=profile)

        collector_name = f"{provider}_route53"
        if collector_name not in COLLECTOR_REGISTRY:
            print(f"[!] 未找到收集器: {collector_name}")
            continue

        collector_cls = COLLECTOR_REGISTRY[collector_name]
        collector = collector_cls(context)
        resources = collector.collect()

        for r in resources:
            print(f"[{r.resource_type}] {r.name} ({r.id})")

if __name__ == "__main__":
    main()
