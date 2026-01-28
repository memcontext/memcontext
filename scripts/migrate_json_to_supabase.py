"""
One-time migration: JSON storage -> Supabase Postgres

Assumptions:
- Supabase Auth is the user source (auth.users). You must provide a mapping from legacy user_id (e.g. "12324")
  to auth_user_id (UUID). This script can create a deterministic assistant_id per user.
- Uses Service Role key (bypasses RLS) for migration.

Env:
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY
  MEMCONTEXT_DATA_PATH (default: ./data)
  MEMCONTEXT_ASSISTANT_PREFIX (default: assistant_)

Usage (example):
  python scripts/migrate_json_to_supabase.py --map data/user_id_map.json

user_id_map.json example:
  {
    "12324": "0f1c2d3e-....-....",
    "alice": "..."
  }
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from supabase import create_client


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _parse_timestamp(s: Optional[str]) -> Optional[str]:
    # Existing JSON uses "YYYY-MM-DD HH:MM:SS". PostgREST accepts it as timestamptz string in many cases.
    # Keep as-is; you can normalize to ISO8601 if needed later.
    return s if s else None


@dataclass(frozen=True)
class UserCtx:
    legacy_user_id: str
    auth_user_id: str  # UUID string
    assistant_id: str


def _iter_users(data_path: Path) -> Iterable[Tuple[str, Path]]:
    users_dir = data_path / "users"
    if not users_dir.exists():
        return []
    for p in users_dir.iterdir():
        if p.is_dir():
            yield p.name, p


def _upsert_assistant(sb, ctx: UserCtx) -> None:
    sb.table("assistants").upsert(
        {
            "user_id": ctx.auth_user_id,
            "assistant_id": ctx.assistant_id,
        },
        on_conflict="user_id",
    ).execute()


def _migrate_short_term(sb, ctx: UserCtx, user_dir: Path) -> None:
    p = user_dir / "short_term.json"
    if not p.exists():
        return
    items = _load_json(p)
    if not isinstance(items, list) or not items:
        return
    rows = []
    for it in items:
        rows.append(
            {
                "user_id": ctx.auth_user_id,
                "assistant_id": ctx.assistant_id,
                "user_input": it.get("user_input", "") or "",
                "agent_response": it.get("agent_response", "") or "",
                "ts": _parse_timestamp(it.get("timestamp")),
                "meta_data": it.get("meta_data") or {},
            }
        )
    sb.table("short_term_messages").insert(rows).execute()


def _migrate_mid_term(sb, ctx: UserCtx, user_dir: Path) -> None:
    p = user_dir / "mid_term.json"
    if not p.exists():
        return
    obj = _load_json(p) or {}
    sessions: Dict[str, Any] = obj.get("sessions") or {}
    access_frequency: Dict[str, Any] = obj.get("access_frequency") or {}

    # 1) sessions
    session_rows = []
    page_rows = []
    for session_id, s in sessions.items():
        session_rows.append(
            {
                "session_id": session_id,
                "user_id": ctx.auth_user_id,
                "assistant_id": ctx.assistant_id,
                "summary": s.get("summary", "") or "",
                "summary_keywords": s.get("summary_keywords") or [],
                "summary_embedding": s.get("summary_embedding"),
                "l_interaction": int(s.get("L_interaction", 0) or 0),
                "r_recency": float(s.get("R_recency", 1.0) or 1.0),
                "n_visit": int(s.get("N_visit", 0) or 0),
                "h_segment": float(s.get("H_segment", 0.0) or 0.0),
                "last_visit_time": _parse_timestamp(s.get("last_visit_time")),
                "access_count_lfu": int(
                    s.get("access_count_lfu", access_frequency.get(session_id, 0)) or 0
                ),
                "created_at": _parse_timestamp(s.get("timestamp")) or None,
            }
        )

        details = s.get("details") or []
        for page in details:
            page_rows.append(
                {
                    "page_id": page.get("page_id"),
                    "session_id": session_id,
                    "user_id": ctx.auth_user_id,
                    "assistant_id": ctx.assistant_id,
                    "user_input": page.get("user_input", "") or "",
                    "agent_response": page.get("agent_response", "") or "",
                    "ts": _parse_timestamp(page.get("timestamp")),
                    "preloaded": bool(page.get("preloaded", False)),
                    "analyzed": bool(page.get("analyzed", False)),
                    "pre_page_id": page.get("pre_page"),
                    "next_page_id": page.get("next_page"),
                    "meta_info": page.get("meta_info"),
                    "meta_data": page.get("meta_data") or {},
                    "page_keywords": page.get("page_keywords") or [],
                    "page_embedding": page.get("page_embedding"),
                }
            )

    if session_rows:
        # Upsert sessions (in case rerun)
        sb.table("mid_term_sessions").upsert(session_rows, on_conflict="session_id").execute()
    if page_rows:
        # Upsert pages (in case rerun)
        sb.table("mid_term_pages").upsert(page_rows, on_conflict="page_id").execute()


def _migrate_long_term_user(sb, ctx: UserCtx, user_dir: Path) -> None:
    p = user_dir / "long_term_user.json"
    if not p.exists():
        return
    obj = _load_json(p) or {}

    # user_profiles
    up = (obj.get("user_profiles") or {}).get(ctx.legacy_user_id) or {}
    profile_data = up.get("data")
    last_updated = _parse_timestamp(up.get("last_updated"))
    if profile_data:
        sb.table("long_term_user_profiles").upsert(
            {
                "user_id": ctx.auth_user_id,
                "assistant_id": ctx.assistant_id,
                "profile_data": profile_data,
                "last_updated": last_updated,
            },
            on_conflict="user_id",
        ).execute()

    # knowledge_base -> long_term_user_knowledge
    kb = obj.get("knowledge_base") or []
    if kb:
        rows = []
        for it in kb:
            rows.append(
                {
                    "user_id": ctx.auth_user_id,
                    "assistant_id": ctx.assistant_id,
                    "knowledge_text": it.get("knowledge", "") or "",
                    "ts": _parse_timestamp(it.get("timestamp")),
                    "knowledge_embedding": it.get("knowledge_embedding"),
                }
            )
        sb.table("long_term_user_knowledge").insert(rows).execute()


def _migrate_long_term_assistant(sb, ctx: UserCtx, data_path: Path) -> None:
    # Existing layout: data/assistants/<assistant_id>/long_term_assistant.json
    p = data_path / "assistants" / ctx.assistant_id / "long_term_assistant.json"
    if not p.exists():
        return
    obj = _load_json(p) or {}
    ak = obj.get("assistant_knowledge") or []
    if not ak:
        return
    rows = []
    for it in ak:
        rows.append(
            {
                "user_id": ctx.auth_user_id,
                "assistant_id": ctx.assistant_id,
                "knowledge_text": it.get("knowledge", "") or "",
                "ts": _parse_timestamp(it.get("timestamp")),
                "knowledge_embedding": it.get("knowledge_embedding"),
            }
        )
    sb.table("long_term_assistant_knowledge").insert(rows).execute()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", required=True, help="Path to legacy_user_id -> auth_user_id(UUID) JSON map")
    ap.add_argument(
        "--data-path",
        default=os.environ.get("MEMCONTEXT_DATA_PATH", "./data"),
        help="Memcontext data directory (default: ./data or MEMCONTEXT_DATA_PATH)",
    )
    ap.add_argument(
        "--assistant-prefix",
        default=os.environ.get("MEMCONTEXT_ASSISTANT_PREFIX", "assistant_"),
        help="assistant_id = prefix + legacy_user_id (default: assistant_)",
    )
    args = ap.parse_args()

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")

    user_map = _load_json(Path(args.map))
    if not isinstance(user_map, dict) or not user_map:
        raise SystemExit("--map must be a non-empty JSON object")

    data_path = Path(args.data_path)
    sb = create_client(url, key)

    for legacy_user_id, user_dir in _iter_users(data_path):
        auth_user_id = user_map.get(legacy_user_id)
        if not auth_user_id:
            print(f"[SKIP] No auth_user_id mapping for legacy user {legacy_user_id}")
            continue

        ctx = UserCtx(
            legacy_user_id=legacy_user_id,
            auth_user_id=auth_user_id,
            assistant_id=f"{args.assistant_prefix}{legacy_user_id}",
        )
        print(f"[USER] {legacy_user_id} -> {auth_user_id} assistant_id={ctx.assistant_id}")

        _upsert_assistant(sb, ctx)
        _migrate_short_term(sb, ctx, user_dir)
        _migrate_mid_term(sb, ctx, user_dir)
        _migrate_long_term_user(sb, ctx, user_dir)
        _migrate_long_term_assistant(sb, ctx, data_path)

    print("Done.")


if __name__ == "__main__":
    main()

