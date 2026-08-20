#!/usr/bin/env python3
"""Safety and structured-outcome primitives for opt-in App Server CAMP execution."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


class CampExecutionError(RuntimeError):
    pass


CAMP_OUTCOMES = {
    "step_complete",
    "camp_complete",
    "needs_more_context",
    "recoverable_failure",
    "blocked",
    "needs_sol_escalation",
    "needs_user_intervention",
    "cancelled",
    "unknown",
}

CAMP_OUTCOME_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "outcome": {"type": "string", "enum": sorted(CAMP_OUTCOMES)},
        "details": {"type": "string"},
        "evidence": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["outcome", "details", "evidence"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class CampStructuredOutcome:
    outcome: str
    details: str
    evidence: tuple[str, ...]


def parse_camp_outcome(text: str) -> CampStructuredOutcome:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise CampExecutionError(f"CAMP outcome is not valid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise CampExecutionError("CAMP outcome must be a JSON object")
    if set(payload) != {"outcome", "details", "evidence"}:
        raise CampExecutionError("CAMP outcome has missing or unexpected fields")
    outcome = payload.get("outcome")
    details = payload.get("details")
    evidence = payload.get("evidence")
    if outcome not in CAMP_OUTCOMES:
        raise CampExecutionError(f"unknown CAMP outcome {outcome!r}")
    if not isinstance(details, str) or not details.strip():
        raise CampExecutionError("CAMP outcome details must be non-empty text")
    if not isinstance(evidence, list) or any(not isinstance(item, str) for item in evidence):
        raise CampExecutionError("CAMP outcome evidence must be a list of paths or checks")
    return CampStructuredOutcome(str(outcome), details.strip(), tuple(evidence))


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        raise CampExecutionError(
            f"git {' '.join(args)} failed in {root}: {result.stderr.strip()}"
        )
    return result


def git_repository_root(workspace: Path) -> Path:
    resolved = workspace.expanduser().resolve()
    result = _git(resolved, "rev-parse", "--show-toplevel", check=False)
    if result.returncode != 0:
        raise CampExecutionError("write-capable CAMP execution requires a Git-backed workspace")
    root = Path(result.stdout.strip()).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise CampExecutionError("workspace is outside its reported Git repository") from error
    return root


def _status(root: Path) -> dict[str, str]:
    raw = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout
    records = raw.split("\0")
    observed: dict[str, str] = {}
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        if len(record) < 4:
            raise CampExecutionError("unexpected Git porcelain status record")
        status, path = record[:2], record[3:]
        observed[PurePosixPath(path).as_posix()] = status
        if "R" in status or "C" in status:
            if index >= len(records) or not records[index]:
                raise CampExecutionError("incomplete Git rename/copy status record")
            source = PurePosixPath(records[index]).as_posix()
            index += 1
            observed[source] = f"{status}:source"
    return observed


def _path_fingerprint(root: Path, relative: str) -> str | None:
    path = root / relative
    if path.is_symlink():
        return "symlink:" + str(path.readlink())
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalize_scopes(root: Path, expected_paths: Iterable[Path]) -> tuple[str, ...]:
    scopes: list[str] = []
    for supplied in expected_paths:
        candidate = supplied if supplied.is_absolute() else root / supplied
        resolved = candidate.resolve(strict=False)
        try:
            relative = resolved.relative_to(root)
        except ValueError as error:
            raise CampExecutionError(f"expected CAMP path escapes repository: {supplied}") from error
        label = PurePosixPath(relative).as_posix()
        if label in {"", "."}:
            raise CampExecutionError("repository-wide CAMP write scope is not allowed")
        scopes.append(label.rstrip("/"))
    if not scopes:
        raise CampExecutionError("write-capable CAMP execution requires an explicit path scope")
    return tuple(dict.fromkeys(scopes))


def _in_scope(path: str, scopes: tuple[str, ...]) -> bool:
    return any(path == scope or path.startswith(scope + "/") for scope in scopes)


@dataclass
class GitMutationJournal:
    campaign: str
    camp: str
    workspace_root: Path
    repository_root: Path
    expected_paths: tuple[str, ...]
    start_commit: str | None
    start_status: dict[str, str]
    start_dirty_fingerprints: dict[str, str | None]
    start_state_identifier: str

    @classmethod
    def begin(
        cls,
        *,
        campaign: str,
        camp: str,
        workspace: Path,
        expected_paths: Iterable[Path],
    ) -> GitMutationJournal:
        if not campaign.strip() or not camp.strip():
            raise CampExecutionError("campaign and CAMP identifiers are required")
        workspace_root = workspace.expanduser().resolve()
        repository_root = git_repository_root(workspace_root)
        scopes = _normalize_scopes(repository_root, expected_paths)
        status = _status(repository_root)
        overlap = sorted(path for path in status if _in_scope(path, scopes))
        if overlap:
            raise CampExecutionError(
                "expected CAMP paths already contain dirty work: " + ", ".join(overlap)
            )
        commit_result = _git(repository_root, "rev-parse", "HEAD", check=False)
        commit = commit_result.stdout.strip() if commit_result.returncode == 0 else None
        fingerprints = {
            path: _path_fingerprint(repository_root, path) for path in sorted(status)
        }
        state_payload = {
            "commit": commit,
            "status": status,
            "dirty_fingerprints": fingerprints,
        }
        identifier = hashlib.sha256(
            json.dumps(state_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return cls(
            campaign=campaign,
            camp=camp,
            workspace_root=workspace_root,
            repository_root=repository_root,
            expected_paths=scopes,
            start_commit=commit,
            start_status=status,
            start_dirty_fingerprints=fingerprints,
            start_state_identifier=identifier,
        )

    def finalize(
        self,
        *,
        thread_id: str | None,
        turn_id: str | None,
        turn_status: str,
        mutation_events: Iterable[dict[str, Any]] = (),
        cancelled_or_interrupted: bool = False,
        recovery_action: str = "none",
    ) -> dict[str, Any]:
        final_status = _status(self.repository_root)
        all_paths = set(self.start_status) | set(final_status)
        changed_paths = sorted(
            path
            for path in all_paths
            if self.start_status.get(path) != final_status.get(path)
        )
        preserved_dirty = True
        dirty_drift: list[str] = []
        for path, starting_status in self.start_status.items():
            if final_status.get(path) != starting_status or _path_fingerprint(
                self.repository_root, path
            ) != self.start_dirty_fingerprints.get(path):
                preserved_dirty = False
                dirty_drift.append(path)
                if path not in changed_paths:
                    changed_paths.append(path)
        changed_paths.sort()
        unexpected = sorted(
            path for path in changed_paths if not _in_scope(path, self.expected_paths)
        )
        created: list[str] = []
        modified: list[str] = []
        deleted: list[str] = []
        for path in changed_paths:
            before, after = self.start_status.get(path), final_status.get(path)
            if after == "??" and before is None:
                created.append(path)
            elif after is None or (after and "D" in after[:2]):
                deleted.append(path)
            else:
                modified.append(path)
        commands: list[Any] = []
        for event in mutation_events:
            if event.get("type") == "commandExecution" and event.get("command") is not None:
                commands.append(event.get("command"))
        safe = not unexpected and preserved_dirty
        final_state = "verified" if safe else "needs_user_intervention"
        return {
            "schema_version": 1,
            "campaign": self.campaign,
            "camp": self.camp,
            "thread_id": thread_id,
            "turn_id": turn_id,
            "workspace_root": str(self.workspace_root),
            "repository_root": str(self.repository_root),
            "expected_paths": list(self.expected_paths),
            "start_commit": self.start_commit,
            "start_status": dict(self.start_status),
            "start_state_identifier": self.start_state_identifier,
            "files_created": created,
            "files_modified": modified,
            "files_deleted": deleted,
            "commands_executed": commands,
            "turn_status": turn_status,
            "final_state": final_state,
            "cancelled_or_interrupted": cancelled_or_interrupted,
            "recovery_action": recovery_action,
            "preexisting_dirty_preserved": preserved_dirty,
            "preexisting_dirty_drift": dirty_drift,
            "unexpected_paths": unexpected,
            "safe": safe,
        }


def structured_outcome_record(outcome: CampStructuredOutcome) -> dict[str, Any]:
    record = asdict(outcome)
    record["evidence"] = list(outcome.evidence)
    return record


def camp_next_action(
    outcome: CampStructuredOutcome,
    *,
    attempt: int,
    journal: dict[str, Any],
) -> str:
    """Select the lifecycle action; model prose never changes CAMP state directly."""

    if attempt < 1 or attempt > 2:
        raise CampExecutionError("Terra CAMP attempt must be 1 or 2")
    if not journal.get("safe"):
        return "needs_user_intervention"
    mutated = any(
        journal.get(key)
        for key in ("files_created", "files_modified", "files_deleted")
    )
    if outcome.outcome == "camp_complete":
        return "verify_before_campaign_transition"
    if outcome.outcome == "step_complete":
        return "advance_to_next_camp_step"
    if outcome.outcome == "needs_more_context":
        return "gather_focused_context"
    if outcome.outcome == "blocked":
        return "fallback_to_existing_gui"
    if outcome.outcome in {"cancelled", "unknown", "needs_user_intervention"}:
        return "needs_user_intervention"
    if outcome.outcome in {"recoverable_failure", "needs_sol_escalation"}:
        if mutated:
            return "reconcile_workspace_before_retry"
        if outcome.outcome == "recoverable_failure" and attempt == 1:
            return "retry_terra_once"
        return "escalate_to_sol_read_only"
    raise CampExecutionError(f"unhandled CAMP outcome {outcome.outcome!r}")
