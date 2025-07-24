import yaml

def load_accounts_config(path="config/accounts.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)["accounts"]
