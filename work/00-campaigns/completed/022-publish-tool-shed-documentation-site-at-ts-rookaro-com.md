# Publish Tool Shed documentation site at ts.rookaro.com

Status: complete
Type: campaign
Updated: 2026-08-17
Next Action: none
Campaign ID: publish-tool-shed-documentation-site-at-ts-rookaro-com
Campaign Number: 022
Outcome: Create and operate a responsive public Tool Shed documentation site whose root teaches the flexible human/AI development process, whose /help hierarchy provides source-grounded guidance, and whose single-page /ref gives a fast bookmarkable command reference without duplicating the canonical command catalog.
Primary Focus Areas: provider-portability
Supporting Focus Areas: qualification-release
Depends On: none
Decision: none
Detour For: none
Return To: none
Completion Gate: Git-tracked canonical site source implements /, direct-loadable /help pages, and single-page /ref from authoritative Tool Shed documentation; maintainer generation, preview, deployment, routing, and verification instructions are current; focused and full repository checks pass; a healthy nginx:alpine deployment serves port 8087 from /home/jon/docker/ts.rookaro.com; the exact HTTPS Rookaro route is active; public paths, anchors, assets, desktop/mobile layouts, privacy review, existing routes, and unrelated-host fallback are verified end to end.
Completion Evidence: Generated 12 direct-loadable responsive pages and 55 canonical command cards; focused site checks and the full 128-test validator passed; GitHub Validate run 32057123667 passed on Linux and Windows; dedicated nginx:alpine container ts-rookaro-com is healthy on port 8087; exact HTTPS route is active; public paths, stable anchors, assets, build hashes, privacy markers, desktop/mobile overflow, existing route selection, and unrelated-host fallback were verified.
Completion Date: 2026-08-17
Completion Order: 20
Disposition: completed

## Request

Create and maintain the public Tool Shed documentation site at `https://ts.rookaro.com`.

### Confirmed deployment context

- Wildcard DNS and Nginx Proxy Manager wildcard TLS already cover `*.rookaro.com`.
- The healthy `rookaro-router` on `sup` receives traffic on port `8080`.
- Exact routes are maintained in `/home/jon/docker/rookaro.com/config/routes.json` under the
  procedure in `/home/jon/docker/rookaro.com/VISITING-CODEX.md`.
- `ts.rookaro.com` currently reaches the branded unconfigured-host `404` fallback.
- Port `8087` was observed available during discovery.
- Keep canonical source in this Git-tracked Tool Shed repository. Treat
  `/home/jon/docker/ts.rookaro.com` as a deployed copy, not the editing source.
- Deploy a small health-checked `nginx:alpine` service and register this exact route without adding
  DNS or Nginx Proxy Manager configuration unless current evidence disproves the discovery:

```json
{
  "host": "ts.rookaro.com",
  "target": "http://192.168.7.5:8087",
  "require_https": true
}
```

### Product intent and information architecture

The website presents Tool Shed as a flexible AI-assisted development process, not merely a command
catalog. It has three deliberately distinct surfaces:

1. `/` introduces Tool Shed and its human/AI development philosophy to a new user.
2. `/help` is the detailed manual, with direct-loadable topic pages where useful.
3. `/ref` is one compact, bookmarkable command-reference page with no `/ref/*` subpages.

Use simple global navigation: `Tool Shed`, `Overview`, `Help`, and `Reference`. The approximate help
structure is `/help/ideas`, `/help/planning`, `/help/roadmaps`, `/help/campaigns`,
`/help/execution`, `/help/maintenance`, and `/help/commands`; adjust only when the repository's
actual documentation supports a cleaner organization.

### Overview requirements

Lead with the concept that Tool Shed turns an incomplete idea into working, verified software
through a conversational human/AI process. Explain that users need not begin with architecture,
requirements, or a complete design.

Visually communicate the adaptable flow from idea through exploration, planning, roadmap,
campaign, build/test/review cycles, and completion. Show that new knowledge may send work back to
planning or revise the roadmap; do not present a rigid waterfall.

Clearly distinguish:

