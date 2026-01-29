from __future__ import annotations

"""
LocalStore: 基于本地 JSON 文件的 `MemoryStorage` 实现。

设计目标：
- 与现有的 `mid_term.json` 结构完全兼容；
- 作为 SupabaseStore 尚未接入时的本地后端；
- 实现 `MemoryStorage` 的全部方法，使 `MidTermMemory` 可以通过统一接口读写。
"""

import json
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from .base import MemoryStorage

from ..utils import ensure_directory_exists


class LocalStore(MemoryStorage):
    """
    使用单个 JSON 文件存储：
    {
      "sessions": {session_id: { ... 全部字段，包括 details ... }},
      "access_frequency": {session_id: count_int}
    }
    """

    def __init__(self, file_path: str) -> None:
        # 这里的 file_path 一般就是 user_mid_term_path（每个用户一个文件）
        self.file_path = file_path
        ensure_directory_exists(self.file_path)

    # ------- 内部辅助 -------

    def _read_all(self) -> Dict[str, Any]:
        """读取整个 JSON 文件，容错为空/不存在的情况。"""
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    return {"sessions": {}, "access_frequency": {}}
                data.setdefault("sessions", {})
                data.setdefault("access_frequency", {})
                return data
        except FileNotFoundError:
            return {"sessions": {}, "access_frequency": {}}
        except json.JSONDecodeError:
            return {"sessions": {}, "access_frequency": {}}
        except Exception:
            return {"sessions": {}, "access_frequency": {}}

    def _write_all(self, sessions: Mapping[str, Dict[str, Any]]) -> None:
        """写回整个 JSON 文件，根据 session 中的 access_count_lfu 生成 access_frequency。"""
        access_frequency: Dict[str, int] = {}
        for sid, s in sessions.items():
            try:
                access_frequency[sid] = int(s.get("access_count_lfu", 0) or 0)
            except Exception:
                access_frequency[sid] = 0

        data_to_save = {
            "sessions": sessions,
            "access_frequency": access_frequency,
        }
        ensure_directory_exists(self.file_path)
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=2)

    # ---------- 会话加载 / 元信息 ----------

    def load_sessions_meta(self, user_id: str) -> Mapping[str, Dict[str, Any]]:
        """
        从 JSON 文件加载所有 session 的元信息。

        - 返回值中不会移除 details 字段（为了兼容现有结构），
          但 `MidTermMemory` 也可以选择只使用轻量字段。
        - user_id 在本地实现中不参与路径选择，保持接口一致即可。
        """
        data = self._read_all()
        sessions: Dict[str, Dict[str, Any]] = data.get("sessions", {}) or {}
        access_freq: Dict[str, int] = data.get("access_frequency", {}) or {}

        for sid, meta in sessions.items():
            meta.setdefault("id", sid)
            # 将 access_frequency 合并回 session，方便上层使用
            if "access_count_lfu" not in meta:
                meta["access_count_lfu"] = int(access_freq.get(sid, 0) or 0)

        return sessions

    def load_session_pages(self, user_id: str, session_id: str) -> List[Dict[str, Any]]:
        """
        本地 JSON 直接从 sessions[session_id]["details"] 取出。
        """
        data = self._read_all()
        sessions: Dict[str, Dict[str, Any]] = data.get("sessions", {}) or {}
        s = sessions.get(session_id) or {}
        details = s.get("details") or []
        if not isinstance(details, list):
            return []
        return details

    # ---------- 写入 / 更新 ----------

    def save_session_batch(
        self,
        user_id: str,
        sessions: Iterable[Dict[str, Any]],
    ) -> None:
        """
        将给定的所有 session 视为当前完整状态，全量覆盖文件内容。
        """
        sessions_by_id: Dict[str, Dict[str, Any]] = {}
        for s in sessions:
            sid = s.get("id")
            if not sid:
                # 如果没有 id，则跳过；上层 `MidTermMemory` 通常会保证 id 存在
                continue
            sessions_by_id[sid] = s

        self._write_all(sessions_by_id)

    def upsert_session_with_pages(
        self,
        user_id: str,
        session: Dict[str, Any],
        pages: Sequence[Dict[str, Any]],
    ) -> str:
        """
        插入/更新单个 session，并覆盖其 details 为给定 pages。
        """
        data = self._read_all()
        sessions: Dict[str, Dict[str, Any]] = data.get("sessions", {}) or {}

        sid = session.get("id")
        if not sid:
            # 本地实现中不负责生成 id，只简单兜底一个固定占位；
            # 实际场景中，MidTermMemory 会自行生成。
            sid = "session_local_placeholder"
            session["id"] = sid

        # 确保 details 覆盖为最新 pages
        session = dict(session)
        session["details"] = list(pages)
        sessions[sid] = session

        self._write_all(sessions)
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
        data = self._read_all()
        sessions: Dict[str, Dict[str, Any]] = data.get("sessions", {}) or {}
        session = sessions.get(session_id)
        if not session:
            # 找不到则直接返回，不抛异常，保持容错
            return

        current_details = session.get("details") or []
        if not isinstance(current_details, list):
            current_details = []
        session["details"] = current_details + list(pages)
        sessions[session_id] = session

        self._write_all(sessions)

    def update_session_stats(
        self,
        user_id: str,
        session_id: str,
        stats: Mapping[str, Any],
    ) -> None:
        """
        在 JSON 中更新 session 的轻量统计字段（如 N_visit / H_segment 等）。
        """
        data = self._read_all()
        sessions: Dict[str, Dict[str, Any]] = data.get("sessions", {}) or {}
        session = sessions.get(session_id)
        if not session:
            return

        for k, v in stats.items():
            session[k] = v

        sessions[session_id] = session
        self._write_all(sessions)

    def delete_session(
        self,
        user_id: str,
        session_id: str,
    ) -> None:
        """
        从 JSON 中删除一个 session 及其所有 pages。
        """
        data = self._read_all()
        sessions: Dict[str, Dict[str, Any]] = data.get("sessions", {}) or {}

        if session_id in sessions:
            del sessions[session_id]

        self._write_all(sessions)

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
        本地 JSON 模式下，通常仍然由 `MidTermMemory` 自己在内存里用 FAISS 检索。

        为了简单起见，这里直接返回空列表，并在文档中注明：
        - 如果你希望 LocalStore 也支持向量检索，可以在后续版本中复用
          `MidTermMemory.search_sessions` 中的 FAISS 逻辑搬到这里实现。
        """
        return []
