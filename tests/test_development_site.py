from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "development_site",
    ROOT / "scripts" / "development_site.py",
)
assert SPEC and SPEC.loader
DEVELOPMENT_SITE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = DEVELOPMENT_SITE
SPEC.loader.exec_module(DEVELOPMENT_SITE)


class DevelopmentSiteTests(unittest.TestCase):
    def test_plan_is_lan_only_and_separate_from_production(self) -> None:
        contract = DEVELOPMENT_SITE.target_contract()
        self.assertEqual(contract["compose_project"], "tsrookarocom-dev")
        self.assertEqual(contract["endpoint"], "http://192.168.7.5:8443")
        self.assertEqual(contract["workpc_endpoint"], "http://127.0.0.1:8443")
        self.assertFalse(contract["public_route"])
        self.assertNotEqual(contract["target"], contract["production_target"])
        with self.assertRaisesRegex(
            DEVELOPMENT_SITE.DevelopmentSiteError,
            "must not be the production",
        ):
            DEVELOPMENT_SITE.target_contract(DEVELOPMENT_SITE.PRODUCTION_ROOT)

    def test_cli_plan_is_json_and_nonmutating(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "development_site.py"), "--json", "plan"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["operation"], "plan")
        self.assertEqual(payload["compose_project"], "tsrookarocom-dev")

    def test_deploy_environment_must_match_staged_identity_without_reading_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            marker = {
                "compose_project": "tsrookarocom-dev",
                "image_tag": "dev-0123456789ab",
            }
            (target / DEVELOPMENT_SITE.MARKER).write_text(
                json.dumps(marker),
                encoding="utf-8",
            )
            environment = target / ".env"
            environment.write_text(
                "\n".join(
                    (
                        "COMPOSE_PROJECT_NAME=tsrookarocom-dev",
                        "POSTGRES_PASSWORD=never-inspected",
                        "TOOL_SHED_DASHBOARD_SECRET_KEY=never-inspected",
                        "TOOL_SHED_DASHBOARD_ENVIRONMENT=development",
                        "TOOL_SHED_DASHBOARD_ALLOW_INSECURE_HTTP=1",
                        "TOOL_SHED_DASHBOARD_IMAGE_TAG=dev-0123456789ab",
                        "TOOL_SHED_DOCS_CONTAINER_NAME=ts-rookaro-com-dev",
                        "TOOL_SHED_SITE_BIND_ADDRESS=192.168.7.5",
                        "TOOL_SHED_SITE_PORT=8443",
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            os.chmod(environment, 0o600)
            DEVELOPMENT_SITE._controlled_environment(target, marker)
            environment.write_text(
                environment.read_text(encoding="utf-8").replace(
                    "TOOL_SHED_SITE_PORT=8443",
                    "TOOL_SHED_SITE_PORT=8087",
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                DEVELOPMENT_SITE.DevelopmentSiteError,
                "TOOL_SHED_SITE_PORT",
            ):
                DEVELOPMENT_SITE._controlled_environment(target, marker)

    def test_deploy_recreates_docs_after_atomic_public_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            marker = {
                "compose_project": "tsrookarocom-dev",
                "image_tag": "dev-0123456789ab",
            }
            (target / DEVELOPMENT_SITE.MARKER).write_text(
                json.dumps(marker),
                encoding="utf-8",
            )
            environment = target / ".env"
            environment.write_text("placeholder=1\n", encoding="utf-8")
            os.chmod(environment, 0o600)

            with (
                mock.patch.object(DEVELOPMENT_SITE, "_controlled_environment"),
                mock.patch.object(DEVELOPMENT_SITE, "run") as run,
                mock.patch.object(
                    DEVELOPMENT_SITE,
                    "status",
                    return_value={"development_health": {"healthy": True}},
                ),
            ):
                result = DEVELOPMENT_SITE.deploy(target=target)

            self.assertEqual(result["state"], "started")
            commands = [call.args[0] for call in run.call_args_list]
            self.assertEqual(commands[0][-2:], ("config", "--quiet"))
            self.assertEqual(commands[1][-3:], ("up", "-d", "--no-build"))
            self.assertEqual(
                commands[2][-6:],
                (
                    "up",
                    "-d",
                    "--no-build",
                    "--force-recreate",
                    "--no-deps",
                    "docs",
                ),
            )

    def test_workpc_tunnel_contract_is_localhost_only_and_restartable(self) -> None:
        script = (ROOT / "scripts" / "workpc_development_tunnel.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("127.0.0.1:${LocalPort}:${RemoteTarget}", script)
        self.assertIn('RemoteTarget = "192.168.7.5:8443"', script)
        self.assertIn("RestartCount 999", script)
        self.assertNotIn("0.0.0.0:${LocalPort}", script)


if __name__ == "__main__":
    unittest.main()