- **Idea:** incomplete intent is a valid starting point.
- **Planning:** collaborative investigation answers, “What are we really trying to build?”
- **Roadmap:** ordered outcomes and checkpoints answer, “How do we get from here to done?”
- **Campaign:** a focused execution cycle answers, “What are we accomplishing right now?”
- **Review and adaptation:** actual evidence selects the next campaign or revises the roadmap.
- **Completion:** the intended result works and is verified; compiling, running tests, finishing a
  prompt, or ending one campaign is not sufficient by itself.

Make the roadmap/campaign review loop visually prominent and preserve this central message:
**Roadmaps provide direction. Campaigns provide execution. Reality is allowed to change the
roadmap.**

Include a major human/AI partnership section built around “You steer. AI works the process.” The
user retains intent, judgment, priorities, corrections, and outcome acceptance. AI supplies much
of the investigation, planning assistance, implementation, testing, verification, documentation,
and continuity, but is not autonomous project authority.

Introduce commands only after explaining the process. Use a small set of real examples from
`docs/commands.md`, explain that natural language remains valid, link examples to detailed help,
and provide a prominent `/ref` call to action.

### Help requirements

Make `/help` a documentation landing page organized for both learning and operation. Detailed pages
should explain what a feature is, when to use it, how it fits the lifecycle, real commands and
expected behavior, examples, common misuse, completion conditions, and related topics.

Cover at least ideas/exploration, planning, roadmaps, campaigns, execution, review/completion,
commands, maintenance, interrupted or recovered work, existing projects, and unfamiliar
repositories. Campaign guidance must explain scope, roadmap relationships, execution expectations,
stopping and completion rules, and how campaign evidence may alter a roadmap. Use actual
implementation and current repository documentation as authority; do not invent behavior to fill
pages.

### Reference requirements

Make `/ref` fast to scan, friendly to browser search, usable on phones, printable where practical,
and addressable through stable anchors such as `/ref#planning`, `/ref#campaigns`, and
`/ref#maintenance`. Organize real commands according to the canonical documentation. Each entry
contains only its command and syntax, one-line purpose, one or two short examples, and a detailed
help link. Never invent a `ts:` command.

Keep `docs/commands.md` authoritative unless inspection identifies a better existing canonical
source. Prefer generated command-reference content. If complete generation is impractical, make
the synchronization mechanism explicit, testable, and difficult to overlook.

### Design and implementation constraints

- Keep the Rookaro visual identity where practical without overdesigning the site.
- Give `/` a visual explanatory treatment, `/help` a readable documentation hierarchy and
  navigation system, and `/ref` a denser command-oriented presentation.
- Use responsive semantic HTML and CSS, lightweight JavaScript only where it materially helps,
  stable headings/anchors, comfortable reading widths, and desktop/mobile support.
- Avoid unnecessary frameworks or heavy dependencies when static HTML/CSS/JS is sufficient.
- Preserve useful existing material and prefer actual Tool Shed terminology when it differs from
  assumptions in this request.
- Do not expose credentials, internal addresses or paths, private workspace state, or private
  project information in public content.

### Delivery, verification, and maintenance

Do not stop at mockups. Inspect, plan, implement, build, test, deploy, route, and verify the public
site. Confirm direct loading of help subpaths rather than relying only on client-side navigation.
Verify `/`, `/help`, topic pages, `/ref`, anchors, assets, desktop/mobile layouts, container health,
port `8087`, router selection, public HTTPS, privacy, unaffected existing routes, and the branded
fallback for unrelated hosts.

Update the most appropriate existing maintainer documentation with the canonical source,
command-reference source, generation, preview, build, deployment, routing, verification, deployed
copy, and future command-propagation procedures. Avoid scattering redundant README files.

At completion report the implementation, files changed, deployment changes, URLs, verification,
assumptions or terminology discrepancies, and remaining maintenance concerns.

## Completion Check

Git-tracked canonical site source implements /, direct-loadable /help pages, and single-page /ref from authoritative Tool Shed documentation; maintainer generation, preview, deployment, routing, and verification instructions are current; focused and full repository checks pass; a healthy nginx:alpine deployment serves port 8087 from /home/jon/docker/ts.rookaro.com; the exact HTTPS Rookaro route is active; public paths, anchors, assets, desktop/mobile layouts, privacy review, existing routes, and unrelated-host fallback are verified end to end.
