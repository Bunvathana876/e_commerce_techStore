-- Prepared metadata capture only. Not executed against production by this task.
-- psql variable expected_revision must be independently verified by the owner.
\set ON_ERROR_STOP on
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout='10s';
SET LOCAL lock_timeout='2s';
SELECT set_config('blue_panda_backup.expected_revision', :'expected_revision', true) AS reviewed_revision \gset
DO $$ BEGIN
  IF current_database() <> 'postgres'
     OR current_setting('server_version_num')::int / 10000 <> 17
     OR (SELECT array_agg(version_num::text ORDER BY version_num) FROM public.alembic_version)
        IS DISTINCT FROM ARRAY[current_setting('blue_panda_backup.expected_revision')] THEN
    RAISE EXCEPTION 'STOP: recovery source version/revision mismatch';
  END IF;
END $$;
SELECT json_build_object(
  'captured_at_utc', now(),
  'server_version', current_setting('server_version'),
  'read_only', current_setting('transaction_read_only'),
  'revision', (SELECT json_agg(version_num ORDER BY version_num) FROM public.alembic_version),
  'roles', (SELECT json_agg(x ORDER BY rolname) FROM
    (SELECT rolname,rolsuper,rolinherit,rolcreaterole,rolcreatedb,rolcanlogin,
     rolreplication,rolbypassrls,rolconnlimit,rolvaliduntil FROM pg_roles) x),
  'memberships', (SELECT json_agg(x ORDER BY member,granted_role) FROM
    (SELECT a.rolname AS member,b.rolname AS granted_role,m.admin_option,m.inherit_option,m.set_option
     FROM pg_auth_members m JOIN pg_roles a ON a.oid=m.member JOIN pg_roles b ON b.oid=m.roleid) x),
  'schemas', (SELECT json_agg(x ORDER BY nspname) FROM
    (SELECT nspname,pg_get_userbyid(nspowner) AS owner,nspacl::text AS acl FROM pg_namespace
     WHERE nspname IN ('public','graphql_public','extensions')) x),
  'extensions', (SELECT json_agg(x ORDER BY extname) FROM
    (SELECT extname,extversion FROM pg_extension) x),
  'default_privileges', (SELECT json_agg(x ORDER BY creator,schema,objtype) FROM
    (SELECT pg_get_userbyid(d.defaclrole) AS creator,coalesce(n.nspname,'<global>') AS schema,
     d.defaclobjtype AS objtype,d.defaclacl::text AS acl FROM pg_default_acl d
     LEFT JOIN pg_namespace n ON n.oid=d.defaclnamespace
     WHERE n.nspname='public' OR d.defaclnamespace=0) x)
)::text;
ROLLBACK;
