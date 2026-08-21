"""Bounded, reusable discovery of the local Codex CLI.

This module deliberately discovers executables only from an explicit override,
the operating-system PATH lookup, and a small allowlist of platform locations.
It does not install Codex, change PATH, or treat discovery as qualification.
"""

from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping


class CodexSource(str, Enum):
    EXPLICIT_OVERRIDE = "explicit_override"
    PATH = "path"
    TRUSTED_LOCATION = "trusted_location"
    VSCODE_EXTENSION = "openai_vscode_extension"


class CodexReadiness(str, Enum):
    NOT_FOUND = "not_found"
    INVALID_EXECUTABLE = "invalid_executable"
    APP_SERVER_UNAVAILABLE = "app_server_unavailable"
    AVAILABLE_UNQUALIFIED = "available_unqualified"
    AVAILABLE_QUALIFIED = "available_qualified"


@dataclass(frozen=True)
class CodexCliResolution:
    """The result of local Codex discovery, validation, and readiness probing."""

    source: CodexSource | None
    executable: Path | None
    version: str | None
    readiness: CodexReadiness
    error: str | None = None
    diagnostics: tuple[str, ...] = field(default_factory=tuple)

    @property
    def found(self) -> bool:
        return self.executable is not None

    @property
    def app_server_available(self) -> bool:
        return self.readiness in {
            CodexReadiness.AVAILABLE_UNQUALIFIED,
            CodexReadiness.AVAILABLE_QUALIFIED,
        }

    @property
    def qualified(self) -> bool:
        return self.readiness is CodexReadiness.AVAILABLE_QUALIFIED

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.value if self.source else None,
            "executable": str(self.executable) if self.executable else None,
            "version": self.version,
            "readiness": self.readiness.value,
            "error": self.error,
            "diagnostics": list(self.diagnostics),
        }


CommandRunner = Callable[[list[str]], Any]
PathLookup = Callable[[str], str | None]
PathTest = Callable[[Path], bool]
Globber = Callable[[str], Iterable[str]]
Qualifier = Callable[[str], bool]


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, timeout=5, check=False)


def _command_result(result: Any) -> tuple[int, str, str]:
    """Accept CompletedProcess-like objects and small test doubles."""

    if isinstance(result, tuple):
        code, stdout, stderr = result
        return int(code), str(stdout or ""), str(stderr or "")
    return (
        int(getattr(result, "returncode")),
        str(getattr(result, "stdout", "") or ""),
        str(getattr(result, "stderr", "") or ""),
    )


def _version_from(output: str) -> str | None:
    match = re.search(r"\b(\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)\b", output)
    return match.group(1) if match else None


def _extension_version(path: Path) -> tuple[int, ...]:
    """Return a comparable package version from ``openai.chatgpt-<version>``."""

    extension = next((part for part in path.parts if part.lower().startswith("openai.chatgpt-")), "")
    match = re.search(r"openai\.chatgpt-([0-9][0-9A-Za-z.+-]*)$", extension, re.I)
    if not match:
        return ()
    return tuple(int(piece) for piece in re.findall(r"\d+", match.group(1)))


