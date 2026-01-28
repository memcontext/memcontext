# Supabase 表结构设置指南

本文档说明如何在本地 Supabase 实例（http://192.168.22.111:8000/）中创建表结构。

## 前提条件

1. Supabase 实例正在运行（http://192.168.22.111:8000/）
2. 已安装 Python 依赖：`pip install -r requirements.txt`
3. 知道数据库连接信息（默认本地 Supabase 使用端口 54322）

## 方式 1: 使用 Supabase Studio Web UI（最简单）⭐ 推荐

1. **打开 Supabase Studio**
   ```
   http://192.168.22.111:8000/studio
   ```

2. **进入 SQL Editor**
   - 在左侧菜单找到 "SQL Editor"
   - 点击 "New query"

3. **执行 schema.sql**
   - 打开项目中的 `supabase/schema.sql` 文件
   - 复制全部内容
   - 粘贴到 SQL Editor
   - 点击 "Run" 或按 `Ctrl+Enter` (Windows) / `Cmd+Enter` (Mac)

4. **验证**
   - 在左侧菜单找到 "Table Editor"
   - 应该能看到 7 张新表：
     - `assistants`
     - `short_term_messages`
     - `mid_term_sessions`
     - `mid_term_pages`
     - `long_term_user_profiles`
     - `long_term_user_knowledge`
     - `long_term_assistant_knowledge`

## 方式 2: 使用 Python 脚本（psycopg2）

如果你安装了 `psycopg2-binary`，可以使用自动化脚本：

```bash
# 安装依赖（如果还没安装）
pip install psycopg2-binary

# 执行建表脚本
python scripts/setup_supabase_tables_psql.py
```

**自定义连接参数：**
```bash
python scripts/setup_supabase_tables_psql.py \
    --host 192.168.22.111 \
    --port 54322 \
    --user postgres \
    --password your_password \
    --database postgres
```

**使用环境变量：**
```bash
export DB_HOST=192.168.22.111
export DB_PORT=54322
export DB_USER=postgres
export DB_PASSWORD=your_password
export DB_NAME=postgres

python scripts/setup_supabase_tables_psql.py
```

## 方式 3: 使用 psql 命令行

如果你有 `psql` 命令行工具：

```bash
# 连接数据库
psql "postgresql://postgres:postgres@192.168.22.111:54322/postgres"

# 在 psql 中执行
\i supabase/schema.sql

# 或者直接执行
psql "postgresql://postgres:postgres@192.168.22.111:54322/postgres" -f supabase/schema.sql
```

**注意：** 请根据你的实际配置修改：
- 密码（默认可能是 `postgres`）
- 端口（本地 Supabase 默认是 `54322`，不是 `5432`）

## 方式 4: 使用 Docker（如果 Supabase 是用 Docker 运行的）

如果你用 Docker 运行 Supabase，可以直接在容器内执行：

```bash
# 找到 Supabase 的数据库容器
docker ps | grep supabase

# 执行 SQL 文件
docker exec -i <container_name> psql -U postgres -d postgres < supabase/schema.sql
```

## 验证表是否创建成功

### 在 Supabase Studio 中验证

1. 打开 http://192.168.22.111:8000/studio
2. 进入 "Table Editor"
3. 应该看到 7 张表

### 使用 SQL 查询验证

在 SQL Editor 中执行：

```sql
-- 查看所有表
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_name IN (
    'assistants',
    'short_term_messages',
    'mid_term_sessions',
    'mid_term_pages',
    'long_term_user_profiles',
    'long_term_user_knowledge',
    'long_term_assistant_knowledge'
  )
ORDER BY table_name;

-- 检查 pgvector 扩展
SELECT * FROM pg_extension WHERE extname = 'vector';

-- 检查 RLS 策略
SELECT tablename, policyname 
FROM pg_policies 
WHERE schemaname = 'public'
ORDER BY tablename, policyname;
```

## 常见问题

### 1. 连接被拒绝

**错误：** `could not connect to server: Connection refused`

**解决：**
- 确认 Supabase 正在运行
- 检查端口是否正确（本地 Supabase 通常用 54322）
- 检查防火墙设置

### 2. 认证失败

**错误：** `password authentication failed`

**解决：**
- 检查数据库密码（默认可能是 `postgres`）
- 查看 Supabase 配置文件中的数据库密码

### 3. 扩展不存在

**错误：** `extension "vector" does not exist`

**解决：**
- 确认 Supabase 版本支持 pgvector
- 手动安装扩展：
  ```sql
  CREATE EXTENSION IF NOT EXISTS vector;
  ```

### 4. 权限不足

**错误：** `permission denied`

**解决：**
- 使用 `postgres` 超级用户执行
- 或使用 Service Role Key（在 Supabase Studio 中执行）

## 下一步

表创建成功后，你可以：

1. **迁移现有 JSON 数据到 Supabase**
   ```bash
   python scripts/migrate_json_to_supabase.py --map user_id_map.json
   ```

2. **在代码中使用 Supabase 存储**
   ```python
   from memcontext import Memcontext
   
   mem = Memcontext(
       user_id="your_user_id",
       storage_backend="supabase",
       supabase_user_id="uuid-from-auth-users",
       supabase_url="http://192.168.22.111:8000",
       supabase_key="your_anon_key",
       # ... 其他参数
   )
   ```

## 参考

- [Supabase 官方文档](https://supabase.com/docs)
- [pgvector 文档](https://github.com/pgvector/pgvector)
- [PostgreSQL RLS 文档](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
