from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "bootstrap_closure.py"


def project_binding(workspace: Path) -> str:
    project_id = json.loads(
        (workspace / "work" / "tool-shed-project.json").read_text(encoding="utf-8")
    )["project_id"]
    digest = hashlib.sha256()
    for value in ("tool-shed-binding-v1", project_id, str(workspace.resolve()), "bootstrap-closure"):
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:24]


class BootstrapClosureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        subprocess.run(["git", "init", "--quiet"], cwd=self.workspace, check=True)
        subprocess.run(["git", "config", "user.name", "Tool Shed Tests"], cwd=self.workspace, check=True)
        subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=self.workspace, check=True)
        for relative, content in {
            "work/tool-shed-project.json": json.dumps(
                {"schema_version": 1, "project_id": str(uuid.uuid4()), "project_name": "fixture"},
                indent=2,
                sort_keys=True,
            )
            + "\n",
            "work/ideas/idea-fixture.md": "# Idea\n\nDesired outcome.\n",
            "work/maps/map-fixture.md": "# Map\n\nApproved direction.\n",
            "work/roadmaps/roadmap-fixture.md": "# Roadmap\n\nStatus: approved\nRevision: 1\n",
            "docs/fixture-contract.md": "# Contract\n\nFrozen.\n",
        }.items():
            path = self.workspace / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.workspace, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "fixture"], cwd=self.workspace, check=True)
        self.manifest = self.workspace / "work" / "evidence" / "bootstrap-closure-fixture.json"
        self.manifest.parent.mkdir(parents=True)
        self.manifest.write_text(json.dumps(self.draft(), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def draft(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "kind": "tool-shed-bootstrap-closure",
            "initiative": {"id": "fixture-initiative", "title": "Fixture initiative", "status": "active"},
            "project": {"project_id": "populated-by-baseline"},
            "bindings": [
                {"role": "idea", "path": "work/ideas/idea-fixture.md", "sha256": "pending"},
                {"role": "project-map", "path": "work/maps/map-fixture.md", "sha256": "pending"},
                {"role": "program-roadmap", "path": "work/roadmaps/roadmap-fixture.md", "sha256": "pending"},
                {"role": "authority-contract", "path": "docs/fixture-contract.md", "sha256": "pending"},
            ],
            "authority_contract": "docs/fixture-contract.md",
            "requirements": [
                {
                    "id": "REQ-FIXTURE-001",
                    "summary": "Freeze the fixture contract",
                    "origin": {"path": "work/ideas/idea-fixture.md", "section": "Desired outcome"},
                    "milestone": "M1-FIXTURE",
                    "evidence_gate": "G1-FIXTURE",
                    "disposition": "accepted",
                    "evidence_ids": ["EVID-FIXTURE-001"],
                }
            ],
            "decisions": [
                {
                    "id": "DEC-FIXTURE-001",
                    "summary": "Use a deterministic file manifest",
                    "status": "settled",
                    "rationale": "It remains independent from the future database.",
                }
            ],
            "changes": [],
            "evidence": [
                {
                    "id": "EVID-FIXTURE-001",
                    "gate": "G1-FIXTURE",
                    "status": "passed",
                    "references": [{"path": "docs/fixture-contract.md", "sha256": "pending"}],
                    "covers_change_ids": [],
                    "verified_at": "2026-08-28T00:00:00Z",
                }
            ],
            "migration_items": [
                {"id": "MIG-FIXTURE-001", "summary": "Rebuild the fixture", "milestone": "M1-FIXTURE", "status": "complete"}
            ],
            "upgrade_targets": [
                {
                    "id": "UPG-FIXTURE-001",
                    "summary": "Upgrade the fixture",
                    "milestone": "M1-FIXTURE",
                    "status": "complete",
                    "kind": "workspace",
                    "minimum_updater_protocol": 4,
                }
            ],
            "verdicts": [
                {
                    "scope": "G1-FIXTURE",
                    "disposition": "satisfied",
                    "summary": "The fixture gate passed.",
                    "evidence_ids": ["EVID-FIXTURE-001"],
                    "authorized_by": "fixture",
                },
                {
                    "scope": "initiative",
                    "disposition": "open",
                    "summary": "The fixture initiative remains open.",
                    "evidence_ids": [],
                    "authorized_by": "fixture",
                },
            ],
            "release_gate": {"mode": "blocking", "required_scopes": ["initiative"]},
            "baseline": {},
            "state_token": "",
        }

    def run_cli(self, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--workspace", str(self.workspace), "--json", *arguments],
            cwd=self.workspace,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=check,
        )

    def baseline(self) -> dict[str, object]:
        result = self.run_cli(
            "baseline",
            "--manifest",
            str(self.manifest.relative_to(self.workspace)),
            "--project-binding",
            project_binding(self.workspace),
        )
        return json.loads(result.stdout)

    def test_baseline_verify_report_and_final_gate(self) -> None:
        baseline = self.baseline()
        self.assertTrue(baseline["valid"])
        verified = self.run_cli(
            "verify",
            "--manifest",
            str(self.manifest.relative_to(self.workspace)),
            "--gate",
            "G1-FIXTURE",
        )
        self.assertTrue(json.loads(verified.stdout)["valid"])

        release = self.run_cli(
            "verify",
            "--manifest",
            str(self.manifest.relative_to(self.workspace)),
            "--require-final",
            check=False,
        )
        self.assertEqual(release.returncode, 1)
        self.assertIn("release gate scope initiative is not terminal", release.stdout)

        report = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--workspace",
                str(self.workspace),
                "report",
                "--manifest",
                str(self.manifest.relative_to(self.workspace)),
            ],
            cwd=self.workspace,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        self.assertIn("# Bootstrap Closure Report: Fixture initiative", report.stdout)
        self.assertIn("Release ready: `no`", report.stdout)

        token = json.loads(self.manifest.read_text(encoding="utf-8"))["state_token"]
        verdict = self.run_cli(
            "record-verdict",
            "--manifest",
            str(self.manifest.relative_to(self.workspace)),
            "--expect",
            token,
            "--project-binding",
            project_binding(self.workspace),
            "--scope",
            "initiative",
            "--disposition",
            "satisfied",
            "--summary",
            "The fixture outcome is satisfied.",
            "--authorization",
            "fixture",
            "--evidence",
            "EVID-FIXTURE-001",
        )
        self.assertNotEqual(json.loads(verdict.stdout)["state_token"], token)
        final = self.run_cli(
            "verify",
            "--manifest",
            str(self.manifest.relative_to(self.workspace)),
            "--require-final",
        )
        self.assertTrue(json.loads(final.stdout)["release_ready"])

    def test_stale_binding_and_missing_required_records_fail(self) -> None:
        self.baseline()
        (self.workspace / "docs" / "fixture-contract.md").write_text("changed\n", encoding="utf-8")
        result = self.run_cli(
            "verify",
            "--manifest",
            str(self.manifest.relative_to(self.workspace)),
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("binding 4 is stale", result.stdout)
        self.assertIn("evidence EVID-FIXTURE-001 reference 1 is stale", result.stdout)

        for missing_key in ("upgrade_targets", "verdicts"):
            with self.subTest(missing_key=missing_key):
                path = self.workspace / f"work/evidence/missing-{missing_key}.json"
                payload = self.draft()
                payload[missing_key] = []
                path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                failed = self.run_cli(
                    "baseline",
                    "--manifest",
                    str(path.relative_to(self.workspace)),
                    "--project-binding",
                    project_binding(self.workspace),
                    check=False,
                )
                self.assertEqual(failed.returncode, 2)
                expected = "initiative verdict" if missing_key == "verdicts" else "release_gate references unknown verdict scopes"
                if missing_key == "verdicts":
                    self.assertIn(expected, failed.stderr)
                else:
                    self.assertIn("bootstrap closure upgrade_targets", failed.stderr)

    def test_record_change_requires_rerun_and_rejects_stale_tokens(self) -> None:
        baseline = self.baseline()
        old_token = str(baseline["state_token"])
        changed = self.run_cli(
            "record-change",
            "--manifest",
            str(self.manifest.relative_to(self.workspace)),
            "--expect",
            old_token,
            "--project-binding",
            project_binding(self.workspace),
            "--change-id",
            "CHG-FIXTURE-001",
            "--summary",
            "Clarify the frozen contract",
            "--rationale",
            "The evidence must cover the accepted clarification.",
            "--authorization",
            "fixture",
            "--requirement",
            "REQ-FIXTURE-001",
            "--decision",
            "DEC-FIXTURE-001",
            "--rerun-evidence",
            "EVID-FIXTURE-001",
        )
        changed_token = json.loads(changed.stdout)["state_token"]
        incomplete = self.run_cli(
            "verify",
            "--manifest",
            str(self.manifest.relative_to(self.workspace)),
            check=False,
        )
        self.assertEqual(incomplete.returncode, 1)
        self.assertIn("still requires evidence EVID-FIXTURE-001 to be rerun", incomplete.stdout)

        stale = self.run_cli(
            "record-verdict",
            "--manifest",
            str(self.manifest.relative_to(self.workspace)),
            "--expect",
            old_token,
            "--project-binding",
            project_binding(self.workspace),
            "--scope",
            "initiative",
            "--disposition",
            "open",
            "--summary",
            "Still open.",
            "--authorization",
            "fixture",
            check=False,
        )
        self.assertEqual(stale.returncode, 2)
        self.assertIn("stale bootstrap closure state", stale.stderr)

        rerun = self.run_cli(
            "record-evidence",
            "--manifest",
            str(self.manifest.relative_to(self.workspace)),
            "--expect",
            changed_token,
            "--project-binding",
            project_binding(self.workspace),
            "--evidence-id",
            "EVID-FIXTURE-001",
            "--status",
            "passed",
            "--reference",
            "docs/fixture-contract.md",
            "--covers-change",
            "CHG-FIXTURE-001",
        )
        self.assertNotEqual(json.loads(rerun.stdout)["state_token"], changed_token)
        final = self.run_cli(
            "verify",
            "--manifest",
            str(self.manifest.relative_to(self.workspace)),
            "--gate",
            "G1-FIXTURE",
        )
        self.assertTrue(json.loads(final.stdout)["valid"])

    def test_record_change_requires_affected_state_evidence_and_known_history(self) -> None:
        baseline = self.baseline()
        token = str(baseline["state_token"])
        base_arguments = (
            "record-change",
            "--manifest",
            str(self.manifest.relative_to(self.workspace)),
            "--expect",
            token,
            "--project-binding",
            project_binding(self.workspace),
            "--change-id",
            "CHG-FIXTURE-002",
            "--summary",
            "Attempt an incomplete change",
            "--rationale",
            "The command must reject incomplete accounting.",
            "--authorization",
            "fixture",
        )
        empty = self.run_cli(*base_arguments, check=False)
        self.assertEqual(empty.returncode, 2)
        self.assertIn("at least one affected requirement or decision", empty.stderr)

        no_evidence = self.run_cli(
            *base_arguments,
            "--requirement",
            "REQ-FIXTURE-001",
            check=False,
        )
        self.assertEqual(no_evidence.returncode, 2)
        self.assertIn("at least one evidence result to rerun", no_evidence.stderr)

        unknown_history = self.run_cli(
            *base_arguments,
            "--requirement",
            "REQ-FIXTURE-001",
            "--rerun-evidence",
            "EVID-FIXTURE-001",
            "--supersedes",
            "CHG-FIXTURE-UNKNOWN",
            check=False,
        )
        self.assertEqual(unknown_history.returncode, 2)
        self.assertIn("supersedes unknown changes", unknown_history.stderr)


if __name__ == "__main__":
    unittest.main()
