"""Regression contract for `ts: next --app-server` route guidance."""

from pathlib import Path
import unittest


ROUTE_REFERENCE = (
    Path(__file__).resolve().parents[1]
    / "skills/tool-shed/references/campaign-routes.md"
)
ROOT = Path(__file__).resolve().parents[1]


class NextAppServerForwardingContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.route = ROUTE_REFERENCE.read_text(encoding="utf-8")
        cls.flat_route = " ".join(cls.route.split())

    def test_next_is_forwarding_not_a_qualified_role(self):
        self.assertIn("`ts: next --app-server`", self.route)
        self.assertIn("ordinary `next` selection unchanged", self.route)
        self.assertIn("not an App Server role", self.route)
        self.assertIn("reuses ordinary `next` selection unchanged", self.flat_route)

    def test_eligible_camp_forwards_to_existing_terra_medium_path(self):
        self.assertIn(
            "app_server_dispatch.py --workspace . next --json", self.route
        )
        self.assertIn("existing bounded `camp-run` path", self.route)
        self.assertIn("`gpt-5.6-terra` with `medium` reasoning", self.route)
        self.assertIn("Do not create a `next` role selector, a second CAMP runner", self.route)

    def test_dispatcher_forbids_nested_codex_wrapper(self):
        self.assertIn("Do not launch `codex exec`", self.route)
        self.assertIn("zero model tokens", self.route)
        self.assertIn("shell-free deterministic verification argv arrays", self.route)

    def test_non_camp_and_failed_selection_remain_safe(self):
        self.assertIn("without starting CAMP execution", self.flat_route)
        self.assertIn("Discussion remains GUI-native", self.route)
        self.assertIn("fails closed", self.route)
        self.assertIn("explicit App Server remains fail-closed", self.route)
        self.assertIn("This forwarding never changes the repository default", self.flat_route)
        self.assertIn("or enables API fallback", self.route)

    def test_installer_and_user_docs_publish_the_same_forwarding_contract(self):
        paths = (
            ROOT / "README.md",
            ROOT / "docs/commands.md",
            ROOT / "docs/operator-guide.md",
            ROOT / "docs/codex-app-server-execution.md",
            ROOT / "docs/codex-app-server-maintainer-note.md",
            ROOT / "scripts/install_into_workspace.py",
        )
        for path in paths:
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text(encoding="utf-8")
                self.assertIn("ts: next --app-server", text)
        installer = paths[-1].read_text(encoding="utf-8")
        self.assertIn("normal `next` navigation", installer)
        self.assertIn("Do not make `next` a role", installer)
        self.assertIn("bounded Terra/medium `camp-run` path", installer)
        self.assertIn("protected user-local preference", installer)
        self.assertIn("add API fallback", installer)


if __name__ == "__main__":
    unittest.main()
