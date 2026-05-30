-- ============================================================================
-- Petlio RAG — Supabase (Postgres + pgvector) schema
--
-- HOW TO RUN:
--   1. Create a free project at https://supabase.com
--   2. Open the project → SQL Editor → New query
--   3. Paste this whole file and click "Run"
--   4. Copy Project URL + anon key from Settings → API into your
--      .env / Streamlit secrets as SUPABASE_URL and SUPABASE_KEY
--
-- The embedding dimension (384) matches chromadb's bundled MiniLM model used
-- in supabase_store.py. Do not change it without re-ingesting all documents.
-- ============================================================================

-- 1. Enable the pgvector extension
create extension if not exists vector;

-- 2. The documents table — one row per text chunk
create table if not exists documents (
    id           text primary key,
    content      text not null,
    source       text,
    chunk_index  int,
    embedding    vector(384),
    created_at   timestamptz default now()
);

-- 3. Approximate-nearest-neighbour index for fast cosine search
create index if not exists documents_embedding_idx
    on documents using ivfflat (embedding vector_cosine_ops)
    with (lists = 100);

-- index for quick per-source listing/deletion
create index if not exists documents_source_idx on documents (source);

-- 4. Similarity search RPC called by supabase_store.retrieve()
--    Returns the closest `match_count` chunks by cosine similarity.
create or replace function match_documents(
    query_embedding vector(384),
    match_count int default 5
)
returns table (
    id          text,
    content     text,
    source      text,
    chunk_index int,
    similarity  float
)
language sql stable
as $$
    select
        d.id,
        d.content,
        d.source,
        d.chunk_index,
        1 - (d.embedding <=> query_embedding) as similarity
    from documents d
    order by d.embedding <=> query_embedding
    limit match_count;
$$;
