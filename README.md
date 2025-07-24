
### DB 数据库
#### 🧪 sqlite 使用方式示例
```
python core/models.py
```
你将看到：

`✅ Initialized DB at sqlite:///cloud_assets.db`

#### 🧪 改用 PostgreSQ
修改数据库 URL
你可以用环境变量指定 PostgreSQL 数据库，例如：
```
export DB_URL="postgresql+psycopg2://username:password@localhost:5432/cloud_assets"
```
或者直接在代码中设置
```
db_url = "postgresql+psycopg2://user:pass@host:5432/dbname"
engine = init_db(db_url)

```