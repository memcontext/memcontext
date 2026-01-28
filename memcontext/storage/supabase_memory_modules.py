from __future__ import annotations

from typing import Any, Dict, List, Optional

from supabase import Client

from ..mid_term import MidTermMemory
from ..long_term import LongTermMemory
from ..utils import get_timestamp


class SupabaseMidTermMemory(MidTermMemory):
    """
    MidTermMemory backed by Supabase tables:
      - mid_term_sessions
      - mid_term_pages

    Strategy:
    - Load all sessions+pages into memory on init (same dict structure as file-backed version)
    - Reuse all existing in-memory logic (insert/merge/search/heat/lfu)
    - Persist by overriding save()/load() with DB upserts
    """

    def __init__(
        self,
        client: Client,
        *,
        user_id: str,
        client,
        max_capacity: int = 2000,
        embedding_model_name: str = "all-MiniLM-L6-v2",
        embedding_model_kwargs: dict | None = None,
    ):
        # file_path is unused but required by base __init__; bypass base init and set fields manually
        self.file_path = "<supabase>"
        self.client = client
        self.max_capacity = max_capacity
        self.sessions: Dict[str, Any] = {}
        from collections import defaultdict
        self.access_frequency = defaultdict(int)
        self.heap = []
        self.embedding_model_name = embedding_model_name
        self.embedding_model_kwargs = embedding_model_kwargs if embedding_model_kwargs is not None else {}

        self._client = client
        self._user_id = user_id

        self.load()

    def save(self):
        # Upsert sessions
        session_rows = []
        page_rows = []
        for session_id, s in self.sessions.items():
            session_rows.append(
                {
                    "session_id": session_id,
                    "user_id": self._user_id,
                    "summary": s.get("summary", "") or "",
                    "summary_keywords": s.get("summary_keywords") or [],
                    "summary_embedding": s.get("summary_embedding"),
                    "l_interaction": int(s.get("L_interaction", 0) or 0),
                    "r_recency": float(s.get("R_recency", 1.0) or 1.0),
                    "n_visit": int(s.get("N_visit", 0) or 0),
                    "h_segment": float(s.get("H_segment", 0.0) or 0.0),
                    "last_visit_time": s.get("last_visit_time"),
                    "access_count_lfu": int(s.get("access_count_lfu", 0) or 0),
                }
            )

            for p in s.get("details", []) or []:
                page_rows.append(
                    {
                        "page_id": p.get("page_id"),
                        "session_id": session_id,
                        "user_id": self._user_id,
                        "user_input": p.get("user_input", "") or "",
                        "agent_response": p.get("agent_response", "") or "",
                        "time_stamp": p.get("timestamp"),
                        "preloaded": bool(p.get("preloaded", False)),
                        "analyzed": bool(p.get("analyzed", False)),
                        "pre_page_id": p.get("pre_page"),
                        "next_page_id": p.get("next_page"),
                        "meta_info": p.get("meta_info"),
                        "meta_data": p.get("meta_data") or {},
                        "page_keywords": p.get("page_keywords") or [],
                        "page_embedding": p.get("page_embedding"),
                    }
                )

        if session_rows:
            self._client.table("mid_term_sessions").upsert(session_rows, on_conflict="session_id").execute()
        if page_rows:
            self._client.table("mid_term_pages").upsert(page_rows, on_conflict="page_id").execute()

    def load(self):
        # Load sessions
        res = (
            self._client.table("mid_term_sessions")
            .select(
                "session_id,summary,summary_keywords,summary_embedding,l_interaction,r_recency,n_visit,h_segment,last_visit_time,access_count_lfu,created_at"
            )
            .eq("user_id", self._user_id)
            .execute()
        )
        sessions = res.data or []

        # Load pages
        pres = (
            self._client.table("mid_term_pages")
            .select(
                "page_id,session_id,user_input,agent_response,time_stamp,preloaded,analyzed,pre_page_id,next_page_id,meta_info,meta_data,page_keywords,page_embedding"
            )
            .eq("user_id", self._user_id)
            .execute()
        )
        pages = pres.data or []

        # Build session dicts
        self.sessions = {}
        for s in sessions:
            sid = s["session_id"]
            self.sessions[sid] = {
                "id": sid,
                "summary": s.get("summary"),
                "summary_keywords": s.get("summary_keywords") or [],
                "summary_embedding": s.get("summary_embedding") or [],
                "details": [],
                "L_interaction": int(s.get("l_interaction", 0) or 0),
                "R_recency": float(s.get("r_recency", 1.0) or 1.0),
                "N_visit": int(s.get("n_visit", 0) or 0),
                "H_segment": float(s.get("h_segment", 0.0) or 0.0),
                "timestamp": s.get("created_at") or get_timestamp(),
                "last_visit_time": s.get("last_visit_time") or s.get("created_at") or get_timestamp(),
                "access_count_lfu": int(s.get("access_count_lfu", 0) or 0),
            }

        for p in pages:
            sid = p["session_id"]
            if sid not in self.sessions:
                continue
            self.sessions[sid]["details"].append(
                {
                    "page_id": p.get("page_id"),
                    "user_input": p.get("user_input", ""),
                    "agent_response": p.get("agent_response", ""),
                    "timestamp": p.get("time_stamp"),
                    "preloaded": bool(p.get("preloaded", False)),
                    "analyzed": bool(p.get("analyzed", False)),
                    "pre_page": p.get("pre_page_id"),
                    "next_page": p.get("next_page_id"),
                    "meta_info": p.get("meta_info"),
                    "meta_data": p.get("meta_data") or {},
                    "page_keywords": p.get("page_keywords") or [],
                    "page_embedding": p.get("page_embedding") or [],
                }
            )

        # access_frequency derives from sessions' access_count_lfu
        from collections import defaultdict

        self.access_frequency = defaultdict(int)
        for sid, s in self.sessions.items():
            self.access_frequency[sid] = int(s.get("access_count_lfu", 0) or 0)

        self.rebuild_heap()


