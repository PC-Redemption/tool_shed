# Hosted Dashboard Operations

The Tool Shed dashboard is an optional advisory read model for explicitly enrolled local
instances. Local Hybrid SQLite state remains authoritative. The hosted service cannot invoke Tool
Shed commands, mutate local state, restart workers, cancel work, or retrieve arbitrary detail.

## Privacy contract

Report schema v1 rejects unknown fields. It accepts project and instance UUIDs, display name,
platform and client versions, current lifecycle counters, controlled material-event codes,
content-free App Server aggregates and failure signatures, and Work Efficiency aggregates with
explicit measured-token coverage. It rejects paths, prompts, source text, commands, raw output,
exception messages, credentials, secrets, and uncontrolled event summaries. Requests are capped at
256 KiB; event and failure lists are bounded.

Reporter credentials are opaque 256-bit values. The server stores only a SHA-256 verifier and a
non-secret lookup prefix. Local connection state is mode `0600` under a mode `0700` user-local
directory. The credential is returned once after an authenticated approval and is never printed by
status. Disconnect revokes it server-side.

Material events are retained for 90 days. Sanitized failure groups are retained for 30 days and
reports include at most 20 groups. Hosted rows are current advisory state; deleting or recovering
the hosted database never alters local Tool Shed work.

## Local enrollment and reporting

Obtain fresh bindings before mutations:

```bash
python3 scripts/project_identity.py --workspace . identity --operation dashboard-connect --json
python3 scripts/project_identity.py --workspace . identity --operation dashboard-report --json
```

Start enrollment, approve the displayed code in the authenticated dashboard, then poll once:

```bash
python3 scripts/dashboard_reporter.py --workspace . connect \
  --server https://ts.rookaro.com --project-binding <dashboard-connect-binding>
python3 scripts/dashboard_reporter.py --workspace . connect-poll \
  --project-binding <dashboard-connect-binding>
```

Managed database writes enqueue a controlled event and wake a detached singleton worker. Its local
SQLite outbox preserves ordered idempotent delivery, bounded exponential backoff, one-minute
heartbeats, and a final quiescent report after two idle hours. The independent safety pass compares
the local domain digest every 15 minutes and delivers a convergence report when it changes:

```bash
python3 scripts/dashboard_reporter.py --workspace . scheduler-plan
python3 scripts/dashboard_reporter.py --workspace . scheduler-install \
  --project-binding <dashboard-report-binding>
```

Scheduler installation is project-scoped: a systemd user timer on Linux, LaunchAgent on macOS, or
scheduled task on Windows. Inspect without credentials using `status`. Revoke with `disconnect`.
Network or service failures leave the outbox queued and never fail the originating local write.
Remove the safety scheduler with `scheduler-remove` when disconnecting the project permanently.

## Production deployment

The supported compose stack in `site/deploy/` runs Nginx, Django 5.2 LTS with Gunicorn, and
PostgreSQL 17. It requires these protected environment values:

- `POSTGRES_PASSWORD`: unique database password;
- `TOOL_SHED_DASHBOARD_SECRET_KEY`: at least 50 random characters;
- optional `POSTGRES_DB` and `POSTGRES_USER`;
- optional `TOOL_SHED_DASHBOARD_ALLOWED_HOSTS` and
  `TOOL_SHED_DASHBOARD_CSRF_ORIGINS` for a non-default host;
- optional `TOOL_SHED_DASHBOARD_AUTH_MODE`: `local-mfa` by default, or `local-password` for
  ordinary username/password authentication.

Do not commit the deployment environment. From the exact release checkout, build the immutable
dashboard image and public site, then stage `docker-compose.yml`, `nginx.conf`, and the generated
`public/` tree in the production deployment directory. Set `TOOL_SHED_DASHBOARD_IMAGE_TAG` there to
the exact release tag. Start without rebuilding from a mutable production directory:

