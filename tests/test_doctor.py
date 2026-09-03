from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import doctor  # noqa: E402
import document_conversion  # noqa: E402
import document_store  # noqa: E402
import hybrid_state  # noqa: E402


def run(
    *arguments: str,
    cwd: Path = ROOT,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *arguments],
        cwd=cwd,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def git(cwd: Path, *arguments: str) -> None:
    subprocess.run(["git", *arguments], cwd=cwd, check=True, stdout=subprocess.DEVNULL)


def work_digest(workspace: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted((workspace / "work").rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(workspace).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


class DoctorTests(unittest.TestCase):
    def install_workspace(self, workspace: Path) -> None:
        git(workspace, "init", "-q")
        git(workspace, "config", "user.name", "Tool Shed Doctor Tests")
        git(workspace, "config", "user.email", "doctor@example.invalid")
        manifest = json.loads((ROOT / "SHED_VERSION.json").read_text(encoding="utf-8"))
        shed = workspace / "tool_shed"
        for relative in manifest["content_hashes"]:
            source = ROOT / relative
            target = shed / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        shutil.copy2(ROOT / "SHED_VERSION.json", shed / "SHED_VERSION.json")
        run(str(shed / "scripts" / "install_into_workspace.py"), str(workspace))
        git(workspace, "add", ".")
        git(workspace, "commit", "-q", "-m", "Install Tool Shed")

    def campaign_command(self, workspace: Path, *arguments: str) -> dict[str, object]:
        script = workspace / "tool_shed" / "scripts" / "campaign_queue.py"
        status = json.loads(run(str(script), "--workspace", str(workspace), "status", "--json").stdout)
        result = run(
            str(script),
            "--workspace",
            str(workspace),
            *arguments,
            "--expect",
            str(status["state_token"]),
            "--project-binding",
            str(status["project"]["session_binding"]),
            "--json",
        )
        return json.loads(result.stdout)

    def test_schema3_doctor_uses_database_document_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            database = workspace / ".tool-shed/state.sqlite3"
            database.parent.mkdir(parents=True)
            database.touch()
            audit = {
                "hybrid_schema": 3,
                "classification": "VALID_DIRTY",
                "findings": [],
            }
            listed = {"documents": [], "count": 0}
            with mock.patch.object(doctor.document_store, "audit", return_value=audit), mock.patch.object(
                doctor.document_store, "list_documents", return_value=listed
            ):
                state = doctor.database_document_state(workspace)
            self.assertIsNotNone(state)
            self.assertEqual(state["campaigns"]["authority"], "sqlite")

    def test_detects_stale_index_and_dirty_campaign_transition_across_passing_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            self.install_workspace(workspace)
            self.campaign_command(
                workspace,
                "add",
                "doctor-fixture",
                "Doctor fixture",
                "--outcome",
                "reproduce stale indexes",
                "--completion-gate",
                "focused check passes",
            )
            self.campaign_command(workspace, "start", "doctor-fixture")
            run(
                str(workspace / "tool_shed" / "scripts" / "update_work_index.py"),
                "--workspace",
                str(workspace),
                "--no-preflight",
            )
            git(workspace, "add", ".")
            git(workspace, "commit", "-q", "-m", "Checkpoint working campaign")
            self.campaign_command(
                workspace,
                "block",
                "doctor-fixture",
                "--reason",
                "fixture decision",
            )

            before = work_digest(workspace)
            command = workspace / "tool_shed" / "scripts" / "doctor.py"
            result = run(str(command), "--workspace", str(workspace), "--json")
            report = json.loads(result.stdout)
            self.assertEqual(work_digest(workspace), before)
            self.assertEqual(report["schema_version"], 1)
            self.assertEqual(report["verdict"], "INVALID")
            self.assertTrue(report["read_only"])
            codes = {item["code"] for item in report["findings"]}
            self.assertIn("WORK_INDEX_STALE", codes)
            self.assertIn("DIRTY_CAMPAIGN_STATE", codes)
            self.assertFalse(report["checks"]["reconciliation"]["changes_required"])
            self.assertEqual(report["checks"]["campaigns"]["finding_count"], 0)

            strict = run(
                str(command), "--workspace", str(workspace), "--strict", check=False
            )
            self.assertEqual(strict.returncode, 1)

            repaired = run(
                str(command),
                "--workspace",
                str(workspace),
                "--repair",
                "--expect",
                report["state_token"],
                "--project-binding",
                report["project"]["session_binding"],
                "--json",
            )
            repaired_report = json.loads(repaired.stdout)
            self.assertFalse(repaired_report["read_only"])
            self.assertEqual(
                repaired_report["repair"]["repaired_paths"],
                ["work/index.md", "work/index.json"],
            )
            repaired_codes = {item["code"] for item in repaired_report["findings"]}
            self.assertNotIn("WORK_INDEX_STALE", repaired_codes)
            self.assertIn("DIRTY_CAMPAIGN_STATE", repaired_codes)

    def test_external_runtime_claim_requires_a_durable_workspace_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            completed = workspace / "work" / "00-campaigns" / "completed"
            completed.mkdir(parents=True)
            card = completed / "001-runtime-claim.md"
            card.write_text(
                "# Runtime claim\n\n"
                "Status: complete\n"
                "Type: campaign\n"
                "Updated: 2026-08-18\n"
                "Next Action: none\n"
                "Campaign ID: runtime-claim\n"
                "Campaign Number: 001\n"
                "Outcome: verify runtime\n"
                "Depends On: none\n"
                "Decision: none\n"
                "Completion Gate: runtime works\n"
                "Completion Evidence: production deployment was verified\n"
                "Completion Date: 2026-08-18\n"
                "Completion Order: 1\n"
                "Disposition: completed\n",
                encoding="utf-8",
            )
            report = doctor.external_evidence_state(workspace)
            self.assertEqual(report["unsupported_claim_count"], 1)

            evidence = workspace / "work" / "evidence" / "runtime.md"
            evidence.parent.mkdir(parents=True)
            evidence.write_text("sanitized observation\n", encoding="utf-8")
            card.write_text(
                card.read_text(encoding="utf-8").replace(
                    "production deployment was verified",
                    "production deployment was verified; work/evidence/runtime.md",
                ),
                encoding="utf-8",
            )
            report = doctor.external_evidence_state(workspace)
            self.assertEqual(report["unsupported_claim_count"], 0)

    def test_schema2_doctor_uses_database_lifecycle_not_retained_campaign_and_indexes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            self.install_workspace(workspace)
            self.campaign_command(
                workspace,
                "add",
                "retained-working",
                "Retained working campaign",
                "--outcome",
                "prove database authority",
                "--completion-gate",
                "database lifecycle wins",
            )
            self.campaign_command(workspace, "start", "retained-working")
            run(
                str(workspace / "tool_shed" / "scripts" / "update_work_index.py"),
                "--workspace",
                str(workspace),
                "--no-preflight",
            )
            git(workspace, "add", ".")
            git(workspace, "commit", "-q", "-m", "Checkpoint retained working source")

            identity = json.loads((workspace / "work/tool-shed-project.json").read_text(encoding="utf-8"))
            binding = hashlib.sha256(
                b"tool-shed-binding-v1\0"
                + identity["project_id"].encode()
                + b"\0"
                + str(workspace.resolve()).encode()
                + b"\0hybrid-state\0"
            ).hexdigest()[:24]
            database = workspace / ".tool-shed/state.sqlite3"
            hybrid_state.initialize(workspace, project_binding=binding, target=database)
            document_store.migrate(workspace, project_binding=binding, database=database)
            plan = document_conversion.build_plan(workspace, database=database)
            document_conversion.apply_plan(
                workspace,
                project_binding=binding,
                manifest=plan,
                database=database,
                actor="fixture",
            )
            campaign = document_store.list_documents(
                workspace, document_type="campaign", database=database
            )["documents"][0]
            document_store.set_lifecycle(
                workspace,
                project_binding=binding,
                identity=campaign["visible_id"],
                lifecycle="completed",
                expected_revision=campaign["document_revision"],
                actor="fixture",
                reason="database lifecycle is current",
                database=database,
            )

            report = doctor.inspect(workspace)
            codes = {item["code"] for item in report["findings"]}
            self.assertEqual(report["checks"]["campaigns"]["authority"], "sqlite")
            self.assertEqual(report["checks"]["campaigns"]["working"], [])
            self.assertFalse(report["checks"]["indexes"]["applicable"])
            self.assertEqual(report["checks"]["reconciliation"]["whole_work_finding_count"], 0)
            self.assertNotIn("WORK_INDEX_STALE", codes)
            self.assertNotIn("CAMPAIGN_RECONCILIATION_DECISION", codes)

    def test_schema2_doctor_warns_about_semantic_document_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            self.install_workspace(workspace)
            identity = json.loads((workspace / "work/tool-shed-project.json").read_text(encoding="utf-8"))
            binding = hashlib.sha256(
                b"tool-shed-binding-v1\0"
                + identity["project_id"].encode()
                + b"\0"
                + str(workspace.resolve()).encode()
                + b"\0hybrid-state\0"
            ).hexdigest()[:24]
            database = workspace / ".tool-shed/state.sqlite3"
            hybrid_state.initialize(workspace, project_binding=binding, target=database)
            document_store.migrate(workspace, project_binding=binding, database=database)
            document_store.create_document(
                workspace,
                project_binding=binding,
                document_type="idea-brief",
                title="Unreconciled promoted idea",
                body="# Unreconciled promoted idea\n\nStatus: promoted\nType: idea-brief\n",
                lifecycle="active",
                metadata={"document_type": "idea-brief"},
                actor="fixture",
                reason="semantic Doctor fixture",
                database=database,
            )

            report = doctor.inspect(workspace)
            findings = {item["code"]: item for item in report["findings"]}
            self.assertIn("DOCUMENT_SEMANTIC_DRIFT", findings)
            self.assertEqual(findings["DOCUMENT_SEMANTIC_DRIFT"]["classification"], "warning")
            self.assertEqual(findings["DOCUMENT_SEMANTIC_DRIFT"]["sample_paths"], ("IDEA-0001",))


if __name__ == "__main__":
    unittest.main()
