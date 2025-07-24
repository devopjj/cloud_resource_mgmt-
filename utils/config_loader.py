import yaml
import yaml
from core.context import CollectorContext

def load_accounts_config(path="config/accounts.yaml"):
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    return data["accounts"]

def load_accounts_yaml(path: str) -> list[CollectorContext]:
    print(path)
    with open(path, "r") as f:
        raw = yaml.safe_load(f)

    contexts = []

    for account in raw.get("accounts", []):
        provider = account["provider"]
        profile = account["profile"]
        account_id = account["account_id"]
        name = account.get("name", "")
        regions = account.get("regions", [])

        for region in regions:
            context = CollectorContext(
                provider=provider,
                account_id=account_id,
                profile=profile,
                region=region,
                config=account.get("config", {}),
                name=name,
            )
            contexts.append(context)

    return contexts    
