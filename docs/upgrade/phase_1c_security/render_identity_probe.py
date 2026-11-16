"""Read-only probe for an existing running Render service shell, not local proof.

Uses runtime DATABASE_URL without importing app/config/startup. Requires only the
already-installed SQLAlchemy and psycopg2. Supply non-secret expected project ref
and Render service ID; never pass a connection URL, password or token as arguments.
The output contains only runtime provenance, role/permission metadata and booleans.
"""
import argparse
from datetime import datetime, timezone
import json
import os
import re
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool


def probe(expected_project_ref, expected_service_id):
    if not re.fullmatch(r'[a-z0-9]{20}', expected_project_ref):
        raise ValueError('Expected project reference format invalid')
    if not expected_service_id.startswith('srv-') or os.environ.get('RENDER_SERVICE_ID') != expected_service_id:
        raise ValueError('Not the independently verified running Render service')
    raw_url = os.environ['DATABASE_URL']
    if raw_url.startswith('postgres://'):
        raw_url = raw_url.replace('postgres://', 'postgresql+psycopg2://', 1)
    elif raw_url.startswith('postgresql://'):
        raw_url = raw_url.replace('postgresql://', 'postgresql+psycopg2://', 1)
    url = make_url(raw_url)
    if url.drivername != 'postgresql+psycopg2' or url.database != 'postgres':
        raise ValueError('Unexpected driver/database')
    host = url.host or ''
    if host.endswith('.pooler.supabase.com'):
        matched = (url.username or '').rsplit('.', 1)[-1] == expected_project_ref
        mode = {5432: 'session_pooler', 6543: 'transaction_pooler'}.get(url.port, 'unknown_pooler_port')
    else:
        matched = host == 'db.' + expected_project_ref + '.supabase.co'
        mode = 'direct'
    if not matched:
        raise ValueError('Runtime target does not match independently verified project')
    # Preserve runtime URL options (including any role option), but add enforced
    # read-only and bounded-timeout settings last. Never weaken an existing TLS mode.
    query = dict(url.query)
    if any(key in query for key in ('host', 'hostaddr', 'port', 'dbname', 'user', 'password', 'service')):
        raise ValueError('Connection routing overrides require separate target review')
    if query.get('sslmode') in ('disable', 'allow', 'prefer'):
        raise ValueError('Runtime TLS setting is weaker than require')
    query.setdefault('sslmode', 'require')
    query['options'] = str(query.get('options', '')) + ' -c default_transaction_read_only=on -c statement_timeout=10000 -c lock_timeout=2000'
    url = url.set(query=query)
    engine = create_engine(url, poolclass=NullPool, connect_args={'connect_timeout': 10})
    result = {
        'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'expected_service_matches': True,
        'expected_project_matches': True,
        'runtime_commit': os.environ.get('RENDER_GIT_COMMIT'),
        'instance_id_present': bool(os.environ.get('RENDER_INSTANCE_ID')),
        'connection_mode': mode,
        'production_writes': 0,
    }
    try:
        with engine.connect().execution_options(isolation_level='REPEATABLE READ') as conn:
            transaction = conn.begin()
            try:
                conn.execute(text('SET TRANSACTION READ ONLY'))
                # First application-schema read. No auth rows are selected.
                revisions = list(conn.execute(text('SELECT version_num FROM public.alembic_version ORDER BY version_num')).scalars())
                if revisions != ['a1b2c3d4e5f6']:
                    raise ValueError('Revision drift; renewed review required')
                result['revisions'] = revisions
                result['connection'] = dict(conn.execute(text("SELECT current_user AS database_role, session_user AS login_role, current_setting('role') AS configured_role, current_setting('server_version') AS server_version, current_setting('transaction_read_only') AS read_only, current_setting('transaction_isolation') AS isolation")).mappings().one())
                result['client_tls'] = conn.connection.driver_connection.info.ssl_in_use
                result['role_flags'] = dict(conn.execute(text('SELECT rolsuper, rolinherit, rolcanlogin, rolcreaterole, rolcreatedb, rolbypassrls FROM pg_roles WHERE rolname=current_user')).mappings().one())
                result['tables'] = [dict(row) for row in conn.execute(text("SELECT c.relname, pg_get_userbyid(c.relowner) AS owner, pg_has_role(current_user,c.relowner,'USAGE') AS effective_owner_membership, c.relrowsecurity AS rls, c.relforcerowsecurity AS forced_rls, has_schema_privilege(current_user,'public','USAGE') AS schema_usage, has_table_privilege(current_user,c.oid,'SELECT') AS can_select, has_table_privilege(current_user,c.oid,'INSERT') AS can_insert, has_table_privilege(current_user,c.oid,'UPDATE') AS can_update, has_table_privilege(current_user,c.oid,'DELETE') AS can_delete, has_sequence_privilege(current_user,pg_get_serial_sequence('public.'||c.relname,'id'),'USAGE') AS sequence_usage FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname IN ('users','user_sessions','refresh_tokens') ORDER BY c.relname")).mappings()]
                if len(result['tables']) != 3:
                    raise ValueError('Missing expected tables')
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-project-ref', required=True)
    parser.add_argument('--expected-service-id', required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(probe(args.expected_project_ref, args.expected_service_id), indent=2))
    except Exception as error:
        # Exception text can include URL/password, so report type/SQLSTATE only.
        original = getattr(error, 'orig', error)
        print(json.dumps({'status': 'UNVERIFIED', 'error_type': type(error).__name__,
                          'sqlstate': getattr(original, 'pgcode', None), 'details': 'suppressed'}))
        sys.exit(2)
