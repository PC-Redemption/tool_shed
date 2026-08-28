from __future__ import annotations

import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import maintainer_hybrid_conversion as conversion


class MaintainerHybridConversionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name) / "workspace"
        self.workspace.mkdir()
        subprocess.run(["git", "init", "--quiet"], cwd=self.workspace, check=True)
        subprocess.run(["git", "config", "user.name", "Tool Shed Tests"], cwd=self.workspace, check=True)
        subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=self.workspace, check=True)
        self.project_id = str(uuid.uuid4())
        files = {
            ".gitignore": "/.tool-shed/\n/cache/\n",
            "work/tool-shed-project.json": json.dumps(
                {"schema_version": 1, "project_id": self.project_id, "project_name": "fixture"},
                indent=2,
                sort_keys=True,
            )
            + "\n",
            conversion.ASSIGNED_IDS.as_posix(): json.dumps(
                {
                    "schema_version": 1,
                    "kind": "tool-shed-maintainer-assigned-ids",
                    "project_id": self.project_id,
                    "sources": [
                        {
                            "path": "work/source.md",
                            "artifact_id": str(uuid.uuid4()),
                            "import_id": str(uuid.uuid4()),
                        }
                    ],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            "work/source.md": "# Source\n\nRetained bytes.\n",
        }
        for relative, content in files.items():
            path = self.workspace / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.workspace, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "fixture"], cwd=self.workspace, check=True)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_inventory_archive_verification_and_restore_cover_git_states(self) -> None:
        ignored = self.workspace / "cache/generated.bin"
        ignored.parent.mkdir()
        ignored.write_bytes(b"ignored bytes")
        untracked = self.workspace / "owner-note.txt"
        untracked.write_text("untracked owner bytes\n", encoding="utf-8")
        inventory = conversion.build_inventory(self.workspace)
        self.assertEqual(inventory["counts"]["untracked"], 1)
        self.assertEqual(inventory["counts"]["ignored"], 1)
        with self.assertRaisesRegex(conversion.ConversionError, "clean tracked and untracked"):
            conversion.create_archive(self.workspace, Path(self.temporary.name) / "refused.tar.gz")
        subprocess.run(["git", "add", "owner-note.txt"], cwd=self.workspace, check=True)
        subprocess.run(["git", "commit", "--quiet", "-m", "retain note"], cwd=self.workspace, check=True)
        archive = Path(self.temporary.name) / "conversion.tar.gz"
        result = conversion.create_archive(self.workspace, archive)
        verified = conversion.verify_archive(archive)
        self.assertEqual(result["archive_sha256"], verified["archive_sha256"])
        self.assertTrue(verified["valid"])
        with tarfile.open(archive, "r:gz") as handle:
            self.assertIn("cache/generated.bin", handle.getnames())
        restored = Path(self.temporary.name) / "restored"
        conversion.restore_archive(archive, restored)
        self.assertEqual((restored / "cache/generated.bin").read_bytes(), b"ignored bytes")
        self.assertEqual((restored / "owner-note.txt").read_text(), "untracked owner bytes\n")

    def test_archive_outputs_must_be_external(self) -> None:
        with self.assertRaisesRegex(conversion.ConversionError, "outside"):
            conversion.require_external_path(self.workspace, self.workspace / "archive.tar.gz")


if __name__ == "__main__":
    unittest.main()
