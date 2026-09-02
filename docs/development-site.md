# Private Development Site

Status: implementation
Environment: development
Host: `sup.local` (`192.168.7.5`)
LAN endpoint: `http://192.168.7.5:8443`
Workpc endpoint: `http://127.0.0.1:8443`

The private development site is a separate deployment of the Tool Shed documentation and
dashboard stack. It shares the `sup.local` Docker daemon with production but shares no Compose
project, container name, network, volume, database, environment file, generated site tree, writable
mount, credential, reporter identity, log, backup path, or published port.

| Boundary | Development | Production |
| --- | --- | --- |
| Root | `/home/jon/docker/ts.rookaro.com-dev` | `/home/jon/docker/ts.rookaro.com` |
| Compose project | `tsrookarocom-dev` | `tsrookarocom` |
| Docs container | `ts-rookaro-com-dev` | `ts-rookaro-com` |
| Host endpoint | `192.168.7.5:8443` | `0.0.0.0:8087` behind the public router |
| Protocol | Plain HTTP on LAN/SSH tunnel only | Public HTTPS |
| Data | Empty PostgreSQL database plus deterministic synthetic rows | Production database |

The development site must never be added to public DNS, Nginx Proxy Manager, or the Rookaro public
hostname router. Production Compose commands must not be used to operate development, and
development commands must always retain the explicit `tsrookarocom-dev` project identity.

## Stage An Exact Commit

The stage operation exports the selected Git commit, builds the dashboard image from that clean
archive, generates the public site, and copies only deployment artifacts into the managed
development root. It does not use uncommitted files and does not create `.env` or start containers.

```bash
python3 scripts/development_site.py --json plan
python3 scripts/development_site.py --json stage --commit <exact-commit-sha>
```

The managed marker binds the staged commit, image tag, project, root, and endpoints. An existing
directory without that marker is refused.

## Protected Development Environment

After staging, copy `/home/jon/docker/ts.rookaro.com-dev/.env.example` to `.env`, replace the two
secret placeholders with new development-only values, and set mode `0600`. Never copy the
production `.env`, database password, Django secret, maintainer password, TOTP seed, reporter
credential, or session material. The deploy command checks only controlled identity fields and
does not print or retain secret values.

Credential and authentication creation is a protected operator boundary. Once explicitly
authorized, create the development-only values through protected host-local tooling, then deploy:

```bash
python3 scripts/development_site.py --json deploy
python3 scripts/development_site.py --json status
```

The development container runs migrations automatically. Real enrolled development reporters are
the normal dashboard data source. An empty dashboard may optionally seed deterministic,
credential-free sample rows; they are hidden by default and are not required for readiness:

```bash
docker compose --project-name tsrookarocom-dev \
  --project-directory /home/jon/docker/ts.rookaro.com-dev \
  --env-file /home/jon/docker/ts.rookaro.com-dev/.env \
  -f /home/jon/docker/ts.rookaro.com-dev/docker-compose.yml \
  exec dashboard python /app/dashboard/manage.py seed_dashboard_development

docker compose --project-name tsrookarocom-dev \
  --project-directory /home/jon/docker/ts.rookaro.com-dev \
  --env-file /home/jon/docker/ts.rookaro.com-dev/.env \
  -f /home/jon/docker/ts.rookaro.com-dev/docker-compose.yml \
  exec dashboard python /app/dashboard/manage.py check_dashboard_development
```

Do not use visible synthetic projects as fixture identity. Linux and Windows qualification should
enroll their actual disposable test-bed project identities. Re-running the optional seed command
also re-hides its two deterministic sample projects.

The development health response includes `"environment": "development"`; every dashboard and
login page displays a development banner. Production defaults retain HTTPS redirect, secure
cookies, HSTS, production cookie names, and the production environment marker.

## Access

The Linux test bed on `sup` and Windows test bed on `gogetter` use
`http://192.168.7.5:8443`. Workpc uses a persistent localhost-only OpenSSH tunnel. Copy
`scripts/workpc_development_tunnel.ps1` to Workpc and run it in the logged-in user session:

```powershell
.\workpc_development_tunnel.ps1 -Action Install -SshHost sup.local
.\workpc_development_tunnel.ps1 -Action Status
```

The scheduled task binds only `127.0.0.1:8443`, fails when the port cannot be bound, sends SSH
keepalives, starts at logon, and restarts after failure. It uses Workpc's existing OpenSSH host and
key configuration; no private key belongs in this repository. `Stop`, `Start`, and `Remove` operate
only the `ToolShedDevelopmentTunnel` task.

## Stop, Restart, And Rollback

```bash
python3 scripts/development_site.py --json stop
python3 scripts/development_site.py --json deploy
```

These commands address only `tsrookarocom-dev`. Staging preserves one previous generated public
tree as `public.previous`; application rollback stages the prior exact commit and redeploys it.
Database reset or volume deletion is intentionally not automated: it requires an exact target,
backup/disposition decision, and explicit destructive authority.

Before and after every development deployment, verify production remains healthy at
`http://127.0.0.1:8087/healthz`, production containers remain in project `tsrookarocom`, and no
production container, network, or volume identity changed.
