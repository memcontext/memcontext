-- Supabase schema for Memcontext (JSON -> Postgres)
-- Assumptions:
-- - Users come from Supabase Auth (auth.users)
-- - One assistant per user (assistant_id bound to user_id)
-- - Embedding dimension detected from existing JSON: 2048

begin;

-- Extensions
create extension if not exists vector;
create extension if not exists pgcrypto;

-- ================
-- 1) assistants
-- ================
create table if not exists public.assistants (
  assistant_id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  created_at timestamptz not null default now()
);

alter table public.assistants enable row level security;

drop policy if exists assistants_select_own on public.assistants;
create policy assistants_select_own
on public.assistants for select
using (auth.uid() = user_id);

drop policy if exists assistants_insert_own on public.assistants;
create policy assistants_insert_own
on public.assistants for insert
with check (auth.uid() = user_id);

drop policy if exists assistants_update_own on public.assistants;
create policy assistants_update_own
on public.assistants for update
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

drop policy if exists assistants_delete_own on public.assistants;
create policy assistants_delete_own
on public.assistants for delete
using (auth.uid() = user_id);

-- ======================
-- 2) short_term_messages
-- ======================
create table if not exists public.short_term_messages (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  

  user_input text not null,
  agent_response text not null,
  ts timestamptz not null default now(),
  meta_data jsonb not null default '{}'::jsonb,

  created_at timestamptz not null default now()
);

create index if not exists idx_stm_user_ts
on public.short_term_messages (user_id, ts desc);

alter table public.short_term_messages enable row level security;

drop policy if exists stm_select_own on public.short_term_messages;
create policy stm_select_own
on public.short_term_messages for select
using (auth.uid() = user_id);

drop policy if exists stm_insert_own on public.short_term_messages;
create policy stm_insert_own
on public.short_term_messages for insert
with check (auth.uid() = user_id);

drop policy if exists stm_delete_own on public.short_term_messages;
create policy stm_delete_own
on public.short_term_messages for delete
using (auth.uid() = user_id);

-- ==================
-- 3) mid_term_sessions
-- ==================
create table if not exists public.mid_term_sessions (
  session_id text primary key, -- reuse existing "session_xxx"
  user_id uuid not null references auth.users(id) on delete cascade,
  
  summary text not null,
  summary_keywords jsonb not null default '[]'::jsonb,
  summary_embedding vector,

  -- heat & stats (session level)
  L_interaction integer not null default 0,
  R_recency double precision not null default 1.0,
  N_visit integer not null default 0,
  H_segment double precision not null default 0.0,

  last_visit_time timestamptz,
  access_count_lfu bigint not null default 0,

  created_at timestamptz not null default now()
);

create index if not exists idx_mts_user
on public.mid_term_sessions (user_id);

create index if not exists idx_mts_user_lfu
on public.mid_term_sessions (user_id, access_count_lfu asc);

create index if not exists idx_mts_user_heat
on public.mid_term_sessions (user_id, h_segment desc);

-- Optional vector index (enable when data volume grows)
-- create index if not exists idx_mts_summary_embedding_hnsw
-- on public.mid_term_sessions using hnsw (summary_embedding vector_cosine_ops);

alter table public.mid_term_sessions enable row level security;

drop policy if exists mts_select_own on public.mid_term_sessions;
create policy mts_select_own
on public.mid_term_sessions for select
using (auth.uid() = user_id);

drop policy if exists mts_insert_own on public.mid_term_sessions;
create policy mts_insert_own
on public.mid_term_sessions for insert
with check (auth.uid() = user_id);

drop policy if exists mts_update_own on public.mid_term_sessions;
create policy mts_update_own
on public.mid_term_sessions for update
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

drop policy if exists mts_delete_own on public.mid_term_sessions;
create policy mts_delete_own
on public.mid_term_sessions for delete
using (auth.uid() = user_id);

