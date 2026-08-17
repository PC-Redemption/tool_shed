#!/usr/bin/env python3
"""Build and validate the static Tool Shed documentation site."""

from __future__ import annotations

import argparse
import html
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
COMMANDS = ROOT / "docs" / "commands.md"
DEFAULT_OUTPUT = ROOT / "build" / "ts.rookaro.com"
PUBLIC_SOURCE = "https://github.com/PC-Redemption/tool_shed/blob/main/docs/commands.md"


@dataclass(frozen=True)
class Page:
    path: str
    title: str
    description: str
    source: str
    section: str


PAGES = (
    Page("", "Tool Shed", "Turn an incomplete idea into working, verified software with a flexible human and AI process.", "home.html", "overview"),
    Page("help", "Tool Shed Help", "Learn the Tool Shed process, then go deeper on the part of the lifecycle you need.", "help/index.html", "help"),
    Page("help/ideas", "Ideas and exploration", "Start with incomplete intent and explore the outcome before committing to a plan.", "help/ideas.html", "help"),
    Page("help/planning", "Planning", "Turn discoveries into proportionate, evidence-backed coordination.", "help/planning.html", "help"),
    Page("help/roadmaps", "Program roadmaps", "Give multi-milestone work direction without turning the plan into a rigid promise.", "help/roadmaps.html", "help"),
    Page("help/campaigns", "Campaigns", "Use focused owner-facing execution cycles with explicit outcomes and completion evidence.", "help/campaigns.html", "help"),
    Page("help/execution", "Execution levels", "Choose how far an authorized change should travel from implementation to production.", "help/execution.html", "help"),
    Page("help/review", "Review and completion", "Use actual evidence to accept the outcome, revise direction, or select the next campaign.", "help/review.html", "help"),
    Page("help/recovery", "Existing and interrupted work", "Orient safely in unfamiliar repositories and resume work without inventing history.", "help/recovery.html", "help"),
    Page("help/commands", "Using Tool Shed commands", "Route a request clearly while keeping natural language, scope, and authority intact.", "help/commands.html", "help"),
    Page("help/maintenance", "Installation and maintenance", "Install, update, validate, and preserve Tool Shed workspaces safely.", "help/maintenance.html", "help"),
)


SECTION_ANCHORS = {
    "Help And Discovery": ("discovery", "Help and discovery", "/help/commands/"),
    "Execution Endpoints": ("execution", "Execution", "/help/execution/"),
    "Owner Campaign Queue": ("campaigns", "Campaigns", "/help/campaigns/"),
    "Program Roadmaps": ("planning", "Planning and roadmaps", "/help/roadmaps/"),
    "Q&A Inbox": ("maintenance", "Maintenance and continuity", "/help/recovery/"),
    "Version And Update Status": ("maintenance", "Maintenance and continuity", "/help/maintenance/"),
    "Codex Reasoning Maintenance": ("maintenance", "Maintenance and continuity", "/help/maintenance/"),
    "Artifact And Workspace Requests": ("planning", "Planning and roadmaps", "/help/planning/"),
}


@dataclass(frozen=True)
class Command:
    syntax: str
    purpose: str
    group: str
    group_title: str
    help_path: str


def plain_markdown(value: str) -> str:
    value = re.sub(r"\[([^]]+)]\([^)]+\)", r"\1", value)
    value = re.sub(r"`([^`]+)`", r"\1", value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"\1", value)
    return value.strip().rstrip(".") + "."


def extract_commands(source: str) -> list[Command]:
    commands: list[Command] = []
    seen: set[str] = set()
    section = ""
    fence = ""
    default_purpose = {
        "Q&A Inbox": "Read the workspace Q&A inbox without clearing or rewriting it",
        "Artifact And Workspace Requests": "Ask Tool Shed to coordinate or preserve workspace work in the smallest useful form",
        "Execution Endpoints": "Run the requested validation level without changing source or environments",
    }

    def add(syntax: str, purpose: str) -> None:
        normalized = syntax.strip()
        if normalized in seen or section not in SECTION_ANCHORS:
            return
        group, group_title, help_path = SECTION_ANCHORS[section]
        seen.add(normalized)
        commands.append(Command(normalized, plain_markdown(purpose), group, group_title, help_path))

    for raw_line in source.splitlines():
        if raw_line.startswith("## "):
            section = raw_line[3:].strip()
            fence = ""
            continue
        if raw_line.startswith("```"):
            fence = "" if fence else raw_line[3:].strip()
            continue
        if section not in SECTION_ANCHORS:
            continue
        if raw_line.startswith("|"):
            cells = [cell.strip() for cell in raw_line.strip().strip("|").split("|")]
            if len(cells) >= 2:
                match = re.fullmatch(r"`(ts:[^`]+)`", cells[0])
                if match and cells[1] not in {"Usage", "Stop after", "Equivalent route"}:
                    add(match.group(1), cells[1])
            continue
        if fence == "text" and raw_line.strip().startswith("ts:"):
            add(raw_line.strip(), default_purpose.get(section, "Use this Tool Shed route"))
    return commands


