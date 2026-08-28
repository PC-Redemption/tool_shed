from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import update_snapshot  # noqa: E402


class Protocol4UpdaterTests(unittest.TestCase):
    def test_protocol3_refuses_protocol4_release_before_mutation(self) -> None:
        with self.assertRaisesRegex(
            update_snapshot.UpdateError,
            "requires updater protocol 4, but this updater supports protocol 3",
        ):
            update_snapshot.require_supported_updater_protocol(
                {"minimum_updater_protocol": 4},
                supported_protocol=3,
            )

    def test_protocol4_accepts_protocol4_release(self) -> None:
        self.assertEqual(
            update_snapshot.require_supported_updater_protocol(
                {"minimum_updater_protocol": 4},
                supported_protocol=4,
            ),
            4,
        )


if __name__ == "__main__":
    unittest.main()
