"""Synthetic-only encrypted recovery rehearsal; never reads .env or live URLs.

Uses the cached approved PostgreSQL 17 image and two disposable, network-less
tmpfs containers. Accepts no source, archive, connection or production arguments.
"""
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import uuid


def main():
    root = Path(__file__).resolve().parents[3]
    security = root / "docs/upgrade/phase_1c_security"
    tree = ast.parse((security / "rehearse_postgres17.py").read_text())
    constants = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign) and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"fixture", "snapshot", "history"}
    }
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("PG") and key != "DATABASE_URL"}
    started = []
    checks = []

    def run(*command, data=None, good=True):
        result = subprocess.run(command, input=data, capture_output=True, env=env)
        if good and result.returncode:
            # Do not emit SQL, decrypted bytes, connection or exception details.
            raise RuntimeError("Synthetic recovery command failed: " + command[0])
        return result

    image = json.loads(run("docker", "image", "inspect", "postgres:17-alpine").stdout)[0]["Id"]

    def sql(container, statement, role="postgres"):
        return run("docker", "exec", "-i", container, "psql", "-X", "-At",
                   "-v", "ON_ERROR_STOP=1", "-U", role, "-d", "postgres",
                   data=statement.encode()).stdout.strip()

    def start(label):
        name = "bp-recovery-" + label + "-" + uuid.uuid4().hex[:12]
        run("docker", "run", "--detach", "--rm", "--pull=never", "--name", name,
            "--label", "blue-panda.synthetic-recovery=" + name,
            "--network", "none", "--read-only",
            "--tmpfs", "/var/lib/postgresql/data:rw,noexec,nosuid,size=512m",
            "--tmpfs", "/var/run/postgresql:rw,noexec,nosuid,size=8m",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=32m",
            "--env", "POSTGRES_USER=bp_fixture", "--env", "POSTGRES_DB=postgres",
            "--env", "POSTGRES_HOST_AUTH_METHOD=trust", image,
            "postgres", "-c", "listen_addresses=", "-c", "cluster_name=" + name)
        started.append(name)
        for _ in range(30):
            if run("docker", "exec", name, "cat", "/proc/1/comm", good=False).stdout.strip() == b"postgres":
                if run("docker", "exec", name, "pg_isready", "-U", "bp_fixture", good=False).returncode == 0:
                    break
            time.sleep(1)
        else:
            raise RuntimeError("Synthetic cluster readiness timeout")
        info = json.loads(run("docker", "inspect", name).stdout)[0]
        assert info["HostConfig"]["NetworkMode"] == "none"
        assert info["HostConfig"]["ReadonlyRootfs"] and info["HostConfig"]["AutoRemove"]
        assert not info["HostConfig"].get("Binds") and not info["HostConfig"]["PortBindings"]
        assert not any(m["Type"] in {"bind", "volume"} for m in info["Mounts"])
        assert sql(name, "SHOW cluster_name", "bp_fixture").decode() == name
        assert sql(name, "SHOW listen_addresses", "bp_fixture") == b""
        assert sql(name, "SHOW data_directory", "bp_fixture") == b"/var/lib/postgresql/data"
        assert int(sql(name, "SHOW server_version_num", "bp_fixture")) // 10000 == 17
        return name

    try:
        source = start("source")
        target = start("target")
        sql(source, constants["fixture"], "bp_fixture")
        sql(target, constants["fixture"].split("SET ROLE postgres;", 1)[0], "bp_fixture")
        run("docker", "exec", source, "mkdir", "/tmp/security")
        names = ["apply.sql", "target_guard.sql", "deny_assertions.sql"]
        for name in names:
            run("docker", "exec", "-i", source, "sh", "-c", 'cat > "$1"',
                "--", "/tmp/security/" + name, data=(security / name).read_bytes())
        run("docker", "exec", source, "psql", "-X", "-U", "postgres", "-d", "postgres",
            "-v", "ON_ERROR_STOP=1", "-v", "expected_server_major=17",
            "-v", "approval=APPROVED_AUTH_TABLE_ACL_WINDOW", "-f", "/tmp/security/apply.sql")
        checks.append("two isolated PostgreSQL 17 clusters; remediated synthetic fixture only")
        archive = run("docker", "exec", source, "pg_dump", "-U", "postgres", "-d", "postgres",
                      "--format=custom", "--schema=public", "--strict-names", "--no-password").stdout
        assert archive.startswith(b"PGDMP")
        catalog = """SELECT json_build_object(
          'relations',(SELECT json_agg(x ORDER BY relname) FROM
            (SELECT relname,relkind,(CASE WHEN relkind IN ('r','S') THEN
             coalesce(relacl,acldefault(CASE WHEN relkind='S' THEN 's'::"char" ELSE 'r'::"char" END,relowner))
             ELSE relacl END)::text AS acl,relrowsecurity,relforcerowsecurity,
             pg_get_userbyid(relowner) AS owner FROM pg_class
             WHERE relnamespace='public'::regnamespace) x),
          'constraints',(SELECT json_agg(x ORDER BY conname) FROM
            (SELECT conname,pg_get_constraintdef(oid) AS definition FROM pg_constraint
             WHERE connamespace='public'::regnamespace) x),
          'indexes',(SELECT json_agg(x ORDER BY indexname) FROM
            (SELECT indexname,indexdef FROM pg_indexes WHERE schemaname='public') x),
          'policies',(SELECT json_agg(x ORDER BY tablename,policyname) FROM
            (SELECT tablename,policyname,permissive,roles,cmd,qual,with_check
             FROM pg_policies WHERE schemaname='public') x),
          'columns',(SELECT json_agg(x ORDER BY table_name,ordinal_position) FROM
            (SELECT table_name,column_name,ordinal_position,is_nullable,data_type,column_default
             FROM information_schema.columns WHERE table_schema='public') x))::text"""
        expected_catalog = sql(source, catalog)
        metadata_path = Path(__file__).with_name("backup_metadata.sql")
        metadata_command = ["docker", "exec", "-i", source, "psql", "-X", "-qAt",
                            "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres"]
        role_metadata = run(*metadata_command, "-v", "expected_revision=a1b2c3d4e5f6",
                            data=metadata_path.read_bytes()).stdout.strip()
        assert json.loads(role_metadata)["read_only"] == "on"
        assert run(*metadata_command, "-v", "expected_revision=unexpected",
                   data=metadata_path.read_bytes(), good=False).returncode != 0
        checks.append("read-only password-free metadata capture; revision drift refused")
        with tempfile.TemporaryDirectory(prefix="bp-synthetic-cms-") as tmp:
            work = Path(tmp)
            key, cert = work / "fixture-key.pem", work / "fixture-cert.pem"
            wrong_key, wrong_cert = work / "wrong-key.pem", work / "wrong-cert.pem"
            for private, public in [(key, cert), (wrong_key, wrong_cert)]:
                run("openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                    "-subj", "/CN=synthetic-only", "-days", "1", "-keyout", str(private), "-out", str(public))
                private.chmod(0o600)
            def encrypt(data):
                return run("openssl", "cms", "-encrypt", "-binary", "-stream", "-aes-256-gcm",
                           "-outform", "DER", str(cert), data=data).stdout

            def decrypt(data, private=key, recipient=cert, good=True):
                return run("openssl", "cms", "-decrypt", "-binary", "-inform", "DER",
                           "-recip", str(recipient), "-inkey", str(private), data=data, good=good)

            encrypted = encrypt(archive)
            encrypted_roles = encrypt(role_metadata)
            recovered = decrypt(encrypted).stdout
            assert recovered == archive
            assert decrypt(encrypted_roles).stdout == role_metadata
            checks.append("CMS AES-256-GCM archive and password-free role metadata round-trip")
            assert decrypt(encrypted, wrong_key, wrong_cert, good=False).returncode != 0
            tampered = bytearray(encrypted)
            tampered[len(tampered) // 2] ^= 1
            assert decrypt(bytes(tampered), good=False).returncode != 0
            checks.append("wrong recipient and modified ciphertext rejected before any restore")
            # Only successfully authenticated bytes enter this disposable target.
            # Keep the fresh cluster's initdb public schema/default ACL baseline.
            schema_metadata = sql(target, "SELECT json_agg(x ORDER BY nspname)::text FROM "
                                  "(SELECT nspname,pg_get_userbyid(nspowner) AS owner,nspacl::text AS acl "
                                  "FROM pg_namespace WHERE nspname IN ('public','graphql_public','extensions')) x")
            assert json.loads(schema_metadata) == json.loads(role_metadata)["schemas"]
            run("docker", "exec", "-i", target, "sh", "-c", 'cat > /tmp/recovery.dump', data=recovered)
            toc = run("docker", "exec", target, "pg_restore", "--list", "/tmp/recovery.dump").stdout.decode()
            # public already exists and its exact owner/ACL was independently matched.
            lines = toc.splitlines()
            public_entries = [line for line in lines if re.match(r"^\d+; \d+ \d+ SCHEMA - public \S+$", line)]
            assert len(public_entries) == 1
            restore_list = "\n".join(";" + line if line in public_entries else line for line in lines) + "\n"
            run("docker", "exec", "-i", target, "sh", "-c", 'cat > /tmp/restore.list', data=restore_list.encode())
            run("docker", "exec", target, "pg_restore", "-U", "bp_fixture", "-d", "postgres",
                "--exit-on-error", "--single-transaction", "--use-list=/tmp/restore.list", "/tmp/recovery.dump")
        actual_catalog = sql(target, catalog)
        if actual_catalog != expected_catalog:
            expected_json, actual_json = json.loads(expected_catalog), json.loads(actual_catalog)
            differences = {key: [(left, right) for left, right in zip(expected_json[key], actual_json[key])
                                 if left != right] for key in expected_json if expected_json[key] != actual_json[key]}
            raise AssertionError({"synthetic_metadata_differences": differences})
        assert sql(target, constants["history"]) == b"t"
        # pg_dump may restore explicit owner-only ACLs as equivalent NULL defaults.
        normalized = constants["snapshot"].replace(
            "relacl::text", "coalesce(relacl,acldefault(CASE WHEN relkind='S' THEN 's'::\"char\" ELSE 'r'::\"char\" END,relowner))::text")
        assert sql(target, normalized) == sql(source, normalized)
        restored_metadata = json.loads(run(
            "docker", "exec", "-i", target, "psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1",
            "-U", "postgres", "-d", "postgres", "-v", "expected_revision=a1b2c3d4e5f6",
            data=metadata_path.read_bytes()).stdout)
        original_metadata = json.loads(role_metadata)
        for name in ["revision", "roles", "memberships", "schemas", "extensions", "default_privileges"]:
            if restored_metadata[name] != original_metadata[name]:
                raise AssertionError({"synthetic_metadata_component": name,
                                      "source": original_metadata[name], "target": restored_metadata[name]})
        checks.append("restore preserves owner/ACL/RLS/policies, columns, indexes, constraints and revoked/consumed fixture history")
        checks.append("fixture role bootstrap, memberships, schema ACL, extensions, default grants and revision match")
        checks.append("plaintext archive stayed in memory/isolated tmpfs; no live data or host dump file")
        result = {"checked_at_utc": datetime.now(timezone.utc).isoformat(),
                  "postgresql": sql(source, "SHOW server_version").decode(), "image_id": image,
                  "openssl": run("openssl", "version").stdout.decode().strip(),
                  "production_connections": 0, "synthetic_only": True, "checks": checks,
                  "reviewed_sql_sha256": {name: hashlib.sha256((security / name).read_bytes()).hexdigest()
                                          for name in names}}
    finally:
        for name in reversed(started):
            run("docker", "stop", "--time", "10", name, good=False)
        remaining = run("docker", "ps", "-aq", "--filter", "label=blue-panda.synthetic-recovery").stdout.strip()
        if remaining:
            raise RuntimeError("Synthetic recovery cleanup unverified")
    result["temporary_containers_removed"] = True
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
