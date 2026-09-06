from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from scripts.codex_app_server import CodexAppServerClient
from scripts.context_retrieval import BoundedContextReader, ContextRetrievalError


class BoundedContextReaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "src").mkdir()
        (self.root / "src" / "alpha.py").write_text(
            "one\ntwo\nthree\nfour\n", encoding="utf-8"
        )
        (self.root / "src" / "beta.py").write_text("beta\n" * 30_000, encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def reader(self, files: tuple[Path, ...] = (Path("src/alpha.py"),)) -> BoundedContextReader:
        return BoundedContextReader(
            self.root,
            files,
            max_snapshot_bytes=2_000_000,
            max_manifest_bytes=12_000,
            max_read_bytes=64,
            max_total_bytes=80,
            max_lines=10,
        )

    @staticmethod
    def request(reader: BoundedContextReader, **overrides: object) -> dict[str, object]:
        arguments: dict[str, object] = {
            "manifest_sha256": reader.manifest_digest,
            "path": "src/alpha.py",
            "start_line": 2,
            "line_count": 2,
        }
        arguments.update(overrides)
        return {"tool": "read_context", "namespace": None, "arguments": arguments}

    def test_manifest_is_deterministic_and_can_cover_more_than_inline_context(self) -> None:
        with self.reader((Path("src/beta.py"), Path("src/alpha.py"))) as first:
            with self.reader((Path("src/alpha.py"), Path("src/beta.py"))) as second:
                self.assertEqual(first.manifest_digest, second.manifest_digest)
                self.assertGreater(first.evidence_summary()["snapshot_bytes"], 100_000)
                self.assertEqual(
                    ["src/alpha.py", "src/beta.py"], first.evidence_summary()["allowlisted_paths"]
                )

    def test_read_requires_digest_allowlist_and_range_and_retains_no_content(self) -> None:
        with self.reader() as reader:
            response = reader.handle(self.request(reader))

            self.assertTrue(response["success"])
            payload = json.loads(response["contentItems"][0]["text"])
            self.assertEqual("two\nthree\n", payload["content"])
            summary = reader.evidence_summary()
            self.assertFalse(summary["content_retained"])
            self.assertNotIn("content", summary["reads"][0])
            self.assertEqual(10, summary["returned_bytes"])

            refused = reader.handle(
                self.request(reader, manifest_sha256="0" * 64, path="../secret")
            )
            self.assertFalse(refused["success"])
            self.assertEqual("manifest_digest_mismatch", summary_code(refused))

    def test_read_normalizes_crlf_before_range_and_byte_budget_accounting(self) -> None:
        windows_text = self.root / "src" / "windows.txt"
        windows_text.write_bytes(b"one\r\ntwo\r\nthree\r\nfour\r\n")
        with self.reader((Path("src/windows.txt"),)) as reader:
            request = self.request(reader, path="src/windows.txt")
            response = reader.handle(request)

            self.assertTrue(response["success"])
            payload = json.loads(response["contentItems"][0]["text"])
            self.assertEqual("two\nthree\n", payload["content"])
            self.assertEqual(10, payload["returned_bytes"])
            self.assertEqual(23, reader.evidence_summary()["snapshot_bytes"])

    def test_source_change_and_each_budget_fail_closed(self) -> None:
        with self.reader() as reader:
            (self.root / "src" / "alpha.py").write_text("changed\n", encoding="utf-8")
            self.assertEqual(
                "source_digest_mismatch", summary_code(reader.handle(self.request(reader)))
            )

        long_line = self.root / "src" / "long.txt"
        long_line.write_text("x" * 65 + "\n", encoding="utf-8")
        with self.reader((Path("src/long.txt"),)) as reader:
            request = self.request(reader, path="src/long.txt", start_line=1, line_count=1)
            self.assertEqual("per_read_budget_exceeded", summary_code(reader.handle(request)))

        (self.root / "src" / "alpha.py").write_text(
            "one\ntwo\nthree\nfour\n", encoding="utf-8"
        )
        with self.reader() as reader:
            first = self.request(reader, start_line=1, line_count=4)
            self.assertTrue(reader.handle(first)["success"])
            # Repeated valid reads eventually consume the cumulative source-byte budget.
            self.assertTrue(reader.handle(first)["success"])
            self.assertTrue(reader.handle(first)["success"])
            self.assertTrue(reader.handle(first)["success"])
            self.assertEqual("cumulative_budget_exceeded", summary_code(reader.handle(first)))

    def test_constructor_refuses_symlink_and_traversal(self) -> None:
        (self.root / "link.py").symlink_to(self.root / "src" / "alpha.py")
        with self.assertRaises(ContextRetrievalError):
            self.reader((Path("link.py"),))
        with self.assertRaises(ContextRetrievalError):
            self.reader((Path("../alpha.py"),))
        real = self.root / "real"
        real.mkdir()
        (real / "nested.py").write_text("nested\n", encoding="utf-8")
        (self.root / "linked-parent").symlink_to(real, target_is_directory=True)
        with self.assertRaises(ContextRetrievalError):
            self.reader((Path("linked-parent/nested.py"),))


class DynamicToolProtocolTests(unittest.TestCase):
    def test_client_routes_only_the_dynamic_tool_request_method(self) -> None:
        handler = Mock(return_value={"success": True, "contentItems": []})
        client = CodexAppServerClient(dynamic_tool_handler=handler)
        sender = Mock()
        client._send = sender  # type: ignore[method-assign]
        params = {
            "threadId": "thread",
            "turnId": "turn",
            "callId": "call",
            "tool": "read_context",
            "namespace": None,
            "arguments": {},
        }

        client._handle_server_request({"id": 7, "method": "item/tool/call", "params": params})

        handler.assert_called_once_with(params)
        sender.assert_called_once_with(
            {"id": 7, "result": {"success": True, "contentItems": []}}
        )

    def test_thread_start_sends_dynamic_tool_specs(self) -> None:
        client = CodexAppServerClient()
        client.request = Mock(return_value={"thread": {"id": "thread"}})  # type: ignore[method-assign]
        tools = [{"type": "function", "name": "read_context", "description": "read", "inputSchema": {}}]

        client.start_thread(
            model="gpt-5.6-sol",
            cwd=Path.cwd(),
            approval_policy="never",
            sandbox="read-only",
            dynamic_tools=tools,
        )

        params = client.request.call_args.args[1]
        self.assertEqual(tools, params["dynamicTools"])

    def test_planning_allowlist_interrupts_any_non_dynamic_tool(self) -> None:
        client = CodexAppServerClient(timeout=1)
        client.interrupt = Mock(return_value={})  # type: ignore[method-assign]
        client._notifications.extend(
            [
                {
                    "method": "item/started",
                    "params": {
                        "threadId": "thread",
                        "turnId": "turn",
                        "item": {"id": "web", "type": "webSearch"},
                    },
                },
                {
                    "method": "turn/completed",
                    "params": {
                        "threadId": "thread",
                        "turn": {"id": "turn", "status": "interrupted"},
                    },
                },
            ]
        )

        result = client.wait_for_turn(
            "thread",
            "turn",
            allowed_tool_call_types=frozenset({"dynamicToolCall"}),
        )

        self.assertEqual("worker_tool_call_disallowed", result.control_stop["kind"])
        client.interrupt.assert_called_once()


def summary_code(response: dict[str, object]) -> str:
    items = response["contentItems"]
    assert isinstance(items, list)
    item = items[0]
    assert isinstance(item, dict)
    return str(json.loads(str(item["text"]))["code"])


if __name__ == "__main__":
    unittest.main()
