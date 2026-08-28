from __future__ import annotations

import contextlib
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import hybrid_state


def project_binding(workspace: Path) -> str:
    project_id = json.loads(
        (workspace / "work" / "tool-shed-project.json").read_text(encoding="utf-8")
    )["project_id"]
    digest = hashlib.sha256()
    for value in ("tool-shed-binding-v1", project_id, str(workspace.resolve()), "hybrid-state"):
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:24]


class HybridStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        self.project_id = str(uuid.uuid4())
        self.prepare_workspace(self.workspace, self.project_id)
        self.binding = project_binding(self.workspace)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def prepare_workspace(self, workspace: Path, project_id: str) -> None:
        subprocess.run(["git", "init", "--quiet"], cwd=workspace, check=True)
        subprocess.run(["git", "config", "user.name", "Tool Shed Tests"], cwd=workspace, check=True)
        subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=workspace, check=True)
        files = {
            ".gitignore": "/.tool-shed/\n",
            "work/tool-shed-project.json": json.dumps(
                {"schema_version": 1, "project_id": project_id, "project_name": "fixture"},
                indent=2,
                sort_keys=True,
            )
            + "\n",
            "work/ideas/idea-one.md": "# Idea One\n\nOriginal bytes.\n",
            "work/maps/map-two.md": "# Map Two\n\nOriginal bytes.\n",
        }
        for relative, content in files.items():
            path = workspace / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=workspace, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "fixture"], cwd=workspace, check=True)

    def initialize(self) -> dict[str, object]:
        return hybrid_state.initialize(self.workspace, project_binding=self.binding)

    def import_pair(self) -> dict[str, object]:
        return hybrid_state.import_files(
            self.workspace,
            [Path("work/ideas/idea-one.md"), Path("work/maps/map-two.md")],
            project_binding=self.binding,
        )

    def test_initialization_freezes_schema_migration_and_clean_lineage(self) -> None:
        result = self.initialize()
        self.assertEqual(result["classification"], "CLEAN")
        database = self.workspace / ".tool-shed" / "state.sqlite3"
        with contextlib.closing(sqlite3.connect(database)) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 1)
            self.assertEqual(connection.execute("PRAGMA application_id").fetchone()[0], 0x54534831)
            self.assertEqual(connection.execute("SELECT count(*) FROM migration_ledger").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT count(*) FROM sqlite_schema WHERE type='trigger'").fetchone()[0], 54)
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
        repeated = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "hybrid_state.py"),
                "--workspace",
                str(self.workspace),
                "init",
                "--project-binding",
                self.binding,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(repeated.returncode, 2)
        self.assertIn("already exists", repeated.stderr)

    def test_managed_import_relationship_and_source_preservation(self) -> None:
        self.initialize()
        originals = {
            path: (self.workspace / path).read_bytes()
            for path in ("work/ideas/idea-one.md", "work/maps/map-two.md")
        }
        imported = self.import_pair()
        self.assertEqual(imported["actual_writes"], 4)
        ids = [item["artifact_id"] for item in imported["result"]]
        self.assertTrue(all(uuid.UUID(item).version == 4 for item in ids))
        related = hybrid_state.add_relationship(
            self.workspace,
            project_binding=self.binding,
            from_artifact_id=ids[0],
            relation_type="produces",
            to_artifact_id=ids[1],
            provenance="fixture",
        )
        self.assertEqual(related["actual_writes"], 1)
        audit = hybrid_state.audit(self.workspace)
        self.assertEqual(audit["classification"], "VALID_DIRTY")
        with contextlib.closing(sqlite3.connect(self.workspace / ".tool-shed/state.sqlite3")) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM artifact").fetchone()[0], 2)
            self.assertEqual(connection.execute("SELECT count(*) FROM import_record").fetchone()[0], 2)
            self.assertEqual(connection.execute("SELECT count(*) FROM relationship").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT count(*) FROM structural_change").fetchone()[0], 5)
            self.assertEqual(connection.execute("SELECT count(*) FROM event").fetchone()[0], 5)
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
            with self.assertRaisesRegex(sqlite3.IntegrityError, "immutable"):
                connection.execute(
                    "UPDATE relationship SET from_artifact_id = ?",
                    (ids[1],),
                )
        for path, content in originals.items():
            self.assertEqual((self.workspace / path).read_bytes(), content)

    def test_assigned_import_ids_and_guarded_hybrid_cutover(self) -> None:
        self.initialize()
        assignments = {
            "work/ideas/idea-one.md": {
                "artifact_id": str(uuid.uuid4()),
                "import_id": str(uuid.uuid4()),
            },
            "work/maps/map-two.md": {
                "artifact_id": str(uuid.uuid4()),
                "import_id": str(uuid.uuid4()),
            },
        }
        imported = hybrid_state.import_files(
            self.workspace,
            [Path(item) for item in assignments],
            project_binding=self.binding,
            assigned_ids=assignments,
        )
        self.assertEqual(
            {item["artifact_id"] for item in imported["result"]},
            {item["artifact_id"] for item in assignments.values()},
        )
        checkpoint = hybrid_state.write_checkpoint(
            self.workspace,
            project_binding=self.binding,
        )
        cutover = hybrid_state.activate_hybrid_mode(
            self.workspace,
            project_binding=self.binding,
            expected_checkpoint_digest=checkpoint["digest"],
        )
        self.assertEqual(cutover["result"]["to"], "hybrid")
        self.assertEqual(hybrid_state.audit(self.workspace)["storage_mode"], "hybrid")
        self.assertFalse(hybrid_state.legacy_write_check(self.workspace, "artifact.id")["allowed"])
        self.assertTrue(hybrid_state.legacy_write_check(self.workspace, "docs.body")["allowed"])
        with self.assertRaisesRegex(hybrid_state.HybridStateError, "requires shadow mode"):
            hybrid_state.activate_hybrid_mode(
                self.workspace,
                project_binding=self.binding,
                expected_checkpoint_digest=checkpoint["digest"],
            )

    def test_unmanaged_write_and_schema_bypass_are_detected(self) -> None:
        self.initialize()
        imported = self.import_pair()
        artifact_id = imported["result"][0]["artifact_id"]
        database = self.workspace / ".tool-shed/state.sqlite3"
        with contextlib.closing(sqlite3.connect(database)) as connection:
            connection.execute(
                "UPDATE artifact SET lifecycle_state = 'changed-directly' WHERE id = ?",
                (artifact_id,),
            )
            connection.commit()
        unmanaged = hybrid_state.audit(self.workspace)
        self.assertEqual(unmanaged["classification"], "UNMANAGED_REVIEW")
        self.assertTrue(unmanaged["unmanaged_write_detected"])

        other = Path(tempfile.mkdtemp(dir=self.workspace.parent))
        try:
            self.prepare_workspace(other, str(uuid.uuid4()))
            hybrid_state.initialize(other, project_binding=project_binding(other))
            with contextlib.closing(sqlite3.connect(other / ".tool-shed/state.sqlite3")) as connection:
                connection.execute("DROP TRIGGER ts_account_artifact_update")
                connection.commit()
            invalid = hybrid_state.audit(other)
            self.assertEqual(invalid["classification"], "INVALID")
            self.assertIn("schema or accounting-trigger digest changed", invalid["findings"])
        finally:
            shutil.rmtree(other)

    def test_corrupt_database_is_refused_without_mutation(self) -> None:
        self.initialize()
        corrupt = self.workspace / ".tool-shed/corrupt.sqlite3"
        shutil.copy2(self.workspace / ".tool-shed/state.sqlite3", corrupt)
        with corrupt.open("r+b") as handle:
            handle.seek(0)
            handle.write(b"corrupt-tool-shed-state")
        before = corrupt.read_bytes()
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "hybrid_state.py"),
                "--workspace",
                str(self.workspace),
                "audit",
                "--database",
                ".tool-shed/corrupt.sqlite3",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Hybrid state operation failed", result.stderr)
        self.assertEqual(corrupt.read_bytes(), before)

    def test_interrupted_managed_write_rolls_back_completely(self) -> None:
        self.initialize()

        def interrupted(connection: sqlite3.Connection, revision: int) -> None:
            stamp = hybrid_state.now()
            connection.execute(
                "INSERT INTO artifact VALUES (?, 'file', NULL, 'work/interrupted.md', 'file', "
                "'imported', ?, ?, ?)",
                (str(uuid.uuid4()), hashlib.sha256(b"x").hexdigest(), stamp, stamp),
            )
            raise RuntimeError("simulated interruption")

        with self.assertRaisesRegex(RuntimeError, "simulated interruption"):
            hybrid_state.managed_write(
                self.workspace,
                project_binding=self.binding,
                command="interrupted-test",
                actor="fixture",
                callback=interrupted,
            )
        audit = hybrid_state.audit(self.workspace)
        self.assertEqual(audit["classification"], "CLEAN")
        self.assertEqual(audit["current_revision"], 0)
        with contextlib.closing(sqlite3.connect(self.workspace / ".tool-shed/state.sqlite3")) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM artifact").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT count(*) FROM managed_operation").fetchone()[0], 0)
        self.assertFalse((self.workspace / ".tool-shed/state.lock").exists())

    def test_checkpoint_and_fresh_rebuild_preserve_semantics(self) -> None:
        self.initialize()
        self.import_pair()
        checkpoint = hybrid_state.write_checkpoint(
            self.workspace,
            project_binding=self.binding,
        )
        self.assertEqual(hybrid_state.audit(self.workspace)["classification"], "CLEAN")
        rebuilt = hybrid_state.rebuild_from_checkpoint(
            self.workspace,
            project_binding=self.binding,
            checkpoint=Path(checkpoint["path"]),
            output=Path(".tool-shed/rebuilt.sqlite3"),
        )
        self.assertEqual(rebuilt["checkpoint_digest"], checkpoint["digest"])
        live = hybrid_state.audit(self.workspace)
        copy_audit = hybrid_state.audit(
            self.workspace, self.workspace / ".tool-shed/rebuilt.sqlite3"
        )
        self.assertEqual(copy_audit["classification"], "CLEAN")
        self.assertEqual(copy_audit["domain_digest"], live["domain_digest"])
        with contextlib.closing(sqlite3.connect(self.workspace / ".tool-shed/state.sqlite3")) as live_db, \
                contextlib.closing(sqlite3.connect(self.workspace / ".tool-shed/rebuilt.sqlite3")) as rebuilt_db:
            live_db.row_factory = sqlite3.Row
            rebuilt_db.row_factory = sqlite3.Row
            for table in hybrid_state.PORTABLE_TABLES:
                if table == "workspace":
                    continue
                self.assertEqual(
                    hybrid_state.table_rows(rebuilt_db, table),
                    hybrid_state.table_rows(live_db, table),
                    table,
                )

        checkpoint_path = self.workspace / checkpoint["path"]
        payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        payload["envelope"]["database_revision"] += 1
        checkpoint_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(hybrid_state.HybridStateError, "checkpoint digest"):
            hybrid_state.rebuild_from_checkpoint(
                self.workspace,
                project_binding=self.binding,
                checkpoint=Path(checkpoint["path"]),
                output=Path(".tool-shed/tampered.sqlite3"),
            )

    def test_backup_retention_lineage_and_legacy_refusal(self) -> None:
        self.initialize()
        for _ in range(4):
            hybrid_state.verified_backup(self.workspace, project_binding=self.binding)
        backups = list((self.workspace / ".tool-shed/backups").glob("*.sqlite3"))
        self.assertEqual(len(backups), 3)
        for backup in backups:
            self.assertEqual(hybrid_state.audit(self.workspace, backup)["classification"], "CLEAN")

        database = self.workspace / ".tool-shed/state.sqlite3"
        with contextlib.closing(sqlite3.connect(database)) as connection:
            connection.execute("UPDATE state_meta SET storage_mode = 'hybrid' WHERE id = 1")
            connection.commit()
        denied = hybrid_state.legacy_write_check(self.workspace, "artifact.id")
        allowed = hybrid_state.legacy_write_check(self.workspace, "docs.body")
        self.assertFalse(denied["allowed"])
        self.assertTrue(allowed["allowed"])

        other = Path(tempfile.mkdtemp(dir=self.workspace.parent))
        try:
            self.prepare_workspace(other, self.project_id)
            (other / ".tool-shed").mkdir()
            shutil.copy2(database, other / ".tool-shed/state.sqlite3")
            foreign = hybrid_state.audit(other)
            self.assertEqual(foreign["classification"], "INVALID")
            self.assertIn("database worktree lineage does not match this workspace", foreign["findings"])
        finally:
            shutil.rmtree(other)


if __name__ == "__main__":
    unittest.main()
