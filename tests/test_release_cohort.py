from __future__ import annotations

import contextlib
import json
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import hybrid_state  # noqa: E402
import release_cohort  # noqa: E402
from project_identity import binding_token  # noqa: E402


class ReleaseCohortTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        subprocess.run(["git", "init", "--quiet"], cwd=self.workspace, check=True)
        subprocess.run(
            ["git", "config", "user.name", "Tool Shed Tests"], cwd=self.workspace, check=True
        )
        subprocess.run(
            ["git", "config", "user.email", "tests@example.invalid"],
            cwd=self.workspace,
            check=True,
        )
        identity = {
            "schema_version": 1,
            "project_id": str(uuid.uuid4()),
            "project_name": "release-cohort-fixture",
        }
        files = {
            ".gitignore": "/.tool-shed/\n",
            "work/tool-shed-project.json": json.dumps(identity, indent=2, sort_keys=True) + "\n",
            "product.txt": "released baseline\n",
        }
        for relative, content in files.items():
            path = self.workspace / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.workspace, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "baseline"], cwd=self.workspace, check=True)
        subprocess.run(["git", "tag", "v1.0.0"], cwd=self.workspace, check=True)
        (self.workspace / "product.txt").write_text("Work2 candidate\n", encoding="utf-8")
        subprocess.run(["git", "add", "product.txt"], cwd=self.workspace, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "candidate"], cwd=self.workspace, check=True)
        self.binding = binding_token(self.workspace, operation="hybrid-state")
        hybrid_state.initialize(self.workspace, project_binding=self.binding)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _write_release_policy(
        self,
        *,
        policy: str = "fixed-width-dotted-numeric",
        prefix: str = "v",
        widths: list[int] | None = None,
    ) -> None:
        release_identity: dict[str, object] = {
            "schema_version": 1,
            "policy": policy,
        }
        if policy == "fixed-width-dotted-numeric":
            release_identity.update(
                {"prefix": prefix, "segment_widths": widths or [2, 2, 2]}
            )
        (self.workspace / ".tool-shed-policy.json").write_text(
            json.dumps(
                {"schema_version": 1, "release_identity": release_identity},
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    def _close_cycle(self, cycle_id: str) -> None:
        def write(connection, revision):
            stamp = hybrid_state.now()
            connection.execute(
                "UPDATE cycle SET lifecycle_state='terminal', closed_at=? WHERE id=?",
                (stamp, cycle_id),
            )
            verdict_id = hybrid_state.random_uuid()
            connection.execute(
                "INSERT INTO outcome_verdict VALUES (?, ?, 'fixture', 'satisfied', ?, ?, ?, ?)",
                (verdict_id, cycle_id, "Production release verified.", "fixture", revision, stamp),
            )
            connection.execute(
                "INSERT INTO reconciliation VALUES (?, ?, ?, '[]', ?, 'reconciled', ?, '[]')",
                (hybrid_state.random_uuid(), cycle_id, revision, verdict_id, stamp),
            )

        hybrid_state.managed_write(
            self.workspace,
            project_binding=self.binding,
            command="close-fixture-origin",
            actor="fixture",
            callback=write,
            expected_writes=3,
        )

    def test_work5_freeze_refuses_unresolved_app_server_dispatch(self) -> None:
        with mock.patch.object(
            release_cohort,
            "require_no_app_server_dispatch_debt",
            side_effect=release_cohort.AppServerUserStateError("dispatch debt"),
        ):
            with self.assertRaisesRegex(release_cohort.ReleaseCohortError, "dispatch debt"):
                release_cohort.freeze(
                    self.workspace,
                    expected="unused",
                    project_binding=self.binding,
                    content_commitish="HEAD",
                )

    def test_default_policy_rejects_leading_zero_release_tags(self) -> None:
        subprocess.run(["git", "tag", "-d", "v1.0.0"], cwd=self.workspace, check=True, stdout=subprocess.DEVNULL)
        baseline = subprocess.run(
            ["git", "rev-parse", "HEAD^"], cwd=self.workspace, check=True, text=True, capture_output=True
        ).stdout.strip()
        subprocess.run(["git", "tag", "v01.00.00", baseline], cwd=self.workspace, check=True)
        current = release_cohort.status(self.workspace)
        self.assertTrue(current["current_base_tag"].startswith("root:"))
        self.assertEqual(current["release_identity"]["policy"]["policy"], "strict-semver")
        self.assertEqual(current["release_identity"]["selected_tag"], None)
        self.assertEqual(
            current["release_identity"]["rejected_tags"][0]["tag"], "v01.00.00"
        )

    def test_fixed_width_policy_preserves_exact_tag(self) -> None:
        subprocess.run(
            ["git", "tag", "-d", "v1.0.0"],
            cwd=self.workspace,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        baseline = subprocess.run(
            ["git", "rev-parse", "HEAD^"],
            cwd=self.workspace,
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        subprocess.run(["git", "tag", "v00.05.00", baseline], cwd=self.workspace, check=True)
        self._write_release_policy()
        current = release_cohort.status(self.workspace)
        self.assertEqual(current["current_base_tag"], "v00.05.00")
        self.assertEqual(current["release_identity"]["selected_tag"], "v00.05.00")
        self.assertEqual(
            current["release_identity"]["policy"]["policy"],
            "fixed-width-dotted-numeric",
        )
        self.assertEqual(current["release_identity"]["policy"]["source"], ".tool-shed-policy.json")

    def test_release_policy_rejects_unsafe_or_executable_extensions(self) -> None:
        self._write_release_policy(prefix="release/", widths=[2, 2, 2])
        with self.assertRaisesRegex(release_cohort.ReleaseCohortError, "safe 1-32"):
            release_cohort.status(self.workspace)
        payload = {
            "schema_version": 1,
            "release_identity": {
                "schema_version": 1,
                "policy": "strict-semver",
                "validator": "./repository-hook",
            },
        }
        (self.workspace / ".tool-shed-policy.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
        with self.assertRaisesRegex(release_cohort.ReleaseCohortError, "unsupported fields"):
            release_cohort.status(self.workspace)

    def test_topology_fallback_ignores_numeric_order_and_finalized_preference_wins(self) -> None:
        subprocess.run(
            ["git", "tag", "-d", "v1.0.0"],
            cwd=self.workspace,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        subprocess.run(["git", "tag", "v9.0.0", "HEAD^"], cwd=self.workspace, check=True)
        subprocess.run(["git", "tag", "v1.1.0", "HEAD"], cwd=self.workspace, check=True)
        fallback = release_cohort._release_identity_status(
            self.workspace, release_cohort._commit(self.workspace, "HEAD"), []
        )
        self.assertEqual(fallback["selected_tag"], "v1.1.0")
        preferred = release_cohort._release_identity_status(
            self.workspace,
            release_cohort._commit(self.workspace, "HEAD"),
            ["v9.0.0"],
        )
        self.assertEqual(preferred["selected_tag"], "v9.0.0")
        self.assertEqual(preferred["selection_source"], "finalized-cohort")

    def test_unreachable_eligible_tag_is_reported_and_not_selected(self) -> None:
        subprocess.run(["git", "checkout", "--orphan", "unreachable"], cwd=self.workspace, check=True, stdout=subprocess.DEVNULL)
        (self.workspace / "orphan.txt").write_text("orphan\n", encoding="utf-8")
        subprocess.run(["git", "add", "orphan.txt"], cwd=self.workspace, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "orphan"], cwd=self.workspace, check=True)
        subprocess.run(["git", "tag", "v2.0.0"], cwd=self.workspace, check=True)
        subprocess.run(["git", "checkout", "master"], cwd=self.workspace, check=True, stdout=subprocess.DEVNULL)
        current = release_cohort.status(self.workspace)
        rejection = next(
            item for item in current["release_identity"]["rejected_tags"]
            if item["tag"] == "v2.0.0"
        )
        self.assertIn("not reachable", rejection["reason"])
        self.assertEqual(current["current_base_tag"], "v1.0.0")

    def test_multiple_eligible_tags_on_selected_commit_fail_closed(self) -> None:
        subprocess.run(["git", "tag", "v1.0.1", "HEAD^"], cwd=self.workspace, check=True)
        with self.assertRaisesRegex(release_cohort.ReleaseCohortError, "multiple eligible"):
            release_cohort.status(self.workspace)

    def test_registration_selects_a_base_reachable_from_the_candidate(self) -> None:
        subprocess.run(["git", "tag", "v1.1.0", "HEAD"], cwd=self.workspace, check=True)
        candidate = subprocess.run(
            ["git", "rev-parse", "HEAD^"],
            cwd=self.workspace,
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        initial = release_cohort.status(self.workspace)
        self.assertEqual(initial["current_base_tag"], "v1.1.0")
        registered = release_cohort.register(
            self.workspace,
            expected=initial["state_token"],
            project_binding=self.binding,
            commitish=candidate,
            origin_cycles=[],
            accepted_outcome="Release the older reachable candidate.",
            summary="Candidate-specific baseline fixture.",
        )
        self.assertEqual(registered["status"]["active"][0]["base_tag"], "v1.0.0")

    def test_working_base_repair_is_topology_guarded_and_append_only(self) -> None:
        registered = release_cohort.register(
            self.workspace,
            expected=release_cohort.status(self.workspace)["state_token"],
            project_binding=self.binding,
            commitish="HEAD",
            origin_cycles=[],
            accepted_outcome="Ship the fixed-width base repair.",
            summary="Base repair fixture.",
        )
        subprocess.run(["git", "tag", "v1.1.0", "HEAD"], cwd=self.workspace, check=True)
        plan = release_cohort.preview_base_repair(self.workspace, tag="v1.1.0")
        self.assertFalse(plan["writes_performed"])
        repaired = release_cohort.repair_base(
            self.workspace,
            project_binding=self.binding,
            expected_plan_token=plan["plan_token"],
            manifest=plan,
        )
        cohort = repaired["status"]["active"][0]
        self.assertEqual(cohort["original_base_tag"], "v1.0.0")
        self.assertEqual(cohort["base_tag"], "v1.1.0")
        self.assertEqual(cohort["base_correction_count"], 1)
        self.assertEqual(len(cohort["candidates"]), 1)
        with contextlib.closing(
            hybrid_state.connect(hybrid_state.database_path(self.workspace), writable=False)
        ) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM evidence_reference WHERE cycle_id=? AND kind='release-base-tag'",
                    (cohort["cycle_id"],),
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM evidence_reference WHERE cycle_id=? AND kind='release-base-tag-correction'",
                    (cohort["cycle_id"],),
                ).fetchone()[0],
                1,
            )
        frozen = release_cohort.freeze(
            self.workspace,
            expected=repaired["status"]["state_token"],
            project_binding=self.binding,
            content_commitish="HEAD",
        )
        with self.assertRaisesRegex(release_cohort.ReleaseCohortError, "only while a cohort is working"):
            release_cohort.preview_base_repair(
                self.workspace, tag="v01.01.00", cohort_id=frozen["status"]["active"][0]["cycle_id"]
            )

    def test_work2_registration_release_and_final_reconciliation_are_persistent(self) -> None:
        initial = release_cohort.status(self.workspace)
        registered = release_cohort.register(
            self.workspace,
            expected=initial["state_token"],
            project_binding=self.binding,
            commitish="HEAD",
            origin_cycles=[],
            accepted_outcome="Ship and production-verify the candidate behavior.",
            summary="Fixture candidate outcome.",
        )
        direct_cycle = registered["result"]["created_direct_cycle"]
        current = registered["status"]
        self.assertEqual(current["projection"]["projection_source_revision"], current["revision"])
        self.assertEqual(current["projection"]["projection_source_digest"], current["domain_digest"])
        self.assertEqual(current["active"][0]["base_tag"], "v1.0.0")
        self.assertEqual(len(current["active"][0]["candidates"]), 1)
        self.assertEqual(
            current["active"][0]["candidates"][0]["origin_cycle_id"], direct_cycle
        )

        repeated = release_cohort.register(
            self.workspace,
            expected=current["state_token"],
            project_binding=self.binding,
            commitish="HEAD",
            origin_cycles=[direct_cycle],
            accepted_outcome=None,
            summary=None,
        )
        self.assertFalse(repeated["writes_performed"])
        self.assertEqual(repeated["status"]["revision"], current["revision"])

        frozen = release_cohort.freeze(
            self.workspace,
            expected=current["state_token"],
            project_binding=self.binding,
            content_commitish="HEAD",
        )
        first_content_commit = frozen["result"]["content_commit"]
        (self.workspace / "product.txt").write_text("Corrected Work5 candidate\n", encoding="utf-8")
        subprocess.run(["git", "add", "product.txt"], cwd=self.workspace, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "correct candidate"], cwd=self.workspace, check=True)
        corrected = release_cohort.status(self.workspace)
        with self.assertRaisesRegex(
            release_cohort.ReleaseCohortError, "requires durable failed-CI evidence"
        ):
            release_cohort.freeze(
                self.workspace,
                expected=corrected["state_token"],
                project_binding=self.binding,
                content_commitish="HEAD",
            )
        refrozen = release_cohort.freeze(
            self.workspace,
            expected=corrected["state_token"],
            project_binding=self.binding,
            content_commitish="HEAD",
            failure_evidence="https://example.invalid/actions/runs/failed",
        )
        content_commit = refrozen["result"]["content_commit"]
        self.assertEqual(refrozen["result"]["previous_content_commit"], first_content_commit)
        self.assertNotEqual(content_commit, first_content_commit)
        self.assertEqual(refrozen["status"]["active"][0]["content_commit"], content_commit)
        subprocess.run(["git", "tag", "v1.1.0", content_commit], cwd=self.workspace, check=True)
        tagged = release_cohort.status(self.workspace)
        published = release_cohort.record_release(
            self.workspace,
            expected=tagged["state_token"],
            project_binding=self.binding,
            tag="v1.1.0",
            evidence="https://example.invalid/releases/v1.1.0",
        )
        candidate = published["status"]["active"][0]["candidates"][0]
        self.assertEqual(candidate["disposition"], "released-pending-reconciliation")
        with self.assertRaisesRegex(
            release_cohort.ReleaseCohortError, "still require closed-loop reconciliation"
        ):
            release_cohort.finalize(
                self.workspace,
                expected=published["status"]["state_token"],
                project_binding=self.binding,
                authorization="fixture",
            )

        self._close_cycle(direct_cycle)
        ready = release_cohort.status(self.workspace)
        finalized = release_cohort.finalize(
            self.workspace,
            expected=ready["state_token"],
            project_binding=self.binding,
            authorization="fixture",
        )
        self.assertEqual(finalized["result"]["lifecycle"], "terminal")
        self.assertEqual(finalized["status"]["active"], [])
        self.assertEqual(finalized["status"]["recent_terminal"][0]["release_tag"], "v1.1.0")
        self.assertEqual(release_cohort.status(self.workspace)["finding_count"], 0)

        checkpoint = hybrid_state.write_checkpoint(
            self.workspace, project_binding=self.binding
        )
        rebuilt = hybrid_state.rebuild_from_checkpoint(
            self.workspace,
            project_binding=self.binding,
            checkpoint=Path(checkpoint["path"]),
            output=Path(".tool-shed/rebuilt-release-cohort.sqlite3"),
        )
        self.assertEqual(rebuilt["domain_digest"], hybrid_state.audit(self.workspace)["domain_digest"])

    def test_registration_expands_to_every_open_parent_outcome(self) -> None:
        ids: dict[str, str] = {}

        def write(connection, revision):
            stamp = hybrid_state.now()
            for name in ("idea", "roadmap"):
                artifact_id = hybrid_state.random_uuid()
                cycle_id = hybrid_state.random_uuid()
                ids[f"{name}_artifact"] = artifact_id
                ids[f"{name}_cycle"] = cycle_id
                connection.execute(
                    "INSERT INTO artifact VALUES (?, ?, NULL, ?, 'sqlite', 'working', ?, ?, ?)",
                    (artifact_id, name, f"sqlite/documents/{name}", "0" * 64, stamp, stamp),
                )
                connection.execute(
                    "INSERT INTO cycle VALUES (?, ?, ?, ?, 'working', ?, NULL)",
                    (cycle_id, name, artifact_id, f"Complete {name} outcome.", stamp),
                )
                verdict_id = hybrid_state.random_uuid()
                connection.execute(
                    "INSERT INTO outcome_verdict VALUES (?, ?, ?, 'open', ?, 'fixture', ?, ?)",
                    (verdict_id, cycle_id, name, f"Open {name}.", revision, stamp),
                )
                connection.execute(
                    "INSERT INTO reconciliation VALUES (?, ?, ?, '[]', ?, 'open', ?, '[]')",
                    (hybrid_state.random_uuid(), cycle_id, revision, verdict_id, stamp),
                )
            connection.execute(
                "INSERT INTO relationship VALUES (?, ?, 'outcome-parent', ?, 'fixture', ?, NULL)",
                (
                    hybrid_state.random_uuid(), ids["roadmap_artifact"], ids["idea_artifact"],
                    revision,
                ),
            )

        hybrid_state.managed_write(
            self.workspace,
            project_binding=self.binding,
            command="create-parent-chain",
            actor="fixture",
            callback=write,
            expected_writes=9,
        )
        initial = release_cohort.status(self.workspace)
        registered = release_cohort.register(
            self.workspace,
            expected=initial["state_token"],
            project_binding=self.binding,
            commitish="HEAD",
            origin_cycles=[ids["roadmap_cycle"]],
            accepted_outcome=None,
            summary=None,
        )
        candidates = registered["status"]["active"][0]["candidates"]
        self.assertEqual(
            {item["origin_cycle_id"] for item in candidates},
            {ids["roadmap_cycle"], ids["idea_cycle"]},
        )
        self.assertEqual(registered["status"]["finding_count"], 0)
        with contextlib.closing(
            hybrid_state.connect(hybrid_state.database_path(self.workspace), writable=False)
        ) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM relationship WHERE relation_type='release-candidate-member'"
                ).fetchone()[0],
                2,
            )

    def test_terminal_pre_cohort_work2_result_gets_one_release_extension(self) -> None:
        ids: dict[str, str] = {}

        def write(connection, revision):
            stamp = hybrid_state.now()
            artifact_id = hybrid_state.random_uuid()
            cycle_id = hybrid_state.random_uuid()
            verdict_id = hybrid_state.random_uuid()
            ids.update(artifact=artifact_id, cycle=cycle_id)
            connection.execute(
                "INSERT INTO artifact VALUES (?, 'direct-work', NULL, ?, 'sqlite', 'terminal', ?, ?, ?)",
                (artifact_id, f"sqlite/outcome-capsules/{artifact_id}", "1" * 64, stamp, stamp),
            )
            connection.execute(
                "INSERT INTO cycle VALUES (?, 'direct-work', ?, ?, 'terminal', ?, ?)",
                (cycle_id, artifact_id, "Deliver the prior Work2 fix.", stamp, stamp),
            )
            connection.execute(
                "INSERT INTO outcome_verdict VALUES (?, ?, 'fixture', 'satisfied', ?, 'fixture', ?, ?)",
                (verdict_id, cycle_id, "Work2 checks passed.", revision, stamp),
            )
            connection.execute(
                "INSERT INTO reconciliation VALUES (?, ?, ?, '[]', ?, 'reconciled', ?, '[]')",
                (hybrid_state.random_uuid(), cycle_id, revision, verdict_id, stamp),
            )

        hybrid_state.managed_write(
            self.workspace,
            project_binding=self.binding,
            command="create-terminal-work2-origin",
            actor="fixture",
            callback=write,
            expected_writes=4,
        )
        initial = release_cohort.status(self.workspace)
        registered = release_cohort.register(
            self.workspace,
            expected=initial["state_token"],
            project_binding=self.binding,
            commitish="HEAD",
            origin_cycles=[ids["cycle"]],
            accepted_outcome=None,
            summary=None,
        )
        extension = registered["result"]["release_extensions"][0]
        self.assertEqual(extension["original_cycle_id"], ids["cycle"])
        self.assertNotEqual(extension["extension_cycle_id"], ids["cycle"])
        candidate = registered["status"]["active"][0]["candidates"][0]
        self.assertEqual(candidate["origin_cycle_id"], extension["extension_cycle_id"])

        repeated = release_cohort.register(
            self.workspace,
            expected=registered["status"]["state_token"],
            project_binding=self.binding,
            commitish="HEAD",
            origin_cycles=[ids["cycle"]],
            accepted_outcome=None,
            summary=None,
        )
        self.assertFalse(repeated["writes_performed"])
        with contextlib.closing(
            hybrid_state.connect(hybrid_state.database_path(self.workspace), writable=False)
        ) as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM relationship WHERE relation_type='release-extension-of'"
                ).fetchone()[0],
                1,
            )

    def test_sequential_milestone_releases_share_one_open_parent(self) -> None:
        ids: dict[str, str] = {}

        def create_chain(connection, revision):
            stamp = hybrid_state.now()
            for name in ("parent", "milestone-one"):
                artifact_id = hybrid_state.random_uuid()
                cycle_id = hybrid_state.random_uuid()
                ids[f"{name}_artifact"] = artifact_id
                ids[f"{name}_cycle"] = cycle_id
                connection.execute(
                    "INSERT INTO artifact VALUES (?, ?, NULL, ?, 'sqlite', 'working', ?, ?, ?)",
                    (artifact_id, name, f"sqlite/documents/{name}", "2" * 64, stamp, stamp),
                )
                connection.execute(
                    "INSERT INTO cycle VALUES (?, ?, ?, ?, 'working', ?, NULL)",
                    (cycle_id, name, artifact_id, f"Complete {name}.", stamp),
                )
                verdict_id = hybrid_state.random_uuid()
                connection.execute(
                    "INSERT INTO outcome_verdict VALUES (?, ?, ?, 'open', ?, 'fixture', ?, ?)",
                    (verdict_id, cycle_id, name, f"Open {name}.", revision, stamp),
                )
                connection.execute(
                    "INSERT INTO reconciliation VALUES (?, ?, ?, '[]', ?, 'open', ?, '[]')",
                    (hybrid_state.random_uuid(), cycle_id, revision, verdict_id, stamp),
                )
            connection.execute(
                "INSERT INTO relationship VALUES (?, ?, 'outcome-parent', ?, 'fixture', ?, NULL)",
                (
                    hybrid_state.random_uuid(), ids["milestone-one_artifact"],
                    ids["parent_artifact"], revision,
                ),
            )

        hybrid_state.managed_write(
            self.workspace,
            project_binding=self.binding,
            command="create-sequential-release-chain",
            actor="fixture",
            callback=create_chain,
            expected_writes=9,
        )
        first = release_cohort.register(
            self.workspace,
            expected=release_cohort.status(self.workspace)["state_token"],
            project_binding=self.binding,
            commitish="HEAD",
            origin_cycles=[ids["milestone-one_cycle"]],
            accepted_outcome=None,
            summary=None,
        )
        first_cohort = first["result"]["cohort_id"]
        self._close_cycle(ids["milestone-one_cycle"])
        frozen = release_cohort.freeze(
            self.workspace,
            expected=release_cohort.status(self.workspace)["state_token"],
            project_binding=self.binding,
            content_commitish="HEAD",
        )
        subprocess.run(["git", "tag", "v1.1.0", frozen["result"]["content_commit"]], cwd=self.workspace, check=True)
        release_cohort.record_release(
            self.workspace,
            expected=release_cohort.status(self.workspace)["state_token"],
            project_binding=self.binding,
            tag="v1.1.0",
            evidence="https://example.invalid/releases/v1.1.0",
        )

        (self.workspace / "product.txt").write_text("Second milestone\n", encoding="utf-8")
        subprocess.run(["git", "add", "product.txt"], cwd=self.workspace, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "second milestone"], cwd=self.workspace, check=True)

        def create_second_milestone(connection, revision):
            stamp = hybrid_state.now()
            artifact_id = hybrid_state.random_uuid()
            cycle_id = hybrid_state.random_uuid()
            ids["milestone-two_artifact"] = artifact_id
            ids["milestone-two_cycle"] = cycle_id
            connection.execute(
                "INSERT INTO artifact VALUES (?, 'milestone', NULL, ?, 'sqlite', 'working', ?, ?, ?)",
                (artifact_id, "sqlite/documents/milestone-two", "3" * 64, stamp, stamp),
            )
            connection.execute(
                "INSERT INTO cycle VALUES (?, 'milestone', ?, ?, 'working', ?, NULL)",
                (cycle_id, artifact_id, "Complete milestone two.", stamp),
            )
            verdict_id = hybrid_state.random_uuid()
            connection.execute(
                "INSERT INTO outcome_verdict VALUES (?, ?, 'milestone', 'open', ?, 'fixture', ?, ?)",
                (verdict_id, cycle_id, "Open milestone two.", revision, stamp),
            )
            connection.execute(
                "INSERT INTO reconciliation VALUES (?, ?, ?, '[]', ?, 'open', ?, '[]')",
                (hybrid_state.random_uuid(), cycle_id, revision, verdict_id, stamp),
            )
            connection.execute(
                "INSERT INTO relationship VALUES (?, ?, 'outcome-parent', ?, 'fixture', ?, NULL)",
                (
                    hybrid_state.random_uuid(), artifact_id, ids["parent_artifact"], revision,
                ),
            )

        hybrid_state.managed_write(
            self.workspace,
            project_binding=self.binding,
            command="create-second-milestone",
            actor="fixture",
            callback=create_second_milestone,
            expected_writes=5,
        )
        second = release_cohort.register(
            self.workspace,
            expected=release_cohort.status(self.workspace)["state_token"],
            project_binding=self.binding,
            commitish="HEAD",
            origin_cycles=[ids["milestone-two_cycle"]],
            accepted_outcome=None,
            summary=None,
        )
        second_cohort = second["result"]["cohort_id"]
        self.assertNotEqual(first_cohort, second_cohort)
        self.assertEqual(second["status"]["finding_count"], 0)
        self.assertEqual(len(second["status"]["active"]), 2)

        second_frozen = release_cohort.freeze(
            self.workspace,
            expected=second["status"]["state_token"],
            project_binding=self.binding,
            content_commitish="HEAD",
        )
        subprocess.run(["git", "tag", "v1.2.0", second_frozen["result"]["content_commit"]], cwd=self.workspace, check=True)
        release_cohort.record_release(
            self.workspace,
            expected=release_cohort.status(self.workspace)["state_token"],
            project_binding=self.binding,
            tag="v1.2.0",
            evidence="https://example.invalid/releases/v1.2.0",
        )
        both_pending = release_cohort.status(self.workspace)
        with self.assertRaisesRegex(release_cohort.ReleaseCohortError, "specify --cohort-id"):
            release_cohort.finalize(
                self.workspace,
                expected=both_pending["state_token"],
                project_binding=self.binding,
                authorization="fixture",
            )

        self._close_cycle(ids["milestone-two_cycle"])
        self._close_cycle(ids["parent_cycle"])
        for cohort_id in (first_cohort, second_cohort):
            current = release_cohort.status(self.workspace)
            release_cohort.finalize(
                self.workspace,
                expected=current["state_token"],
                project_binding=self.binding,
                authorization="fixture",
                cohort_id=cohort_id,
            )
        self.assertEqual(release_cohort.status(self.workspace)["active"], [])


if __name__ == "__main__":
    unittest.main()
