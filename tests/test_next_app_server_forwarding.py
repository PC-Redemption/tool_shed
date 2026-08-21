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

    def test_next_is_forwarding_not_a_qualified_role(self):
        self.assertIn("`ts: next --app-server`", self.route)
        self.assertIn("ordinary `next` selection unchanged", self.route)
        self.assertIn("not an App Server role", self.route)
        self.assertIn("same\naction and CAMP as unflagged `ts: next`", self.route)

    def test_eligible_camp_forwards_to_existing_terra_medium_path(self):
        self.assertIn(
            "`app_server_control.py select camp-run --app-server --json`", self.route
        )
        self.assertIn("existing bounded `camp-run` path", self.route)
        self.assertIn("`gpt-5.6-terra` with `medium` reasoning", self.route)
        self.assertIn("Do not create a `next` selector, a second CAMP\nrunner", self.route)

    def test_non_camp_and_failed_selection_remain_safe(self):
        self.assertIn("without starting CAMP execution", self.route)
        self.assertIn("Discussion remains GUI-native.", self.route)
        self.assertIn("fails closed", self.route)
        self.assertIn("do not silently switch backends", self.route)
        self.assertIn("never\npersists state, changes the global default from off", self.route)
        self.assertIn("or enables API\nfallback", self.route)

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
        self.assertIn("bounded Terra/medium path", installer)
        self.assertIn("persist the preference", installer)
        self.assertIn("add API fallback", installer)


if __name__ == "__main__":
    unittest.main()
