# Nestora server: authentication foundation

This directory is a clean FastAPI server with secure cookie authentication.
It contains a static migration snapshot of the legacy domain-table schema but
never connects to the legacy database at runtime.

## What is included

- Server-side opaque sessions in an HttpOnly `nestora_session` cookie.
- A separate readable CSRF cookie used with the `X-CSRF-Token` header.
- A fixed JSON response envelope: `success`, `message`, `data`, and `meta`.
- SQLAlchemy async data access, explicit transactions, Alembic migrations, and
  a self-contained RBAC seed snapshot with a bootstrap super administrator.
- A self-contained Alembic migration for the remaining legacy domain tables;
  it creates table definitions only and does not copy legacy business data.

## First-time local setup

1. Enter this directory: `cd server`.
2. Create and activate an isolated Python environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install the runtime dependencies:

   ```bash
   python -m pip install --upgrade pip
   python -m pip install -e .
   ```

4. Copy `.env.example` to `.env` and set strong database and cookie values.
5. Create a new empty MySQL database: `python -m scripts.create_database`.
6. Create its tables: `python -m alembic upgrade head`.
7. Seed country, region, district, and city reference data:
   `python -m scripts.seed_locations`.
8. Seed the saved roles, features, role-feature permissions, and bootstrap administrator:
   `python -m scripts.seed_auth`.
9. Run the API through the installed environment: `python -m uvicorn app.main:app --reload`.

The commands above are intentionally manual. They can create or alter the
database, so do not run them against the legacy Nestora database.

`scripts.seed_locations` verifies the checksum of its pinned India state and
district source before inserting data. For an offline run, provide that exact
JSON snapshot explicitly with `--india-data-file /path/to/india.json`.

## Frontend integration note

This server keeps legacy route paths under `/api/auth`, but it does not return
a browser-visible JWT. A cross-origin browser client must use
`withCredentials: true` and send `X-CSRF-Token` on protected writes. Until the
client is changed or the API is served through the same origin, the old JWT
client cannot use cookie sessions end-to-end.
