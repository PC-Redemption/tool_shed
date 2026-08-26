#!/usr/bin/env python3
"""Load and validate Tool Shed provider-adapter metadata."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "adapters" / "providers.json"
CAPABILITY_LEVELS = {
    1: "discussion",
    2: "planning",
    3: "workspace",
    4: "integrated",
    5: "delivery",
}


class AdapterManifestError(ValueError):
    """Raised when provider-adapter metadata is unsafe or malformed."""


def _safe_relative_path(value: object, *, field: str) -> str:
    text = str(value or "")
    if (
        not text
        or "\\" in text
        or text.startswith("/")
        or (len(text) >= 3 and text[0].isalpha() and text[1] == ":" and text[2] == "/")
    ):
        raise AdapterManifestError(f"{field} must be a safe repository-relative path")
    parts = tuple(part for part in text.split("/") if part)
    if not parts or all(part == "." for part in parts) or ".." in parts:
        raise AdapterManifestError(f"{field} must be a safe repository-relative path")
    return "/".join(parts)


def load_manifest(path: Path = MANIFEST) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AdapterManifestError(f"cannot read provider manifest {path}: {error}") from error
    if payload.get("schema_version") != 1:
        raise AdapterManifestError("provider manifest schema_version must equal 1")
    _safe_relative_path(payload.get("skill_source"), field="skill_source")
    providers = payload.get("providers")
    if not isinstance(providers, dict) or not providers:
        raise AdapterManifestError("provider manifest must define a non-empty providers object")
    seen_paths: set[str] = set()
    for provider_id, config in providers.items():
        if not isinstance(provider_id, str) or not provider_id or not isinstance(config, dict):
            raise AdapterManifestError("provider entries must map non-empty IDs to objects")
        instruction_path = _safe_relative_path(
            config.get("instruction_path"), field=f"providers.{provider_id}.instruction_path"
        )
        if instruction_path in seen_paths:
            raise AdapterManifestError(f"duplicate provider instruction path: {instruction_path}")
        seen_paths.add(instruction_path)
        if config.get("instruction_format") not in {"markdown", "mdc"}:
            raise AdapterManifestError(
                f"providers.{provider_id}.instruction_format must be markdown or mdc"
            )
        level = config.get("qualified_level")
        if level not in CAPABILITY_LEVELS:
            raise AdapterManifestError(
                f"providers.{provider_id}.qualified_level must be 1 through 5"
            )
        if config.get("qualification_basis") not in {"static", "local-runtime-and-static"}:
            raise AdapterManifestError(
                f"providers.{provider_id}.qualification_basis must be static or local-runtime-and-static"
            )
        if not str(config.get("display_name") or "").strip():
            raise AdapterManifestError(f"providers.{provider_id}.display_name is required")
    return payload


def provider_ids(path: Path = MANIFEST) -> tuple[str, ...]:
    return tuple(sorted(load_manifest(path)["providers"]))


def provider_config(provider_id: str, path: Path = MANIFEST) -> dict[str, Any]:
    providers = load_manifest(path)["providers"]
    try:
        return dict(providers[provider_id])
    except KeyError as error:
        choices = ", ".join(sorted(providers))
        raise AdapterManifestError(f"unknown provider {provider_id!r}; choose from: {choices}") from error
