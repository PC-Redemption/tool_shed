#!/usr/bin/env python3
"""Protected user-local cache for Codex dirty-read qualification summaries."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

try:
    from scripts import subprocess_launch
except ModuleNotFoundError:  # Direct imports from the scripts directory
    import subprocess_launch  # type: ignore[no-redef]


CACHE_SCHEMA_VERSION = 1
DIRTY_QUALIFICATION_POLICY_REVISION = "dirty-read-v2"
DEFAULT_MAX_AGE_SECONDS = 7 * 24 * 60 * 60
LOCK_TIMEOUT_SECONDS = 10.0
STALE_LOCK_SECONDS = 30.0


class QualificationCacheError(RuntimeError):
    pass


def default_qualification_cache_path(
    environment: Mapping[str, str] | None = None,
) -> Path:
    values = os.environ if environment is None else environment
    codex_root = values.get("CODEX_HOME")
    base = Path(codex_root).expanduser() if codex_root else Path.home() / ".codex"
    return base / "tool-shed" / "dirty-read-qualifications.json"


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json_hash(value: Any) -> str:
    return _sha256_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )


def _protocol_fingerprint(executable: Path) -> tuple[str, str]:
    """Hash generated protocol schemas, falling back to a sanitized runtime probe."""

    with tempfile.TemporaryDirectory(prefix="tool-shed-codex-schema-") as temporary:
        output = Path(temporary)
        try:
            generated = subprocess_launch.run(
                [
                    str(executable),
                    "app-server",
                    "generate-json-schema",
                    "--experimental",
                    "--out",
                    str(output),
                ],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            generated = None
        schemas = sorted(output.rglob("*.json"))
        if generated is not None and generated.returncode == 0 and schemas:
            digest = hashlib.sha256()
            for schema in schemas:
                digest.update(schema.relative_to(output).as_posix().encode("utf-8"))
                digest.update(b"\0")
                digest.update(schema.read_bytes())
                digest.update(b"\0")
            return "generated-schema", digest.hexdigest()

    try:
        probe = subprocess_launch.run(
            [str(executable), "app-server", "--help"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        payload = {
            "returncode": probe.returncode,
            "stdout_sha256": _sha256_bytes(probe.stdout.encode("utf-8")),
            "stderr_sha256": _sha256_bytes(probe.stderr.encode("utf-8")),
        }
    except (OSError, subprocess.TimeoutExpired) as error:
        payload = {"probe_error": type(error).__name__}
    return "runtime-probe", _canonical_json_hash(payload)


@dataclass(frozen=True)
class QualificationIdentity:
    executable: str
    executable_sha256: str
    codex_version: str
    protocol_source: str
    protocol_sha256: str
    qualification_policy_sha256: str
    model_policy_sha256: str
    platform: str

    @property
    def key(self) -> str:
        return _canonical_json_hash(self.as_dict())

    def as_dict(self) -> dict[str, str]:
        return {
            "executable": self.executable,
            "executable_sha256": self.executable_sha256,
            "codex_version": self.codex_version,
            "protocol_source": self.protocol_source,
            "protocol_sha256": self.protocol_sha256,
            "qualification_policy_sha256": self.qualification_policy_sha256,
            "model_policy_sha256": self.model_policy_sha256,
            "platform": self.platform,
        }


def build_qualification_identity(
    *,
    executable: Path,
    codex_version: str,
    config_path: Path,
    model_policy_path: Path,
) -> QualificationIdentity:
    resolved = executable.expanduser().resolve()
    try:
        config = json.loads(config_path.expanduser().resolve().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise QualificationCacheError(f"cannot fingerprint qualification policy: {error}") from error
    qualification = config.get("qualification") if isinstance(config, dict) else None
    policy_payload = {
        "revision": DIRTY_QUALIFICATION_POLICY_REVISION,
        "qualification": qualification,
    }
    protocol_source, protocol_sha256 = _protocol_fingerprint(resolved)
    return QualificationIdentity(
        executable=str(resolved),
        executable_sha256=_sha256_file(resolved),
        codex_version=codex_version,
        protocol_source=protocol_source,
        protocol_sha256=protocol_sha256,
        qualification_policy_sha256=_canonical_json_hash(policy_payload),
        model_policy_sha256=_sha256_file(model_policy_path.expanduser().resolve()),
        platform=f"{platform.system().lower()}-{platform.machine().lower()}",
    )


@dataclass(frozen=True)
class CacheLookup:
    status: str
    source: str
    invalidation_reason: str | None
    record: dict[str, Any] | None

    def as_dict(self) -> dict[str, Any]:
        summary = None
        if self.record:
            summary = {
                "state": self.record.get("state"),
                "outcome": self.record.get("outcome"),
                "recorded_at": self.record.get("recorded_at"),
                "safe_blockers": list(self.record.get("safe_blockers") or []),
            }
        return {
            "status": self.status,
            "source": self.source,
            "invalidation_reason": self.invalidation_reason,
            "record": summary,
        }


class QualificationCache:
    """Read and atomically update sanitized qualification summaries."""

    def __init__(
        self,
        path: Path | None = None,
        *,
        max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
        now: Callable[[], float] | None = None,
    ) -> None:
        if max_age_seconds <= 0:
            raise ValueError("qualification cache max age must be positive")
        self.path = (path or default_qualification_cache_path()).expanduser().resolve()
        self.max_age_seconds = max_age_seconds
        self.now = now or time.time
        self._reject_tool_shed_tree()

    def _reject_tool_shed_tree(self) -> None:
        canonical = Path(__file__).resolve().parents[1]
        try:
            self.path.relative_to(canonical)
        except ValueError:
            pass
        else:
            raise QualificationCacheError("qualification cache must remain outside Tool Shed")
        if any(parent.name == "tool_shed" for parent in self.path.parents):
            raise QualificationCacheError(
                "qualification cache must not be stored in an installed Tool Shed snapshot"
            )

    def lookup(self, identity: QualificationIdentity) -> CacheLookup:
        payload, reason = self._read_payload()
        if payload is None:
            return CacheLookup("miss", "user-local-cache", reason, None)
        records = payload.get("records")
        if not isinstance(records, dict):
            return CacheLookup("miss", "user-local-cache", "malformed-cache", None)
        record = records.get(identity.key)
        if isinstance(record, dict):
            if not self._valid_record(record):
                return CacheLookup("miss", "user-local-cache", "malformed-entry", None)
            age = float(self.now()) - float(record["recorded_epoch"])
            if age < 0 or (
                record.get("state") == "qualified" and age > self.max_age_seconds
            ):
                return CacheLookup("miss", "user-local-cache", "stale", None)
            if record.get("identity") != identity.as_dict():
                return CacheLookup("miss", "user-local-cache", "identity-mismatch", None)
            return CacheLookup("hit", "user-local-cache", None, dict(record))
        return CacheLookup(
            "miss",
            "user-local-cache",
            self._invalidation_reason(records, identity),
            None,
        )

    def store(
        self,
        identity: QualificationIdentity,
        *,
        state: str,
        outcome: str,
        safe_blockers: list[str] | tuple[str, ...] = (),
    ) -> CacheLookup:
        if state not in {"qualified", "unsafe_denied"}:
            raise ValueError("only qualified or reviewed unsafe summaries may be cached")
        epoch = float(self.now())
        record = {
            "identity": identity.as_dict(),
            "state": state,
            "outcome": outcome,
            "safe_blockers": sorted({str(item) for item in safe_blockers}),
            "recorded_at": datetime.fromtimestamp(epoch, tz=UTC).isoformat(),
            "recorded_epoch": epoch,
        }
        with self._locked():
            payload, _ = self._read_payload()
            if payload is None:
                payload = {"schema_version": CACHE_SCHEMA_VERSION, "records": {}}
            records = payload.get("records")
            if not isinstance(records, dict):
                records = {}
                payload = {"schema_version": CACHE_SCHEMA_VERSION, "records": records}
            records[identity.key] = record
            self._atomic_write(payload)
        return CacheLookup("hit", "user-local-cache", None, record)

    def _read_payload(self) -> tuple[dict[str, Any] | None, str | None]:
        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None, "not-found"
        except OSError:
            return None, "unreadable-cache"
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None, "malformed-cache"
        if not isinstance(payload, dict) or payload.get("schema_version") != CACHE_SCHEMA_VERSION:
            return None, "unsupported-cache-schema"
        return payload, None

    @staticmethod
    def _valid_record(record: dict[str, Any]) -> bool:
        return bool(
            isinstance(record.get("identity"), dict)
            and record.get("state") in {"qualified", "unsafe_denied"}
            and isinstance(record.get("outcome"), str)
            and isinstance(record.get("recorded_epoch"), (int, float))
            and isinstance(record.get("recorded_at"), str)
            and isinstance(record.get("safe_blockers"), list)
        )

    @staticmethod
    def _invalidation_reason(
        records: dict[str, Any], identity: QualificationIdentity
    ) -> str:
        expected = identity.as_dict()
        related = [
            record
            for record in records.values()
            if isinstance(record, dict)
            and isinstance(record.get("identity"), dict)
            and record["identity"].get("executable") == expected["executable"]
        ]
        if not related:
            return "cache-miss"
        prior = related[-1]["identity"]
        comparisons = (
            ("platform", "foreign-platform"),
            ("codex_version", "codex-version-changed"),
            ("executable_sha256", "executable-changed"),
            ("protocol_sha256", "protocol-changed"),
            ("qualification_policy_sha256", "qualification-policy-changed"),
            ("model_policy_sha256", "model-policy-changed"),
        )
        for field, reason in comparisons:
            if prior.get(field) != expected[field]:
                return reason
        return "identity-mismatch"

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(self.path.parent, 0o700)
        except OSError:
            pass
        lock = self.path.with_suffix(self.path.suffix + ".lock")
        deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
        descriptor: int | None = None
        while descriptor is None:
            try:
                descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                try:
                    stale = time.time() - lock.stat().st_mtime > STALE_LOCK_SECONDS
                except OSError:
                    stale = False
                if stale:
                    try:
                        lock.unlink()
                    except OSError:
                        pass
                    continue
                if time.monotonic() >= deadline:
                    raise QualificationCacheError("timed out waiting for qualification cache lock")
                time.sleep(0.02)
        try:
            os.close(descriptor)
            yield
        finally:
            try:
                lock.unlink()
            except FileNotFoundError:
                pass

    def _atomic_write(self, payload: dict[str, Any]) -> None:
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
        )
        temp_path = Path(temporary)
        try:
            os.chmod(temp_path, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(payload, stream, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, self.path)
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
        finally:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass
