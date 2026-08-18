#!/usr/bin/env python3
"""Manage opt-in, file-based Tool Shed Program Roadmaps."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import campaign_queue
from project_identity import ProjectIdentityError, bind_state_token, require_project_binding
from update_work_index import discover_artifacts, render as render_index, render_json as render_index_json


SCHEMA_VERSION = 1
PROPOSAL_KIND = "tool-shed-roadmap-proposal"
CAMPAIGN_PLAN_KIND = "tool-shed-roadmap-campaign-plan"
ROADMAP_STATUSES = {"proposed", "approved", "executing", "complete", "superseded"}
CURRENT_STATUSES = {"approved", "executing", "complete"}
ID_RE = campaign_queue.ID_RE
STABLE_ID_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*$")
DEFINITION_RE = re.compile(
    r"^## Roadmap Definition\s*$\n\n```json\n(?P<json>.*?)\n```",
    re.MULTILINE | re.DOTALL,
)
HEADER_KEYS = (
    "Status",
    "Type",
    "Updated",
    "Next Action",
    "Roadmap ID",
    "Revision",
    "Source Project Map",
    "Source State Token",
    "Proposal Token",
    "Approved",
    "Current Milestone",
    "Supersedes",
    "Superseded By",
)
SOURCE_SKIP = {
    "work/index.md",
    "work/index.json",
    "work/00-campaigns/active-queue.md",
    "work/00-campaigns/completed-queue.md",
}


class RoadmapError(ValueError):
    pass


@dataclass
class Roadmap:
    path: Path
    title: str
    fields: dict[str, str]
    definition: dict[str, Any]

    @property
    def roadmap_id(self) -> str:
        return self.fields.get("Roadmap ID", "")

    @property
    def revision(self) -> int:
        try:
            return int(self.fields.get("Revision", "0"))
        except ValueError:
            return 0

    @property
    def status(self) -> str:
        return self.fields.get("Status", "")


def _canonical(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _token(payload: object) -> str:
    return hashlib.sha256(_canonical(payload)).hexdigest()[:16]


def _file_token(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.name.encode("utf-8"))
    digest.update(b"\0")
    digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def roadmap_root(workspace: Path) -> Path:
    return workspace / "work" / "roadmaps"


def refresh_indexes(workspace: Path) -> None:
    work = workspace / "work"
    work.mkdir(parents=True, exist_ok=True)
    artifacts = discover_artifacts(work)
    (work / "index.md").write_text(render_index(artifacts), encoding="utf-8", newline="\n")
    (work / "index.json").write_text(render_index_json(artifacts), encoding="utf-8", newline="\n")


def _campaign_belongs_to(path: Path, roadmap_id: str) -> bool:
    if "00-campaigns" not in path.parts or not path.is_file():
        return False
    for line in path.read_text(encoding="utf-8").splitlines()[:45]:
        if line == f"Roadmap: {roadmap_id}":
            return True
    return False


def source_state_token(workspace: Path, roadmap_id: str | None = None) -> str:
    """Hash roadmap inputs while excluding generated projections and roadmap outputs."""
    digest = hashlib.sha256()
    candidates: list[Path] = []
    for relative in ("README.md", "AGENTS.md"):
        path = workspace / relative
        if path.is_file():
            candidates.append(path)
    for directory in (workspace / "docs", workspace / "work"):
        if directory.is_dir():
            candidates.extend(path for path in directory.rglob("*.md") if path.is_file())
    for path in sorted(set(candidates)):
        relative = path.relative_to(workspace).as_posix()
        if relative in SOURCE_SKIP or relative.startswith("work/roadmaps/"):
            continue
        if "/evidence/generated/" in f"/{relative}":
            continue
        if roadmap_id and _campaign_belongs_to(path, roadmap_id):
            continue
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return bind_state_token(
        workspace,
        "program-roadmap-source",
        digest.hexdigest(),
        allow_unidentified=True,
    )


def map_token(path: Path) -> str:
    try:
        work_index = path.resolve().parts.index("work")
    except ValueError as error:
        raise RoadmapError(f"project map is outside work/: {path}") from error
    workspace = Path(*path.resolve().parts[:work_index])
    return bind_state_token(
        workspace,
        "program-roadmap-map",
        _file_token(path),
        allow_unidentified=True,
    )


def parse_headers(text: str) -> tuple[str, dict[str, str]]:
    title = "Untitled"
    fields: dict[str, str] = {}
    for raw in text.splitlines()[:45]:
        if raw.startswith("# "):
            title = raw[2:].removeprefix("Program Roadmap: ").strip()
        if ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        if key.strip() in HEADER_KEYS:
            fields[key.strip()] = value.strip()
    return title, fields


def parse_roadmap(path: Path) -> Roadmap:
    text = path.read_text(encoding="utf-8")
    title, fields = parse_headers(text)
    match = DEFINITION_RE.search(text)
    if match is None:
        raise RoadmapError(f"roadmap has no JSON definition: {path}")
    try:
        definition = json.loads(match.group("json"))
    except json.JSONDecodeError as error:
        raise RoadmapError(f"roadmap definition is invalid JSON: {path}: {error}") from error
    if not isinstance(definition, dict):
        raise RoadmapError(f"roadmap definition must be an object: {path}")
    return Roadmap(path, title, fields, definition)


def load_roadmaps(workspace: Path) -> list[Roadmap]:
    root = roadmap_root(workspace)
    if not root.is_dir():
        return []
    return [parse_roadmap(path) for path in sorted(root.glob("roadmap-*.md"))]


def _roadmap_path(workspace: Path, roadmap_id: str, revision: int) -> Path:
    suffix = "" if revision == 1 else f"-r{revision}"
    return roadmap_root(workspace) / f"roadmap-{roadmap_id}{suffix}.md"


def proposal_token(definition: dict[str, Any], source_token: str) -> str:
    return _token({"definition": definition, "source_state_token": source_token})


def render_roadmap(roadmap: Roadmap) -> str:
    lines = [f"# Program Roadmap: {roadmap.title}", ""]
    for key in HEADER_KEYS:
        if key in roadmap.fields:
            lines.append(f"{key}: {roadmap.fields[key]}")
    lines.extend(
        [
            "",
            "## Roadmap Definition",
            "",
            "```json",
            json.dumps(roadmap.definition, indent=2, sort_keys=True),
            "```",
            "",
            "## Revision History",
            "",
            f"- Revision {roadmap.revision}: {roadmap.status} on {roadmap.fields.get('Updated', date.today().isoformat())}.",
            "",
        ]
    )
    return "\n".join(lines)


def _require_list(definition: dict[str, Any], key: str) -> list[Any]:
    value = definition.get(key)
    if not isinstance(value, list):
        raise RoadmapError(f"roadmap definition {key} must be a list")
    return value


def _require_strings(value: object, context: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise RoadmapError(f"{context} must be a list of non-empty strings")
    return [str(item) for item in value]


def _validate_acyclic(nodes: dict[str, list[str]], label: str) -> list[str]:
    findings: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str, chain: list[str]) -> None:
        if node in visiting:
            findings.append(f"{label} dependency cycle: " + " -> ".join([*chain, node]))
            return
        if node in visited:
            return
        visiting.add(node)
        for dependency in nodes.get(node, []):
            if dependency not in nodes:
                findings.append(f"{label} {node} has missing dependency {dependency}")
            else:
                visit(dependency, [*chain, node])
        visiting.remove(node)
        visited.add(node)

    for node in nodes:
        visit(node, [])
    return findings


def validate_definition(definition: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    required_text = ("desired_outcome", "non_goals", "constraints", "authority_boundaries")
    for key in required_text:
        if not isinstance(definition.get(key), str) or not definition[key].strip():
            findings.append(f"roadmap definition needs non-empty {key}")
    for key in ("assumptions", "unknowns", "decisions"):
        try:
            _require_strings(definition.get(key), key)
        except RoadmapError as error:
            findings.append(str(error))

    collections: dict[str, list[dict[str, Any]]] = {}
    for key in ("phases", "milestones", "gates", "candidate_campaigns", "artifact_mappings"):
        try:
            raw = _require_list(definition, key)
        except RoadmapError as error:
            findings.append(str(error))
            collections[key] = []
            continue
        if not all(isinstance(item, dict) for item in raw):
            findings.append(f"roadmap definition {key} entries must be objects")
            collections[key] = []
        else:
            collections[key] = raw  # type: ignore[assignment]

    id_keys = {"phases": "id", "milestones": "id", "gates": "id", "candidate_campaigns": "campaign_id"}
    id_sets: dict[str, set[str]] = {}
    for key, id_key in id_keys.items():
        values: list[str] = []
        for item in collections[key]:
            value = item.get(id_key)
            valid = ID_RE.fullmatch(value) if key == "candidate_campaigns" and isinstance(value, str) else STABLE_ID_RE.fullmatch(value) if isinstance(value, str) else None
            if not valid:
                findings.append(f"{key} entry has invalid stable {id_key}: {value or 'missing'}")
            else:
                values.append(str(value))
        duplicates = sorted({value for value in values if values.count(value) > 1})
        if duplicates:
            findings.append(f"{key} repeats IDs: " + ", ".join(duplicates))
        id_sets[key] = set(values)

    phase_graph: dict[str, list[str]] = {}
    for item in collections["phases"]:
        phase_id = item.get("id")
        if not isinstance(item.get("title"), str) or not str(item.get("title", "")).strip():
            findings.append(f"phase {phase_id or 'missing'} needs a title")
        try:
            dependencies = _require_strings(item.get("depends_on", []), f"phase {phase_id} depends_on")
        except RoadmapError as error:
            findings.append(str(error))
            dependencies = []
        if isinstance(phase_id, str):
            phase_graph[phase_id] = dependencies
    findings.extend(_validate_acyclic(phase_graph, "phase"))

    milestone_graph: dict[str, list[str]] = {}
    for item in collections["milestones"]:
        milestone_id = item.get("id")
        phase = item.get("phase")
        if phase not in id_sets["phases"]:
            findings.append(f"milestone {milestone_id or 'missing'} references unknown phase {phase}")
        if not isinstance(item.get("outcome"), str) or not str(item.get("outcome", "")).strip():
            findings.append(f"milestone {milestone_id or 'missing'} needs an observable outcome")
        try:
            dependencies = _require_strings(item.get("depends_on", []), f"milestone {milestone_id} depends_on")
        except RoadmapError as error:
            findings.append(str(error))
            dependencies = []
        if isinstance(milestone_id, str):
            milestone_graph[milestone_id] = dependencies
    for item in collections["gates"]:
        gate_id = item.get("id")
        if not isinstance(item.get("pass_criteria"), str) or not str(item.get("pass_criteria", "")).strip():
            findings.append(f"gate {gate_id or 'missing'} needs pass_criteria")
        if not isinstance(item.get("evidence_required"), bool):
            findings.append(f"gate {gate_id or 'missing'} needs boolean evidence_required")
        try:
            required = _require_strings(item.get("requires_milestones", []), f"gate {gate_id} requires_milestones")
            unlocked = _require_strings(item.get("unlocks_milestones", []), f"gate {gate_id} unlocks_milestones")
        except RoadmapError as error:
            findings.append(str(error))
            required, unlocked = [], []
        missing = sorted((set(required) | set(unlocked)) - id_sets["milestones"])
        if missing:
            findings.append(f"gate {gate_id or 'missing'} references unknown milestones: " + ", ".join(missing))
        for unlocked_milestone in unlocked:
            milestone_graph.setdefault(unlocked_milestone, []).extend(required)
    findings.extend(_validate_acyclic(milestone_graph, "milestone/gate"))

    campaign_graph: dict[str, list[str]] = {}
    for item in collections["candidate_campaigns"]:
        campaign_id = item.get("campaign_id")
        for key in ("title", "outcome", "completion_gate", "request"):
            if not isinstance(item.get(key), str) or not str(item.get(key, "")).strip():
                findings.append(f"candidate campaign {campaign_id or 'missing'} needs {key}")
        if item.get("milestone") not in id_sets["milestones"]:
            findings.append(f"candidate campaign {campaign_id or 'missing'} references unknown milestone {item.get('milestone')}")
        unlocks = item.get("unlocks_gate", "none")
        if unlocks != "none" and unlocks not in id_sets["gates"]:
            findings.append(f"candidate campaign {campaign_id or 'missing'} references unknown gate {unlocks}")
        try:
            dependencies = _require_strings(item.get("depends_on", []), f"candidate campaign {campaign_id} depends_on")
            _require_strings(item.get("primary_focus_areas", []), f"candidate campaign {campaign_id} primary_focus_areas")
            _require_strings(item.get("supporting_focus_areas", []), f"candidate campaign {campaign_id} supporting_focus_areas")
        except RoadmapError as error:
            findings.append(str(error))
            dependencies = []
        if isinstance(campaign_id, str):
            campaign_graph[campaign_id] = [item for item in dependencies if item in id_sets["candidate_campaigns"]]
    findings.extend(_validate_acyclic(campaign_graph, "candidate campaign"))
    mapping_paths: list[str] = []
    allowed_classifications = {"completed", "active", "remaining", "superseded", "excluded", "uncertain"}
    for mapping in collections["artifact_mappings"]:
        path = mapping.get("path")
        classification = mapping.get("classification")
        if not isinstance(path, str) or not path.startswith("work/"):
            findings.append("artifact mapping needs a work/ path")
        else:
            mapping_paths.append(path)
        if classification not in allowed_classifications:
            findings.append(f"artifact mapping {path or 'missing'} has invalid classification")
        phase = mapping.get("phase")
        milestone = mapping.get("milestone")
        if phase is not None and phase not in id_sets["phases"]:
            findings.append(f"artifact mapping {path or 'missing'} references unknown phase {phase}")
        if milestone is not None and milestone not in id_sets["milestones"]:
            findings.append(f"artifact mapping {path or 'missing'} references unknown milestone {milestone}")
        if not isinstance(mapping.get("evidence"), str) or not str(mapping.get("evidence", "")).strip():
            findings.append(f"artifact mapping {path or 'missing'} needs concrete evidence")
        state = mapping.get("state_token")
        if not isinstance(state, str) or not re.fullmatch(r"[0-9a-f]{16}", state):
            findings.append(f"artifact mapping {path or 'missing'} needs a 16-character state_token")
    duplicates = sorted({path for path in mapping_paths if mapping_paths.count(path) > 1})
    if duplicates:
        findings.append("artifact mappings repeat paths: " + ", ".join(duplicates))
    return sorted(set(findings))


def validate_roadmap(roadmap: Roadmap) -> list[str]:
    findings = validate_definition(roadmap.definition)
    if roadmap.fields.get("Type") != "program-roadmap":
        findings.append(f"{roadmap.path.name} Type must be program-roadmap")
    if roadmap.status not in ROADMAP_STATUSES:
        findings.append(f"{roadmap.path.name} has invalid Status {roadmap.status!r}")
    if not ID_RE.fullmatch(roadmap.roadmap_id):
        findings.append(f"{roadmap.path.name} has invalid Roadmap ID")
    if roadmap.revision < 1:
        findings.append(f"{roadmap.path.name} has invalid Revision")
    expected = proposal_token(roadmap.definition, roadmap.fields.get("Source State Token", ""))
    if roadmap.fields.get("Proposal Token") != expected:
        findings.append(f"{roadmap.path.name} has stale or invalid Proposal Token")
    return findings


def validate_all(workspace: Path) -> list[str]:
    findings: list[str] = []
    current: dict[str, list[Roadmap]] = {}
    seen: set[tuple[str, int]] = set()
    for roadmap in load_roadmaps(workspace):
        findings.extend(validate_roadmap(roadmap))
        key = (roadmap.roadmap_id, roadmap.revision)
        if key in seen:
            findings.append(f"duplicate roadmap revision {roadmap.roadmap_id} r{roadmap.revision}")
        seen.add(key)
        if roadmap.status in CURRENT_STATUSES:
            current.setdefault(roadmap.roadmap_id, []).append(roadmap)
    for roadmap_id, items in current.items():
        if len(items) > 1:
            findings.append(f"roadmap {roadmap_id} has more than one current approved revision")
    return sorted(set(findings))


def _artifact_classification(status: str, kind: str) -> str:
    normalized = status.strip().lower()
    if normalized in {"complete", "completed", "done", "decided", "accepted"}:
        return "completed"
    if normalized in {"working", "blocked", "active", "proposed"}:
        return "active"
    if normalized in {"queued", "deferred"}:
        return "remaining"
    if normalized in {"superseded", "abandoned"}:
        return "superseded"
    if normalized == "excluded" or kind == "focus-area-catalog":
        return "excluded"
    return "uncertain"


def _section_lines(path: Path, name: str) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    heading = f"## {name}".lower()
    start = next((index + 1 for index, line in enumerate(lines) if line.strip().lower() == heading), None)
    if start is None:
        return []
    result: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        if line.strip():
            result.append(line.strip())
    return result


def discover_project(workspace: Path) -> dict[str, Any]:
    work = workspace / "work"
    artifacts = discover_artifacts(work) if work.is_dir() else []
    evidence = []
    for artifact in artifacts:
        if artifact.kind() == "program-roadmap":
            continue
        evidence.append(
            {
                "path": artifact.path.as_posix(),
                "type": artifact.kind() or "unknown",
                "status": artifact.status() or "unknown",
                "classification": _artifact_classification(artifact.status(), artifact.kind()),
                "title": artifact.title,
            }
        )
    maps = [item for item in evidence if item["type"] == "project-map"]
    for item in maps:
        path = workspace / item["path"]
        item["purpose"] = " ".join(_section_lines(path, "Purpose")) or None
        item["workstreams"] = _section_lines(path, "Workstreams")
    owner_work = [
        item for item in evidence
        if item["type"] not in {"focus-area-catalog"} and not item["path"].startswith("work/00-campaigns/")
    ]
    entry_mode = "greenfield" if len(owner_work) <= 1 and not any(item["type"] == "campaign" for item in evidence) else "existing"
    counts = {name: sum(item["classification"] == name for item in evidence) for name in ("completed", "active", "remaining", "superseded", "excluded", "uncertain")}
    canonical_docs = [
        path.relative_to(workspace).as_posix()
        for path in [workspace / "README.md", *sorted((workspace / "docs").glob("*.md"))]
        if path.is_file()
    ]
    indexed_paths: set[str] = set()
    index_error: str | None = None
    index_path = work / "index.json"
    if index_path.is_file():
        try:
            index_payload = json.loads(index_path.read_text(encoding="utf-8"))
            indexed_paths = {
                str(item["path"])
                for item in index_payload.get("artifacts", [])
                if isinstance(item, dict) and isinstance(item.get("path"), str)
            }
        except (json.JSONDecodeError, AttributeError) as error:
            index_error = str(error)
    discovered_paths = {item["path"] for item in evidence}
    index_drift = {
        "missing_from_index": sorted(discovered_paths - indexed_paths) if index_path.is_file() else [],
        "missing_from_work_tree": sorted(indexed_paths - discovered_paths),
        "error": index_error,
    }
    return {
        "entry_mode": entry_mode,
        "canonical_docs": canonical_docs,
        "project_maps": maps,
        "artifacts": evidence,
        "classification_counts": counts,
        "index_drift": index_drift,
    }


def develop_payload(
    workspace: Path,
    roadmap_id: str | None,
    project_map: str | None = None,
) -> dict[str, Any]:
    discovery = discover_project(workspace)
    maps = discovery["project_maps"]
    for item in maps:
        item["map_token"] = map_token(workspace / item["path"])
    candidates = [item for item in maps if item["status"] in {"active", "approved", "proposed"}]
    if project_map:
        selected = next((item for item in candidates if item["path"] == project_map), None)
        if selected is None:
            raise RoadmapError("selected project map is not an active, approved, or proposed work/maps artifact")
    else:
        selected = candidates[0] if len(candidates) == 1 else None
    blockers: list[str] = []
    if not candidates:
        blockers.append("establish a project map before proposing a Program Roadmap")
    elif len(candidates) > 1 and selected is None:
        blockers.append("select one source project map explicitly")
    elif discovery["entry_mode"] == "greenfield" and selected["status"] != "approved":
        blockers.append("approve the initial greenfield project map with an exact map token")
    source = source_state_token(workspace, roadmap_id)
    mapping_preview = [
        {
            "path": item["path"],
            "classification": item["classification"],
            "phase": None,
            "milestone": None,
            "evidence": f"Type {item['type']}; Status {item['status']}",
            "state_token": _file_token(workspace / item["path"]),
            "mapping_state": "unmapped",
            "conflicts": ["ambiguous lifecycle evidence"] if item["classification"] == "uncertain" else [],
        }
        for item in discovery["artifacts"]
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "tool-shed-roadmap-development",
        "writes_performed": False,
        "source_state_token": source,
        "roadmap_id": roadmap_id,
        "selected_project_map": selected["path"] if selected else None,
        "blockers": blockers,
        **discovery,
        "priority_order": [
            "hard dependencies",
            "unresolved decisions",
            "safety and irreversibility",
            "shared enabling value",
            "thin vertical slice",
            "cost of late assumption discovery",
        ],
        "mapping_preview": mapping_preview,
        "proposal_skeleton": {
            "schema_version": SCHEMA_VERSION,
            "kind": PROPOSAL_KIND,
            "roadmap_id": roadmap_id,
            "revision": 1,
            "title": None,
            "project_map": selected["path"] if selected else None,
            "source_state_token": source,
            "definition": {
                "desired_outcome": "",
                "non_goals": "",
                "constraints": "",
                "authority_boundaries": "",
                "assumptions": [],
                "unknowns": [],
                "decisions": [],
                "phases": [],
                "milestones": [],
                "gates": [],
                "candidate_campaigns": [],
                "artifact_mappings": mapping_preview,
            },
        },
    }


def _replace_header(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}:.*$", re.MULTILINE)
    if not pattern.search(text):
        raise RoadmapError(f"artifact has no {key} header")
    return pattern.sub(f"{key}: {value}", text, count=1)


def approve_map(workspace: Path, relative: str, expected: str) -> dict[str, Any]:
    path = (workspace / relative).resolve()
    maps = (workspace / "work" / "maps").resolve()
    if maps not in path.parents or not path.is_file():
        raise RoadmapError("project map must be an existing file under work/maps/")
    if expected != map_token(path):
        raise RoadmapError(f"stale project-map state: expected {expected}, current {map_token(path)}")
    text = path.read_text(encoding="utf-8")
    _, fields = parse_headers(text)
    status = fields.get("Status", "")
    if status not in {"active", "proposed", "approved"}:
        raise RoadmapError(f"project map status {status!r} cannot be approved")
    text = _replace_header(text, "Status", "approved")
    text = _replace_header(text, "Updated", date.today().isoformat())
    text = _replace_header(text, "Next Action", "develop an exact Program Roadmap proposal")
    campaign_queue.ensure_tree(workspace)
    campaign_queue.apply_transaction(workspace, {path: text})
    refresh_indexes(workspace)
    return {"path": relative, "status": "approved", "map_token": map_token(path)}


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RoadmapError("manifest must be a JSON object")
    return payload


def require_fresh_mappings(workspace: Path, definition: dict[str, Any]) -> None:
    for mapping in definition["artifact_mappings"]:
        path = workspace / mapping["path"]
        if not path.is_file():
            raise RoadmapError(f"mapped artifact no longer exists: {mapping['path']}")
        current = _file_token(path)
        if mapping["state_token"] != current:
            raise RoadmapError(
                f"stale mapped artifact {mapping['path']}: expected {mapping['state_token']}, current {current}"
            )


def propose(workspace: Path, manifest_path: Path, expected: str) -> dict[str, Any]:
    payload = _load_json(manifest_path)
    if payload.get("schema_version") != SCHEMA_VERSION or payload.get("kind") != PROPOSAL_KIND:
        raise RoadmapError("unsupported roadmap proposal manifest")
    roadmap_id = payload.get("roadmap_id")
    revision = payload.get("revision")
    title = payload.get("title")
    project_map = payload.get("project_map")
    definition = payload.get("definition")
    if not isinstance(roadmap_id, str) or not ID_RE.fullmatch(roadmap_id):
        raise RoadmapError("proposal requires a lowercase kebab-case roadmap_id")
    if not isinstance(revision, int) or revision < 1:
        raise RoadmapError("proposal revision must be a positive integer")
    if not isinstance(title, str) or not title.strip() or not isinstance(definition, dict):
        raise RoadmapError("proposal requires title and definition")
    current_source = source_state_token(workspace, roadmap_id)
    if expected != current_source or payload.get("source_state_token") != current_source:
        raise RoadmapError(f"stale roadmap source state: expected {expected}, current {current_source}")
    project_map_path = workspace / str(project_map)
    if not isinstance(project_map, str) or not project_map.startswith("work/maps/") or not project_map_path.is_file():
        raise RoadmapError("proposal requires an existing work/maps project_map")
    _, selected_map_fields = parse_headers(project_map_path.read_text(encoding="utf-8"))
    if selected_map_fields.get("Status") not in {"active", "approved"}:
        raise RoadmapError("proposal project map must be active or approved")
    discovery = discover_project(workspace)
    if discovery["entry_mode"] == "greenfield":
        _, map_fields = parse_headers(project_map_path.read_text(encoding="utf-8"))
        if map_fields.get("Status") != "approved":
            raise RoadmapError("greenfield project map must be approved before roadmap proposal")
    findings = validate_definition(definition)
    if findings:
        raise RoadmapError("invalid roadmap proposal: " + "; ".join(findings))
    require_fresh_mappings(workspace, definition)
    if discovery["entry_mode"] == "existing":
        expected_paths = {item["path"] for item in discovery["artifacts"]}
        mapped_paths = {item["path"] for item in definition["artifact_mappings"]}
        if expected_paths != mapped_paths:
            missing = sorted(expected_paths - mapped_paths)
            extra = sorted(mapped_paths - expected_paths)
            details = []
            if missing:
                details.append("missing " + ", ".join(missing))
            if extra:
                details.append("unknown " + ", ".join(extra))
            raise RoadmapError("existing-project artifact mapping is not exact: " + "; ".join(details))
    existing = [item for item in load_roadmaps(workspace) if item.roadmap_id == roadmap_id]
    if any(item.revision == revision for item in existing):
        raise RoadmapError(f"roadmap revision already exists: {roadmap_id} r{revision}")
    if existing and revision != max(item.revision for item in existing) + 1:
        raise RoadmapError("roadmap revision must increment the latest revision by one")
    if not existing and revision != 1:
        raise RoadmapError("the first roadmap revision must be 1")
    supersedes = "none"
    if existing:
        prior = max(existing, key=lambda item: item.revision)
        if prior.status not in CURRENT_STATUSES:
            raise RoadmapError("a new revision must supersede a current approved roadmap")
        supersedes = prior.path.relative_to(workspace).as_posix()
    token = proposal_token(definition, current_source)
    milestone_ids = [str(item["id"]) for item in definition["milestones"]]
    roadmap = Roadmap(
        _roadmap_path(workspace, roadmap_id, revision),
        title.strip(),
        {
            "Status": "proposed",
            "Type": "program-roadmap",
            "Updated": date.today().isoformat(),
            "Next Action": f"approve exact proposal token {token}",
            "Roadmap ID": roadmap_id,
            "Revision": str(revision),
            "Source Project Map": project_map,
            "Source State Token": current_source,
            "Proposal Token": token,
            "Approved": "none",
            "Current Milestone": milestone_ids[0] if milestone_ids else "none",
            "Supersedes": supersedes,
            "Superseded By": "none",
        },
        definition,
    )
    campaign_queue.ensure_tree(workspace)
    campaign_queue.apply_transaction(workspace, {roadmap.path: render_roadmap(roadmap)})
    refresh_indexes(workspace)
    return roadmap_payload(workspace, parse_roadmap(roadmap.path))


def find_roadmap(workspace: Path, roadmap_id: str, revision: int | None = None) -> Roadmap:
    matches = [item for item in load_roadmaps(workspace) if item.roadmap_id == roadmap_id]
    if revision is not None:
        matches = [item for item in matches if item.revision == revision]
    if not matches:
        raise RoadmapError(f"unknown roadmap: {roadmap_id}" + (f" r{revision}" if revision else ""))
    return max(matches, key=lambda item: item.revision)


def approve(workspace: Path, roadmap_id: str, revision: int, expected: str, token: str) -> dict[str, Any]:
    roadmap = find_roadmap(workspace, roadmap_id, revision)
    if roadmap.status != "proposed":
        raise RoadmapError("only a proposed roadmap can be approved")
    current_source = source_state_token(workspace, roadmap_id)
    if expected != current_source or roadmap.fields.get("Source State Token") != current_source:
        raise RoadmapError(f"stale roadmap source state: expected {expected}, current {current_source}")
    if token != roadmap.fields.get("Proposal Token"):
        raise RoadmapError("approval token does not match the exact roadmap proposal")
    require_fresh_mappings(workspace, roadmap.definition)
    changes: dict[Path, str | None] = {}
    prior_path = roadmap.fields.get("Supersedes", "none")
    if prior_path != "none":
        prior = parse_roadmap(workspace / prior_path)
        if prior.status not in CURRENT_STATUSES:
            raise RoadmapError("superseded roadmap revision is no longer current")
        prior.fields["Status"] = "superseded"
        prior.fields["Updated"] = date.today().isoformat()
        prior.fields["Next Action"] = "none"
        prior.fields["Superseded By"] = roadmap.path.relative_to(workspace).as_posix()
        changes[prior.path] = render_roadmap(prior)
    roadmap.fields["Status"] = "approved"
    roadmap.fields["Updated"] = date.today().isoformat()
    roadmap.fields["Approved"] = date.today().isoformat()
    roadmap.fields["Next Action"] = f"derive campaigns for milestone {roadmap.fields['Current Milestone']}"
    changes[roadmap.path] = render_roadmap(roadmap)
    campaign_queue.apply_transaction(workspace, changes)
    refresh_indexes(workspace)
    return roadmap_payload(workspace, parse_roadmap(roadmap.path))


def _campaigns_for_roadmap(workspace: Path, roadmap_id: str) -> list[campaign_queue.Campaign]:
    if not campaign_queue.campaign_root(workspace).is_dir():
        return []
    return [
        item for item in campaign_queue.load_all(workspace).values()
        if item.fields.get("Roadmap") == roadmap_id
    ]


def _progress(workspace: Path, roadmap: Roadmap) -> dict[str, Any]:
    campaigns = _campaigns_for_roadmap(workspace, roadmap.roadmap_id)
    milestones: dict[str, dict[str, Any]] = {}
    for milestone in roadmap.definition["milestones"]:
        milestone_id = milestone["id"]
        linked = [item for item in campaigns if item.fields.get("Milestone") == milestone_id]
        expected = [item for item in roadmap.definition["candidate_campaigns"] if item["milestone"] == milestone_id]
        complete = [item for item in linked if item.status == "complete"]
        materialized_ids = {item.campaign_id for item in linked}
        expected_ids = {item["campaign_id"] for item in expected}
        done = bool(expected_ids) and expected_ids <= materialized_ids and len(complete) == len(expected_ids)
        milestones[milestone_id] = {
            "outcome": milestone["outcome"],
            "expected_campaigns": sorted(expected_ids),
            "materialized_campaigns": sorted(materialized_ids),
            "completed_campaigns": sorted(item.campaign_id for item in complete),
            "status": "complete" if done else "active" if linked else "planned",
        }
    gates: dict[str, dict[str, Any]] = {}
    for gate in roadmap.definition["gates"]:
        required = gate["requires_milestones"]
        milestone_complete = all(milestones[item]["status"] == "complete" for item in required)
        evidence = [
            item.fields.get("Completion Evidence", "none")
            for item in campaigns
            if item.status == "complete" and item.fields.get("Milestone") in required
        ]
        evidence_ok = not gate["evidence_required"] or (bool(evidence) and all(item != "none" for item in evidence))
        gates[gate["id"]] = {
            "pass_criteria": gate["pass_criteria"],
            "requires_milestones": required,
            "evidence": evidence,
            "status": "passed" if milestone_complete and evidence_ok else "waiting",
        }
    return {"milestones": milestones, "gates": gates}


def roadmap_payload(workspace: Path, roadmap: Roadmap) -> dict[str, Any]:
    progress = _progress(workspace, roadmap)
    computed_current = next(
        (
            milestone["id"]
            for milestone in roadmap.definition["milestones"]
            if progress["milestones"][milestone["id"]]["status"] != "complete"
        ),
        None,
    )
    return {
        "roadmap_id": roadmap.roadmap_id,
        "revision": roadmap.revision,
        "status": roadmap.status,
        "path": roadmap.path.relative_to(workspace).as_posix(),
        "roadmap_token": _file_token(roadmap.path),
        "proposal_token": roadmap.fields.get("Proposal Token"),
        "source_state_token": roadmap.fields.get("Source State Token"),
        "current_source_state_token": source_state_token(workspace, roadmap.roadmap_id),
        "source_drift": roadmap.fields.get("Source State Token") != source_state_token(workspace, roadmap.roadmap_id),
        "computed_current_milestone": computed_current,
        **progress,
        "findings": validate_roadmap(roadmap),
    }


def derive(workspace: Path, roadmap_id: str, milestone_id: str) -> dict[str, Any]:
    roadmap = find_roadmap(workspace, roadmap_id)
    if roadmap.status not in {"approved", "executing"}:
        raise RoadmapError("campaigns can be derived only from an approved or executing roadmap")
    milestones = {item["id"]: item for item in roadmap.definition["milestones"]}
    if milestone_id not in milestones:
        raise RoadmapError(f"unknown milestone: {milestone_id}")
    campaigns = campaign_queue.load_all(workspace)
    candidates = [item for item in roadmap.definition["candidate_campaigns"] if item["milestone"] == milestone_id]
    existing = sorted(item["campaign_id"] for item in candidates if item["campaign_id"] in campaigns)
    operations = [item for item in candidates if item["campaign_id"] not in campaigns]
    progress = _progress(workspace, roadmap)
    blockers = [
        f"milestone dependency {item} is not complete"
        for item in milestones[milestone_id].get("depends_on", [])
        if progress["milestones"][item]["status"] != "complete"
    ]
    blockers.extend(
        f"gate {gate['id']} has not passed"
        for gate in roadmap.definition["gates"]
        if milestone_id in gate["unlocks_milestones"] and progress["gates"][gate["id"]]["status"] != "passed"
    )
    order = campaign_queue.queue_order(workspace)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "kind": CAMPAIGN_PLAN_KIND,
        "roadmap_id": roadmap.roadmap_id,
        "roadmap_revision": roadmap.revision,
        "roadmap_token": _file_token(roadmap.path),
        "campaign_state_token": campaign_queue.state_token(workspace),
        "milestone": milestone_id,
        "milestone_outcome": milestones[milestone_id]["outcome"],
        "existing_campaigns": existing,
        "campaigns": operations,
        "readiness": "ready" if not blockers else "waiting",
        "readiness_blockers": blockers,
        "proposed_queue_positions": {
            item["campaign_id"]: len(order) + index
            for index, item in enumerate(operations, start=1)
        },
        "writes_performed": False,
    }
    payload["manifest_token"] = _token(payload)
    return payload


def apply_campaign_plan(workspace: Path, manifest_path: Path, expected: str) -> dict[str, Any]:
    manifest = _load_json(manifest_path)
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("kind") != CAMPAIGN_PLAN_KIND:
        raise RoadmapError("unsupported campaign-plan manifest")
    supplied_token = manifest.pop("manifest_token", None)
    computed = _token(manifest)
    manifest["manifest_token"] = supplied_token
    if supplied_token != computed or expected != computed:
        raise RoadmapError("campaign-plan approval does not match the exact manifest")
    roadmap = find_roadmap(workspace, str(manifest.get("roadmap_id")), int(manifest.get("roadmap_revision", 0)))
    if roadmap.status not in {"approved", "executing"}:
        raise RoadmapError("campaign plan requires an approved roadmap")
    if manifest.get("roadmap_token") != _file_token(roadmap.path):
        raise RoadmapError("stale roadmap revision; derive a fresh campaign plan")
    if manifest.get("campaign_state_token") != campaign_queue.state_token(workspace):
        raise RoadmapError("stale campaign queue; derive a fresh campaign plan")
    if manifest.get("readiness") != "ready" or manifest.get("readiness_blockers"):
        raise RoadmapError("campaign plan milestone is not ready for materialization")
    candidates = manifest.get("campaigns")
    if not isinstance(candidates, list) or not all(isinstance(item, dict) for item in candidates):
        raise RoadmapError("campaign plan campaigns must be a list of objects")
    canonical = {
        item["campaign_id"]: item
        for item in roadmap.definition["candidate_campaigns"]
        if item["milestone"] == manifest.get("milestone")
    }
    if candidates != [item for item in canonical.values() if item["campaign_id"] not in campaign_queue.load_all(workspace)]:
        raise RoadmapError("campaign plan does not exactly match the approved roadmap candidates")
    campaigns = campaign_queue.load_all(workspace)
    order = campaign_queue.queue_order(workspace)
    changes: dict[Path, str | None] = {}
    for candidate in candidates:
        campaign_id = candidate["campaign_id"]
        if campaign_id in campaigns:
            raise RoadmapError(f"campaign already exists: {campaign_id}")
        dependencies = candidate.get("depends_on", [])
        missing = sorted(set(dependencies) - set(campaigns) - set(canonical))
        if missing:
            raise RoadmapError("campaign plan has missing dependencies: " + ", ".join(missing))
        prefixed_number = campaign_queue.NUMBERED_ID_RE.match(campaign_id)
        campaign_number = (
            prefixed_number.group(1)
            if prefixed_number
            else campaign_queue.next_campaign_number(campaigns)
        )
        text = campaign_queue._campaign_text(
            campaign_id,
            candidate["title"],
            candidate["outcome"],
            candidate["completion_gate"],
            dependencies,
            candidate.get("decision", "none"),
            "none",
            "none",
            candidate.get("primary_focus_areas", []),
            candidate.get("supporting_focus_areas", []),
            campaign_number,
        ).replace("Add detailed execution context here.", candidate["request"])
        path = (
            campaign_queue.campaign_root(workspace)
            / "active"
            / campaign_queue.campaign_filename(campaign_id, campaign_number)
        )
        item = campaign_queue.parse_campaign_text(path, text)
        item.fields["Roadmap"] = roadmap.roadmap_id
        item.fields["Roadmap Revision"] = str(roadmap.revision)
        item.fields["Milestone"] = str(candidate["milestone"])
        item.fields["Unlocks Gate"] = str(candidate.get("unlocks_gate", "none"))
        text = campaign_queue.render_campaign(item)
        campaigns[campaign_id] = item
        order.append(campaign_id)
        changes[path] = text
    roadmap.fields["Status"] = "executing"
    roadmap.fields["Updated"] = date.today().isoformat()
    roadmap.fields["Next Action"] = "execute the first ready roadmap campaign through ts: next"
    changes[roadmap.path] = render_roadmap(roadmap)
    changes.update(campaign_queue._refresh_changes(workspace, order, campaigns))
    campaign_queue.apply_transaction(workspace, changes)
    refresh_indexes(workspace)
    return {
        "writes_performed": True,
        "created_campaigns": [item["campaign_id"] for item in candidates],
        "roadmap": roadmap_payload(workspace, parse_roadmap(roadmap.path)),
        "campaign_state_token": campaign_queue.state_token(workspace),
    }


def overview(workspace: Path) -> dict[str, Any]:
    discovery = discover_project(workspace)
    roadmaps = load_roadmaps(workspace)
    current = sorted((item for item in roadmaps if item.status in CURRENT_STATUSES), key=lambda item: (item.roadmap_id, item.revision))
    queue = campaign_queue.status_payload(workspace) if campaign_queue.campaign_root(workspace).is_dir() else None
    roadmap_states = [roadmap_payload(workspace, item) for item in current]
    strategic = None
    if roadmap_states:
        state = roadmap_states[-1]
        waiting_gates = [gate_id for gate_id, gate in state["gates"].items() if gate["status"] != "passed"]
        strategic = f"satisfy gate {waiting_gates[0]}" if waiting_gates else "review roadmap completion"
    execution = queue.get("working", [None])[0] if queue and queue.get("working") else queue.get("next") if queue else None
    focus_coverage: dict[str, Any] = {}
    catalog = campaign_queue.load_focus_area_catalog(workspace)
    if catalog is not None:
        all_campaigns = campaign_queue.load_all(workspace)
        for focus_id, area in catalog.areas.items():
            focus_coverage[focus_id] = {
                "name": area.name,
                "primary_campaigns": sorted(
                    item.campaign_id for item in all_campaigns.values()
                    if focus_id in item.primary_focus_areas
                ),
                "supporting_campaigns": sorted(
                    item.campaign_id for item in all_campaigns.values()
                    if focus_id in item.supporting_focus_areas
                ),
            }
    drift = validate_all(workspace)
    if any(discovery["index_drift"].get(key) for key in ("missing_from_index", "missing_from_work_tree", "error")):
        drift.append("work index does not match the discovered artifact surface")
    if queue:
        drift.extend(f"campaign queue: {item}" for item in queue.get("findings", []))
    if any(item["source_drift"] for item in roadmap_states):
        drift.append("approved roadmap source inputs changed")
    return {
        "schema_version": SCHEMA_VERSION,
        "writes_performed": False,
        "project_maps": discovery["project_maps"],
        "roadmaps": roadmap_states,
        "focus_area_catalog": "work/focus-areas.md" if (workspace / "work" / "focus-areas.md").is_file() else None,
        "focus_area_coverage": focus_coverage,
        "index_drift": discovery["index_drift"],
        "campaign_queue": queue,
        "recommended_next": {"strategic": strategic, "execution": execution},
        "drift_findings": sorted(set(drift)),
    }


def review_payload(workspace: Path, roadmap_id: str) -> dict[str, Any]:
    roadmap = find_roadmap(workspace, roadmap_id)
    payload = roadmap_payload(workspace, roadmap)
    payload["review"] = {
        "assumptions": roadmap.definition["assumptions"],
        "unknowns": roadmap.definition["unknowns"],
        "decisions": roadmap.definition["decisions"],
        "authority_boundaries": roadmap.definition["authority_boundaries"],
        "revision_recommended": payload["source_drift"] or bool(payload["findings"]),
    }
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--json", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    develop = commands.add_parser("develop")
    develop.add_argument("--roadmap-id")
    develop.add_argument("--project-map")
    approve_project_map = commands.add_parser("approve-map")
    approve_project_map.add_argument("path")
    approve_project_map.add_argument("--expect", required=True)
    approve_project_map.add_argument("--project-binding", required=True)
    propose_parser = commands.add_parser("propose")
    propose_parser.add_argument("--manifest", required=True)
    propose_parser.add_argument("--expect", required=True)
    propose_parser.add_argument("--project-binding", required=True)
    approve_parser = commands.add_parser("approve")
    approve_parser.add_argument("roadmap_id")
    approve_parser.add_argument("--revision", type=int, required=True)
    approve_parser.add_argument("--expect", required=True)
    approve_parser.add_argument("--proposal-token", required=True)
    approve_parser.add_argument("--project-binding", required=True)
    derive_parser = commands.add_parser("derive")
    derive_parser.add_argument("roadmap_id")
    derive_parser.add_argument("--milestone", required=True)
    apply_parser = commands.add_parser("apply-campaign-plan")
    apply_parser.add_argument("--manifest", required=True)
    apply_parser.add_argument("--expect", required=True)
    apply_parser.add_argument("--project-binding", required=True)
    status = commands.add_parser("status")
    status.add_argument("roadmap_id", nargs="?")
    review = commands.add_parser("review")
    review.add_argument("roadmap_id")
    commands.add_parser("overview")
    commands.add_parser("validate")
    for child in commands.choices.values():
        child.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    workspace = Path(args.workspace).expanduser().resolve()
    try:
        if args.command in {"approve-map", "propose", "approve", "apply-campaign-plan"}:
            require_project_binding(
                workspace,
                args.project_binding,
                operation="program-roadmap",
            )
        if args.command == "develop":
            payload: object = develop_payload(workspace, args.roadmap_id, args.project_map)
        elif args.command == "approve-map":
            payload = approve_map(workspace, args.path, args.expect)
        elif args.command == "propose":
            payload = propose(workspace, Path(args.manifest).expanduser().resolve(), args.expect)
        elif args.command == "approve":
            payload = approve(workspace, args.roadmap_id, args.revision, args.expect, args.proposal_token)
        elif args.command == "derive":
            payload = derive(workspace, args.roadmap_id, args.milestone)
        elif args.command == "apply-campaign-plan":
            payload = apply_campaign_plan(workspace, Path(args.manifest).expanduser().resolve(), args.expect)
        elif args.command == "status":
            if args.roadmap_id:
                payload = roadmap_payload(workspace, find_roadmap(workspace, args.roadmap_id))
            else:
                payload = [roadmap_payload(workspace, item) for item in load_roadmaps(workspace)]
        elif args.command == "overview":
            payload = overview(workspace)
        elif args.command == "review":
            payload = review_payload(workspace, args.roadmap_id)
        else:
            findings = validate_all(workspace)
            payload = {"valid": not findings, "findings": findings}
    except (
        RoadmapError,
        campaign_queue.CampaignError,
        ProjectIdentityError,
        OSError,
        json.JSONDecodeError,
    ) as error:
        print(f"Program Roadmap operation failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
