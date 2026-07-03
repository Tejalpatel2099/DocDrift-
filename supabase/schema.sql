-- ============================================================================
-- DocDrift — Supabase / PostgreSQL schema
-- Run this in the Supabase SQL Editor (SQL Editor -> New query -> paste -> Run).
-- Safe to re-run: uses IF NOT EXISTS everywhere.
-- ============================================================================

-- pgvector gives us the `vector` column type and cosine-distance operators.
create extension if not exists vector;

-- ---------------------------------------------------------------------------
-- repos: one row per indexed public GitHub repository.
-- `status` drives the frontend polling UI:
--   pending -> indexing -> ready | error
-- ---------------------------------------------------------------------------
create table if not exists repos (
  id              uuid primary key default gen_random_uuid(),
  github_url      text not null unique,
  name            text not null,
  default_branch  text,
  status          text not null default 'pending',
  last_indexed_at timestamptz,
  created_at      timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- chunks: embedded pieces of the repo (code by function/class, docs by heading).
-- embedding is 1536-dim to match OpenAI text-embedding-3-small.
-- ---------------------------------------------------------------------------
create table if not exists chunks (
  id          uuid primary key default gen_random_uuid(),
  repo_id     uuid not null references repos(id) on delete cascade,
  file_path   text not null,
  start_line  int  not null,
  end_line    int  not null,
  chunk_type  text not null check (chunk_type in ('code', 'doc')),
  content     text not null,
  embedding   vector(1536),
  created_at  timestamptz not null default now()
);

create index if not exists chunks_repo_id_idx on chunks (repo_id);
create index if not exists chunks_chunk_type_idx on chunks (chunk_type);

-- IVFFlat index for fast approximate cosine search. Build AFTER inserting data
-- for best results; for v1's repo sizes this is optional but cheap to keep.
create index if not exists chunks_embedding_idx
  on chunks using ivfflat (embedding vector_cosine_ops) with (lists = 100);

-- ---------------------------------------------------------------------------
-- drift_flags: results of a "Re-scan". One row per doc chunk the LLM judged
-- to be out of sync with the current code.
-- ---------------------------------------------------------------------------
create table if not exists drift_flags (
  id                uuid primary key default gen_random_uuid(),
  repo_id           uuid not null references repos(id) on delete cascade,
  doc_chunk_id      uuid references chunks(id) on delete set null,
  related_code_path text,
  verdict           text not null,  -- e.g. 'in_sync' | 'drifted'
  reason            text,
  severity          text not null default 'low' check (severity in ('low', 'medium', 'high')),
  created_at        timestamptz not null default now()
);

create index if not exists drift_flags_repo_id_idx on drift_flags (repo_id);

-- ---------------------------------------------------------------------------
-- match_chunks: RPC for cosine similarity top-k retrieval (used in Phase 2).
-- Returns the closest chunks to a query embedding, optionally filtered by
-- repo and chunk_type. Distance operator <=> is cosine distance in pgvector,
-- so similarity = 1 - distance.
-- ---------------------------------------------------------------------------
create or replace function match_chunks(
  query_embedding vector(1536),
  match_repo_id   uuid,
  match_count     int default 10,
  filter_type     text default null
)
returns table (
  id         uuid,
  file_path  text,
  start_line int,
  end_line   int,
  chunk_type text,
  content    text,
  similarity float
)
language sql stable
as $$
  select
    c.id,
    c.file_path,
    c.start_line,
    c.end_line,
    c.chunk_type,
    c.content,
    1 - (c.embedding <=> query_embedding) as similarity
  from chunks c
  where c.repo_id = match_repo_id
    and (filter_type is null or c.chunk_type = filter_type)
  order by c.embedding <=> query_embedding
  limit match_count;
$$;
