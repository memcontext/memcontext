from __future__ import annotations

"""
SupabaseStore: 基于 Supabase（Postgres + pgvector）的 `MemoryStorage` 实现。

注意：
- 这里假设你已经在 Supabase 中：
  - 安装了 pgvector 扩展；
  - 创建了 `mid_term_sessions` / `mid_term_pages` 两张表；
  - 并在其中分别创建了 `session_embedding` / `page_embedding` 的 vector 列。
- 具体的 URL / SERVICE_ROLE_KEY / 表名等通过外部配置或调用方传入。
"""

import uuid
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence
from urllib.parse import urlparse

import numpy as np
from supabase import Client, create_client

from .base import MemoryStorage
from ..utils import generate_id

try:
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

# 确定性映射：应用内字符串 ID（如 "baojunfei"）→ 数据库 UUID 列
_NAMESPACE_UUID = uuid.uuid5(uuid.NAMESPACE_DNS, "memcontext.local")


def _str_to_uuid(s: str) -> str:
    """将应用内字符串 ID 转为确定性 UUID 字符串，供 DB 的 uuid 列使用。"""
    return str(uuid.uuid5(_NAMESPACE_UUID, s))


def _user_knowledge_row_to_entry(row: Dict[str, Any]) -> Dict[str, Any]:
    """DB 行 (knowledge_text, time_stamp) → 上层期望的 entry (knowledge, timestamp)。"""
    return {
        "knowledge": row.get("knowledge_text") or row.get("knowledge", ""),
        "timestamp": row.get("time_stamp") or row.get("timestamp", ""),
        "knowledge_embedding": row.get("knowledge_embedding"),
    }


def _assistant_knowledge_row_to_entry(row: Dict[str, Any]) -> Dict[str, Any]:
    """DB 行 (knowledge, time_stamp) → 上层期望的 entry (knowledge, timestamp)。"""
    return {
        "knowledge": row.get("knowledge", ""),
        "timestamp": row.get("time_stamp") or row.get("timestamp", ""),
        "knowledge_embedding": row.get("knowledge_embedding"),
    }


class SupabaseStore(MemoryStorage):
    """
    基于 Supabase（Postgres + pgvector）的 MidTerm 存储实现。

    推荐的底层表结构（字段名可根据你实际建表调整）：

    - 表 `mid_term_sessions`：
        - id TEXT PRIMARY KEY
        - user_id TEXT NOT NULL
        - summary TEXT
        - summary_keywords TEXT[]
        - session_embedding vector(2048)
        - L_interaction INTEGER
        - N_visit INTEGER
        - R_recency DOUBLE PRECISION
        - H_segment DOUBLE PRECISION
        - timestamp TEXT / TIMESTAMPTZ
        - last_visit_time TEXT / TIMESTAMPTZ
        - access_count_lfu INTEGER
        - created_at TIMESTAMPTZ DEFAULT now()

    - 表 `mid_term_pages`：
        - id TEXT PRIMARY KEY
        - session_id TEXT REFERENCES mid_term_sessions(id) ON DELETE CASCADE
        - user_id TEXT NOT NULL
        - user_input TEXT
        - agent_response TEXT
        - page_embedding vector(2048)
        - page_keywords TEXT[]
        - timestamp TEXT
        - pre_page TEXT
        - next_page TEXT
        - meta_info JSONB
        - meta_data JSONB
        - preloaded BOOLEAN
        - analyzed BOOLEAN
        - created_at TIMESTAMPTZ DEFAULT now()
    """

    def __init__(
        self,
        *,
        supabase_url: str,
        supabase_key: str,
        embedding_dim: int,
        schema: str = "public",
        mid_sessions_table: str = "sessions",
        mid_pages_table: str = "pages",
        ltm_user_profiles_table: str = "long_term_user_profiles",
        ltm_user_knowledge_table: str = "long_term_user_knowledge",
        ltm_assistant_knowledge_table: str = "long_term_assistant_knowledge",
        short_term_table: str = "short_term",
        auto_create_tables: bool = True,
        create_hnsw_index: bool = False,
        postgres_connection_string: Optional[str] = None,
        postgres_host: Optional[str] = None,
        postgres_port: int = 5432,
        postgres_db: str = "postgres",
        postgres_user: str = "postgres",
        postgres_password: Optional[str] = None,
    ) -> None:
        """
        初始化 Supabase 客户端和表配置。

        参数：
        - auto_create_tables: 如果为 True，会在初始化时检测表是否存在，不存在则自动创建
        - postgres_connection_string: Postgres 连接字符串（如 "postgresql://user:pass@host:port/db"）
        - postgres_host/port/db/user/password: 如果未提供 connection_string，会尝试从这些参数构建连接
        """
        self._supabase_url = supabase_url
        self._supabase_key = supabase_key
        self._embedding_dim = embedding_dim
        self._schema = schema
        self._mid_sessions_table = mid_sessions_table
        self._mid_pages_table = mid_pages_table
        self._ltm_user_profiles_table = ltm_user_profiles_table
        self._ltm_user_knowledge_table = ltm_user_knowledge_table
        self._ltm_assistant_knowledge_table = ltm_assistant_knowledge_table
        self._short_term_table = short_term_table

        # 创建 Supabase 客户端
        self._client: Client = create_client(self._supabase_url, self._supabase_key)

        # 可选：是否在 DB 上创建 HNSW 索引以加速向量检索
        self._create_hnsw_index = create_hnsw_index

        # 自动建表（如果启用）
        if auto_create_tables:
            self._postgres_conn_str = postgres_connection_string
            self._postgres_host = postgres_host
            self._postgres_port = postgres_port
            self._postgres_db = postgres_db
            self._postgres_user = postgres_user
            self._postgres_password = postgres_password
            # _ensure_tables_exist() 内部已处理异常并打印 SQL，不会抛出异常
            self._ensure_tables_exist()

    # ------- 内部辅助 -------

    def _sessions_table(self) -> str:
        return f"{self._schema}.{self._mid_sessions_table}" if self._schema else self._mid_sessions_table

    def _pages_table(self) -> str:
        return f"{self._schema}.{self._mid_pages_table}" if self._schema else self._mid_pages_table

    def _get_postgres_connection_string(self) -> Optional[str]:
        """构建 Postgres 连接字符串。"""
        if self._postgres_conn_str:
            return self._postgres_conn_str

        # 尝试从 Supabase URL 推断 Postgres 主机
        if not self._postgres_host:
            parsed = urlparse(self._supabase_url)
            # 对于本地部署（如 http://192.168.22.111:8000），Postgres 通常在 5432
            if parsed.hostname and "localhost" in parsed.hostname or "127.0.0.1" in parsed.hostname:
                host = "localhost"
            elif parsed.hostname:
                host = parsed.hostname
            else:
                return None
        else:
            host = self._postgres_host

        # 构建连接字符串
        if self._postgres_password:
            return f"postgresql://{self._postgres_user}:{self._postgres_password}@{host}:{self._postgres_port}/{self._postgres_db}"
        else:
            # 如果没有密码，尝试无密码连接（本地开发常见）
            return f"postgresql://{self._postgres_user}@{host}:{self._postgres_port}/{self._postgres_db}"

    def _table_exists(self, table_name: str) -> bool:
        """检测表是否存在（通过 Supabase REST API）。"""
        try:
            # 尝试查询表的第一行，如果表不存在会报错
            self._client.table(table_name).select("*").limit(1).execute()
            return True
        except Exception:
            # 表不存在或其他错误
            return False

    def _ensure_tables_exist(self) -> None:
        """确保所有需要的表都存在，不存在则创建。"""
        # 已移除自动建表逻辑。请在 Supabase SQL Editor 中执行 doc/supabase_setup.sql（仅需执行一次）
        print("Auto-create disabled. Please execute 'doc/supabase_setup.sql' in Supabase SQL Editor to create required tables, RPCs and optional indexes (run once).")
        return
