#!/usr/bin/env python3
"""Refresh or inspect Tool Shed's cached Codex model/reasoning catalog."""

from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
DEFAULT_TTL_HOURS = 24.0


class CatalogError(RuntimeError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def default_cache_path() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    root = Path(codex_home).expanduser() if codex_home else Path.home() / ".codex"
    return root / "tool-shed" / "reasoning-catalog.json"


def send_message(process: subprocess.Popen[str], message: dict[str, Any]) -> None:
    if process.stdin is None:
        raise CatalogError("Codex app-server stdin is unavailable")
    process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
    process.stdin.flush()


def wait_for_response(
    messages: queue.Queue[str], request_id: int, *, timeout: float
) -> dict[str, Any]:
    deadline = utc_now().timestamp() + timeout
    while True:
        remaining = deadline - utc_now().timestamp()
        if remaining <= 0:
            raise CatalogError(f"timed out waiting for Codex app-server response {request_id}")
        try:
            raw = messages.get(timeout=remaining)
        except queue.Empty as error:
            raise CatalogError(f"timed out waiting for Codex app-server response {request_id}") from error
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if message.get("id") != request_id:
            continue
        if "error" in message:
            raise CatalogError(f"Codex app-server error: {message['error']}")
        result = message.get("result")
        if not isinstance(result, dict):
            raise CatalogError(f"Codex app-server response {request_id} has no result object")
        return result


def query_codex_catalog(codex: str, *, timeout: float) -> tuple[list[dict[str, Any]], str]:
    try:
        process = subprocess.Popen(
            [codex, "app-server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
    except OSError as error:
        raise CatalogError(f"cannot start Codex app-server: {error}") from error

    messages: queue.Queue[str] = queue.Queue()

    def read_stdout() -> None:
        if process.stdout is not None:
            for line in process.stdout:
                messages.put(line)

    reader = threading.Thread(target=read_stdout, daemon=True)
    reader.start()
    try:
        send_message(
            process,
            {
                "method": "initialize",
                "id": 0,
                "params": {
                    "clientInfo": {
                        "name": "tool_shed",
                        "title": "Tool Shed",
                        "version": "1.0.0",
                    }
                },
            },
        )
        initialized = wait_for_response(messages, 0, timeout=timeout)
        send_message(process, {"method": "initialized", "params": {}})
        send_message(
            process,
            {
                "method": "model/list",
                "id": 1,
                "params": {"limit": 1000, "includeHidden": False},
            },
        )
        result = wait_for_response(messages, 1, timeout=timeout)
        models = result.get("data")
        if not isinstance(models, list):
            raise CatalogError("Codex model/list response has no data array")
        user_agent = str(initialized.get("userAgent") or "unknown")
        return [model for model in models if isinstance(model, dict)], user_agent
    finally:
        if process.stdin is not None:
            process.stdin.close()
        try:
            process.terminate()
        except OSError:
            pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)


def normalize_model(model: dict[str, Any]) -> dict[str, Any]:
    efforts: list[dict[str, str]] = []
    for entry in model.get("supportedReasoningEfforts") or []:
        if not isinstance(entry, dict) or not entry.get("reasoningEffort"):
            continue
        efforts.append(
            {
                "id": str(entry["reasoningEffort"]),
                "description": str(entry.get("description") or ""),
            }
        )
    return {
        "id": str(model.get("id") or model.get("model") or ""),
        "model": str(model.get("model") or model.get("id") or ""),
        "display_name": str(model.get("displayName") or model.get("model") or model.get("id") or ""),
        "default_reasoning_effort": model.get("defaultReasoningEffort"),
        "supported_reasoning_efforts": efforts,
        "is_default": bool(model.get("isDefault", False)),
        "input_modalities": model.get("inputModalities") or ["text", "image"],
        "upgrade": model.get("upgrade"),
    }


def build_catalog(models: list[dict[str, Any]], user_agent: str, *, ttl_hours: float) -> dict[str, Any]:
    retrieved = utc_now()
    return {
        "schema_version": SCHEMA_VERSION,
        "source": "codex-app-server:model/list",
        "source_user_agent": user_agent,
        "retrieved_at": retrieved.isoformat().replace("+00:00", "Z"),
        "expires_at": (retrieved + timedelta(hours=ttl_hours)).isoformat().replace("+00:00", "Z"),
        "models": [normalize_model(model) for model in models if model.get("id") or model.get("model")],
    }


def write_catalog(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
        try:
            temporary.chmod(0o600)
        except OSError:
            pass
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def read_catalog(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise CatalogError(f"reasoning catalog does not exist: {path}") from error
    except json.JSONDecodeError as error:
        raise CatalogError(f"reasoning catalog is invalid JSON: {path}") from error
    if payload.get("schema_version") != SCHEMA_VERSION or not isinstance(payload.get("models"), list):
        raise CatalogError(f"reasoning catalog has an unsupported schema: {path}")
    return payload


def catalog_status(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    expires = payload.get("expires_at")
    try:
        expires_at = datetime.fromisoformat(str(expires).replace("Z", "+00:00"))
        fresh = utc_now() < expires_at
    except ValueError:
        fresh = False
    return {
        "path": str(path),
        "fresh": fresh,
        "source": payload.get("source"),
        "source_user_agent": payload.get("source_user_agent"),
        "retrieved_at": payload.get("retrieved_at"),
        "expires_at": expires,
        "model_count": len(payload["models"]),
        "models": payload["models"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    refresh = subparsers.add_parser("refresh", help="Refresh the cache through Codex app-server model/list.")
    refresh.add_argument("--codex", default="codex", help="Codex executable. Defaults to codex on PATH.")
    refresh.add_argument("--timeout", type=float, default=15.0, help="Seconds allowed per app-server response.")
    refresh.add_argument("--ttl-hours", type=float, default=DEFAULT_TTL_HOURS)
    refresh.add_argument("--cache", type=Path, default=default_cache_path())
    status = subparsers.add_parser("status", help="Inspect the cache without network or subprocesses.")
    status.add_argument("--cache", type=Path, default=default_cache_path())
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cache = args.cache.expanduser().resolve()
    try:
        if args.command == "refresh":
            if args.timeout <= 0 or args.ttl_hours <= 0:
                raise CatalogError("--timeout and --ttl-hours must be greater than zero")
            models, user_agent = query_codex_catalog(args.codex, timeout=args.timeout)
            payload = build_catalog(models, user_agent, ttl_hours=args.ttl_hours)
            if not payload["models"]:
                raise CatalogError("Codex returned an empty visible model catalog")
            write_catalog(cache, payload)
        else:
            payload = read_catalog(cache)
        print(json.dumps(catalog_status(cache, payload), indent=2, sort_keys=True))
        return 0
    except CatalogError as error:
        print(json.dumps({"error": str(error), "path": str(cache)}, indent=2), file=os.sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
