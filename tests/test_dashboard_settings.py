from __future__ import annotations

import os
import runpy
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "dashboard" / "config" / "settings.py"


class DashboardSettingsTests(unittest.TestCase):
    def load(self, **environment: str) -> dict[str, object]:
        with patch.dict(os.environ, environment, clear=True):
            return runpy.run_path(str(SETTINGS))

    def test_production_defaults_keep_https_security_enabled(self) -> None:
        settings = self.load()
        self.assertEqual(settings["DASHBOARD_ENVIRONMENT"], "production")
        self.assertFalse(settings["DASHBOARD_ALLOW_INSECURE_HTTP"])
        self.assertTrue(settings["SECURE_SSL_REDIRECT"])
        self.assertTrue(settings["SESSION_COOKIE_SECURE"])
        self.assertEqual(settings["SECURE_HSTS_SECONDS"], 31_536_000)

    def test_development_http_requires_both_environment_and_explicit_switch(self) -> None:
        settings = self.load(
            TOOL_SHED_DASHBOARD_ENVIRONMENT="development",
            TOOL_SHED_DASHBOARD_ALLOW_INSECURE_HTTP="1",
        )
        self.assertTrue(settings["DASHBOARD_ALLOW_INSECURE_HTTP"])
        self.assertFalse(settings["SECURE_SSL_REDIRECT"])
        self.assertFalse(settings["SESSION_COOKIE_SECURE"])
        self.assertEqual(settings["SECURE_HSTS_SECONDS"], 0)

        production = self.load(
            TOOL_SHED_DASHBOARD_ENVIRONMENT="production",
            TOOL_SHED_DASHBOARD_ALLOW_INSECURE_HTTP="1",
        )
        self.assertFalse(production["DASHBOARD_ALLOW_INSECURE_HTTP"])
        self.assertTrue(production["SECURE_SSL_REDIRECT"])

    def test_unknown_environment_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be production or development"):
            self.load(TOOL_SHED_DASHBOARD_ENVIRONMENT="staging")


if __name__ == "__main__":
    unittest.main()
