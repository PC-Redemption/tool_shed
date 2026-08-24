from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.codex_cli_resolver import (
    CodexCliResolution,
    CodexQualificationState,
    CodexReadiness,
    CodexSource,
)
from scripts.codex_app_server_compatibility import format_status, status_report


class CodexCliReportingTests(unittest.TestCase):
    def report(self, resolution: CodexCliResolution, records=()):
        with patch("scripts.codex_app_server_compatibility.CodexCliResolver") as resolver:
            resolver.return_value.resolve.return_value = resolution
            with patch("scripts.codex_app_server_compatibility.load_qualifications", return_value=list(records)):
                return status_report()

    def test_windows_bundle_is_available_and_unqualified(self):
        executable = Path("C:/Users/me/.vscode/extensions/openai.chatgpt-1.2.0/bin/windows-x86_64/codex.exe")
        report = self.report(CodexCliResolution(
            CodexSource.VSCODE_EXTENSION,
            executable,
            "0.144.6",
            CodexReadiness.AVAILABLE_UNQUALIFIED,
            qualification_state=CodexQualificationState.BELOW_MINIMUM,
        ))
        self.assertEqual("AVAILABLE", report["codex_cli"])
        self.assertEqual("OpenAI VS Code extension", report["codex_discovery"])
        self.assertEqual(str(executable), report["codex_executable"])
        self.assertEqual("unqualified_version", report["compatibility"])
        self.assertEqual("below-minimum", report["qualification_state"])
        self.assertEqual({}, report["enabled_roles"])
        self.assertIn("Compatibility: unqualified version", format_status(report))

    def test_missing_and_invalid_are_distinct(self):
        missing = self.report(CodexCliResolution(None, None, None, CodexReadiness.NOT_FOUND, "not found"))
        invalid = self.report(CodexCliResolution(CodexSource.PATH, Path("/bad/codex"), None, CodexReadiness.INVALID_EXECUTABLE, "bad version"))
        self.assertEqual("not_installed_or_not_found", missing["compatibility"])
        self.assertEqual("invalid_executable", invalid["compatibility"])

    def test_app_server_unavailable_preserves_detected_version(self):
        report = self.report(CodexCliResolution(
            CodexSource.PATH, Path("/bin/codex"), "0.144.6", CodexReadiness.APP_SERVER_UNAVAILABLE, "unknown command"
        ))
        self.assertEqual("0.144.6", report["installed_codex"])
        self.assertFalse(report["app_server_available"])
        self.assertEqual("app_server_unavailable", report["compatibility"])

    def test_qualified_version_is_reported(self):
        report = self.report(
            CodexCliResolution(CodexSource.PATH, Path("/bin/codex"), "0.144.6", CodexReadiness.AVAILABLE_QUALIFIED),
            [{"codex_version": "0.144.6", "status": "qualified", "routing": {}, "workspace_writing": False}],
        )
        self.assertEqual("qualified", report["compatibility"])
        self.assertEqual("exact-qualified", report["qualification_state"])
        self.assertEqual("write-not-qualified", report["write_qualification_state"])

    def test_unseen_eligible_version_reports_dirty_qualifying_without_enabled_roles(self):
        report = self.report(
            CodexCliResolution(
                CodexSource.VSCODE_EXTENSION,
                Path("/opt/codex-new"),
                "0.200.0-alpha.7",
                CodexReadiness.AVAILABLE_UNQUALIFIED,
                qualification_state=CodexQualificationState.DIRTY_QUALIFYING,
            )
        )
        self.assertEqual("dirty-qualifying", report["qualification_state"])
        self.assertEqual(["planning", "verification"], report["dirty_qualifying_roles"])
        self.assertEqual({}, report["enabled_roles"])
        self.assertEqual("write-not-qualified", report["write_qualification_state"])

    def test_app_server_probe_failure_reports_transient_fallback(self):
        report = self.report(
            CodexCliResolution(
                CodexSource.PATH,
                Path("/opt/codex"),
                "0.200.0",
                CodexReadiness.APP_SERVER_UNAVAILABLE,
                "probe timed out",
                qualification_state=CodexQualificationState.APP_SERVER_UNAVAILABLE,
            )
        )
        self.assertEqual("transient-fallback", report["qualification_state"])
        self.assertEqual({}, report["enabled_roles"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
