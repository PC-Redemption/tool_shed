from __future__ import annotations

import copy
import hashlib
import json
import re
import unittest
import uuid
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "completion-watcher-v1" / "contract-cases.json"
SCHEMA_ROOT = ROOT / "schemas" / "completion-watcher" / "v1"
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")

CHECKER_STATES = {"WAITING", "SATISFIED", "TERMINAL_UNSATISFIED", "CHECK_ERROR"}
RESULT_REASONS = {
    "WAITING": {"TARGET_NONTERMINAL"},
    "SATISFIED": {"TARGET_SUCCEEDED", "CONDITION_MET"},
    "TERMINAL_UNSATISFIED": {
        "TARGET_FAILED",
        "TARGET_CANCELLED",
        "TARGET_PREEMPTED",
        "TARGET_SUPERSEDED",
    },
    "CHECK_ERROR": {"TARGET_MISSING_TRANSIENT", "SOURCE_UNAVAILABLE", "CHECKER_INTERNAL"},
}
EVENT_REASONS = {
    "SATISFIED": {"TARGET_SUCCEEDED", "CONDITION_MET"},
    "TERMINAL_UNSATISFIED": {
        "TARGET_FAILED",
        "TARGET_CANCELLED",
        "TARGET_PREEMPTED",
        "TARGET_SUPERSEDED",
        "TARGET_MISSING_AFTER_GRACE",
    },
    "CHECK_ERROR_EXHAUSTED": {"CONSECUTIVE_CHECK_ERRORS_EXHAUSTED"},
    "WATCH_CANCELLED": {"OPERATOR_CANCELLED_WATCH"},
    "RETIRED_WITHOUT_CONCLUSION": {"ADMINISTRATIVE_RETIREMENT"},
}


def _require_exact_keys(payload: dict[str, object], required: set[str], optional: set[str]) -> None:
    missing = required - payload.keys()
    unknown = payload.keys() - required - optional
    if missing:
        raise ValueError(f"missing fields: {sorted(missing)}")
    if unknown:
        raise ValueError(f"unknown fields: {sorted(unknown)}")


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("invalid timestamp") from error


def _bounded_text(value: object, *, minimum: int = 0, maximum: int) -> str:
    if not isinstance(value, str) or not minimum <= len(value) <= maximum:
        raise ValueError(f"text length must be {minimum}..{maximum}")
    return value


def _safe_id(value: object) -> str:
    value = _bounded_text(value, minimum=1, maximum=64)
    if not SAFE_ID.fullmatch(value):
        raise ValueError("invalid safe identifier")
    return value


def _watch_id(value: object) -> str:
    value = _bounded_text(value, minimum=36, maximum=36)
    parsed = uuid.UUID(value)
    if parsed.version != 4 or str(parsed) != value:
        raise ValueError("watch ID must be a canonical lowercase UUIDv4")
    return value


def _validate_workspace(payload: object) -> None:
    if not isinstance(payload, dict):
        raise ValueError("workspace must be an object")
    _require_exact_keys(payload, {"id", "alias"}, set())
    _safe_id(payload["id"])
    _bounded_text(payload["alias"], minimum=1, maximum=80)


def _validate_target(payload: object) -> None:
    if not isinstance(payload, dict):
        raise ValueError("target must be an object")
    _require_exact_keys(payload, {"kind", "id"}, {"generation"})
    _safe_id(payload["kind"])
    _bounded_text(payload["id"], minimum=1, maximum=256)
    if "generation" in payload:
        _bounded_text(payload["generation"], minimum=1, maximum=128)