def example_for(syntax: str) -> str:
    example = syntax
    replacements = {
        "<goal>": "refresh the release notes",
        "[scope]": "the current change",
        "<spot|focused|full|release>": "focused",
        "<topic-or-command>": "campaigns",
        "<topic>": "deployment options",
        "<campaign>": "022",
        "<id>": "M1",
        "<token>": "TOKEN",
        "<task>": "a repository migration",
        "<need>": "a deployment checklist",
        "<behavior change>": "the retry behavior",
        "<multi-step outcome>": "the authentication migration",
        "<unknown>": "deployment options",
        "<decision>": "use SQLite for local state",
        "<workpackage>": "wp-example",
    }
    for placeholder, value in replacements.items():
        example = example.replace(placeholder, value)
    example = re.sub(r"<[^>]+>", "example", example)
    return example


def command_id(command: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", command.lower()).strip("-")
    return f"cmd-{value[:72]}"


def render_reference(commands: list[Command]) -> str:
    group_order = ("discovery", "planning", "campaigns", "execution", "maintenance")
    groups: dict[str, list[Command]] = {key: [] for key in group_order}
    titles: dict[str, str] = {}
    for command in commands:
        groups[command.group].append(command)
        titles[command.group] = command.group_title
    quick_links = "".join(
        f'<a href="#{group}">{html.escape(titles[group])}</a>'
        for group in group_order
        if groups[group]
    )
    sections: list[str] = []
    for group in group_order:
        if not groups[group]:
            continue
        cards = []
        for command in groups[group]:
            cards.append(
                f'''<article class="ref-card" id="{command_id(command.syntax)}">
  <code>{html.escape(command.syntax)}</code>
  <p>{html.escape(command.purpose)}</p>
  <div class="ref-example"><span>Example</span><code>{html.escape(example_for(command.syntax))}</code></div>
  <a class="detail-link" href="{command.help_path}">Detailed help <span aria-hidden="true">→</span></a>
</article>'''
            )
        sections.append(
            f'''<section class="ref-section" id="{group}" aria-labelledby="{group}-title">
  <div class="section-heading"><p class="eyebrow">Command group</p><h2 id="{group}-title">{html.escape(titles[group])}</h2><a href="#top">Back to top</a></div>
  <div class="ref-grid">{"".join(cards)}</div>
</section>'''
        )
    return f'''<section class="page-hero compact" id="top">
  <p class="eyebrow">Bookmark this page</p>
  <h1>Tool Shed command reference</h1>
  <p class="lede">Every supported prompt route, on one searchable page. Commands guide the AI agent; they are not shell commands.</p>
  <nav class="jump-links" aria-label="Reference sections">{quick_links}</nav>
</section>
<aside class="source-note">Generated from the <a href="{PUBLIC_SOURCE}">canonical command reference</a>. Natural-language requests remain valid.</aside>
{"".join(sections)}'''


def navigation(section: str) -> str:
    items = (
        ("overview", "/", "Overview"),
        ("help", "/help/", "Help"),
        ("reference", "/ref/", "Reference"),
    )
    links = []
    for key, href, label in items:
        current = ' aria-current="page"' if key == section else ""
        links.append(f'<a href="{href}"{current}>{label}</a>')
    return "".join(links)


def shell(*, title: str, description: str, body: str, section: str) -> str:
    page_title = "Tool Shed" if title == "Tool Shed" else f"{title} · Tool Shed"
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#07131d">
  <meta name="description" content="{html.escape(description, quote=True)}">
  <link rel="stylesheet" href="/assets/site.css">
  <title>{html.escape(page_title)}</title>
</head>
<body>
  <a class="skip-link" href="#content">Skip to content</a>
  <header class="site-header">
    <a class="brand" href="/" aria-label="Tool Shed home"><span class="rook" aria-hidden="true">♜</span><span><b>ROOKARO</b><small>Tool Shed</small></span></a>
    <nav aria-label="Primary">{navigation(section)}</nav>
  </header>
  <main id="content">{body}</main>
  <footer class="site-footer"><p><b>Tool Shed</b> keeps human intent and AI execution aligned.</p><nav aria-label="Footer"><a href="/help/">Help</a><a href="/ref/">Reference</a><a href="https://github.com/PC-Redemption/tool_shed">Source</a></nav></footer>
</body>
</html>
'''


def write_page(public: Path, page: Page) -> None:
    fragment = (SITE / "pages" / page.source).read_text(encoding="utf-8")
    target = public / page.path / "index.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        shell(title=page.title, description=page.description, body=fragment, section=page.section),
        encoding="utf-8",
        newline="\n",
    )


def validate_site(public: Path, commands: list[Command]) -> list[str]:
    errors: list[str] = []
    html_files = sorted(public.rglob("*.html"))
    expected = [public / page.path / "index.html" for page in PAGES]
    expected.append(public / "ref" / "index.html")
    for path in expected:
        if not path.is_file():
            errors.append(f"missing generated page: {path.relative_to(public)}")
    anchors: dict[Path, set[str]] = {}
    for path in html_files:
        content = path.read_text(encoding="utf-8")
        anchors[path] = set(re.findall(r'\bid="([^"]+)"', content))
        if "<main" not in content or "<nav" not in content or "viewport" not in content:
            errors.append(f"missing semantic or responsive shell: {path.relative_to(public)}")
        lowered = content.lower()
        for private_marker in ("/home/", "192.168.", "jon@", "pcredemption.com"):
            if private_marker in lowered:
                errors.append(f"private deployment detail in {path.relative_to(public)}: {private_marker}")
        for reference in re.findall(r'(?:href|src)="([^"]+)"', content):
            if reference.startswith(("https://", "http://", "mailto:", "#")):
                continue
            path_part, _, anchor = reference.partition("#")
            if path_part.startswith("/"):
                candidate = public / path_part.lstrip("/")
            else:
                candidate = path.parent / path_part
            if path_part.endswith("/") or candidate.is_dir():
                candidate /= "index.html"
            if not path_part:
                candidate = path
            if not candidate.is_file():
                errors.append(f"broken local link in {path.relative_to(public)}: {reference}")
            elif anchor:
                target_anchors = anchors.get(candidate)
                if target_anchors is None:
                    target_anchors = set(re.findall(r'\bid="([^"]+)"', candidate.read_text(encoding="utf-8")))
                    anchors[candidate] = target_anchors
                if anchor not in target_anchors:
                    errors.append(f"missing anchor in {path.relative_to(public)}: {reference}")
    reference = (public / "ref" / "index.html").read_text(encoding="utf-8")
    for command in commands:
        escaped = html.escape(command.syntax)
        if escaped not in reference:
            errors.append(f"canonical command missing from reference: {command.syntax}")
    for anchor in ("planning", "campaigns", "maintenance"):
        if f'id="{anchor}"' not in reference:
            errors.append(f"stable reference anchor missing: {anchor}")
    return errors


def build(output: Path) -> tuple[Path, list[Command]]:
    if output.exists():
        shutil.rmtree(output)
    public = output / "public"
    public.mkdir(parents=True)
    shutil.copytree(SITE / "assets", public / "assets")
    for page in PAGES:
        write_page(public, page)
    commands = extract_commands(COMMANDS.read_text(encoding="utf-8"))
    reference = public / "ref" / "index.html"
    reference.parent.mkdir(parents=True)
    reference.write_text(
        shell(
            title="Command reference",
            description="A compact, complete, and bookmarkable reference for Tool Shed prompt routes.",
            body=render_reference(commands),
            section="reference",
        ),
        encoding="utf-8",
        newline="\n",
    )
    shutil.copy2(SITE / "deploy" / "docker-compose.yml", output / "docker-compose.yml")
    shutil.copy2(SITE / "deploy" / "nginx.conf", output / "nginx.conf")
    errors = validate_site(public, commands)
    if errors:
        raise ValueError("site validation failed:\n- " + "\n- ".join(errors))
    return public, commands


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Deployment bundle directory")
    parser.add_argument("--check", action="store_true", help="Build and validate in a temporary directory")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        with tempfile.TemporaryDirectory(prefix="tool-shed-site-") as temporary:
            public, commands = build(Path(temporary) / "bundle")
            print(f"Tool Shed documentation site check passed: {len(list(public.rglob('*.html')))} pages, {len(commands)} commands")
        return 0
    public, commands = build(args.output.resolve())
    print(f"Built {len(list(public.rglob('*.html')))} pages and {len(commands)} commands at {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
