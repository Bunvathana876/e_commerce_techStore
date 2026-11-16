"""Disposable Unix-socket-only fixture rehearsal; never consumes DATABASE_URL."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile

source = Path(__file__).resolve().parent
root = Path(tempfile.mkdtemp(prefix='bp-security-rehearsal-', dir='/tmp')).resolve()
sock = root / 'sock'
sock.mkdir()
data = root / 'data'
env = {k:v for k,v in os.environ.items() if not k.startswith('PG') and k != 'DATABASE_URL'}
started = False
checks = []

def run(args, good=True, **kwargs):
    r = subprocess.run(args, env=env, text=True, capture_output=True, **kwargs)
    if good and r.returncode:
        print(r.stderr[:3000])
        raise AssertionError('Fixture command failed')
    return r

def psql(sql=None, file=None, approved=True, good=True):
    args=['psql','-X','-h',str(sock),'-U','postgres','-d','postgres','-v','ON_ERROR_STOP=1','-v','expected_server_major='+major]
    if approved: args += ['-v','approval=APPROVED_AUTH_TABLE_ACL_WINDOW']
    if file: args += ['-f',str(file)]
    else: args += ['-At','-c',sql]
    return run(args,good=good)

try:
    run(['initdb','-D',str(data),'-U','bp_fixture','-A','trust','--no-locale','-E','UTF8'])
    run(['pg_ctl','-D',str(data),'-l',str(root/'postgres.log'),'-w','-o',f"-k {sock} -h '' -F",'start'])
    started=True
    run(['psql','-X','-h',str(sock),'-U','bp_fixture','-d','postgres','-v','ON_ERROR_STOP=1','-c',"CREATE ROLE postgres LOGIN BYPASSRLS; CREATE ROLE anon NOLOGIN; CREATE ROLE authenticated NOLOGIN; CREATE ROLE service_role NOLOGIN BYPASSRLS; GRANT anon,authenticated,service_role TO postgres WITH ADMIN OPTION; ALTER DATABASE postgres OWNER TO postgres;"])
    # Only local Unix socket, disabled TCP, and exact temporary cluster path accepted.
    args=['psql','-X','-h',str(sock),'-U','bp_fixture','-d','postgres','-At','-c']
    assert run(args+["SHOW listen_addresses"]).stdout.strip()==''
    assert Path(run(args+["SHOW data_directory"]).stdout.strip()).resolve()==data
    version=run(args+["SHOW server_version"]).stdout.strip()
    major=version.split('.')[0]
    fixture="CREATE TABLE public.alembic_version(version_num text); INSERT INTO public.alembic_version VALUES ('a1b2c3d4e5f6');"
    for table in ['users','user_sessions','refresh_tokens']:
        fixture+=f"CREATE TABLE public.{table}(id serial PRIMARY KEY); INSERT INTO public.{table} DEFAULT VALUES; GRANT ALL ON TABLE public.{table} TO anon,authenticated,service_role; GRANT ALL ON SEQUENCE public.{table}_id_seq TO anon,authenticated,service_role;"
    psql(sql=fixture)
    snapshot_sql="SELECT json_agg(x ORDER BY relname)::text FROM (SELECT relname,relacl::text,relrowsecurity,relforcerowsecurity FROM pg_class WHERE relnamespace='public'::regnamespace AND (relkind='S' OR relname IN ('users','user_sessions','refresh_tokens'))) x"
    before=psql(sql=snapshot_sql).stdout.strip()
    r=psql(file=source/'apply.sql',approved=False,good=False)
    assert r.returncode and psql(sql=snapshot_sql).stdout.strip()==before
    checks.append('missing approval fails without changes')
    psql(sql="UPDATE public.alembic_version SET version_num='unexpected-fixture'")
    r=psql(file=source/'apply.sql',good=False)
    assert r.returncode and psql(sql=snapshot_sql).stdout.strip()==before
    psql(sql="UPDATE public.alembic_version SET version_num='a1b2c3d4e5f6'")
    checks.append('revision drift fails without changes')
    psql(file=source/'inspect.sql')
    checks.append('metadata inspection parses and completes read-only')
    psql(file=source/'apply.sql')
    psql(file=source/'verify.sql')
    checks.append('apply plus 45 API-role statement denials and privilege assertions')
    psql(sql='GRANT SELECT ON public.users TO anon')
    assert psql(sql='SET ROLE anon; SELECT 1 FROM public.users').stdout.strip() == 'SET'
    psql(sql='REVOKE SELECT ON public.users FROM anon')
    checks.append('RLS default deny hides populated fixture after accidental SELECT regrant')
    # Exercise the same owner/BYPASSRLS capability used by the inspected connection.
    psql(sql='BEGIN; INSERT INTO public.users DEFAULT VALUES; INSERT INTO public.user_sessions DEFAULT VALUES; INSERT INTO public.refresh_tokens DEFAULT VALUES; UPDATE public.users SET id=id; UPDATE public.user_sessions SET id=id; UPDATE public.refresh_tokens SET id=id; SELECT 1 FROM public.users LIMIT 0; DELETE FROM public.refresh_tokens; DELETE FROM public.user_sessions; DELETE FROM public.users; ROLLBACK;')
    checks.append('non-superuser postgres owner/BYPASSRLS CRUD succeeds after apply')
    after=psql(sql=snapshot_sql).stdout.strip()
    r=psql(file=source/'apply.sql',good=False)
    assert r.returncode and psql(sql=snapshot_sql).stdout.strip()==after
    checks.append('repeat apply aborts instead of accepting baseline drift')
    psql(file=source/'rollback.sql')
    assert psql(sql=snapshot_sql).stdout.strip()==before
    checks.append('rollback exactly restores table/sequence ACLs and RLS flags')
    psql(file=source/'apply.sql')
    psql(file=source/'verify.sql')
    checks.append('reapply and negative tests succeed after rollback')
    print(json.dumps({'runtime':version,'production_connections':0,'checks':checks},indent=2))
finally:
    if started: run(['pg_ctl','-D',str(data),'-m','fast','-w','stop'],good=False)
    # Preserve this temporary test directory; no repository or production cleanup.
