-- Metadata only; psql, protected independently verified libpq service.
\set ON_ERROR_STOP on
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout='10s';
SET LOCAL lock_timeout='2s';
DO $$ BEGIN
 IF (SELECT array_agg(version_num::text ORDER BY version_num) FROM public.alembic_version) IS DISTINCT FROM ARRAY['a1b2c3d4e5f6']::text[] THEN
 RAISE EXCEPTION 'STOP: revision drift';
 END IF;
END $$;
-- connection
SELECT current_database()='postgres' AS expected_database, current_user, session_user, current_setting('server_version') AS server_version, current_setting('transaction_read_only') AS read_only, current_setting('transaction_isolation') AS isolation, (SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()) AS pooler_to_database_tls_pg_stat_ssl;

-- tables
SELECT c.relname, pg_get_userbyid(c.relowner) AS owner, c.relrowsecurity AS rls, c.relforcerowsecurity AS force_rls, c.relacl::text AS acl, (SELECT count(*) FROM pg_policy p WHERE p.polrelid=c.oid) AS policies FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname IN ('users','user_sessions','refresh_tokens') ORDER BY c.relname;

-- roles
SELECT rolname, rolsuper, rolinherit, rolcreaterole, rolcreatedb, rolcanlogin, rolreplication, rolbypassrls FROM pg_roles WHERE rolname IN ('anon','authenticated','authenticator','service_role',current_user) ORDER BY rolname;

-- memberships
SELECT a.rolname AS member, b.rolname AS granted_role, m.admin_option, m.inherit_option, m.set_option FROM pg_auth_members m JOIN pg_roles a ON a.oid=m.member JOIN pg_roles b ON b.oid=m.roleid WHERE a.rolname IN ('anon','authenticated','authenticator','service_role',current_user) ORDER BY 1,2;

-- schema
SELECT n.nspname, pg_get_userbyid(n.nspowner) AS owner, n.nspacl::text AS acl FROM pg_namespace n WHERE n.nspname IN ('public','graphql_public') ORDER BY 1;

-- effective_schema
SELECT r.rolname, has_schema_privilege(r.oid,'public','USAGE') AS usage, has_schema_privilege(r.oid,'public','CREATE') AS create FROM pg_roles r WHERE r.rolname IN ('anon','authenticated','authenticator','service_role',current_user) ORDER BY 1;

-- effective_table
SELECT r.rolname,c.relname,p.privilege,has_table_privilege(r.oid,c.oid,p.privilege) AS allowed FROM pg_roles r CROSS JOIN pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace CROSS JOIN (VALUES ('SELECT'),('INSERT'),('UPDATE'),('DELETE'),('TRUNCATE'),('REFERENCES'),('TRIGGER'),('MAINTAIN')) p(privilege) WHERE r.rolname IN ('anon','authenticated','service_role',current_user) AND n.nspname='public' AND c.relname IN ('users','user_sessions','refresh_tokens') ORDER BY 1,2,3;

-- column_acl
SELECT c.relname,a.attname,a.attacl::text AS acl FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname IN ('users','user_sessions','refresh_tokens') AND a.attnum>0 AND NOT a.attisdropped AND a.attacl IS NOT NULL ORDER BY 1,2;

-- sequences
SELECT c.relname,pg_get_userbyid(c.relowner) AS owner,c.relacl::text AS acl FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='S' AND c.oid IN (pg_get_serial_sequence('public.users','id')::regclass,pg_get_serial_sequence('public.user_sessions','id')::regclass,pg_get_serial_sequence('public.refresh_tokens','id')::regclass) ORDER BY 1;

-- defaults
SELECT pg_get_userbyid(d.defaclrole) AS creator,COALESCE(n.nspname,'<global>') AS schema,d.defaclobjtype,d.defaclacl::text AS acl FROM pg_default_acl d LEFT JOIN pg_namespace n ON n.oid=d.defaclnamespace WHERE n.nspname='public' OR d.defaclnamespace=0 ORDER BY 1,2,3;

-- policies
SELECT tablename,policyname,permissive,roles,cmd,qual,with_check FROM pg_policies WHERE schemaname='public' AND tablename IN ('users','user_sessions','refresh_tokens');

-- api_schema_settings
SELECT 'session' AS source, v.name, current_setting(v.name,true) AS value FROM (VALUES ('pgrst.db_schemas'),('pgrst.db_anon_role')) v(name) UNION ALL SELECT COALESCE(r.rolname,'<all>'),split_part(s,'=',1),substring(s from position('=' in s)+1) FROM pg_db_role_setting d LEFT JOIN pg_roles r ON r.oid=d.setrole CROSS JOIN LATERAL unnest(d.setconfig) s WHERE split_part(s,'=',1) IN ('pgrst.db_schemas','pgrst.db_anon_role');

-- public_functions
SELECT p.proname,pg_get_function_identity_arguments(p.oid) AS args,pg_get_userbyid(p.proowner) AS owner,p.prosecdef AS security_definer,p.proacl::text AS acl,has_function_privilege('anon',p.oid,'EXECUTE') AS anon_execute,has_function_privilege('authenticated',p.oid,'EXECUTE') AS authenticated_execute FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' ORDER BY 1,2;

-- dependent_views
SELECT DISTINCT vn.nspname AS schema,v.relname,v.relkind,v.reloptions,v.relacl::text AS acl FROM pg_depend d JOIN pg_rewrite rw ON rw.oid=d.objid JOIN pg_class v ON v.oid=rw.ev_class JOIN pg_namespace vn ON vn.oid=v.relnamespace WHERE d.refobjid IN ('public.users'::regclass,'public.user_sessions'::regclass,'public.refresh_tokens'::regclass) AND v.relkind IN ('v','m') ORDER BY 1,2;

-- extensions
SELECT extname FROM pg_extension WHERE extname IN ('pg_graphql','pgjwt','pgcrypto') ORDER BY 1;
SET LOCAL ROLE anon;
SELECT 1 FROM public.users LIMIT 0;
SELECT 1 FROM public.user_sessions LIMIT 0;
SELECT 1 FROM public.refresh_tokens LIMIT 0;
RESET ROLE;
SET LOCAL ROLE authenticated;
SELECT 1 FROM public.users LIMIT 0;
SELECT 1 FROM public.user_sessions LIMIT 0;
SELECT 1 FROM public.refresh_tokens LIMIT 0;
RESET ROLE;
ROLLBACK;