#         if not PSYCOPG2_AVAILABLE:
#             print("Warning: psycopg2 not installed. Cannot auto-create tables.")
#             print("Please install: pip install psycopg2-binary")
#             return

#         conn_str = self._get_postgres_connection_string()
#         if not conn_str:
#             print("Warning: Cannot determine Postgres connection info. Skipping auto-create tables.")
#             print("Please provide postgres_connection_string or postgres_host/password in SupabaseStore.__init__")
#             return

#         # 生成建表 SQL（用于手动执行或自动执行）
#         create_table_sqls = []

#         # 确保 pgvector 扩展
#         create_table_sqls.append("CREATE EXTENSION IF NOT EXISTS vector;")

#         # 检查表是否存在，如果检查失败（网络问题等），默认认为表不存在，生成建表 SQL
#         # 1. sessions 表
#         try:
#             table_exists = self._table_exists(self._mid_sessions_table)
#         except Exception:
#             table_exists = False  # 检查失败，默认认为表不存在
#         if not table_exists:
#             sql = f"""
# CREATE TABLE IF NOT EXISTS {self._schema}.{self._mid_sessions_table} (
#     session_id TEXT PRIMARY KEY,
#     user_id UUID NOT NULL,
#     summary TEXT,
#     summary_keywords JSONB,
#     summary_embedding vector({self._embedding_dim}),
#     l_interaction INTEGER DEFAULT 0,
#     n_visit INTEGER DEFAULT 0,
#     r_recency DOUBLE PRECISION DEFAULT 1.0,
#     h_segment DOUBLE PRECISION DEFAULT 0.0,
#     last_visit_time TIMESTAMPTZ,
#     access_count_lfu BIGINT DEFAULT 0,
#     created_at TIMESTAMPTZ DEFAULT NOW()
# );
# """
#             create_table_sqls.append(sql)

#         # 2. pages 表
#         try:
#             table_exists = self._table_exists(self._mid_pages_table)
#         except Exception:
#             table_exists = False
#         if not table_exists:
#             sql = f"""
# CREATE TABLE IF NOT EXISTS {self._schema}.{self._mid_pages_table} (
#     page_id TEXT PRIMARY KEY,
#     session_id TEXT NOT NULL,
#     user_id UUID NOT NULL,
#     user_input TEXT,
#     agent_response TEXT,
#     time_stamp TIMESTAMPTZ,
#     preloaded BOOLEAN DEFAULT FALSE,
#     analyzed BOOLEAN DEFAULT FALSE,
#     pre_page_id TEXT,
#     next_page_id TEXT,
#     meta_info TEXT,
#     meta_data JSONB,
#     page_keywords JSONB,
#     page_embedding vector({self._embedding_dim}),
#     created_at TIMESTAMPTZ DEFAULT NOW()
# );
# """
#             create_table_sqls.append(sql)

