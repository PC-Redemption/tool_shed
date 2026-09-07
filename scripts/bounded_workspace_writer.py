#!/usr/bin/env python3
"""One-shot, digest-bound workspace writes for App Server CAMP execution."""

from __future__ import annotations

import sys as _runtime_sys

_runtime_sys.dont_write_bytecode = True

import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


class BoundedWorkspaceWriteError(ValueError):
    """Raised when a bounded writer cannot establish a safe initial boundary."""


class BoundedWorkspaceWriter:
    """Expose one exact-file replacement without granting model filesystem write access."""

    TOOL_NAME = "write_workspace_file"

    def __init__(
        self,
        workspace: Path,
        expected_paths: Iterable[Path],
        *,
        max_write_bytes: int = 65_536,
    ) -> None:
        if isinstance(max_write_bytes, bool) or not isinstance(max_write_bytes, int) or max_write_bytes <= 0:
            raise BoundedWorkspaceWriteError("max_write_bytes must be a positive integer")
        self.workspace = workspace.resolve()
        if not self.workspace.is_dir():
            raise BoundedWorkspaceWriteError("workspace must be an existing directory")
        self.max_write_bytes = max_write_bytes
        self._entries: dict[str, dict[str, Any]] = {}
        self.evidence: list[dict[str, Any]] = []
        self.mutation_count = 0
        for supplied in expected_paths:
            relative = self._normalize_path(supplied)
            label = relative.as_posix()
            if label in self._entries:
                continue
            candidate = self.workspace / relative
            if self._has_symlink_component(relative):
                raise BoundedWorkspaceWriteError(f"bounded write refuses symlinked path: {label}")
            if candidate.exists() and not candidate.is_file():
                raise BoundedWorkspaceWriteError(f"bounded write requires a file or absent path: {label}")
            if not candidate.parent.is_dir():
                raise BoundedWorkspaceWriteError(f"bounded write parent must already exist: {label}")
            raw = candidate.read_bytes() if candidate.exists() else None
            if raw is not None:
                if b"\0" in raw:
                    raise BoundedWorkspaceWriteError(f"bounded write requires UTF-8 text: {label}")
                try:
                    raw.decode("utf-8")
                except UnicodeDecodeError as error:
                    raise BoundedWorkspaceWriteError(
                        f"bounded write requires UTF-8 text: {label}"
                    ) from error
            self._entries[label] = {
                "path": label,
                "state": "existing" if raw is not None else "absent",
                "sha256": hashlib.sha256(raw).hexdigest() if raw is not None else "absent",
            }
        if not self._entries:
            raise BoundedWorkspaceWriteError("bounded write requires at least one expected path")

    @staticmethod
    def _normalize_path(supplied: Path) -> Path:
        raw = supplied.as_posix().replace("\\", "/")
        pure = PurePosixPath(raw)
        if (
            supplied.is_absolute()
            or pure.is_absolute()
            or not pure.parts
            or ":" in pure.parts[0]
            or any(part in {"", ".", ".."} for part in pure.parts)
        ):
            raise BoundedWorkspaceWriteError(f"invalid bounded write path: {raw}")
        return Path(*pure.parts)

    def _has_symlink_component(self, relative: Path) -> bool:
        current = self.workspace
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                return True
        return False

    @property
    def dynamic_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "name": self.TOOL_NAME,
                "description": (
                    "Atomically replace one declared UTF-8 workspace file. Use exactly once, "
                    "with a path and starting digest from the supplied CAMP boundary."
                ),
                "inputSchema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "path": {"type": "string", "enum": sorted(self._entries)},
                        "expected_sha256": {"type": "string"},
                        "content": {"type": "string", "maxLength": self.max_write_bytes},
                    },
                    "required": ["path", "expected_sha256", "content"],
                },
            }
        ]

    @property
    def boundary(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "kind": "tool-shed-bounded-workspace-write",
            "max_write_bytes": self.max_write_bytes,
            "files": [self._entries[key] for key in sorted(self._entries)],
        }

    def handle(self, params: dict[str, Any]) -> dict[str, Any]:
        if params.get("tool") != self.TOOL_NAME or params.get("namespace") not in {None, ""}:
            return self._failure("unknown_tool", None)
        arguments = params.get("arguments")
        if not isinstance(arguments, dict) or set(arguments) != {
            "path",
            "expected_sha256",
            "content",
        }:
            return self._failure("invalid_arguments", None)
        label = arguments.get("path")
        expected = arguments.get("expected_sha256")
        content = arguments.get("content")
        if self.mutation_count:
            return self._failure("mutation_already_performed", label)
        if not isinstance(label, str) or label not in self._entries:
            return self._failure("path_not_allowlisted", label)
        if not isinstance(expected, str) or expected != self._entries[label]["sha256"]:
            return self._failure("starting_digest_mismatch", label)
        if not isinstance(content, str) or "\0" in content:
            return self._failure("content_not_utf8_text", label)
        raw = content.encode("utf-8")
        if len(raw) > self.max_write_bytes:
            return self._failure("write_budget_exceeded", label)
        relative = Path(*PurePosixPath(label).parts)
        candidate = self.workspace / relative
        if self._has_symlink_component(relative) or not candidate.parent.is_dir():
            return self._failure("live_path_changed", label)
        try:
            live = candidate.read_bytes() if candidate.exists() else None
        except OSError:
            return self._failure("live_path_changed", label)
        live_digest = hashlib.sha256(live).hexdigest() if live is not None else "absent"
        if live_digest != expected or (candidate.exists() and not candidate.is_file()):
            return self._failure("live_digest_mismatch", label)
        mode = stat.S_IMODE(candidate.stat().st_mode) if candidate.exists() else 0o600
        handle, temporary_name = tempfile.mkstemp(prefix=f".{candidate.name}.", dir=candidate.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.chmod(mode)
            os.replace(temporary, candidate)
        except OSError:
            if temporary.exists():
                temporary.unlink()
            return self._failure("atomic_replace_failed", label)
        self.mutation_count = 1
        evidence = {
            "status": "written",
            "path": label,
            "starting_sha256": expected,
            "result_sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self.evidence.append(evidence)
        return self._result(True, evidence)

    def _failure(self, code: str, label: Any) -> dict[str, Any]:
        evidence = {"status": "refused", "code": code, "path": label if isinstance(label, str) else None}
        self.evidence.append(evidence)
        return self._result(False, evidence)

    @staticmethod
    def _result(success: bool, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "success": success,
            "contentItems": [
                {
                    "type": "inputText",
                    "text": json.dumps(payload, sort_keys=True, separators=(",", ":")),
                }
            ],
        }
