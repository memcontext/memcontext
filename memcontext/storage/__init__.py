from __future__ import annotations

"""
storage 包导出统一接口：

- `MemoryStorage` 抽象基类：定义 MidTerm/LongTerm 等内存层对持久化的期望接口；
- `SupabaseStore`：基于 Supabase（Postgres + pgvector）的实现（当前主要用于 MidTermMemory）；
- `LocalStore`：本地文件/JSON 实现的占位符，你可以在 `local_store.py` 里按需要补全。
"""

from .base import MemoryStorage
from .superbase_store import SupabaseStore

try:
    # LocalStore 目前可能还是空骨架，这里用 try/except 兼容未实现阶段
    from .local_store import LocalStore  # type: ignore
except Exception:  # pragma: no cover - 仅作为占位兼容
    LocalStore = None  # type: ignore

__all__ = [
    "MemoryStorage",
    "SupabaseStore",
    "LocalStore",
]
