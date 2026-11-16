-- psql only. Audit through the existing independently verified Supabase target.
-- Credentials belong in a protected libpq service/pass file, never this file.
-- Expected PRE-MIGRATION revision. A changed revision requires renewed review.
-- Do not run through a web SQL editor that ignores psql ON_ERROR_STOP semantics.
\set ON_ERROR_STOP on

BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '10s';
SET LOCAL lock_timeout = '2s';

-- This is the first application-schema read. Any mismatch aborts the transaction.
DO $$
DECLARE
    revisions text[];
BEGIN
    SELECT array_agg(version_num::text ORDER BY version_num)
      INTO revisions FROM public.alembic_version;
    IF revisions IS DISTINCT FROM ARRAY['a1b2c3d4e5f6']::text[] THEN
        RAISE EXCEPTION 'STOP: unexpected live Alembic revision; renewed review required';
    END IF;
END
$$;

SELECT version_num FROM public.alembic_version;
SELECT current_database() = 'postgres' AS expected_database,
       current_setting('server_version') AS server_version,
       current_setting('transaction_read_only') AS read_only,
       current_setting('transaction_isolation') AS isolation;

-- Catalog metadata only; no account rows, credential hashes or bearer values.
SELECT table_name, column_name, data_type, character_maximum_length,
       is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN ('users', 'user_sessions', 'refresh_tokens', 'sellers')
ORDER BY table_name, ordinal_position;

SELECT c.relname AS table_name, co.contype AS constraint_type,
       pg_get_constraintdef(co.oid) AS definition, co.convalidated AS validated
FROM pg_constraint co
JOIN pg_class c ON c.oid = co.conrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relname IN ('users', 'user_sessions', 'refresh_tokens', 'sellers')
ORDER BY c.relname, co.conname;

SELECT t.relname AS table_name, i.relname AS index_name,
       ix.indisunique, ix.indisvalid, ix.indisready,
       pg_get_indexdef(ix.indexrelid) AS definition
FROM pg_index ix
JOIN pg_class t ON t.oid = ix.indrelid
JOIN pg_class i ON i.oid = ix.indexrelid
JOIN pg_namespace n ON n.oid = t.relnamespace
WHERE n.nspname = 'public'
  AND t.relname IN ('users', 'user_sessions', 'refresh_tokens', 'sellers')
ORDER BY t.relname, i.relname;

SELECT c.relname AS table_name, c.relrowsecurity, c.relforcerowsecurity,
       (SELECT count(*) FROM pg_policy p WHERE p.polrelid = c.oid) AS policies,
       (SELECT count(*) FROM pg_trigger t
         WHERE t.tgrelid = c.oid AND NOT t.tgisinternal) AS custom_triggers,
       (SELECT count(*) FROM pg_rewrite r
         WHERE r.ev_class = c.oid AND r.rulename <> '_RETURN') AS custom_rules
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relname IN ('users', 'user_sessions', 'refresh_tokens')
ORDER BY c.relname;

SELECT r.rolname AS api_role, c.relname AS table_name,
       has_table_privilege(r.oid, c.oid, 'SELECT') AS can_select,
       has_table_privilege(r.oid, c.oid, 'INSERT') AS can_insert,
       has_table_privilege(r.oid, c.oid, 'UPDATE') AS can_update,
       has_table_privilege(r.oid, c.oid, 'DELETE') AS can_delete
FROM pg_roles r CROSS JOIN pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE r.rolname IN ('anon', 'authenticated') AND n.nspname = 'public'
  AND c.relname IN ('users', 'user_sessions', 'refresh_tokens')
ORDER BY r.rolname, c.relname;

SELECT (SELECT count(*) FROM public.users) AS users,
       (SELECT count(*) FROM public.users WHERE role = 'admin' AND is_active) AS active_admins,
       (SELECT count(*) FROM public.users WHERE role = 'seller' AND is_active) AS active_sellers,
       (SELECT count(*) FROM public.users WHERE role = 'customer' AND is_active) AS active_customers,
       (SELECT count(*) FROM public.sellers) AS sellers,
       (SELECT count(*) FROM public.user_sessions) AS sessions,
       (SELECT count(*) FROM public.user_sessions WHERE is_revoked) AS revoked_sessions,
       (SELECT count(*) FROM public.refresh_tokens) AS refresh_tokens,
       (SELECT count(*) FROM public.user_sessions s LEFT JOIN public.users u
         ON u.id = s.user_id WHERE u.id IS NULL) AS orphan_sessions,
       (SELECT count(*) FROM public.refresh_tokens t LEFT JOIN public.user_sessions s
         ON s.session_id = t.session_id WHERE s.session_id IS NULL) AS orphan_refresh_tokens;

ROLLBACK;
