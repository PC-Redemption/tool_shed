from __future__ import annotations

import importlib.util
import html
import re
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_docs_site", ROOT / "scripts" / "build_docs_site.py")
assert SPEC and SPEC.loader
SITE_BUILDER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SITE_BUILDER
SPEC.loader.exec_module(SITE_BUILDER)


class DocumentationSiteTests(unittest.TestCase):
    def test_build_produces_direct_loadable_pages_and_complete_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            public, commands = SITE_BUILDER.build(Path(temporary) / "bundle")
            expected = (
                "index.html",
                "guide/index.html",
                "guide/new-project/index.html",
                "guide/existing-project/index.html",
                "guide/project-map/index.html",
                "guide/roadmap/index.html",
                "guide/generate-campaigns/index.html",
                "guide/queue-and-select/index.html",
                "guide/execute/index.html",
                "guide/complete-and-review/index.html",
                "help/index.html",
                "help/ideas/index.html",
                "help/planning/index.html",
                "help/roadmaps/index.html",
                "help/campaigns/index.html",
                "help/execution/index.html",
                "help/work-level-customization/index.html",
                "help/review/index.html",
                "help/recovery/index.html",
                "help/commands/index.html",
                "help/maintenance/index.html",
                "ref/index.html",
            )
            for relative in expected:
                self.assertTrue((public / relative).is_file(), relative)
            self.assertGreaterEqual(len(commands), 35)
            reference = (public / "ref" / "index.html").read_text(encoding="utf-8")
            for anchor in ("planning", "campaigns", "maintenance"):
                self.assertIn(f'id="{anchor}"', reference)
            for command in commands:
                self.assertIn(command.syntax.replace("<", "&lt;").replace(">", "&gt;"), reference)

    def test_guide_exposes_complete_copy_ready_workflow(self) -> None:
        prompts = (
            "ts: version",
            "ts: discuss <project idea>",
            "ts: map the active workstreams",
            "ts: fulltsupgrade",
            "ts: onboard this existing project",
            "ts: build focus areas",
            "ts: review work state",
            "ts: reconcile campaigns",
            "ts: develop roadmap",
            "ts: propose roadmap",
            "ts: approve roadmap <token>",
            "ts: derive campaigns for milestone M1",
            "ts: approve campaign plan <token>",
            "ts: add <campaign outcome>",
            "ts: overview",
            "ts: status",
            "ts: next",
            "ts:work1 <goal>",
            "ts:work2 <goal>",
            "ts:work3 <scope>",
            "ts:work4 <scope>",
            "ts:work5 <scope>",
            "ts:check focused",
            "ts: review the current campaign against its completion gate and complete it if verified",
            "ts: roadmap status",
            "ts: review roadmap",
        )
        with tempfile.TemporaryDirectory() as temporary:
            public, _ = SITE_BUILDER.build(Path(temporary) / "bundle")
            guide = "\n".join(
                path.read_text(encoding="utf-8")
                for path in sorted((public / "guide").rglob("index.html"))
            )
            visible = html.unescape(re.sub(r"<[^>]+>", "", guide))
            for prompt in prompts:
                self.assertIn(prompt, visible)
            self.assertIn("creates no campaigns", visible.lower())
            self.assertIn("previews a campaign manifest", visible.lower())
            self.assertIn("bounded-work shortcut", visible.lower())

    def test_copy_controls_are_accessible_and_copy_only_visible_code(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            public, commands = SITE_BUILDER.build(Path(temporary) / "bundle")
            pages = [path for path in (public / "guide").rglob("index.html") if path.parent != public / "guide"]
            pages.append(public / "ref" / "index.html")
            for path in pages:
                content = path.read_text(encoding="utf-8")
                blocks = re.findall(r'<div class="copy-block"><code>(.*?)</code><button class="copy-command" type="button" aria-label="([^"]+)">([^<]+)</button></div>', content)
                self.assertTrue(blocks, path)
                for visible, label, button_text in blocks:
                    self.assertTrue(html.unescape(visible).strip())
                    self.assertIn("Copy", label)
                    self.assertTrue(button_text.startswith("Copy"))
            script = (public / "assets" / "site.js").read_text(encoding="utf-8")
            self.assertIn("code.textContent.trim()", script)
            self.assertIn("clipboard.writeText(value)", script)
            self.assertIn('role="status" aria-live="polite"', (public / "ref" / "index.html").read_text(encoding="utf-8"))
            reference = (public / "ref" / "index.html").read_text(encoding="utf-8")
            self.assertIn('<table class="command-table">', reference)
            self.assertNotIn('class="ref-card"', reference)
            self.assertEqual(reference.count('<button class="copy-command"'), len(commands) * 2)
            for level in range(1, 6):
                command_anchor = SITE_BUILDER.command_id(f"ts:work{level} <goal>" if level < 3 else f"ts:work{level} [scope]")
                row = reference.split(f'id="{command_anchor}"', 1)[1].split("</tr>", 1)[0]
                self.assertIn('href="/help/work-level-customization/"', row)

    def test_work_level_customization_help_is_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            public, _ = SITE_BUILDER.build(Path(temporary) / "bundle")
            page = (public / "help" / "work-level-customization" / "index.html").read_text(encoding="utf-8")
            for detail in (
                "work/tool-shed.yaml",
                "schema_version: 1",
                "work_model: split",
                "before:",
                "after:",
                "run_default: false",
                "tool_shed/scripts/work_level_config.py",
                "scripts/work_level_config.py",
                "Lower-level envelopes do not repeat",
                "preserve its bytes",
            ):
                self.assertIn(detail, page)

    def test_compact_layout_removes_large_card_minimums(self) -> None:
        css = (ROOT / "site" / "assets" / "site.css").read_text(encoding="utf-8")
        self.assertNotIn("min-height: 13rem", css)
        self.assertNotIn(".ref-card", css)
        self.assertIn(".table-scroll", css)
        self.assertIn(".guide-layout", css)
        self.assertIn(".command-table thead th:first-child", css)
        self.assertIn("text-align: left", css)

    def test_asset_urls_are_content_versioned_for_returning_browsers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            public, _ = SITE_BUILDER.build(Path(temporary) / "bundle")
            page = (public / "ref" / "index.html").read_text(encoding="utf-8")
            revision = SITE_BUILDER.asset_revision()
            self.assertIn(f'/assets/site.css?v={revision}', page)
            self.assertIn(f'/assets/site.js?v={revision}', page)

    def test_overview_preserves_core_process_and_partnership_messages(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            public, _ = SITE_BUILDER.build(Path(temporary) / "bundle")
            overview = (public / "index.html").read_text(encoding="utf-8")
            self.assertIn("Roadmaps provide direction. Campaigns provide execution.", overview)
            self.assertIn("Reality is allowed to change the roadmap.", overview)
            self.assertIn("You steer. AI works the process.", overview)

    def test_deployment_bundle_is_a_dedicated_nginx_service(self) -> None:
        compose = (ROOT / "site" / "deploy" / "docker-compose.yml").read_text(encoding="utf-8")
        nginx = (ROOT / "site" / "deploy" / "nginx.conf").read_text(encoding="utf-8")
        self.assertIn("container_name: ts-rookaro-com", compose)
        self.assertIn('"8087:80"', compose)
        self.assertIn("nginx:alpine", compose)
        self.assertIn("healthcheck:", compose)
        self.assertIn("try_files $uri $uri/ =404", nginx)


if __name__ == "__main__":
    unittest.main()
