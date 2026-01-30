-- =============================================================================
-- Supabase 初始化脚本：创建 pgvector 扩展、必要表，以及用于 pgvector 检索的 RPC 函数
-- 在 Supabase SQL Editor 中执行此脚本（或分段执行）。只需执行一次（或在重建 DB 后再执行）。
-- 注意：请根据你的 embedding_dim（本项目默认 2048）调整 vector(...) 的维度。
-- =============================================================================

-- 启用 pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- -----------------------------------------------------------------------------
-- 表：sessions
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.sessions (
  session_id TEXT PRIMARY KEY,
  user_id UUID NOT NULL,
  summary TEXT,
  summary_keywords JSONB,
  summary_embedding vector(2048),
  l_interaction INTEGER DEFAULT 0,
  n_visit INTEGER DEFAULT 0,
  r_recency DOUBLE PRECISION DEFAULT 1.0,
  h_segment DOUBLE PRECISION DEFAULT 0.0,
  last_visit_time TIMESTAMPTZ,
  access_count_lfu BIGINT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 表：pages
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.pages (
  page_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  user_id UUID NOT NULL,
  user_input TEXT,
  agent_response TEXT,
  time_stamp TIMESTAMPTZ,
  preloaded BOOLEAN DEFAULT FALSE,
  analyzed BOOLEAN DEFAULT FALSE,
  pre_page_id TEXT,
  next_page_id TEXT,
  meta_info TEXT,
  meta_data JSONB,
  page_keywords JSONB,
  page_embedding vector(2048),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 表：long_term_user_profiles
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.long_term_user_profiles (
  user_id UUID PRIMARY KEY,
  profile_data TEXT,
  last_updated TIMESTAMPTZ DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 表：long_term_user_knowledge
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.long_term_user_knowledge (
  id TEXT PRIMARY KEY,
  user_id UUID NOT NULL,
  knowledge_text TEXT,
  time_stamp TIMESTAMPTZ DEFAULT NOW(),
  knowledge_embedding vector(2048)
);

-- -----------------------------------------------------------------------------
-- 表：long_term_assistant_knowledge
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.long_term_assistant_knowledge (
  id TEXT PRIMARY KEY,
  assistant_id UUID NOT NULL,
  user_id UUID,
  knowledge TEXT,
  time_stamp TIMESTAMPTZ DEFAULT NOW(),
  knowledge_embedding vector(2048)
);

-- -----------------------------------------------------------------------------
-- 可选：为向量列创建 HNSW 索引（建议在数据量大时执行；建索引可能耗时）
-- 如需创建索引，可取消下面语句的注释并在低流量时执行。
-- -----------------------------------------------------------------------------
-- CREATE INDEX IF NOT EXISTS idx_sessions_summary_embedding
--   ON public.sessions USING hnsw (summary_embedding vector_cosine_ops);

-- CREATE INDEX IF NOT EXISTS idx_pages_page_embedding
--   ON public.pages USING hnsw (page_embedding vector_cosine_ops);

-- CREATE INDEX IF NOT EXISTS idx_ltm_user_knowledge_embedding
--   ON public.long_term_user_knowledge USING hnsw (knowledge_embedding vector_cosine_ops);

-- CREATE INDEX IF NOT EXISTS idx_ltm_assistant_knowledge_embedding
--   ON public.long_term_assistant_knowledge USING hnsw (knowledge_embedding vector_cosine_ops);

-- =============================================================================
-- 以下为 pgvector RPC：在数据库侧做相似度检索（将这些函数也执行一次）
-- =============================================================================

-- 1. 按 summary_embedding 相似度返回该用户 top-k sessions（仅向量排序，不含关键词）
CREATE OR REPLACE FUNCTION public.match_sessions_by_embedding(
  p_user_id uuid,
  p_query_embedding vector(2048),
  p_limit int DEFAULT 10
)
RETURNS SETOF public.sessions
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT *
  FROM public.sessions
  WHERE sessions.user_id = p_user_id
  ORDER BY sessions.summary_embedding <=> p_query_embedding
  LIMIT p_limit;
END;
$$;

-- 2. 按 page_embedding 相似度返回某 session 下满足阈值的 pages
CREATE OR REPLACE FUNCTION public.match_pages_by_embedding(
  p_user_id uuid,
  p_session_id text,
  p_query_embedding vector(2048),
  p_sim_threshold float DEFAULT 0.0,
  p_limit int DEFAULT 50
)
RETURNS SETOF public.pages
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT *
  FROM public.pages
  WHERE pages.user_id = p_user_id
    AND pages.session_id = p_session_id
    AND (1 - (pages.page_embedding <=> p_query_embedding)) >= p_sim_threshold
  ORDER BY pages.page_embedding <=> p_query_embedding
  LIMIT p_limit;
END;
$$;

-- 3. 用户长期知识：按 knowledge_embedding 相似度检索
CREATE OR REPLACE FUNCTION public.match_user_knowledge_by_embedding(
  p_user_id uuid,
  p_query_embedding vector(2048),
  p_sim_threshold float DEFAULT 0.0,
  p_limit int DEFAULT 10
)
RETURNS SETOF public.long_term_user_knowledge
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT *
  FROM public.long_term_user_knowledge
  WHERE long_term_user_knowledge.user_id = p_user_id
    AND (1 - (long_term_user_knowledge.knowledge_embedding <=> p_query_embedding)) >= p_sim_threshold
  ORDER BY long_term_user_knowledge.knowledge_embedding <=> p_query_embedding
  LIMIT p_limit;
END;
$$;

-- 4. 助手长期知识：按 knowledge_embedding 相似度检索
CREATE OR REPLACE FUNCTION public.match_assistant_knowledge_by_embedding(
  p_assistant_id uuid,
  p_query_embedding vector(2048),
  p_sim_threshold float DEFAULT 0.0,
  p_limit int DEFAULT 10
)
RETURNS SETOF public.long_term_assistant_knowledge
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT *
  FROM public.long_term_assistant_knowledge
  WHERE long_term_assistant_knowledge.assistant_id = p_assistant_id
    AND (1 - (long_term_assistant_knowledge.knowledge_embedding <=> p_query_embedding)) >= p_sim_threshold
  ORDER BY long_term_assistant_knowledge.knowledge_embedding <=> p_query_embedding
  LIMIT p_limit;
END;
$$;

-- =============================================================================
-- 结束
-- =============================================================================