#         # 3. long_term_user_profiles 表
#         try:
#             table_exists = self._table_exists(self._ltm_user_profiles_table)
#         except Exception:
#             table_exists = False
#         if not table_exists:
#             sql = f"""
# CREATE TABLE IF NOT EXISTS {self._schema}.{self._ltm_user_profiles_table} (
#     user_id UUID PRIMARY KEY,
#     profile_data TEXT,
#     last_updated TIMESTAMPTZ DEFAULT NOW()
# );
# """
#             create_table_sqls.append(sql)

#         # 4. long_term_user_knowledge 表
#         try:
#             table_exists = self._table_exists(self._ltm_user_knowledge_table)
#         except Exception:
#             table_exists = False
#         if not table_exists:
#             sql = f"""
# CREATE TABLE IF NOT EXISTS {self._schema}.{self._ltm_user_knowledge_table} (
#     id TEXT PRIMARY KEY,
#     user_id UUID NOT NULL,
#     knowledge_text TEXT,
#     time_stamp TIMESTAMPTZ DEFAULT NOW(),
#     knowledge_embedding vector({self._embedding_dim})
# );
# """
#             create_table_sqls.append(sql)

#         # 5. long_term_assistant_knowledge 表
#         try:
#             table_exists = self._table_exists(self._ltm_assistant_knowledge_table)
#         except Exception:
#             table_exists = False
#         if not table_exists:
#             sql = f"""
# CREATE TABLE IF NOT EXISTS {self._schema}.{self._ltm_assistant_knowledge_table} (
#     id TEXT PRIMARY KEY,
#     assistant_id UUID NOT NULL,
#     user_id UUID,
#     knowledge TEXT,
#     time_stamp TIMESTAMPTZ DEFAULT NOW(),
#     knowledge_embedding vector({self._embedding_dim})
# );
# """
#             create_table_sqls.append(sql)

#         # 如果没有需要创建的表，直接返回
#         if len(create_table_sqls) <= 1:  # 只有 pgvector 扩展
#             print("All required tables already exist.")
#             return

#         # 取消自动在代码中执行建表/建索引；改为打印出 SQL，供用户在 Supabase SQL Editor 中手动执行。
#         # （在很多环境下自动连接数据库并创建表/索引有权限和安全风险，交由用户在控制台执行更安全可控。）
#         if getattr(self, "_create_hnsw_index", False):
#             # 将索引 SQL 也加入要打印的 SQL 列表，以便用户一并执行
#             create_table_sqls.append(
#                 f\"CREATE INDEX IF NOT EXISTS idx_{self._mid_sessions_table}_summary_embedding ON {self._schema}.{self._mid_sessions_table} USING hnsw (summary_embedding vector_cosine_ops);\"
#             )
#             create_table_sqls.append(
#                 f\"CREATE INDEX IF NOT EXISTS idx_{self._mid_pages_table}_page_embedding ON {self._schema}.{self._mid_pages_table} USING hnsw (page_embedding vector_cosine_ops);\"
#             )
#             create_table_sqls.append(
#                 f\"CREATE INDEX IF NOT EXISTS idx_{self._ltm_user_knowledge_table}_knowledge_embedding ON {self._schema}.{self._ltm_user_knowledge_table} USING hnsw (knowledge_embedding vector_cosine_ops);\"
#             )
#             create_table_sqls.append(
#                 f\"CREATE INDEX IF NOT EXISTS idx_{self._ltm_assistant_knowledge_table}_knowledge_embedding ON {self._schema}.{self._ltm_assistant_knowledge_table} USING hnsw (knowledge_embedding vector_cosine_ops);\"
#             )

