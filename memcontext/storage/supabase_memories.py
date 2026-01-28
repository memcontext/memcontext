from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from supabase import Client

from ..utils import get_timestamp


@dataclass(frozen=True)
class SupabaseIdentity:
    """
    Identity needed for RLS-protected access.
    - user_id: auth.users.id (UUID string)
    - assistant_id: optional, used for assistant-specific long-term knowledge
    """

    user_id: str
    assistant_id: str


class SupabaseShortTermMemory:
    """
    Drop-in alternative to ShortTermMemory for Supabase.
    Keeps the same public methods used by Memcontext: add_qa_pair/is_full/pop_oldest/get_all.
    """
    ##实际上identy 中的 assistant_id 并没有用到
    def __init__(self, client: Client, ident: SupabaseIdentity, max_capacity: int = 10):
        self.client = client
        self.ident = ident
        self.max_capacity = max_capacity

    def add_qa_pair(self, qa_pair: Dict[str, Any]):
        ts = qa_pair.get("timestamp") or get_timestamp()
        meta = qa_pair.get("meta_data") or {}
        self.client.table("short_term_messages").insert(
            {
                "user_id": self.ident.user_id,
                "user_input": qa_pair.get("user_input", "") or "",
                "agent_response": qa_pair.get("agent_response", "") or "",
                "ts": ts,
                "meta_data": meta,
            }
        ).execute()

    def get_all(self) -> List[Dict[str, Any]]:
        res = (
            self.client.table("short_term_messages")
            .select("user_input,agent_response,ts,meta_data")
            .eq("user_id", self.ident.user_id)
            .order("ts", desc=False)
            .execute()
        )
        rows = res.data or []
        return [
            {
                "user_input": r.get("user_input", ""),
                "agent_response": r.get("agent_response", ""),
                "timestamp": r.get("ts"),
                "meta_data": r.get("meta_data") or {},
            }
            for r in rows
        ]

    def is_full(self) -> bool:
        res = (
            self.client.table("short_term_messages")
            .select("id", count="exact")
            .eq("user_id", self.ident.user_id)
            .execute()
        )
        count = res.count or 0
        return count >= self.max_capacity

    def pop_oldest(self) -> Optional[Dict[str, Any]]:
        # Fetch oldest row then delete it (single-row)
        res = (
            self.client.table("short_term_messages")
            .select("id,user_input,agent_response,ts,meta_data")
            .eq("user_id", self.ident.user_id)
            .order("ts", desc=False)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            return None
        row = rows[0]
        self.client.table("short_term_messages").delete().eq("id", row["id"]).execute()
        return {
            "user_input": row.get("user_input", ""),
            "agent_response": row.get("agent_response", ""),
            "timestamp": row.get("ts"),
            "meta_data": row.get("meta_data") or {},
        }


class SupabaseLongTermMemory:
    """
    Replacement for LongTermMemory for Supabase.
    This class supports both 'user long term' and 'assistant long term' usage by switching tables.
    """

    def __init__(
        self,
        client: Client,
        ident: SupabaseIdentity,
        *,
        knowledge_capacity: int = 100,
        knowledge_table: str,
        profile_table: Optional[str] = None,
    ):
        self.client = client
        self.ident = ident
        self.knowledge_capacity = knowledge_capacity
        self.knowledge_table = knowledge_table
        self.profile_table = profile_table

    # ---- user profile (only meaningful when profile_table is set) ----
    def get_raw_user_profile(self, user_id: str) -> str:
        if not self.profile_table:
            return "None"
        res = (
            self.client.table(self.profile_table)
            .select("profile_data")
            .eq("user_id", self.ident.user_id)
            .eq("assistant_id", self.ident.assistant_id)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return (rows[0].get("profile_data") if rows else None) or "None"

    def update_user_profile(self, user_id: str, new_data: str, merge: bool = True):
        # For Supabase, we overwrite (merge behavior is handled by upstream prompt if needed)
        if not self.profile_table:
            return
        self.client.table(self.profile_table).upsert(
            {
                "user_id": self.ident.user_id,
                "assistant_id": self.ident.assistant_id,
                "profile_data": new_data,
                "last_updated": get_timestamp(),
            },
            on_conflict="user_id",
        ).execute()

    # ---- knowledge entries ----
    def add_knowledge_entry(self, knowledge_text: str, knowledge_deque=None, type_name: str = "knowledge"):
        # Keep signature compatible; ignore knowledge_deque/type_name and write to DB.
        if not knowledge_text or knowledge_text.strip().lower() in ["", "none", "- none", "- none."]:
            return
        # embedding is produced by existing LongTermMemory in current code; if you switch to this class,
        # you should pass precomputed knowledge_embedding or implement embedding generation here.
        raise NotImplementedError(
            "SupabaseLongTermMemory.add_knowledge_entry expects upstream to be adapted to compute embeddings "
            "and call add_user_knowledge/add_assistant_knowledge with embedding payload."
        )

    def add_user_knowledge(self, knowledge_text: str, knowledge_embedding: Optional[List[float]] = None, ts: Optional[str] = None):
        self._insert_knowledge(knowledge_text, knowledge_embedding=knowledge_embedding, ts=ts)

    def add_assistant_knowledge(self, knowledge_text: str, knowledge_embedding: Optional[List[float]] = None, ts: Optional[str] = None):
        self._insert_knowledge(knowledge_text, knowledge_embedding=knowledge_embedding, ts=ts)

    def _insert_knowledge(self, knowledge_text: str, *, knowledge_embedding: Optional[List[float]], ts: Optional[str]):
        self.client.table(self.knowledge_table).insert(
            {
                "user_id": self.ident.user_id,
                "assistant_id": self.ident.assistant_id,
                "knowledge_text": knowledge_text,
                "ts": ts or get_timestamp(),
                "knowledge_embedding": knowledge_embedding,
            }
        ).execute()

    def get_user_knowledge(self) -> List[Dict[str, Any]]:
        res = (
            self.client.table(self.knowledge_table)
            .select("knowledge_text,ts,knowledge_embedding")
            .eq("user_id", self.ident.user_id)
            .eq("assistant_id", self.ident.assistant_id)
            .order("ts", desc=False)
            .execute()
        )
        rows = res.data or []
        return [
            {
                "knowledge": r.get("knowledge_text", ""),
                "timestamp": r.get("ts"),
                "knowledge_embedding": r.get("knowledge_embedding"),
            }
            for r in rows
        ]

