# Scheduled jobs

`scripts.jobs.run_daily` is the single entry point for all daily Nestora jobs.
It delegates the actual work to `app.jobs.daily`, keeping deployment scheduling
separate from business logic.

Run it once a day at 09:00 India time. For a host that supports `CRON_TZ`:

```cron
CRON_TZ=Asia/Kolkata
0 9 * * * cd /path/to/server && DEBUG=false ./.venv/bin/python -m scripts.jobs.run_daily
```

For platforms with their own scheduler UI, configure the equivalent command and
timezone there. Do not run this command from FastAPI startup or from every API
worker; the database delivery ledger makes retries safe, but one scheduler is
the intended deployment model.
