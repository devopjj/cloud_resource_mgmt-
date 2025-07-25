
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

### 0725: init_db.py
✅ 适用数据库：
    ✅ SQLite
    ✅ MySQL（自动 CREATE DATABASE）
    #### 注意会删库重建
    ```
    python init_db.py
    🚀 使用数据库连接：mysql+mysqlconnector://extra:bluecat63@10.11.11.62:3306/cloud_resources?charset=utf8mb4
    ✅ MySQL 数据库 `cloud_resources` 已确认存在
    ✅ 数据表初始化完成

    ```
    ✅ PostgreSQL（自动 CREATE DATABASE）