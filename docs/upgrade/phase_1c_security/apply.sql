-- DRAFT: NOT AUTHORIZED FOR PRODUCTION. See ../PHASE_1C_SECURITY_REMEDIATION_PLAN.md.
-- psql only; protected independently verified libpq service. No credentials in argv.
-- Must first pass matching PostgreSQL 17 staging/actual backend-role acceptance.
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL lock_timeout='2s';
SET LOCAL statement_timeout='10s';
\ir target_guard.sql
-- Lock the bounded set so ACL/policy checks and changes cannot race other DDL.
LOCK TABLE public.users, public.user_sessions, public.refresh_tokens IN ACCESS EXCLUSIVE MODE;
DO $state$
DECLARE c record; expected_acl aclitem[];
BEGIN
  FOR c IN SELECT cls.* FROM pg_class cls JOIN pg_namespace n ON n.oid=cls.relnamespace
    WHERE n.nspname='public' AND cls.relname IN
      ('users','user_sessions','refresh_tokens','users_id_seq','user_sessions_id_seq','refresh_tokens_id_seq')
  LOOP
    expected_acl := CASE WHEN c.relkind='S' THEN '{postgres=rwU/postgres,anon=rwU/postgres,authenticated=rwU/postgres,service_role=rwU/postgres}'::aclitem[] ELSE '{postgres=arwdDxtm/postgres,anon=arwdDxtm/postgres,authenticated=arwdDxtm/postgres,service_role=arwdDxtm/postgres}'::aclitem[] END;
    IF pg_get_userbyid(c.relowner) <> 'postgres'
       OR (SELECT array_agg(x::text ORDER BY x::text) FROM unnest(c.relacl) x)
          IS DISTINCT FROM (SELECT array_agg(x::text ORDER BY x::text) FROM unnest(expected_acl) x)
       OR (c.relkind <> 'S' AND (c.relrowsecurity IS DISTINCT FROM false OR c.relforcerowsecurity)) THEN
      RAISE EXCEPTION 'STOP: unexpected ACL/RLS state on %; renewed review required', c.relname;
    END IF;
  END LOOP;
END
$state$;

REVOKE ALL PRIVILEGES ON TABLE public.users, public.user_sessions, public.refresh_tokens
  FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL PRIVILEGES ON SEQUENCE public.users_id_seq, public.user_sessions_id_seq,
  public.refresh_tokens_id_seq FROM PUBLIC, anon, authenticated, service_role;
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.refresh_tokens ENABLE ROW LEVEL SECURITY;
-- No API policies: all three are internal FastAPI tables. Preserve owner/BYPASSRLS.
\ir deny_assertions.sql
COMMIT;
