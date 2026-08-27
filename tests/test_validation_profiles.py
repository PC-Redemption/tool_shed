from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import validate_tool_shed as validator


class ValidationProfileTests(unittest.TestCase):
    def test_profiles_assign_tests_and_steps_without_repetition(self) -> None:
        discovered = [
            "test_scripts.ScriptTests.test_example",
            "test_validation_profiles.ValidationProfileTests.test_example",
        ]

        self.assertEqual(validator.select_test_ids("full", discovered), discovered)
        self.assertEqual(validator.select_test_ids("release", discovered), discovered)
        self.assertEqual(
            validator.select_test_ids("focused", discovered),
            ["test_validation_profiles.ValidationProfileTests.test_example"],
        )
        self.assertEqual(
            validator.select_test_ids("focused", [discovered[0]]),
            [discovered[0]],
        )

        focused = validator.profile_step_names("focused", canonical=True)
        full = validator.profile_step_names("full", canonical=True)
        release = validator.profile_step_names("release", canonical=True)
        for steps in (focused, full, release):
            self.assertEqual(len(steps), len(set(steps)))
        self.assertNotIn("smoke_temp_workspace", focused)
        self.assertNotIn("smoke_temp_workspace", full)
        self.assertEqual(set(release) - set(full), {"smoke_temp_workspace"})
        self.assertEqual(validator.parse_args([]).profile, "full")

    def test_isolated_runner_collects_every_result_in_stable_order(self) -> None:
        calls: list[str] = []

        def fake_run(test_id: str, state_root: Path) -> validator.TestResult:
            calls.append(test_id)
            return validator.TestResult(test_id, int(test_id == "test_z"), 0.01, "", "")

        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(
            validator,
            "_run_test_case",
            side_effect=fake_run,
        ):
            results = validator.execute_test_cases(
                ["test_z", "test_a"],
                jobs=2,
                state_root=Path(temporary),
            )

        self.assertEqual(set(calls), {"test_a", "test_z"})
        self.assertEqual([item.test_id for item in results], ["test_a", "test_z"])
        self.assertEqual([item.returncode for item in results], [0, 1])


if __name__ == "__main__":
    unittest.main()