def validate_descriptor(payload: dict[str, object]) -> None:
    required = {
        "schema_version",
        "watch_id",
        "created_at",
        "display_name",
        "workspace",
        "target",
        "checker",
        "policy",
        "notification",
    }
    _require_exact_keys(payload, required, {"review_url"})
    if payload["schema_version"] != 1:
        raise ValueError("unsupported descriptor schema")
    _watch_id(payload["watch_id"])
    _timestamp(payload["created_at"])
    _bounded_text(payload["display_name"], minimum=1, maximum=120)
    _validate_workspace(payload["workspace"])
    _validate_target(payload["target"])

    checker = payload["checker"]
    if not isinstance(checker, dict):
        raise ValueError("checker must be an object")
    _require_exact_keys(
        checker,
        {"argv", "timeout_seconds"},
        {"working_directory", "credential_profile"},
    )
    argv = checker["argv"]
    if not isinstance(argv, list) or not 1 <= len(argv) <= 16:
        raise ValueError("checker argv must contain 1..16 entries")
    for argument in argv:
        _bounded_text(argument, minimum=1, maximum=2048)
    timeout = checker["timeout_seconds"]
    if not isinstance(timeout, int) or not 1 <= timeout <= 55:
        raise ValueError("checker timeout must be 1..55 seconds")
    if "working_directory" in checker:
        _bounded_text(checker["working_directory"], minimum=1, maximum=4096)
    if "credential_profile" in checker:
        _safe_id(checker["credential_profile"])

    policy = payload["policy"]
    if not isinstance(policy, dict):
        raise ValueError("policy must be an object")
    _require_exact_keys(
        policy,
        {
            "poll_interval_seconds",
            "missing_grace_checks",
            "max_consecutive_check_errors",
            "claim_lease_seconds",
            "idle_exit_scans",
        },
        {"review_after", "administrative_retire_after"},
    )
    if policy["poll_interval_seconds"] != 60 or policy["idle_exit_scans"] != 2:
        raise ValueError("v1 cadence and idle exit are fixed")
    for field, lower, upper in (
        ("missing_grace_checks", 1, 10),
        ("max_consecutive_check_errors", 1, 20),
        ("claim_lease_seconds", 60, 900),
    ):
        value = policy[field]
        if not isinstance(value, int) or not lower <= value <= upper:
            raise ValueError(f"invalid policy field: {field}")
    for field in ("review_after", "administrative_retire_after"):
        if field in policy:
            _timestamp(policy[field])

    notification = payload["notification"]
    if not isinstance(notification, dict):
        raise ValueError("notification must be an object")
    _require_exact_keys(notification, {"adapter"}, {"profile"})
    if notification["adapter"] not in {"none", "project", "hosted"}:
        raise ValueError("invalid notification adapter")
    if notification["adapter"] == "none" and "profile" in notification:
        raise ValueError("none adapter must not name a profile")
    if notification["adapter"] != "none" and "profile" not in notification:
        raise ValueError("configured adapter requires a profile")
    if "profile" in notification:
        _safe_id(notification["profile"])
    if "review_url" in payload:
        review_url = _bounded_text(payload["review_url"], minimum=1, maximum=2048)
        if not review_url.startswith(("https://", "http://")):
            raise ValueError("review URL must be HTTP(S)")


def validate_result(payload: dict[str, object], descriptor: dict[str, object]) -> None:
    _require_exact_keys(
        payload,
        {
            "schema_version",
            "state",
            "observed_at",
            "target",
            "reason_code",
            "identity_confirmed",
            "target_exists",
            "authoritative_nonterminal",
        },
        {"progress_at", "detail"},
    )
    if payload["schema_version"] != 1 or payload["state"] not in CHECKER_STATES:
        raise ValueError("invalid checker result version or state")
    _timestamp(payload["observed_at"])
    _validate_target(payload["target"])
    if payload["target"] != descriptor["target"]:
        raise ValueError("checker result target does not match immutable descriptor target")
    state = str(payload["state"])
    if payload["reason_code"] not in RESULT_REASONS[state]:
        raise ValueError("reason code does not match checker state")
    for field in ("identity_confirmed", "target_exists", "authoritative_nonterminal"):
        if not isinstance(payload[field], bool):
            raise ValueError(f"{field} must be boolean")
    if state == "WAITING" and not (
        payload["identity_confirmed"]
        and payload["target_exists"]
        and payload["authoritative_nonterminal"]
    ):
        raise ValueError("WAITING requires exact live nonterminal evidence")
    if state in {"SATISFIED", "TERMINAL_UNSATISFIED"} and (
        not payload["identity_confirmed"] or payload["authoritative_nonterminal"]
    ):
        raise ValueError("terminal result requires confirmed identity and non-waiting evidence")
    if state == "CHECK_ERROR" and payload["authoritative_nonterminal"]:
        raise ValueError("CHECK_ERROR cannot claim authoritative nonterminal evidence")
    if "progress_at" in payload:
        _timestamp(payload["progress_at"])
    if "detail" in payload:
        _bounded_text(payload["detail"], maximum=512)


