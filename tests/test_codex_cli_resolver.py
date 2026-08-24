from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

from scripts.codex_cli_resolver import (
    CodexCliResolver,
    CodexQualificationState,
    CodexReadiness,
    CodexSource,
    semantic_version_key,
)


class CodexCliResolverTests(unittest.TestCase):
    def resolver(self, *, files=(), responses=None, **kwargs):
        responses = responses or {}

        def runner(command):
            result = responses.get(tuple(command))
            if isinstance(result, Exception):
                raise result
            return result or subprocess.CompletedProcess(command, 1, "", "unknown command")

        return CodexCliResolver(
            is_file=lambda path: Path(path) in {Path(item) for item in files},
            runner=runner,
            **kwargs,
        )

    @staticmethod
    def supported(path: Path, version="0.144.6"):
        return {
            (str(path), "--version"): (0, f"codex {version}\n", ""),
            (str(path), "app-server", "--help"): (0, "help", ""),
        }

    def test_explicit_override_precedes_path_and_can_be_qualified(self):
        explicit, on_path = Path("/opt/codex"), Path("/bin/codex")
        responses = self.supported(explicit)
        responses.update(self.supported(on_path, "0.1.0"))
        result = self.resolver(files=(explicit, on_path), responses=responses, path_lookup=lambda _: str(on_path)).resolve(
            executable_override=explicit, qualified_versions=("0.144.6",)
        )
        self.assertEqual(CodexSource.EXPLICIT_OVERRIDE, result.source)
        self.assertEqual(CodexReadiness.AVAILABLE_QUALIFIED, result.readiness)

    def test_path_is_used_before_linux_trusted_location(self):
        on_path, local = Path("/bin/codex"), Path("/home/me/.local/bin/codex")
        responses = self.supported(on_path)
        responses.update(self.supported(local, "0.2.0"))
        result = self.resolver(files=(on_path, local), responses=responses, platform="linux", home=Path("/home/me"), path_lookup=lambda _: str(on_path)).resolve()
        self.assertEqual(CodexSource.PATH, result.source)
        self.assertEqual("0.144.6", result.version)

    def test_newest_valid_windows_extension_is_selected(self):
        old = Path("C:/Users/me/.vscode/extensions/openai.chatgpt-0.9.0/bin/windows-x86_64/codex.exe")
        broken = Path("C:/Users/me/.vscode/extensions/openai.chatgpt-1.2.0/bin/windows-x86_64/codex.exe")
        newest = Path("C:/Users/me/.vscode/extensions/openai.chatgpt-1.1.0/bin/windows-x86_64/codex.exe")
        responses = self.supported(old, "0.100.0")
        responses.update(self.supported(newest, "0.144.6"))
        result = self.resolver(
            files=(old, broken, newest), responses=responses, platform="win32", home=Path("C:/Users/me"),
            path_lookup=lambda _: None, globber=lambda _: [str(old), str(broken), str(newest)],
        ).resolve()
        self.assertEqual(CodexSource.VSCODE_EXTENSION, result.source)
        self.assertEqual(newest, result.executable)
        self.assertEqual(CodexReadiness.AVAILABLE_UNQUALIFIED, result.readiness)

    def test_windows_extension_versions_with_different_segment_counts_sort_safely(self):
        shorter = Path("C:/Users/me/.vscode/extensions/openai.chatgpt-2.1/bin/windows-x86_64/codex.exe")
        longer = Path("C:/Users/me/.vscode/extensions/openai.chatgpt-2.1.1/bin/windows-x86_64/codex.exe")
        responses = self.supported(shorter, "0.140.0")
        responses.update(self.supported(longer, "0.144.6"))
        result = self.resolver(
            files=(shorter, longer), responses=responses, platform="win32", home=Path("C:/Users/me"),
            path_lookup=lambda _: None, globber=lambda _: [str(shorter), str(longer)],
        ).resolve()
        self.assertEqual(longer, result.executable)

    def test_linux_gui_finds_cli_bundled_in_openai_vscode_extension_without_path(self):
        bundled = Path(
            "/home/me/.vscode/extensions/openai.chatgpt-2.4.0/"
            "bin/linux-x86_64/codex"
        )
        result = self.resolver(
            files=(bundled,),
            responses=self.supported(bundled),
            platform="linux",
            home=Path("/home/me"),
            path_lookup=lambda _: None,
            globber=lambda pattern: [str(bundled)] if "linux-x86_64" in pattern else [],
        ).resolve(qualified_versions=("0.144.6",))
        self.assertEqual(CodexSource.VSCODE_EXTENSION, result.source)
        self.assertEqual(bundled, result.executable)
        self.assertEqual(CodexReadiness.AVAILABLE_QUALIFIED, result.readiness)

    def test_linux_remote_extension_roots_and_arm64_bundle_are_bounded(self):
        bundled = Path(
            "/home/me/.vscode-server/extensions/openai.chatgpt-3.0.0/"
            "bin/linux-aarch64/codex"
        )
        patterns = []

        def globber(pattern):
            patterns.append(pattern)
            normalized = pattern.replace("\\", "/")
            return [str(bundled)] if ".vscode-server/" in normalized and "linux-aarch64" in normalized else []

        result = self.resolver(
            files=(bundled,), responses=self.supported(bundled), platform="linux",
            home=Path("/home/me"), path_lookup=lambda _: None, globber=globber,
        ).resolve()
        self.assertEqual(bundled, result.executable)
        normalized_patterns = [item.replace("\\", "/") for item in patterns]
        self.assertTrue(any(".vscode/extensions/openai.chatgpt-*" in item for item in normalized_patterns))
        self.assertTrue(any(".vscode-server/extensions/openai.chatgpt-*" in item for item in normalized_patterns))
        self.assertTrue(all("openai.chatgpt-*" in item for item in normalized_patterns))

    def test_newer_linux_extension_precedes_older_standard_location(self):
        local = Path("/home/me/.local/bin/codex")
        bundled = Path(
            "/home/me/.vscode/extensions/openai.chatgpt-2.4.0/"
            "bin/linux-x86_64/codex"
        )
        responses = self.supported(local)
        responses.update(self.supported(bundled, "0.200.0"))
        result = self.resolver(
            files=(local, bundled), responses=responses, platform="linux",
            home=Path("/home/me"), path_lookup=lambda _: None,
            globber=lambda _: [str(bundled)],
        ).resolve()
        self.assertEqual(CodexSource.VSCODE_EXTENSION, result.source)
        self.assertEqual(bundled, result.executable)
        self.assertEqual([local, bundled], [item.executable for item in result.inventory])

    def test_older_path_does_not_hide_newer_eligible_windows_extension(self):
        on_path = Path("C:/Tools/codex.exe")
        bundled = Path(
            "C:/Users/me/.vscode/extensions/openai.chatgpt-4.0.0/"
            "bin/windows-x86_64/codex.exe"
        )
        responses = self.supported(on_path, "0.149.0")
        responses.update(self.supported(bundled, "0.200.0-alpha.7"))
        result = self.resolver(
            files=(on_path, bundled),
            responses=responses,
            platform="win32",
            home=Path("C:/Users/me"),
            path_lookup=lambda _: str(on_path),
            globber=lambda _: [str(bundled)],
        ).resolve(minimum_version="0.146.0", qualified_versions=("0.149.0",))
        self.assertEqual(bundled, result.executable)
        self.assertEqual(
            CodexQualificationState.DIRTY_QUALIFYING,
            result.qualification_state,
        )
        self.assertEqual(
            ["exact_qualified", "dirty_qualifying"],
            [item.qualification_state.value for item in result.inventory],
        )

    def test_equal_version_uses_source_priority_only_as_tie_breaker(self):
        on_path = Path("/opt/bin/codex")
        bundled = Path(
            "/home/me/.vscode/extensions/openai.chatgpt-4.0.0/"
            "bin/linux-x86_64/codex"
        )
        responses = self.supported(on_path, "0.200.0")
        responses.update(self.supported(bundled, "0.200.0"))
        result = self.resolver(
            files=(on_path, bundled),
            responses=responses,
            platform="linux",
            home=Path("/home/me"),
            path_lookup=lambda _: str(on_path),
            globber=lambda pattern: [str(bundled)] if "linux-x86_64" in pattern else [],
        ).resolve(minimum_version="0.146.0")
        self.assertEqual(CodexSource.PATH, result.source)
        self.assertEqual(on_path, result.executable)

    def test_highest_selection_skips_newer_candidate_without_app_server(self):
        on_path = Path("/opt/bin/codex")
        local = Path("/home/me/.local/bin/codex")
        bundled = Path(
            "/home/me/.vscode/extensions/openai.chatgpt-4.0.0/"
            "bin/linux-x86_64/codex"
        )
        responses = self.supported(on_path, "0.149.0")
        responses.update(self.supported(local, "0.300.0"))
        responses[(str(local), "app-server", "--help")] = (2, "", "unavailable")
        responses.update(self.supported(bundled, "0.200.0"))
        result = self.resolver(
            files=(on_path, local, bundled),
            responses=responses,
            platform="linux",
            home=Path("/home/me"),
            path_lookup=lambda _: str(on_path),
            globber=lambda pattern: [str(bundled)] if "linux-x86_64" in pattern else [],
        ).resolve(minimum_version="0.146.0")
        self.assertEqual(bundled, result.executable)
        by_path = {item.executable: item for item in result.inventory}
        self.assertEqual(
            CodexQualificationState.APP_SERVER_UNAVAILABLE,
            by_path[local].qualification_state,
        )

    def test_semantic_version_order_prefers_stable_and_newer_prereleases(self):
        versions = ["0.149.0-alpha.4.3", "0.149.0", "0.150.0-alpha.1"]
        self.assertEqual(
            ["0.149.0-alpha.4.3", "0.149.0", "0.150.0-alpha.1"],
            sorted(versions, key=semantic_version_key),
        )

    def test_explicit_override_is_authoritative_while_inventory_remains_complete(self):
        explicit = Path("/opt/old-codex")
        on_path = Path("/opt/new-codex")
        responses = self.supported(explicit, "0.145.9")
        responses.update(self.supported(on_path, "0.300.0"))
        result = self.resolver(
            files=(explicit, on_path),
            responses=responses,
            path_lookup=lambda _: str(on_path),
            trusted_locations=(),
        ).resolve(executable_override=explicit, minimum_version="0.146.0")
        self.assertEqual(explicit, result.executable)
        self.assertEqual(CodexSource.EXPLICIT_OVERRIDE, result.source)
        self.assertEqual(CodexQualificationState.BELOW_MINIMUM, result.qualification_state)
        self.assertEqual([explicit, on_path], [item.executable for item in result.inventory])

    def test_invalid_path_candidate_does_not_hide_valid_trusted_candidate(self):
        invalid, local = Path("/bin/codex"), Path("/home/me/.local/bin/codex")
        result = self.resolver(
            files=(invalid, local), responses=self.supported(local), platform="linux", home=Path("/home/me"), path_lookup=lambda _: str(invalid)
        ).resolve()
        self.assertEqual(local, result.executable)
        self.assertTrue(any("recognizable Codex version" in item for item in result.diagnostics))

    def test_missing_and_invalid_are_distinct(self):
        missing = self.resolver(platform="linux", home=Path("/empty"), path_lookup=lambda _: None).resolve()
        self.assertEqual(CodexReadiness.NOT_FOUND, missing.readiness)
        invalid = Path("/bin/codex")
        broken = self.resolver(files=(invalid,), platform="linux", home=Path("/empty"), path_lookup=lambda _: str(invalid)).resolve()
        self.assertEqual(CodexReadiness.INVALID_EXECUTABLE, broken.readiness)

    def test_app_server_is_probed_separately_from_version(self):
        executable = Path("/bin/codex")
        responses = {(str(executable), "--version"): (0, "codex 0.144.6", ""), (str(executable), "app-server", "--help"): (2, "", "unknown command")}
        result = self.resolver(files=(executable,), responses=responses, path_lookup=lambda _: str(executable)).resolve()
        self.assertEqual(CodexReadiness.APP_SERVER_UNAVAILABLE, result.readiness)
        self.assertEqual("0.144.6", result.version)

    def test_explicit_missing_override_is_invalid_and_is_not_replaced(self):
        on_path = Path("/bin/codex")
        result = self.resolver(files=(on_path,), responses=self.supported(on_path), path_lookup=lambda _: str(on_path)).resolve(
            executable_override=Path("/missing/codex")
        )
        self.assertEqual(CodexReadiness.INVALID_EXECUTABLE, result.readiness)
        self.assertEqual(CodexSource.EXPLICIT_OVERRIDE, result.source)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
