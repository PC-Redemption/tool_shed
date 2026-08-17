from __future__ import annotations

import importlib.util
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
                "help/index.html",
                "help/ideas/index.html",
                "help/planning/index.html",
                "help/roadmaps/index.html",
                "help/campaigns/index.html",
                "help/execution/index.html",
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