#         print(\"Warning: auto-create-tables is disabled in code. Please execute the following SQL in Supabase SQL Editor:\")\n+        print(\"\\n\" + \"=\" * 80)\n+        for sql in create_table_sqls:\n+            print(sql)\n+            print(\"\\n\")\n+        print(\"=\" * 80)\n+        print(\"After executing the SQL above in Supabase SQL Editor, restart the application.\")\n+        return

    @staticmethod
    def _to_vector(value: Optional[Sequence[float]], dim: int) -> Optional[List[float]]:
        """
        将传入的 embedding 归一化为固定长度 list[float]；长度不匹配时做简单截断/补零。
        """
        if value is None:
            return None
        arr = np.array(value, dtype=np.float32)
        if arr.ndim != 1:
            arr = arr.reshape(-1)
        if arr.size > dim:
            arr = arr[:dim]
        elif arr.size < dim:
            pad = np.zeros(dim - arr.size, dtype=np.float32)
            arr = np.concatenate([arr, pad])
        return arr.tolist()

    @staticmethod
    def _parse_vector_value(value: Any) -> Optional[List[float]]:
        """
        将从 Supabase/PostgREST 返回的 vector 值解析为 List[float]。

        说明：pgvector 经 PostgREST 返回时，常见形式是字符串，如：
        - "[0.1,0.2,...]"
        - "(0.1,0.2,...)"
        也可能已经是 list/tuple。
        """
        if value is None:
            return None

        # 已经是 list/tuple
        if isinstance(value, (list, tuple)):
            try:
                return [float(x) for x in value]
            except Exception:
                return None

        # 可能是字符串形式
        if isinstance(value, str):
            s = value.strip()
            if not s:
                return None
            try:
                # JSON array: "[...]"
                if s.startswith("[") and s.endswith("]"):
                    import json

                    arr = json.loads(s)
                    if isinstance(arr, list):
                        return [float(x) for x in arr]
                    return None
                # pgvector: "(...)"
                if s.startswith("(") and s.endswith(")"):
                    inner = s[1:-1].strip()
                    if not inner:
                        return []
                    parts = [p.strip() for p in inner.split(",")]
                    return [float(p) for p in parts if p != ""]
            except Exception:
                return None

        return None

    def _embedding_to_rpc_str(self, embedding: Sequence[float]) -> str:
        """
        将 embedding 转为 pgvector RPC 所需的字符串格式 "[x,y,z,...]"。
        """
        vec = self._to_vector(embedding, self._embedding_dim)
        if vec is None:
            return "[]"
        return "[" + ",".join(str(x) for x in vec) + "]"

    # ---------- Long-term memory: user profiles ----------

    def upsert_user_profile(self, user_id: str, profile_text: str, last_updated: str) -> None:
        """
        更新或插入长期用户画像。
        表：long_term_user_profiles(user_id, profile_data, last_updated)
        """
        row = {
            "user_id": _str_to_uuid(user_id),
            "profile_data": profile_text,
            "last_updated": last_updated,
        }
        self._client.table(self._ltm_user_profiles_table).upsert(row).execute()

    def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户画像记录。
        """
        resp = (
            self._client.table(self._ltm_user_profiles_table)
            .select("*")
            .eq("user_id", _str_to_uuid(user_id))
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        if not rows:
            return {}
        row = rows[0]
        return {
            "data": row.get("profile_data"),
            "last_updated": row.get("last_updated"),
        }

    # ---------- Long-term memory: user knowledge ----------

    def add_user_knowledge(
        self,
        user_id: str,
        knowledge_text: str,
        embedding: Sequence[float],
        timestamp: str,
    ) -> None:
        """
        向 long_term_user_knowledge 表添加一条用户知识。
        表结构：id, user_id, knowledge_text, time_stamp, knowledge_embedding
        """
        row = {
            "id": generate_id("ltm_user_kn"),
            "user_id": _str_to_uuid(user_id),
            "knowledge_text": knowledge_text,
            "time_stamp": timestamp,
            "knowledge_embedding": self._to_vector(embedding, self._embedding_dim),
        }
        self._client.table(self._ltm_user_knowledge_table).insert(row).execute()

    def get_user_knowledge(self, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取用户知识列表，按时间倒序，最多 limit 条。
        """
        resp = (
            self._client.table(self._ltm_user_knowledge_table)
            .select("*")
            .eq("user_id", _str_to_uuid(user_id))
            .order("time_stamp", desc=True)
            .limit(limit)
            .execute()
        )
        rows = resp.data or []
        return [_user_knowledge_row_to_entry(r) for r in rows]

    def search_user_knowledge_by_embedding(
        self,
        user_id: str,
        query_embedding: Sequence[float],
        threshold: float,
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """
        优先使用 pgvector RPC 在 DB 侧做相似度检索；RPC 不可用时回退到本地向量运算。
        """
        try:
            resp = self._client.rpc(
                "match_user_knowledge_by_embedding",
                {
                    "p_user_id": _str_to_uuid(user_id),
                    "p_query_embedding": self._embedding_to_rpc_str(query_embedding),
                    "p_sim_threshold": float(threshold),
                    "p_limit": int(top_k),
                },
            ).execute()
            rows = resp.data or []
            return [_user_knowledge_row_to_entry(r) for r in rows]
        except Exception:
            pass
        # 回退：本地全量拉取 + 相似度计算
        q_vec = np.array(query_embedding, dtype=np.float32)
        if q_vec.ndim != 1:
            q_vec = q_vec.reshape(-1)

        resp = (
            self._client.table(self._ltm_user_knowledge_table)
            .select("*")
            .eq("user_id", _str_to_uuid(user_id))
            .execute()
        )
        rows = resp.data or []
        if not rows:
            return []

        scored: List[Dict[str, Any]] = []
        for row in rows:
            emb = self._parse_vector_value(row.get("knowledge_embedding"))
            if not emb:
                continue
            v = np.array(emb, dtype=np.float32)
            if v.ndim != 1:
                v = v.reshape(-1)
            sim = float(np.dot(v, q_vec) / (np.linalg.norm(v) * np.linalg.norm(q_vec) + 1e-8))
            if sim < threshold:
                continue
            scored.append({"entry": row, "score": sim})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return [_user_knowledge_row_to_entry(s["entry"]) for s in scored[:top_k]]

    # ---------- Long-term memory: assistant knowledge ----------

    def add_assistant_knowledge(
        self,
        assistant_id: str,
        knowledge_text: str,
        embedding: Sequence[float],
        timestamp: str,
        user_id: Optional[str] = None,
    ) -> None:
        """
        向 long_term_assistant_knowledge 表添加一条助手知识。
        表结构：id, assistant_id, user_id, knowledge, time_stamp, knowledge_embedding
        user_id 用于区分不同用户的助手知识；为 None 时表示全局助手知识。
        """
        row = {
            "id": generate_id("ltm_assistant_kn"),
            "assistant_id": _str_to_uuid(assistant_id),
            "user_id": _str_to_uuid(user_id) if user_id else None,
            "knowledge": knowledge_text,
            "time_stamp": timestamp,
            "knowledge_embedding": self._to_vector(embedding, self._embedding_dim),
        }
        self._client.table(self._ltm_assistant_knowledge_table).insert(row).execute()

    def get_assistant_knowledge(
        self,
        assistant_id: str,
        limit: int = 100,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取助手知识列表，按时间倒序，最多 limit 条。
        user_id 不为空时仅返回该用户的助手知识。
        """
        q = (
            self._client.table(self._ltm_assistant_knowledge_table)
            .select("*")
            .eq("assistant_id", _str_to_uuid(assistant_id))
            .order("time_stamp", desc=True)
            .limit(limit)
        )
        if user_id is not None:
            q = q.eq("user_id", _str_to_uuid(user_id))
        resp = q.execute()
        rows = resp.data or []
        return [_assistant_knowledge_row_to_entry(r) for r in rows]

    def search_assistant_knowledge_by_embedding(
        self,
        assistant_id: str,
        query_embedding: Sequence[float],
        threshold: float,
        top_k: int,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        优先使用 pgvector RPC 在 DB 侧做相似度检索；RPC 不可用时回退到本地向量运算。
        user_id 不为空时仅检索该用户的助手知识。
        """
        try:
            rpc_params = {
                "p_assistant_id": _str_to_uuid(assistant_id),
                "p_query_embedding": self._embedding_to_rpc_str(query_embedding),
                "p_sim_threshold": float(threshold),
                "p_limit": int(top_k),
            }
            if user_id is not None:
                rpc_params["p_user_id"] = _str_to_uuid(user_id)
            resp = self._client.rpc(
                "match_assistant_knowledge_by_embedding",
                rpc_params,
            ).execute()
            rows = resp.data or []
            return [_assistant_knowledge_row_to_entry(r) for r in rows]
        except Exception:
            pass
        # 回退：本地全量拉取 + 相似度计算
        q_vec = np.array(query_embedding, dtype=np.float32)
        if q_vec.ndim != 1:
            q_vec = q_vec.reshape(-1)

        q = (
            self._client.table(self._ltm_assistant_knowledge_table)
            .select("*")
            .eq("assistant_id", _str_to_uuid(assistant_id))
        )
        if user_id is not None:
            q = q.eq("user_id", _str_to_uuid(user_id))
        resp = q.execute()
        rows = resp.data or []
        if not rows:
            return []

        scored: List[Dict[str, Any]] = []
        for row in rows:
            emb = self._parse_vector_value(row.get("knowledge_embedding"))
            if not emb:
                continue
            v = np.array(emb, dtype=np.float32)
            if v.ndim != 1:
                v = v.reshape(-1)
            sim = float(np.dot(v, q_vec) / (np.linalg.norm(v) * np.linalg.norm(q_vec) + 1e-8))
            if sim < threshold:
                continue
            scored.append({"entry": row, "score": sim})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return [_assistant_knowledge_row_to_entry(s["entry"]) for s in scored[:top_k]]

    # ---------- 短期记忆 (short_term) ----------

    def load_short_term_items(self, user_id: str) -> List[Dict[str, Any]]:
        """按 user_id 加载短期记忆 QA 对列表，按 created_at 升序（最旧在前）。"""
        resp = (
            self._client.table(self._short_term_table)
            .select("*")
            .eq("user_id", _str_to_uuid(user_id))
            .order("created_at", desc=False)
            .execute()
        )
        rows = resp.data or []
        return [
            {
                "user_input": r.get("user_input"),
                "agent_response": r.get("agent_response"),
                "timestamp": r.get("time_stamp") or r.get("timestamp", ""),
                "meta_data": r.get("meta_data") or {},
            }
            for r in rows
        ]

    def add_short_term_item(self, user_id: str, qa_pair: Dict[str, Any]) -> None:
        """插入一条短期 QA 对。"""
        item_id = generate_id("st")
        row = {
            "id": item_id,
            "user_id": _str_to_uuid(user_id),
            "user_input": qa_pair.get("user_input"),
            "agent_response": qa_pair.get("agent_response"),
            "time_stamp": qa_pair.get("timestamp", ""),
            "meta_data": qa_pair.get("meta_data") or {},
        }
        self._client.table(self._short_term_table).insert(row).execute()

    def pop_oldest_short_term_item(self, user_id: str) -> Optional[Dict[str, Any]]:
        """删除该用户最早的一条短期记录并返回其内容；若无则返回 None。"""
        resp = (
            self._client.table(self._short_term_table)
            .select("*")
            .eq("user_id", _str_to_uuid(user_id))
            .order("created_at", desc=False)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        if not rows:
            return None
        row = rows[0]
        self._client.table(self._short_term_table).delete().eq(
            "id", row["id"]
        ).execute()
        return {
            "user_input": row.get("user_input"),
            "agent_response": row.get("agent_response"),
            "timestamp": row.get("time_stamp") or row.get("timestamp", ""),
            "meta_data": row.get("meta_data") or {},
        }

    def count_short_term_items(self, user_id: str) -> int:
        """返回该用户短期记忆条数。"""
        items = self.load_short_term_items(user_id)
        return len(items)

    # ---------- 会话加载 / 元信息 ----------

    def load_sessions_meta(self, user_id: str) -> Mapping[str, Dict[str, Any]]:
        """
        从 Supabase 加载某个用户的所有 mid-term session 元信息。
        """
        resp = (
            self._client.table(self._mid_sessions_table)
            .select("*")
            .eq("user_id", _str_to_uuid(user_id))
            .execute()
        )
        rows = resp.data or []

        sessions: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            # 数据表使用 session_id 作为主键
            sid = row.get("session_id")
            if not sid:
                continue

            meta: Dict[str, Any] = {
                "id": sid,
                "summary": row.get("summary"),
                "summary_keywords": row.get("summary_keywords") or [],
                "summary_embedding": self._parse_vector_value(row.get("summary_embedding")),
                "L_interaction": row.get("l_interaction", 0),
                "N_visit": row.get("n_visit", 0),
                "R_recency": row.get("r_recency", 1.0),
                "H_segment": row.get("h_segment", 0.0),
                # sessions 表里没有单独的 timestamp 字段，必要时可用 created_at
                "timestamp": row.get("created_at"),
                "last_visit_time": row.get("last_visit_time"),
                "access_count_lfu": row.get("access_count_lfu", 0),
                # details 不在这里加载，由上层按需单独获取
            }
            sessions[sid] = meta

        return sessions

    def load_session_pages(self, user_id: str, session_id: str) -> List[Dict[str, Any]]:
        """
        从 pages 表加载某个 session 的全部 pages，用于填充 session["details"]。
        """
        resp = (
            self._client.table(self._mid_pages_table)
            .select("*")
            .eq("user_id", _str_to_uuid(user_id))
            .eq("session_id", session_id)
            .order("time_stamp", desc=False)
            .execute()
        )
        rows = resp.data or []
        details: List[Dict[str, Any]] = []
        for row in rows:
            details.append(
                {
                    "page_id": row.get("page_id"),
                    "user_input": row.get("user_input"),
                    "agent_response": row.get("agent_response"),
                    "timestamp": row.get("time_stamp"),
                    "preloaded": bool(row.get("preloaded", False)),
                    "analyzed": bool(row.get("analyzed", False)),
                    "pre_page": row.get("pre_page_id"),
                    "next_page": row.get("next_page_id"),
                    "meta_info": row.get("meta_info"),
                    "meta_data": row.get("meta_data") or {},
                    "page_keywords": row.get("page_keywords") or [],
                    "page_embedding": self._parse_vector_value(row.get("page_embedding")),
                }
            )
        return details

    # ---------- 写入 / 更新 ----------

    def save_session_batch(
        self,
        user_id: str,
        sessions: Iterable[Dict[str, Any]],
    ) -> None:
        """
        批量保存一批 session 及其 pages。

        实现策略（简单版本）：
        - 对所有 session 生成 mid_term_sessions 行；
        - 删除这些 session_id 对应的旧 pages；
        - 再插入新的 pages。
        """
        sessions = list(sessions)  # materialize 迭代器
        if not sessions:
            return None

        # 按 session_id / page_id 去重，避免同一批次 upsert 出现重复键（PostgreSQL 21000）
        session_rows_by_id: Dict[str, Dict[str, Any]] = {}
        page_rows_by_id: Dict[str, Dict[str, Any]] = {}
        session_ids: List[str] = []

        for s in sessions:
            sid = s.get("id") or generate_id("session")
            s["id"] = sid
            session_ids.append(sid)

            session_rows_by_id[sid] = {
                "session_id": sid,
                "user_id": _str_to_uuid(user_id),
                "summary": s.get("summary"),
                "summary_keywords": s.get("summary_keywords") or [],
                "summary_embedding": self._to_vector(
                    s.get("summary_embedding"), self._embedding_dim
                ),
                "l_interaction": s.get("L_interaction", 0),
                "n_visit": s.get("N_visit", 0),
                "r_recency": s.get("R_recency", 1.0),
                "h_segment": s.get("H_segment", 0.0),
                "last_visit_time": s.get("last_visit_time"),
                "access_count_lfu": s.get("access_count_lfu", 0),
            }

            for page in s.get("details", []) or []:
                pid = page.get("page_id") or generate_id("page")
                page_rows_by_id[pid] = {
                    "page_id": pid,
                    "session_id": sid,
                    "user_id": _str_to_uuid(user_id),
                    "user_input": page.get("user_input"),
                    "agent_response": page.get("agent_response"),
                    "time_stamp": page.get("timestamp"),
                    "preloaded": page.get("preloaded", False),
                    "analyzed": page.get("analyzed", False),
                    "pre_page_id": page.get("pre_page"),
                    "next_page_id": page.get("next_page"),
                    "meta_info": page.get("meta_info"),
                    "meta_data": page.get("meta_data"),
                    "page_keywords": page.get("page_keywords") or [],
                    "page_embedding": self._to_vector(
                        page.get("page_embedding"), self._embedding_dim
                    ),
                }

        session_rows = list(session_rows_by_id.values())
        page_rows = list(page_rows_by_id.values())

        # upsert sessions
        if session_rows:
            self._client.table(self._mid_sessions_table).upsert(
                session_rows
            ).execute()

        # 清理旧 pages
        unique_session_ids = list(set(session_ids))
        for sid in unique_session_ids:
            self._client.table(self._mid_pages_table).delete().eq(
                "user_id", _str_to_uuid(user_id)
            ).eq("session_id", sid).execute()

        # 插入新 pages
        if page_rows:
            self._client.table(self._mid_pages_table).upsert(page_rows).execute()

        return None

    def upsert_session_with_pages(
        self,
        user_id: str,
        session: Dict[str, Any],
        pages: Sequence[Dict[str, Any]],
    ) -> str:
        """
        插入或更新一个 session 以及它的一组 pages，返回最终的 session_id。
        """
        sid = session.get("id") or generate_id("session")
        session["id"] = sid

        session_row = {
            "session_id": sid,
            "user_id": _str_to_uuid(user_id),
            "summary": session.get("summary"),
            "summary_keywords": session.get("summary_keywords") or [],
            "summary_embedding": self._to_vector(
                session.get("summary_embedding"), self._embedding_dim
            ),
            "l_interaction": session.get("L_interaction", 0),
            "n_visit": session.get("N_visit", 0),
            "r_recency": session.get("R_recency", 1.0),
            "h_segment": session.get("H_segment", 0.0),
            "last_visit_time": session.get("last_visit_time"),
            "access_count_lfu": session.get("access_count_lfu", 0),
        }

        self._client.table(self._mid_sessions_table).upsert([session_row]).execute()

        page_rows: List[Dict[str, Any]] = []
        for page in pages:
            pid = page.get("page_id") or generate_id("page")
            page_rows.append(
                {
                    "page_id": pid,
                    "session_id": sid,
                    "user_id": _str_to_uuid(user_id),
                    "user_input": page.get("user_input"),
                    "agent_response": page.get("agent_response"),
                    "time_stamp": page.get("timestamp"),
                    "preloaded": page.get("preloaded", False),
                    "analyzed": page.get("analyzed", False),
                    "pre_page_id": page.get("pre_page"),
                    "next_page_id": page.get("next_page"),
                    "meta_info": page.get("meta_info"),
                    "meta_data": page.get("meta_data"),
                    "page_keywords": page.get("page_keywords") or [],
                    "page_embedding": self._to_vector(
                        page.get("page_embedding"), self._embedding_dim
                    ),
                }
            )

        if page_rows:
            self._client.table(self._mid_pages_table).upsert(page_rows).execute()

        return sid

    def append_pages_to_session(
        self,
        user_id: str,
        session_id: str,
        pages: Sequence[Dict[str, Any]],
    ) -> None:
        """
        向已有 session 追加 pages。
        """
        if not pages:
            return None

        page_rows: List[Dict[str, Any]] = []
        for page in pages:
            pid = page.get("page_id") or generate_id("page")
            page_rows.append(
                {
                    "page_id": pid,
                    "session_id": session_id,
                    "user_id": _str_to_uuid(user_id),
                    "user_input": page.get("user_input"),
                    "agent_response": page.get("agent_response"),
                    "time_stamp": page.get("timestamp"),
                    "preloaded": page.get("preloaded", False),
                    "analyzed": page.get("analyzed", False),
                    "pre_page_id": page.get("pre_page"),
                    "next_page_id": page.get("next_page"),
                    "meta_info": page.get("meta_info"),
                    "meta_data": page.get("meta_data"),
                    "page_keywords": page.get("page_keywords") or [],
                    "page_embedding": self._to_vector(
                        page.get("page_embedding"), self._embedding_dim
                    ),
                }
            )

        self._client.table(self._mid_pages_table).upsert(page_rows).execute()
        return None

    def update_session_stats(
        self,
        user_id: str,
        session_id: str,
        stats: Mapping[str, Any],
    ) -> None:
        """
        更新 session 的热度 / 访问统计等轻量字段。
        """
        # 字段名映射：内存中的字段名 -> 数据库列名
        field_mapping = {
            "N_visit": "n_visit",
            "L_interaction": "l_interaction",
            "R_recency": "r_recency",
            "H_segment": "h_segment",
            "last_visit_time": "last_visit_time",
            "access_count_lfu": "access_count_lfu",
        }
        
        allowed_fields = set(field_mapping.keys())
        update_payload = {}
        for k, v in stats.items():
            if k in allowed_fields:
                # 使用数据库列名（小写）
                update_payload[field_mapping[k]] = v
        
        if not update_payload:
            return None

        (
            self._client.table(self._mid_sessions_table)
            .update(update_payload)
            .eq("user_id", _str_to_uuid(user_id))
            .eq("session_id", session_id)
            .execute()
        )
        return None

    def delete_session(
        self,
        user_id: str,
        session_id: str,
    ) -> None:
        """
        删除一个 session 及其 pages。
        """
        # 如果没有设置 ON DELETE CASCADE，可以先删 pages
        self._client.table(self._mid_pages_table).delete().eq(
            "user_id", _str_to_uuid(user_id)
        ).eq("session_id", session_id).execute()

        self._client.table(self._mid_sessions_table).delete().eq(
            "user_id", _str_to_uuid(user_id)
        ).eq("session_id", session_id).execute()
        return None

    # ---------- 检索 ----------

    def search_sessions_by_embedding(
        self,
        user_id: str,
        query_embedding: Sequence[float],
        segment_similarity_threshold: float,
        page_similarity_threshold: float,
        top_k_sessions: int,
        keyword_alpha: float = 1.0,
        query_keywords: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        优先使用 pgvector RPC 在 DB 侧做 session/page 向量检索；RPC 不可用时回退到本地全量拉取+相似度计算。
        """
        q_vec = np.array(query_embedding, dtype=np.float32)
        if q_vec.ndim != 1:
            q_vec = q_vec.reshape(-1)
        query_kw_set = set(query_keywords or [])

        # 优先走 RPC：session 按向量相似度取 top_k，再对每个 session 用 RPC 取 pages
        try:
            session_resp = self._client.rpc(
                "match_sessions_by_embedding",
                {
                    "p_user_id": _str_to_uuid(user_id),
                    "p_query_embedding": self._embedding_to_rpc_str(query_embedding),
                    "p_limit": int(top_k_sessions),
                },
            ).execute()
            session_rows = session_resp.data or []
            if not session_rows:
                return []

            # 为每个 session 算语义分 + 可选关键词分，过滤并取 top_k
            scored_sessions: List[Dict[str, Any]] = []
            for row in session_rows:
                sid = row.get("session_id")
                if not sid:
                    continue
                emb = self._parse_vector_value(row.get("summary_embedding"))
                if not emb:
                    continue
                s_vec = np.array(emb, dtype=np.float32)
                if s_vec.ndim != 1:
                    s_vec = s_vec.reshape(-1)
                sim = float(
                    np.dot(s_vec, q_vec)
                    / (np.linalg.norm(s_vec) * np.linalg.norm(q_vec) + 1e-8)
                )
                s_keywords = set(row.get("summary_keywords") or [])
                kw_score = 0.0
                if query_kw_set and s_keywords:
                    inter = len(query_kw_set & s_keywords)
                    union = len(query_kw_set | s_keywords)
                    if union > 0:
                        kw_score = inter / union
                overall = sim + keyword_alpha * kw_score
                if overall < segment_similarity_threshold:
                    continue
                scored_sessions.append(
                    {"row": row, "session_id": sid, "semantic_sim": sim, "overall_score": overall}
                )
            scored_sessions.sort(key=lambda x: x["overall_score"], reverse=True)
            top_sessions = scored_sessions[:top_k_sessions]

            results: List[Dict[str, Any]] = []
            for s in top_sessions:
                sid = s["session_id"]
                pages_resp = self._client.rpc(
                    "match_pages_by_embedding",
                    {
                        "p_user_id": _str_to_uuid(user_id),
                        "p_session_id": sid,
                        "p_query_embedding": self._embedding_to_rpc_str(query_embedding),
                        "p_sim_threshold": float(page_similarity_threshold),
                        "p_limit": 50,
                    },
                ).execute()
                page_rows = pages_resp.data or []
                matched_pages = []
                for page in page_rows:
                    p_emb = self._parse_vector_value(page.get("page_embedding"))
                    if not p_emb:
                        continue
                    p_vec = np.array(p_emb, dtype=np.float32)
                    if p_vec.ndim != 1:
                        p_vec = p_vec.reshape(-1)
                    p_sim = float(
                        np.dot(p_vec, q_vec)
                        / (np.linalg.norm(p_vec) * np.linalg.norm(q_vec) + 1e-8)
                    )
                    if p_sim < page_similarity_threshold:
                        continue
                    matched_pages.append({"page_data": page, "score": p_sim})
                if not matched_pages:
                    continue
                matched_pages.sort(key=lambda x: x["score"], reverse=True)
                results.append(
                    {
                        "session_id": sid,
                        "session_summary": s["row"].get("summary"),
                        "session_relevance_score": s["overall_score"],
                        "matched_pages": matched_pages,
                    }
                )
            results.sort(key=lambda x: x["session_relevance_score"], reverse=True)
            return results
        except Exception:
            pass

        # 回退：本地全量拉取 + 相似度计算
        sessions_resp = (
            self._client.table(self._mid_sessions_table)
            .select("*")
            .eq("user_id", _str_to_uuid(user_id))
            .execute()
        )
        session_rows = sessions_resp.data or []
        if not session_rows:
            return []

        scored_sessions = []
        for row in session_rows:
            sid = row.get("session_id")
            if not sid:
                continue
            emb = self._parse_vector_value(row.get("summary_embedding"))
            if not emb:
                continue
            s_vec = np.array(emb, dtype=np.float32)
            if s_vec.ndim != 1:
                s_vec = s_vec.reshape(-1)
            sim = float(np.dot(s_vec, q_vec) / (np.linalg.norm(s_vec) * np.linalg.norm(q_vec) + 1e-8))
            s_keywords = set(row.get("summary_keywords") or [])
            kw_score = 0.0
            if query_kw_set and s_keywords:
                inter = len(query_kw_set & s_keywords)
                union = len(query_kw_set | s_keywords)
                if union > 0:
                    kw_score = inter / union
            overall = sim + keyword_alpha * kw_score
            if overall < segment_similarity_threshold:
                continue
            scored_sessions.append(
                {"row": row, "session_id": sid, "semantic_sim": sim, "overall_score": overall}
            )
        if not scored_sessions:
            return []
        scored_sessions.sort(key=lambda x: x["overall_score"], reverse=True)
        top_sessions = scored_sessions[:top_k_sessions]

        results = []
        for s in top_sessions:
            sid = s["session_id"]
            pages_resp = (
                self._client.table(self._mid_pages_table)
                .select("*")
                .eq("user_id", _str_to_uuid(user_id))
                .eq("session_id", sid)
                .execute()
            )
            page_rows = pages_resp.data or []
            matched_pages = []
            for page in page_rows:
                p_emb = self._parse_vector_value(page.get("page_embedding"))
                if not p_emb:
                    continue
                p_vec = np.array(p_emb, dtype=np.float32)
                if p_vec.ndim != 1:
                    p_vec = p_vec.reshape(-1)
                p_sim = float(
                    np.dot(p_vec, q_vec)
                    / (np.linalg.norm(p_vec) * np.linalg.norm(q_vec) + 1e-8)
                )
                if p_sim < page_similarity_threshold:
                    continue
                matched_pages.append({"page_data": page, "score": p_sim})
            if not matched_pages:
                continue
            matched_pages.sort(key=lambda x: x["score"], reverse=True)
            results.append(
                {
                    "session_id": sid,
                    "session_summary": s["row"].get("summary"),
                    "session_relevance_score": s["overall_score"],
                    "matched_pages": matched_pages,
                }
            )
        results.sort(key=lambda x: x["session_relevance_score"], reverse=True)
        return results