class SupabaseLongTermMemory(LongTermMemory):
    """
    LongTermMemory backed by Supabase tables:
      - long_term_user_profiles (optional; only for user long-term)
      - long_term_user_knowledge
      - long_term_assistant_knowledge

    Strategy:
    - Reuse existing logic for embedding + in-memory structures
    - Override save/load to persist/read from tables
    """

    def __init__(
        self,
        client: Client,
        *,
        user_id: str,
        assistant_id: str,
        knowledge_capacity: int = 100,
        embedding_model_name: str = "all-MiniLM-L6-v2",
        embedding_model_kwargs: dict | None = None,
        mode: str,  # "user" | "assistant"
    ):
        self._client = client
        self._user_id = user_id
        self._assistant_id = assistant_id
        self._mode = mode

        # file_path unused; bypass file IO by setting it and calling load() (overridden)
        self.file_path = "<supabase>"
        self.knowledge_capacity = knowledge_capacity
        from collections import deque

        self.user_profiles = {}
        self.knowledge_base = deque(maxlen=self.knowledge_capacity)
        self.assistant_knowledge = deque(maxlen=self.knowledge_capacity)
        self.embedding_model_name = embedding_model_name
        self.embedding_model_kwargs = embedding_model_kwargs if embedding_model_kwargs is not None else {}

        self.load()

    def save(self):
        # Persist user profile (user-mode only)
        if self._mode == "user":
            prof = self.user_profiles.get(self._user_id)
            if prof and prof.get("data"):
                self._client.table("long_term_user_profiles").upsert(
                    {
                        "user_id": self._user_id,
                        "profile_data": prof.get("data"),
                        "last_updated": prof.get("last_updated") or get_timestamp(),
                    },
                    on_conflict="user_id",
                ).execute()

        # Persist knowledge rows (append-only; for idempotency you can add a hash later)
        if self._mode == "user":
            table = "long_term_user_knowledge"
            entries = list(self.knowledge_base)
        else:
            table = "long_term_assistant_knowledge"
            entries = list(self.assistant_knowledge)

        if entries:
            rows = []
            for e in entries:
                if table == "long_term_user_knowledge":
                    rows.append(
                        {
                            "user_id": self._user_id,
                            "knowledge_text": e.get("knowledge", ""),
                            "time_stamp": e.get("timestamp"),
                            "knowledge_embedding": e.get("knowledge_embedding"),
                        }
                    )
                else:
                    rows.append(
                        {
                            "assistant_id": self._assistant_id,
                            "user_id": self._user_id,
                            "knowledge": e.get("knowledge", ""),
                            "time_stamp": e.get("timestamp"),
                            "knowledge_embedding": e.get("knowledge_embedding"),
                        }
                    )
            # Insert; duplicates are possible if called repeatedly. Prefer writing via add_* methods.
            self._sb.table(table).insert(rows).execute()

    def load(self):
        from collections import deque

        self.user_profiles = {}
        self.knowledge_base = deque(maxlen=self.knowledge_capacity)
        self.assistant_knowledge = deque(maxlen=self.knowledge_capacity)

        # user profile
        if self._mode == "user":
            res = (
                self._sb.table("long_term_user_profiles")
                .select("profile_data,last_updated")
                .eq("user_id", self._user_id)
                .limit(1)
                .execute()
            )
            rows = res.data or []
            if rows:
                self.user_profiles[self._user_id] = {
                    "data": rows[0].get("profile_data"),
                    "last_updated": rows[0].get("last_updated") or get_timestamp(),
                }

        # knowledge
        if self._mode == "user":
            table = "long_term_user_knowledge"
            dest = "knowledge_base"
        else:
            table = "long_term_assistant_knowledge"
            dest = "assistant_knowledge"

        kres = (
            self._client.table(table)
            .select("*")
            .eq("user_id", self._user_id)
            .order("time_stamp", desc=False)
            .execute()
        )
        krows = kres.data or []
        for r in krows[-self.knowledge_capacity :]:
            if table == "long_term_user_knowledge":
                entry = {
                    "knowledge": r.get("knowledge_text", ""),
                    "timestamp": r.get("time_stamp"),
                    "knowledge_embedding": r.get("knowledge_embedding"),
                }
            else:
                if r.get("assistant_id") != self._assistant_id:
                    continue
                entry = {
                    "knowledge": r.get("knowledge", ""),
                    "timestamp": r.get("time_stamp"),
                    "knowledge_embedding": r.get("knowledge_embedding"),
                }
            if dest == "knowledge_base":
                self.knowledge_base.append(entry)
            else:
                self.assistant_knowledge.append(entry)

