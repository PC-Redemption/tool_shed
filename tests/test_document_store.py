from __future__ import annotations

import contextlib
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import document_store  # noqa: E402
import hybrid_state  # noqa: E402


def binding(workspace: Path) -> str:
    project_id = json.loads((workspace / "work/tool-shed-project.json").read_text(encoding="utf-8"))["project_id"]
    digest = hashlib.sha256()
    for value in ("tool-shed-binding-v1", project_id, str(workspace.resolve()), "hybrid-state"):
        digest.update(value.encode())
        digest.update(b"\0")
    return digest.hexdigest()[:24]


class DocumentStoreThinSliceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        subprocess.run(["git", "init", "--quiet"], cwd=self.workspace, check=True)
        subprocess.run(["git", "config", "user.name", "Tool Shed Tests"], cwd=self.workspace, check=True)
        subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=self.workspace, check=True)
        files = {
            ".gitignore": "/.tool-shed/\n",
            "work/tool-shed-project.json": json.dumps({"schema_version": 1, "project_id": str(uuid.uuid4()), "project_name": "document-fixture"}, indent=2) + "\n",
            "work/ideas/idea-one.md": "# Idea One\n\nOriginal idea bytes.\n",
            "work/maps/map-one.md": "# Map One\n\nOriginal map bytes.\n",
        }
        for relative, content in files.items():
            path = self.workspace / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.workspace, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "fixture"], cwd=self.workspace, check=True)
        self.binding = binding(self.workspace)
        self.database = self.workspace / ".tool-shed/state.sqlite3"
        hybrid_state.initialize(self.workspace, project_binding=self.binding, target=self.database)
        document_store.migrate(self.workspace, project_binding=self.binding, database=self.database)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_create_document_normalizes_workspace_before_preferred_alias(self) -> None:
        presented_workspace = self.workspace / "presentation-alias"
        original_require = document_store.require_path_within

        def canonical_require(root: Path, candidate: Path) -> Path:
            if candidate.as_posix().endswith("work/evidence/canonical-alias.md"):
                return self.workspace / "work/evidence/canonical-alias.md"
            return original_require(root, candidate)

        with (
            mock.patch.object(document_store, "resolved_workspace", return_value=self.workspace),
            mock.patch.object(document_store, "require_path_within", side_effect=canonical_require),
        ):
            created = document_store.create_document(
                presented_workspace,
                project_binding=self.binding,
                document_type="evidence-summary",
                title="Canonical alias",
                body="# Canonical alias\n",
                lifecycle="completed",
                metadata={},
                actor="fixture",
                reason="prove canonical workspace-relative alias",
                preferred_path="work/evidence/canonical-alias.md",
                database=self.database,
            )["result"]

        aliases = document_store.resolve(
            self.workspace, created["visible_id"], database=self.database
        )["aliases"]
        self.assertEqual(aliases[0]["path"], "work/evidence/canonical-alias.md")

    def test_managed_writes_reuse_physical_audit_only_while_database_is_unchanged(self) -> None:
        hybrid_state._PHYSICAL_AUDIT_CACHE.pop(str(self.database.resolve()), None)
        document_store._MANAGED_AUDIT_CACHE.pop(
            (str(self.workspace), str(self.database)), None
        )
        original = hybrid_state.integrity_check
        with (
            mock.patch.object(hybrid_state, "integrity_check", wraps=original) as checked,
            mock.patch("dashboard_reporter.enqueue_if_connected"),
        ):
            for index in range(2):
                document_store.create_document(
                    self.workspace,
                    project_binding=self.binding,
                    document_type="ticket",
                    title=f"Cached audit {index}",
                    body=f"# Cached audit {index}\n",
                    lifecycle="active",
                    metadata={},
                    actor="fixture",
                    reason="physical audit cache qualification",
                    database=self.database,
                )
            hybrid_state.managed_write(
                self.workspace,
                project_binding=self.binding,
                command="shared-physical-audit-cache-probe",
                actor="fixture",
                callback=lambda _connection, revision: {"revision": revision},
                expected_writes=0,
                path=self.database,
            )
            self.assertEqual(
                hybrid_state.audit(self.workspace, self.database)["classification"],
                "VALID_DIRTY",
            )
            self.assertEqual(checked.call_count, 1)

            stat = self.database.stat()
            os.utime(
                self.database,
                ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000),
            )
            document_store.create_document(
                self.workspace,
                project_binding=self.binding,
                document_type="ticket",
                title="Invalidated audit",
                body="# Invalidated audit\n",
                lifecycle="active",
                metadata={},
                actor="fixture",
                reason="database signature invalidates cache",
                database=self.database,
            )
            self.assertEqual(checked.call_count, 2)

    def test_managed_write_reuses_its_sealing_domain_digest_for_exit_audit(self) -> None:
        with mock.patch("dashboard_reporter.enqueue_if_connected"):
            document_store.create_document(
                self.workspace,
                project_binding=self.binding,
                document_type="ticket",
                title="Warm managed audit cache",
                body="# Warm managed audit cache\n",
                lifecycle="active",
                metadata={},
                actor="fixture",
                reason="prepare managed audit cache",
                database=self.database,
            )
            original = document_store.domain_digest
            with mock.patch.object(document_store, "domain_digest", wraps=original) as digested:
                document_store.create_document(
                    self.workspace,
                    project_binding=self.binding,
                    document_type="ticket",
                    title="Single digest write",
                    body="# Single digest write\n",
                    lifecycle="active",
                    metadata={},
                    actor="fixture",
                    reason="prove one full semantic scan per managed write",
                    database=self.database,
                )
            self.assertEqual(digested.call_count, 1)

    def test_transactional_edit_relationship_checkpoint_rebuild_and_outcome(self) -> None:
        originals = {path: (self.workspace / path).read_bytes() for path in ("work/ideas/idea-one.md", "work/maps/map-one.md")}
        idea = document_store.import_document(
            self.workspace, project_binding=self.binding, source=Path("work/ideas/idea-one.md"),
            document_type="idea-brief", lifecycle="active", actor="fixture", reason="thin slice", database=self.database,
        )["result"]
        project_map = document_store.import_document(
            self.workspace, project_binding=self.binding, source=Path("work/maps/map-one.md"),
            document_type="project-map", lifecycle="working", actor="fixture", reason="thin slice", database=self.database,
        )["result"]
        self.assertEqual(idea["visible_id"], "IDEA-0001")
        self.assertEqual(project_map["visible_id"], "MAP-0001")
        self.assertFalse(idea["idempotent"])
        revision_before_repeat = document_store.audit(self.workspace, self.database)["current_revision"]
        repeated = document_store.import_document(
            self.workspace, project_binding=self.binding, source=Path("work/ideas/idea-one.md"),
            document_type="idea-brief", lifecycle="active", actor="fixture", reason="repeat", database=self.database,
        )["result"]
        self.assertTrue(repeated["idempotent"])
        self.assertEqual(document_store.audit(self.workspace, self.database)["current_revision"], revision_before_repeat)

        edit_path = Path(".tool-shed/idea-edit.md")
        document_store.export_edit(self.workspace, idea["visible_id"], edit_path, database=self.database)
        absolute_edit = self.workspace / edit_path
        exported = absolute_edit.read_text(encoding="utf-8")
        absolute_edit.write_text(exported.replace("Original idea bytes.", "Revised database-owned body."), encoding="utf-8")
        applied = document_store.apply_edit(
            self.workspace, project_binding=self.binding, edit=edit_path, actor="fixture", reason="prove revision fence", database=self.database,
        )
        self.assertEqual(applied["result"]["document_revision"], 2)
        shown = document_store.show(self.workspace, idea["artifact_id"], database=self.database)
        self.assertIn("Revised database-owned body.", shown["body_markdown"])
        self.assertEqual(len(document_store.history(self.workspace, idea["visible_id"], database=self.database)["revisions"]), 2)
        self.assertIn("Revised database-owned body.", document_store.diff_revisions(self.workspace, idea["visible_id"], 1, 2, database=self.database)["diff"])
        with self.assertRaisesRegex(document_store.DocumentStoreError, "stale document revision"):
            document_store.apply_edit(self.workspace, project_binding=self.binding, edit=edit_path, actor="fixture", reason="stale", database=self.database)

        relationship = document_store.relate(
            self.workspace, project_binding=self.binding, source=idea["visible_id"], relation="produces",
            target=project_map["visible_id"], actor="fixture", database=self.database,
        )
        relationship_revision = document_store.audit(self.workspace, self.database)["current_revision"]
        repeated_relationship = document_store.relate(
            self.workspace, project_binding=self.binding, source=idea["visible_id"], relation="produces",
            target=project_map["visible_id"], actor="fixture", database=self.database,
        )
        self.assertFalse(repeated_relationship["writes_performed"])
        self.assertTrue(repeated_relationship["result"]["idempotent"])
        self.assertEqual(
            repeated_relationship["result"]["relationship_id"],
            relationship["result"]["relationship_id"],
        )
        self.assertEqual(
            document_store.audit(self.workspace, self.database)["current_revision"],
            relationship_revision,
        )
        relations = document_store.related(self.workspace, idea["visible_id"], database=self.database)["relationships"]
        self.assertEqual(len(relations), 1)
        self.assertEqual(relations[0]["to_visible_id"], "MAP-0001")
        outcome = document_store.open_outcome(
            self.workspace, project_binding=self.binding, identity=idea["visible_id"],
            accepted_outcome="Prove database-owned revision and reconciliation propagation.", actor="fixture", database=self.database,
        )["result"]
        self.assertEqual((outcome["lifecycle"], outcome["verdict"], outcome["reconciliation"]), ("working", "open", "open"))

        checkpoint = document_store.write_checkpoint(
            self.workspace, project_binding=self.binding, output=Path("work/state/checkpoints/thin-v2.json"), database=self.database,
        )
        self.assertTrue(checkpoint["objects"])
        rebuilt_path = Path(".tool-shed/rebuilt-v2.sqlite3")
        trusted_schema_during_create: list[int] = []
        create_schema = hybrid_state.create_schema

        def observe_trusted_schema(connection: sqlite3.Connection, *, include_triggers: bool = True) -> None:
            trusted_schema_during_create.append(int(connection.execute("PRAGMA trusted_schema").fetchone()[0]))
            create_schema(connection, include_triggers=include_triggers)

        with mock.patch.object(hybrid_state, "create_schema", side_effect=observe_trusted_schema):
            rebuilt = document_store.rebuild(
                self.workspace, project_binding=self.binding, checkpoint=Path(checkpoint["path"]), output=rebuilt_path,
            )
        self.assertEqual(trusted_schema_during_create, [1])
        self.assertEqual(rebuilt["domain_digest"], document_store.audit(self.workspace, self.database)["domain_digest"])
        self.assertEqual(document_store.show(self.workspace, idea["visible_id"], database=self.workspace / rebuilt_path)["body_markdown"], shown["body_markdown"])

        class LegacyJsonConnection:
            def __init__(self, connection: sqlite3.Connection) -> None:
                self.connection = connection
                self.statements: list[str] = []

            def execute(self, statement: str, *args: object) -> object:
                self.statements.append(statement)
                if statement == "PRAGMA function_list":
                    return [("json_valid", 1, "s", "utf8", 1, 2048)]
                return self.connection.execute(statement, *args)

        with contextlib.closing(hybrid_state.connect(self.workspace / rebuilt_path, writable=False)) as connection:
            legacy = LegacyJsonConnection(connection)
            legacy_audit = document_store.audit_connection(self.workspace, legacy)  # type: ignore[arg-type]
            self.assertEqual(legacy_audit["classification"], "CLEAN")
            self.assertIn("PRAGMA trusted_schema=ON", legacy.statements)
            self.assertEqual(int(connection.execute("PRAGMA trusted_schema").fetchone()[0]), 0)

        for relative, content in originals.items():
            self.assertEqual((self.workspace / relative).read_bytes(), content)

    def test_direct_sql_sets_unmanaged_review(self) -> None:
        imported = document_store.import_document(
            self.workspace, project_binding=self.binding, source=Path("work/ideas/idea-one.md"),
            document_type="idea-brief", lifecycle="active", actor="fixture", reason="thin slice", database=self.database,
        )["result"]
        with contextlib.closing(sqlite3.connect(self.database)) as connection:
            connection.execute("UPDATE document SET title='Direct SQL' WHERE id=?", (imported["artifact_id"],))
            connection.commit()
        result = document_store.audit(self.workspace, self.database)
        self.assertEqual(result["classification"], "UNMANAGED_REVIEW")
        self.assertTrue(result["unmanaged_write_detected"])

    def test_audit_rejects_duplicate_active_relationship_edges(self) -> None:
        first = document_store.create_document(
            self.workspace, project_binding=self.binding, document_type="ticket", title="First",
            body="# First\n", lifecycle="active", metadata={}, actor="fixture", reason="audit",
            database=self.database,
        )["result"]
        second = document_store.create_document(
            self.workspace, project_binding=self.binding, document_type="checklist", title="Second",
            body="# Second\n", lifecycle="active", metadata={}, actor="fixture", reason="audit",
            database=self.database,
        )["result"]
        document_store.relate(
            self.workspace, project_binding=self.binding, source=first["visible_id"], relation="verified-by",
            target=second["visible_id"], actor="fixture", database=self.database,
        )
        with contextlib.closing(sqlite3.connect(self.database)) as connection:
            connection.execute(
                "INSERT INTO relationship VALUES (?, ?, 'verified-by', ?, 'direct-sql', 3, NULL)",
                (str(uuid.uuid4()), first["artifact_id"], second["artifact_id"]),
            )
            connection.commit()
        result = document_store.audit(self.workspace, self.database)
        self.assertEqual(result["classification"], "INVALID")
        self.assertIn("duplicate active relationship edges: 1", result["findings"])

    def test_semantic_audit_reports_promoted_missing_outcome_and_type_drift(self) -> None:
        idea = document_store.create_document(
            self.workspace, project_binding=self.binding, document_type="idea-brief", title="Promoted idea",
            body="# Promoted idea\n\nStatus: promoted\nType: idea-brief\n", lifecycle="active",
            metadata={"document_type": "idea-brief"}, actor="fixture", reason="semantic audit",
            database=self.database,
        )["result"]
        def introduce_type_drift(connection: sqlite3.Connection, revision: int) -> dict[str, object]:
            connection.execute("UPDATE artifact SET type='document' WHERE id=?", (idea["artifact_id"],))
            return {"artifact_id": idea["artifact_id"], "revision": revision}

        document_store.managed_write(
            self.workspace, project_binding=self.binding, command="fixture-type-drift",
            actor="fixture", callback=introduce_type_drift, database=self.database,
        )
        result = document_store.audit(self.workspace, self.database)
        self.assertEqual(result["classification"], "VALID_DIRTY")
        self.assertEqual(
            {item["code"] for item in result["semantic_findings"]},
            {"DOCUMENT_TYPE_DRIFT", "PROMOTED_IDEA_MISSING_OUTCOME"},
        )
        listed = document_store.list_documents(
            self.workspace, document_type="idea-brief", database=self.database
        )["documents"]
        self.assertEqual(listed[0]["visible_id"], idea["visible_id"])
        self.assertEqual(listed[0]["type"], "idea-brief")
        self.assertEqual(listed[0]["stored_type"], "document")
        corrected = document_store.set_type(
            self.workspace, project_binding=self.binding, identity=idea["visible_id"],
            document_type="idea-brief", expected_revision=1, actor="fixture", reason="repair type",
            database=self.database,
        )["result"]
        self.assertFalse(corrected["idempotent"])
        self.assertNotIn(
            "DOCUMENT_TYPE_DRIFT",
            {item["code"] for item in document_store.audit(self.workspace, self.database)["semantic_findings"]},
        )

    def test_complete_outcome_updates_document_body_cycle_and_reconciliation_atomically(self) -> None:
        campaign = document_store.create_document(
            self.workspace,
            project_binding=self.binding,
            document_type="campaign",
            title="Atomic completion",
            body="# Atomic completion\n\nStatus: working\n",
            lifecycle="active",
            metadata={"document_type": "campaign"},
            actor="fixture",
            reason="atomic completion fixture",
            database=self.database,
        )["result"]
        cycle = document_store.open_outcome(
            self.workspace,
            project_binding=self.binding,
            identity=campaign["visible_id"],
            accepted_outcome="The campaign completes coherently.",
            actor="fixture",
            database=self.database,
        )["result"]["cycle_id"]
        completed = document_store.complete_outcome(
            self.workspace,
            project_binding=self.binding,
            identity=campaign["visible_id"],
            expected_revision=1,
            disposition="satisfied",
            summary="Atomic completion verified.",
            authorization="fixture",
            actor="fixture",
            database=self.database,
        )["result"]
        self.assertEqual(completed["cycle_id"], cycle)
        shown = document_store.show(self.workspace, campaign["visible_id"], database=self.database)
        self.assertEqual(shown["lifecycle"], "completed")
        self.assertIn("Status: completed", shown["body_markdown"])
        with contextlib.closing(hybrid_state.connect(self.database, writable=False)) as connection:
            row = connection.execute(
                "SELECT c.lifecycle_state, r.state, v.disposition FROM cycle c "
                "JOIN reconciliation r ON r.cycle_id=c.id AND r.origin_revision=("
                "SELECT MAX(r2.origin_revision) FROM reconciliation r2 WHERE r2.cycle_id=c.id) "
                "JOIN outcome_verdict v ON v.id=r.verdict_id WHERE c.id=?",
                (cycle,),
            ).fetchone()
        self.assertEqual(tuple(row), ("terminal", "reconciled", "satisfied"))

    def test_bounded_interface_and_disposable_lifecycle_views(self) -> None:
        first = document_store.create_document(
            self.workspace, project_binding=self.binding, document_type="ticket", title="Repair compact context",
            body="# Repair compact context\n\nUnique search marker alpha.\n", lifecycle="active",
            metadata={"priority": "high"}, actor="fixture", reason="interface proof", database=self.database,
        )["result"]
        second = document_store.create_document(
            self.workspace, project_binding=self.binding, document_type="checklist", title="Verify compact context",
            body="# Verify compact context\n\nRelated body beta.\n", lifecycle="working",
            metadata={}, actor="fixture", reason="interface proof", database=self.database,
        )["result"]
        relationship = document_store.relate(
            self.workspace, project_binding=self.binding, source=first["visible_id"], relation="verified-by",
            target=second["visible_id"], actor="fixture", database=self.database,
        )["result"]
        self.assertEqual(document_store.list_documents(self.workspace, lifecycle="active", database=self.database)["documents"][0]["visible_id"], first["visible_id"])
        self.assertEqual(document_store.search(self.workspace, "unique search marker", database=self.database)["documents"][0]["visible_id"], first["visible_id"])
        self.assertEqual(document_store.resolve(self.workspace, first["visible_id"], database=self.database)["artifact_id"], first["artifact_id"])
        capsule = document_store.context_capsule(self.workspace, first["visible_id"], byte_budget=512, database=self.database)
        self.assertEqual(capsule["documents"][0]["visible_id"], first["visible_id"])
        self.assertIn(second["visible_id"], capsule["omitted_ids"])
        moved = document_store.set_lifecycle(
            self.workspace, project_binding=self.binding, identity=first["visible_id"], lifecycle="completed",
            expected_revision=1, actor="fixture", reason="qualified", database=self.database,
        )["result"]
        self.assertEqual(moved["document_revision"], 2)
        self.assertIn(
            "Status: completed",
            document_store.show(self.workspace, first["visible_id"], database=self.database)["body_markdown"],
        )
        rendered = document_store.render_views(self.workspace, database=self.database)
        view_root = self.workspace / rendered["path"]
        first_render = sorted((view_root / "completed").glob("TKT-*.md"))[0].read_bytes()
        self.assertIn(first["visible_id"].encode(), first_render)
        (view_root / "completed" / "manual-noise.md").write_text("noise", encoding="utf-8")
        document_store.render_views(self.workspace, database=self.database)
        self.assertFalse((view_root / "completed" / "manual-noise.md").exists())
        self.assertEqual(sorted((view_root / "completed").glob("TKT-*.md"))[0].read_bytes(), first_render)
        document_store.unrelate(
            self.workspace, project_binding=self.binding, relationship_id=relationship["relationship_id"],
            actor="fixture", database=self.database,
        )
        self.assertEqual(document_store.related(self.workspace, first["visible_id"], database=self.database)["relationships"], [])

    def test_database_aware_creation_and_legacy_writer_fences(self) -> None:
        with contextlib.closing(sqlite3.connect(self.database)) as connection:
            connection.execute("UPDATE state_meta SET storage_mode='hybrid' WHERE id=1")
            connection.commit()
        created = subprocess.run(
            [
                sys.executable, str(ROOT / "scripts/new_artifact.py"), "ticket", "Database Native Ticket",
                "--workspace", str(self.workspace), "--project-binding", self.binding,
            ],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
        visible_id = created.stdout.strip()
        self.assertRegex(visible_id, r"^TKT-[0-9]{4,}$")
        self.assertEqual(document_store.show(self.workspace, visible_id, database=self.database)["title"], "Database Native Ticket")
        self.assertFalse((self.workspace / "work/tickets/ticket-database-native-ticket.md").exists())

        for script, command in (("campaign_queue.py", "status"), ("program_roadmap.py", "overview")):
            fenced = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / script), "--workspace", str(self.workspace), command, "--json"],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            )
            self.assertEqual(fenced.returncode, 2)
            self.assertIn("authority is SQLite", fenced.stderr)


if __name__ == "__main__":
    unittest.main()
