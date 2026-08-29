from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


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

    def test_schema2_preflight_rebuilds_both_recovery_checkpoints(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            database = workspace / ".tool-shed/state.sqlite3"
            database.parent.mkdir(parents=True)
            database.write_bytes(b"live")
            checkpoints = workspace / "work/state/checkpoints"
            checkpoints.mkdir(parents=True)
            (checkpoints / "state-v1.json").write_text("{}\n", encoding="utf-8")
            (checkpoints / "state-v2.json").write_text("{}\n", encoding="utf-8")
            audit = {
                "classification": "CLEAN",
                "schema_version": 2,
                "domain_digest": "current-domain",
            }
            backup = {"backup": ".tool-shed/backup.sqlite3"}
            legacy = {"domain_digest": "legacy-domain"}
            current = {"domain_digest": "current-domain"}
            with (
                mock.patch.object(update_snapshot, "binding_token", return_value="binding"),
                mock.patch.object(
                    update_snapshot,
                    "protocol4_hybrid_audit",
                    side_effect=[audit, audit],
                ),
                mock.patch.object(
                    update_snapshot,
                    "_protocol4_hybrid_command",
                    side_effect=[backup, legacy],
                ) as hybrid_command,
                mock.patch.object(
                    update_snapshot,
                    "_protocol4_document_command",
                    return_value=current,
                ) as document_command,
            ):
                result = update_snapshot.protocol4_hybrid_preflight(
                    workspace,
                    workspace / "snapshot",
                    timeout=60,
                )

            self.assertEqual(hybrid_command.call_count, 2)
            document_command.assert_called_once()
            self.assertEqual(result["shadow_rebuild"], current)
            self.assertEqual(result["recovery_rebuilds"]["state_v1"], legacy)
            self.assertEqual(result["recovery_rebuilds"]["state_v2"], current)

    def test_schema2_preflight_requires_document_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            database = workspace / ".tool-shed/state.sqlite3"
            database.parent.mkdir(parents=True)
            database.write_bytes(b"live")
            checkpoint = workspace / "work/state/checkpoints/state-v1.json"
            checkpoint.parent.mkdir(parents=True)
            checkpoint.write_text("{}\n", encoding="utf-8")
            audit = {
                "classification": "CLEAN",
                "schema_version": 2,
                "domain_digest": "current-domain",
            }
            with (
                mock.patch.object(update_snapshot, "binding_token", return_value="binding"),
                mock.patch.object(
                    update_snapshot,
                    "protocol4_hybrid_audit",
                    side_effect=[audit, audit],
                ),
                mock.patch.object(
                    update_snapshot,
                    "_protocol4_hybrid_command",
                    side_effect=[{"backup": ".tool-shed/backup.sqlite3"}, {"domain_digest": "legacy"}],
                ),
            ):
                with self.assertRaisesRegex(update_snapshot.UpdateError, "state-v2 checkpoint"):
                    update_snapshot.protocol4_hybrid_preflight(
                        workspace,
                        workspace / "snapshot",
                        timeout=60,
                    )


if __name__ == "__main__":
    unittest.main()
