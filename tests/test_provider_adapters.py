"""Tests for provider-adapter manifest path validation."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.provider_adapters import AdapterManifestError, _safe_relative_path


class SafeRelativePathTests(unittest.TestCase):
    def test_accepts_posix_repository_relative_paths(self) -> None:
        for value, expected in (
            ("instructions/marshal.md", "instructions/marshal.md"),
            ("providers/cursor/adapter.mdc", "providers/cursor/adapter.mdc"),
            ("./providers/codex.md", "./providers/codex.md"),
        ):
            with self.subTest(value=value):
                self.assertEqual(_safe_relative_path(value, field="path"), expected)

    def test_rejects_unsafe_or_non_meaningful_paths(self) -> None:
        invalid_paths = (
            "",
            ".",
            "./",
            "././",
            "../adapter.md",
            "providers/../adapter.md",
            r"..\adapter.md",
            r"providers\..\adapter.md",
            "/etc/adapter.md",
            "C:/adapters/adapter.md",
            r"C:\adapters\adapter.md",
            "//server/share/adapter.md",
            r"\\server\share\adapter.md",
            r"providers\adapter.md",
        )
        for value in invalid_paths:
            with self.subTest(value=value):
                with self.assertRaises(AdapterManifestError):
                    _safe_relative_path(value, field="path")


if __name__ == "__main__":
    unittest.main()
