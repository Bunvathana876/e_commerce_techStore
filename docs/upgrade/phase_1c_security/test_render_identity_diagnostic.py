"""Offline safety checks; synthetic environment, mocked probe and process exec.

Run from repository root:
rtk proxy backend/.venv/bin/python -m unittest discover -s docs/upgrade/phase_1c_security -p test_render_identity_diagnostic.py
"""
import ast
from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shlex
import unittest
from unittest.mock import Mock, patch


FOLDER = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "diagnostic_launcher", FOLDER / "render_identity_diagnostic_launcher.py"
)
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)
FIXTURE_REF = "abcdefghijklmnopqrst"
FIXTURE_HASH = hashlib.sha256(FIXTURE_REF.encode()).hexdigest()
FIXTURE_ENV = {
    "RENDER": "true",
    "RENDER_SERVICE_ID": launcher.EXPECTED_SERVICE_ID,
    "RENDER_GIT_COMMIT": launcher.EXPECTED_COMMIT,
    "RENDER_INSTANCE_ID": "synthetic-instance",
    "ENVIRONMENT": "production",
    "AUTO_INIT_DB": "false",
    "SEED_DEMO_DATA": "false",
    "DATABASE_URL": (
        "postgresql://fixture.abcdefghijklmnopqrst:synthetic-password@"
        "aws-0-us-east-1.pooler.supabase.com:5432/postgres"
    ),
}
FIXTURE_RESULT = {
    "runtime_commit": launcher.EXPECTED_COMMIT,
    "connection": {
        "read_only": "on", "isolation": "repeatable read", "server_version": "17.11"
    },
    "client_tls": True,
    "connection_mode": "session_pooler",
    "tables": [{"relname": name} for name in ("users", "user_sessions", "refresh_tokens")],
}


class DiagnosticSafetyTests(unittest.TestCase):
    def invoke(self, environment=None, result=None, error=None, preflight_failure=False):
        environment = FIXTURE_ENV.copy() if environment is None else environment
        probe = Mock(return_value=deepcopy(FIXTURE_RESULT if result is None else result))
        probe.side_effect = error
        output = io.StringIO()
        with (
            patch.dict(os.environ, environment, clear=True),
            patch.object(launcher, "EXPECTED_PROJECT_SHA256", FIXTURE_HASH),
            patch.object(launcher.os, "execvp") as handoff,
            patch.object(launcher.signal, "signal"),
            patch.object(launcher.signal, "alarm") as alarm,
            redirect_stdout(output),
        ):
            if preflight_failure:
                with self.assertRaises(SystemExit) as stopped:
                    launcher.run_diagnostic(probe)
                self.assertEqual(stopped.exception.code, 2)
                handoff.assert_not_called()
                alarm.assert_not_called()
            else:
                launcher.run_diagnostic(probe)
                handoff.assert_called_once_with("sh", ["sh", "-c", launcher.ORIGINAL_START])
                self.assertEqual(alarm.call_args_list[0].args, (45,))
                self.assertEqual(alarm.call_args_list[-1].args, (0,))
            self.assertEqual(dict(os.environ), environment)
        lines = output.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith("READ_ONLY_ROLE_PROBE "))
        self.assertNotIn("synthetic-password", lines[0])
        return json.loads(lines[0].split(" ", 1)[1]), probe

    def test_observed_role_hands_off_without_environment_mutation(self):
        result, probe = self.invoke()
        self.assertEqual(result["status"], "ROLE_OBSERVED")
        self.assertEqual(result["instance_sha256"], hashlib.sha256(b"synthetic-instance").hexdigest())
        probe.assert_called_once_with(FIXTURE_REF, launcher.EXPECTED_SERVICE_ID)

    def test_wrong_service_commit_or_unsafe_start_stops_candidate(self):
        for key, value in (
            ("RENDER", "false"), ("RENDER_SERVICE_ID", "srv-other"),
            ("RENDER_GIT_COMMIT", "different-commit"), ("RENDER_INSTANCE_ID", ""),
            ("ENVIRONMENT", "development"), ("AUTO_INIT_DB", "true"),
            ("SEED_DEMO_DATA", "true"), ("RUN_MIGRATIONS_ON_STARTUP", "true"),
        ):
            with self.subTest(key=key):
                result, probe = self.invoke({**FIXTURE_ENV, key: value}, preflight_failure=True)
                self.assertEqual(result["status"], "UNVERIFIED")
                probe.assert_not_called()

    def test_inherited_libpq_override_never_opens_probe_connection(self):
        for key in ("PGHOSTADDR", "PGSERVICE", "PGOPTIONS", "PGPASSWORD"):
            with self.subTest(key=key):
                result, probe = self.invoke({**FIXTURE_ENV, key: "synthetic"})
                self.assertEqual(result["status"], "UNVERIFIED")
                probe.assert_not_called()

    def test_wrong_target_never_opens_probe_connection(self):
        result, probe = self.invoke({**FIXTURE_ENV, "DATABASE_URL": FIXTURE_ENV["DATABASE_URL"].replace(
            FIXTURE_REF, "zyxwvutsrqponmlkjihg"
        )})
        self.assertEqual(result["status"], "UNVERIFIED")
        probe.assert_not_called()

    def test_probe_failure_suppresses_exception_text_and_starts_original_app(self):
        for error in (RuntimeError("synthetic-password"), TimeoutError("synthetic-password")):
            with self.subTest(error=type(error).__name__):
                result, _ = self.invoke(error=error)
                self.assertEqual(result["status"], "UNVERIFIED")
                self.assertEqual(result["details"], "suppressed")

    def test_incomplete_or_drifted_evidence_is_not_verified(self):
        for key, value in (("client_tls", False), ("connection_mode", "unknown_pooler_port"),
                           ("runtime_commit", "different-commit"), ("tables", [])):
            with self.subTest(key=key):
                result = deepcopy(FIXTURE_RESULT)
                result[key] = value
                observed, _ = self.invoke(result=result)
                self.assertEqual(observed["status"], "UNVERIFIED")
        for key, value in (("read_only", "off"), ("isolation", "read committed"),
                           ("server_version", "18.1")):
            with self.subTest(connection_key=key):
                result = deepcopy(FIXTURE_RESULT)
                result["connection"][key] = value
                observed, _ = self.invoke(result=result)
                self.assertEqual(observed["status"], "UNVERIFIED")

    def test_command_exactly_bundles_reviewed_sources_without_running_them(self):
        command = (FOLDER / "render_identity_docker_command.txt").read_text().strip()
        argv = shlex.split(command)
        self.assertEqual(argv[:2], ["python", "-c"])
        expression = ast.parse(argv[2]).body[0].value
        self.assertIsInstance(expression, ast.Call)
        self.assertEqual(expression.func.id, "exec")
        bundle = ast.literal_eval(expression.args[0])
        probe = (FOLDER / "render_identity_probe.py").read_text()
        self.assertEqual(hashlib.sha256(probe.encode()).hexdigest(),
                         "3fe1b1237b74ea401ae1ba6ec1aa6d2d0e3391c7652b18836a64decb0f4cdd73")
        expected = probe.split("\nif __name__ == '__main__':", 1)[0] + "\n"
        expected += (FOLDER / "render_identity_diagnostic_launcher.py").read_text()
        expected += "\nrun_diagnostic(probe)\n"
        self.assertEqual(bundle, expected)
        compile(bundle, "<offline-command-check>", "exec")
        self.assertNotIn("PREPARE_FROM_VERIFIED_TARGET", bundle)


if __name__ == "__main__":
    unittest.main()
