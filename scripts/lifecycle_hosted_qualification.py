#!/usr/bin/env python3
"""Drive deterministic reporter outage/convergence against isolated development hosting."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlparse

sys.dont_write_bytecode = True

import dashboard_reporter
import lifecycle_qualification
from project_identity import load_project_identity


KIND = "tool-shed-hosted-qualification-transport"


class HostedQualificationError(RuntimeError):
    pass


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _development_server(value: str) -> str:
    parsed = urlparse(value)
    host = (parsed.hostname or "").casefold()
    private = host.startswith(("127.", "10.", "192.168.")) or host == "localhost"
    if parsed.scheme not in {"http", "https"} or not host or not (private or "dev" in host):
        raise HostedQualificationError("server is not an explicit development target")
    return value.rstrip("/")


def _rows(workspace: Path) -> list[dict[str, Any]]:
    path = dashboard_reporter.outbox_path(workspace)
    if not path.is_file():
        return []
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        return [
            {
                "event_id": str(row["id"]),
                "sequence": int(row["sequence"]),
                "payload": json.loads(row["payload_json"]),
                "attempts": int(row["attempts"]),
                "delivered": row["delivered_at"] is not None,
            }
            for row in connection.execute("SELECT * FROM outbox ORDER BY sequence")
        ]
    finally:
        connection.close()


def _pending(workspace: Path) -> list[dict[str, Any]]:
    return [item for item in _rows(workspace) if not item["delivered"]]


def _binding(workspace: Path) -> str:
    from project_identity import binding_token

    return binding_token(workspace, operation="dashboard-report")


def _require_manifest(workspace: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    lifecycle_qualification.validate_manifest(manifest)
    if manifest["target"]["environment"] != "development":
        raise HostedQualificationError("hosted qualification is restricted to development")
    identity = load_project_identity(workspace)
    state = dashboard_reporter.load_connection(workspace)
    if str(identity["project_id"]) != str(manifest["fixture"]["project_id"]):
        raise HostedQualificationError("manifest project does not match the source workspace")
    if str(state.get("instance_id")) != str(manifest["fixture"]["instance_id"]):
        raise HostedQualificationError("manifest instance does not match the isolated connection")
    if state.get("status") != "connected" or not state.get("reporter_token"):
        raise HostedQualificationError("isolated reporter connection is not active")
    return state


def _summary_row(row: dict[str, Any]) -> dict[str, Any]:
    payload = row["payload"]
    return {
        "event_id": row["event_id"],
        "sequence": row["sequence"],
        "idempotency_key": payload["idempotency_key"],
        "payload_digest": lifecycle_qualification.digest(payload),
    }


def drive_outage(workspace: Path, manifest: dict[str, Any], server: str) -> dict[str, Any]:
    state = _require_manifest(workspace, manifest)
    if _pending(workspace):
        raise HostedQualificationError("outage phase requires an empty outbox; use the sealed prior record to resume")
    good_server = _development_server(server)
    if state.get("server") != good_server:
        state["server"] = good_server
        dashboard_reporter._write_private_json(  # noqa: SLF001 - bounded qualification hook
            dashboard_reporter.connection_path(state["project_id"]), state
        )
    baseline = dashboard_reporter._enqueue_connected(workspace, reason="qualification-baseline")  # noqa: SLF001
    delivered = dashboard_reporter.worker_once(workspace)
    if delivered.get("status") != "delivered":
        raise HostedQualificationError("baseline report did not reach development hosting")
    state = dashboard_reporter.load_connection(workspace)
    state["server"] = "http://127.0.0.1:1"
    dashboard_reporter._write_private_json(  # noqa: SLF001
        dashboard_reporter.connection_path(state["project_id"]), state
    )
    try:
        dashboard_reporter._enqueue_connected(workspace, reason="qualification-offline-one")  # noqa: SLF001
        dashboard_reporter._enqueue_connected(workspace, reason="qualification-offline-two")  # noqa: SLF001
        try:
            dashboard_reporter.worker_once(workspace)
        except dashboard_reporter.DashboardReporterError:
            outage_status = "unavailable"
        else:
            raise HostedQualificationError("unavailable endpoint unexpectedly accepted a report")
    finally:
        state = dashboard_reporter.load_connection(workspace)
        state["server"] = good_server
        dashboard_reporter._write_private_json(  # noqa: SLF001
            dashboard_reporter.connection_path(state["project_id"]), state
        )
    pending = _pending(workspace)
    if len(pending) < 2:
        raise HostedQualificationError("outage did not retain both queued reports")
    return {
        "schema_version": 1,
        "kind": KIND,
        "run_id": manifest["run_id"],
        "project_id": manifest["fixture"]["project_id"],
        "instance_id": manifest["fixture"]["instance_id"],
        "project_name": load_project_identity(workspace)["project_name"],
        "baseline": _summary_row(next(item for item in _rows(workspace) if item["sequence"] == baseline["sequence"])),
        "queued": [_summary_row(item) for item in pending],
        "outage": {
            "status": outage_status,
            "pending_count": len(pending),
            "hosted_sequence": baseline["sequence"],
            "latest_sequence": pending[-1]["sequence"],
        },
        "source": {"layer": "reporter-outbox", "authority_class": "transport-record"},
    }


def _submit(server: str, token: str, payload: dict[str, Any]) -> str:
    try:
        result = dashboard_reporter._request(  # noqa: SLF001
            server + "/api/v1/reports",
            payload=payload,
            headers={"Authorization": "Bearer " + token},
        )
        return str(result.get("status"))
    except dashboard_reporter.DashboardHTTPError as error:
        if error.status_code == 409 and error.detail == "report sequence is stale":
            return "stale"
        raise


def _browser_freshness(path: Path | None, project_name: str) -> str | None:
    if path is None:
        return None
    value = lifecycle_qualification.load_json(path, label="outage browser snapshot")
    project = next((item for item in value.get("projects", []) if item.get("name") == project_name), None)
    return None if project is None else project.get("freshness")


def drive_convergence(
    workspace: Path,
    manifest: dict[str, Any],
    server: str,
    prior: dict[str, Any],
    outage_browser: Path | None,
) -> dict[str, Any]:
    state = _require_manifest(workspace, manifest)
    good_server = _development_server(server)
    if prior.get("kind") != KIND or prior.get("run_id") != manifest["run_id"]:
        raise HostedQualificationError("prior outage record does not match the sealed run")
    pending = _pending(workspace)
    prior_sequences = [item["sequence"] for item in prior.get("queued", [])]
    if [item["sequence"] for item in pending] != prior_sequences:
        raise HostedQualificationError("outbox changed after the sealed outage checkpoint")
    token = str(state["reporter_token"])
    older, newer = pending[0], pending[-1]
    submissions = [
        {"sequence": newer["sequence"], "status": _submit(good_server, token, newer["payload"])},
        {"sequence": newer["sequence"], "status": _submit(good_server, token, newer["payload"])},
        {"sequence": older["sequence"], "status": _submit(good_server, token, older["payload"])},
    ]
    for _ in range(len(pending) + 1):
        if not _pending(workspace):
            break
        dashboard_reporter.worker_once(workspace)
    final_event = dashboard_reporter._enqueue_connected(workspace, reason="qualification-converged")  # noqa: SLF001
    final_status = dashboard_reporter.worker_once(workspace)
    if final_status.get("status") != "delivered" or _pending(workspace):
        raise HostedQualificationError("reporter outbox did not converge")
    rows = _rows(workspace)
    final_row = next(item for item in rows if item["sequence"] == final_event["sequence"])
    accepted = [prior["baseline"]["idempotency_key"], newer["payload"]["idempotency_key"], final_row["payload"]["idempotency_key"]]
    result = dict(prior)
    result["outage"] = {
        **dict(prior["outage"]),
        "browser_freshness": _browser_freshness(outage_browser, str(prior["project_name"])),
    }
    result.update(
        {
            "delivery": {"submissions": submissions, "pending_count": 0},
            "accepted_idempotency_keys": accepted,
            "latest_payload": final_row["payload"],
        }
    )
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--server", required=True)
    parser.add_argument("--state-root", required=True)
    parser.add_argument("--output", required=True)
    sub = parser.add_subparsers(dest="phase", required=True)
    sub.add_parser("outage")
    converge = sub.add_parser("converge")
    converge.add_argument("--prior", required=True)
    converge.add_argument("--outage-browser")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        workspace = Path(args.workspace).resolve()
        os.environ["TOOL_SHED_STATE_ROOT"] = str(Path(args.state_root).resolve())
        manifest = lifecycle_qualification.load_json(Path(args.manifest), label="manifest")
        if args.phase == "outage":
            result = drive_outage(workspace, manifest, args.server)
        else:
            prior = lifecycle_qualification.load_json(Path(args.prior), label="prior outage record")
            result = drive_convergence(
                workspace,
                manifest,
                args.server,
                prior,
                Path(args.outage_browser) if args.outage_browser else None,
            )
        _write(Path(args.output), result)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (HostedQualificationError, dashboard_reporter.DashboardReporterError, OSError, sqlite3.DatabaseError, ValueError) as error:
        print(f"Hosted qualification failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
