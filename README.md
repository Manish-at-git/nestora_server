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

## Refreshing the IAM seed snapshot

To capture the configured database's current roles, features, and role-feature
permissions into the checked-in seed snapshot, run:

`python -m scripts.refresh_iam_seed_snapshot`

The command reads the database only and rewrites
`app/modules/iam/seed_data.py`. It does not run any seed or migration and
never changes database records.

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
   npm install
   ```

4. Copy `.env.example` to `.env` and set strong database and cookie values.
5. Create a new empty MySQL database: `python -m scripts.create_database`.
6. Create its tables: `python -m alembic upgrade head`.
7. Seed country, region, district, and city reference data:
   `python -m scripts.seeds.seed_locations`.
8. Seed the saved roles, features, role-feature permissions, and bootstrap administrator:
   `python -m scripts.seeds.seed_auth`.
9. Optional for local or test environments: seed the one-time entity-type
   catalogue: `python -m scripts.seeds.seed_entity_types`. It creates or
   reactivates only Condominium, Townhouse, and Single Family.
10. Optional for local or test environments: after entity types, seed every
    scripted sample entity: `python -m scripts.seeds.seed_entities`. Entity
    records are otherwise live application data and this command is never run
    automatically.
11. Optional for local or test environments: seed the editable onboarding
    welcome and password-reset OTP templates: `python -m scripts.seeds.seed_email_templates`.
    The seed reads the server-owned HTML files in
    `app/modules/email_templates/templates`. Existing administrator-edited
    templates are preserved; only missing templates are created and
    soft-deleted defaults are restored.
12. Run the API through the installed environment: `python -m uvicorn app.main:app --reload`.

The commands above are intentionally manual. They can create or alter the
database, so do not run them against the legacy Nestora database.

`scripts.seeds.seed_locations` verifies the checksum of its pinned India state and
district source before inserting data. For an offline run, provide that exact
JSON snapshot explicitly with `--india-data-file /path/to/india.json`.

## Frontend integration note

This server keeps legacy route paths under `/api/auth`, but it does not return
a browser-visible JWT. A cross-origin browser client must use
`withCredentials: true` and send `X-CSRF-Token` on protected writes. Until the
client is changed or the API is served through the same origin, the old JWT
client cannot use cookie sessions end-to-end.
