# core/context.py

class CollectorContext:
    def __init__(self, provider: str, account_id: str = None, region: str = None,
                 name: str = None, profile: str = None, config: dict = None):
        """多云环境的收集上下文，保存当前账户及凭据信息"""
        self.provider = provider
        self.account_id = account_id or ""    # 云账号唯一ID，如AWS账号ID等
        self.name = name or ""               # 云账户别名/名称
        self.region = region or ""           # 区域信息（如适用）
        self.profile = profile or None       # AWS本地凭据配置名称（如果有）
        self.config = config or {}           # 其它配置，例如密钥、token等

    def get_boto3_session(self):
        import boto3
        # 根据配置优先使用AWS profile，其次使用明文密钥
        if self.profile:
            return boto3.Session(profile_name=self.profile, region_name=self.region or None)
        else:
            return boto3.Session(
                aws_access_key_id=self.config.get("aws_access_key_id"),
                aws_secret_access_key=self.config.get("aws_secret_access_key"),
                region_name=self.region or None,
            )

    def __repr__(self):
        return f"<Context {self.provider}:{self.account_id}@{self.region or 'N/A'}>"
