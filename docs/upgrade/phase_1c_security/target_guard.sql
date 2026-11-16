-- Included by apply/rollback inside a bounded transaction; not standalone.
-- Required psql variables: approval, expected_server_major.
SELECT set_config('blue_panda_security.approval', :'approval', true),
       set_config('blue_panda_security.expected_major', :'expected_server_major', true);
DO $guard$
BEGIN
  IF current_setting('blue_panda_security.approval') <> 'APPROVED_AUTH_TABLE_ACL_WINDOW'
     OR current_database() <> 'postgres'
     OR current_user <> 'postgres' OR session_user <> 'postgres'
     OR current_setting('server_version_num')::int / 10000 <>
        current_setting('blue_panda_security.expected_major')::int
     OR NOT (SELECT rolbypassrls FROM pg_roles WHERE rolname=current_user) THEN
    RAISE EXCEPTION 'STOP: approval, target version, owner session or BYPASSRLS mismatch';
  END IF;
  IF (SELECT array_agg(version_num::text ORDER BY version_num) FROM public.alembic_version)
       IS DISTINCT FROM ARRAY['a1b2c3d4e5f6']::text[] THEN
    RAISE EXCEPTION 'STOP: revision drift; renewed review required';
  END IF;
  IF (SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
      WHERE n.nspname='public' AND c.relname IN ('users','user_sessions','refresh_tokens')
      AND c.relkind='r' AND pg_get_userbyid(c.relowner)='postgres') <> 3
     OR EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public'
                AND tablename IN ('users','user_sessions','refresh_tokens'))
     OR EXISTS (SELECT 1 FROM pg_attribute a
                WHERE a.attrelid IN ('public.users'::regclass,'public.user_sessions'::regclass,
                                    'public.refresh_tokens'::regclass) AND a.attacl IS NOT NULL)
     OR EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
                WHERE n.nspname='public')
     OR EXISTS (SELECT 1 FROM pg_depend d JOIN pg_rewrite rw ON rw.oid=d.objid
                JOIN pg_class c ON c.oid=rw.ev_class
                WHERE d.refobjid IN ('public.users'::regclass,'public.user_sessions'::regclass,
                                    'public.refresh_tokens'::regclass) AND c.relkind IN ('v','m')) THEN
    RAISE EXCEPTION 'STOP: ownership, table, policy, column ACL, function or view drift';
  END IF;
  IF pg_get_serial_sequence('public.users','id') IS DISTINCT FROM 'public.users_id_seq'
     OR pg_get_serial_sequence('public.user_sessions','id') IS DISTINCT FROM 'public.user_sessions_id_seq'
     OR pg_get_serial_sequence('public.refresh_tokens','id') IS DISTINCT FROM 'public.refresh_tokens_id_seq' THEN
    RAISE EXCEPTION 'STOP: sequence binding drift';
  END IF;
END
$guard$;
