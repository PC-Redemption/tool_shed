# Tool Shed Documentation Site

The public Tool Shed guide is served at [ts.rookaro.com](https://ts.rookaro.com). Canonical site
source is tracked in this repository under `site/`; `/home/jon/docker/ts.rookaro.com` on `sup` is
only a generated deployment copy.

## Information Architecture

- `/` explains the flexible human/AI development process.
- `/help/` and its direct-loadable topic paths provide the detailed operating guide.
- `/ref/` is one compact command page with stable section anchors.

Page fragments live under `site/pages/`, shared styling lives under `site/assets/`, and the
deployment definition lives under `site/deploy/`. The generator wraps each fragment in the common
semantic shell and validates internal links, anchors, required pages, assets, and public-content
privacy markers.

`docs/commands.md` is the only canonical command catalog. `scripts/build_docs_site.py` parses its
documented prompt tables and command blocks to generate `/ref/`; do not manually add a second
command inventory to the site. When commands change, update `docs/commands.md`, run the site check,
and rebuild. Explanatory help pages may use selected examples but must not claim new routes.

## Generate And Preview

Run a disposable validation build:

```bash
python3 scripts/build_docs_site.py --check
```

Build the deployable bundle under the ignored `build/` directory:

```bash
python3 scripts/build_docs_site.py
```

Preview it from the repository root, then open `http://127.0.0.1:8088/`:

```bash
python3 -m http.server 8088 --directory build/ts.rookaro.com/public
```

Run the focused tests with:

```bash
python3 -m unittest tests.test_docs_site
```

## Deploy The Separate Site Server

The site is intentionally its own Docker Compose project and nginx container. It is not embedded
in the existing Rookaro landing site or router container. From a validated canonical checkout:

1. Build with `python3 scripts/build_docs_site.py`.
2. Copy the contents of `build/ts.rookaro.com/` to
   `/home/jon/docker/ts.rookaro.com/` on `sup`.
3. On `sup`, run `docker compose up -d` from that deployment directory.
4. Confirm `ts-rookaro-com` is healthy and `http://127.0.0.1:8087/healthz` returns `healthy`.

The host port is `8087`. Before deploying, confirm the port and container name remain unused.
The generated `public/` directory is mounted read-only into `nginx:alpine`; nginx configuration is
also mounted read-only.

## Route Through Rookaro

Follow `/home/jon/docker/rookaro.com/VISITING-CODEX.md` on `sup`. Preserve every existing live
route, edit the bind-mounted `config/routes.json` in place, and add exactly:

```json
{
  "host": "ts.rookaro.com",
  "target": "http://192.168.7.5:8087",
  "require_https": true
}
```

Wildcard DNS and TLS already cover the hostname; do not add a DNS record, an Nginx Proxy Manager
host, or a wildcard router route for this site.

## Verify A Deployment

Verify all layers rather than treating configuration as proof:

- container health and the host-local health endpoint;
- direct loads for `/`, `/help/`, every linked help topic, and `/ref/`;
- `/ref/#planning`, `/ref/#campaigns`, and `/ref/#maintenance`;
- CSS response, internal links, and absence of private paths, addresses, credentials, and project
  state in generated public HTML;
- desktop and mobile viewport layouts;
- router selection reports `X-Rookaro-Route: ts.rookaro.com` over public HTTPS;
- representative existing Rookaro routes remain selected correctly;
- an unrelated hostname still reaches the branded fallback.

For rollback, restore the prior deployment directory if one exists, or stop the dedicated Compose
project and remove only the exact `ts.rookaro.com` route from the preserved route configuration.
Do not restart Nginx Proxy Manager for an ordinary site rollback.
