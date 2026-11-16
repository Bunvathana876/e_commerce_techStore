"""Temporary Render Docker Command wrapper; not approved for deployment.

The command artifact combines the unchanged reviewed probe with this wrapper.
No application module is imported by the diagnostic. The project fingerprint is
derived locally from the independently dashboard-verified target, never from
Render's own DATABASE_URL. Only this non-secret identifier is fingerprinted.
"""
import hashlib
import json
import os
import re
import signal

from sqlalchemy.engine import make_url


EXPECTED_SERVICE_ID = "srv-dbmof167bikc73bjl1j0"
EXPECTED_COMMIT = "ad26cefb3dae4d0a24d1b53c8cdb5f494ac602cf"
EXPECTED_PROJECT_SHA256 = "96e4caeee92b4c586333132913e437b6878d589a16b3ee94fb620801a4418e89"
ORIGINAL_START = (
    "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} "
    "--workers ${WORKERS:-1} --proxy-headers"
)


def emit_metadata(value):
    print("READ_ONLY_ROLE_PROBE " + json.dumps(value, sort_keys=True), flush=True)


def deadline_expired(signum, frame):
    raise TimeoutError("Diagnostic time budget exceeded")


def run_diagnostic(probe_function):
    # Stop the candidate before app import if its identity or startup safety
    # differs from the reviewed Docker runtime. Never mutate runtime settings.
    safe_start = (
        os.environ.get("RENDER") == "true"
        and os.environ.get("RENDER_SERVICE_ID") == EXPECTED_SERVICE_ID
        and os.environ.get("RENDER_GIT_COMMIT") == EXPECTED_COMMIT
        and bool(os.environ.get("RENDER_INSTANCE_ID"))
        and os.environ.get("ENVIRONMENT", "").strip().lower() == "production"
        and os.environ.get("AUTO_INIT_DB", "").strip().lower() == "false"
        and os.environ.get("SEED_DEMO_DATA", "").strip().lower() == "false"
        and os.environ.get("RUN_MIGRATIONS_ON_STARTUP", "false").strip().lower() == "false"
    )
    if not safe_start:
        emit_metadata({"status": "UNVERIFIED", "reason": "runtime_preflight_mismatch"})
        raise SystemExit(2)

    signal.signal(signal.SIGALRM, deadline_expired)
    signal.alarm(45)
    try:
        # Do not silently clear inherited libpq configuration. Any PG* input
        # requires private review before a probe can attest the connection.
        if any(key.startswith("PG") and value for key, value in os.environ.items()):
            raise ValueError("Inherited libpq configuration requires review")
        runtime_url = make_url(os.environ["DATABASE_URL"])
        host = runtime_url.host or ""
        if host.endswith(".pooler.supabase.com"):
            project_ref = (runtime_url.username or "").rsplit(".", 1)[-1]
        else:
            match = re.fullmatch(r"db\.([a-z0-9]{20})\.supabase\.co", host)
            if match is None:
                raise ValueError("Unexpected runtime host")
            project_ref = match.group(1)
        if hashlib.sha256(project_ref.encode("ascii")).hexdigest() != EXPECTED_PROJECT_SHA256:
            raise ValueError("Runtime project mismatch")

        result = probe_function(project_ref, EXPECTED_SERVICE_ID)
        connection = result["connection"]
        if (
            result["runtime_commit"] != EXPECTED_COMMIT
            or connection["read_only"] != "on"
            or connection["isolation"] != "repeatable read"
            or connection["server_version"].split(".", 1)[0] != "17"
            or result["client_tls"] is not True
            or result["connection_mode"] not in {"direct", "session_pooler", "transaction_pooler"}
            or {table["relname"] for table in result["tables"]}
            != {"users", "user_sessions", "refresh_tokens"}
        ):
            raise ValueError("Runtime evidence incomplete or drifted")
        result["status"] = "ROLE_OBSERVED"
        result["instance_sha256"] = hashlib.sha256(
            os.environ["RENDER_INSTANCE_ID"].encode("utf-8")
        ).hexdigest()
        emit_metadata(result)
    except Exception as error:
        original = getattr(error, "orig", error)
        emit_metadata({
            "status": "UNVERIFIED",
            "error_type": type(error).__name__,
            "sqlstate": getattr(original, "pgcode", None),
            "details": "suppressed",
        })
    finally:
        signal.alarm(0)

    # A failed read-only diagnostic does not turn into a fix or a retry loop.
    # Continue the exact committed Docker CMD, with its original environment.
    os.execvp("sh", ["sh", "-c", ORIGINAL_START])
