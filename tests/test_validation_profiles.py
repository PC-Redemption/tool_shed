from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

from scripts import benchmark_validation as benchmark
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
        sharded = [
            validator.shard_test_ids(discovered, index, 2)
            for index in range(2)
        ]
        self.assertEqual(sharded, [[discovered[0]], [discovered[1]]])
        self.assertEqual(
            sorted(test_id for shard in sharded for test_id in shard),
            discovered,
        )
        focused = validator.profile_step_names("focused", canonical=True)
        full = validator.profile_step_names("full", canonical=True)
        release = validator.profile_step_names("release", canonical=True)
        for steps in (focused, full, release):
            self.assertEqual(len(steps), len(set(steps)))
        self.assertNotIn("smoke_temp_workspace", focused)
        self.assertNotIn("smoke_temp_workspace", full)
        self.assertIn("validate_bootstrap_closures", full)
        self.assertIn("validate_bootstrap_closures", release)
        self.assertEqual(set(release) - set(full), {"smoke_temp_workspace"})
        self.assertEqual(
            validator.profile_step_names(
                "release", canonical=True, primary_shard=False
            ),
            ("run_unit_tests",),
        )
        self.assertEqual(validator.parse_args([]).profile, "full")
        budgeted = validator.parse_args(
            [
                "--profile",
                "release",
                "--warn-seconds",
                "60",
                "--max-seconds",
                "300",
            ]
        )
        self.assertEqual(budgeted.warn_seconds, 60.0)
        self.assertEqual(budgeted.max_seconds, 300.0)
        sharded_args = validator.parse_args(
            ["--shard-index", "3", "--shard-count", "4"]
        )
        self.assertEqual((sharded_args.shard_index, sharded_args.shard_count), (3, 4))
        validator.report_time_budget(
            "release", 59.999, budgeted.warn_seconds, budgeted.max_seconds
        )
        warning = io.StringIO()
        with redirect_stderr(warning):
            validator.report_time_budget(
                "release", 60.001, budgeted.warn_seconds, budgeted.max_seconds
            )
        self.assertIn("exceeded its 60s advisory threshold", warning.getvalue())
        with self.assertRaisesRegex(SystemExit, "exceeded its 300s budget"):
            validator.report_time_budget(
                "release", 300.001, budgeted.warn_seconds, budgeted.max_seconds
            )

    def test_scheduled_benchmark_uses_repeated_primary_shard_median(self) -> None:
        args = benchmark.parse_args(["--samples", "3", "--jobs", "8"])
        command = benchmark.validator_command(args)
        self.assertIn("--warn-seconds", command)
        self.assertEqual(command[command.index("--max-seconds") + 1], "300")
        self.assertEqual(command[command.index("--shard-index") + 1], "0")
        self.assertEqual(command[command.index("--shard-count") + 1], "8")

        warning = io.StringIO()
        with redirect_stderr(warning):
            median = benchmark.evaluate_median([59.0, 61.0, 70.0], 60.0, 180.0)
        self.assertEqual(median, 61.0)
        self.assertIn("median exceeded its 60s advisory threshold", warning.getvalue())
        with self.assertRaisesRegex(SystemExit, "exceeded its 180s budget"):
            benchmark.evaluate_median([179.0, 181.0, 190.0], 60.0, 180.0)

    def test_bootstrap_closure_validation_uses_final_gate_only_for_release(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            evidence = root / "work" / "evidence"
            evidence.mkdir(parents=True)
            manifest = evidence / "bootstrap-closure-fixture.json"
            manifest.write_text("{}\n", encoding="utf-8")
            with mock.patch.object(validator, "ROOT", root), mock.patch.object(
                validator, "step"
            ), mock.patch.object(validator, "run") as run:
                validator.validate_bootstrap_closures(require_final=False)
                development = run.call_args.args[0]
                self.assertNotIn("--require-final", development)
                run.reset_mock()
                validator.validate_bootstrap_closures(require_final=True)
                release = run.call_args.args[0]
                self.assertIn("--require-final", release)

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
