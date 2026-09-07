from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from scripts.bounded_workspace_writer import (
    BoundedWorkspaceWriteError,
    BoundedWorkspaceWriter,
)


def call(writer: BoundedWorkspaceWriter, path: str, digest: str, content: str):
    return writer.handle(
        {
            "tool": BoundedWorkspaceWriter.TOOL_NAME,
            "arguments": {
                "path": path,
                "expected_sha256": digest,
                "content": content,
            },
        }
    )


class BoundedWorkspaceWriterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_replaces_one_exact_digest_bound_file_and_preserves_mode(self) -> None:
        target = self.root / "target.txt"
        target.write_text("before\n", encoding="utf-8")
        target.chmod(0o640)
        writer = BoundedWorkspaceWriter(self.root, (Path("target.txt"),))
        digest = hashlib.sha256(b"before\n").hexdigest()

        result = call(writer, "target.txt", digest, "after\n")

        self.assertTrue(result["success"])
        self.assertEqual("after\n", target.read_text(encoding="utf-8"))
        self.assertEqual(0o640, target.stat().st_mode & 0o777)
        self.assertEqual(1, writer.mutation_count)
        self.assertEqual("written", writer.evidence[0]["status"])
        self.assertNotIn("after", str(writer.evidence))

    def test_creates_only_a_declared_file_with_an_existing_parent(self) -> None:
        writer = BoundedWorkspaceWriter(self.root, (Path("new.txt"),))

        result = call(writer, "new.txt", "absent", "created\n")

        self.assertTrue(result["success"])
        self.assertEqual("created\n", (self.root / "new.txt").read_text(encoding="utf-8"))

    def test_refuses_outside_stale_oversize_and_second_mutations(self) -> None:
        target = self.root / "target.txt"
        target.write_text("before\n", encoding="utf-8")
        writer = BoundedWorkspaceWriter(
            self.root, (Path("target.txt"),), max_write_bytes=8
        )
        digest = hashlib.sha256(b"before\n").hexdigest()

        self.assertFalse(call(writer, "../outside.txt", "absent", "x")["success"])
        self.assertFalse(call(writer, "target.txt", digest, "123456789")["success"])
        target.write_text("controller\n", encoding="utf-8")
        self.assertFalse(call(writer, "target.txt", digest, "worker\n")["success"])

        replay = BoundedWorkspaceWriter(self.root, (Path("target.txt"),))
        current = hashlib.sha256(b"controller\n").hexdigest()
        self.assertTrue(call(replay, "target.txt", current, "first\n")["success"])
        self.assertFalse(call(replay, "target.txt", current, "second\n")["success"])
        self.assertEqual("first\n", target.read_text(encoding="utf-8"))

    @unittest.skipIf(os.name == "nt", "creating a test symlink may require Windows elevation")
    def test_refuses_symlinked_targets_at_boundary_creation(self) -> None:
        outside = self.root.parent / f"{self.root.name}-outside.txt"
        outside.write_text("keep\n", encoding="utf-8")
        try:
            (self.root / "link.txt").symlink_to(outside)
            with self.assertRaises(BoundedWorkspaceWriteError):
                BoundedWorkspaceWriter(self.root, (Path("link.txt"),))
            self.assertEqual("keep\n", outside.read_text(encoding="utf-8"))
        finally:
            outside.unlink(missing_ok=True)

    def test_dynamic_schema_exposes_only_allowlisted_paths(self) -> None:
        (self.root / "b.txt").write_text("b", encoding="utf-8")
        writer = BoundedWorkspaceWriter(
            self.root, (Path("b.txt"), Path("a.txt"))
        )

        schema = writer.dynamic_tools[0]

        self.assertEqual("write_workspace_file", schema["name"])
        self.assertEqual(
            ["a.txt", "b.txt"], schema["inputSchema"]["properties"]["path"]["enum"]
        )
        self.assertFalse(schema["inputSchema"]["additionalProperties"])


if __name__ == "__main__":
    unittest.main()
