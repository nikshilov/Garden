# 🗄️ Supabase / Postgres Persistence Guide

Garden World Chat supports two interchangeable persistence back-ends:

| Backend | Use-case | Pros | Cons |
|---------|----------|------|------|
| **JSON (default)** | Local dev / offline | Zero-setup; human-readable | Not multi-user; no joins/search |
| **Supabase** | Cloud / multi-device | Fully-managed Postgres + storage; SQL; auth | Requires setup & network access |

---
## 1. Prerequisites

1. **Supabase project** – sign in at <https://app.supabase.com> and create a new project.
2. **Service Role Key** – `Settings → API → Project API keys → service_role`.
3. **Project URL** – `Settings → API → Project URL (https://<ref>.supabase.co)`.
4. **Python package** inside your virtualenv:
   ```bash
   pip install supabase
   ```

> ✨  **Tip:** always work inside the repository’s `.venv` (PEP 668 safe).

---
## 2. Environment variables

Create / edit `prototype/.env` (see `.env.example`):
```env
# Select backend
STORAGE_BACKEND=supabase

# Supabase credentials
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Other variables (API keys, thresholds, etc.) remain unchanged.

---
## 3. Database schema

Run these statements once (SQL editor or `psql`):
```sql
-- Memories
create table if not exists memories (
  id uuid primary key,
  character_id text not null,
  event_text text not null,
  weight real default 0.1,
  sentiment integer default 0,
  emotions jsonb default '{}',
  created_at timestamptz default now(),
  last_accessed timestamptz default now(),
  last_touched timestamptz default now(),
  archived boolean default false
);

-- Events / scheduler
create table if not exists events (
  id uuid primary key,
  character_id text not null,
  event_time timestamptz not null,
  description text,
  reminder_time timestamptz,
  completed boolean default false,
  user_responded boolean default false,
  created_at timestamptz default now()
);
```
No RLS is required for server-side key usage, but you may add policies for anon/read-only clients later.

---
## 4. Running & testing

### Local run (CLI / Streamlit)
```bash
source .venv/bin/activate   # ensure venv
python -m garden_graph.cli  # or `streamlit run ...`
```
All messages/memories will persist to Postgres.

### Automated tests
```bash
STORAGE_BACKEND=supabase pytest -q        # 55 green tests
```
The suite truncates JSON files and uses isolated tables; data remains in your DB unless you clean it.

---
## 5. Maintenance / troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Errno 8 nodename nor servname provided` | Wrong `SUPABASE_URL` | Copy exact URL from **Settings → API** |
| `RuntimeError: supabase-py package not installed` | package missing | `pip install supabase` inside venv |
| `TypeError: '<' not supported between str and datetime` | Old rows with string timestamps | Update code (already fixed) or delete test data |
| Pip “externally-managed” error | PEP 668 macOS Python | Always use the project `.venv` |

---
## 6. Switching back to JSON
Simply set `STORAGE_BACKEND=json` (or unset) and restart – the application falls back to local flat-files in `prototype/garden_graph/data/`.

---
_Last updated: 2025-06-17_
