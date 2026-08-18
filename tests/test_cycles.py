from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import campaign_queue  # noqa: E402
import program_roadmap  # noqa: E402
from tests.test_scripts import run_script  # noqa: E402


class CycleStateTests(unittest.TestCase):
    def install(self, workspace: Path) -> None:
        run_script("scripts/install_into_workspace.py", str(workspace))

    def status(self, workspace: Path) -> dict[str, object]:
        return json.loads(
            run_script(
                "scripts/campaign_queue.py",
                "--workspace",
                str(workspace),
                "status",
                "--json",
            ).stdout
        )

    def add(self, workspace: Path, campaign_id: str) -> None:
        state = self.status(workspace)
        run_script(
            "scripts/campaign_queue.py",
            "--workspace",
            str(workspace),
            "add",
            campaign_id,
            campaign_id.replace("-", " ").title(),
            "--outcome",
            f"deliver {campaign_id}",
            "--completion-gate",
            f"{campaign_id} verified",
            "--expect",
            str(state["state_token"]),
        )

    def campaign_record(
        self,
        workspace: Path,
        *,
        number: str,
        campaign_id: str,
        milestone: str,
        unlocks_gate: str,
        status: str = "complete",
    ) -> Path:
        folder = "completed" if status == "complete" else status
        path = (
            workspace
            / "work"
            / "00-campaigns"
            / folder
            / campaign_queue.campaign_filename(campaign_id, number)
        )
        text = campaign_queue._campaign_text(
            campaign_id,
            campaign_id.replace("-", " ").title(),
            f"deliver {campaign_id}",
            f"{campaign_id} verified",
            [],
            "none",
            "none",
            "none",
            [],
            [],
            number,
        )
        item = campaign_queue.parse_campaign_text(path, text)
        item.fields.update(
            {
                "Status": status,
                "Next Action": "none" if status == "complete" else "owner decides when to resume",
                "Completion Evidence": f"tests:{campaign_id}" if status == "complete" else "none",
                "Completion Date": "2026-08-18" if status == "complete" else "",
                "Completion Order": str(int(number)) if status == "complete" else "",
                "Disposition": "completed" if status == "complete" else "deferred",
                "Roadmap": "demo",
                "Roadmap Revision": "1",
                "Milestone": milestone,
                "Unlocks Gate": unlocks_gate,
            }
        )
        path.write_text(campaign_queue.render_campaign(item), encoding="utf-8")
        return path

    def roadmap_definition(self) -> dict[str, object]:
        campaigns = []
        for milestone, campaign_id, gate in (
            ("M1", "finish-m1", "G1"),
            ("M2", "finish-m2", "G2"),
        ):
            campaigns.append(
                {
                    "campaign_id": campaign_id,
                    "title": campaign_id,
                    "outcome": f"complete {milestone}",
                    "completion_gate": f"{milestone} verified",
                    "request": f"Complete {milestone}.",
                    "milestone": milestone,
                    "depends_on": [] if milestone == "M1" else ["finish-m1"],
                    "primary_focus_areas": [],
                    "supporting_focus_areas": [],
                    "decision": "none",
                    "unlocks_gate": gate,
                }
            )
        return {
            "desired_outcome": "finish both milestones",
            "non_goals": "none",
            "constraints": "preserve approval boundaries",
            "authority_boundaries": "derivation does not approve materialization",
            "assumptions": [],
            "unknowns": [],
            "decisions": [],
            "phases": [{"id": "P1", "title": "Delivery", "depends_on": []}],
            "milestones": [
                {"id": "M1", "title": "First", "phase": "P1", "depends_on": [], "outcome": "M1 complete"},
                {"id": "M2", "title": "Second", "phase": "P1", "depends_on": ["M1"], "outcome": "M2 complete"},
            ],
            "gates": [
                {"id": "G1", "title": "First gate", "requires_milestones": ["M1"], "unlocks_milestones": ["M2"], "pass_criteria": "M1 evidence", "evidence_required": True},
                {"id": "G2", "title": "Final gate", "requires_milestones": ["M2"], "unlocks_milestones": [], "pass_criteria": "M2 evidence", "evidence_required": True},
            ],
            "candidate_campaigns": campaigns,
            "artifact_mappings": [],
        }

    def write_roadmap(self, workspace: Path) -> program_roadmap.Roadmap:
        definition = self.roadmap_definition()
        source_token = program_roadmap.source_state_token(workspace, "demo")
        roadmap = program_roadmap.Roadmap(
            workspace / "work" / "roadmaps" / "roadmap-demo.md",
            "Demo",
            {
                "Status": "executing",
                "Type": "program-roadmap",
                "Updated": "2026-08-18",
                "Next Action": "continue milestone waves",
                "Roadmap ID": "demo",
                "Revision": "1",
                "Source Project Map": "none",
                "Source State Token": source_token,
                "Proposal Token": program_roadmap.proposal_token(definition, source_token),
                "Approved": "2026-08-18",
                "Current Milestone": "M2",
                "Supersedes": "none",
                "Superseded By": "none",
            },
            definition,
        )
        roadmap.path.write_text(program_roadmap.render_roadmap(roadmap), encoding="utf-8")
        return roadmap

    def test_origins_are_computed_and_status_next_overview_share_one_capsule(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            self.install(workspace)
            self.add(workspace, "owner-work")
            state = self.status(workspace)
            self.assertEqual(state["cycle_state"]["dimensions"]["work_origin"], "owner-originated")

            next_payload = json.loads(
                run_script(
                    "scripts/campaign_queue.py", "--workspace", str(workspace), "next", "--json"
                ).stdout
            )
            overview = json.loads(
                run_script(
                    "scripts/program_roadmap.py", "--workspace", str(workspace), "overview", "--json"
                ).stdout
            )
            self.assertEqual(state["cycle_state"], next_payload["cycle_state"])
            self.assertEqual(state["cycle_state"], overview["cycle_state"])
            rendered = program_roadmap.render_cycle_state(state["cycle_state"])
            for arguments in (
                ("scripts/campaign_queue.py", "--workspace", str(workspace), "status"),
                ("scripts/campaign_queue.py", "--workspace", str(workspace), "next"),
                ("scripts/program_roadmap.py", "--workspace", str(workspace), "overview"),
            ):
                self.assertIn(rendered, run_script(*arguments).stdout)

            owner = campaign_queue.load_all(workspace)["owner-work"]
            roadmap_item = campaign_queue.parse_campaign_text(owner.path, campaign_queue.render_campaign(owner))
            roadmap_item.fields["Roadmap"] = "demo"
            detour = campaign_queue.parse_campaign_text(owner.path, campaign_queue.render_campaign(owner))
            detour.fields["Detour For"] = "parent"
            detour.fields["Return To"] = "parent"
            self.assertEqual(program_roadmap.campaign_origin(None), "direct")
            self.assertEqual(program_roadmap.campaign_origin(owner), "owner-originated")
            self.assertEqual(program_roadmap.campaign_origin(roadmap_item), "roadmap-derived")
            self.assertEqual(program_roadmap.campaign_origin(detour), "detour")
            direct_capsule = program_roadmap.cycle_state_capsule(
                workspace, campaigns={}, order=[]
            )
            self.assertEqual(direct_capsule["dimensions"]["work_origin"], "direct")
            roadmap_capsule = program_roadmap.cycle_state_capsule(
                workspace,
                campaigns={roadmap_item.campaign_id: roadmap_item},
                order=[roadmap_item.campaign_id],
            )
            self.assertEqual(
                roadmap_capsule["dimensions"]["work_origin"], "roadmap-derived"
            )
            detour.fields["Status"] = "working"
            detour_capsule = program_roadmap.cycle_state_capsule(
                workspace,
                campaigns={detour.campaign_id: detour},
                order=[detour.campaign_id],
            )
            self.assertEqual(detour_capsule["dimensions"]["work_origin"], "detour")
            self.assertEqual(detour_capsule["campaign_cycle"]["return_to"], "parent")
            self.assertEqual(
                detour_capsule["dimensions"]["coordination_level"],
                "independent-request-dimension",
            )
            self.assertEqual(
                detour_capsule["dimensions"]["execution_endpoint"],
                "independent-request-dimension",
            )

    def test_empty_queue_reports_derivation_exact_plan_approval_and_completed_program(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            self.install(workspace)
            self.campaign_record(
                workspace,
                number="001",
                campaign_id="finish-m1",
                milestone="M1",
                unlocks_gate="G1",
            )
            roadmap = self.write_roadmap(workspace)

            derivable = self.status(workspace)["cycle_state"]
            self.assertEqual(derivable["owning_cycle"], "milestone-wave")
            self.assertEqual(derivable["milestone_wave_cycle"]["state"], "derivable")
            self.assertEqual(
                derivable["next_transition"]["command"],
                "ts: derive campaigns for milestone M2",
            )

            plan = program_roadmap.derive(workspace, "demo", "M2")
            plan_root = workspace / "work" / "roadmaps" / "campaign-plans"
            plan_root.mkdir()
            (plan_root / "demo-r1-M2.json").write_text(
                json.dumps(plan, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            pending = self.status(workspace)["cycle_state"]
            self.assertEqual(pending["milestone_wave_cycle"]["state"], "awaiting-plan-approval")
            self.assertEqual(
                pending["next_transition"]["command"],
                f"ts: approve campaign plan {plan['manifest_token']}",
            )
            self.assertTrue(pending["next_transition"]["requires_exact_approval"])

            deferred = self.campaign_record(
                workspace,
                number="002",
                campaign_id="finish-m2",
                milestone="M2",
                unlocks_gate="G2",
                status="deferred",
            )
            incomplete = self.status(workspace)["cycle_state"]
            self.assertEqual(incomplete["milestone_wave_cycle"]["state"], "active")
            self.assertEqual(incomplete["next_transition"]["command"], "ts: roadmap status")

            deferred.unlink()
            self.campaign_record(
                workspace,
                number="002",
                campaign_id="finish-m2",
                milestone="M2",
                unlocks_gate="G2",
            )
            complete = self.status(workspace)["cycle_state"]
            self.assertEqual(complete["program_cycle"]["state"], "complete")
            self.assertEqual(complete["owning_cycle"], "program")
            self.assertEqual(complete["next_transition"]["command"], "none")
            self.assertIn("all roadmap milestones", complete["next_transition"]["reason"])


if __name__ == "__main__":
    unittest.main()
