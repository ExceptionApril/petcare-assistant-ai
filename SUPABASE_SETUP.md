# Supabase RAG Setup (persistent vector store)

By default Petlio stores RAG documents in a **local ChromaDB** folder. That works
on your laptop, but on **Streamlit Cloud the filesystem is wiped on every
restart**, so uploaded documents disappear. Moving the vector store to Supabase
(Postgres + pgvector) makes it **persistent** — and the app automatically uses
Supabase the moment the two credentials below are present (otherwise it falls
back to local ChromaDB, no code change needed).

## 1. Create a free Supabase project
1. Go to <https://supabase.com> → **New project** (free tier is enough).
2. Pick a name + database password, wait ~2 minutes for it to provision.

## 2. Run the schema migration
1. In your project, open **SQL Editor → New query**.
2. Paste the entire contents of [`supabase_schema.sql`](supabase_schema.sql) and click **Run**.
   This enables `pgvector`, creates the `documents` table, the cosine-similarity
   index, and the `match_documents()` search function.

## 3. Copy your credentials
In the Supabase dashboard → **Settings → API**:
- **Project URL** → `SUPABASE_URL`
- **anon / public** key → `SUPABASE_KEY`

## 4. Add them to the app
- **Local dev** — edit `.env`:
  ```env
  SUPABASE_URL=https://xxxxxxxx.supabase.co
  SUPABASE_KEY=eyJhbGciOi...
  ```
- **Streamlit Cloud** — *Manage app → Settings → Secrets*, add the same two lines
  (TOML format, values in quotes). See `.streamlit/secrets.toml.example`.

## 5. Verify
Restart the app. The sidebar status pill should switch from
**"Local store"** (amber dot) to **"Supabase store"** (green dot). Upload a PDF/TXT,
restart the app, and the document count should persist.

### Notes
- The embedding model is ChromaDB's bundled ONNX `all-MiniLM-L6-v2` (**384-dim**).
  The SQL column `vector(384)` must match — don't change one without the other.
- `anon` key is fine for this single-tenant demo. For production, restrict access
  with Row Level Security or use a service-role key kept server-side only.
- To wipe the store: `delete from documents;` in the SQL editor.
