"""Rehearse unchanged ACL scripts in an existing official PostgreSQL 17 image.

Never pulls/builds images, mounts host data, loads .env, or uses DATABASE_URL.
Synthetic auth rows only; this is SQL-role evidence, not Render/login acceptance.
The unique disposable container has no network, ports or persistent volumes.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', default='postgres:17-alpine')
    args = parser.parse_args()
    source = Path(__file__).resolve().parent
    identity = 'bp-security-pg17-' + uuid.uuid4().hex[:12]
    env = {k: v for k, v in os.environ.items() if not k.startswith('PG') and k != 'DATABASE_URL'}

    def run(*command, good=True, **options):
        result = subprocess.run(command, env=env, text=True, capture_output=True, **options)
        if good and result.returncode:
            # Commands contain only synthetic fixture SQL and non-secret paths.
            raise RuntimeError(result.stderr[:2000])
        return result

    info = json.loads(run('docker', 'image', 'inspect', args.image).stdout)[0]
    image_id = info['Id']
    checks = []
    started = False

    def psql(sql=None, filename=None, approved=True, good=True, role='postgres'):
        command = ['docker', 'exec', '-i', '--user', 'postgres', identity, 'psql', '-X',
                   '-U', role, '-d', 'postgres', '-v', 'ON_ERROR_STOP=1',
                   '-v', 'VERBOSITY=sqlstate', '-v', 'expected_server_major=17']
        if approved:
            command += ['-v', 'approval=APPROVED_AUTH_TABLE_ACL_WINDOW']
        if filename:
            command += ['-f', '/tmp/security/' + filename]
        else:
            command += ['-At']
        return run(*command, good=good, input=sql)

    def copy_sql(path):
        # Docker's archive-copy path may not see a directory inside tmpfs.
        # Write through exec and verify bytes without changing the SQL artifact.
        contents = path.read_bytes()
        destination = '/tmp/security/' + path.name
        run('docker', 'exec', '-i', identity, 'sh', '-c', 'cat > "$1"',
            '--', destination, input=contents.decode('utf-8'))
        copied_hash = run('docker', 'exec', identity, 'sha256sum', destination).stdout.split()[0]
        assert copied_hash == hashlib.sha256(contents).hexdigest()

    snapshot = "SELECT json_agg(x ORDER BY relname)::text FROM (SELECT relname,relacl::text,relrowsecurity,relforcerowsecurity FROM pg_class WHERE relnamespace='public'::regnamespace AND (relkind='S' OR relname IN ('users','user_sessions','refresh_tokens'))) x"
    fixture = """
CREATE ROLE postgres LOGIN BYPASSRLS NOSUPERUSER;
CREATE ROLE anon NOLOGIN; CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN BYPASSRLS;
GRANT anon,authenticated,service_role TO postgres WITH ADMIN OPTION;
ALTER DATABASE postgres OWNER TO postgres;
SET ROLE postgres;
CREATE TABLE public.alembic_version(version_num varchar(32) PRIMARY KEY);
INSERT INTO public.alembic_version VALUES ('a1b2c3d4e5f6');
CREATE TABLE public.users (
 id serial PRIMARY KEY, name varchar(100) NOT NULL, email varchar(255) NOT NULL,
 password_hash varchar(255) NOT NULL, phone varchar(30), avatar varchar(500),
 role varchar(20) NOT NULL DEFAULT 'customer', is_active boolean NOT NULL,
 created_at timestamp NOT NULL DEFAULT now(), updated_at timestamp NOT NULL DEFAULT now());
CREATE UNIQUE INDEX ix_users_email ON public.users(email);
CREATE TABLE public.user_sessions (
 id serial PRIMARY KEY, session_id varchar(36) NOT NULL, user_id integer NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
 token_family varchar(36) NOT NULL, ip_address varchar(45), user_agent varchar(255), device_name varchar(100),
 is_revoked boolean NOT NULL DEFAULT false, revoked_reason varchar(50), expires_at timestamptz NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), last_activity_at timestamptz NOT NULL DEFAULT now());
CREATE UNIQUE INDEX ix_user_sessions_session_id ON public.user_sessions(session_id);
CREATE INDEX ix_user_sessions_user_id ON public.user_sessions(user_id);
CREATE INDEX ix_user_sessions_token_family ON public.user_sessions(token_family);
CREATE INDEX ix_user_sessions_expires_at ON public.user_sessions(expires_at);
CREATE TABLE public.refresh_tokens (
 id serial PRIMARY KEY, session_id varchar(36) NOT NULL REFERENCES public.user_sessions(session_id) ON DELETE CASCADE,
 token_hash varchar(64) NOT NULL, parent_token_hash varchar(64), is_revoked boolean NOT NULL DEFAULT false,
 expires_at timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), used_at timestamptz);
