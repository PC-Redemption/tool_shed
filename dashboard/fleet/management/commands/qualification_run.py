from __future__ import annotations

import json
import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from dashboard.fleet.contracts import ContractError
from dashboard.fleet.services import (
    create_qualification_run,
    expire_qualification_run,
    purge_qualification_run,
    qualification_purge_preview,
)


class Command(BaseCommand):
    help = "Manage development-only, purpose-bound qualification runs without exposing credentials."

    def add_arguments(self, parser):
        parser.add_argument("action", choices=("create", "expire", "preview-purge", "purge"))
        parser.add_argument("--manifest")
        parser.add_argument("--manifest-json")
        parser.add_argument("--run-id")
        parser.add_argument("--token-file")
        parser.add_argument("--preview-token")
        parser.add_argument("--force", action="store_true")

    @staticmethod
    def _write_secret(path_value: str, token: str) -> None:
        path = Path(path_value)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = path.with_name(path.name + ".tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(token + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            os.chmod(path, 0o600)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise

    @staticmethod
    def _manifest(options) -> dict:
        supplied = [bool(options.get("manifest")), bool(options.get("manifest_json"))]
        if sum(supplied) != 1:
            raise CommandError("create requires exactly one of --manifest or --manifest-json")
        try:
            if options.get("manifest"):
                value = json.loads(Path(options["manifest"]).read_text(encoding="utf-8"))
            else:
                value = json.loads(options["manifest_json"])
        except (OSError, json.JSONDecodeError) as error:
            raise CommandError("qualification manifest is unreadable or invalid JSON") from error
        if not isinstance(value, dict):
            raise CommandError("qualification manifest must be a JSON object")
        return value

    def handle(self, *args, **options):
        action = options["action"]
        try:
            if action == "create":
                if not options.get("token_file"):
                    raise CommandError("create requires --token-file")
                run, token = create_qualification_run(self._manifest(options))
                self._write_secret(options["token_file"], token)
                result = {
                    "schema_version": 1,
                    "kind": "tool-shed-qualification-run",
                    "action": "create",
                    "run_id": run.run_id,
                    "status": run.status,
                    "credential_scope": "qualification:write",
                    "credential_written": True,
                    "expires_at": run.expires_at.isoformat(),
                }
            elif action == "expire":
                if not options.get("run_id"):
                    raise CommandError("expire requires --run-id")
                run = expire_qualification_run(options["run_id"], force=options["force"])
                result = {
                    "schema_version": 1,
                    "kind": "tool-shed-qualification-run",
                    "action": "expire",
                    "run_id": run.run_id,
                    "status": run.status,
                    "expired_at": run.expired_at.isoformat() if run.expired_at else None,
                }
            elif action == "preview-purge":
                if not options.get("run_id"):
                    raise CommandError("preview-purge requires --run-id")
                result = {
                    "schema_version": 1,
                    "kind": "tool-shed-qualification-run",
                    "action": "preview-purge",
                    **qualification_purge_preview(options["run_id"]),
                }
            else:
                if not options.get("run_id") or not options.get("preview_token"):
                    raise CommandError("purge requires --run-id and --preview-token")
                purged = purge_qualification_run(options["run_id"], options["preview_token"])
                result = {
                    "schema_version": 1,
                    "kind": "tool-shed-qualification-run",
                    "action": "purge",
                    **{
                        key: value.isoformat() if hasattr(value, "isoformat") else value
                        for key, value in purged.items()
                        if key != "preview_token"
                    },
                }
        except ContractError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(json.dumps(result, sort_keys=True, separators=(",", ":")))
