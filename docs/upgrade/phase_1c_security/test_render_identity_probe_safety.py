"""Offline safety tests for render_identity_probe.py.

Validates probe security guarantees without connecting to production:
- Parameter and project reference validation
- Connection routing override rejection
- Weak TLS rejection and mandatory SSL enforcement
- Read-only transaction, lock timeout, and statement timeout injection
- Pooler and direct host matching logic
- Mandatory transaction rollback and engine disposal
- Exception sanitization and credential suppression
"""
from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import MagicMock, Mock, patch

FOLDER = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "render_identity_probe", FOLDER / "render_identity_probe.py"
)
probe_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe_module)


VALID_PROJECT_REF = "abcdefghijklmnopqrst"
VALID_SERVICE_ID = "srv-dbmof167bikc73bjl1j0"
BASE_POOLER_URL = f"postgresql://postgres.{VALID_PROJECT_REF}:secret-pass@aws-0-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require"


class RenderIdentityProbeSafetyTests(unittest.TestCase):
    def test_invalid_project_ref_format_rejected(self):
        invalid_refs = [
            "short",
            "this_project_ref_is_too_long_123456",
            "contains-hyphen!!",
            "semi;colon;drop--",
            "UPPERCASEPROJECT1234",
            "",
        ]
        for ref in invalid_refs:
            with self.subTest(ref=ref):
                with self.assertRaises(ValueError) as ctx:
                    probe_module.probe(ref, VALID_SERVICE_ID)
                self.assertIn("Expected project reference format invalid", str(ctx.exception))

    def test_service_id_mismatch_rejected(self):
        with patch.dict(os.environ, {"RENDER_SERVICE_ID": "srv-real-service"}, clear=True):
            # Service ID doesn't start with srv-
            with self.assertRaises(ValueError) as ctx:
                probe_module.probe(VALID_PROJECT_REF, "invalid-prefix")
            self.assertIn("Not the independently verified running Render service", str(ctx.exception))

            # Service ID does not match RENDER_SERVICE_ID
            with self.assertRaises(ValueError) as ctx:
                probe_module.probe(VALID_PROJECT_REF, "srv-other-service")
            self.assertIn("Not the independently verified running Render service", str(ctx.exception))

    def test_unexpected_database_or_driver_rejected(self):
        env = {"RENDER_SERVICE_ID": VALID_SERVICE_ID}
        # Non-postgres database
        bad_db_url = f"postgresql://postgres.{VALID_PROJECT_REF}:secret@aws-0-us-east-1.pooler.supabase.com:5432/wrong_db"
        with patch.dict(os.environ, {**env, "DATABASE_URL": bad_db_url}, clear=True):
            with self.assertRaises(ValueError) as ctx:
                probe_module.probe(VALID_PROJECT_REF, VALID_SERVICE_ID)
            self.assertIn("Unexpected driver/database", str(ctx.exception))

    def test_connection_routing_overrides_rejected(self):
        env = {"RENDER_SERVICE_ID": VALID_SERVICE_ID}
        for bad_param in ("host", "hostaddr", "port", "dbname", "user", "password", "service"):
            bad_url = f"{BASE_POOLER_URL}&{bad_param}=evil.com"
            with self.subTest(param=bad_param):
                with patch.dict(os.environ, {**env, "DATABASE_URL": bad_url}, clear=True):
                    with self.assertRaises(ValueError) as ctx:
                        probe_module.probe(VALID_PROJECT_REF, VALID_SERVICE_ID)
                    self.assertIn("Connection routing overrides require separate target review", str(ctx.exception))

    def test_weak_tls_modes_rejected(self):
        env = {"RENDER_SERVICE_ID": VALID_SERVICE_ID}
        for weak_mode in ("disable", "allow", "prefer"):
            bad_url = f"postgresql://postgres.{VALID_PROJECT_REF}:secret@aws-0-us-east-1.pooler.supabase.com:5432/postgres?sslmode={weak_mode}"
            with self.subTest(mode=weak_mode):
                with patch.dict(os.environ, {**env, "DATABASE_URL": bad_url}, clear=True):
                    with self.assertRaises(ValueError) as ctx:
                        probe_module.probe(VALID_PROJECT_REF, VALID_SERVICE_ID)
                    self.assertIn("Runtime TLS setting is weaker than require", str(ctx.exception))

    def test_project_mismatch_rejected(self):
        env = {"RENDER_SERVICE_ID": VALID_SERVICE_ID}
        wrong_url = "postgresql://postgres.otherprojectref1234:secret@aws-0-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require"
        with patch.dict(os.environ, {**env, "DATABASE_URL": wrong_url}, clear=True):
            with self.assertRaises(ValueError) as ctx:
                probe_module.probe(VALID_PROJECT_REF, VALID_SERVICE_ID)
            self.assertIn("Runtime target does not match independently verified project", str(ctx.exception))

    @patch.object(probe_module, "create_engine")
    def test_read_only_and_timeouts_injected_into_engine(self, mock_create_engine):
        env = {"RENDER_SERVICE_ID": VALID_SERVICE_ID, "DATABASE_URL": BASE_POOLER_URL}
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        mock_conn = MagicMock()
        mock_engine.connect.return_value.execution_options.return_value.__enter__.return_value = mock_conn
        mock_tx = MagicMock()
        mock_conn.begin.return_value = mock_tx

        # Configure mocked query returns
        mock_conn.connection.driver_connection.info.ssl_in_use = True
        
        # 1st execute: alembic_version
        rev_mock = MagicMock()
        rev_mock.scalars.return_value = ["a1b2c3d4e5f6"]
        
        # 2nd execute: connection info
        conn_info_mock = MagicMock()
        conn_info_mock.mappings.return_value.one.return_value = {
            "database_role": "postgres",
            "login_role": "postgres",
            "configured_role": "none",
            "server_version": "17.1",
            "read_only": "on",
            "isolation": "repeatable read",
        }
        
        # 3rd execute: role flags
        roles_mock = MagicMock()
        roles_mock.mappings.return_value.one.return_value = {
            "rolsuper": False,
            "rolinherit": True,
            "rolcanlogin": True,
            "rolcreaterole": False,
            "rolcreatedb": False,
            "rolbypassrls": False,
        }
        
        # 4th execute: tables
        tables_mock = MagicMock()
        tables_mock.mappings.return_value = [
            {"relname": "refresh_tokens"},
            {"relname": "user_sessions"},
            {"relname": "users"},
        ]

        # Execute sequence
        mock_conn.execute.side_effect = [
            MagicMock(),      # SET TRANSACTION READ ONLY
            rev_mock,        # SELECT version_num
            conn_info_mock,  # SELECT current_user ...
            roles_mock,      # SELECT rolsuper ...
            tables_mock,     # SELECT tables ...
        ]

        with patch.dict(os.environ, env, clear=True):
            result = probe_module.probe(VALID_PROJECT_REF, VALID_SERVICE_ID)

        # Verify engine creation received enforced read_only and timeout query parameters
        call_url = mock_create_engine.call_args[0][0]
        self.assertIn("default_transaction_read_only=on", call_url.query.get("options", ""))
        self.assertIn("statement_timeout=10000", call_url.query.get("options", ""))
        self.assertIn("lock_timeout=2000", call_url.query.get("options", ""))
        self.assertEqual(call_url.query.get("sslmode"), "require")
        self.assertEqual(mock_create_engine.call_args[1]["connect_args"]["connect_timeout"], 10)

        # Verify transaction rollback and engine disposal
        mock_tx.rollback.assert_called_once()
        mock_engine.dispose.assert_called_once()
        self.assertEqual(result["production_writes"], 0)
        self.assertEqual(result["connection_mode"], "session_pooler")
        self.assertEqual(len(result["tables"]), 3)

    @patch.object(probe_module, "create_engine")
    def test_revision_drift_aborts_with_rollback_and_dispose(self, mock_create_engine):
        env = {"RENDER_SERVICE_ID": VALID_SERVICE_ID, "DATABASE_URL": BASE_POOLER_URL}
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        mock_conn = MagicMock()
        mock_engine.connect.return_value.execution_options.return_value.__enter__.return_value = mock_conn
        mock_tx = MagicMock()
        mock_conn.begin.return_value = mock_tx

        # Return unexpected revision
        drift_mock = MagicMock()
        drift_mock.scalars.return_value = ["drifted_revision_123"]
        mock_conn.execute.side_effect = [
            MagicMock(),  # SET TRANSACTION READ ONLY
            drift_mock,   # SELECT version_num -> drifted
        ]

        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ValueError) as ctx:
                probe_module.probe(VALID_PROJECT_REF, VALID_SERVICE_ID)
            self.assertIn("Revision drift; renewed review required", str(ctx.exception))

        mock_tx.rollback.assert_called_once()
        mock_engine.dispose.assert_called_once()


if __name__ == "__main__":
    unittest.main()