CREATE UNIQUE INDEX ix_refresh_tokens_token_hash ON public.refresh_tokens(token_hash);
CREATE INDEX ix_refresh_tokens_session_id ON public.refresh_tokens(session_id);
CREATE INDEX ix_refresh_tokens_expires_at ON public.refresh_tokens(expires_at);
GRANT ALL ON TABLE public.users,public.user_sessions,public.refresh_tokens TO anon,authenticated,service_role;
GRANT ALL ON SEQUENCE public.users_id_seq,public.user_sessions_id_seq,public.refresh_tokens_id_seq TO anon,authenticated,service_role;
INSERT INTO public.users(name,email,password_hash,is_active) VALUES ('Synthetic fixture','fixture@example.invalid','not-a-valid-password-hash',true);
INSERT INTO public.user_sessions(session_id,user_id,token_family,expires_at,is_revoked) VALUES ('fixture-session',1,'fixture-family',now()+interval '1 day',true);
INSERT INTO public.refresh_tokens(session_id,token_hash,expires_at,is_revoked,used_at) VALUES ('fixture-session',repeat('0',64),now()+interval '1 day',true,now());
"""
    try:
        run('docker', 'run', '--detach', '--rm', '--pull=never', '--name', identity,
            '--label', 'blue-panda.security-gates=' + identity, '--network', 'none', '--read-only',
            '--tmpfs', '/var/lib/postgresql/data:rw,noexec,nosuid,size=512m',
            '--tmpfs', '/var/run/postgresql:rw,noexec,nosuid,size=8m',
            '--tmpfs', '/tmp:rw,noexec,nosuid,size=32m',
            '--env', 'POSTGRES_USER=bp_fixture', '--env', 'POSTGRES_DB=postgres',
            '--env', 'POSTGRES_HOST_AUTH_METHOD=trust', image_id,
            'postgres', '-c', 'listen_addresses=', '-c', 'cluster_name=' + identity)
        started = True
        for _ in range(30):
            final_server = run('docker', 'exec', identity, 'cat', '/proc/1/comm', good=False).stdout.strip() == 'postgres'
            if final_server and run('docker', 'exec', identity, 'pg_isready', '-U', 'bp_fixture', good=False).returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError('Isolated database readiness timeout')
        actual = json.loads(run('docker', 'inspect', identity).stdout)[0]
        assert actual['HostConfig']['NetworkMode'] == 'none'
        assert not actual['HostConfig']['PortBindings'] and not actual['HostConfig'].get('Binds')
        assert not any(m['Type'] in ('bind', 'volume') for m in actual['Mounts'])
        assert psql(sql='SHOW listen_addresses', role='bp_fixture').stdout.strip() == ''
        assert psql(sql='SHOW cluster_name', role='bp_fixture').stdout.strip() == identity
        assert psql(sql='SHOW data_directory', role='bp_fixture').stdout.strip() == '/var/lib/postgresql/data'
        version = psql(sql='SHOW server_version', role='bp_fixture').stdout.strip()
        assert psql(sql='SHOW server_version_num', role='bp_fixture').stdout.strip().startswith('17')
        run('docker', 'exec', identity, 'mkdir', '/tmp/security')
        names = ['apply.sql', 'rollback.sql', 'target_guard.sql', 'deny_assertions.sql', 'verify.sql', 'inspect.sql']
        for name in names:
            copy_sql(source / name)
        psql(sql=fixture, role='bp_fixture')
        before = psql(sql=snapshot).stdout.strip()
        denied = psql(filename='apply.sql', approved=False, good=False)
        assert denied.returncode and psql(sql=snapshot).stdout.strip() == before
        checks.append('missing approval aborts with unchanged ACL/RLS')
        psql(sql="UPDATE public.alembic_version SET version_num='unexpected-fixture'")
        assert psql(filename='apply.sql', good=False).returncode
        assert psql(sql=snapshot).stdout.strip() == before
        psql(sql="UPDATE public.alembic_version SET version_num='a1b2c3d4e5f6'")
        checks.append('revision drift aborts with unchanged ACL/RLS')
        psql(filename='inspect.sql')
        # Hold an ordinary reader lock to exercise the exact script's 2s timeout.
        locker = subprocess.Popen(['docker', 'exec', '--user', 'postgres', identity, 'psql', '-X', '-U', 'postgres', '-d', 'postgres', '-c', 'BEGIN; LOCK TABLE public.users IN ACCESS SHARE MODE; SELECT pg_sleep(6); ROLLBACK;'], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(30):
                held = psql(sql="SELECT EXISTS(SELECT 1 FROM pg_locks WHERE relation='public.users'::regclass AND mode='AccessShareLock' AND granted AND pid<>pg_backend_pid())").stdout.strip()
                if held == 't':
                    break
                time.sleep(0.1)
            else:
                raise RuntimeError('Fixture reader lock not observed')
            denied = psql(filename='apply.sql', good=False)
            assert denied.returncode and '55P03' in denied.stderr
            assert psql(sql=snapshot).stdout.strip() == before
        finally:
            locker.wait(timeout=15)
        checks.append('2s lock timeout 55P03 leaves ACL/RLS unchanged')
        with tempfile.TemporaryDirectory(prefix='bp-acl-failure-') as tmp:
            failure = Path(tmp) / 'apply_failure.sql'
            failure.write_text((source / 'apply.sql').read_text().replace('\\ir deny_assertions.sql', 'SELECT 1/0;\n\\ir deny_assertions.sql'))
            copy_sql(failure)
            denied = psql(filename='apply_failure.sql', good=False)
            assert denied.returncode and '22012' in denied.stderr
            assert psql(sql=snapshot).stdout.strip() == before
        checks.append('failure after revocations/RLS rolls back the entire transaction')
        psql(filename='apply.sql')
        psql(filename='verify.sql')
        checks.append('unchanged apply and 45 API-role SELECT/DML-planning denials pass')
        psql(sql='GRANT SELECT ON public.users TO anon')
        assert psql(sql='SET ROLE anon; SELECT 1 FROM public.users').stdout.strip() == 'SET'
        psql(sql='REVOKE SELECT ON public.users FROM anon')
        checks.append('RLS hides populated fixture after accidental SELECT regrant')
        # Owner capability check, not a claim about an unverified Render identity.
        psql(sql="BEGIN; SELECT 1 FROM public.users LIMIT 0; SELECT 1 FROM public.user_sessions LIMIT 0; SELECT 1 FROM public.refresh_tokens LIMIT 0; UPDATE public.users SET id=id; UPDATE public.user_sessions SET id=id; UPDATE public.refresh_tokens SET id=id; INSERT INTO public.users(name,email,password_hash,is_active) VALUES ('Temporary fixture','temporary@example.invalid','invalid-fixture-hash',true); DELETE FROM public.refresh_tokens; DELETE FROM public.user_sessions; DELETE FROM public.users; ROLLBACK;")
        checks.append('non-superuser postgres owner/BYPASSRLS retains fixture CRUD')
        history = "SELECT (SELECT count(*) FROM public.users)=1 AND (SELECT count(*) FROM public.user_sessions WHERE is_revoked)=1 AND (SELECT count(*) FROM public.refresh_tokens WHERE is_revoked AND used_at IS NOT NULL)=1"
        assert psql(sql=history).stdout.strip() == 't'
        after = psql(sql=snapshot).stdout.strip()
        assert psql(filename='apply.sql', good=False).returncode
        assert psql(sql=snapshot).stdout.strip() == after
        psql(filename='rollback.sql')
        assert psql(sql=snapshot).stdout.strip() == before
        assert psql(sql=history).stdout.strip() == 't'
        checks.append('rollback restores exact ACL/RLS baseline and preserves fixture history')
        psql(filename='apply.sql')
        psql(filename='verify.sql')
        assert psql(sql=history).stdout.strip() == 't'
        checks.append('reapplication and denial tests pass with fixture history retained')
        print(json.dumps({'checked_at_utc': datetime.now(timezone.utc).isoformat(),
                          'postgresql': version, 'image_id': image_id,
                          'network': 'none', 'host_mounts': 0, 'persistent_volumes': 0,
                          'production_connections': 0, 'render_role_verified': False,
                          'sql_copy_method': 'docker exec stdin with SHA-256 verification',
                          'sql_files_verified': names + ['apply_failure.sql'],
                          'reviewed_sql_sha256': {n: hashlib.sha256((source/n).read_bytes()).hexdigest() for n in names},
                          'checks': checks}, indent=2))
    finally:
        if started:
            # Stop only this run's verified disposable container; tmpfs data expires.
            run('docker', 'stop', '--time', '10', identity, good=False)


if __name__ == '__main__':
    main()
