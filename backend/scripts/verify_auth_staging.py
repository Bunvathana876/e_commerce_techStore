"""Run current backend tests on Python 3.12 + disposable PostgreSQL 16.

Uses existing local images; never builds, pulls, loads .env, publishes ports or
runs application entrypoints. All test source is copied from an explicit allowlist.
Run from backend: rtk .venv/bin/python scripts/verify_auth_staging.py
"""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import uuid


CONTAINER_FIXTURE = r'''
# Staging harness override, only in the throwaway source copy.
@pytest.fixture(scope="session")
def pg_cluster():
    expected_name = os.environ["BP_TEST_CLUSTER_NAME"]
    pg_engine = create_engine(URL.create(
        "postgresql+psycopg2", username="bp_test", database="postgres",
        query={"host": "/bp-test-socket"},
    ), pool_size=12, max_overflow=12)
    try:
        with pg_engine.connect() as conn:
            assert pg_engine.url.host is None
            assert conn.exec_driver_sql("SHOW listen_addresses").scalar_one() == ""
            assert conn.exec_driver_sql("SHOW cluster_name").scalar_one() == expected_name
            assert conn.exec_driver_sql("SHOW server_version_num").scalar_one().startswith("16")
            assert conn.exec_driver_sql("SHOW data_directory").scalar_one() == "/var/lib/postgresql/data"
        yield pg_engine, Path("/var/lib/postgresql/data")
    finally:
        pg_engine.dispose()
'''


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-image", default="blue-panda-backend:staging")
    parser.add_argument("--postgres-image", default="postgres:16-alpine")
    args = parser.parse_args()
    # Fail rather than pull an unexpected image or upgrade dependencies.
    for image in [args.backend_image, args.postgres_image]:
        run("docker", "image", "inspect", image, stdout=subprocess.DEVNULL)
    backend_root = Path(__file__).resolve().parents[1]
    # The runtime image has no Git. Verify repository ignore rules on the host
    # before excluding that filesystem-only check from container pytest.
    for repository in [backend_root, backend_root.parent]:
        for name in [".env", ".env.local", ".env.production", ".env.backup"]:
            run("git", "check-ignore", name, cwd=repository, stdout=subprocess.DEVNULL)
    identity = "bp-auth-test-" + uuid.uuid4().hex[:12]
    pg_name, python_name, socket_volume = identity + "-pg", identity + "-py", identity + "-sock"
    volume_created = False
    try:
        with tempfile.TemporaryDirectory(prefix="bp-auth-source-") as temporary:
            source = Path(temporary)
            for directory in ["app", "alembic", "tests", "scripts"]:
                shutil.copytree(backend_root / directory, source / directory,
                                ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".env", ".env.*"))
            shutil.copy2(backend_root / "alembic.ini", source / "alembic.ini")
            with (source / "tests/conftest.py").open("a") as conftest:
                conftest.write(CONTAINER_FIXTURE)
            run("docker", "volume", "create", socket_volume, stdout=subprocess.DEVNULL)
            volume_created = True
            run("docker", "run", "--detach", "--name", pg_name, "--network", "none",
                "--tmpfs", "/var/lib/postgresql/data:rw,noexec,nosuid",
                "--mount", f"type=volume,source={socket_volume},target=/var/run/postgresql",
                "--env", "POSTGRES_USER=bp_test", "--env", "POSTGRES_HOST_AUTH_METHOD=trust",
                args.postgres_image, "postgres", "-c", "listen_addresses=",
                "-c", f"cluster_name={identity}", stdout=subprocess.DEVNULL)
            for attempt in range(60):
                ready = subprocess.run(["docker", "exec", pg_name, "pg_isready", "-h", "/var/run/postgresql", "-U", "bp_test"],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if ready.returncode == 0:
                    break
                time.sleep(1)
            else:
                raise RuntimeError("Disposable PostgreSQL did not become ready.")
            run("docker", "exec", pg_name, "postgres", "--version")
            run("docker", "run", "--rm", "--name", python_name, "--network", "none", "--read-only",
                "--tmpfs", "/tmp:rw,nosuid", "--tmpfs", "/app:rw,nosuid,mode=1777",
                "--mount", f"type=bind,source={source},target=/test-source,readonly",
                "--mount", f"type=volume,source={socket_volume},target=/bp-test-socket",
                "--env", f"BP_TEST_CLUSTER_NAME={identity}", "--env", "PYTHONDONTWRITEBYTECODE=1", "--env", "ENVIRONMENT=test",
                "--env", "PYTHONPATH=/app", "--workdir", "/app", "--entrypoint", "sh", args.backend_image,
                "-c", "cp -R /test-source/. /app/ && python --version && python -m pytest -q -rs -p no:cacheprovider -k 'not test_6_private_environment_files_are_ignored_by_git'")
    finally:
        # Only resources created with this unpredictable per-run name are removed.
        for container in [python_name, pg_name]:
            subprocess.run(["docker", "rm", "--force", container], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if volume_created:
            subprocess.run(["docker", "volume", "rm", socket_volume], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