-- ===============
-- 4) mid_term_pages
-- ===============
create table if not exists public.mid_term_pages (
  page_id text primary key, -- reuse existing "page_xxx"
  session_id text not null references public.mid_term_sessions(session_id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  

  user_input text not null,
  agent_response text not null,
  time_stamp timestamptz not null default now(),

  preloaded boolean not null default false,
  analyzed boolean not null default false,

  pre_page_id text null references public.mid_term_pages(page_id) on delete set null,
  next_page_id text null references public.mid_term_pages(page_id) on delete set null,

  meta_info text,
  meta_data jsonb not null default '{}'::jsonb,

  page_keywords jsonb not null default '[]'::jsonb,
  page_embedding vector,

  created_at timestamptz not null default now()
);

create index if not exists idx_mtp_session_ts
on public.mid_term_pages (session_id,user_id, time_stamp desc);

create index if not exists idx_mtp_user_analyzed_false
on public.mid_term_pages (user_id, analyzed)
where analyzed = false;

-- Optional vector index (enable when data volume grows)
-- create index if not exists idx_mtp_page_embedding_hnsw
-- on public.mid_term_pages using hnsw (page_embedding vector_cosine_ops);

alter table public.mid_term_pages enable row level security;

drop policy if exists mtp_select_own on public.mid_term_pages;
create policy mtp_select_own
on public.mid_term_pages for select
using (auth.uid() = user_id);

drop policy if exists mtp_insert_own on public.mid_term_pages;
create policy mtp_insert_own
on public.mid_term_pages for insert
with check (auth.uid() = user_id);

drop policy if exists mtp_update_own on public.mid_term_pages;
create policy mtp_update_own
on public.mid_term_pages for update
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

drop policy if exists mtp_delete_own on public.mid_term_pages;
create policy mtp_delete_own
on public.mid_term_pages for delete
using (auth.uid() = user_id);

-- =======================
-- 5) long_term_user_profiles
-- =======================
create table if not exists public.long_term_user_profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  
  profile_data text not null,
  last_updated timestamptz not null default now()
  
);
create index if not exists idx_ltup_user_ts
on public.long_term_user_profiles (user_id, last_updated desc);


alter table public.long_term_user_profiles enable row level security;

drop policy if exists ltup_select_own on public.long_term_user_profiles;
create policy ltup_select_own
on public.long_term_user_profiles for select
using (auth.uid() = user_id);

drop policy if exists ltup_insert_own on public.long_term_user_profiles;
create policy ltup_insert_own
on public.long_term_user_profiles for insert
with check (auth.uid() = user_id);

drop policy if exists ltup_update_own on public.long_term_user_profiles;
create policy ltup_update_own
on public.long_term_user_profiles for update
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

-- ======================
-- 6) long_term_user_knowledge (knowledge_base)
-- ======================
create table if not exists public.long_term_user_knowledge (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  
  knowledge_text text not null,
  time_stamp timestamptz not null default now(),
  knowledge_embedding vector
);

create index if not exists idx_ltuk_user_ts
on public.long_term_user_knowledge (user_id, time_stamp desc);

-- Optional vector index
-- create index if not exists idx_ltuk_embedding_hnsw
-- on public.long_term_user_knowledge using hnsw (knowledge_embedding vector_cosine_ops);

alter table public.long_term_user_knowledge enable row level security;

drop policy if exists ltuk_select_own on public.long_term_user_knowledge;
create policy ltuk_select_own
on public.long_term_user_knowledge for select
using (auth.uid() = user_id);

drop policy if exists ltuk_insert_own on public.long_term_user_knowledge;
create policy ltuk_insert_own
on public.long_term_user_knowledge for insert
with check (auth.uid() = user_id);

drop policy if exists ltuk_delete_own on public.long_term_user_knowledge;
create policy ltuk_delete_own
on public.long_term_user_knowledge for delete
using (auth.uid() = user_id);

-- ==========================
-- 7) long_term_assistant_knowledge (assistant_knowledge)
-- ==========================
create table if not exists public.long_term_assistant_knowledge (
  id bigint generated always as identity primary key,
  assistant_id uuid not null references public.assistants(assistant_id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  knowledge text not null,
  time_stamp timestamptz not null default now(),
  knowledge_embedding vector

);

create index if not exists idx_ltak_user_ts
on public.long_term_assistant_knowledge (assistant_id, time_stamp desc);

-- Optional vector index
-- create index if not exists idx_ltak_embedding_hnsw
-- on public.long_term_assistant_knowledge using hnsw (knowledge_embedding vector_cosine_ops);

alter table public.long_term_assistant_knowledge enable row level security;

drop policy if exists ltak_select_own on public.long_term_assistant_knowledge;
create policy ltak_select_own
on public.long_term_assistant_knowledge for select
using (auth.uid() = user_id);

drop policy if exists ltak_insert_own on public.long_term_assistant_knowledge;
create policy ltak_insert_own
on public.long_term_assistant_knowledge for insert
with check (auth.uid() = user_id);

drop policy if exists ltak_delete_own on public.long_term_assistant_knowledge;
create policy ltak_delete_own
on public.long_term_assistant_knowledge for delete
using (auth.uid() = user_id);

commit;

