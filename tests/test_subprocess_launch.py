from __future__ import annotations

import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import subprocess_launch  # noqa: E402


class SubprocessLaunchTests(unittest.TestCase):
    def test_windows_background_run_receives_create_no_window(self) -> None:
        with mock.patch.object(
            subprocess_launch.platform, "system", return_value="Windows"
        ), mock.patch.object(subprocess_launch.subprocess, "run") as run:
            with subprocess_launch.windowless_subprocesses():
                subprocess_launch.run(["git", "status"], check=False)
        self.assertEqual(
            run.call_args.kwargs["creationflags"],
            subprocess_launch.CREATE_NO_WINDOW,
        )

    def test_non_windows_background_run_omits_windows_flags(self) -> None:
        with mock.patch.object(
            subprocess_launch.platform, "system", return_value="Linux"
        ), mock.patch.object(subprocess_launch.subprocess, "run") as run:
            with subprocess_launch.windowless_subprocesses():
                subprocess_launch.run(["git", "status"], check=False)
        self.assertNotIn("creationflags", run.call_args.kwargs)

    def test_windows_interactive_run_retains_visible_default(self) -> None:
        with mock.patch.object(
            subprocess_launch.platform, "system", return_value="Windows"
        ), mock.patch.object(subprocess_launch.subprocess, "run") as run:
            subprocess_launch.run(["git", "status"], check=False)
        self.assertNotIn("creationflags", run.call_args.kwargs)

    def test_windows_dashboard_qualification_covers_real_acceptance_signals(self) -> None:
        script = ROOT / "scripts/qualify_windows_dashboard.ps1"
        content = script.read_text(encoding="utf-8")
        for expected in (
            "SetWinEventHook",
            "Win32_ProcessStartTrace",
            "$scriptsPath = $PSScriptRoot",
            "for _ in range(10)",
            "LastTaskResult",
            "pending_events",
            "persistent_worker_processes_started",
            "visible_console_windows",
        ):
            self.assertIn(expected, content)

        shell = shutil.which("pwsh") or shutil.which("powershell")
        if shell is None:
            return
        quoted_script = str(script).replace("'", "''")
        parsed = subprocess.run(
            [
                shell,
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                f"$path='{quoted_script}'; $errors=$null; "
                "[System.Management.Automation.Language.Parser]::ParseFile("
                "$path, [ref]$null, [ref]$errors) > $null; "
                "if ($errors.Count) { $errors | Out-String | Write-Error; exit 1 }",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(parsed.returncode, 0, parsed.stderr)


if __name__ == "__main__":
    unittest.main()