class CodexCliResolver:
    """Resolve Codex through only explicitly trusted, deterministic locations."""

    def __init__(
        self,
        *,
        platform: str | None = None,
        environment: Mapping[str, str] | None = None,
        home: Path | None = None,
        path_lookup: PathLookup | None = None,
        is_file: PathTest | None = None,
        globber: Globber | None = None,
        runner: CommandRunner | None = None,
        trusted_locations: Iterable[Path] | None = None,
    ) -> None:
        self.platform = (platform or sys.platform).lower()
        self.environment = dict(os.environ if environment is None else environment)
        self.home = Path(home) if home is not None else Path.home()
        self.path_lookup = path_lookup or shutil.which
        self.is_file = is_file or Path.is_file
        self.globber = globber or glob.glob
        self.runner = runner or _run
        self._trusted_locations = (
            tuple(Path(path) for path in trusted_locations)
            if trusted_locations is not None
            else None
        )

    def resolve(
        self,
        *,
        executable_override: str | Path | None = None,
        qualified_versions: Iterable[str] = (),
        is_qualified: Qualifier | None = None,
    ) -> CodexCliResolution:
        """Discover one usable CLI without changing system or user configuration.

        An explicit override is authoritative: a broken override is reported as
        invalid instead of silently selecting another executable. Other invalid
        candidates are retained as diagnostics while later trusted sources are
        considered, so a broken PATH entry does not hide a valid bundled CLI.
        """

        qualifier = is_qualified or set(qualified_versions).__contains__
        diagnostics: list[str] = []
        if executable_override is not None:
            return self._validate(
                CodexSource.EXPLICIT_OVERRIDE, Path(executable_override), qualifier, diagnostics
            )

        path_candidate = self.path_lookup("codex")
        if path_candidate:
            result = self._validate(CodexSource.PATH, Path(path_candidate), qualifier, diagnostics)
            if result.readiness is not CodexReadiness.INVALID_EXECUTABLE:
                return result
            diagnostics.extend(result.diagnostics)

        for candidate in self._trusted_candidates():
            result = self._validate(candidate[0], candidate[1], qualifier, diagnostics)
            if result.readiness is not CodexReadiness.INVALID_EXECUTABLE:
                return result
            diagnostics.extend(result.diagnostics)

        if diagnostics:
            return CodexCliResolution(
                None, None, None, CodexReadiness.INVALID_EXECUTABLE,
                "No discovered Codex candidate passed --version validation.", tuple(diagnostics),
            )
        return CodexCliResolution(
            None, None, None, CodexReadiness.NOT_FOUND,
            "Codex CLI was not found in the supported locations.", (),
        )

    def _trusted_candidates(self) -> Iterable[tuple[CodexSource, Path]]:
        locations = self._trusted_locations if self._trusted_locations is not None else self._default_locations()
        for location in locations:
            if self.is_file(location):
                yield CodexSource.TRUSTED_LOCATION, location
        discovered: dict[str, Path] = {}
        for pattern in self._vscode_extension_patterns():
            for value in self.globber(pattern):
                path = Path(value)
                discovered.setdefault(str(path).lower(), path)
        # Stable path ordering breaks equal-version ties; the second stable
        # sort selects descending numeric versions without mixing integer and
        # string tuple members when version segment counts differ.
        paths = sorted(discovered.values(), key=lambda item: str(item).lower())
        paths.sort(key=_extension_version, reverse=True)
        for path in paths:
            if self.is_file(path):
                yield CodexSource.VSCODE_EXTENSION, path

    def _vscode_extension_patterns(self) -> tuple[str, ...]:
        if self.platform.startswith("win"):
            roots = (self.home / ".vscode" / "extensions",)
            bundles = (("windows-x86_64", "codex.exe"),)
        elif self.platform.startswith("linux"):
            roots = (
                self.home / ".vscode" / "extensions",
                self.home / ".vscode-insiders" / "extensions",
                self.home / ".vscode-server" / "extensions",
                self.home / ".vscode-server-insiders" / "extensions",
            )
            bundles = (
                ("linux-x86_64", "codex"),
                ("linux-aarch64", "codex"),
                ("linux-arm64", "codex"),
            )
        else:
            return ()
        return tuple(
            str(root / "openai.chatgpt-*" / "bin" / architecture / executable)
            for root in roots
            for architecture, executable in bundles
        )

    def _default_locations(self) -> tuple[Path, ...]:
        if self.platform.startswith("win"):
            local = self.environment.get("LOCALAPPDATA")
            program_files = self.environment.get("PROGRAMFILES")
            values = [
                Path(local) / "Programs" / "Codex" / "codex.exe" if local else None,
                Path(program_files) / "OpenAI" / "Codex" / "codex.exe" if program_files else None,
            ]
        elif self.platform == "darwin":
            values = [
                self.home / ".local" / "bin" / "codex",
                Path("/Applications/Codex.app/Contents/MacOS/codex"),
                Path("/usr/local/bin/codex"),
            ]
        else:
            values = [self.home / ".local" / "bin" / "codex", Path("/usr/local/bin/codex"), Path("/usr/bin/codex")]
        return tuple(item for item in values if item is not None)

    def _validate(
        self,
        source: CodexSource,
        executable: Path,
        qualifier: Qualifier,
        prior_diagnostics: list[str],
    ) -> CodexCliResolution:
        executable = Path(executable)
        if not self.is_file(executable):
            return CodexCliResolution(
                source, executable, None, CodexReadiness.INVALID_EXECUTABLE,
                "Candidate is not an executable file.", tuple(prior_diagnostics + [f"{executable}: not a file"]),
            )
        try:
            code, stdout, stderr = _command_result(self.runner([str(executable), "--version"]))
        except (OSError, subprocess.TimeoutExpired, ValueError) as error:
            return CodexCliResolution(
                source, executable, None, CodexReadiness.INVALID_EXECUTABLE,
                f"Codex --version could not run: {error}", tuple(prior_diagnostics + [f"{executable}: --version failed"]),
            )
        version = _version_from(stdout + stderr)
        if code != 0 or version is None:
            return CodexCliResolution(
                source, executable, None, CodexReadiness.INVALID_EXECUTABLE,
                "Candidate did not return a recognizable Codex version.",
                tuple(prior_diagnostics + [f"{executable}: invalid --version response"]),
            )
        try:
            app_server_code, _, app_server_error = _command_result(
                self.runner([str(executable), "app-server", "--help"])
            )
        except (OSError, subprocess.TimeoutExpired, ValueError) as error:
            return CodexCliResolution(
                source, executable, version, CodexReadiness.APP_SERVER_UNAVAILABLE,
                f"Codex App Server probe failed: {error}", tuple(prior_diagnostics),
            )
        if app_server_code != 0:
            message = app_server_error.strip() or "Codex App Server command is unavailable."
            return CodexCliResolution(
                source, executable, version, CodexReadiness.APP_SERVER_UNAVAILABLE,
                message, tuple(prior_diagnostics),
            )
        readiness = CodexReadiness.AVAILABLE_QUALIFIED if qualifier(version) else CodexReadiness.AVAILABLE_UNQUALIFIED
        return CodexCliResolution(source, executable, version, readiness, None, tuple(prior_diagnostics))
