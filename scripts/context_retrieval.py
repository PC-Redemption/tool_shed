#!/usr/bin/env python3
"""Digest-bound, read-only source retrieval for App Server planning."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

sys.dont_write_bytecode = True


class ContextRetrievalError(ValueError):
    """Raised when a reference snapshot or request violates its contract."""


class BoundedContextReader:
    """Own an isolated immutable snapshot and serve bounded line-range reads."""

    TOOL_NAME = "read_context"

    def __init__(
        self,
        source_root: Path,
        files: Iterable[Path],
        *,
        max_snapshot_bytes: int,
        max_manifest_bytes: int,
        max_read_bytes: int,
        max_total_bytes: int,
        max_lines: int,
    ) -> None:
        limits = (
            max_snapshot_bytes,
            max_manifest_bytes,
            max_read_bytes,
            max_total_bytes,
            max_lines,
        )
        if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in limits):
            raise ContextRetrievalError("context retrieval limits must be positive integers")
        if max_read_bytes > max_total_bytes:
            raise ContextRetrievalError("per-read budget cannot exceed cumulative budget")
        self.source_root = source_root.resolve()
        self.max_read_bytes = max_read_bytes
        self.max_total_bytes = max_total_bytes
        self.max_lines = max_lines
        self.returned_bytes = 0
        self.evidence: list[dict[str, Any]] = []
        self._temporary = tempfile.TemporaryDirectory(prefix="tool-shed-context-references-")
        self.snapshot_root = Path(self._temporary.name).resolve()
        self._entries: dict[str, dict[str, Any]] = {}

        total = 0
        for supplied in files:
            relative = self._normalize_declared_path(supplied)
            label = relative.as_posix()
            if label in self._entries:
                continue
            candidate = self.source_root / relative
            if self._has_symlink_component(relative):
                raise ContextRetrievalError(f"context reference refuses symlinked file: {label}")
            resolved = candidate.resolve()
            try:
                resolved.relative_to(self.source_root)
            except ValueError as error:
                raise ContextRetrievalError(f"context reference escapes source workspace: {label}") from error
            if not resolved.is_file():
                raise ContextRetrievalError(f"context reference requires a regular file: {label}")
            raw = resolved.read_bytes()
            if b"\0" in raw:
                raise ContextRetrievalError(f"context reference must be text: {label}")
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError as error:
                raise ContextRetrievalError(f"context reference must be UTF-8: {label}") from error
            if total + len(raw) > max_snapshot_bytes:
                continue
            total += len(raw)
            destination = self.snapshot_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
            destination.chmod(0o400)
            self._entries[label] = {
                "path": label,
                "bytes": len(raw),
                "lines": len(text.splitlines()),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }

        manifest_base = {
            "schema_version": 1,
            "kind": "tool-shed-context-reference-manifest",
            "limits": {
                "max_read_bytes": max_read_bytes,
                "max_total_bytes": max_total_bytes,
                "max_lines": max_lines,
            },
            "files": [self._entries[key] for key in sorted(self._entries)],
        }
        encoded = self._canonical(manifest_base)
        while len(encoded) > max_manifest_bytes and self._entries:
            self._entries.pop(next(reversed(self._entries)))
            manifest_base["files"] = [self._entries[key] for key in sorted(self._entries)]
            encoded = self._canonical(manifest_base)
        if len(encoded) > max_manifest_bytes:
            self.close()
            raise ContextRetrievalError("context reference manifest exceeds its byte budget")
        self.manifest_digest = hashlib.sha256(encoded).hexdigest()
        self.manifest = {**manifest_base, "manifest_sha256": self.manifest_digest}

    @staticmethod
    def _canonical(payload: dict[str, Any]) -> bytes:
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    @staticmethod
    def _normalize_declared_path(supplied: Path) -> Path:
        raw = supplied.as_posix().replace("\\", "/")
        pure = PurePosixPath(raw)
        if (
            supplied.is_absolute()
            or pure.is_absolute()
            or not pure.parts
            or ":" in pure.parts[0]
            or any(part in {"", ".", ".."} for part in pure.parts)
        ):
            raise ContextRetrievalError(f"invalid context reference path: {raw}")
        return Path(*pure.parts)

    def _has_symlink_component(self, relative: Path) -> bool:
        current = self.source_root
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                return True
        return False

    def close(self) -> None:
        self._temporary.cleanup()

    def __del__(self) -> None:
        temporary = getattr(self, "_temporary", None)
        if temporary is not None:
            temporary.cleanup()

    def __enter__(self) -> "BoundedContextReader":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @property
    def dynamic_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "name": self.TOOL_NAME,
                "description": (
                    "Read one allowlisted UTF-8 source line range from the digest-bound planning "
                    "snapshot. Use only paths in the supplied manifest."
                ),
                "inputSchema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "manifest_sha256": {"type": "string"},
                        "path": {"type": "string"},
                        "start_line": {"type": "integer", "minimum": 1},
                        "line_count": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": self.max_lines,
                        },
                    },
                    "required": ["manifest_sha256", "path", "start_line", "line_count"],
                },
            }
        ]

    def handle(self, params: dict[str, Any]) -> dict[str, Any]:
        if params.get("tool") != self.TOOL_NAME or params.get("namespace") not in {None, ""}:
            return self._failure("unknown_tool", None, None, None)
        arguments = params.get("arguments")
        if not isinstance(arguments, dict) or set(arguments) != {
            "manifest_sha256",
            "path",
            "start_line",
            "line_count",
        }:
            return self._failure("invalid_arguments", None, None, None)
        digest = arguments.get("manifest_sha256")
        label = arguments.get("path")
        start = arguments.get("start_line")
        count = arguments.get("line_count")
        if digest != self.manifest_digest:
            return self._failure("manifest_digest_mismatch", label, start, count)
        if not isinstance(label, str) or label not in self._entries:
            return self._failure("path_not_allowlisted", label, start, count)
        if (
            isinstance(start, bool)
            or not isinstance(start, int)
            or start < 1
            or isinstance(count, bool)
            or not isinstance(count, int)
            or not 1 <= count <= self.max_lines
        ):
            return self._failure("invalid_range", label, start, count)
        entry = self._entries[label]
        live_source = self.source_root / Path(*PurePosixPath(label).parts)
        relative = Path(*PurePosixPath(label).parts)
        if self._has_symlink_component(relative) or not live_source.is_file():
            return self._failure("source_digest_mismatch", label, start, count)
        try:
            live_raw = live_source.read_bytes()
        except OSError:
            return self._failure("source_digest_mismatch", label, start, count)
        if len(live_raw) != entry["bytes"] or hashlib.sha256(live_raw).hexdigest() != entry["sha256"]:
            return self._failure("source_digest_mismatch", label, start, count)
        snapshot = self.snapshot_root / relative
        try:
            raw = snapshot.read_bytes()
        except OSError:
            return self._failure("snapshot_digest_mismatch", label, start, count)
        if len(raw) != entry["bytes"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            return self._failure("snapshot_digest_mismatch", label, start, count)
        lines = raw.decode("utf-8").splitlines(keepends=True)
        if start > len(lines) and not (start == 1 and not lines):
            return self._failure("range_out_of_bounds", label, start, count)
        selected = "".join(lines[start - 1 : start - 1 + count])
        selected_bytes = len(selected.encode("utf-8"))
        if selected_bytes > self.max_read_bytes:
            return self._failure("per_read_budget_exceeded", label, start, count, selected_bytes)
        if self.returned_bytes + selected_bytes > self.max_total_bytes:
            return self._failure("cumulative_budget_exceeded", label, start, count, selected_bytes)
        self.returned_bytes += selected_bytes
        end = min(len(lines), start + count - 1)
        evidence = {
            "status": "returned",
            "manifest_sha256": self.manifest_digest,
            "path": label,
            "source_sha256": entry["sha256"],
            "start_line": start,
            "end_line": end,
            "returned_bytes": selected_bytes,
            "cumulative_returned_bytes": self.returned_bytes,
        }
        self.evidence.append(evidence)
        payload = {
            **evidence,
            "content": selected,
            "complete_file": start == 1 and end == len(lines),
        }
        return {
            "success": True,
            "contentItems": [
                {"type": "inputText", "text": json.dumps(payload, sort_keys=True)}
            ],
        }

    def _failure(
        self,
        code: str,
        path: Any,
        start: Any,
        count: Any,
        requested_bytes: int | None = None,
    ) -> dict[str, Any]:
        evidence = {
            "status": "refused",
            "code": code,
            "manifest_sha256": self.manifest_digest,
            "path": path if isinstance(path, str) else None,
            "start_line": start if isinstance(start, int) and not isinstance(start, bool) else None,
            "line_count": count if isinstance(count, int) and not isinstance(count, bool) else None,
            "requested_bytes": requested_bytes,
            "returned_bytes": 0,
            "cumulative_returned_bytes": self.returned_bytes,
        }
        self.evidence.append(evidence)
        return {
            "success": False,
            "contentItems": [
                {"type": "inputText", "text": json.dumps(evidence, sort_keys=True)}
            ],
        }

    def evidence_summary(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "manifest_sha256": self.manifest_digest,
            "allowlisted_files": len(self._entries),
            "allowlisted_paths": sorted(self._entries),
            "snapshot_bytes": sum(int(entry["bytes"]) for entry in self._entries.values()),
            "read_calls": len(self.evidence),
            "returned_bytes": self.returned_bytes,
            "refused_calls": sum(1 for item in self.evidence if item["status"] == "refused"),
            "reads": [dict(item) for item in self.evidence],
            "content_retained": False,
        }
