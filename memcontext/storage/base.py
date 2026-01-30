from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


class MemoryStorage(ABC):
    """
    抽象的内存持久化接口。

    目前专门为 `MidTermMemory` 设计签名，后续可以扩展给 LongTerm 等其它层级。
    约定：
    - 大体结构仍然是「session + pages」；
    - embedding 存在存储层（数据库），`MidTermMemory` 内存里只保留必要的元信息；
    - 所有方法都必须按 user 维度做隔离。
    """

    # ---------- 会话加载 / 元信息 ----------

    @abstractmethod
    def load_sessions_meta(self, user_id: str) -> Mapping[str, Dict[str, Any]]:
        """
        加载某个用户的所有 session 元信息，但不加载任何大 embedding。

        返回值建议是：
        {
            session_id: {
                "id": ...,
                "summary": ...,
                "summary_keywords": [...],
                "L_interaction": ...,
                "N_visit": ...,
                "R_recency": ...,
                "H_segment": ...,
                "timestamp": ...,
                "last_visit_time": ...,
                "access_count_lfu": ...,
                # 允许附带其它轻量字段，但不要包含 page / embedding
            },
            ...
        }
        """
        raise NotImplementedError

    @abstractmethod
    def load_session_pages(self, user_id: str, session_id: str) -> List[Dict[str, Any]]:
        """
        加载某个 session 的 pages 明细（对应 MidTermMemory 里的 session["details"]）。

        返回值建议是 page_dict 列表，字段与 `MidTermMemory` 当前使用保持一致，例如：
        [
          {
            "page_id": str,
            "user_input": str,
            "agent_response": str,
            "timestamp": str,
            "preloaded": bool,
            "analyzed": bool,
            "pre_page": Optional[str],
            "next_page": Optional[str],
            "meta_info": Optional[str],
            "meta_data": dict,
            "page_keywords": list,
            "page_embedding": Optional[list[float]],
          },
          ...
        ]
        """
        raise NotImplementedError

    # ---------- 写入 / 更新 ----------

    @abstractmethod
    def save_session_batch(
        self,
        user_id: str,
        sessions: Iterable[Dict[str, Any]],
    ) -> None:
        """
        批量保存一批 session 及其下属的 pages。

        使用场景：
        - `MidTermMemory.save()` 全量落库；
        - 迁移脚本将本地 JSON 一次性写入 Supabase。

        要求：
        - 同一 user 内部应使用事务保证一致性；
        - sessions 中的每个 dict 至少包含：
          - 顶层 session 字段（id, summary, keywords, heat 等）
          - `details`: List[page_dict]，其中 page_dict 内可以带 page_embedding 等大字段，
            由具体实现决定是否真正写入、是否只留在向量表中。
        """
        raise NotImplementedError

    @abstractmethod
    def upsert_session_with_pages(
        self,
        user_id: str,
        session: Dict[str, Any],
        pages: Sequence[Dict[str, Any]],
    ) -> str:
        """
        插入或更新一个 session 以及它的一组 pages，返回最终的 session_id。

        使用场景：
        - `MidTermMemory.add_session` 新建 session；
        - `MidTermMemory.insert_pages_into_session` 在「新建 session」分支下调用。

        约定：
        - 如果 `session` 中没有 id，由实现生成一个新的 session_id；
        - pages 中的 page 结构与当前 MidTerm `details` 里的 page 结构保持一致。
        """
        raise NotImplementedError

    @abstractmethod
    def append_pages_to_session(
        self,
        user_id: str,
        session_id: str,
        pages: Sequence[Dict[str, Any]],
    ) -> None:
        """
        向已有 session 追加一批 pages。

        使用场景：
        - `MidTermMemory.insert_pages_into_session` 在「合并到已有 session」分支下调用。
        """
        raise NotImplementedError

    @abstractmethod
    def update_session_stats(
        self,
        user_id: str,
        session_id: str,
        stats: Mapping[str, Any],
    ) -> None:
        """
        更新与热度 / 访问频次相关的轻量字段，例如：
        - N_visit
        - L_interaction
        - R_recency
        - H_segment
        - last_visit_time
        - access_count_lfu

        使用场景：
        - 检索后根据访问情况更新；
        - Updater/eviction 后调整 heat 等。
        """
        raise NotImplementedError

    @abstractmethod
    def delete_session(
        self,
        user_id: str,
        session_id: str,
    ) -> None:
        """
        删除一个 session 及其所有 pages（用于 LFU 淘汰等场景）。
        """
        raise NotImplementedError

    # ---------- 检索 ----------

    @abstractmethod
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
        使用向量 + 关键词从存储层检索匹配的 sessions 和 pages。

        建议返回格式与 `MidTermMemory.search_sessions` 当前返回值兼容：
        [
          {
            "session_id": str,
            "session_summary": str,
            "session_relevance_score": float,
            "matched_pages": [
              {
                "page_data": { ... 不含大 embedding 也可以 ... },
                "score": float,  # 与 query 的相似度
              },
              ...
            ],
          },
          ...
        ]
        """
        raise NotImplementedError