```bash
docker build -f dashboard/Dockerfile -t tool-shed-dashboard:<release-tag> .
python3 scripts/build_docs_site.py --output <production-directory>
docker compose --project-directory <production-directory> \
  -f <production-directory>/docker-compose.yml up -d --no-build
docker compose --project-directory <production-directory> \
  -f <production-directory>/docker-compose.yml ps
```

The dashboard runs migrations and static collection before Gunicorn. Nginx rate-limits API
requests, serves public documentation and dashboard static assets, and proxies `/dashboard/` and
`/api/v1/`. Authenticated dashboard pages use one visibility-scoped, read-only server-sent event
stream to reload when semantic database state changes. Hidden and navigated-away pages close their
streams, and heartbeat-only receipt timestamps do not trigger reloads. Work Efficiency stores and
displays metric changes rather than a new row for every unchanged sliding-window report. Security
settings require HTTPS, secure cookies, HSTS, an explicit host allowlist, and CSRF trusted origins.

## First maintainer and optional MFA

Create the first maintainer interactively. When `TOOL_SHED_DASHBOARD_AUTH_MODE=local-mfa`, also
provision TOTP; `local-password` requires only the maintainer username and password. Do not put
passwords, TOTP seeds, or provisioning URIs in logs or tracked files.

```bash
docker compose -f site/deploy/docker-compose.yml exec dashboard \
  python /app/dashboard/manage.py createsuperuser
```

For `local-mfa` only:

```bash
docker compose -f site/deploy/docker-compose.yml exec dashboard \
  python /app/dashboard/manage.py dashboard_admin_mfa begin --username <username>
docker compose -f site/deploy/docker-compose.yml exec dashboard \
  python /app/dashboard/manage.py dashboard_admin_mfa confirm \
  --username <username> --token <current-code>
```

For either mode:

```bash
docker compose -f site/deploy/docker-compose.yml exec dashboard \
  python /app/dashboard/manage.py check_dashboard_production
```

The last command fails closed unless the database is reachable, production security settings are
valid, and an active staff maintainer exists. In `local-mfa` mode it additionally requires a
confirmed TOTP device and OTP-aware authentication for the fleet dashboard and Django admin.

## Backup, restore, and rollback

Run an encrypted PostgreSQL backup daily from protected operator automation. Keep seven daily and
four weekly copies. One portable pattern is `pg_dump --format=custom` piped directly to `age` with
an operator-owned recipient; never write an unencrypted intermediate dump. Store the recipient in
protected configuration and the private key outside the host. Record backup timestamp, database,
encrypted artifact size, and verification result—not secrets.

Quarterly, restore the newest encrypted backup into an isolated PostgreSQL 17 instance, run
migrations, run `check_dashboard_production` with isolated maintainer fixtures, and verify project,
instance, receipt, event, and aggregate counts. The first-release objectives are RPO at most 24
hours and RTO at most two hours.

For an application rollback, retain the PostgreSQL volume, deploy the previous immutable release,
and run its compatibility checks before serving traffic. Do not reverse a migration until its
documented safety is proven. If the database is unavailable, keep the dashboard offline while local
reporters safely queue. After recovery, reporters converge without local work loss. Revoke and
re-enroll a reporter if a credential may have been exposed.

## Operational checks

- Public: `/`, `/help/`, and `/dashboard/healthz` return without authentication.
- Protected: `/dashboard/`, `/dashboard/admin/`, project views, and enrollment decisions require
  a maintainer password, plus TOTP when `local-mfa` is configured.
- Reporter: an invalid bearer token receives `401`; valid repeated idempotency keys do not duplicate
  work; stale sequence numbers fail.
- Fleet: stale means no report for 20 minutes; `Unknown` is preserved when an aggregate is absent or
  measured-token coverage is incomplete.
- Capacity: first-release qualification covers at least 100 enrolled rows and 25 currently active
  instances without changing the local authority or payload contract.