def validate_watch_record(payload: dict[str, object]) -> None:
    _require_exact_keys(
        payload,
        {
            "record_version",
            "descriptor",
            "descriptor_sha256",
            "lifecycle_state",
            "due_at",
            "missing_streak",
            "error_streak",
            "checker_attempts",
        },
        {
            "last_checked_at",
            "last_progress_at",
            "cancel_requested_at",
            "terminal_event_id",
            "claim",
        },
    )
    if payload["record_version"] != 1:
        raise ValueError("invalid watch record version")
    descriptor = payload["descriptor"]
    validate_descriptor(descriptor)
    canonical = json.dumps(
        descriptor,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    if payload["descriptor_sha256"] != hashlib.sha256(canonical).hexdigest():
        raise ValueError("descriptor digest mismatch")
    state = payload["lifecycle_state"]
    if state not in {"PENDING", "CLAIMED", "RETIRING"}:
        raise ValueError("invalid watch lifecycle state")
    _timestamp(payload["due_at"])
    for field in ("missing_streak", "error_streak", "checker_attempts"):
        if not isinstance(payload[field], int) or payload[field] < 0:
            raise ValueError(f"invalid watch counter: {field}")
    if state == "CLAIMED" and "claim" not in payload:
        raise ValueError("claimed watch requires lease metadata")
    if state == "RETIRING" and "terminal_event_id" not in payload:
        raise ValueError("retiring watch requires terminal event ID")


def terminal_event_id(watch_id: str) -> str:
    return hashlib.sha256(
        ("tool-shed-watch-terminal-v1\0" + watch_id).encode("utf-8")
    ).hexdigest()


def validate_terminal_event(payload: dict[str, object], descriptor: dict[str, object]) -> None:
    _require_exact_keys(
        payload,
        {
            "schema_version",
            "event_id",
            "idempotency_key",
            "watch_id",
            "workspace",
            "display_name",
            "target",
            "terminal_class",
            "reason_code",
            "occurred_at",
            "enqueued_at",
            "notification_adapter",
        },
        {"sanitized_detail", "review_url"},
    )
    if payload["schema_version"] != 1:
        raise ValueError("invalid terminal event version")
    watch_id = _watch_id(payload["watch_id"])
    expected_event_id = terminal_event_id(watch_id)
    if payload["event_id"] != expected_event_id:
        raise ValueError("terminal event ID is not deterministic")
    if payload["idempotency_key"] != f"watch-terminal-v1:{expected_event_id}":
        raise ValueError("terminal idempotency key is not deterministic")
    _validate_workspace(payload["workspace"])
    _bounded_text(payload["display_name"], minimum=1, maximum=120)
    _validate_target(payload["target"])
    for field in ("workspace", "display_name", "target", "watch_id"):
        if payload[field] != descriptor[field]:
            raise ValueError(f"terminal event changed immutable descriptor field: {field}")
    terminal_class = str(payload["terminal_class"])
    if terminal_class not in EVENT_REASONS or payload["reason_code"] not in EVENT_REASONS[terminal_class]:
        raise ValueError("reason code does not match terminal class")
    occurred = _timestamp(payload["occurred_at"])
    enqueued = _timestamp(payload["enqueued_at"])
    if enqueued < occurred:
        raise ValueError("event cannot be enqueued before occurrence")
    if payload["notification_adapter"] != descriptor["notification"]["adapter"]:
        raise ValueError("terminal event changed notification adapter")
    if "sanitized_detail" in payload:
        _bounded_text(payload["sanitized_detail"], maximum=512)
    if "review_url" in payload:
        _bounded_text(payload["review_url"], minimum=1, maximum=2048)


def _checker_error(previous: dict[str, object], policy: dict[str, int], *, missing: bool) -> dict[str, object]:
    error_streak = int(previous.get("error_streak", 0)) + 1
    missing_streak = int(previous.get("missing_streak", 0)) + 1 if missing else 0
    if missing and missing_streak >= policy["missing_grace_checks"]:
        return {
            "action": "ENQUEUE_TERMINAL",
            "terminal_class": "TERMINAL_UNSATISFIED",
            "reason_code": "TARGET_MISSING_AFTER_GRACE",
        }
    if error_streak >= policy["max_consecutive_check_errors"]:
        return {
            "action": "ENQUEUE_TERMINAL",
            "terminal_class": "CHECK_ERROR_EXHAUSTED",
            "reason_code": "CONSECUTIVE_CHECK_ERRORS_EXHAUSTED",
        }
    return {
        "action": "REQUEUE",
        "state": "CHECK_ERROR",
        "missing_streak": missing_streak,
        "error_streak": error_streak,
    }


def evaluate_transition(
    case: dict[str, object],
    descriptor: dict[str, object],
    results: dict[str, dict[str, object]],
) -> dict[str, object]:
    previous = dict(case["previous"])
    observation = dict(case["observation"])
    if previous.get("outbox_has_terminal"):
        return {"action": "RETIRE_AFTER_ENQUEUE"}
    if previous.get("cancel_requested"):
        return {
            "action": "ENQUEUE_TERMINAL",
            "terminal_class": "WATCH_CANCELLED",
            "reason_code": "OPERATOR_CANCELLED_WATCH",
        }
    if previous.get("administrative_retire_requested"):
        return {
            "action": "ENQUEUE_TERMINAL",
            "terminal_class": "RETIRED_WITHOUT_CONCLUSION",
            "reason_code": "ADMINISTRATIVE_RETIREMENT",
        }
    if observation["type"] == "ensure_runner" and previous.get("runner_lock_held"):
        return {"action": "NO_START_LOCK_HELD"}
    if (
        previous.get("claim_owner")
        and previous.get("claim_owner") != previous.get("current_runner")
        and previous.get("current_runner_has_lock")
    ):
        return {"action": "RECOVER_CLAIM"}
    policy = descriptor["policy"]
    if observation["type"] in {"runner_fault", "identity_mismatch"}:
        return _checker_error(previous, policy, missing=False)
    if observation["type"] != "result":
        raise ValueError(f"unsupported observation: {observation['type']}")
    result = results[str(observation["result"])]
    validate_result(result, descriptor)
    state = result["state"]
    if state == "WAITING":
        return {
            "action": "REQUEUE_REVIEW_DUE" if previous.get("review_due") else "REQUEUE",
            "state": "WAITING",
            "missing_streak": 0,
            "error_streak": 0,
        }
    if state == "SATISFIED":
        return {
            "action": "ENQUEUE_TERMINAL",
            "terminal_class": "SATISFIED",
            "reason_code": result["reason_code"],
        }
    if state == "TERMINAL_UNSATISFIED":
        return {
            "action": "ENQUEUE_TERMINAL",
            "terminal_class": "TERMINAL_UNSATISFIED",
            "reason_code": result["reason_code"],
        }
    return _checker_error(
        previous,
        policy,
        missing=result["reason_code"] == "TARGET_MISSING_TRANSIENT",
    )


class CompletionWatcherContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.descriptor = cls.fixture["descriptor"]

    def test_schema_documents_parse_and_match_the_oracle(self) -> None:
        schemas = {
            path.name: json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(SCHEMA_ROOT.glob("*.schema.json"))
        }
        self.assertEqual(
            set(schemas),
            {
                "watch-descriptor.schema.json",
                "watch-record.schema.json",
                "checker-result.schema.json",
                "terminal-event.schema.json",
            },
        )
        for schema in schemas.values():
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            set(schemas["checker-result.schema.json"]["properties"]["state"]["enum"]),
            CHECKER_STATES,
        )
        self.assertEqual(
            set(schemas["checker-result.schema.json"]["properties"]["reason_code"]["enum"]),
            set().union(*RESULT_REASONS.values()),
        )
        self.assertEqual(
            set(schemas["terminal-event.schema.json"]["properties"]["terminal_class"]["enum"]),
            set(EVENT_REASONS),
        )
        self.assertEqual(
            set(schemas["terminal-event.schema.json"]["properties"]["reason_code"]["enum"]),
            set().union(*EVENT_REASONS.values()),
        )

    def test_valid_descriptor_results_and_events(self) -> None:
        validate_descriptor(self.descriptor)
        validate_watch_record(self.fixture["watch_record"])
        for result in self.fixture["checker_results"].values():
            validate_result(result, self.descriptor)
        for event in self.fixture["terminal_events"].values():
            validate_terminal_event(event, self.descriptor)

    def test_invalid_payloads_are_rejected(self) -> None:
        for invalid in self.fixture["invalid_payloads"]:
            with self.subTest(invalid["id"]), self.assertRaises(ValueError):
                if invalid["kind"] == "descriptor":
                    payload = copy.deepcopy(self.descriptor)
                    target = payload
                    for part in invalid["set_path"][:-1]:
                        target = target[part]
                    target[invalid["set_path"][-1]] = invalid["value"]
                    validate_descriptor(payload)
                elif invalid["kind"] == "checker_result":
                    payload = copy.deepcopy(self.fixture["checker_results"][invalid["base"]])
                    payload.update(invalid["set"])
                    validate_result(payload, self.descriptor)
                else:
                    payload = copy.deepcopy(self.fixture["terminal_events"][invalid["base"]])
                    payload.update(invalid["set"])
                    validate_terminal_event(payload, self.descriptor)

    def test_transition_oracle(self) -> None:
        for case in self.fixture["transition_cases"]:
            with self.subTest(case["id"]):
                self.assertEqual(
                    evaluate_transition(case, self.descriptor, self.fixture["checker_results"]),
                    case["expected"],
                )

    def test_linux_and_windows_portability_oracle(self) -> None:
        platforms = {item["platform"]: item for item in self.fixture["platform_cases"]}
        self.assertEqual(set(platforms), {"linux", "windows"})
        self.assertEqual(platforms["linux"]["directory_mode"], "0700")
        self.assertEqual(platforms["linux"]["file_mode"], "0600")
        self.assertEqual(platforms["linux"]["singleton_lock"], "flock")
        self.assertEqual(platforms["windows"]["singleton_lock"], "LockFileEx")
        self.assertTrue(platforms["windows"]["current_user_acl_required"])
        self.assertTrue(all(item["reject_links"] for item in platforms.values()))


if __name__ == "__main__":
    unittest.main()
