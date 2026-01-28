from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from supabase import Client, create_client


@dataclass(frozen=True)
class SupabaseConfig:
    url: str
    key: str

import json
from pathlib import Path
def load_supabase_config(
    *,
    url_env: str = "SUPABASE_URL",
    key_env: str = "SUPABASE_ANON_KEY",
) -> SupabaseConfig:
    cfg_path = Path(__file__).resolve().parents[2] / "config.json"
    url = ""
    key = ""
    if cfg_path.exists():
        data = json.load(open(cfg_path, "r", encoding="utf-8"))
        supa = data.get("supabase", {})
        url = (supa.get("url") or "").strip()
        key = (supa.get("anon_key") or "").strip()

    # 2. 如果还没有，再用环境变量兜底
    url = url or (os.environ.get(url_env) or "").strip()
    key = key or (os.environ.get(key_env) or "").strip()

    if not url or not key:
        raise RuntimeError("Missing Supabase URL/key in config.json or env")
    return SupabaseConfig(url=url, key=key)



def make_supabase_client(cfg: SupabaseConfig) -> Client:
    return create_client(cfg.url, cfg.key)

