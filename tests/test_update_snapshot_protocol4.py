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

    def test_post_install_doctor_accepts_only_new_declared_campaign_projections(self) -> None:
        doctor = {
            "verdict": "INVALID",
            "findings": [{"code": "DIRTY_CAMPAIGN_STATE"}],
        }
        paths = {
            "work/00-campaigns/active-queue.md",
            "work/00-campaigns/completed-queue.md",
        }
        result = update_snapshot.qualify_post_install_doctor(
            doctor,
            campaign_dirty_before=set(),
            campaign_dirty_after=paths,
            allowed_campaign_mutations=paths,
        )
        self.assertEqual(result["reason"], "exact-updater-created-campaign-projections")
        self.assertEqual(result["paths"], sorted(paths))

        for before, after, allowed in (
            ({"work/00-campaigns/active-queue.md"}, paths, paths),
            (set(), paths | {"work/00-campaigns/active/001-owner.md"}, paths),
        ):
            with self.assertRaisesRegex(update_snapshot.UpdateError, "doctor reported INVALID"):
                update_snapshot.qualify_post_install_doctor(
                    doctor,
                    campaign_dirty_before=before,
                    campaign_dirty_after=after,
                    allowed_campaign_mutations=allowed,
                )

        with self.assertRaisesRegex(update_snapshot.UpdateError, "doctor reported INVALID"):
            update_snapshot.qualify_post_install_doctor(
                {"verdict": "INVALID", "findings": [{"code": "WORK_INDEX_STALE"}]},
                campaign_dirty_before=set(),
                campaign_dirty_after=paths,
                allowed_campaign_mutations=paths,
            )


if __name__ == "__main__":
    unittest.main()
