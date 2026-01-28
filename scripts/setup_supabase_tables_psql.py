#!/usr/bin/env python3
"""
使用 psycopg2 直接在 PostgreSQL 中执行 schema.sql（适用于本地 Supabase）

前提条件:
    pip install psycopg2-binary

使用方法:
    python scripts/setup_supabase_tables_psql.py
    
    或者指定连接参数:
    python scripts/setup_supabase_tables_psql.py \\
        --host 192.168.22.111 \\
        --port 54322 \\
        --user postgres \\
        --password postgres \\
        --database postgres
"""

import os
import sys
import argparse
from pathlib import Path

try:
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
except ImportError:
    print("错误: 请先安装 psycopg2: pip install psycopg2-binary")
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


def execute_schema(host: str, port: int, user: str, password: str, database: str):
    """执行 schema.sql"""
    print(f"连接到 PostgreSQL: {host}:{port}/{database}")
    
    try:
        # 连接数据库
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        # 读取 SQL 文件
        sql_content = read_schema_file()
        
        # 执行 SQL（schema.sql 已经包含了 BEGIN/COMMIT，所以不需要额外事务）
        cursor = conn.cursor()
        
        print("正在执行 schema.sql...")
        print("-" * 60)
        
        # 执行 SQL（psycopg2 的 execute 可以执行多语句）
        cursor.execute(sql_content)
        
        cursor.close()
        conn.close()
        
        print("-" * 60)
        print("✅ 表创建成功!")
        print("\n已创建的表:")
        print("  - assistants")
        print("  - short_term_messages")
        print("  - mid_term_sessions")
        print("  - mid_term_pages")
        print("  - long_term_user_profiles")
        print("  - long_term_user_knowledge")
        print("  - long_term_assistant_knowledge")
        
    except psycopg2.OperationalError as e:
        print(f"❌ 连接失败: {e}")
        print("\n请检查:")
        print("  1. Supabase 是否正在运行")
        print("  2. 数据库连接参数是否正确")
        print("  3. 防火墙是否允许连接")
        sys.exit(1)
    except psycopg2.Error as e:
        print(f"❌ SQL 执行失败: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="使用 psycopg2 在 Supabase PostgreSQL 中执行 schema.sql")
    parser.add_argument(
        "--host",
        type=str,
        default=os.getenv("DB_HOST", "192.168.22.111"),
        help="数据库主机 (默认: 192.168.22.111)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("DB_PORT", "54322")),
        help="数据库端口 (默认: 54322，本地 Supabase 通常使用此端口)"
    )
    parser.add_argument(
        "--user",
        type=str,
        default=os.getenv("DB_USER", "postgres"),
        help="数据库用户 (默认: postgres)"
    )
    parser.add_argument(
        "--password",
        type=str,
        default=os.getenv("DB_PASSWORD", "postgres"),
        help="数据库密码 (默认: postgres，请根据实际配置修改)"
    )
    parser.add_argument(
        "--database",
        type=str,
        default=os.getenv("DB_NAME", "postgres"),
        help="数据库名 (默认: postgres)"
    )
    
    args = parser.parse_args()
    
    execute_schema(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database
    )


if __name__ == "__main__":
    main()
