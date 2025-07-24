from typing import Optional

class CollectorContext:
    def __init__(self, provider: str, account: str, profile: Optional[str] = None, region: Optional[str] = None):
        self.provider = provider
        self.account = account
        self.profile = profile
        self.region = region
