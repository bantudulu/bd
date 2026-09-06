# BantuDulu Production Security Runbook

This repository is configured so production runtime does not mutate schema or seed demo data by default.

## Required production environment variables

- `SECRET_KEY` — random secret, never commit it.
- `APP_ENV=production`
- `DATABASE_URL` — persistent PostgreSQL/MySQL connection URL.
- `STARTUP_DB_INIT=false`
- `ENABLE_DEMO_SEED=false`
- `ENABLE_CATALOG_SYNC=false`

Recommended:
- `GOOGLE_CLIENT_ID`
- `TURNSTILE_SITE_KEY`
- `TURNSTILE_SECRET_KEY`

Keep disabled until a real payment backend is connected:
- `PAYMENT_BANK_ENABLED=false`
- `PAYMENT_QRIS_ENABLED=false`

After applying the marketplace migration:
- `MARKETPLACE_SCHEMA_ENABLED=true`

## Persistent database cutover

For a new empty persistent database, set `DATABASE_URL` and migrate current SQLite data:

```bash
python scripts/migrate_sqlite_to_persistent.py
alembic stamp head
```

For an existing BantuDulu database that already has the core tables but not the new marketplace tables:

```bash
alembic upgrade head
```

After the extension tables exist, set `MARKETPLACE_SCHEMA_ENABLED=true`.

## Admin account

Create or rotate a real admin account:

```bash
python scripts/create_admin.py
```

Never use the source-code demo password in production.

## Deployment gate

Before deploying:

```bash
python scripts/production_readiness.py
python -c "from app.main import app; print(len(app.openapi()['paths']))"
```

## Security model

- Customer order reads are ownership-scoped.
- Admin API role is revalidated against the database.
- Login/register use honeypot + rate limiting and can require Cloudflare Turnstile.
- Google credentials are verified server-side before creating a customer session.
- API responses and authenticated pages are `no-store`.
- Service worker never caches `/api/*` or authenticated pages.
- Bank/QRIS are unavailable until real payment reconciliation exists.
