#!/usr/bin/env python3
"""
在本地 Supabase 实例中执行 schema.sql 建表脚本

使用方法:
    python scripts/setup_supabase_tables.py --url http://192.168.22.111:8000 --key YOUR_SERVICE_ROLE_KEY

或者设置环境变量:
    export SUPABASE_URL=http://192.168.22.111:8000
    export SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
    python scripts/setup_supabase_tables.py
"""

import os
import sys
import argparse
from pathlib import Path

try:
    from supabase import create_client, Client
except ImportError:
    print("错误: 请先安装 supabase 库: pip install supabase")
    sys.exit(1)


def read_schema_file():
    """读取 schema.sql 文件"""
    script_dir = Path(__file__).parent
    schema_path = script_dir.parent / "supabase" / "schema.sql"
    
    if not schema_path.exists():
        print(f"错误: 找不到 schema.sql 文件: {schema_path}")
        sys.exit(1)
    
    with open(schema_path, "r", encoding="utf-8") as f:
        return f.read()


def execute_schema(supabase_url: str, service_role_key: str):
    """执行 schema.sql"""
    print(f"连接到 Supabase: {supabase_url}")
    
    # 创建 Supabase 客户端（使用 service_role_key 绕过 RLS）
    supabase: Client = create_client(supabase_url, service_role_key)
    
    # 读取 SQL 文件
    sql_content = read_schema_file()
    
    # 注意：Supabase Python 客户端不直接支持执行原始 SQL
    # 我们需要使用 PostgREST 的 RPC 或者直接连接 PostgreSQL
    # 这里提供一个使用 psycopg2 的替代方案
    
    print("\n⚠️  注意: Supabase Python 客户端不支持直接执行 DDL SQL")
    print("请使用以下方式之一执行 schema.sql:\n")
    
    print("方式 1: 使用 psql 命令行（推荐）")
    print("-" * 60)
    print(f"psql 'postgresql://postgres:postgres@192.168.22.111:54322/postgres' -f supabase/schema.sql")
    print("-" * 60)
    
    print("\n方式 2: 使用 Supabase Studio Web UI")
    print("-" * 60)
    print(f"1. 打开浏览器访问: http://192.168.22.111:8000/studio")
    print("2. 进入 SQL Editor")
    print("3. 复制 supabase/schema.sql 的内容")
    print("4. 粘贴并执行")
    print("-" * 60)
    
    print("\n方式 3: 使用 Python + psycopg2（需要安装 psycopg2）")
    print("-" * 60)
    print("如果安装了 psycopg2，可以使用以下代码:")
    print("""
import psycopg2
from pathlib import Path

schema_path = Path("supabase/schema.sql")
with open(schema_path, "r", encoding="utf-8") as f:
    sql = f.read()

conn = psycopg2.connect(
    host="192.168.22.111",
    port=54322,  # 本地 Supabase 默认端口
    database="postgres",
    user="postgres",
    password="postgres"  # 默认密码，根据你的配置修改
)
conn.autocommit = True
cursor = conn.cursor()
cursor.execute(sql)
cursor.close()
conn.close()
print("✅ 表创建成功!")
    """)
    print("-" * 60)


def main():
    parser = argparse.ArgumentParser(description="在 Supabase 中执行 schema.sql 建表")
    parser.add_argument(
        "--url",
        type=str,
        default=os.getenv("SUPABASE_URL", "http://192.168.22.111:8000"),
        help="Supabase URL (默认从环境变量 SUPABASE_URL 读取)"
    )
    parser.add_argument(
        "--key",
        type=str,
        default=os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
        help="Supabase Service Role Key (默认从环境变量 SUPABASE_SERVICE_ROLE_KEY 读取)"
    )
    
    args = parser.parse_args()
    
    if not args.key:
        print("错误: 请提供 Supabase Service Role Key")
        print("使用方法: python scripts/setup_supabase_tables.py --key YOUR_KEY")
        print("或设置环境变量: export SUPABASE_SERVICE_ROLE_KEY=your_key")
        sys.exit(1)
    
    execute_schema(args.url, args.key)


if __name__ == "__main__":
    main()
